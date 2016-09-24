import PyQt4
import sys
from collections import defaultdict
from PyQt4 import QtGui, QtCore
from model import Model, FileNode, TaskNode, CrossLinkNode
from compiler.ast import Node

Qt = QtCore.Qt
# http://doc.qt.io/qt-4.8/qgraphicsview.html

def getText(node):
    if isinstance(node, TaskNode):
        return 'Task: ' + node.id
    elif isinstance(node, FileNode):
        return 'File: ' + node.id
    return None


class Cfg(object):
    
    NodeFontName = 'Sans'
    NodeFontSize = 12
    NodeFont = QtGui.QFont(NodeFontName, NodeFontSize)
    ConSpacing = 10
    NodeSpacing = 20
    GenPen = QtGui.QPen(Qt.DashLine)
    GenPen.setColor(QtGui.QColor(0, 130, 130))
    GenPen.setWidth(1)
    NormPen = QtGui.QPen(Qt.SolidLine)
    NodeWidthInc = 20
    NodeHeight = 30
    CrossLinkHeight = 10
    MinHorizontalColumnSpacing = 100


def getPen(name):
    return Cfg.GenPen if name in ('pFile', 'gen', 'pTask') else Cfg.NormPen


class VisNode(object):
    
    def __init__(self, node, width, x=0, y=0):
        '''x, y - vertical center on left side'''
        self.node = node        
        self.width = width
        self.leftWallH = Cfg.ConSpacing * (len(node.leftCons) - 1)
        self.rightWallH = Cfg.ConSpacing * (len(node.rightCons) - 1)
        nodeHeight = Cfg.CrossLinkHeight if isinstance(node, CrossLinkNode) else Cfg.NodeHeight
        self.boxH = max(self.leftWallH, self.rightWallH, nodeHeight)
        self.hBoxH = 0.5 * self.boxH
        self.setPos(x, y)

    def setPos(self, x, y):
        self.x, self.y = x, y
        self.lwy0 = self.y - 0.5 * self.leftWallH
        self.lwy1 = self.lwy0 + self.leftWallH
        self.rwy0 = self.y - 0.5 * self.rightWallH
        self.rwy1 = self.rwy0 + self.rightWallH
        self.y0 = self.y - 0.5 * self.boxH
        self.y1 = self.y + self.boxH
        # ry0 = yPos + 0.5 * (boxH - rectH)

    def setY(self, y):
        self.setPos(self.x, y)

    def render(self, scene):
        if isinstance(self.node, CrossLinkNode):
            scene.addLine(self.x, self.y, self.x + self.width, self.y, getPen(self.node.name))
        else:
            scene.addLine(self.x, self.lwy0, self.x, self.lwy1)
            xPosR = self.x + self.width
            scene.addLine(xPosR, self.rwy0, xPosR, self.rwy1)
            ry0 = self.y - 0.5 * Cfg.NodeHeight
            scene.addRect(self.x, ry0, self.width, Cfg.NodeHeight)
            textItem = scene.addText(getText(self.node), Cfg.NodeFont)
            br = textItem.boundingRect()
            textItem.setX(self.x + 0.5 * (self.width - br.width()))
            textItem.setY(ry0 + 0.5 * (Cfg.NodeHeight - br.height()))
            

class MyView(QtGui.QGraphicsView):

    @staticmethod
    def adjustVerticalColumnPlacement(prevVNodes, vNodes):
        if prevVNodes:
            prevY0, prevY1 = prevVNodes[0].y0, prevVNodes[-1].y1
            prevH = prevY1 - prevY0 
            y0, y1 = vNodes[0].y0, vNodes[-1].y1
            h = y1 - y0
            # scan range: y0 = prevY0 -> y1 = prevY1
            scanDepth = 5
            scanRes = 5
            scanRange = max(scanRes, abs(h - prevH))
            yOffs0 = y0 - prevY0 - scanRange  # TODO: !!!!
            yOffs1 = yOffs0 + scanRange
            print 'prevY0:{}, prevY1:{}, y0:{}, y1:{}, yOffs0:{}, yOffs1:{}, scanRange:{}'.format(
                prevY0, prevY1, y0, y1, yOffs0, yOffs1, scanRange)
            bestYOffs = (0, sys.maxint)     # (yOffs, yDeltaSum)
            yDeltaSumDict = {}  # {yOffs, yDeltaSum}
            yDict = {n.node.id: n.y for n in vNodes}
            print 'yDict={}'.format(yDict)
            while scanDepth > 0:
                print 'scanDepth: {}'.format(scanDepth)
                yStep = scanRange / (scanRes - 1)
                for _ in range(scanRes):
                    yOffs = int(round(yOffs0))
                    if yOffs not in yDeltaSumDict:
                        yDeltaSum = 0
                        for prevVNode in prevVNodes:
                            for rCon in prevVNode.node.rightCons:
                                y = yDict[rCon.rightNode.id] + yOffs
                                yDeltaSum += y - prevVNode.y
                                # yDeltaSum += prevVNode.y - y
                        yDeltaSum = abs(yDeltaSum)
                        print 'yOffs:{}, yDeltaSum: {}'.format(yOffs, yDeltaSum)
                        yDeltaSumDict[yOffs] = yDeltaSum
                        if yDeltaSum < bestYOffs[1]:
                            bestYOffs = (yOffs, yDeltaSum)
                    yOffs0 += yStep
                if yStep <= 1:
                    break
                # calc new xOffs0 and scanRange
                scanRange = max(scanRes, scanRange * float(2) /  scanRes)
                yOffs0 = bestYOffs[0] - 0.5 * scanRange
                scanDepth -= 1
            yOffs = bestYOffs[0]
            print 'yOffs={}'.format(yOffs)
            for vNode in vNodes:
                vNode.setY(vNode.y + yOffs)

    def __init__(self, model):
        super(self.__class__, self).__init__()
        self.setWindowTitle('Boncz Geza dependency graph visualization tool (early alpha).')

        def getMaxTextWidth(nodes):
            maxW = 0
            for n in nodes:
                text = getText(n)
                if text:
                    fm = QtGui.QFontMetrics(Cfg.NodeFont)
                    w = fm.width(text)
                    if w > maxW:
                        maxW = w
            return maxW
                
        QtGui.QGraphicsView.__init__(self)

        self.scene = QtGui.QGraphicsScene(self)
        xPos = 0
        rightConDict = defaultdict(list) # {(nodeId, rightNodeId): [(x, y)]}
        leftConDict = defaultdict(list)  # {(leftNodeId, nodeId): [(x, y)]}
        prevVNodes = []
        for nodes in model.columns:
            rectW = getMaxTextWidth(nodes) + Cfg.NodeWidthInc
            yPos = 0
            vNodes = []
            for node in nodes:
                vn = VisNode(node, rectW)
                vNodes.append(vn)
                yPos += vn.hBoxH
                vn.setPos(xPos, yPos)
                yPos += vn.hBoxH + Cfg.NodeSpacing 
            MyView.adjustVerticalColumnPlacement(prevVNodes, vNodes)
            for vn in vNodes:
                node = vn.node
                vn.render(self.scene)
                # connect left nodes
                y0 = vn.lwy0
                x0 = xPos
                for lCon in node.leftCons:
                    for (x1, y1) in leftConDict[(lCon.leftNode.id, node.id)]:
                        self.scene.addLine(x0, y0, x1, y1, getPen(lCon.name))
                        y0 += Cfg.ConSpacing
                # create rightConDict which is the next leftConDict
                y = vn.rwy0
                x = xPos + rectW
                for con in node.rightCons:
                    rightConDict[node.id, con.rightNode.id].append((x, y))
                    y += Cfg.ConSpacing
            leftConDict.clear()
            leftConDict.update(rightConDict)
            rightConDict.clear()
            prevVNodes = vNodes
                        
            xPos += rectW + Cfg.MinHorizontalColumnSpacing
        self.setScene(self.scene)

    def wheelEvent(self, event):
        # print 'wheelEvent: delta:{}'.format(event.delta())  # +- 120
        d = event.delta()
        s = 1.1 if d > 0 else 0.9
        self.scale(s, s)

    def mousePressEvent(self, event):
        return
        # print str(event.pos)
        # pos = self.mapToScene(event.pos()).toPoint()
        pos = event.pos()
        item = self.itemAt(pos)
        if item:
            pen = item.pen()
            pen.setColor(QtGui.QColor(0, 128, 0))
            pen.setWidth(4)
            item.setPen(pen)
            # item.update()
            # self.scene.update()
        print 'item: {}'.format(item)


def show(depGraph):
    model = Model.create(depGraph)
    app = QtGui.QApplication(sys.argv)
    view = MyView(model)
    view.show()
    sys.exit(app.exec_())
    


if __name__ == '__main__':
    pass