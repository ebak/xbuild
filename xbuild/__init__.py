import os
from multiprocessing import Lock
from sortedcontainers import SortedList
from collections import defaultdict

from internals import UserData, QueueTask

class Task(object):

    def __init__(
        self, name=None, targets=[], fileDeps=[], taskDeps=[],
        upToDate=None, action=None, prio=0
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
        self.meta = {}  # json serializable dict
        # dependency calculator tasks need to fill these fields
        self.providedFileDeps = []
        self.providedTaskDeps = []
        # task related data can be stored here which is readable by other tasks
        self.userData = UserData

    def getId(self):
        '''Returns name if has or 1st target otherwise'''
        return self.name if self.name else self.targets[0]
        


class Builder(object):

    def __init__(self, name='default'):
        # TODO: taskName related dict
        self.targetTaskDict = {}    # {targetName: task}
        self.nameTaskDict = {}      # {taskName: task}
        self.fileDepParentTaskDict = defaultdict(list) # {fileDep: [parentTask]}
        self.taskDepParentTaskDict = defaultdict(list) # {taskDep: [parentTask]}
        self.upToDateFiles = set()  # name of files
        self.upToDateTasks = set()  # name of tasks
        self.lock = Lock()
        self.buildQueue = SortedList()  # contains QueueTasks

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
            task = Task(name, targets, fileDeps, taskDeps, upToDate, action, prio)
            for trg in targets:
                self.targetTaskDict[trg] = task
            if name:
                self.nameTaskDict[name] = task
            for fileDep in fileDeps:
                self.fileDepParentTaskDict[fileDep].append(task)
            for taskDep in taskDeps:
                self.taskDepParentTaskDict[taskDep].append(task)

    def __putTaskToBuildQueue(self, task, prio=[]):
        # lock is handled by caller
        # --- handle dependencies
        targetPrio = prio + [task.prio]
        if task.taskDeps:
            # --- taskDeps
            for taskDep in task.taskDeps:
                if taskDep not in self.upToDateNodes:
                    taskDepTask = self.targetTaskDict.get(taskDep)
                    if taskDepTask is None:
                        self.errorf("Task '{}' refers to a not existing task '{}'!", task.getId(), taskDep)
                        return False
                    self.__putTaskToBuildQueue(taskDepTask, targetPrio)
        elif task.fileDeps:
            # --- no need to wait for taskDeps
            # --- fileDeps
            for fileDep in task.fileDeps:
                if fileDep not in self.upToDateNodes:
                    if fileDep in self.targetTaskDict:
                        self._fillBuildQueue(fileDep, targetPrio)
                    else:
                        if os.path.isfile(fileDep):
                            self.upToDateFiles.add(fileDep)
                        else:
        else:
            # --- there are no dependencies
            # TODO: execute upToDate and Action from one queue task
            # TODO: when a task is completed and provides files and or tasks, build those
            #       before the task is marked completed
            if task.upToDate or task.action:
                self.buildQueue.add(QueueTask(self, task))
        return True
 
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
                    self.upToDateFiles.add(nameOrTarget)
                    return True
                self.errorf("No task to make target '{}'!", nameOrTarget)
                return False
            return self.__putTaskToBuildQueue(task, prio)

    def buildOne(self, target):
        pass
    
    def check(self):
        # TODO: find cycles
        pass
             