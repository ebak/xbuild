from collections import OrderedDict


class UserData(object):
    pass


class Depth(object):

    def __init__(self, lower=None, higher=None):
        self.lower, self.higher = lower, higher

    def reset(self):
        self.lower = self.higher = None

    def set(self,v):
        if self.lower is None or v < self.lower:
            self.lower = v
        if self.higher is None or v > self.higher:
            self.higher = v


class Node(object):

    @staticmethod
    def concatDicts(*dicts):
        # ordering is not needed
        res = {}
        for d in dicts:
            res.update(d)
        return res

    @staticmethod
    def sumLengths(*containers):
        res = 0
        for c in containers:
            res += len(c)
        return res

    def __init__(self, nodeId):
        self.id = nodeId
        self.depth = Depth()
        self.selectCnt = 0
        self.data = UserData()
        # cache
        self._resetCache()

    def __repr__(self):
        return self.id
    
    def _resetCache(self):
        # self.leftNodeDicts= None
        # self.rightNodeDicts = None
        self.leftNodes = None
        self.rightNodes = None
        self.leftNodeList = None
        self.rightNodeList = None

    def getId(self):
        return self.id
    
    def _unlinkNode(self, provFn, nodeId):
        for nodeDict in provFn():
            if nodeId in nodeDict:
                del nodeDict[nodeId]
                self._resetCache()
                return

    def unlinkLeftNode(self, nodeId):
        self._unlinkNode(self.getLeftNodeDicts, nodeId)

    def unlinkRightNode(self, nodeId):
        self._unlinkNode(self.getRightNodeDicts, nodeId)

    def floats(self):
        return self.getLeftNodeCount() + self.getRightNodeCount() == 0
    
    def getLeftNodeList(self):
        if self.leftNodeList is None:
            self.leftNodeList = self.getLeftNodes().values()
        return self.leftNodeList

    def getRightNodeList(self):
        if self.rightNodeList is None:
            self.rightNodeList = self.getRightNodes().values()
        return self.rightNodeList

    def getLeftNodes(self):
        if self.leftNodes is None:
            dicts = self.getLeftNodeDicts()
            self.leftNodes = Node.concatDicts(*dicts)
        return self.leftNodes

    def getLeftNodeCount(self):
        return len(self.getLeftNodes())

    def getRightNodeCount(self):
        return len(self.getRightNodes())

    def getRightNodes(self):
        if self.rightNodes is None:
            dicts = self.getRightNodeDicts()
            self.rightNodes = Node.concatDicts(*dicts)
        return self.rightNodes

    def getLeftNodeDicts(self):
        assert False

    def getRightNodeDicts(self):
        assert False


class FileNode(Node):

    def __init__(self, fpath):
        super(self.__class__, self).__init__(fpath)
        self.fpath = fpath
        # referred nodes should be stored in fast lookup, fast edit container (dict, ordereddict),
        # because on the fly referred node removal is needed.
        self.targetOf = {}
        self.generatedOf = {}
        self.providedOf = {}   # if a file is provided than it is also a task target
        self.fileDepOf = OrderedDict()
        self.dynFileDepOf = OrderedDict()

    def getLeftNodeDicts(self):
        return self.fileDepOf, self.dynFileDepOf

    def getRightNodeDicts(self):
        return self.targetOf, self.generatedOf, self.providedOf

    def setTargetOf(self, taskNode):
        assert not self.targetOf
        assert not self.generatedOf
        self.targetOf[taskNode.id] = taskNode

    def setGeneratedOf(self, taskNode):
        assert not self.targetOf
        assert not self.generatedOf
        self.generatedOf[taskNode.id] = taskNode

    def setProvidedOf(self, taskNode):
        assert not self.providedOf
        assert not self.generatedOf
        self.providedOf[taskNode.id] = taskNode


class TaskNode(Node):

    def __init__(self, taskId, name=None):
        super(self.__class__, self).__init__(taskId)
        self.name = name
        self.targets = {}   # {fpath: FileNode}
        self.fileDeps = OrderedDict()
        self.dynFileDeps = OrderedDict()
        self.taskDeps = OrderedDict()
        self.generatedFiles = OrderedDict()
        self.providedFiles = OrderedDict()
        self.providedTasks = OrderedDict()
        self.providedOf = OrderedDict()
        self.taskDepOf = OrderedDict()

    def getCreatedLeftNodeDicts(self):
        return \
            self.targets, self.generatedFiles, \
            self.providedFiles, self.providedTasks

    def getCreatedLeftNodeList(self):
        res = []
        for d in self.getCreatedLeftNodeDicts():
            res += d.values()
        return res

    def getLeftNodeDicts(self):
        return \
            self.targets, self.generatedFiles, \
            self.providedFiles, self.providedTasks, self.taskDepOf

    def getRightNodeDicts(self):
        return self.fileDeps, self.dynFileDeps, self.taskDeps, self.providedOf


class DepGraph(object):

    def __init__(self):
        self.fileDict = {}  # {fileName: FileNode}
        self.taskDict = {}  # {taskName: TaskNode} # TODO: for smaller dict only named tasks should be stored here
        self.rootFileDict = {}  # {fileName: FileNode}
        self.rootTaskDict = {}  # {taskName: TaskNode}
        self.selectedFiles = {}
        self.selectedTasks = {}
        # self.hasDephts = False
        self.columns = None     # depth columns

    def getFileNode(self, fpath):
        node = self.fileDict.get(fpath)
        if node is None:
            node = FileNode(fpath)
            self.fileDict[fpath] = node
            self.rootFileDict[fpath] = node
        return node

    def getTaskNode(self, taskId, taskName):
        if taskName is None:
            assert taskName not in self.taskDict
            return TaskNode(taskName)
        node = self.taskDict.get(taskName)
        if node is None:
            node = TaskNode(taskId, taskName)
            if taskName:
                self.taskDict[taskName] = node
                self.rootTaskDict[taskName] = node
        return node

    def addTask(
        self, name=None, targets=None, fileDeps=None, dynFileDeps=None,
        taskDeps=None, generatedFiles=None, providedFiles=None, providedTasks=None):

        def lst(var):
            if var is None:
                return []
            else:
                assert isinstance(var, list)
                return var

        self.columns = None
        targets = lst(targets)
        taskId = name if name else targets[0]

        taskNode = self.getTaskNode(taskId, name)
        taskNode.id = taskId
        
        def setTargetOf(node, value): node.setTargetOf(value)
        def setGeneratedOf(node, value): node.setGeneratedOf(value)
        def setProvidedOf(node, value): node.setProvidedOf(value)
        
        def addCreatedFiles(res, fpaths, setFn):
            if len(fpaths) and taskNode.name in self.rootTaskDict:
                del self.rootTaskDict[taskNode.name]
            for fpath in fpaths:
                node = self.getFileNode(fpath)
                setFn(node, taskNode)
                res[node.id] = node
            return res
        
        addCreatedFiles(taskNode.targets, lst(targets), setTargetOf)
        addCreatedFiles(taskNode.generatedFiles, lst(generatedFiles), setGeneratedOf)
        addCreatedFiles(taskNode.providedFiles, lst(providedFiles), setProvidedOf) 
        
        def appendFileDepOf(n, v): n.fileDepOf[v.id] = v
        def appendDynFileDepOf(n, v): n.dynFileDepOf[v.id] = v

        def addFileDeps(res, fpaths, appendFn):
            for fpath in fpaths:
                node = self.getFileNode(fpath)
                res[node.id] = node
                if node.fpath in self.rootFileDict:
                    del self.rootFileDict[node.fpath]
                appendFn(node, taskNode)
            return res
        
        addFileDeps(taskNode.fileDeps, lst(fileDeps), appendFileDepOf)
        addFileDeps(taskNode.dynFileDeps, lst(dynFileDeps), appendDynFileDepOf)

        def appendTaskDepOf(n, v): n.taskDepOf[v.id] = v

        def addTaskDeps(res, taskNames, appendFn):
            for taskName in taskNames:
                node = self.getTaskNode(taskName, taskName)
                res[node.id] = node
                if node.name in self.rootTaskDict:
                    del self.rootTaskDict[taskName]
                appendFn(node, taskNode)

        addTaskDeps(taskNode.taskDeps, lst(taskDeps), appendTaskDepOf)
        
        providedTasks = lst(providedTasks)
        if len(providedTasks) and taskNode.name in self.rootTaskDict:
            del self.rootTaskDict[taskNode.name]
        for provTaskName in providedTasks:
            node = self.getTaskNode(provTaskName)
            node.providedOf = taskNode
            taskNode.providedTasks.append(node)
        return taskNode

    def removeTask(self, taskNode):
        
        if taskNode.name and taskNode.name not in self.taskDict:
            # it may be already removed as it could become floating node at removal of other nodes
            return
        
        def unlinkLeft(rightNode, leftNodeId): rightNode.unlinkLeftNode(leftNodeId)
        def unlinkRight(leftNode, rightNodeId): leftNode.unlinkRightNode(rightNodeId)
        
        def unlink(nodeList, unlinkerFn):
            for node in nodeList:
                unlinkerFn(node, taskNode.id)
                if node.floats():
                    self._unregNode(node)

        self.columns = None
        # unlink targets, generated files, provided files?
        unlink(taskNode.getLeftNodeList(), unlinkRight)
        # unlink fileDeps, dynFileDeps, taskDeps
        unlink(taskNode.getRightNodeList(), unlinkLeft)
        self._unregNode(taskNode)

    def getTask(self, targetOrTaskName):
        task = self.taskDict.get(targetOrTaskName)
        if task is None:
            target = self.fileDict.get(targetOrTaskName)
            if target is not None:
                # get task for target
                return target.targetOf.values()[0] if target.targetOf else None
        return task

    def getAllTasks(self):
        taskIdDict = self.taskDict.copy()    # {id: TaskNode}
        for fileNode in self.fileDict.values():
            for taskNode in fileNode.targetOf.values():   # at most 1 iteration
                if taskNode.id not in taskIdDict:
                    taskIdDict[taskNode.id] = taskNode
        return taskIdDict

    def selectRight(self, targetOrNameList, maxDepth=1024, exclusiveChilds=True, selectTopOutputs=True, leaveLeaves=False):
        '''
        exclusiveChilds:
            If True, only those children are selected (rightNodes) which are not belonging to
            unselected parents (leftNodes)
        selectTopOutputs:
            If True and the top level node is a TaskNode, than all of its outputs (targets, generatedFiles, etc.)
            are selected.
        Returns: (selectedFiles, selectedTasks)
        '''

        touched = {}    # {nodeId: Node}
        selectedFiles = {}
        selectedTasks = {}

        def selectNode(node, depth):
            
            def select():
                selDict = selectedFiles if isinstance(node, FileNode) else selectedTasks
                nId = node.getId()
                if nId not in selDict:
                    selDict[nId] = node
                    newDepth = depth + 1
                    for rightNode in node.getRightNodeList():
                        selectNode(rightNode, newDepth)
                        # If rightNode is a TaskNode via taskDep, all of its targets have to be selected.
                        if isinstance(rightNode, TaskNode) and isinstance(node, TaskNode):
                            # rightNode is a task dependency
                            for trgNode in rightNode.targets.values():
                                selectNode(trgNode, depth)
        
            if depth == 0:
                select()
                return
            if depth >= maxDepth:
                return
            if leaveLeaves and node.getRightNodeCount() == 0:
                return
            if node.selectCnt == 0:
                touched[node.getId()] = node
            node.selectCnt += 1
            if exclusiveChilds:
                # select child only if all of its parents are selected
                if node.selectCnt >= node.getLeftNodeCount():
                    # selectCnt can be greater than leftNodeCount. When node is a task target, it may not be referred
                    # directly, but its task may be referred by its name.
                    select()
            else:
                # select child anyway
                select()

        topTasks = []
        for targetOrName in targetOrNameList:
            node = self.taskDict.get(targetOrName)
            if node is None:
                node = self.fileDict.get(targetOrName)
            if node is not None:
                if selectTopOutputs and isinstance(node, TaskNode):
                    topTasks.append(node)
                selectNode(node, 0)
            else:
                pass    # TODO error handling if needed
        
        # selectTopOutputs
        for taskNode in topTasks:
            for leftNode in taskNode.getCreatedLeftNodeList():
                selectNode(leftNode, 0)

        # clean selectCnt
        for node in touched.values():
            node.selectCnt = 0
        return selectedFiles, selectedTasks

    def calcDepths(self):
        if self.columns is not None:
            return
        columns = []
        depth = 0
        nodes = self.rootFileDict.values() + self.rootTaskDict.values()
        while len(nodes) > 0:
            columns.append(nodes)
            rightNodeDict = {}
            for node in nodes:
                node.depth.set(depth)
                for rnDict in node.getRightNodeDicts():
                    rightNodeDict.update(rnDict)
            depth += 1
            nodes = rightNodeDict.values()
        self.columns = []
        for depth, nodes in enumerate(columns):
            self.columns.append([n for n in nodes if n.depth.higher == depth])

    def _unregFile(self, fpath):
        # TODO: better function name (maybe some LUT class instead of the 2 dicts)
        del self.fileDict[fpath]
        if fpath in self.rootFileDict:
            del self.rootFileDict[fpath]

    def _unregTask(self, taskName):
        del self.taskDict[taskName]
        if taskName in self.rootTaskDict:
            del self.rootTaskDict[taskName]

    def _unregNode(self, node):
        if isinstance(node, FileNode):
            self._unregFile(node.id)
        elif node.name:
            self._unregTask(node.name)

