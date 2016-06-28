
class UserData(object):
    pass

class QueueTask(object):

    def __init__(self, prio):
        self.prio = prio

    def __cmp__(self, o):
        chkLen = min(len(self.prio), len(o.prio))
        for i in range(chkLen):
            diff = self.prio[i] - o.prio[i]
            if diff:
                return diff
        return 0

