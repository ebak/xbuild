import PyQt4
import sys
from collections import defaultdict
from PyQt4 import QtGui, QtCore
from model import Model, FileNode, TaskNode, CrossLinkNode

Qt = QtCore.Qt
QColor = QtGui.QColor
# http://doc.qt.io/qt-4.8/qgraphicsview.html

def getText(node):
    if isinstance(node, TaskNode):
        return 'Task: ' + node.id
    elif isinstance(node, FileNode):
        return 'File: ' + node.id
    return None


class Cfg(object):
    
    NodeFontName = 'Sans'
    NodeFontSize = 14
    NodeFont = QtGui.QFont(NodeFontName, NodeFontSize)
    SlotFontName = 'Sans'
    SlotFontSize = 8
    SlotFontColor = QColor(60, 0, 0)
    SlotFont = QtGui.QFont(SlotFontName, SlotFontSize)
    ConSpacing = 20
    NodeSpacing = 20
    GenPen = QtGui.QPen(Qt.SolidLine)
    GenPen.setColor(QColor(140, 128, 128))
    GenPen.setWidth(1)
    NormPen = QtGui.QPen(Qt.SolidLine)
    NormPen.setColor(QColor(128, 0, 0))
    NormPen.setWidth(1)
    RLeafPen = QtGui.QPen(Qt.SolidLine)
    RLeafPen.setColor(QColor(0, 128, 0))
    RLeafPen.setWidth(2)
    LLeafPen = QtGui.QPen(Qt.SolidLine)
    LLeafPen.setColor(QColor(0, 0, 128))
    LLeafPen.setWidth(2)
    TaskBrush = QtGui.QBrush(QColor(180, 180, 255))
    FileBrush = QtGui.QBrush(QColor(235, 230, 180))
    NodeWidthInc = 120
    NodeHeight = 30
    CrossLinkHeight = 1
    MinHorizontalColumnSpacing = 100
    PinLength = 10


def getPen(name):
    return Cfg.GenPen if name in ('pFile', 'gen', 'pTask') else Cfg.NormPen


class VisNode(object):
    
    def __init__(self, node, width, x=0, y=0):
        '''x, y - vertical center on left side'''
        self.node = node        
        self.width = width
        self.rectWidth = width - 2 * Cfg.PinLength
        if isinstance(node, CrossLinkNode):
            self.leftWallH, self.rightWallH = 1, 1
            nodeHeight = Cfg.CrossLinkHeight
            self.conSpacing = 1
        else:
            self.leftWallH = Cfg.ConSpacing * (len(node.leftCons))
            self.rightWallH = Cfg.ConSpacing * (len(node.rightCons))
            nodeHeight = Cfg.NodeHeight
            self.conSpacing = Cfg.ConSpacing
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
        self.leftSlotCoords = None  # {leftNodeId: (x, y, slotName)}
        self.rightSlotCoords = None # {rightNodeId: (x, y, slotName)}

    def setY(self, y):
        self.setPos(self.x, y)

    def render(self, scene):
        
        def drawSlotText(xInner, xFn):
            textItem = scene.addText(name, Cfg.SlotFont)
            textItem.setDefaultTextColor(Cfg.SlotFontColor)
            br = textItem.boundingRect()
            textItem.setX(xFn(xInner, br))
            textItem.setY(y - 0.5 * br.height())
            
        if isinstance(self.node, CrossLinkNode):
            scene.addLine(self.x, self.y, self.x + self.width, self.y, getPen(self.node.name))
        else:
            if self.node.leftCons:
                if self.node.rightCons:
                    rectPen = Cfg.NormPen
                else:
                    rectPen = Cfg.RLeafPen
            else:
                print '{} leftLeaf'.format(self.node.id)
                rectPen = Cfg.LLeafPen
            ry0 = self.y - 0.5 * Cfg.NodeHeight
            brush = Cfg.TaskBrush if isinstance(self.node, TaskNode) else Cfg.FileBrush
            scene.addRect(self.x + Cfg.PinLength, self.y0, self.rectWidth, self.boxH, rectPen, brush)
            # draw slot pins
            for x, y, name in self.getLeftSlotCoords().values():
                xInner = x + Cfg.PinLength
                scene.addLine(x, y, xInner, y, rectPen)
                drawSlotText(xInner, xFn=lambda xi,br: xi + 1)
            for x, y, name in self.getRightSlotCoords().values():
                xInner = x - Cfg.PinLength
                scene.addLine(x, y, xInner, y, rectPen)
                drawSlotText(xInner, xFn=lambda xi,br: xi - br.width())
            textItem = scene.addText(getText(self.node), Cfg.NodeFont)
            br = textItem.boundingRect()
            textItem.setX(self.x + 0.5 * (self.width - br.width()))
            textItem.setY(ry0 + 0.5 * (Cfg.NodeHeight - br.height()))

    def _calcSlotCoords(self, cons, getNodeFn, x, y0):
        '''Returns {getNodeFn(con).id: (x, y, slotName)}'''
        res = {}
        if not cons:
            return res
        y = 0.5 * self.conSpacing + y0
        for con in cons:
            res[getNodeFn(con).id] = (x, y, con.name)
            y += self.conSpacing
        return res

    def getLeftSlotCoords(self):
        '''Returns {leftNodeId: (x, y, slotName)}'''
        if self.leftSlotCoords is None:
            self.leftSlotCoords = self._calcSlotCoords(
                self.node.leftCons, getNodeFn=lambda con: con.leftNode, x=self.x, y0=self.lwy0)
        return self.leftSlotCoords
    
    def getRightSlotCoords(self):
        '''Returns {rightNodeId: (x, y, slotName)}'''
        if self.rightSlotCoords is None:
            self.rightSlotCoords = self._calcSlotCoords(
                self.node.rightCons, getNodeFn=lambda con: con.rightNode, x=self.x + self.width, y0=self.rwy0)
        return self.rightSlotCoords
            

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
            scanRange = max(scanRes, abs(prevH - h))
            yOffs0 = prevY0 - y0 if h <= prevH else prevY1 - y1  
            yOffs1 = yOffs0 + scanRange
            # print 'prevY0:{}, prevY1:{}, y0:{}, y1:{}, yOffs0:{}, yOffs1:{}, scanRange:{}'.format(
            #    prevY0, prevY1, y0, y1, yOffs0, yOffs1, scanRange)
            bestYOffs = (0, sys.maxint)     # (yOffs, yDeltaSum)
            yDeltaSumDict = {}  # {yOffs, yDeltaSum}
            yDict = {n.node.id: n.y for n in vNodes}
            # print 'yDict={}'.format(yDict)
            while scanDepth > 0:
                # print 'scanDepth: {}'.format(scanDepth)
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
                        # print 'yOffs:{}, yDeltaSum: {}'.format(yOffs, yDeltaSum)
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
            # print 'yOffs={}'.format(yOffs)
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
        leftConDict = defaultdict(list)  # {(leftNodeId, nodeId): [(x, y)]}
        prevVNodes = []
        for nodes in model.columns:
            rightConDict = defaultdict(list) # {(nodeId, rightNodeId): [(x, y)]}
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
                # connect to left nodes
                for leftNodeId, (lx, ly, name) in vn.getLeftSlotCoords().items():
                    for rx, ry, _ in leftConDict[(leftNodeId, node.id)]:
                        self.scene.addLine(lx, ly, rx, ry, getPen(name))
                # create rightConDict which is the next leftConDict
                for rightNodeId, (x, y, name) in vn.getRightSlotCoords().items():
                    rightConDict[(node.id, rightNodeId)].append((x, y, name))
            leftConDict = rightConDict
            prevVNodes = vNodes
                        
            xPos += rectW + 2 * Cfg.PinLength + Cfg.MinHorizontalColumnSpacing
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