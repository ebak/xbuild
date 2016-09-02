import traceback
import threading
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
                self.queue.release(queueTask)
            elif queueTask is None:
                return
            else:
                assert False
            # next iteration if queueTask is False

# TODO: this class may not be needed, it slows down the execution
class SyncVars(object):

    def __init__(self, numWorkers):
        self.numWorkers = numWorkers
        self.waitingWorkers = set()
        self.finished = False

    def isFinished(self):
        # with self.lock:
        logger.debugf("finished={}", self.finished)
        return self.finished

    def setFinished(self):
        # with self.lock:
        logger.debug("setFinished()")
        self.finished = True

    def incWaitingWorkers(self):
        '''Returns True when all workers are waiting'''
        # with self.lock:
        thrName = threading.current_thread().name
        assert thrName not in self.waitingWorkers
        self.waitingWorkers.add(thrName)
        res = len(self.waitingWorkers) >= self.numWorkers
        logger.debugf("res={}, waitingWorkers={}", res, self.waitingWorkers)
        return res

    def decWaitingWorkers(self):
        # with self.lock:
        thrName = threading.current_thread().name
        self.waitingWorkers.remove(thrName)
        logger.debugf("waitingWorkers={}", self.waitingWorkers)

    def getNumOfWaitingWorkers(self):
        # with self.lock:
        return len(self.waitingWorkers)

    def getNumOfRunningWorkers(self):
        return self.numWorkers - len(self.waitingWorkers)

class BuildQueue(object):

    def __init__(self, numWorkers):
        self.sortedList = SortedList()

        self.cnd = Condition(RLock())
        self.numWorkers = numWorkers
        self.sync = SyncVars(numWorkers)
        self.workers = None # thread can be started only once
        # build is finished when all the workers are waiting
        self.greedyRun = False
        self.loadedGreedyTask = None
        self.loadedQueueTask = None
        self.rc = 0
        self.exclGroups = set()

    def _excluded(self, queueTask):
        if not queueTask.task.exclGroup:
            return False
        return queueTask.task.exclGroup in self.exclGroups

    def add(self, queueTask):
        assert isinstance(queueTask, QueueTask)
        with self.cnd:
            logger.debugf("queue.add('{}')", queueTask.task.getId())
            notify = False
            # print("queue.add('{}')", queueTask.task.getId())
            self.sortedList.add(queueTask)
            if self.loadedQueueTask is None and self.sync.getNumOfWaitingWorkers() > 0:
                self.loadedQueueTask = self._getTask()
                if self.loadedQueueTask is not None:
                    notify = True
                    logger.debug('notify()')
                    self.cnd.notify()
        # note, it is not good to notify if there are at least 1 running worker. FIXME: why?
        if notify:
            # Yielding is needed because when worker 'A' adds a task and wakes up worker 'B', worker 'B'
            # must be able to fetch the newly added task. When we not yield here, worker 'A' can fetch the task
            # from worker 'B' which causes race condition issue.
            sleep(0.01)    # yield

    def _getTask(self):
        # check self.sync.getNumOfWaitingWorkers() == 0 from caller if needed
        if self.greedyRun:
            return None
        if self.loadedGreedyTask:
            if self.sync.getNumOfWaitingWorkers() >= self.sync.numWorkers - 1:
                queueTask = self.loadedGreedyTask
                self.loadedGreedyTask = None
                self.greedyRun = True
                return queueTask
            else:
                return None
        if len(self.sortedList) > 0:
            for i in range(len(self.sortedList)):
                queueTask = self.sortedList[i]
                if not self._excluded(queueTask):
                    del self.sortedList[i]
                    grp = queueTask.task.exclGroup
                    if grp:
                        self.exclGroups.add(grp)
                    if queueTask.task.greedy:
                        if self.sync.getNumOfWaitingWorkers() >= self.sync.numWorkers - 1:
                            self.greedyRun = True
                            return queueTask
                        else:
                            self.loadedGreedyTask = queueTask
                            return None
                    return queueTask
            return None        
            
    def get(self):
        with self.cnd:
            logger.debug('get()')
            if self.sync.isFinished():
                return None
            if self.numWorkers == 1:
                # simple case, 1 worker
                if not len(self.sortedList):
                    self.sync.setFinished()
                    return None
                else:
                    queueTask = self.sortedList[0]
                    del self.sortedList[0]
                    return queueTask
            else:
                # Don't fetch task if someone else is waiting !!!
                # Here the waiting worker is woken up and this worker would fetch the 
                # task before it, which causes race condition problem. 
                queueTask = None if self.sync.getNumOfWaitingWorkers() > 0 else self._getTask()
                if queueTask is not None:
                    return queueTask
                else:
                    logger.debug('no schedulable queue entry')
                    if self.sync.incWaitingWorkers():
                        # all workers are waiting, finish build
                        if self.loadedGreedyTask is None:
                            self.sync.setFinished()
                            logger.debugf('notifyAll')
                            self.cnd.notifyAll()
                            queueTask = None
                        else:
                            queueTask = self.loadedGreedyTask
                            self.loadedGreedyTask = None
                            self.greedyRun = True
                        self.sync.decWaitingWorkers()
                        return queueTask
                    logger.debug('wait()')
                    self.cnd.wait()
                    logger.debug('wait() passed')
                    self.sync.decWaitingWorkers()
                    queueTask = self.loadedQueueTask
                    self.loadedQueueTask = None
                    return queueTask

    def release(self, queueTask):
        with self.cnd:
            grp = queueTask.task.exclGroup
            if grp is not None:
                self.exclGroups.remove(grp)
            self.greedyRun = False
            notify = False
            # TODO: in case of greedy wait all workers should be woken up somehow.
            # MAybe loadedQueueTask / worker?
            if self.loadedQueueTask is None and self.sync.getNumOfWaitingWorkers() > 0:
                self.loadedQueueTask = self._getTask()
                if self.loadedQueueTask is not None:
                    notify = True
                    logger.debug('notify()')
                    self.cnd.notify()
        if notify:
            sleep(0.01) # Thread.yield()

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
        self.pf = self.builder.db.pathFormer
        self.prio = task.requestedPrio
        assert self.prio
        self.task = task

    def __cmp__(self, o):
        return prioCmp(self.prio, o.prio)

    def getTaskId(self):
        return self.pf.encode(self.task.getId())
    
    def logFailure(self, what, rc):
        errorf('{}: {} failed! Return code: {}', self.getTaskId(), what, rc)

    def logUpToDate(self):
        infof('{} is up-to-date.', self.getTaskId())

    def logBuild(self):
        infof('Building {}.', self.getTaskId())

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
                # reset task's generated and provided files before action run
                self.task.generatedFiles = []
                self.task.providedFile = []
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
            errorf("Exception in upToDate of task '{}': {} msg: '{}'", self.getTaskId(), type(e), e)
            traceback.print_exc()
            return 1
        
        if utdRet: # task upToDate
            return 0
    
        try:
            self.logBuild()
            return runAction()
        except Exception as e:
            # TODO dump exception trace
            errorf("Exception in action of task '{}': {} msg: '{}'", self.getTaskId(), type(e), e)
            traceback.print_exc()
            return 1
        
    
    def execute(self):
        if self._execute():
            # upToDate or action FAILED
            self.builder.queue.stop(1)
        else:
            # upToDate or action PASSED
            try:
                # inject generated dependencies
                if self.task.generatedFiles or self.task.providedFiles or self.task.providedTasks:
                    # the task can be marked up-to-date when provided files and tasks are built
                    logger.debugf('{} has provided files or tasks', self.getTaskId())
                    # Tasks for generated files needs to be added even if the generator task is up-to-date.
                    # If the generator task is up-to-date, the intermediate files between the provided files
                    # and generated files may be changed.
                    self.builder._executeTaskFactory(self.task)
                    self.builder._injectGenerated(self.task)
                # else:
                logger.debugf('Build of {} is completed', self.getTaskId())
                # -- task completed, notify parents
                self.builder._handleTaskBuildCompleted(self.task)
            except Exception as e:
                # e.g. calculating task data hashes may fail
                errorf("Exception in task '{}': {} msg: '{}'", self.getTaskId(), type(e), e)
                traceback.print_exc()

