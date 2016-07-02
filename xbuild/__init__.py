from fs import FS
from hash import HashDict, HashEnt
from builder import Task, Builder
from console import xdebug


__all__ = ['FS', 'HashDict', 'HashEnt', 'Task', 'Builder']



def targetUpToDate(bldr, task, **kvArgs):
    # if dependencies are not changed, targets also need check
    def checkFileDeps(fileDeps):
        for fileDep in fileDeps:
            hashEnt = bldr.hashDict.get(fileDep)
            if hashEnt.new is None:
                # there can be file dependencies coming from outside the build process 
                hashEnt.setByFile(bldr.fs, fileDep)
            if not hashEnt.matches():
                return False
    
    # not up-to-date when target doesn't exist
    for trg in task.targets:
        if not bldr.fs.isfile(trg):
            return False

    checkFileDeps(task.fileDeps)
    for taskDep in task.taskDeps:
        if not checkFileDeps(taskDep.providedFileDeps):
            return False
    # File dependencies are not changed. Now check the targets.
    for trg in task.targets:
        hashEnt = bldr.hashDict.get(trg)
        if hashEnt.new is None:
            hashEnt.setByFile(bldr.fs, trg)
        if not hashEnt.matches():
            return False
    return True



        


