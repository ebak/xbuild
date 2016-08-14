def notUpToDate(bldr, task):
    return False


def targetUpToDate(bldr, task):
    # if dependencies are not changed, targets also need check
    def checkFiles(fileDeps):
        for fileDep in fileDeps:
            hashEnt = bldr.db.hashDict.get(fileDep)
            if hashEnt.new is None:
                # there can be file dependencies coming from outside the build process 
                hashEnt.setByFile(bldr.fs, fileDep)
            if not hashEnt.matches():
                return False
        return True
    
    # not up-to-date when target doesn't exist
    for trg in task.targets:
        if not bldr.fs.isfile(trg):
            return False

    # detect fileDeps list change
    if task.getFileDeps() != task.savedFileDeps:
        return False
    if not checkFiles(task.getFileDeps()):
        return False
    # File dependencies are not changed. Now check the targets.
    if not checkFiles(task.targets):
        return False
    # up-to-date status of provided files are checked by the QueueTask
    if not task.providedFiles:
        task.providedFiles += task.savedProvidedFiles
    # TODO: how to handle savedProvidedTasks?
    if not task.generatedFiles:
        task.generatedFiles += task.savedGeneratedFiles
    if not checkFiles(task.providedFiles):
        return False
    if not checkFiles(task.generatedFiles):
        return False
    return True


def fetchAllDynFileDeps(genTask):
    return genTask.generatedFiles, genTask.providedFiles


class FetchDynFileDeps(object):

    def __init__(self, filterFn, fetchGen=False, fetchProv=False, **kwargs):
        '''filterFn(fileList, **kwargs) must return filtered fileList.'''
        self.filterFn = filterFn
        self.fetchGen, self.fetchProv = fetchGen, fetchProv
        self.kwargs = kwargs
    
    def __call__(self, genTask):
        return \
            self.filterFn(genTask.generatedFiles, **self.kwargs) if self.fetchGen else [], \
            self.filterFn(genTask.providedFiles, **self.kwargs) if self.fetchProv else []


class EndFilter(object):

    def __init__(self, end, ignoreCase=True):
        self.end = end.lower() if ignoreCase else end
        self.ignoreCase = ignoreCase

    def __call__(self, fileList):
        if self.ignoreCase:
            return [f for f in fileList if f.lower().endswith(self.end)]
        else:
            return [f for f in fileList if f.endswith(self.end)]

class StartFilter(object):

    def __init__(self, start, ignoreCase=True):
        self.start = start.lower() if ignoreCase else start
        self.ignoreCase = ignoreCase

    def __call__(self, fileList):
        if self.ignoreCase:
            return [f for f in fileList if f.lower().startswith(self.start)]
        else:
            return [f for f in fileList if f.startswith(self.start)]


class RegExpFilter(object):

    def __init__(self, pattern):
        self.pattern = pattern

    def __call__(self, fileList):
        return [f for f in fileList if self.pattern.matches(f)]
