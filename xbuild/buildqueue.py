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

# TODO: this class may not be needed, it slows down the execution
class SyncVars(object):

    def __init__(self, numWorkers):
        self.numWorkers = numWorkers
        self.waitingWorkers = 0
        self.finished = False
        self.lock = RLock()

    def isFinished(self):
        with self.lock:
            logger.debugf("finished={}", self.finished)
            return self.finished

    def setFinished(self):
        with self.lock:
            logger.debug("setFinished()")
            self.finished = True

    def incWaitingWorkers(self):
        '''Returns True when all workers are waiting'''
        with self.lock:
            self.waitingWorkers += 1
            res = self.waitingWorkers >= self.numWorkers
            logger.debugf("res={}, waitingWorkers={}", res, self.waitingWorkers)
            return res

    def decWaitingWorkers(self):
        with self.lock:
            self.waitingWorkers -= 1
            logger.debugf("waitingWorkers={}", self.waitingWorkers)

class BuildQueue(object):

    def __init__(self, numWorkers):
        self.sortedList = SortedList()

        self.cnd = Condition(RLock())   # TODO: Is Condition inner implementation is wrong? Is it possible to do it well?
        self.numWorkers = numWorkers
        self.sync = SyncVars(numWorkers)
        self.workers = None # thread can be started only once
        # build is finished when all the workers are waiting
        self.rc = 0

    def add(self, queueTask):
        assert isinstance(queueTask, QueueTask)
        with self.cnd:
            logger.debugf("queue.add('{}')", queueTask.task.getId())
            notify = not len(self.sortedList)
            self.sortedList.add(queueTask)
            if notify:
                self.cnd.notify()
        if notify:
            # Yielding is needed because when worker 'A' adds a task and wakes up worker 'B', worker 'B'
            # must be able to fetch the newly added task. When we not yield here, worker 'A' can fetch the task
            # from worker 'B' which causes race condition issue.
            sleep(0.01)    # yield
            
    def get(self):

        def getTask():
            queueTask = self.sortedList[0]
            del self.sortedList[0]        
            return queueTask

        with self.cnd:
            if self.sync.isFinished():
                return None
            if self.numWorkers == 1:
                # simple case, 1 worker
                if not len(self.sortedList):
                    self.sync.setFinished()
                    return None
                else:
                    return getTask()
            else:
                if len(self.sortedList) > 0:
                    return getTask()
                else:
                    if self.sync.incWaitingWorkers():
                        # self.stop(0) doesn't help
                        self.sync.setFinished()  # moving to function doesn't help
                        logger.debugf('notifyAll')
                        self.cnd.notifyAll()
                        self.sync.decWaitingWorkers()
                        return None
                    self.cnd.wait()
                    self.sync.decWaitingWorkers()
                    return None if self.sync.isFinished() else getTask()

    def start(self):
        if self.sync.isFinished():
            raise NotImplementedError("Builder instance can be used only once.")
        self.rc = 0
        if not len(self.sortedList):
            info("All targets are up-to-date. Nothing to do.")
            self.sync.setFinished()
            return
        self.workers = [Worker(self, i) for i in range(self.numWorkers)]
        for worker in self.workers:
            worker.start()
        for worker in self.workers:
            logger.debugf("Joining worker {}", worker.id)
            worker.join()

    def stop(self, rc):
        logger.debugf('rc={}', rc)
        with self.cnd:
            self.rc = rc
            self.sync.setFinished()
            self.cnd.notifyAll()

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
                res = self.task._runCallback(utd, self.builder)
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
                res = self.task._runCallback(act, self.builder)
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
            try:
                # TODO: revise -- build provided dependencies if there are any
                if self.task.providedFiles or self.task.providedTasks:
                    # the task can be marked up-to-date when provided files and tasks are built
                    logger.debugf('{} has provided files or tasks', self.task.getId())
                    # Tasks for generated files needs to be added even if the generator task is up-to-date.
                    # If the generator task is up-to-date, the intermediate files between the provided files
                    # and generated files may be changed.
                    self.builder._executeTaskFactory(self.task)
                    self.builder._injectGenerated(self.task)
                    if False: # TODO: remove
                        self.builder._updateProvidedDepends(self.task)
                        for provFile in self.task.providedFiles:
                            if not self.builder._putFileToBuildQueue(provFile, self.task.requestedPrio):
                                self.builder.queue.stop(1)
                                return
                        for provTask in self.task.providedTasks:
                            if not self.builder._putTaskToBuildQueue(provTask, self.task.requestedPrio):
                                self.builder.queue.stop(1)
                                return
                else:
                    logger.debugf('Build of {} is completed', self.task.getId())
                    # -- task completed, notify parents
                    self.builder._handleTaskBuildCompleted(self.task)
            except Exception as e:
                # e.g. calculating task data hashes may fail
                errorf("Exception in task '{}': {} msg: '{}'", self.task.getId(), type(e), e)
                traceback.print_exc()

