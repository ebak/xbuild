import sys
import math
import json
import PyQt4
from collections import defaultdict
from PyQt4 import QtGui, QtCore
from xbuild.pathformer import NoPathFormer
from model import Model, FileNode, TaskNode, CrossLinkNode
from nodepopup import NodePopup
from mouse import Mouse


Qt = QtCore.Qt
QColor = QtGui.QColor
QPoint = QtCore.QPoint
QLineF = QtCore.QLineF
# http://doc.qt.io/qt-4.8/qgraphicsview.html

def getText(node, pathFormer=NoPathFormer):
    if isinstance(node, TaskNode):
        return 'Task: ' + pathFormer.encode(node.id)
    elif isinstance(node, FileNode):
        return 'File: ' + pathFormer.encode(node.id)
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
    MinHorizontalColumnSpacing = 10 # 00
    PinLength = 10


def getPen(name):
    return Cfg.GenPen if name in ('pFile', 'gen', 'pTask') else Cfg.NormPen


# QGraphicsItem.data()
# QGraphicsItem.setData()


class VisNode(object):
    
    def __init__(self, node, colIdx, width, x=0, y=0, pathFormer=NoPathFormer):
        '''x, y - vertical center on left side'''
        self.node, self.colIdx, self.width = node, colIdx, width
        self.pathFormer = pathFormer
        self.nodeId = (self.colIdx, self.node.order)
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
        # graphics items
        # nodeId in QGraphicsItem.data strings: (colIdx, node.order)
        self.rect = None
        self.label = None
        self.leftSlots = {}     # {leftNodeId: (line, text)}
        self.rightSlots = {}
        
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

    def setX(self, x):
        self.x = x
        self.leftSlotCoords = None
        self.rightSlotCoords = None

    def render(self, nodeLayer, slotLabelLayer, nodeLabelLayer, lineLayer):
        nodeId = self.nodeId
        
        def drawSlotText(conNodeId, xInner, y, xFn, name):
            data = {
                'type': 'Slot',
                'gItem': 'Text',
                'prnt': nodeId,
                'conId': conNodeId}
            textItem = QtGui.QGraphicsTextItem(name)
            textItem.setFont(Cfg.SlotFont)
            textItem.setDefaultTextColor(Cfg.SlotFontColor)
            br = textItem.boundingRect()
            textItem.setX(xFn(xInner, br))
            textItem.setY(y - 0.5 * br.height())
            textItem.setData(0, json.dumps(data))   # TODO: use int-key value pairs instead of json
            slotLabelLayer.add(textItem)
            return textItem

        def drawSlots(oDict, slotCoords, xInnerFn, xFn):
            data = {
                'type': 'Slot',
                'gItem': 'Line',
                'prnt': nodeId}
            for conNodeId, (x, y, name) in slotCoords.items():
                data['conId'] = conNodeId
                xInner = xInnerFn(x)
                line = QtGui.QGraphicsLineItem(x, y, xInner, y)
                line.setPen(rectPen)
                line.setData(0, json.dumps(data))
                lineLayer.add(line)
                oDict[nodeId] = (line, drawSlotText(nodeId, xInner, y, xFn, name))

        data = {
            'type': 'Task' if isinstance(self.node, TaskNode) else ('File' if isinstance(self.node, FileNode) else 'Link'),
            'id': nodeId}
        self.leftSlots.clear()
        self.rightSlots.clear()
        if isinstance(self.node, CrossLinkNode):
            line = QtGui.QGraphicsLineItem(self.x, self.y, self.x + self.width, self.y)
            line.setPen(getPen(self.node.name))
            data['gItem'] = 'Line'
            line.setData(0, json.dumps(data))
            nodeLayer.add(line)
        else:
            if self.node.leftCons:
                if self.node.rightCons:
                    rectPen = Cfg.NormPen
                else:
                    rectPen = Cfg.RLeafPen
            else:
                # print '{} leftLeaf'.format(self.node.id)
                rectPen = Cfg.LLeafPen
            ry0 = self.y - 0.5 * Cfg.NodeHeight
            brush = Cfg.TaskBrush if isinstance(self.node, TaskNode) else Cfg.FileBrush
            self.rect = QtGui.QGraphicsRectItem(self.x + Cfg.PinLength, self.y0, self.rectWidth, self.boxH)
            self.rect.setPen(rectPen)
            self.rect.setBrush(brush)
            data['gItem'] = 'Rect'
            self.rect.setData(0, json.dumps(data))
            nodeLayer.add(self.rect)
            # draw left slots
            drawSlots(
                self.leftSlots, self.getLeftSlotCoords(),
                xInnerFn=lambda x: x + Cfg.PinLength, xFn=lambda xi,br: xi + 1)
            # draw right slots
            drawSlots(
                self.rightSlots, self.getRightSlotCoords(),
                xInnerFn=lambda x: x - Cfg.PinLength, xFn=lambda xi,br: xi - br.width())
            # draw node label
            self.label = textItem = QtGui.QGraphicsTextItem(getText(self.node, self.pathFormer))
            textItem.setFont(Cfg.NodeFont)
            br = textItem.boundingRect()
            textItem.setX(self.x + 0.5 * (self.width - br.width()))
            textItem.setY(ry0 + 0.5 * (Cfg.NodeHeight - br.height()))
            data['gItem'] = 'Text'
            textItem.setData(0, json.dumps(data))
            nodeLabelLayer.add(textItem)

    def _calcSlotCoords(self, cons, conIdx, getNodeFn, x, y0):
        '''Returns {(conIdx, getNodeFn(con).order): (x, y, slotName)}'''
        res = {}
        if not cons:
            return res
        y = 0.5 * self.conSpacing + y0
        for con in cons:
            res[(conIdx, getNodeFn(con).order)] = (x, y, con.name)
            y += self.conSpacing
        return res

    def getLeftSlotCoords(self):
        '''Returns {leftNodeId: (x, y, slotName)}'''
        if self.leftSlotCoords is None:
            self.leftSlotCoords = self._calcSlotCoords(
                self.node.leftCons, self.colIdx - 1, getNodeFn=lambda con: con.leftNode, x=self.x, y0=self.lwy0)
        return self.leftSlotCoords
    
    def getRightSlotCoords(self):
        '''Returns {rightNodeId: (x, y, slotName)}'''
        if self.rightSlotCoords is None:
            self.rightSlotCoords = self._calcSlotCoords(
                self.node.rightCons, self.colIdx + 1, getNodeFn=lambda con: con.rightNode, x=self.x + self.width, y0=self.rwy0)
        return self.rightSlotCoords


class Layer(QtGui.QGraphicsItem):

    def __init__(self, parent=None):
        super(self.__class__, self).__init__(parent)

    def add(self, item):
        item.setParentItem(self)

    # void QGraphicsItem::paint(QPainter * painter, const QStyleOptionGraphicsItem * option, QWidget * widget = 0)
    def paint(self, painter, option, widget=None):
        pass

    def boundingRect(self):
        return QtCore.QRectF(0.0, 0.0, 0.0, 0.0)


class MyView(QtGui.QGraphicsView):
    
    RecTgAlpha = 1.0 / math.tan(math.radians(70))

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
                                delta = y - prevVNode.y
                                yDeltaSum += delta
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

    def __init__(self, model, pathFormer):
        super(self.__class__, self).__init__()
        self.pathFormer = pathFormer
        self.model = model
        self.setWindowTitle('Boncz Geza dependency graph visualization tool (early alpha).')
        # self.resize(QtGui.QApplication.desktop().size());
        # self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform) 
        self.mouse = Mouse()
        
        self.scene = QtGui.QGraphicsScene()
        self.nodeLayer, self.slotLabelLayer, self.nodeLabelLayer, self.lineLayer = [Layer() for _ in range(4)]
        for layer in self.nodeLayer, self.slotLabelLayer, self.nodeLabelLayer, self.lineLayer:
            self.scene.addItem(layer)
        self.nodePopup = NodePopup(self)
        self.buildScene()

    def buildScene(self):

        def getMaxTextWidth(nodes):
            maxW = 0
            for n in nodes:
                text = getText(n, self.pathFormer)
                if text:
                    fm = QtGui.QFontMetrics(Cfg.NodeFont)
                    w = fm.width(text)
                    if w > maxW:
                        maxW = w
            return maxW

        xPos = 0
        leftConDict = defaultdict(list)  # {(leftNodeId, nodeId): [(x, y)]}
        prevVNodes = []
        prevRectW = None
        for colIdx, nodes in enumerate(self.model.columns):
            rightConDict = defaultdict(list) # {(nodeId, rightNodeId): [(x, y)]}
            rectW = getMaxTextWidth(nodes) + Cfg.NodeWidthInc
            yPos = 0
            vNodes = []
            for node in nodes:
                vn = VisNode(node, colIdx, rectW, pathFormer=self.pathFormer)
                vNodes.append(vn)
                yPos += vn.hBoxH
                vn.setPos(xPos, yPos)
                yPos += vn.hBoxH + Cfg.NodeSpacing 
            MyView.adjustVerticalColumnPlacement(prevVNodes, vNodes)
            if prevRectW is not None:
                # get left connections' maxYDelta
                maxYDelta = 0
                for vn in vNodes:
                    node = vn.node
                    for leftNodeId, (lx, ly, _) in vn.getLeftSlotCoords().items():
                        for rx, ry, _ in leftConDict[(leftNodeId, node.id)]:
                            delta = abs(ry - ly)
                            if delta > maxYDelta:
                                maxYDelta = delta
                # calculate horizontal column spacing
                minHDist = maxYDelta * MyView.RecTgAlpha
                horizontalSpacing = max(minHDist, Cfg.MinHorizontalColumnSpacing)
                # print 'maxYDelta={}, minHDist={}, horizontalSpacing={}'.format(maxYDelta, minHDist, horizontalSpacing)
                xPos += prevRectW + 2 * Cfg.PinLength + horizontalSpacing
            # render nodes
            for vn in vNodes:
                node = vn.node
                # print '{} xPos:{}'.format(node.id, xPos)
                vn.setX(xPos)
                vn.render(self.nodeLayer, self.slotLabelLayer, self.nodeLabelLayer, self.lineLayer)
                # connect to left nodes
                for leftNodeId, (lx, ly, name) in vn.getLeftSlotCoords().items():
                    for rx, ry, _ in leftConDict[(leftNodeId, vn.nodeId)]:
                        line = QtGui.QGraphicsLineItem(lx, ly, rx, ry,)
                        line.setPen(getPen(name))
                        self.lineLayer.add(line)
                # create rightConDict which is the next leftConDict
                for rightNodeId, (x, y, name) in vn.getRightSlotCoords().items():
                    # print 'rightNodeId:{}, vn.nodeId:{}'.format(rightNodeId, vn.nodeId)
                    rightConDict[(vn.nodeId, rightNodeId)].append((x, y, name))
            leftConDict = rightConDict
            prevVNodes = vNodes
            prevRectW = rectW
        self.setScene(self.scene)

    def wheelEvent(self, event):
        
        def setVis(grp, vis):
            if vis:
                if not grp.isVisible():
                    grp.show()
            else:
                if grp.isVisible():
                    grp.hide()

        def showAndHide(grpsToShow, grpsToHide):
            for grp in grpsToShow:
                setVis(grp, True)
            for grp in grpsToHide:
                setVis(grp, False)

        # print 'wheelEvent: delta:{}'.format(event.delta())  # +- 120
        d = event.delta()
        s = 1.1 if d > 0 else 0.9
        self.scale(s, s)
        factor = self.transform().m11()
        if factor > 0.5:
            showAndHide([self.nodeLayer, self.slotLabelLayer, self.nodeLabelLayer, self.lineLayer], [])
        elif factor > 0.25:
            showAndHide([self.nodeLayer, self.nodeLabelLayer, self.lineLayer], [self.slotLabelLayer])
        elif factor > 0.125:
            showAndHide([self.nodeLayer, self.lineLayer], [self.slotLabelLayer, self.nodeLabelLayer])
        else:
            showAndHide([self.nodeLayer], [self.slotLabelLayer, self.nodeLabelLayer, self.lineLayer])

    def mousePressEvent(self, event):
        self.mouse.pressEvent(event)

    def leftClick(self, event):
        print 'leftClick'
        pass

    def rightClick(self, event):
        pos = event.pos()
        item = self.itemAt(pos)
        if item:
            data = item.data(0).toString()
            if data:
                print 'rightClick data:{}'.format(data)
            else:
                print 'rightClick no data'
        else:
            print 'rightClick'
        pass

    def leftPressMove(self, event):
        p = event.pos()
        pp = self.mouse.prevPos
        # if pp is not None:
        dx = p.x() - pp.x()
        dy = p.y() - pp.y()
        # print 'dx:{}, dy:{}'.format(dx, dy)
        hsb = self.horizontalScrollBar()
        vsb = self.verticalScrollBar()
        hsb.setValue(hsb.value() - dx)
        vsb.setValue(vsb.value() - dy)
        # self.translate(dx, dy)

    def rightPressMove(self, event):
        pass

    def mouseReleaseEvent(self, event):
        self.mouse.releaseEvent(event, clickHandler=self)

    def mouseMoveEvent(self, event):
        self.mouse.moveEvent(event, moveHandler=self)


def show(depGraph, pathFormer=NoPathFormer()):
    model = Model.create(depGraph)
    app = QtGui.QApplication(sys.argv)
    view = MyView(model, pathFormer)
    view.showMaximized()
    return app.exec_()
    


if __name__ == '__main__':
    pass