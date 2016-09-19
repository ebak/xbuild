# import depgraph as dg
from .. import depgraph as dg
from collections import defaultdict


class Connection(object):

    def __init__(self, leftNode, rightNode, name):
        self.leftNode, self.rightNode = leftNode, rightNode
        self.name = name


class Node(object):

    def __init__(self, nodeId, leftCons, rightCons, order=0):
        self.id = nodeId
        self.leftCons, self.rightCons = leftCons, rightCons
        self.order = order

class FileNode(object):

    def __init__(self, nodeId, leftCons, rigthCons, order=0):
        super(self.__class__.name, self).__init__(nodeId, leftCons, rigthCons, order)


class TaskNode(object):

    def __init__(self, nodeId, leftCons, rigthCons, summary, order=0):
        super(self.__class__.name, self).__init__(nodeId, leftCons, rigthCons, order)
        self.summary = summary


class CrossLinkNode(object):

    def __init__(self, nodeId, leftCons, rigthCons, name, order=0):
        super(self.__class__.name, self).__init__(nodeId, leftCons, rigthCons, order)
        self.name = name


class Column(object):

    def __init__(self, nodes):
        self.nodes = []
        self.idDict = {}
        for i, node in enumerate(nodes):
            self.nodes.append(node)
            node.order = i
            self.idDict[node.id] = node

    
class Model(object):

    @staticmethod
    def create(depGraph):

        def connectLeftNodes(leftToRightDict, rightNodes):
            for rightNode in rightNodes:
                for leftNode in rightNode.leftNodes:
                    leftToRightDict[leftNode.id][rightNode.id].rightNode = rightNode

        def createConnections(leftNode, rightNodeDict, name, newLeftToRightDict, rightCons):
            for rightNodeId in rightNodeDict.keys():
                con = Connection(leftNode=leftNode, rightNode=None, name=name)
                rightCons.append(con)
                newLeftToRightDict[leftNode.id][rightNodeId] = con
            
        depGraph.calcDepths()
        cols = []
        leftToRightDict = {}   # {leftNodeId: {rightNodeId: Connection}}
        prevCrossLinks = {} # {crossLinkId: CrossLinkNode}
        for depth, srcCol in enumerate(depGraph.columns):
            dstCol = []
            cols.append(dstCol)
            newLeftToRightDict = defaultdict(dict)  # {leftNodeId: {rightNodeId: Connection}}
            for order, srcNode in enumerate(srcCol):
                if srcNode.depth.higher == depth:
                    # real node at depth
                    if isinstance(srcNode, dg.FileNode):
                        dstNode = FileNode(
                            srcNode.id, leftCons=[], rigthCons=[], order=order)
                        createConnections(srcNode, srcNode.targetOf, 'trg', newLeftToRightDict, dstNode.rightCons)
                        createConnections(srcNode, srcNode.generatedOf, 'gen', newLeftToRightDict, dstNode.rightCons)
                        createConnections(srcNode, srcNode.providedOf, 'prov', newLeftToRightDict, dstNode.rightCons)
                    else:
                        dstNode = TaskNode(
                            srcNode.id, leftCons=[], rigthCons=[], order=order)
                        # self.fileDeps, self.dynFileDeps, self.taskDeps, self.providedOf
                        for nodeDict, name in (
                            (srcNode.fileDeps, 'fDep'), (srcNode.dynFileDeps, 'dfDep'),
                            (srcNode.taskDeps, 'tDep'), (srcNode.providedOf, 'prov')
                        ):
                            createConnections(srcNode, nodeDict, name, newLeftToRightDict, dstNode.rightCons)
                else:
                    dstNode = CrossLinkNode(
                        srcNode.id, leftCons=[], rigthCons=[], order=order)
                    createConnections(srcNode, srcNode.targetOf, 'trg', newLeftToRightDict, dstNode.rightCons)
                    pass
                dstCol.append(dstNode)
            connectLeftNodes(leftToRightDict, dstCol)
            leftToRightDict = newLeftToRightDict


    def __init__(self):
        self.columns = []


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

    