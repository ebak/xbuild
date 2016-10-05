import json
from collections import defaultdict
from PyQt4 import QtGui, QtCore
from model import FileNode, TaskNode, CrossLinkNode
from xbuild.pathformer import NoPathFormer

Qt = QtCore.Qt
QColor = QtGui.QColor
QBrush = QtGui.QBrush
QPen = QtGui.QPen
QPoint = QtCore.QPoint
QLineF = QtCore.QLineF
# http://doc.qt.io/qt-4.8/qgraphicsview.html

# TODO: call it from static context
def fadeToSelect(qColor):
    r = 0.7
    l = 1.0 - r
    def mix(lv, rv): return int(l * lv + r * rv)
    red, green, blue = 100, 255, 100
    return QColor(mix(qColor.red(), red), mix(qColor.green(), green), mix(qColor.blue(), blue))


def fadeBrushToSelect(qBrush):
    brush = QBrush(qBrush)
    brush.setColor(fadeToSelect(qBrush.color()))
    return brush


def fadePenToSelect(qPen):
    qPen = QPen(qPen)
    qPen.setColor(fadeToSelect(qPen.color()))
    qPen.setWidth(3)
    return qPen


class Cfg(object):    
    NodeFontName = 'sans-serif'
    NodeFontSize = 14
    NodeFont = QtGui.QFont(NodeFontName, NodeFontSize)
    SlotFontName = 'sans-serif'
    SlotFontSize = 8
    SlotFontColor = QColor(60, 0, 0)
    SlotFont = QtGui.QFont(SlotFontName, SlotFontSize)
    ConSpacing = 20
    NodeSpacing = 20
    GenPen = QtGui.QPen(Qt.SolidLine)
    GenPen.setColor(QColor(140, 128, 128))
    GenPen.setWidth(1)
    SelectGenPen = fadePenToSelect(GenPen)
    NormPen = QtGui.QPen(Qt.SolidLine)
    NormPen.setColor(QColor(128, 0, 0))
    NormPen.setWidth(1)
    SelectNormPen = fadePenToSelect(NormPen)
    RLeafPen = QtGui.QPen(Qt.SolidLine)
    RLeafPen.setColor(QColor(0, 128, 0))
    RLeafPen.setWidth(2)
    LLeafPen = QtGui.QPen(Qt.SolidLine)
    LLeafPen.setColor(QColor(0, 0, 128))
    LLeafPen.setWidth(2)
    TaskBrush = QtGui.QBrush(QColor(180, 180, 255))
    SelectTaskBrush = fadeBrushToSelect(TaskBrush)
    FileBrush = QtGui.QBrush(QColor(235, 230, 180))
    SelectFileBrush = fadeBrushToSelect(FileBrush)
    NodeWidthInc = 120
    NodeHeight = 30
    CrossLinkHeight = 1
    MinHorizontalColumnSpacing = 10 # 00
    PinLength = 10


def getText(node, pathFormer=NoPathFormer):
    if isinstance(node, TaskNode):
        return 'Task: ' + pathFormer.encode(node.id)
    elif isinstance(node, FileNode):
        return 'File: ' + pathFormer.encode(node.id)
    return None


class Layer(QtGui.QGraphicsItem):

    def __init__(self, parent=None):
        super(Layer, self).__init__(parent)

    def add(self, item):
        item.setParentItem(self)

    # void QGraphicsItem::paint(QPainter * painter, const QStyleOptionGraphicsItem * option, QWidget * widget = 0)
    def paint(self, painter, option, widget=None):
        pass

    def boundingRect(self):
        return QtCore.QRectF(0.0, 0.0, 0.0, 0.0)


class VisEnt(object):

    @staticmethod
    def getPen(name, select=False):
        if select:
            return Cfg.SelectGenPen if name in ('pFile', 'gen', 'pTask') else Cfg.SelectNormPen
        else:
            return Cfg.GenPen if name in ('pFile', 'gen', 'pTask') else Cfg.NormPen

    def __init__(self):
        self.selected = False

    def render(self, nodeLayer, slotLabelLayer, nodeLabelLayer, lineLayer):
        assert False

    def select(self):
        if not self.selected:
            self.selected = True
            self.doSelect()

    def deselect(self):
        if self.selected:
            self.selected = False
            self.doDeselect()

    def doSelect(self):
        assert False

    def doDeselect(self):
        assert False


# VisEnt
#    VisNode
#        VisRectNode
#            VisCrossLinkNode
#            VisFileNode
#            VisTaskNode
#    VisConnection
class VisNode(VisEnt):

    @staticmethod
    def create(node, colIdx, width, x=0, y=0, pathFormer=NoPathFormer):
        if isinstance(node, FileNode):
            return VisFileNode(node, colIdx, width, x, y, pathFormer)
        elif isinstance(node, TaskNode):
            return VisTaskNode(node, colIdx, width, x, y, pathFormer)
        elif isinstance(node, CrossLinkNode):
            return VisCrossLinkNode(node, colIdx, width, x, y, pathFormer)
        else:
            return None
    
    def __init__(self, node, colIdx, width, x=0, y=0, pathFormer=NoPathFormer):
        '''x, y - vertical center on left side'''
        super(VisNode, self).__init__()
        self.node, self.colIdx, self.width = node, colIdx, width
        self.pathFormer = pathFormer
        self.nodeId = (self.colIdx, self.node.order)
        self.rectWidth = width - 2 * Cfg.PinLength
        #
        self.leftWallH = None
        self.rightWallH = None
        # self.conSpacing = None  # TODO: remove
        self.boxH = None
        self.hBoxH = None
        self.calcHeights()
        #
        self.setPos(x, y)
        # graphics items
        self.leftSlots = {}     # {leftNodeId: (line, text)}
        self.rightSlots = {}

    def calcHeights(self):
        assert False
        
    def setPos(self, x, y):
        self.x, self.y = x, y
        self.leftSlotCoords = None  # {leftNodeId: (x, y, slotName)}
        self.rightSlotCoords = None # {rightNodeId: (x, y, slotName)}

    def setY(self, y):
        self.setPos(self.x, y)

    def setX(self, x):
        self.x = x
        self.leftSlotCoords = None
        self.rightSlotCoords = None

    def _calcSlotCoords(self, cons, colIdx, getNodeFn, x, y0):
        '''Returns {(colIdx, getNodeFn(con).order): (x, y, Connection)}'''
        res = {}
        if not cons:
            return res
        y = 0.5 * self.conSpacing + y0
        for con in cons:
            res[(colIdx, getNodeFn(con).order)] = (x, y, con)
            y += self.conSpacing
        return res

    def getLeftSlotCoords(self):
        '''Returns {leftNodeId: (x, y, Connection)}'''
        if self.leftSlotCoords is None:
            self.leftSlotCoords = self._calcSlotCoords(
                self.node.leftCons, self.colIdx - 1, getNodeFn=lambda con: con.leftNode, x=self.x, y0=self.lwy0)
        return self.leftSlotCoords
    
    def getRightSlotCoords(self):
        '''Returns {rightNodeId: (x, y, Connection)}'''
        if self.rightSlotCoords is None:
            self.rightSlotCoords = self._calcSlotCoords(
                self.node.rightCons, self.colIdx + 1, getNodeFn=lambda con: con.rightNode, x=self.x + self.width, y0=self.rwy0)
        return self.rightSlotCoords


class VisCrossLinkNode(VisNode):

    def __init__(self, node, colIdx, width, x=0, y=0, pathFormer=NoPathFormer):
        super(VisCrossLinkNode, self).__init__(node, colIdx, width, x, y, pathFormer)
        self.conSpacing = 0

    def calcHeights(self):
        self.leftWallH, self.rightWallH = 1, 1
        nodeHeight = Cfg.CrossLinkHeight
        self.boxH = nodeHeight
        self.hBoxH = 0.5 * self.boxH

    def setPos(self, x, y):
        super(VisCrossLinkNode, self).setPos(x, y)
        self.lwy0 = self.y
        self.lwy1 = self.y
        self.rwy0 = self.y
        self.rwy1 = self.y
        self.y0 = self.y - self.hBoxH
        self.y1 = self.y + self.boxH

    def render(self, nodeLayer, slotLabelLayer, nodeLabelLayer, lineLayer):
        data = {'type': 'Link', 'id': self.nodeId}
        self.line = line = QtGui.QGraphicsLineItem(self.x, self.y, self.x + self.width, self.y)
        line.setPen(VisCrossLinkNode.getPen(self.node.name))
        data['gItem'] = 'Line'
        line.setData(0, json.dumps(data))
        nodeLayer.add(line)

    def doSelect(self):
        self.line.setPen(VisEnt.getPen(self.node.name, select=True))

    def doDeselect(self):
        self.line.setPen(VisEnt.getPen(self.node.name))


class VisRectNode(VisNode):
    
    def __init__(self, node, colIdx, width, x, y, pathFormer, brush, selBrush, typeTxt):
        '''x, y - vertical center on left side'''
        super(VisRectNode, self).__init__(node, colIdx, width, x, y, pathFormer)
        self.brush, self.selBrush = brush, selBrush
        self.typeTxt = typeTxt
        self.conSpacing = Cfg.ConSpacing
        self.setPos(x, y)
        # graphics items
        # nodeId in QGraphicsItem.data strings: (colIdx, node.order)
        self.rect = None
        self.label = None
        self.leftSlots = {}     # {leftNodeId: (line, text)}
        self.rightSlots = {}

    def calcHeights(self):
        self.leftWallH = Cfg.ConSpacing * (len(self.node.leftCons))
        self.rightWallH = Cfg.ConSpacing * (len(self.node.rightCons))
        nodeHeight = Cfg.NodeHeight
        self.boxH = max(self.leftWallH, self.rightWallH, nodeHeight)
        self.hBoxH = 0.5 * self.boxH
        
    def setPos(self, x, y):
        super(VisRectNode, self).setPos(x, y)
        self.lwy0 = self.y - 0.5 * self.leftWallH
        self.lwy1 = self.lwy0 + self.leftWallH
        self.rwy0 = self.y - 0.5 * self.rightWallH
        self.rwy1 = self.rwy0 + self.rightWallH
        self.y0 = self.y - 0.5 * self.boxH
        self.y1 = self.y + self.boxH

    def setY(self, y):
        self.setPos(self.x, y)

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
            for conNodeId, (x, y, con) in slotCoords.items():
                data['conId'] = conNodeId
                xInner = xInnerFn(x)
                line = QtGui.QGraphicsLineItem(x, y, xInner, y)
                line.setPen(rectPen)
                line.setData(0, json.dumps(data))
                lineLayer.add(line)
                oDict[nodeId] = (line, drawSlotText(nodeId, xInner, y, xFn, con.name))

        data = {'type': self.typeTxt, 'id': nodeId}
        self.leftSlots.clear()
        self.rightSlots.clear()
        if self.node.leftCons:
            if self.node.rightCons:
                rectPen = Cfg.NormPen
            else:
                rectPen = Cfg.RLeafPen
        else:
            # print '{} leftLeaf'.format(self.node.id)
            rectPen = Cfg.LLeafPen
        ry0 = self.y - 0.5 * Cfg.NodeHeight
        self.rect = QtGui.QGraphicsRectItem(self.x + Cfg.PinLength, self.y0, self.rectWidth, self.boxH)
        self.rect.setPen(rectPen)
        self.rect.setBrush(self.brush)
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

    def doSelect(self):
        self.rect.setBrush(self.selBrush)

    def doDeselect(self):
        self.rect.setBrush(self.brush)


class VisFileNode(VisRectNode):

    def __init__(self, node, colIdx, width, x=0, y=0, pathFormer=NoPathFormer):
        super(VisFileNode, self).__init__(
            node, colIdx, width, x, y, pathFormer, Cfg.FileBrush, Cfg.SelectFileBrush, 'File')


class VisTaskNode(VisRectNode):
    
    def __init__(self, node, colIdx, width, x=0, y=0, pathFormer=NoPathFormer):
        super(VisTaskNode, self).__init__(
            node, colIdx, width, x, y, pathFormer, Cfg.TaskBrush, Cfg.SelectTaskBrush, 'Task')


class VisConnection(VisEnt):

    def __init__(self, con, lCol, lOrd, lx, ly, rCol, rOrd, rx, ry):
        super(VisConnection, self).__init__()
        self.con = con
        self.lCol, self.lOrd, self.lx, self.ly = lCol, lOrd, lx, ly
        self.rCol, self.rOrd, self.rx, self.ry = rCol, rOrd, rx, ry

    def render(self, lineLayer):
        line = self.line = QtGui.QGraphicsLineItem(self.lx, self.ly, self.rx, self.ry,)
        line.setPen(VisEnt.getPen(self.con.name))
        data = {
            'type': 'Con',
            'lId': (self.lCol, self.lOrd), 
            'rId': (self.rCol, self.rOrd),
            'gItem': 'Line'}
        line.setData(0, json.dumps(data))
        lineLayer.add(line)

    def doSelect(self):
        self.line.setPen(VisEnt.getPen(self.con.name, select=True))

    def doDeselect(self):
        self.line.setPen(VisEnt.getPen(self.con.name))
