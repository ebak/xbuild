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
        self.cnd = Condition(RLock())
        self.queueTask = None
        self.stopRequest = False

    def __hash__(self):
        return self.id

    def __eq__(self, o):
        return self.id == o.id

    def run(self):
        logger.debug("started")
        while True:
            with self.cnd:
                self.queue.regWaiter(self)
                if self.stopRequest:
                    break
                if self.queueTask is None:
                    self.cnd.wait()
                    if self.stopRequest:
                        break
            queueTask = self.queueTask
            self.queueTask = None
            assert queueTask is not None
            logger.debugf("got task: {}", queueTask.task.getId())    
            queueTask.execute()
            self.queue.release(queueTask)
        logger.debug('stopped')

    def setQueueTask(self, queueTask):
        '''This function is called by the feeder from the queue.'''
        assert self.queueTask is None
        with self.cnd:
            self.queueTask = queueTask
            self.cnd.notify()   # TODO: yield? Notify only when waits?

    def stop(self):
        with self.cnd:
            self.stopRequest = True
            self.cnd.notify()


class BuildQueue(object):

    def __init__(self, numWorkers):
        self.sortedList = SortedList()

        self.lock = Lock()
        self.numWorkers = numWorkers
        self.workers = None # thread can be started only once
        self.waitingWorkers = []    # for small amount of threads (<=32) list could be faster than set().
        self.greedyRun = False
        self.loadedGreedyTask = None
        self.loadedQueueTask = None
        self.finished = False
        self.rc = 0
        self.exclGroups = set()

    def _excluded(self, queueTask):
        if not queueTask.task.exclGroup:
            return False
        return queueTask.task.exclGroup in self.exclGroups

    def _feedWorkers(self):
        # locked by caller
    
        def stopWorkers():
            for worker in self.waitingWorkers:
                worker.stop()

        def feedWorker(queueTask):
            worker = self.waitingWorkers.pop(0)
            worker.setQueueTask(queueTask)

        if self.finished:
            stopWorkers()
            return
        while len(self.waitingWorkers):
            if self.greedyRun:
                return
            if self.loadedGreedyTask:
                if len(self.waitingWorkers) == self.numWorkers:
                    queueTask = self.loadedGreedyTask
                    self.loadedGreedyTask = None
                    self.greedyRun = True
                    feedWorker(queueTask)
                return
            if len(self.sortedList) > 0:
                taskTaken = False
                for i in range(len(self.sortedList)):
                    queueTask = self.sortedList[i]
                    if not self._excluded(queueTask):
                        taskTaken = True
                        del self.sortedList[i]
                        grp = queueTask.task.exclGroup
                        if grp:
                            self.exclGroups.add(grp)
                        if queueTask.task.greedy:
                            if len(self.waitingWorkers) == self.numWorkers:
                                self.greedyRun = True
                                feedWorker(queueTask)
                            else:
                                self.loadedGreedyTask = queueTask
                            return
                        else:
                            feedWorker(queueTask)
                        break
                # leave if queueTask is not taken
                if not taskTaken:
                    return
            else:
                if len(self.waitingWorkers) == self.numWorkers:
                    # No task in queue and all workers are waiting. Stop build!
                    self.finished = True
                    stopWorkers()
                return

    def add(self, queueTask):
        assert isinstance(queueTask, QueueTask)
        with self.lock:
            logger.debugf("queue.add('{}')", queueTask.task.getId())
            self.sortedList.add(queueTask)

    def regWaiter(self, worker):
        with self.lock:
            self.waitingWorkers.append(worker)
            self._feedWorkers()

    def release(self, queueTask):
        with self.lock:
            grp = queueTask.task.exclGroup
            if grp is not None:
                self.exclGroups.remove(grp)
            self.greedyRun = False

    def start(self):
        if self.finished:
            raise NotImplementedError("Builder instance can be used only once.")
        self.rc = 0
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
        logger.debugf('rc={}', rc)
        with self.lock:
            self.rc = rc
            self.finished = True


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

