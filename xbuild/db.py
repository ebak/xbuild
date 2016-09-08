import os
import json
from hash import HashDict
from fs import Cleaner
from console import logger, infof, warnf, errorf
from collections import defaultdict
from xbuild.pathformer import NoPathFormer

class DB(object):
    
    Version = [0, 0, 0]

    nameSet = set()

    @staticmethod
    def create(name, fs, pathFormer=NoPathFormer()):
        if name in DB.nameSet:
            errorf('DB "{}" is already created!', name)
            return None
        DB.nameSet.add(name)
        return DB(name, fs, pathFormer)

    def __init__(self, name, fs, pathFormer):
        self.name = name
        self.fs = fs
        self.pathFormer = pathFormer
        self.taskIdSavedTaskDict = {}   # {taskId: saved task data}
        self.targetSavedTaskDict = {}   # {targetName: saved task data}
        self.hashDict = HashDict()
        self.filesToClean = set()       # additional files for cleanAll
        pass

    def forget(self):
        DB.nameSet.remove(self.name)

    def load(self):
        fpath = '{}.xbuild'.format(self.name)
        if not self.fs.isfile(fpath):
            return
        try:
            jsonObj = json.loads(self.fs.read(fpath)) # loads() for easier unit test
        except:
            warnf("'{}' is corrupted! JSON load failed!", fpath)
            raise
            return
        # TODO: check version
        if type(jsonObj) is not dict:
            warnf("'{}' is corrupted! Top level dict expected!", fpath)
            return
        hashDictJsonObj = jsonObj.get('HashDict')
        if hashDictJsonObj is None:
            warnf("'{}' is corrupted! 'HashDict' section is missing!", fpath)
            return
        if not self.hashDict._loadJsonObj(hashDictJsonObj, warnf):
            warnf("'{}' is corrupted! Failed to load 'HashDict'!", fpath)
            return
        taskDict = jsonObj.get('Task')
        if taskDict is None:
            warnf("'{}' is corrupted! 'Task' section is missing!", fpath)
            return
        if type(taskDict) is not dict:
            warnf("'{}' is corrupted! 'Task' section is not dict!", fpath)
            return
        self.taskIdSavedTaskDict = taskDict
        self.filesToClean = set(jsonObj.get('FilesToClean', []))    # TODO: type validation
        emptyList = []
        for taskData in taskDict.values():
            for trg in taskData.get('trgs', emptyList):
                self.targetSavedTaskDict[trg] = taskData

    def save(self):
        jsonObj = {'version': [0, 0, 0]}
        jsonObj['HashDict'] = self.hashDict._toJsonObj()
        # taskIdSavedTaskDict
        jsonObj['Task'] = self.taskIdSavedTaskDict
        jsonObj['FilesToClean'] = list(self.filesToClean)
        fpath = '{}.xbuild'.format(self.name)
        self.fs.write(fpath, json.dumps(jsonObj, ensure_ascii=True, indent=1))  # dumps() for easier unit test

    def saveTask(self, bldr, task, storeHash=True):
        taskObj = self.taskIdSavedTaskDict.get(task.getId())
        if taskObj is None:
            taskObj = {}
            self.taskIdSavedTaskDict[task.getId()] = taskObj
            for trg in task.targets:
                self.targetSavedTaskDict[trg] = taskObj
        else:
            taskObj.clear()
        task.toDict(res=taskObj)
        if storeHash:
            self.hashDict.storeTaskHashes(bldr, task)

    def loadTask(self, task):
        # fill up task with saved data
        taskObj = self.taskIdSavedTaskDict.get(task.getId())
        if taskObj:
            task.savedFileDeps = taskObj.get('fDeps', [])
            task.savedDynFileDeps = taskObj.get('dfDeps', [])
            task.savedProvidedFiles = taskObj.get('pFiles', [])
            task.savedProvidedTasks = taskObj.get('pTasks', [])
            task.savedGeneratedFiles = taskObj.get('gFiles', [])
            meta = taskObj.get('meta', {})
            task.meta = meta

    def toGraph(self):
        from depgraph import DepGraph
        graph = DepGraph()
        for taskData in self.taskIdSavedTaskDict.values():
            taskNode = graph.addTask(
                name=taskData.get('name'),
                targets=taskData.get('trgs'),
                fileDeps=taskData.get('fDeps'),
                dynFileDeps=taskData.get('dfDeps'),
                taskDeps=taskData.get('tDeps'),
                generatedFiles=taskData.get('gFiles'),
                providedFiles=taskData.get('pFiles'),
                providedTasks=taskData.get('pTasks'))
            taskNode.data.garbageDir = taskData.get('grbDirs', [])

    def loadGraph(self, graph):
        taskNodes = graph.getAllTasks()
        self.taskIdSavedTaskDict.clear()
        for taskNode in taskNodes:
            data = {}
            def setF(key, field):
                if field:
                    data[key] = field
            setF('name', taskNode.name)
            setF('trgs', taskNode.targets)
            setF('fDeps', taskNode.fileDeps)
            setF('dfDeps', taskNode.dynFileDeps)
            setF('tDeps', taskNode.taskDeps)
            setF('gFiles', taskNode.generatedFiles)
            setF('pFiles', taskNode.providedFiles)
            setF('pTasks', taskNode.providedTasks)
            setF('grbDirs', taskNode.garbageDirs)
            self.taaskIdSavedTaskDict[taskNode.id] = data 

    def getTaskId(self, taskData):
            name = taskData.get('name')
            if name:
                return name
            return taskData.get('trgs')[0]

    def getTaskData(self, targetOrName):
        taskData = self.targetSavedTaskDict.get(targetOrName)
        if taskData is None:
            # this lookup is only good for task names
            taskData = self.taskIdSavedTaskDict.get(targetOrName)
        return taskData

    def clean(self, targetOrNameList, extraFiles=[]):
        graph = self.toGraph()
        selectedFiles, selectedTasks = graph.selectRight(targetOrNameList, exclusiveChilds=True, selectTopOutputs=True)
        filesToRemove = [fNode.fpath for fNode in selectedFiles]

    # TODO: better handling of dynFileDeps cleanup
    def cleanOld(self, targetOrNameList, extraFiles=[]):

        def getId(taskData):
            return self.getTaskId(taskData)

        removedFiles = []
        removedDirs = []
        savedParentTaskDict = defaultdict(set) # {file or taskName: set of parent tasks ids}
        
        # build savedParentTaskDict
        for taskData in self.taskIdSavedTaskDict.values():
            taskId = getId(taskData)
            for fileDep in taskData.get('fDeps', []) + taskData.get('dfDeps', []):
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

        def getTaskData(targetOrName):
            return self.getTaskData(targetOrName)

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
                        if taskId in parentTasks:   # TODO: assert
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
            removeDeps('dfDeps', removeFileTarget)
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
            # remove garbage directories
            for garbageDir in taskData.get('grbDirs', []):
                removedDirs.append(garbageDir)
            
        
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
        logger.debug("remove files and empty folders")
        cleaner = Cleaner(self.fs, removedFiles + extraFiles, removedDirs)
        rDirs, rFiles = cleaner.clean()
        for d in rDirs:
            infof('Removed folder: {}', d)
        for f in rFiles:
            infof('Removed file: {}', f)
        return not errors

    def getTopLevelTaskIds(self):
        targetParentTaskDict = defaultdict(list)   # {target: [parentTask]}
        taskNameParentTaskDict = defaultdict(list) # {taskName: [parentTask]}
        providerTaskDict = {}  # {target or task name: providerTask}
        for taskData in self.taskIdSavedTaskDict.values():
            for fDep in taskData.get('fDeps', []):
                targetParentTaskDict[fDep].append(taskData)
            for tDep in taskData.get('tDeps', []):
                taskNameParentTaskDict[tDep].append(taskData)
            for pEnt in taskData.get('pFiles', []) + taskData.get('pTasks', []):
                providerTaskDict[pEnt] = taskData
                
        def hasIndependentTargets(taskData):
            '''Returns False when the target is a dependency for an other task.'''
            for trg in taskData.get('trgs', []):
                if len(targetParentTaskDict[trg]) or trg in providerTaskDict:
                    return False
            return True

        res = []
        for taskId, taskData in self.taskIdSavedTaskDict.items():
            taskName = taskData.get('name')
            if taskName and len(taskNameParentTaskDict[taskName]):
                continue
            if hasIndependentTargets(taskData):
                res.append(taskId)
        return res

    def registerFilesToClean(self, fpaths):
        for f in fpaths:
            self.filesToClean.add(f)

    def cleanAll(self):
        self.clean(self.getTopLevelTaskIds(), list(self.filesToClean))
        self.filesToClean.clear()  # TODO: remove these files also from the DB

    def genPlantUML(self):
    
        def noEncode(fpath):
            return fpath
    
        def encode(fpath):
            return self.pathFormer.encode(fpath)
    
        def arrowLines(taskIdxStr, arrow, field, text, encode=noEncode):
            res = ''
            for e in taskData.get(field, []):
                res += '[{}] {} () "{}" : {}\n'.format(taskIdxStr, arrow, encode(e), text)
            return res
            
        res = "@startuml\n"
        res += "left to right direction\n"
        idIdxMap = {}
        lastIdx = 0
        # build idIdxMap first
        for taskId in self.taskIdSavedTaskDict:
            idIdxMap[taskId] = 'T{}'.format(lastIdx)
            lastIdx += 1
        for taskId, taskData in self.taskIdSavedTaskDict.items():
            # print 'taskId: ' + taskId
            idx = idIdxMap[taskId]
            # "Task: objs/main.o" as [Task0]
            res += '"Task: {}" as [{}]\n'.format(encode(taskId), idx)
            # targets
            # [Task0] --> () "objs/main.o" : trg
            res += arrowLines(idx, '-up->', 'trgs', 'trg', encode)
            # generated files
            res += arrowLines(idx, '.up.>', 'gFiles', 'gen', encode)
            # provided files
            res += arrowLines(idx, '.up.>', 'pFiles', 'prov', encode)
            # file dependencies
            res += arrowLines(idx, '<--', 'fDeps', 'fDep', encode)
            # dynamic file dependencies
            res += arrowLines(idx, '<--', 'dfDeps', 'dfDep', encode)
            # task dependencies
            # [Task2] --> [Task1] : tDep
            for tDep in taskData.get('tDeps', []):
                if tDep in idIdxMap:
                    res += '[{}] <-- [{}] : tDep\n'.format(idx, idIdxMap[tDep])
                    # TODO: handle broken task dependency
        return res + '@enduml\n'

    def getPartDB(self, nameOrTargetList, depth=4):

        db = DB(self.name, self.fs, self.pathFormer)
        
        def put(nameOrTargetList, depth):
            subDepth = depth - 1
            print 'subDepth: {}'.format(subDepth)
            for nameOrTarget in nameOrTargetList:
                taskData = self.getTaskData(nameOrTarget)
                print 'nameOrTarget: {}, data: {}'.format(nameOrTarget, taskData is not None)
                if taskData:
                    tid = self.getTaskId(taskData)
                    db.taskIdSavedTaskDict[tid] = taskData
                    for trg in taskData.get('trgs', []):
                        db.targetSavedTaskDict[trg] = taskData
                    if subDepth > 0:
                        deps = taskData.get('fDeps', []) + taskData.get('tDeps', []) + taskData.get('dfDeps', [])
                        put(deps, subDepth)
        
        # print 'depth:{}'.format(depth)
        # print 'targetSavedTaskDict: {}'.format(self.targetSavedTaskDict)
        put(nameOrTargetList, depth)
        return db