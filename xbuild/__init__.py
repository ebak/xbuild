import os
from multiprocessing import Lock
from sortedcontainers import SortedList


# FIXME: no need for calcDeps, taskDeps could substitute them?

class Task(object):

    def __init__(
        self, targets, fileDeps=[], calcDeps=[], taskDeps=[], upToDate=None, action=None,
        prio=0
    ):
        self.targets = targets
        self.fileDeps = fileDeps
        self.calcDeps = []
        self.taskDeps = taskDeps
        self.upToDate = upToDate
        self.action = action
        self.meta = {}  # json serializable dict
        # these fields are used when the task calculates dependencies
        self.providedFileDeps = []
        self.providedTaskDeps = []
        self.providedCalcDeps = []
        self.pendingDependCount = 0    # handled by the builder
        


class Builder(object):

    def __init__(self, name='default'):
        self.targetRuleDict = {}    # {targetName: task}
        self.upToDateNodes = set()  # name of targets or files
        self.lock = Lock()
        self.buildQueue = SortedList()  # contains QueueTasks

    def addTask(
        self, targets, fileDeps=[], calcDeps=[], taskDeps=[], upToDate=None, action=None,
        prio=0
    ):
        with self.lock:
            for trg in targets:
                if trg in self.targetRuleDict:
                    raise ValueError("There is already a task for target '{}'!".format(trg))
            task = Task(targets, fileDeps, calcDeps, taskDeps, upToDate, action, prio)
            for trg in targets:
                self.targetRuleDict[trg] = task

    def _fillBuildQueue(self, target, prio=[]):
        with self.lock:
            if target in self.upToDateNodes:
                self.infof("Target '{}' is up-to-date.", target)
                return True # success
            task = self.targetRuleDict.get(target)
            if task is None:
                self.errorf("No rule to make target '{}'!", target)
                return False
            # --- handle dependencies
            targetPrio = prio + [task.prio]
            # --- fileDeps
            for fileDep in target.fileDeps:
                if fileDep not in self.upToDateNodes:
                    if fileDep in self.targetRuleDict:
                        self._fillBuildQueue(fileDep, targetPrio)
                    else:
                        if os.path.isfile(fileDep):
                            self.upToDateNodes.add(fileDep)
            # --- taskDeps

    def buildOne(self, target):
        pass
             