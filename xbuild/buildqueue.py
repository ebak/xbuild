from time import sleep
from sortedcontainers import SortedList
from threading import Lock, RLock, Semaphore, Thread
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

        self.getLock = Lock()
        self.canWaitSem = Semaphore(numWorkers - 1)
        self.metaLock = RLock()
        self.listLock = RLock()
        self.listSem = Semaphore(0)
        
        self.workers = [Worker(self, i) for i in range(numWorkers)]
        # build is finished when all the workers are waiting
        self.waitingWorkers = 0
        self.finished = False
        self.rc = 0

    def add(self, queueTask):
        assert isinstance(queueTask, QueueTask)
        xdebug("queue add")
        with self.listLock:
            self.sortedList.add(queueTask)
            self.listSem.release()  # ++counter

    def get(self):

        def getTask():
            queueTask = self.sortedList[0]
            del self.sortedList[0]        
            return queueTask
        
        def getTaskThreadSafe():
            with self.listLock:
                return getTask()

        if len(self.workers) == 1:
            # simple case, 1 worker
            return getTask() if len(self.sortedList) else None
        else:
            self.getLock.acquire()
            if not self.canWaitSem.acquire(blocking=False):
                self.finished = True
                for _ in range(len(self.workers) - 1):
                    self.listSem.release()
                self.getLock.release()
                return None
            else:
                with self.metaLock:
                    self.getLock.release()
                    self.listSem.acquire()
                    self.canWaitSem.release()
                    return None if self.finished else getTaskThreadSafe()

    def start(self):
        for worker in self.workers:
            xdebug("Starting worker {}".format(worker.id))
            worker.start()
        for worker in self.workers:
            xdebug("Joining worker {}".format(worker.id))
            worker.join()

    def stop(self, rc):
        with self.metaLock:
            self.rc = rc
            self.finished = True


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
        errorf('{}: {} failed! Return code: {}', self.task.getName(), what, rc)

    def logUpToDate(self):
        infof('{} is up-to-date.', self.task.getName())

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
            return 1
        
        if utdRet: # task upToDate
            return 0
    
        try:
            return runAction()
        except Exception as e:
            # TODO dump exception trace
            errorf("Exception in action of task '{}': {} msg: '{}'", self.task.getId(), type(e), e)
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
                    self.builder._markTaskUpToDate(self.task.name)
                for trg in self.task.targets:
                    self.builder._markTargetUpToDate(trg)

