# Copyright (c) 2016 Endre Bak
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import logging
import multiprocessing
from cStringIO import StringIO
from task import Task, TState, CheckType
from threading import RLock
from collections import defaultdict
from db import DB
from fs import FS
from prio import Prio, prioCmp
from callbacks import targetUpToDate, noDynFileDeps
from buildqueue import BuildQueue, QueueTask
from console import logger, getLoggerAdapter, write, cinfo, infof, cinfof, warn, warnf, error, errorf
from pathformer import NoPathFormer

dlogger = getLoggerAdapter('xbuild.builder')
dlogger.setLevel(logging.DEBUG)


def calcNumOfWorkers(workers):
    '''This function is useful for unit testing. It should be overwritten for setting the number of workers threads
    in a test collection.'''
    # it seems to be a bit heavy to have 5 workers on Windows desktop with 2 hyperthreaded CPU cores
    # return workers if workers else multiprocessing.cpu_count() + 1
    return workers if workers else multiprocessing.cpu_count()


# TODO: builder should use the DepGraph model
class Builder(object):

    def __init__(
        self, name='default', workers=0, fs=FS(), pathFormer=NoPathFormer(), printUpToDate=False,
        printInfo=True, hashCheck=True, progressFn=None
    ):
        '''progressFn: e.g: def showProgress(progress) - progress is progress.Progress'''
        self.pathFormer = pathFormer
        self.db = DB.create(name, fs, pathFormer)
        self.workers = calcNumOfWorkers(workers)
        self.fs = fs
        self.printUpToDate = printUpToDate and printInfo
        self.printInfo = printInfo
        self.hashCheck = hashCheck
        self.progressFn = progressFn
        self.targetTaskDict = {}  # {targetName: task}
        self.nameTaskDict = {}  # {taskName: task}
        # self.idTaskDict = {}        # {taskId: task}    # TODO use
        self.parentTaskDict = defaultdict(set)  # {target or task name: set([parentTask])}
        self.providerTaskDict = {}  # {target or task name: providerTask} # TODO: remove
        self.upToDateFiles = set()  # name of files
        self.lock = RLock()
        self.queue = BuildQueue(
            self.workers, printUpToDate=self.printUpToDate, printInfo=self.printInfo, progressFn=progressFn)  # contains QueueTasks
        # load db
        self.db.load()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.db.save()
        self.db.forget()

    def needsHashCheck(self, task):
        return self.hashCheck if task.checkType is None else task.checkType == CheckType.Hash

    def encodePath(self, fpath):
        return self.pathFormer.encode(fpath)
    
    def hasTask(self, nameOrTarget):
        return nameOrTarget in self.nameTaskDict or nameOrTarget in self.targetTaskDict

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
        taskDict = {task.getId(): task for task in self.nameTaskDict.values()}
        return [task for task in taskDict.values() if task.requestedPrio.prioList]

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
        self, name=None, targets=None, fileDeps=None, taskDeps=None, dynFileDepFetcher=noDynFileDeps, taskFactory=None,
        upToDate=targetUpToDate, action=None, cleaner=None, prio=0, exclGroup=None, greedy=False, checkType=None,
        summary=None, desc=None, skipIfExists=False
    ):
        '''Adds a Task to the dependency graph.'''
        task = Task(
            name=name, targets=targets, fileDeps=fileDeps, taskDeps=taskDeps, dynFileDepFetcher=dynFileDepFetcher,
            taskFactory=taskFactory, upToDate=upToDate, action=action, cleaner=cleaner, prio=prio, exclGroup=exclGroup,
            greedy=greedy, checkType=checkType, summary=summary, desc=desc)
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
        needToBuild = {}  # {providedFile: requestPrio}
        with self.lock:
            for parentTask in self.parentTaskDict[genTask.getId()]:  # {target or task name: [parentTask]}
                _, newProvFiles = parentTask._injectDynDeps(genTask)
                for pFile in newProvFiles:
                    self.parentTaskDict[pFile].add(parentTask)
                if parentTask._isRequested():
                    # TODO: request build only for provided files
                    for pFile in newProvFiles:
                        prio = needToBuild.get(pFile)
                        if prio is not None:
                            if prioCmp(prio, parentTask.requestedPrio) > 0:
                                needToBuild[pFile] = parentTask.requestedPrio
                        else:
                            needToBuild[pFile] = parentTask.requestedPrio
            # print '>>>> needToBuild: {}'.format(needToBuild.keys())
            for pFile, prio in needToBuild.items():
                if not self._putFileToBuildQueue(pFile, prio):
                    return  # TODO: error handling
            # generated files don't need any build

    def __checkAndHandleTaskDepCompletition(self, task):
        def queueIfRequested():
            '''Task dependencies can be satisfied, but don't have to be built if not requested.'''
            if task.requestedPrio and task.requestedPrio.isRequested():
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
        # needDebug = name == 'generator'
        needDebug = False
        dlogger.cdebugf(needDebug, 'taskName: {}', name)
        for parentTask in self.parentTaskDict[name]:
            dlogger.cdebugf(needDebug, 'parentTask: {}', parentTask)
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
            return task.pendingTaskDeps, []  # pendingDynTaskDeps
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
            # self.db.saveTask(self, task)    # moved to QueueTask

    def __putTaskToBuildQueue(self, task, prio=None):  # def arg is safe here
        assert isinstance(task, Task)
        # lock is handled by caller
        # --- handle dependencies
        if prio:
            assert isinstance(prio, Prio)
            targetPrio = Prio(prio.prioList + [task.prio], task.summary if task.summary else prio.phase)
            # argetPrio = prio + [task.prio]
        else:
            targetPrio = Prio([task.prio], task.summary)
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
        if task._setRequestPrio(targetPrio):
            self.queue.incRequestedCnt()
        self.__checkAndHandleTaskDepCompletition(task)
        return True

    def _putFileToBuildQueue(self, fpath, prio=None):
        with self.lock:
            if fpath in self.upToDateFiles:
                cinfof(self.printUpToDate, "File '{}' is up-to-date.", self.encodePath(fpath))
                self._markTargetUpToDate(fpath)
                return True  # success
            task = self.targetTaskDict.get(fpath)
            if task is None:
                if self.fs.exists(fpath):
                    self._markTargetUpToDate(fpath)
                    return True
                errorf("No task to make file '{}'!", self.encodePath(fpath))
                return False
            if not prio:
                prio = Prio()
            return self.__putTaskToBuildQueue(task, prio)

    def _putTaskToBuildQueue(self, taskName, prio=None):
        with self.lock:
            task = self.nameTaskDict.get(taskName)
            if task is None:
                errorf("No task named '{}'!", self.encodePath(taskName))
                return False
            if not prio:
                prio = Prio()
            return self.__putTaskToBuildQueue(task, prio)

    # task deps have to be built 1st
    def _putToBuildQueue(self, nameOrTarget, prio=None):
        with self.lock:
            if nameOrTarget in self.upToDateFiles:
                cinfof("File '{}' is up-to-date.", self.printUpToDate, self.encodePath(nameOrTarget))
                return True  # success
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
            if not prio:
                prio = Prio()
            return self.__putTaskToBuildQueue(task, prio)

    def buildOne(self, target):
        '''Builds a target. "target" can also be a task name.'''
        return self.build([target])

    def _buildInitialDepGraph(self, targets):
        '''Invoked by build().'''
        for target in targets:
            if not self._putToBuildQueue(target):
                errorf("BUILD FAILED! exitCode: {}", 1)
                if self.progressFn:
                    from progress import Progress
                    prg = Progress(1)
                    prg.finish(1)
                    self.progressFn(prg)
                return 1
        return 0

    def _startBuildQueue(self):
        '''Invoked by build.'''
        self.queue.start()
        if self.queue.rc:
            errorf("BUILD FAILED! exitCode: {}", self.queue.rc)
        else:
            cinfo(self.printInfo, "BUILD PASSED!")
        return self.queue.rc

    def build(self, targets):
        '''Builds a list targets. A "target" can also be a task name.'''
        rc = self._buildInitialDepGraph(targets)
        if rc:
            return rc
        return self._startBuildQueue()

    def check(self):
        # TODO: find cycles
        pass

    def clean(self, targetOrNameList):
        '''Cleans a list of targets. (The list entries can be targets and task names).'''
        res = self.db.clean(bldr=self, targetOrNameList=targetOrNameList)
        return res

    def cleanOne(self, targetOrName):
        '''Cleans a target or a task referred by its name.'''
        return self.db.clean(bldr=self, targetOrNameList=[targetOrName])

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
        db = self._getTmpDB()  # TODO: rework it when the builder is adapted for DepGraph
        graph = db.getGraph()
        graph.calcDepths()
        db.forget()

        desc = []  # [(lDepth, taskId, summary)]
        placed = set()
        for task in self.targetTaskDict.values() + self.nameTaskDict.values():
            if task.summary and task.getId() not in placed:
                placed.add(task.getId())
                taskNode = graph.getTask(task.getId())
                desc.append((taskNode.depth.lower, task.getId(), task.summary))

        # list top level tasks as 1st
        def myCmp(a, b):
            if a[0] < b[0]:
                return -1
            elif a[0] > b[0]:
                return 1
            return cmp(a[1], b[1])

        res = StringIO()
        for _, taskId, summary in sorted(desc, cmp=myCmp):
            res.write(taskId + '\n')
            res.write('  {}\n'.format(summary))
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

    def showDepGraph(self):
        db = self._getTmpDB()
        depGraph = db.getGraph()
        import xvis.vis as vis
        vis.show(depGraph, self.pathFormer)
        db.forget()

    def genTrgPlantUML(self, nameOrTargetList, depth=4):
        db = self._getTmpDB().getPartDB(nameOrTargetList, depth)
        res = db.genPlantUML()
        db.forget()
        return res
