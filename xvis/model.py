# import depgraph as dg
import xbuild.depgraph as dg
from collections import defaultdict


class Connection(object):

    def __init__(self, leftNode, rightNode, name):
        self.leftNode, self.rightNode = leftNode, rightNode
        self.name = name

    def __repr__(self):
        return '{} <-{}- {}'.format(self.leftNode, self.name, self.rightNode)


class Node(object):

    def __init__(self, nodeId, leftCons, rightCons, order=0):
        self.id = nodeId
        self.leftCons, self.rightCons = leftCons, rightCons
        self.order = order

    def __repr__(self):
        return '{}:{}'.format(self.__class__.__name__, self.id)

    def show(self):
        return '{}:(lNodes:{}, rNodes:{})'.format(
            self.id, [c.leftNode for c in self.leftCons], [c.rightNode for c in self.rightCons])


class FileNode(Node):

    def __init__(self, nodeId, leftCons, rightCons, order=0):
        super(self.__class__, self).__init__(nodeId, leftCons, rightCons, order)


class TaskNode(Node):

    def __init__(self, nodeId, leftCons, rightCons, summary, order=0):
        super(self.__class__, self).__init__(nodeId, leftCons, rightCons, order)
        self.summary = summary


class CrossLinkNode(Node):

    def __init__(self, leftNodeId, rightNodeId, leftCon, rightCon, name, order=0):
        super(self.__class__, self).__init__(
            leftNodeId,
            leftCons=[leftCon] if leftCon else [],
            rightCons=[rightCon] if rightCon else [],
            order=order)
        self.leftNodeId, self.rightNodeId = leftNodeId, rightNodeId
        self.name = name

    def __repr__(self):
        return 'CrossLinkNode: {} <- {}'.format(self.leftNodeId, self.rightNodeId)

    
class Model(object):

    @staticmethod
    def create(depGraph):

        def createDstNode(srcNode):
            if isinstance(srcNode, dg.FileNode):
                return FileNode(srcNode.id, leftCons=[], rightCons=[])
            elif isinstance(srcNode, dg.TaskNode):
                return TaskNode(srcNode.id, leftCons=[], summary='', rightCons=[])
            else:
                assert False

        def getLeftConDescs(srcNode):
            res = []    # [(leftNodeId, rightNodeId, name)]
            if isinstance(srcNode, dg.FileNode):
                # self.fileDepOf, self.dynFileDepOf
                for leftNodeDict, name in ((srcNode.fileDepOf, 'fDep'), (srcNode.dynFileDepOf, 'dfDep')):
                    for leftNodeId in leftNodeDict:
                        res.append((leftNodeId, srcNode.id, name))        
            elif isinstance(srcNode, dg.TaskNode):
                # self.targets, self.generatedFiles, self.providedFiles, self.providedTasks, self.taskDepOf
                for leftNodeDict, name in (
                    (srcNode.targets, 'trg'), (srcNode.generatedFiles, 'gen'),
                    (srcNode.providedFiles, 'pFile'), (srcNode.providedTasks, 'pTask'),
                    (srcNode.taskDepOf, 'tDep')):
                    for leftNodeId in leftNodeDict:
                        res.append((leftNodeId, srcNode.id, name))
            else:
                assert False
            return res

        def setCrossLinkIds(cols):
            for depth, nodes in enumerate(cols):
                for idx, node in enumerate(nodes):
                    if isinstance(node, CrossLinkNode):
                        node.id = '_CrossLink.{}.{}'.format(depth, idx)

        depGraph.calcDepths()
        cols = []
        # prevNodeDict = {}    # {nodeId: Node}
        rightConDict = defaultdict(list)   # {leftNodeId: [right Connection]}
        # right to left column iteration
        for srcCol in reversed(depGraph.columns):
            leftConDict = defaultdict(list)    # {leftNodeId: [left Connection]}
            col = []
            cols.insert(0, col)
            for srcNode in srcCol:
                # 1. place Node
                dstNode = createDstNode(srcNode)
                col.append(dstNode)
                # 2. bind Node to right connections
                rightConList = rightConDict.get(dstNode.id)
                if rightConList:
                    for con in rightConList:
                        con.leftNode = dstNode
                        dstNode.rightCons.append(con)
                    del rightConDict[dstNode.id]
                # 3. create left connections (these will be the right connections on next iteration)
                for leftNodeId, rightNodeId, name in getLeftConDescs(srcNode):
                    con = Connection(leftNode=None, rightNode=dstNode, name=name)
                    dstNode.leftCons.append(con)
                    leftConDict[leftNodeId].append(con)
            # 4. create CrossLinkNodes for unbound right connections
            for leftNodeId, conList in rightConDict.items():
                for con in conList:
                    #assert leftNodeId != con.rightNode.id, 'cols:{} nodeId:{}'.format(
                    #    len(cols), leftNodeId)
                    crNode = CrossLinkNode(
                        leftNodeId=leftNodeId, rightNodeId=con.rightNode.id,
                        leftCon=None, rightCon=con, name=con.name)
                    # Who sets CrossLinkNode.leftCon?
                    lCon = Connection(leftNode=None, rightNode=crNode, name=con.name)
                    crNode.leftCons.append(lCon)
                    con.leftNode = crNode
                    col.append(crNode)
                    # also update leftConDict
                    leftConDict[leftNodeId].append(lCon) # con
            rightConDict.clear()
            rightConDict.update(leftConDict)
            leftConDict.clear()
        setCrossLinkIds(cols)
        Model.calcOrders(cols)
        if False:
            print '--- col0 ---'
            for node in cols[0]:
                print node.show()
            print '--- col1 ---'
            for node in cols[1]:
                print node.show()
        return Model(cols)

    @staticmethod
    def calcOrders(cols):
        for col in cols:
            for o, node in enumerate(col):
                node.order = o

    def __init__(self, columns):
        self.columns = columns


def variations(cnt):

    def vary(lst):
        # res = []
        for i in range(len(lst)):
            subLst = lst[:]
            a = subLst.pop(i)
            if len(subLst) > 1:
                for vsub in vary(subLst):
                    yield [a] + vsub
                    # res.append([a] + vsub)
            else:
                yield [a] + subLst
                #res.append([a] + subLst)
        #return res
    
    return vary(range(cnt))


for i, v in enumerate(variations(3)):
    print '{}: {}'.format(i, v)

    