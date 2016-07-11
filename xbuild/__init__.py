from fs import FS
from hash import HashDict, HashEnt
from builder import Task, Builder
from console import logger


__all__ = ['FS', 'HashDict', 'HashEnt', 'Task', 'Builder']


# TODO: make a generic implementation, which executes for all cases than executes the custom up-to-date method
# if needed.
def targetUpToDate(bldr, task, **kvArgs):
    # if dependencies are not changed, targets also need check
    def checkFiles(fileDeps):
        for fileDep in fileDeps:
            hashEnt = bldr.hashDict.get(fileDep)
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
    # File dependencies are not changed. Now check the targets.
    if not checkFiles(task.targets):
        return False
    # up-to-date status of provided files are checked by the QueueTask
    if not task.providedFiles:
        task.providedFiles += task.savedProvidedFiles
    # TODO: how to handle savedProvidedTasks?
    # Check generated files from previous run
    if not checkFiles(task.savedGeneratedFiles):
        return False
    else:
        task.generatedFiles += task.savedGeneratedFiles
    return True



        


