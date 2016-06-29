
class UserData(object):
    pass

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

    def _execute(self):
        '''Returns 0 at success'''
        def runAction():
            act = self.task.action
            if act:
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
            self.builder.stop()
        else:
            # -- build provided dependencies if there are any
            if self.task.providedFileDeps or self.task.providedTaskDeps:
                