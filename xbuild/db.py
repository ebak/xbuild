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
        if storeHash and bldr.needsHashCheck(task):
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
            taskNode.data.garbageDirs = taskData.get('grbDirs', [])
        return graph

    def loadGraph(self, graph):
        taskNodes = graph.getAllTasks()
        self.taskIdSavedTaskDict.clear()
        self.targetSavedTaskDict.clear()
        for taskNode in taskNodes:
            data = {}
            def setF(key, field):
                if field:
                    if isinstance(field, list):
                        for i in field:
                            assert isinstance(i, unicode) or isinstance(i, str), '{} {}: {}'.format(key, type(i), i)
                    elif not isinstance(field, unicode) or not isinstance(field, str):
                        '{} {}: {}'.format(key, type(field), field)
                    # assert isinstance(field, str) or isinstance(field, list), '{} {}: {}'.format(key, type(field), field)
                    data[key] = field
            setF('name', taskNode.name)
            setF('trgs', taskNode.targets.keys())
            setF('fDeps', taskNode.fileDeps.keys())
            setF('dfDeps', taskNode.dynFileDeps.keys())
            setF('tDeps', taskNode.taskDeps.keys())
            setF('gFiles', taskNode.generatedFiles.keys())
            setF('pFiles', taskNode.providedFiles.keys())
            setF('pTasks', taskNode.providedTasks.keys())
            setF('grbDirs', taskNode.data.garbageDirs)
            self.taskIdSavedTaskDict[taskNode.id] = data
            for trg in data.get('trgs', []):
                self.targetSavedTaskDict[trg] = data

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
        if not targetOrNameList:
            targetOrNameList = graph.rootFileDict.keys() + graph.rootTaskDict.keys()
        selectedFiles, selectedTasks = graph.selectRight(targetOrNameList, exclusiveChilds=True, selectTopOutputs=True, leaveLeaves=True)
        # de-select targets and generated files if their task are not selected
        deselect = []
        for fileName, fileNode in selectedFiles.items():
            for taskName in fileNode.targetOf.keys() + fileNode.generatedOf.keys():
                if taskName not in selectedTasks:
                    deselect.append(fileName)
        for fileName in deselect:
            del selectedFiles[fileName]
        # infof('selectedFiles: {}', selectedFiles)
        # infof('selectedTasks: {}', selectedTasks)
        filesToRemove = selectedFiles.keys()
        dirsToRemove = []
        for tNode in selectedTasks.values():
            dirsToRemove += tNode.data.garbageDirs
        cleaner = Cleaner(self.fs, filesToRemove + extraFiles, dirsToRemove)
        rDirs, rFiles = cleaner.clean()
        for d in rDirs:
            infof('Removed folder: {}', d)
        for f in rFiles:
            infof('Removed file: {}', f)
        # remove selected tasks from graph
        for taskNode in selectedTasks.values():
            graph.removeTask(taskNode)
        self.loadGraph(graph)
        return True # not errors

    def registerFilesToClean(self, fpaths):
        for f in fpaths:
            self.filesToClean.add(f)

    def cleanAll(self):
        self.clean(None, list(self.filesToClean))
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
            # print 'subDepth: {}'.format(subDepth)
            for nameOrTarget in nameOrTargetList:
                taskData = self.getTaskData(nameOrTarget)
                # print 'nameOrTarget: {}, data: {}'.format(nameOrTarget, taskData is not None)
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