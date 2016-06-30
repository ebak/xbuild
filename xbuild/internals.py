from sortedcontainers import SortedList
from multiprocessing import Lock

class UserData(object):
    pass


class BuildQueue(object):

    def __init__(self):
        self.sortedList = SortedList()
        self.lock = Lock()

    def add(self, queueTask):
        assert isinstance(queueTask, QueueTask)
        with self.lock:
            self.add(queueTask)


class QueueTask(object):

    def __init__(self, builder, task):
        self.builder = builder
        self.prio = task.prio
        self.task = task

    def __cmp__(self, o):
        chkLen = min(len(self.prio), len(o.prio))
        for i in range(chkLen):
            diff = self.prio[i] - o.prio[i]
            if diff:
                return diff
        return 0
    
    def logFailure(self, what, rc):
        self.builder.errorf('{}: {} failed! Return code: {}', self.task.getName(), what, rc)

    def logLogUpToDate(self):
        self.builder.infof('{} is up-to-date.', self.task.getName())

    def _execute(self):
        '''Returns 0 at success'''
        def runAction():
            act = self.task.action
            if act:
                self.builder.infof('Building {}.', self.task.getName())
                kvArgs = utd[1] if len(utd) >= 2 else {}
                res = act[0](self.builder, self.task, **kvArgs)
                if res:
                    self.logFailure('action', res)
                return res
                    
            return 0

        utd = self.task.upToDate
        if utd:
            kvArgs = utd[1] if len(utd) >= 2 else {}
            res = utd[0](self.builder, self.task, **kvArgs)
            if type(res) is int:
                self.logFailure('up-to-date check', res)
                return res
            if res:
                self.logUpToDate()
            else:
                return runAction()
        else:
            return runAction()
    
    def execute(self):
        if self._execute():
            self.builder.stop()
        else:
            # -- build provided dependencies if there are any
            if self.task.providedFileDeps or self.task.providedTaskDeps:
                for fileDep in self.task.providedFileDeps:
                    if not self.builder._putFileToBuildQueue(fileDep, self.task.prio):
                        self.builder.stop()
                        return
                for taskDep in self.task.providedTaskDeps:
                    if not self.builder._putTaskToBuildQueue(taskDep, self.task.prio):
                        self.builder.stop()
                        return
            else:
                # -- task completed, notify parents
                if self.task.name:   
                    self.builder._markTaskUpToDate(self.task.name)
                for trg in self.task.targets:
                    self.builder._markTargetUpToDate(trg)
