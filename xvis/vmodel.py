import json
from collections import defaultdict
from PyQt4 import QtGui, QtCore
from model import FileNode, TaskNode, CrossLinkNode
from xbuild.pathformer import NoPathFormer

Qt = QtCore.Qt
QColor = QtGui.QColor
QPoint = QtCore.QPoint
QLineF = QtCore.QLineF
# http://doc.qt.io/qt-4.8/qgraphicsview.html

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


def getText(node, pathFormer=NoPathFormer):
    if isinstance(node, TaskNode):
        return 'Task: ' + pathFormer.encode(node.id)
    elif isinstance(node, FileNode):
        return 'File: ' + pathFormer.encode(node.id)
    return None


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

