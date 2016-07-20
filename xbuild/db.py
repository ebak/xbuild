import os
import json
from hash import HashDict
from fs import Cleaner
from console import logger, infof, warnf, errorf
from collections import defaultdict

class DB(object):
    
    Version = [0, 0, 0]
    
    def __init__(self, name, fs):
        self.name = name   # TODO avoid duplicates
        self.fs = fs
        self.taskIdSavedTaskDict = {}   # {taskId: saved task data}
        self.targetSavedTaskDict = {}   # {targetName: saved task data}
        self.hashDict = HashDict()
        pass

    def load(self):
        fpath = '.{}.xbuild'.format(self.name)
        if not self.fs.isfile(fpath):
            return
        try:
            jsonObj = json.loads(self.fs.read(fpath)) # loads for easier unit test
        except:
            warnf("'{}' is corrupted! JSON load failed!", fpath)
            raise
            return
        # TODO check version
        if type(jsonObj) is not dict:
            warnf("'{}' is corrupted! Top level dict expected!", fpath)
            return
        hashDictJsonObj = jsonObj.get('HashDict')
        if not hashDictJsonObj:
            warnf("'{}' is corrupted! 'HashDict' section is missing!", fpath)
            return
        if not self.hashDict._loadJsonObj(hashDictJsonObj, warnf):
            warnf("'{}' is corrupted! Failed to load 'HashDict'!", fpath)
            return
        taskDict = jsonObj.get('Task')
        if not taskDict:
            warnf("'{}' is corrupted! 'Task' section is missing!", fpath)
            return
        if type(taskDict) is not dict:
            warnf("'{}' is corrupted! 'Meta' section is not dict!", fpath)
            return
        self.taskIdSavedTaskDict = taskDict
        emptyList = []
        for taskData in taskDict.values():
            for trg in taskData.get('trgs', emptyList):
                self.targetSavedTaskDict[trg] = taskData

    def save(self):
        jsonObj = {'version': [0, 0, 0]}
        jsonObj['HashDict'] = self.hashDict._toJsonObj()
        # taskIdSavedTaskDict
        jsonObj['Task'] = self.taskIdSavedTaskDict
        fpath = '.{}.xbuild'.format(self.name)
        self.fs.write(fpath, json.dumps(jsonObj, ensure_ascii=True, indent=1))  # dumps for easier unit test

    def saveTask(self, bldr, task):
        taskObj = self.taskIdSavedTaskDict.get(task.getId())
        if taskObj is None:
            taskObj = {}
            self.taskIdSavedTaskDict[task.getId()] = taskObj
        else:
            taskObj.clear()
        task.toDict(res=taskObj)
        self.hashDict.storeTaskHashes(bldr, task)

    def loadTask(self, task):
        # fill up task with saved data
        taskObj = self.taskIdSavedTaskDict.get(task.getId())
        if taskObj:
            task.savedProvidedFiles = taskObj.get('pFiles', [])
            task.savedProvidedTasks = taskObj.get('pTasks', [])
            task.savedGeneratedFiles = taskObj.get('gFiles', [])
            meta = taskObj.get('meta', {})
            task.meta = meta

    def clean(self, targetOrNameList):

        def getId(taskData):
            name = taskData.get('name')
            if name:
                return name
            return taskData.get('trgs')[0]

        removedFiles = []
        savedParentTaskDict = defaultdict(set) # {file or taskName: set of parent tasks ids}
        
        # build savedParentTaskDict
        for taskData in self.taskIdSavedTaskDict.values():
            taskId = getId(taskData)
            for fileDep in taskData.get('fDeps', []):
                savedParentTaskDict[fileDep].add(taskId)
            for taskDep in taskData.get('tDeps', []):
                savedParentTaskDict[taskDep].add(taskId)

        def removeFile(fpath):
            savedParentTaskDict.pop(fpath, None)
            self.hashDict.remove(fpath)
            if self.fs.isfile(fpath):
                aPath = self.fs.abspath(fpath)
                removedFiles.append(aPath)
                # self.fs.remove(fpath)

        def removeFileTarget(fpath):
            taskData = self.targetSavedTaskDict.get(fpath)
            if taskData:
                removeTask(taskData)
            else:
                # don't remove leaf files, but clean hashes
                self.hashDict.remove(fpath)

        def getTaskData(targetOrName):
            taskData = self.targetSavedTaskDict.get(targetOrName)
            if taskData is None:
                # this lookup is only good for task names
                taskData = self.taskIdSavedTaskDict.get(targetOrName)
            return taskData

        def removeTaskByName(taskName):
            removeTask(self.taskIdSavedTaskDict.get(taskName))
        
        def removeTask(taskData):
            if not taskData:
                return

            def removeDeps(name, remover):
                # remove deps if they are not leaf depends
                for dep in taskData.get(name, []):
                    parentTasks = savedParentTaskDict.get(dep)
                    if parentTasks:
                        parentTasks.remove(taskId)
                        if not parentTasks:
                            del savedParentTaskDict[dep]
                            remover(dep)
                
            taskId = getId(taskData)
            logger.debugf('taskId={}'.format(taskId))
            
            self.taskIdSavedTaskDict.pop(taskId, None)
            # remove targets
            for trg in taskData.get('trgs',[]):
                removeFile(trg)
                self.targetSavedTaskDict.pop(trg, None)
            # remove fileDeps if they are belonging to just on target
            removeDeps('fDeps', removeFileTarget)
            # remove taskDeps if they are belonging to just on target
            removeDeps('tDeps', removeTaskByName)
            # remove generated files
            for gFile in taskData.get('gFiles', []):
                removeFile(gFile)
            # remove provided files
            for pFile in taskData.get('pFiles', []):
                # if pFile has task, remove it, otherwise pFile is just a generated file
                removeTask(self.targetSavedTaskDict.get(pFile))
            # remove provided tasks
            for pTask in taskData.get('pTasks', []):
                removeTask(self.taskIdSavedTaskDict(pTask))
            
        
        '''For simplicity when a task target is removed from the many, the task is removed.'''
        errors = 0
        for targetOrName in targetOrNameList: 
            taskData = getTaskData(targetOrName)
            if taskData is None:
                errorf("There is no saved task for '{}'!", targetOrName)
                errors += 1
            else:
                removeTask(taskData)
        self.save()
        # TODO: move to function, fix, optimize
        logger.debug("remove empty folders")
        cleaner = Cleaner(self.fs, removedFiles)
        rDirs, rFiles = cleaner.clean()
        for d in rDirs:
            infof('Removed folder: {}', d)
        for f in rFiles:
            infof('Removed file: {}', f)
        return not errors
