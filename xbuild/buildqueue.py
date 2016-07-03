import traceback
from time import sleep
from sortedcontainers import SortedList
from threading import Lock, RLock, Semaphore, Thread, Condition
from prio import prioCmp
from task import TState
from console import write, xdebug, xdebugf, info, infof, warn, warnf, error, errorf

class Worker(Thread):

    def __init__(self, queue, wid):
        super(Worker, self).__init__()
        self.queue = queue
        self.id = wid

    def debugf(self, msg, *args):   # TODO: optimize
        xdebugf("Worker{}: ".format(self.id) + msg, args)

    def run(self):
        # self.debugf("started")
        while True:
            queueTask = self.queue.get()
            # self.debugf("fetched task") # TODO: optimize
            if queueTask:
                queueTask.execute()
            else:
                return


class BuildQueue(object):

    def __init__(self, numWorkers):
        self.sortedList = SortedList()

        self.cnd = Condition(RLock())
        self.numWorkers = numWorkers
        self.waitingWorkers = 0
        self.workers = None # thread can be started only once
        # build is finished when all the workers are waiting
        self.finished = False
        self.rc = 0

    def add(self, queueTask):
        assert isinstance(queueTask, QueueTask)
        xdebugf("queue.add('{}')", queueTask.task.getId())
        with self.cnd:
            self.sortedList.add(queueTask)
            if len(self.sortedList) == 1:   # this doesn't help also
                self.cnd.notify()

    def isFinished(self):
        with self.cnd:
            xdebugf("isFinished()={}", self.finished)
            return self.finished

    def setFinished(self):
        xdebug("setFinished()")
        with self.cnd:
            self.finished = True

    def incWaitingWorkers(self):
        with self.cnd:
            self.waitingWorkers += 1

    def decWaitingWorkers(self):
        with self.cnd:
            self.waitingWorkers -= 1

    def allWorkersAreWaiting(self):
        with self.cnd:
            return self.waitingWorkers >= self.numWorkers
            
    def get(self):

        def getTask():
            queueTask = self.sortedList[0]
            del self.sortedList[0]        
            return queueTask

        if self.numWorkers == 1:
            # simple case, 1 worker
            return getTask() if len(self.sortedList) and not self.finished else None
        else:
            # TODO: there is still race condition !!!
            with self.cnd:
                if self.isFinished():
                    return None
                if len(self.sortedList) > 0:
                    return getTask()
                else:
                    self.incWaitingWorkers()
                    if self.allWorkersAreWaiting():
                        # self.stop(0) doesn't help
                        self.setFinished()  # moving to function doesn't help
                        self.cnd.notifyAll()
                        self.decWaitingWorkers()
                        return None
                    self.cnd.wait()
                    self.decWaitingWorkers()
                    return None if self.isFinished() else getTask()

    def start(self):
        self.rc = 0
        self.finished = False
        if not len(self.sortedList):
            info("All targets are up-to-date. Nothing to do.")
            self.finished = True
            return
        self.workers = [Worker(self, i) for i in range(self.numWorkers)]
        for worker in self.workers:
            xdebug("Starting worker {}".format(worker.id))
            worker.start()
        for worker in self.workers:
            xdebug("Joining worker {}".format(worker.id))
            worker.join()

    def stop(self, rc):
        with self.cnd:
            self.rc = rc
            self.finished = True

class QueueTask(object):

    def __init__(self, builder, task):
        self.builder = builder
        self.prio = task.requestedPrio
        assert self.prio
        self.task = task

    def __cmp__(self, o):
        return prioCmp(self.prio, o.prio)
    
    def logFailure(self, what, rc):
        errorf('{}: {} failed! Return code: {}', self.task.getId(), what, rc)

    def logUpToDate(self):
        infof('{} is up-to-date.', self.task.getId())

    def logBuild(self):
        infof('Building {}.', self.task.getId())

    def _execute(self):
        '''Returns 0 at success'''

        def runUpToDate():
            utd = self.task.upToDate
            if utd:
                kvArgs = utd[1] if len(utd) >= 2 else {}
                res = utd[0](self.builder, self.task, **kvArgs)
                if type(res) is int:
                    self.logFailure('up-to-date check', res)
                    return res
                if res:
                    self.logUpToDate()
                return res
            return True
                    
        def runAction():
            act = self.task.action
            if act:
                self.logBuild()
                kvArgs = act[1] if len(act) >= 2 else {}
                res = act[0](self.builder, self.task, **kvArgs)
                if res:
                    self.logFailure('action', res)
                return res   
            return 0
    
        try:
            utdRet = runUpToDate()
            if type(utdRet) is int:
                return utdRet
        except Exception as e:
            # TODO dump exception trace
            errorf("Exception in upToDate of task '{}': {} msg: '{}'", self.task.getId(), type(e), e)
            traceback.print_exc()
            return 1
        
        if utdRet: # task upToDate
            return 0
    
        try:
            return runAction()
        except Exception as e:
            # TODO dump exception trace
            errorf("Exception in action of task '{}': {} msg: '{}'", self.task.getId(), type(e), e)
            traceback.print_exc()
            return 1
        
    
    def execute(self):
        if self._execute():
            # upToDate or action FAILED
            self.builder.queue.stop(1)
        else:
            # upToDate or action PASSED
            self.builder.hashDict.storeTaskHashes(self.builder.fs, self.task)  # FIXME: should it be moved for custom task actions? 
            # -- build provided dependencies if there are any
            if self.task.providedFileDeps or self.task.providedTaskDeps:
                for fileDep in self.task.providedFileDeps:
                    if not self.builder._putFileToBuildQueue(fileDep, self.task.prio):
                        self.builder.queue.stop(1)
                        return
                for taskDep in self.task.providedTaskDeps:
                    if not self.builder._putTaskToBuildQueue(taskDep, self.task.prio):
                        self.builder.queue.stop(1)
                        return
            else:
                # -- task completed, notify parents
                if self.task.name:   
                    self.builder._markTaskUpToDate(self.task)
                else:
                    self.task.state = TState.Built                    
                for trg in self.task.targets:
                    self.builder._markTargetUpToDate(trg)

