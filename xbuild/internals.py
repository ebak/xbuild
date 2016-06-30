from sortedcontainers import SortedList
from threading import Lock, Semaphore, Thread

class UserData(object):
    pass


class Worker(Thread):

    def __init__(self, queue):
        super(Worker, self).__init__()
        self.queue = queue

    def run(self):
        while True:
            queueTask = self.queue.get()
            if queueTask:
                queueTask.execute()
            else:
                return


class BuildQueue(object):

    def __init__(self, numWorkers):
        self.sortedList = SortedList()
        self.lock = Lock()
        self.sem = Semaphore(0)
        self.workers = [Worker(self) for _ in range(numWorkers)]
        # build is finished when all the workers are waiting
        self.waitingWorkers = 0
        self.finished = False
        self.rc = 0

    def add(self, queueTask):
        assert isinstance(queueTask, QueueTask)
        with self.lock:
            self.add(queueTask)
            self.sem.release()  # ++counter

    def get(self):

        def getTask():
            queueTask = self.sortedList[0]
            del self.sortedList[0]        
            return queueTask
        
        def finishBuild():
            self.finished = True
            self.waitingWorkers -= 1
            for _ in range(self.waitingWorkers):
                self.sem.release()  # ++counter, wake up other workers
            
        with self.lock:
            if self.sem.acquire(blocking=False):  # --counter
                self.waitingWorkers -= 1
                return None if self.finished else getTask()
            else:   # could not acquire semaphore, queue is empty
                self.waitingWorkers += 1
                if self.waitingWorkers >= len(self.workers):
                    # all the workers are waiting, build is finished
                    finishBuild()
                    return None
                else:
                    self.sem.acquire()  # --counter
                    self.waitingWorkers -= 1
                    return None if self.finished else getTask()

    def start(self):
        for worker in self.workers:
            worker.start()
        for worker in self.workers:
            worker.join()

    def stop(self, rc):
        with self.lock:
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
        self.builder.errorf('{}: {} failed! Return code: {}', self.task.getName(), what, rc)

    def logUpToDate(self):
        self.builder.infof('{} is up-to-date.', self.task.getName())

    def logBuild(self):
        self.builder.infof('Building {}.', self.task.getName())

    def _execute(self):
        '''Returns 0 at success'''
        def runAction():
            act = self.task.action
            if act:
                self.logBuild()
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
            self.builder.queue.stop(1)
        else:
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

