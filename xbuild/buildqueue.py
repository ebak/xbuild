import traceback
from time import sleep
from sortedcontainers import SortedList
from threading import Lock, RLock, Semaphore, Thread, Condition
from prio import prioCmp
from task import TState
from console import logger, info, infof, warn, warnf, error, errorf

class Worker(Thread):

    def __init__(self, queue, wid):
        super(Worker, self).__init__(name="Wrk{}".format(wid))
        self.queue = queue
        self.id = wid

    def run(self):
        logger.debug("started")
        while True:
            queueTask = self.queue.get()
            logger.debugf("fetched task: {}", queueTask.task.getId() if queueTask else 'None')
            if queueTask:
                queueTask.execute()
            else:
                return


class BuildQueue(object):

    def __init__(self, numWorkers):
        self.sortedList = SortedList()

        self.cnd = Condition(RLock())   # TODO: Is Condition inner implementation is wrong? Is it possible to do it well?
        self.numWorkers = numWorkers
        self.waitingWorkers = 0
        self.workers = None # thread can be started only once
        # build is finished when all the workers are waiting
        self.finished = False
        self.rc = 0

    def add(self, queueTask):
        assert isinstance(queueTask, QueueTask)
        logger.debugf("queue.add('{}')", queueTask.task.getId())
        with self.cnd:
            self.sortedList.add(queueTask)
            if len(self.sortedList) == 1:   # this doesn't help also
                self.cnd.notify()

    def isFinished(self):
        with self.cnd:
            # xdebugf("isFinished()={}", self.finished)
            return self.finished

    def setFinished(self):
        # xdebug("setFinished()")
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

        with self.cnd:
            if self.numWorkers == 1:
                # simple case, 1 worker
                return getTask() if len(self.sortedList) and not self.finished else None
            else:
            # TODO: there is still race condition !!!
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
            worker.start()
        for worker in self.workers:
            logger.debugf("Joining worker {}", worker.id)
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
            else:
                self.logUpToDate()
            return True
                    
        def runAction():
            act = self.task.action
            if act:
                # self.logBuild()
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
            self.logBuild()
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
            # self.builder.hashDict.storeTaskHashes(self.builder, self.task)  # FIXME: should it be moved for custom task actions? 
            # -- build provided dependencies if there are any
            if self.task.providedFiles or self.task.providedTasks:
                # the task can be marked up-to-date when provided files and tasks are built
                logger.debugf('{} has provided files or tasks', self.task.getId())
                self.builder._updateProvidedDepends(self.task)
                for fileDep in self.task.providedFiles:
                    if not self.builder._putFileToBuildQueue(fileDep, self.task.requestedPrio):
                        self.builder.queue.stop(1)
                        return
                for taskDep in self.task.providedTasks:
                    if not self.builder._putTaskToBuildQueue(taskDep, self.task.requestedPrio):
                        self.builder.queue.stop(1)
                        return
            else:
                logger.debugf('Build of {} is completed', self.task.getId())
                # -- task completed, notify parents
                self.builder._handleTaskBuildCompleted(self.task)

