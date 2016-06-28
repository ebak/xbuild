import os
from multiprocessing import Lock
from sortedcontainers import SortedList
from collections import defaultdict

from internals import UserData

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
        


class Builder(object):

    def __init__(self, name='default'):
        # TODO: taskName related dict
        self.targetTaskDict = {}    # {targetName: task}
        self.fileDepParentTaskDict = defaultdict(list) # {fileDep: [parentTask]}
        self.taskDepParentTaskDict = defaultdict(list) # {fileDep: [parentTask]}
        self.upToDateNodes = set()  # name of targets or files
        self.lock = Lock()
        self.buildQueue = SortedList()  # contains QueueTasks

    def addTask(
        self, name=None, targets=[], fileDeps=[], taskDeps=[], upToDate=None, action=None, prio=0
    ):
        with self.lock:
            for trg in targets:
                if trg in self.targetTaskDict:
                    raise ValueError("There is already a task for target '{}'!".format(trg))
            task = Task(name, targets, fileDeps, taskDeps, upToDate, action, prio)
            for trg in targets:
                self.targetTaskDict[trg] = task
            for dep in fileDeps + taskDeps:
                self.parentTaskDict[dep].append(task)
                
    # task deps have to be built 1st
    def _fillBuildQueue(self, target, prio=[]):
        with self.lock:
            if target in self.upToDateNodes:
                self.infof("Target '{}' is up-to-date.", target)
                return True # success
            task = self.targetTaskDict.get(target)
            if task is None:
                self.errorf("No task to make target '{}'!", target)
                return False
            # --- handle dependencies
            targetPrio = prio + [task.prio]
            if task.taskDeps:
                # --- taskDeps
                for taskDep in target.taskDeps:
                    if taskDep not in self.upToDateNodes:
                        taskDepTask = self.targetTaskDict.get(taskDep)
                        if taskDepTask is None:
                            self.errorf("Target '{}' refers to a not existing task '{}'!", target, taskDep)
                            return False
                        self._fillBuildQueue(taskDepTask, targetPrio)
            elif task.fileDeps:
                # --- no need to wait for taskDeps
                # --- fileDeps
                for fileDep in target.fileDeps:
                    if fileDep not in self.upToDateNodes:
                        if fileDep in self.targetTaskDict:
                            self._fillBuildQueue(fileDep, targetPrio)
                        else:
                            if os.path.isfile(fileDep):
                                self.upToDateNodes.add(fileDep)
            else:
                # --- there are no dependencies
                if task.upToDate:
                    self.buildQueue.add(UpToDateTask(self, task, task.upToDate))
                elif task.action:
                    self.buildQueue.add(ActionTask(self, task, task.action))

    def buildOne(self, target):
        pass
    
    def check(self):
        # TODO: find cycles
        pass
             