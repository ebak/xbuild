import sys
import json
import multiprocessing
from task import Task
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
        self.upToDateFiles = set()  # name of files
        self.upToDateTasks = set()  # name of tasks
        self.lock = RLock()
        self.queue = BuildQueue(workers)  # contains QueueTasks TODO !!!
        self.hashDict = HashDict()
        self.metaDict = defaultdict(dict)
        # load db
        self._loadDB()

    def _loadDB(self):
        fpath = '.{}.xbuild'.format(self.name)
        if not self.fs.isfile(fpath):
            return
        try:
            jsonObj = json.loads(self.fs.read(fpath)) # loads for easier unit test
        except:
            self.warnf("'{}' is corrupted! JSON load failed!", fpath)
            raise
            return
        if type(jsonObj) is not dict:
            self.warnf("'{}' is corrupted! Top level dict expected!", fpath)
            return
        hashDictJsonObj = jsonObj.get('HashDict')
        if not hashDictJsonObj:
            self.warnf("'{}' is corrupted! 'HashDict' section is missing!", fpath)
            return
        if not self.hashDict._loadJsonObj(hashDictJsonObj, self.warnf):
            self.warnf("'{}' is corrupted! Failed to load 'HashDict'!", fpath)
            return
        metaJsonObj = jsonObj.get('Meta')
        if not metaJsonObj:
            self.warnf("'{}' is corrupted! 'Meta' section is missing!", fpath)
            return
        if type(metaJsonObj) is not dict:
            self.warnf("'{}' is corrupted! 'Meta' section is not dict!", fpath)
            return
        for name, value in metaJsonObj.items():
            self.metaDict[name].update(value)

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
        self.fs.write(fpath, json.dumps(jsonObj, indent=1))  # dumps for easier unit test

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
        
    def __handleTaskCompletition(self, task):
        # called in locked context
        if not task.pendingFileDeps and not task.pendingTaskDeps:
            # task is ready to build
            self.queue.add(QueueTask(self, task))

    def _markTargetUpToDate(self, target):
        with self.lock:
            self.upToDateFiles.add(target)
            for task in self.parentTaskDict[target]:
                assert target in task.pendingFileDeps
                task.pendingFileDeps.remove(target) # could raise KeyError
    
    def _markTaskUpToDate(self, taskName):
        with self.lock:
            self.upToDateTasks.add(taskName)
            for task in self.parentTaskDict[taskName]:
                assert taskName in task.pendingTaskDeps
                task.pendingTaskDeps.remove(taskName) # could raise KeyError

    def __putTaskToBuildQueue(self, task, prio=[]):
        assert isinstance(task, Task)
        # lock is handled by caller
        # --- handle dependencies
        targetPrio = prio + [task.prio]
        for taskDep in task.pendingTaskDeps:
            assert taskDep not in self.upToDateTasks
            taskDepTask = self.targetTaskDict.get(taskDep)
            if taskDepTask is None:
                self.errorf("Task '{}' refers to a not existing task '{}'!", task.getId(), taskDep)
                return False
            return self.__putTaskToBuildQueue(taskDepTask, targetPrio)
        for fileDep in task.pendingFileDeps.copy():
            if not self._putFileToBuildQueue(fileDep, targetPrio):
                return False
        if not task.pendingFileDeps and not task.pendingFileDeps:
            # When a task is completed and provides files and or tasks, build those
            # before the task is marked completed.
            xdebug("HERE")
            if task.upToDate or task.action:
                self.queue.add(QueueTask(self, task))
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
            if nameOrTarget in self.upToDateTasks:
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
            self._putToBuildQueue(target)
        xdebug("Starting queue")
        self.queue.start()
        if self.queue.rc:
            errorf("BUILD FAILED! exitCode: {}", self.queue.rc)
        else:
            info("BUILD PASSED!")
        self._saveDB()
        
    
    def check(self):
        # TODO: find cycles
        pass
