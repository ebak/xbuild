class UserData(object):
    pass


class Task(object):

    def __init__(
        self, name=None, targets=[], fileDeps=[], taskDeps=[],
        upToDate=None, action=None, prio=0, meta={}
    ):
        '''e.g.: upToDate or action = (function, {key: value,...})
        function args: builder, task, **kvargs'''
        # TODO: type check, taskName
        self.name = name
        self.targets = targets
        self.fileDeps = fileDeps
        self.taskDeps = taskDeps
        self.pendingFileDeps = set(fileDeps)
        self.pendingTaskDeps = set(taskDeps)
        self.upToDate = upToDate
        self.action = action
        self.meta = meta  # json serializable dict
        # dependency calculator tasks need to fill these fields
        self.providedFileDeps = []
        self.providedTaskDeps = []
        # task related data can be stored here which is readable by other tasks
        self.userData = UserData()

    def getId(self):
        '''Returns name if has or 1st target otherwise'''
        return self.name if self.name else self.targets[0]