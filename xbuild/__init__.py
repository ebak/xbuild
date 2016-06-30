import os
import sys
import json
import hashlib
import multiprocessing
from threading import Lock
from collections import defaultdict

from internals import UserData, QueueTask, BuildQueue


class HashEnt(object):

    @staticmethod
    def calcHash(content):
        return hashlib.md5(content).hexdigest()

    @staticmethod
    def _loadJsonObj(jsonObj, warnfFn):
        if type(jsonObj) is not str:
            warnfFn("HashEnt._loadJsonObj(): str entry expected!")
            return None
        return HashEnt(jsonObj, None)
    
    def __init__(self, old=None, new=None):
        self.old, self.new = old, new

    def matches(self):
        return False if self.old is None else self.old == self.new

    def setByContent(self, content):
        self.new = HashEnt.calcHash(content)

    def setByFile(self, fpath):
        if not os.path.isfile(fpath):
            return
        with open(fpath) as f:
            return self.setByContent(f.read())

    def _toJsonObj(self):
        return self.new if self.new else self.old
        

class HashDict(object):


    def __init__(self):
        self.lock = Lock()
        self.nameHashDict = defaultdict(HashEnt)

    def _loadJsonObj(self, jsonObj, warnfFn):
        if type(jsonObj) is not dict:
            warnfFn("HashDict._sloadJsonObj(): dict is expected!")
            return False
        warns = 0
        for name, hashEntObj in jsonObj:
            hashEnt = HashEnt._loadJsonObj(hashEntObj, warnfFn)
            if hashEnt:
                warns += 1
                self.nameHashDict[name] = hashEnt
        return False if warns else True
    
    def _toJsonObj(self):
        return {name: hashEnt._toJsonObj() for name, hashEnt in self.nameHashDict.items()}

    def get(self, name):
        with self.lock:
            return self.nameHashDict.get(name)

    def storeTargetHashes(self, task):
        '''It should be called by the action function at the end.'''
        for trg in task.targets:
            hashEnt = self.nameHashDict.get(trg)
            if not hashEnt.new:
                hashEnt.setByFile(trg)



def targetUpToDate(bldr, task, **kvArgs):
    # if dependencies are not changed, targets also need check
    def checkFileDeps(fileDeps):
        for fileDep in fileDeps:
            hashEnt = bldr.hashDict.get(fileDep)
            if hashEnt.new is None:
                # there can be file dependencies coming from outside the build process 
                hashEnt.setByFile(fileDep)
            if not bldr.hashEnt.matches():
                return False

    checkFileDeps(task.fileDeps)
    for taskDep in task.taskDeps:
        if not checkFileDeps(taskDep.providedFileDeps):
            return False
    # File dependencies are not changed. Now check the targets.
    for trg in task.targets:
        hashEnt = bldr.hashDict.get(trg)
        if hashEnt.new is None:
            hashEnt.setByFile(trg)
        if not hashEnt.matches():
            return False
    return True


class Task(object):

    def __init__(
        self, name=None, targets=[], fileDeps=[], taskDeps=[],
        upToDate=None, action=None, prio=0, meta={}
    ):
        '''e.g.: upToDate or action = (function, {key: value,...})
        function args: builder, task, **kvargs'''
        # TODO: type check, taskName
        self.name = name
        self.targets = targets
        self.fileDeps = fileDeps
        self.taskDeps = taskDeps
        self.pendingFileDeps = set(fileDeps)
        self.pendingTaskDeps = set(taskDeps)
        self.upToDate = upToDate
        self.action = action
        self.meta = meta  # json serializable dict
        # dependency calculator tasks need to fill these fields
        self.providedFileDeps = []
        self.providedTaskDeps = []
        # task related data can be stored here which is readable by other tasks
        self.userData = UserData

    def getId(self):
        '''Returns name if has or 1st target otherwise'''
        return self.name if self.name else self.targets[0]
        


class Builder(object):

    def __init__(self, name='default', workers=0):
        self.name = name    # TODO avoid duplicates
        self.workers = workers if workers else multiprocessing.cpu_count() + 1
        self.targetTaskDict = {}    # {targetName: task}
        self.nameTaskDict = {}      # {taskName: task}
        self.parentTaskDict = defaultdict(list) # {target or task name: [parentTask]}
        self.upToDateFiles = set()  # name of files
        self.upToDateTasks = set()  # name of tasks
        self.lock = Lock()
        self.consoleLock= Lock()
        self.queue = BuildQueue(workers)  # contains QueueTasks TODO !!!
        self.hashDict = HashDict()
        self.metaDict = defaultdict(dict)
        # load db
        self._loadDB()

    def _loadDB(self):
        fpath = '.{}.xbuild'.format(self.name)
        if not os.path.isfile(fpath):
            return
        with open(fpath) as f:
            try:
                jsonObj = json.load(f)
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
        meta = {}.update(self.metaDict)
        for _, task in (self.targetTaskDict + self.nameTaskDict).values():
            taskId = task.getId()
            if taskId not in meta:
                meta[taskId] = task.meta
        jsonObj['Meta'] = meta
        fpath = '.{}.xbuild'.format(self.name)
        with open(fpath, 'w') as f:
            json.dump(jsonObj, f, indent=1)

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

    def write(self, msg, out=sys.stdout):
        with self.consoleLock:
            out.write(msg)
    
    def error(self, msg):
        self.write('ERROR: ' + msg + '\n', out=sys.stderr)
    
    def errorf(self, msg, *args, **kvargs):
        self.error(msg.format(*args, **kvargs))
    
    def info(self, msg):
        self.write('INFO: ' + msg + '\n')
    
    def infof(self, msg, *args, **kvargs):
        self.info(msg.format(*args, **kvargs))
        
    def warn(self, msg):
        self.write('WARNING: ' + msg + '\n')
    
    def warnf(self, msg, *args, **kvargs):
        self.warn(msg.format(*args, **kvargs))
        

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
        if task.taskDeps:
            # --- taskDeps
            for taskDep in task.taskDeps:
                if taskDep not in self.upToDateTasks:
                    taskDepTask = self.targetTaskDict.get(taskDep)
                    if taskDepTask is None:
                        self.errorf("Task '{}' refers to a not existing task '{}'!", task.getId(), taskDep)
                        return False
                    return self.__putTaskToBuildQueue(taskDepTask, targetPrio)
        elif task.fileDeps:
            # --- no need to wait for taskDeps
            # --- fileDeps
            for fileDep in task.fileDeps:
                if not self._putFileToBuildQueue(fileDep, targetPrio):
                    return False
        else:
            # --- there are no dependencies
            # When a task is completed and provides files and or tasks, build those
            # before the task is marked completed.
            if task.upToDate or task.action:
                self.queue.add(QueueTask(self, task))
        return True
    
    def _putFileToBuildQueue(self, fpath, prio=[]):
        with self.lock:
            if fpath in self.upToDateFiles:
                self.infof("File '{}' is up-to-date.", fpath)
                return True # success
            task = self.targetTaskDict.get(fpath)
            if task is None:
                if os.path.exists(fpath):
                    self._markTargetUpToDate(fpath)
                    return True
                self.errorf("No task to make file '{}'!", fpath)
                return False
            return self.__putTaskToBuildQueue(task, prio)

    def _putTaskToBuildQueue(self, taskName, prio=[]):
        with self.lock:
            task = self.nameTaskDict.get(taskName)
            if task is None:
                self.errorf("No task named '{}'!", taskName)
            return self.__putTaskToBuildQueue(task, prio)
        
    # task deps have to be built 1st
    def _putToBuildQueue(self, nameOrTarget, prio=[]):
        with self.lock:
            if nameOrTarget in self.upToDateFiles:
                self.infof("File '{}' is up-to-date.", nameOrTarget)
                return True # success
            if nameOrTarget in self.upToDateTasks:
                self.infof("Task '{}' is up-to-date.", nameOrTarget)
                return True
            task = self.targetTaskDict.get(nameOrTarget)
            if task is None:
                task = self.nameTaskDict.get(nameOrTarget)
            if task is None:
                if os.path.exists(nameOrTarget):
                    self._markTargetUpToDate(nameOrTarget)
                    return True
                self.errorf("No task to make target '{}'!", nameOrTarget)
                return False
            return self.__putTaskToBuildQueue(task, prio)

    def buildOne(self, target):
        return self.build([target])
    
    
    def build(self, targets):
        for target in targets:
            self._putTaskToBuildQueue(target)
        self.queue.start()
        if self.queue.rc:
            self.errorf("BUILD FAILED! exitCode: {}", self.queue.rc)
        else:
            self.info("BUILD PASSED!")
        self._saveDB()
        
    
    def check(self):
        # TODO: find cycles
        pass
