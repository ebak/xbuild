import sys
import json
import multiprocessing
from task import Task, TState
from threading import RLock
from collections import defaultdict
from fs import FS
from hash import HashDict
from buildqueue import BuildQueue, QueueTask
from console import write, xdebug, xdebugf, info, infof, warn, warnf, error, errorf


class Builder(object):

    def __init__(self, name='default', workers=0, fs=FS()):
        self.name = name    # TODO avoid duplicates
        self.workers = workers if workers else multiprocessing.cpu_count() + 1
        self.fs = fs
        self.targetTaskDict = {}    # {targetName: task}
        self.nameTaskDict = {}      # {taskName: task}
        self.parentTaskDict = defaultdict(list) # {target or task name: [parentTask]}
        self.providerTaskDict = {}  # {target or task name: providerTask}
        self.upToDateFiles = set()  # name of files
        self.lock = RLock()
        self.queue = BuildQueue(workers)  # contains QueueTasks TODO !!!
        self.hashDict = HashDict()
        self.metaDict = defaultdict(dict)
        # load db
        self._loadDB()

    def _getRequestedTasks(self):
        taskDict =  {task.getId(): task for task in self.nameTaskDict.values()}
        return [task for task in taskDict.values() if task.requestedPrio]

    def _isTaskUpToDate(self, taskName):
        task = self.nameTaskDict.get(taskName)
        return task and task.state  == TState.Built

    def _loadDB(self):
        fpath = '.{}.xbuild'.format(self.name)
        if not self.fs.isfile(fpath):
            return
        try:
            jsonObj = json.loads(self.fs.read(fpath)) # loads for easier unit test
        except:
            warnf("'{}' is corrupted! JSON load failed!", fpath)
            raise
            return
        if type(jsonObj) is not dict:
            warnf("'{}' is corrupted! Top level dict expected!", fpath)
            return
        hashDictJsonObj = jsonObj.get('HashDict')
        if not hashDictJsonObj:
            warnf("'{}' is corrupted! 'HashDict' section is missing!", fpath)
            return
        if not self.hashDict._loadJsonObj(hashDictJsonObj, warnf):
            warnf("'{}' is corrupted! Failed to load 'HashDict'!", fpath)
            return
        metaJsonObj = jsonObj.get('Meta')
        if not metaJsonObj:
            warnf("'{}' is corrupted! 'Meta' section is missing!", fpath)
            return
        if type(metaJsonObj) is not dict:
            warnf("'{}' is corrupted! 'Meta' section is not dict!", fpath)
            return
        for name, value in metaJsonObj.items():
            self.metaDict[str(name)].update(value)

    def _saveDB(self):
        jsonObj = {'version': [0, 0, 0]}
        jsonObj['HashDict'] = self.hashDict._toJsonObj()
        # metaDict
        meta = {}
        meta.update(self.metaDict)
        for task in (self.targetTaskDict.values() + self.nameTaskDict.values()):
            taskId = task.getId()
            if taskId not in meta:
                meta[taskId] = task.meta
        jsonObj['Meta'] = meta
        fpath = '.{}.xbuild'.format(self.name)
        self.fs.write(fpath, json.dumps(jsonObj, ensure_ascii=True, indent=1))  # dumps for easier unit test

    def addTask(
        self, name=None, targets=[], fileDeps=[], taskDeps=[], upToDate=None, action=None, prio=0
    ):
        with self.lock:
            for trg in targets:
                if trg in self.targetTaskDict:
                    raise ValueError("There is already a task for target '{}'!".format(trg))
                if trg in self.nameTaskDict:
                    raise ValueError("There is already a task named '{}'!".format(trg))
            if name:
                if name in self.nameTaskDict:
                    raise ValueError("There is already a task named '{}'!".format(name))
                if name in self.targetTaskDict:
                    raise ValueError("There is already a task for target '{}'!".format(name))
            task = Task(
                name, targets, fileDeps, taskDeps, upToDate, action, prio,
                meta=None)
            task.meta = self.metaDict[task.getId()]
            for trg in targets:
                self.targetTaskDict[trg] = task
            if name:
                self.nameTaskDict[name] = task
            for fileDep in fileDeps:
                self.parentTaskDict[fileDep].append(task)
            for taskDep in taskDeps:
                self.parentTaskDict[taskDep].append(task)

    def _updateProvidedDepends(self, task):
        with self.lock:
            if task.providedFileDeps:
                task.waitsForBuildOfProvidedStuff = True
                for provFile in task.providedFileDeps:
                    self.providerTaskDict[provFile] = task
                    task.pendingProvidedFiles.add(provFile)
            if task.providedTaskDeps:
                task.waitsForBuildOfProvidedStuff = True
                for provTask in task.providedTaskDeps:
                    self.providerTaskDict[provTask] = task
                    task.pendingTaskDeps.add(provTask)
        
    def __checkAndHandleTaskDepCompletition(self, task):
        def queueIfRequested():
            if task.requestedPrio:
                xdebugf("put to queue: {}", task)
                task.state = TState.Queued
                self.queue.add(QueueTask(self, task))
        # called in locked context
        # debugf("depCompleted?: {}", task)
        if task.state < TState.Ready:
            if not task.pendingFileDeps and not task.pendingTaskDeps:
                task.state = TState.Ready
                queueIfRequested()
        elif task.state == TState.Ready:
            queueIfRequested()

    def __checkAndHandleProvidedDepCompletition(self, task):
        # must be called from locked context
        if not task.pendingProvidedFiles and not task.pendingProvidedTasks:
            self._handleTaskBuildCompleted(task)

    def __markParentTasks(self, name, getPendingDepsFn, getPendingProvidedFn):
        # called within lock
        providerTask = self.providerTaskDict.get(name)
        if providerTask:
            assert name in getPendingProvidedFn(providerTask)
            getPendingProvidedFn(providerTask).remove(name)
            del self.providerTaskDict[name]
            self.__checkAndHandleProvidedDepCompletition(providerTask)
        else:
            for parentTask in self.parentTaskDict[name]:
                if parentTask.state < TState.Queued:
                    # TODO  What to do if task is queued, not built and its requestedPrio changes?
                    assert name in getPendingDepsFn(parentTask)
                    getPendingDepsFn(parentTask).remove(name)
                    self.__checkAndHandleTaskDepCompletition(parentTask)

    def _markTargetUpToDate(self, target):
        def getPendingDeps(task):
            return task.pendingFileDeps
        def getPendingProvided(task):
            return task.pendingProvidedFiles
        with self.lock:
            if target not in self.upToDateFiles:
                # debugf('targetUpToDate: {}', target)
                self.upToDateFiles.add(target)
                self.__markParentTasks(target, getPendingDeps, getPendingProvided)

    def _markTaskUpToDate(self, task):
        def getPendingDeps(task):
            return task.pendingTaskDeps
        def getPendingProvided(task):
            return task.pendingProvidedTasks
        with self.lock:
            if not task.state == TState.Built:
                task.state = TState.Built
                # debugf('taskUpToDate: {}', task)
                self.__markParentTasks(task.name, getPendingDeps, getPendingProvided)

    def _handleTaskBuildCompleted(self, task):
        with self.lock:
            if task.name:   
                self._markTaskUpToDate(task)
            else:
                task.state = TState.Built                    
            for trg in task.targets:
                self._markTargetUpToDate(trg)

    def __putTaskToBuildQueue(self, task, prio=[]):
        assert isinstance(task, Task)
        # lock is handled by caller
        # --- handle dependencies
        assert isinstance(prio, list)
        targetPrio = prio + [task.prio]
        for taskDepName in task.pendingTaskDeps:
            assert not self._isTaskUpToDate(taskDepName)
            depTask = self.nameTaskDict.get(taskDepName)
            if depTask is None:
                errorf("Task '{}' refers to a not existing task '{}'!", task.getId(), taskDepName)
                return False
            # depTask is requested but not yet placed to build queue TODO
            # depTask._setRequestPrio(targetPrio + [depTask.prio])
            if not self.__putTaskToBuildQueue(depTask, targetPrio):
                return False
        for fileDep in task.pendingFileDeps.copy():
            if not self._putFileToBuildQueue(fileDep, targetPrio):
                return False
        task._setRequestPrio(targetPrio)
        self.__checkAndHandleTaskDepCompletition(task)
        return True
    
    def _putFileToBuildQueue(self, fpath, prio=[]):
        with self.lock:
            if fpath in self.upToDateFiles:
                infof("File '{}' is up-to-date.", fpath)
                return True # success
            task = self.targetTaskDict.get(fpath)
            if task is None:
                if self.fs.exists(fpath):
                    self._markTargetUpToDate(fpath)
                    return True
                errorf("No task to make file '{}'!", fpath)
                return False
            return self.__putTaskToBuildQueue(task, prio)

    def _putTaskToBuildQueue(self, taskName, prio=[]):
        with self.lock:
            task = self.nameTaskDict.get(taskName)
            if task is None:
                errorf("No task named '{}'!", taskName)
                return False
            return self.__putTaskToBuildQueue(task, prio)
        
    # task deps have to be built 1st
    def _putToBuildQueue(self, nameOrTarget, prio=[]):
        with self.lock:
            if nameOrTarget in self.upToDateFiles:
                infof("File '{}' is up-to-date.", nameOrTarget)
                return True # success
            if self._isTaskUpToDate(nameOrTarget):
                infof("Task '{}' is up-to-date.", nameOrTarget)
                return True
            task = self.targetTaskDict.get(nameOrTarget)
            if task is None:
                task = self.nameTaskDict.get(nameOrTarget)
            if task is None:
                if self.fs.exists(nameOrTarget):
                    self._markTargetUpToDate(nameOrTarget)
                    return True
                errorf("No task to make target '{}'!", nameOrTarget)
                return False
            return self.__putTaskToBuildQueue(task, prio)

    def buildOne(self, target):
        return self.build([target])
    
    
    def build(self, targets):
        for target in targets:
            if not self._putToBuildQueue(target):
                errorf("BUILD FAILED! exitCode: {}", 1)
                return 1
        xdebug("Starting queue")
        self.queue.start()
        if self.queue.rc:
            errorf("BUILD FAILED! exitCode: {}", self.queue.rc)
        else:
            info("BUILD PASSED!")
        self._saveDB()
        return self.queue.rc
        
    
    def check(self):
        # TODO: find cycles
        pass
