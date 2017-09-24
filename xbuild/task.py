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

from prio import Prio, prioCmp
from callbacks import targetUpToDate, noDynFileDeps
from xbuild.fs import joinPath

class UserData(object):
    pass


class CheckType(object):
    TimeStamp, Hash = range(2)
    TXT = ['TimeStamp', 'Hash']


'''
Ready - task is ready to be placed into the build queue
Queued - task is in the Queue or under building.
Built - task is built, up-to-date'''
class TState(object):
    Init, Ready, Queued, Built = range(4)
    TXT = ['Init', 'Ready', 'Queued', 'Built']

# 1st: build fileDeps, taskDeps
# 2nd: build dynFileDeps
class Task(object):

    @staticmethod
    def makeCB(cb):
        if cb is None:
            return None
        elif type(cb) is tuple:
            if len(cb) == 2:
                if not hasattr(cb[0], '__call__'):
                    raise ValueError("1st tuple element must be a function!")
                if not isinstance(cb[1], dict):
                    raise ValueError("2nd tuple element must be a dict (**kwargs)!")
                return cb
            else:
                raise ValueError("Tuple must have 2 entries: (function, dict)!")
        elif hasattr(cb, '__call__'):
            return (cb, {})
        else:
            raise ValueError("Callback argument must be a function or a tuple: (function, dict)!")

    @staticmethod
    def checkInput(name, targets, fileDeps, taskDeps, dynFileDepFetcher, taskFactory,
        upToDate, action, prio, meta, summary, desc
    ):
        # TODO: implement
        def checkStrList(lst):
            if lst is None:
                return
            assert type(lst) is list, "type is {}".format(type(lst))
            for e in lst:
                assert type(e) in (str, unicode), "type is {}".format(type(e))

        checkStrList(targets)
        checkStrList(fileDeps)
        checkStrList(taskDeps)

    # taskFactory is needed, because it have to be executed even if the generator task is up-to-date
    def __init__(
        self, name=None, targets=None, fileDeps=None, taskDeps=None, dynFileDepFetcher=noDynFileDeps,
        taskFactory=None, upToDate=targetUpToDate, action=None,
        prio=0, meta=None, exclGroup=None, greedy=False, cleaner=None,
        checkType=None, summary=None, desc=None
    ):
        # TODO: extend doc and add it to Builder.addTask() too
        '''
            checkType:
                None, CheckType.Hash, CheckType.TimeStamp
                
            Function references:
                - you can pass a function reference
                - or you can pass a function reference with kwargs: (functionRef, {key: value,...})
                - cleaner must return (filesToRemove, dirsToRemove)
              
            Signature for upToDate and action functions:
                builder, task, **kwargs'''
        Task.checkInput(
            name, targets, fileDeps, taskDeps, dynFileDepFetcher, taskFactory, upToDate, action, prio, meta, summary, desc)
        self.name = name
        self.targets = [] if targets is None else targets
        self.fileDeps = [] if fileDeps is None else fileDeps
        self.dynFileDeps = []
        self.savedFileDeps = None
        self.savedDynFileDeps = None
        self.taskDeps = [] if taskDeps is None else taskDeps
        self.dynFileDepFetcher = Task.makeCB(dynFileDepFetcher)
        self.taskFactory = Task.makeCB(taskFactory)  # create rules to make providedFiles from generatedFiles
        self.prio = prio
        self.requestedPrio = None
        self.pendingFileDeps = set(self.fileDeps)
        self.pendingTaskDeps = set(self.taskDeps)
        self.pendingDynFileDeps = set()
        self.upToDate = Task.makeCB(upToDate)
        self.action = Task.makeCB(action)
        self.cleaner = Task.makeCB(cleaner)
        self.checkType = checkType
        self.meta = {} if meta is None else meta  # json serializable dict
        self.exclGroup = exclGroup
        self.greedy = greedy
        self.summary = summary
        self.desc = desc
        self.state = TState.Init
        # generator tasks need to fill these fields
        self.generatedFiles = []
        self.savedGeneratedFiles = []
        self.providedFiles = []
        self.providedTasks = []
        self.savedProvidedFiles = []
        self.savedProvidedTasks = []
        self.pendingProvidedFiles = set()  # TODO: remove
        self.pendingProvidedTasks = set()  # TODO: remove
        self.garbageDirs = []
        # task related data can be stored here which is readable by other tasks
        self.userData = UserData()

    def __repr__(self, *args, **kwargs):
        res = '{{{} state:{}, req:{}, trgs:{}, '.format(self.getId(), TState.TXT[self.state], bool(self.requestedPrio.prioList), self.targets)
        res += 'fDeps:{}, dfDeps:{}, tDeps:{}, '.format(self.fileDeps, self.dynFileDeps, self.taskDeps)
        res += 'pfDeps:{}, pdFileDeps:{}, ptDeps:{}, '.format(list(self.pendingFileDeps), list(self.pendingDynFileDeps), list(self.pendingTaskDeps))
        res += 'prvFiles:{}, prvTasks:{}}}'.format(self.providedFiles, self.providedTasks)
        return res

    def __eq__(self, o):
        return (
            self.name == o.name and
            self.targets == o.targets and
            set(self.fileDeps) == set(o.fileDeps) and
            set(self.taskDeps) == set(o.taskDeps))

    def __ne__(self, o):
        return not self.__eq__(o)

    def __hash__(self):
        return self.getId().__hash__()

    def getFstTarget(self):
        return self.targets[0] if self.targets else None

    def getTargets(self, filterFn=None, assertCount=None):
        '''Returns the targets where filterFn returns True.'''
        res = list(self.targets)
        if filterFn:
            res = [f for f in res if filterFn(f)]
        if assertCount is not None:
            assert len(res) == assertCount, '{} != {}, targets={}'.format(len(res), assertCount, self.targets)
        return res
        # return res if filterFn is None else [f for f in res if filterFn(f)]

    def getId(self):
        '''Returns name if has or 1st target otherwise'''
        return self.name if self.name else self.getFstTarget()

    def getRawGeneratedFileDeps(self, bldr):
        '''returns providedFiles and generatedFiles of taskDeps'''
        res = []
        for taskDep in self.taskDeps:
            depTask = bldr.nameTaskDict[taskDep]
            res += depTask.providedFiles  # FIXME: locking?
            res += depTask.generatedFiles
        return res

    def _injectDynDeps(self, generatorTask):
        # update pending file deps
        cb, kwargs = self.dynFileDepFetcher
        newGenFileDeps, newProvFileDeps = cb(generatorTask, **kwargs)
        self.pendingDynFileDeps |= set(newProvFileDeps)
        for newDep in newGenFileDeps + newProvFileDeps:
            assert newDep not in self.fileDeps
            if newDep not in self.dynFileDeps:
                self.dynFileDeps.append(newDep)
        return newGenFileDeps, newProvFileDeps

    def getFileDeps(self, filterFn=None, assertCount=None):
        '''returns fileDeps + dynFileDeps'''
        res = self.fileDeps + self.dynFileDeps
        if filterFn:
            res = [f for f in res if filterFn(f)]
        if assertCount is not None:
            assert len(res) == assertCount, '{} != {}, taskId:{}, fileDeps={}'.format(
                len(res), assertCount, self.getId(), self.fileDeps + self.dynFileDeps)
        return res

    def toDict(self, res=None):
        if res is None:
            res = {}
        if self.name:
            res['name'] = self.name
        if self.targets:
            res['trgs'] = list(self.targets)
        if self.fileDeps:
            res['fDeps'] = self.fileDeps
        if self.dynFileDeps:
            res['dfDeps'] = self.dynFileDeps
        if self.taskDeps:
            res['tDeps'] = self.taskDeps
        if self.generatedFiles:
            res['gFiles'] = self.generatedFiles
        if self.providedFiles:
            res['pFiles'] = self.providedFiles
        if self.providedTasks:
            res['pTasks'] = self.providedTasks
        if self.garbageDirs:
            res['grbDirs'] = self.garbageDirs
        if self.meta:
            res['meta'] = self.meta
        return res

    def addGeneratedFiles(self, fs, dpath):
        '''Scans dpath and adds all files found to generatedFiles.'''
        for f in fs.listdir(dpath):
            fpath = joinPath(dpath, f)
            if fs.isfile(fpath):
                self.generatedFiles.append(fpath)
            elif fs.isdir(fpath):
                self.addGeneratedFiles(fs, fpath)

    def getDynFileDeps(self, filterFn=None):
        '''Gets the dynamic file dependencies.'''
        return self.dynFileDeps if filterFn is None else [f for f in self.dynFileDeps if filterFn(f)]

    def _runCallback(self, cbTuple, bldr):
        '''
        cb signature is always (bldr, task, **kwargs)
        Good for: upToDate, action, taskFactory'''
        cb, kwargs = cbTuple
        return cb(bldr, self, **kwargs)

    def _readyAndRequested(self):
        return self.state == TState.Ready and self.requestedPrio.isRequested()

    def _setRequestPrio(self, reqPrio):
        '''Set only when reqPrio is higher than current requestPrio.
        Returns True when the task is first time requested.'''
        if self.requestedPrio:
            if prioCmp(reqPrio, self.requestedPrio) < 0:
                # self.requestedPrio = reqPrio
                self.requestedPrio.copyPrioSettings(reqPrio)
            return False
        else:
            self.requestedPrio = reqPrio
            return True

    def _isRequested(self):
        return self.requestedPrio is not None
