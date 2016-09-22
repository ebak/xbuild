import os
import logging
from console import getLoggerAdapter

logger = getLoggerAdapter('xbuild.callbacks')
logger.setLevel(logging.DEBUG)

def alwaysUpToDate(bldr, task):
    return True


# TODO: handle
def notUpToDate(bldr, task):
    return False

def targetUpToDate(bldr, task, skipFileDepChecks=False):
    if bldr.needsHashCheck(task):
        return targetUpToDateHash(bldr, task, skipFileDepChecks)
    else:
        return targetUpToDateTimeStamp(bldr, task, skipFileDepChecks)


def targetUpToDateTimeStamp(bldr, task, skipFileDepChecks=False):
    # needDebug = task.getId().endswith('VSC.gen')
    needDebug = False
    def checkFiles(targetTime, fileDeps):
        for fileDep in fileDeps:
            if bldr.fs.exists(fileDep):
                if os.path.getmtime(fileDep) > targetTime:
                    return False
            else:
                return False
        return True
    
    targets = list(task.targets)
    # not up-to-date when target doesn't exist
    for trg in targets:
        if not bldr.fs.isfile(trg):
            logger.cdebugf(needDebug, 'target: {} does not exist!', trg)
            return False

    # not up-to-date when generated files don't exist
    for gen in task.savedGeneratedFiles:
        if not bldr.fs.isfile(gen):
            logger.cdebugf(needDebug, 'generated file: {} does not exist!', gen)
            return False

    # get time of most up-to-date target
    targetTime = 0
    for trg in targets + task.savedGeneratedFiles:
        logger.cdebugf(needDebug, 'check file: {}', trg)
        mtime = os.path.getmtime(trg)    # TODO: add getmtime() to FS
        if mtime > targetTime:
            targetTime = mtime
    
    # detect fileDeps list change
    if not skipFileDepChecks and task.fileDeps != task.savedFileDeps:
        logger.cdebugf(needDebug, 'fileDeps:{} != savedFileDeps:{}', task.fileDeps, task.savedFileDeps)
        return False
    if task.dynFileDeps != task.savedDynFileDeps:
        logger.cdebugf(needDebug, 'dynFileDeps:{} != savedDynFileDeps:{}', task.dynFileDeps, task.savedDynFileDeps)
        return False
    
    if targetTime:
        if not skipFileDepChecks and not checkFiles(targetTime, task.getFileDeps()):
            return False
    # up-to-date status of provided files are checked by the QueueTask
    if not task.providedFiles:
        task.providedFiles += task.savedProvidedFiles
    if not task.generatedFiles:
        task.generatedFiles += task.savedGeneratedFiles
    logger.cdebug(needDebug, 'targetUpToDate: True')
    return True


def targetUpToDateHash(bldr, task, skipFileDepChecks=False):

    # needDebug = task.getId().endswith('/clang/module_emb/GROUPED_002_FrTp_MT_AddressRange_PB/FrTp_TestUtils.o')
    needDebug = False
    # if dependencies are not changed, targets also need check
    def checkFiles(fileDeps):
        for fileDep in fileDeps:
            hashEnt = bldr.db.hashDict.get(fileDep)
            with hashEnt.lock:
                if hashEnt.new is None:
                    # there can be file dependencies coming from outside the build process 
                    hashEnt.setByFile(bldr.fs, fileDep)
                logger.cdebugf(needDebug, 'after: {} -> {} matches: {}', fileDep, hashEnt, hashEnt.matches())
                if not hashEnt.matches():
                    return False
        return True
    
    # not up-to-date when target doesn't exist
    for trg in task.targets:
        if not bldr.fs.isfile(trg):
            logger.cdebugf(needDebug, 'target: {} does not exist!', trg)
            return False

    # detect fileDeps list change
    if not skipFileDepChecks and task.fileDeps != task.savedFileDeps:
        logger.cdebugf(needDebug, 'fileDeps:{} != savedFileDeps:{}', task.fileDeps, task.savedFileDeps)
        return False
    if task.dynFileDeps != task.savedDynFileDeps:
        logger.cdebugf(needDebug, 'dynFileDeps:{} != savedDynFileDeps:{}', task.dynFileDeps, task.savedDynFileDeps)
        return False
    if not skipFileDepChecks and not checkFiles(task.getFileDeps()):
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
    # if not checkFiles(task.providedFiles):
    #    return False
    if not checkFiles(task.generatedFiles):
        return False
    logger.cdebug(needDebug, 'targetUpToDate: True')
    return True


def fetchAllDynFileDeps(genTask):
    return genTask.generatedFiles, genTask.providedFiles


def noDynFileDeps(genTask):
    return [], []


class FetchDynFileDeps(object):

    def __init__(self, pathFilterFn=None, fetchGen=False, fetchProv=False, **kwargs):
        '''pathFilterFn(fpath, **kwargs) returns True when fpath is needed.'''
        self.pathFilterFn = pathFilterFn
        self.fetchGen, self.fetchProv = fetchGen, fetchProv
        self.kwargs = kwargs
    
    def __call__(self, genTask):
        def filterPaths(needed, fpaths):
            if needed:
                if self.pathFilterFn is None:
                    return fpaths[:]
                else:
                    return [f for f in fpaths if self.pathFilterFn(f, **self.kwargs)]
            else:
                return []
        return filterPaths(self.fetchGen, genTask.generatedFiles), filterPaths(self.fetchProv, genTask.providedFiles) 


class EndFilter(object):

    def __init__(self, end, ignoreCase=True):
        self.end = end.lower() if ignoreCase else end
        self.ignoreCase = ignoreCase

    def __call__(self, fpath):
        if self.ignoreCase:
            return fpath.lower().endswith(self.end)
        else:
            return fpath.endswith(self.end)

class StartFilter(object):

    def __init__(self, start, ignoreCase=True):
        self.start = start.lower() if ignoreCase else start
        self.ignoreCase = ignoreCase

    def __call__(self, fpath):
        if self.ignoreCase:
            return fpath.lower().startswith(self.start)
        else:
            return fpath.startswith(self.start)


class RegExpFilter(object):

    def __init__(self, pattern):
        self.pattern = pattern

    def __call__(self, fpath):
        return self.pattern.matches(fpath)
