from prio import prioCmp

class UserData(object):
    pass


'''
Ready - task is ready to be placed into the build queue
Queued - task is in the Queue or under building.
Built - task is built, up-to-date'''
class TState(object):
    Init, Ready, Queued, Built = range(4)
    TXT = ['Init', 'Ready', 'Queued', 'Built']

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
                    raise ValueError("2nd tuple element must be a dict (**kvArgs)!")
                return cb
            else:
                raise ValueError("Tuple must have 2 entries: (function, dict)!")
        elif hasattr(cb, '__call__'):
            return (cb, {})
        else:
            raise ValueError("Callback argument must be a function or a tuple: (function, dict)!")

    def __init__(
        self, name=None, targets=[], fileDeps=[], taskDeps=[], taskFactory=None,
        upToDate=None, action=None, prio=0, meta={}
    ):
        '''e.g.: upToDate or action = (function, {key: value,...})
        function args: builder, task, **kvargs'''
        # TODO: type check, taskName
        self.name = name
        self.targets = set(targets)
        self.fileDeps = fileDeps
        self.taskDeps = taskDeps
        self.taskFactory = taskFactory  # create rules to make providedFiles from generatedFiles
        self.prio = prio
        self.requestedPrio = None
        self.pendingFileDeps = set(fileDeps)
        self.pendingTaskDeps = set(taskDeps)
        self.upToDate = Task.makeCB(upToDate)
        self.action = Task.makeCB(action)
        self.meta = meta  # json serializable dict
        self.state = TState.Init
        # generator tasks need to fill these fields
        self.generatedFiles = []
        self.savedGeneratedFiles = []
        self.providedFiles = []
        self.providedTasks = []
        self.savedProvidedFiles = []
        self.savedProvidedTasks = []
        self.pendingProvidedFiles = set()
        self.pendingProvidedTasks = set()
        # task related data can be stored here which is readable by other tasks
        self.userData = UserData()

    def __repr__(self, *args, **kwargs):
        return '{} state:{}, trgs:{}, fDeps:{}, tDeps:{}, pfDeps:{}, ptDeps:{}, prvFiles:{}, prvTasks:{}'.format( 
            self.getId(), TState.TXT[self.state], self.targets, self.fileDeps, self.taskDeps,
            list(self.pendingFileDeps), list(self.pendingTaskDeps), self.providedFiles, self.providedTasks)

    def __eq__(self, o):
        return (
            self.name == o.name and
            self.targets == o.targets and
            set(self.fileDeps) == set(o.fileDeps) and  # TODO: these fields could be stored in sets too
            set(self.taskDeps) == set(o.taskDeps))
            

    def getId(self):
        '''Returns name if has or 1st target otherwise'''
        return self.name if self.name else next(iter(self.targets))

    # TODO: move this method to Builder
    def getAllFileDeps(self, bldr):
        '''returns fileDeps + providedFiles of taskDeps'''
        res = self.fileDeps[:]
        for taskDep in self.taskDeps:
            res += bldr.nameTaskDict[taskDep].providedFiles   # FIXME: locking?
        return res

    def toDict(self, res={}):
        if self.name:
            res['name'] = self.name
        if self.targets:
            res['trgs'] = list(self.targets)
        if self.fileDeps:
            res['fDeps'] = self.fileDeps
        if self.taskDeps:
            res['tDeps'] = self.taskDeps
        if self.generatedFiles:
            res['gFiles'] = self.generatedFiles
        if self.providedFiles:
            res['pFiles'] = self.providedFiles
        if self.providedTasks:
            res['pTasks'] = self.providedTasks
        res['meta'] = self.meta
        return res

    def _readyAndRequested(self):
        return self.state == TState.Ready and self.requestedPrio

    def _setRequestPrio(self, reqPrio):
        '''Set only when reqPrio is higher than current requestPrio.'''
        if self.requestedPrio:
            if prioCmp(reqPrio, self.requestedPrio) < 0:
                self.requestedPrio = reqPrio
        else:
            self.requestedPrio = reqPrio
