from fs import FS
from hash import HashDict, HashEnt
from builder import Task, Builder
from console import logger, getLoggerAdapter, info, infof, warn, warnf, error, errorf


__all__ = [
    'FS', 'HashDict', 'HashEnt', 'Task', 'Builder', 'info', 'infof', 'warn', 'warnf',
    'error', 'errorf', 'getLoggerAdapter']


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

    if not checkFiles(task.fileDeps):
        return False
    for taskDep in task.taskDeps:
        depTask = bldr._getTaskByName(taskDep)
        if depTask:
            if not checkFiles(depTask.providedFiles):
                return False
            if not checkFiles(depTask.generatedFiles):
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





