class Depth(object):

    def __init__(self, lower=None, higher=None):
        self.lower, self.higher = lower, higher


class Node(object):

    def __init__(self):
        self.depth = None
        self.selectCnt = 0

    def getId(self):
        assert False

    def getLeftNodes(self):
        assert False

    def getLeftNodeCount(self):
        assert False

    def getRightNodes(self):
        assert False


class FileNode(Node):

    def __init__(self, fpath):
        super(FileNode, self).__init__()
        self.fpath = fpath
        self.targetOf = None
        self.generatedOf = None
        self.providedOf = None
        self.fileDepOf = []
        self.dynFileDepOf = []

    def getId(self):
        return self.fpath

    def getLeftNodes(self):
        return self.fileDepOf + self.dynFileDepOf

    def getLeftNodeCount(self):
        return len(self.fileDepOf) + len(self.dynFileDepOf)

    def getRightNodes(self):
        assert False # TODO

    def _checkSource(self):
        assert self.targetOf is None
        assert self.generatedOf is None
        assert self.providedOf is None

    def setTargetOf(self, taskNode):
        assert isinstance(taskNode, TaskNode)
        self._checkSource()
        self.targetOf = taskNode

    def setGeneratedOf(self, taskNode):
        assert isinstance(taskNode, TaskNode)
        self._checkSource()
        self.generatedOf = taskNode

    def setProvidedOf(self, taskNode):
        assert isinstance(taskNode, TaskNode)
        self._checkSource()
        self.povidedOf = taskNode


class TaskNode(Node):

    def __init__(self, name=None):
        super(TaskNode, self).__init__()
        self.id = None
        self.name = name
        self.targets = []
        self.fileDeps = []
        self.dynFileDeps = []
        self.taskDeps = []
        self.generatedFiles = [] 
        self.providedFiles = []
        self.providedTasks = []
        self.providedOf = None
        self.taskDepOf = []

    def getId(self):
        return self.id


class DepGraph(object):

    def __init__(self):
        self.fileDict = {}  # {fileName: FileNode}
        self.taskDict = {}  # {taskName: TaskNode} # TODO: for smaller dict only named tasks should be stored here
        self.rootFileDict = {}  # {fileName: FileNode}
        self.rootTaskDict = {}  # {taskName: TaskNode}
        self.selectedFiles = {}
        self.selectedTasks = {}

    def getFileNode(self, fpath):
        node = self.fileDict.get(fpath)
        if node is None:
            node = FileNode(fpath)
            self.fileDict[fpath] = node
            self.rootFileDict[fpath] = node
        return node

    def getTaskNode(self, taskName):
        if taskName is None:
            return TaskNode(taskName)
        node = self.taskDict.get(taskName)
        if node is None:
            node = TaskNode(taskName)
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

        targets = lst(targets)
        taskId = name if name else targets[0]

        taskNode = self.getTaskNode(name)
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
                res.append(node)
            return res
        
        addCreatedFiles(taskNode.targets, lst(targets), setTargetOf)
        addCreatedFiles(taskNode.generatedFiles, lst(generatedFiles), setGeneratedOf)
        addCreatedFiles(taskNode.providedFiles, lst(providedFiles), setProvidedOf) 
        
        def appendFileDepOf(n, v): n.fileDepOf.append(v)
        def appendDynFileDepOf(n, v): n.dynFileDepOf.append(v)

        def addFileDeps(res, fpaths, appendFn):
            for fpath in fpaths:
                node = self.getFileNode(fpath)
                res.append(node)
                if node.fpath in self.rootFileDict:
                    del self.rootFileDict[node.fpath]
                appendFn(node, taskNode)
            return res
        
        addFileDeps(taskNode.fileDeps, lst(fileDeps), appendFileDepOf)
        addFileDeps(taskNode.dynFileDeps, lst(dynFileDeps), appendDynFileDepOf)

        def appendTaskDepOf(n, v): n.taskDepOf.append(v)

        def addTaskDeps(res, taskNames, appendFn):
            for taskName in taskNames:
                node = self.getTaskNode(taskName)
                res.append(node)
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

    def selectRight(self, targetOrNameList, maxDepth=1024, exclusiveChilds=True):

        touched = {}    # {nodeId: Node}
        selectedFiles = {}
        selectedTasks = {}

        def selectNode(node, depth):
            
            def select():
                selDict = selectedFiles if isinstance(node, FileNode) else selectedTasks
                selDict[node.id] = node
                newDepth = depth + 1
                for rightNode in node.getRightNodes():
                    selectNode(rightNode, newDepth)
        
            if depth == 0:
                select()
                return
            if depth >= maxDepth:
                return
            if node.selectCnt == 0:
                touched[node.getId()] = node
            node.selectCnt += 1
            if exclusiveChilds:
                # select child only if all of its parents are selected
                if node.selectCnt == node.getLeftNodeCount():
                    select()
            else:
                # select child anyway
                select()


        for targetOrName in targetOrNameList:
            node = self.taskDict.get(targetOrName)
            if node is None:
                node = self.fileDict.get(targetOrName)
            if node is not None:
                selectNode(node, 0)
            else:
                pass    # TODO error handling if needed

        # clean selectCnt
        for node in touched.values():
            node.selectCnt = 0
        return selectedFiles, selectedTasks