class Depth(object):

    def __init__(self, lower=None, higher=None):
        self.lower, self.higher = lower, higher

class Node(object):

    def __init__(self):
        self.depth = None

    def getId(self):
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
        taskDeps=None, generatedFile=None, providedFiles=None, providedTasks=None):

        def lst(var):
            if var is None:
                return []
            else:
                assert isinstance(var, list)
                return var

        targets = lst(targets)
        taskId = name if name else targets[0]
        fileDeps = lst(fileDeps)
        dynFileDeps = lst(dynFileDeps)
        taskDeps = lst(taskDeps)
        generatedFiles = lst(generatedFile) 
        providedFiles = lst(providedFiles)
        providedTasks = lst(providedTasks)

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
        
        addCreatedFiles(taskNode.targets, targets, setTargetOf)
        addCreatedFiles(taskNode.generatedFiles, generatedFiles, setGeneratedOf)
        addCreatedFiles(taskNode.providedFiles, providedFiles, setProvidedOf) 
        
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
        
        addFileDeps(taskNode.fileDeps, fileDeps, appendFileDepOf)
        addFileDeps(taskNode.dynFileDeps, dynFileDeps, appendDynFileDepOf)

        def appendTaskDepOf(n, v): n.taskDepOf.append(v)

        def addTaskDeps(res, taskNames, appendFn):
            for taskName in taskNames:
                node = self.getTaskNode(taskName)
                res.append(node)
                if node.name in self.rootTaskDict:
                    del self.rootTaskDict[taskName]
                appendFn(node, taskNode)

        addTaskDeps(taskNode.taskDeps, taskDeps, appendTaskDepOf)
        
        # taskNode.providedTasks = []
        if len(providedTasks) and taskNode.name in self.rootTaskDict:
            del self.rootTaskDict[taskNode.name]
        for provTaskName in providedTasks:
            node = self.getTaskNode(provTaskName)
            node.providedOf = taskNode
            taskNode.providedTasks.append(node)