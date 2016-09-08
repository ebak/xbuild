import multiprocessing
from cStringIO import StringIO
from task import Task, TState, CheckType
from threading import RLock
from collections import defaultdict
from db import DB
from fs import FS
from prio import prioCmp
from callbacks import targetUpToDate, fetchAllDynFileDeps
from buildqueue import BuildQueue, QueueTask
from console import write, logger, info, infof, cinfof, warn, warnf, error, errorf
from pathformer import NoPathFormer


def calcNumOfWorkers(workers):
    '''This function is useful for unit testing. It should be overwritten for setting the number of workers threads
    in a test collection.'''
    return workers if workers else multiprocessing.cpu_count() + 1


class Builder(object):

    def __init__(
        self, name='default', workers=0, fs=FS(), pathFormer=NoPathFormer(), printUpToDate=False,
        hashCheck=True
    ):
        self.pathFormer = pathFormer
        self.db = DB.create(name, fs, pathFormer)
        self.workers = calcNumOfWorkers(workers)
        self.fs = fs
        self.printUpToDate = printUpToDate
        self.hashCheck = hashCheck
        self.targetTaskDict = {}    # {targetName: task}
        self.nameTaskDict = {}      # {taskName: task}
        # self.idTaskDict = {}        # {taskId: task}    # TODO use
        self.parentTaskDict = defaultdict(set) # {target or task name: set([parentTask])}
        self.providerTaskDict = {}  # {target or task name: providerTask} # TODO: remove
        self.upToDateFiles = set()  # name of files
        self.lock = RLock()
        self.queue = BuildQueue(self.workers, printUpToDate=self.printUpToDate)  # contains QueueTasks
        # load db
        self.db.load()

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.db.forget()

    def needsHashCheck(self, task):
        return self.hashCheck if task.checkType is None else task.checkType == CheckType.Hash

    def encodePath(self, fpath):
        return self.pathFormer.encode(fpath)

    def _getTaskByName(self, name):
        with self.lock:
            return self.nameTaskDict.get(name)

    def _getTaskById(self, taskId):
        with self.lock:
            task = self.targetTaskDict.get(taskId)
            if task is None:
                task = self.nameTaskDict.get(taskId)
            return task

    def _taskExists(self, task, prefix=''):
        '''Returns True if exists, False if doesn't exist. Raises ValueError if exists with different content.'''
        with self.lock:
            oTsk = self._getTaskById(task.getId())
            if oTsk:
                if oTsk == task:
                    return True
                else:
                    raise ValueError(
                        "{}There is already a task for id '{}' with different content!". format(
                            prefix, task.getId()))
            return False

    def _getRequestedTasks(self):
        taskDict =  {task.getId(): task for task in self.nameTaskDict.values()}
        return [task for task in taskDict.values() if task.requestedPrio]

    def _isTaskUpToDate(self, taskName):
        task = self.nameTaskDict.get(taskName)
        return task and task.state == TState.Built

    def _addTask(self, task):
        with self.lock:
            for trg in task.targets:
                if trg in self.targetTaskDict:
                    raise ValueError("There is already a task for target '{}'!".format(trg))
                if trg in self.nameTaskDict:
                    raise ValueError("There is already a task named '{}'!".format(trg))
            if task.name:
                if task.name in self.nameTaskDict:
                    raise ValueError("There is already a task named '{}'!".format(task.name))
                if task.name in self.targetTaskDict:
                    raise ValueError("There is already a task for target '{}'!".format(task.name))
            for trg in task.targets:
                self.targetTaskDict[trg] = task
            if task.name:
                self.nameTaskDict[task.name] = task
            for fileDep in task.fileDeps:
                self.parentTaskDict[fileDep].add(task)
            for taskDep in task.taskDeps:
                self.parentTaskDict[taskDep].add(task)
            # fill up task with saved data
            self.db.loadTask(task)

    def addTask(
        self, name=None, targets=None, fileDeps=None, taskDeps=None, dynFileDepFetcher=fetchAllDynFileDeps, taskFactory=None,
        upToDate=targetUpToDate, action=None, prio=0, exclGroup=None, greedy=False, checkType=None, summary=None, desc=None,
        skipIfExists=False
    ):
        '''Adds a Task to the dependency graph.'''
        task = Task(
            name=name, targets=targets, fileDeps=fileDeps, taskDeps=taskDeps, dynFileDepFetcher=dynFileDepFetcher,
            taskFactory=taskFactory, upToDate=upToDate, action=action, prio=prio, exclGroup=exclGroup, greedy=greedy,
            checkType=checkType, summary=summary, desc=desc)
        if skipIfExists:
            if self._taskExists(task):
                return
        self._addTask(task)

    def _executeTaskFactory(self, task):
        if task.taskFactory:
            factory, kwargs = task.taskFactory  # TODO: Task._runCallback
            tasks = factory(self, task, **kwargs)
            tid = task.getId()
            with self.lock:
                for tsk in tasks:
                    if not self._taskExists(tsk, "taskFactory of task '{}': ".format(tid)):
                        self._addTask(tsk)

    def _injectGenerated(self, genTask):
        '''Injects task's generated and provided files into its parents.'''
        needToBuild = {}    # {providedFile: requestPrio}
        with self.lock:
            for parentTask in self.parentTaskDict[genTask.getId()]:   # {target or task name: [parentTask]}
                _, newProvFiles = parentTask._injectDynDeps(genTask)
                for pFile in newProvFiles:
                    self.parentTaskDict[pFile].add(parentTask)
                if parentTask._isRequested():
                    # TODO: request build only for provided files
                    for pFile in newProvFiles:
                        prio = needToBuild.get(pFile)
                        if prio is not None:
                            if prioCmp(prio, parentTask.requestedPrio) < 0:
                                needToBuild[pFile] = parentTask.requestedPrio
                        else:
                            needToBuild[pFile] = parentTask.requestedPrio
            # print '>>>> needToBuild: {}'.format(needToBuild.keys())
            for pFile, prio in needToBuild.items():
                if not self._putFileToBuildQueue(pFile, prio):
                    return # TODO: error handling
            # generated files don't need any build
        
    def __checkAndHandleTaskDepCompletition(self, task):
        def queueIfRequested():
            '''Task dependencies can be satisfied, but don't have to be built if not requested.'''
            if task.requestedPrio:
                logger.debugf("put to queue: {}", task)
                task.state = TState.Queued
                self.queue.add(QueueTask(self, task))
        # called in locked context
        # debugf("depCompleted?: {}", task)
        if task.state < TState.Ready:
            if not task.pendingFileDeps and not task.pendingDynFileDeps and not task.pendingTaskDeps:
                task.state = TState.Ready
                queueIfRequested()
        elif task.state == TState.Ready:
            queueIfRequested()

    def __markParentTasks(self, name, getPendingDepsFn):
        for parentTask in self.parentTaskDict[name]:
            if parentTask.state < TState.Queued:
                # TODO  What to do if task is queued, not built and its requestedPrio changes?
                pendingDeps, dynPendingDeps = getPendingDepsFn(parentTask)
                if name in pendingDeps:
                    pendingDeps.remove(name)
                elif name in dynPendingDeps:
                    dynPendingDeps.remove(name)
                else:
                    return
                self.__checkAndHandleTaskDepCompletition(parentTask)

    def _markTargetUpToDate(self, target):
        def getPendingDeps(task):
            return task.pendingFileDeps, task.pendingDynFileDeps
        with self.lock:
            # Due to taskFactories, up-to-date files have to be removed from newly added tasks' pending dependencies.
            # if target not in self.upToDateFiles:
            # debugf('targetUpToDate: {}', target)
            self.upToDateFiles.add(target)
            self.__markParentTasks(target, getPendingDeps)

    def _markTaskUpToDate(self, task):
        def getPendingDeps(task):
            return task.pendingTaskDeps, [] # pendingDynTaskDeps
        with self.lock:
            if not task.state == TState.Built:
                task.state = TState.Built
                # debugf('taskUpToDate: {}', task)
                self.__markParentTasks(task.name, getPendingDeps)

    def _handleTaskBuildCompleted(self, task):
        logger.debugf("{}", task.getId())
        with self.lock:
            if task.name:   
                self._markTaskUpToDate(task)
            else:
                task.state = TState.Built           
            for trg in task.targets:
                self._markTargetUpToDate(trg)
            # update taskIdSavedTaskDict
            self.db.saveTask(self, task)

    def __putTaskToBuildQueue(self, task, prio=[]): # def arg is safe here
        assert isinstance(task, Task)
        # lock is handled by caller
        # --- handle dependencies
        assert isinstance(prio, list)
        targetPrio = prio + [task.prio]
        for taskDepName in task.pendingTaskDeps:
            assert not self._isTaskUpToDate(taskDepName)
            depTask = self.nameTaskDict.get(taskDepName)
            if depTask is None:
                errorf("Task '{}' refers to a not existing task '{}'!", task.getId(), taskDepName)
                return False
            if not self.__putTaskToBuildQueue(depTask, targetPrio):
                return False
        # --- TODO: separate handling of fileDeps and dynFileDeps
        for fileDep in list(task.pendingFileDeps) + list(task.pendingDynFileDeps):
            if not self._putFileToBuildQueue(fileDep, targetPrio):
                return False
        task._setRequestPrio(targetPrio)
        self.__checkAndHandleTaskDepCompletition(task)
        return True
    
    def _putFileToBuildQueue(self, fpath, prio=[]):
        with self.lock:
            if fpath in self.upToDateFiles:
                cinfof(self.printUpToDate, "File '{}' is up-to-date.", self.encodePath(fpath))
                self._markTargetUpToDate(fpath)
                return True # success
            task = self.targetTaskDict.get(fpath)
            if task is None:
                if self.fs.exists(fpath):
                    self._markTargetUpToDate(fpath)
                    return True
                errorf("No task to make file '{}'!", self.encodePath(fpath))
                return False
            return self.__putTaskToBuildQueue(task, prio)

    def _putTaskToBuildQueue(self, taskName, prio=[]):
        with self.lock:
            task = self.nameTaskDict.get(taskName)
            if task is None:
                errorf("No task named '{}'!", self.encodePath(taskName))
                return False
            return self.__putTaskToBuildQueue(task, prio)
        
    # task deps have to be built 1st
    def _putToBuildQueue(self, nameOrTarget, prio=[]):
        with self.lock:
            if nameOrTarget in self.upToDateFiles:
                cinfof("File '{}' is up-to-date.", self.printUpToDate, self.encodePath(nameOrTarget))
                return True # success
            if self._isTaskUpToDate(nameOrTarget):
                cinfof("Task '{}' is up-to-date.", self.printUpToDate, self.encodePath(nameOrTarget))
                return True
            task = self.targetTaskDict.get(nameOrTarget)
            if task is None:
                task = self.nameTaskDict.get(nameOrTarget)
            if task is None:
                if self.fs.exists(nameOrTarget):
                    self._markTargetUpToDate(nameOrTarget)
                    return True
                errorf("No task to make target '{}'!", self.encodePath(nameOrTarget))
                return False
            return self.__putTaskToBuildQueue(task, prio)

    def buildOne(self, target):
        '''Builds a target. "target" can also be a task name.'''
        return self.build([target])
    
    def build(self, targets):
        '''Builds a list targets. A "target" can also be a task name.'''
        for target in targets:
            if not self._putToBuildQueue(target):
                errorf("BUILD FAILED! exitCode: {}", 1)
                return 1
        logger.debug("Starting queue")
        self.queue.start()
        if self.queue.rc:
            errorf("BUILD FAILED! exitCode: {}", self.queue.rc)
        else:
            info("BUILD PASSED!")
        self.db.save()
        return self.queue.rc
        
    def check(self):
        # TODO: find cycles
        pass

    def clean(self, targetOrNameList):
        '''Cleans a list of targets. (The list entries can be targets and task names).'''
        return self.db.clean(targetOrNameList)

    def cleanOne(self, targetOrName):
        '''Cleans a target or a task referred by its name.'''
        return self.db.clean([targetOrName])

    def show(self):
        
        def printHeader(res, task, indent):
            line = indent * ' '
            if task.targets:
                line += 'files:[' + ', '.join(task.targets) + ']'
            if task.name:
                if len(line) > indent:
                    line += ', '
                line += 'task:' + task.name
            res.append(line)

        def printDepends(res, task, indent):
            # common method for fileDeps and taskDeps
            def walkDep(depList, depTaskDict, marker):
                for dep in depList:
                    res.append(' ' * indent + marker + dep)
                    subTask = depTaskDict.get(dep)
                    if subTask:
                        printDepends(res, subTask, indent + 2)
            
            walkDep(task.fileDeps, self.targetTaskDict, 'file:')
            walkDep(task.taskDeps, self.nameTaskDict, 'task:')

        res = []
        idTaskDict = {}
        for task in self.targetTaskDict.values() + self.nameTaskDict.values():
            idTaskDict[task.getId()] = task
        # find top level targets and tasks
        for task in idTaskDict.values():
            if not self.parentTaskDict[task.getId()]:
                printHeader(res, task, indent=0)
                printDepends(res, task, indent=2)
        return '\n'.join(res)

    def listTasks(self):
        '''Lists tasks which have summary.'''
        idTaskDict = {}
        for task in self.targetTaskDict.values() + self.nameTaskDict.values():
            if task.summary:
                idTaskDict[task.getId()] = task
        res = StringIO()
        for tid, task in idTaskDict.items():
            res.write(tid + '\n')
            res.write('  {}\n'.format(task.summary))
            # TODO: format and print task.summary
            res.write('\n')
        return res.getvalue()

    def showTasks(self, tasks):
        '''Shows task summary and description.'''
        res = StringIO()
        for task in tasks:
            res.write(task.getId() + '\n')
            if task.summary:
                res.write('  Summary:\n')
                res.write('    {}\n'.format(task.summary))
                # TODO: format and print task.summary
            if task.desc:
                res.write('  Description:\n')
                # TODO: format and print task.desc
                # TODO: try to use html2text
            res.write('\n')
        return res.getvalue()

    def _getTmpDB(self):
        db = DB.create(name='temporary', fs=self.fs, pathFormer=self.pathFormer)
        idTaskDict = {}
        for task in self.targetTaskDict.values() + self.nameTaskDict.values():
            idTaskDict[task.getId()] = task
        for task in idTaskDict.values():
            db.saveTask(self, task, storeHash=False)
        return db

    def genPlantUML(self):
        db = self._getTmpDB()
        res = db.genPlantUML()
        db.forget()
        return res

    def genTrgPlantUML(self, nameOrTargetList, depth=4):
        db = self._getTmpDB().getPartDB(nameOrTargetList, depth)
        res = db.genPlantUML()
        db.forget()
        return res
