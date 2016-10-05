import sys
import math
import json
from collections import defaultdict
from PyQt4 import QtGui, QtCore
from xbuild.pathformer import NoPathFormer
from model import Model
from nodepopup import NodePopup
from mouse import Mouse
from vmodel import Cfg, Layer, VisNode, VisConnection, getText


Qt = QtCore.Qt
QColor = QtGui.QColor
QPoint = QtCore.QPoint
QLineF = QtCore.QLineF
# http://doc.qt.io/qt-4.8/qgraphicsview.html


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
        
        self.selectedVNode = None
        self.selectedVisEntList = []
        self.scene = QtGui.QGraphicsScene()
        self.nodeLayer, self.slotLabelLayer, self.nodeLabelLayer, self.lineLayer = [Layer() for _ in range(4)]
        for layer in self.nodeLayer, self.slotLabelLayer, self.nodeLabelLayer, self.lineLayer:
            self.scene.addItem(layer)
        np = self.nodePopup = NodePopup(self)
        np.deselectAction.setEnabled(False)
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

        self.vNodeDict = {}     # {vNode.nodeId: vNode}
        self.conList = []       # [{(lOrder, rOrder): VisConnection}]
        xPos = 0
        leftConDict = defaultdict(list)  # {(leftNodeId, nodeId): [(x, y)]}
        prevVNodes = []
        prevRectW = None
        for colIdx, nodes in enumerate(self.model.columns):
            conDict = {}    # {(lOrder, rOrder): VisConnection}
            self.conList.append(conDict)
            rightConDict = defaultdict(list) # {(nodeId, rightNodeId): [(x, y)]}
            rectW = getMaxTextWidth(nodes) + Cfg.NodeWidthInc
            yPos = 0
            vNodes = []
            for node in nodes:
                vn = VisNode.create(node, colIdx, rectW, pathFormer=self.pathFormer)
                self.vNodeDict[vn.nodeId] = vn 
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
                        for rx, ry, _ in leftConDict[(leftNodeId, vn.nodeId)]:
                            delta = abs(ry - ly)
                            if delta > maxYDelta:
                                maxYDelta = delta
                # calculate horizontal column spacing
                minHDist = maxYDelta * MyView.RecTgAlpha
                horizontalSpacing = max(minHDist, Cfg.MinHorizontalColumnSpacing)
                # print 'maxYDelta={}, minHDist={}, horizontalSpacing={}'.format(maxYDelta, minHDist, horizontalSpacing)
                xPos += prevRectW + 2 * Cfg.PinLength + horizontalSpacing
            # render nodes
            lColIdx = colIdx - 1
            for vn in vNodes:
                node = vn.node
                # print '{} xPos:{}'.format(node.id, xPos)
                vn.setX(xPos)
                vn.render(self.nodeLayer, self.slotLabelLayer, self.nodeLabelLayer, self.lineLayer)
                # connect to left nodes
                for leftNodeId, (lx, ly, leftCon) in vn.getLeftSlotCoords().items():
                    # left slot coords of right node
                    assert leftCon.rightNode is node
                    for rx, ry, _ in leftConDict[(leftNodeId, vn.nodeId)]:
                        # right slot coords of left node
                        vCon = VisConnection(leftCon, lColIdx, leftCon.leftNode.order, rx, ry, colIdx, node.order, lx, ly)
                        conDict[(leftCon.leftNode.order, node.order)] = vCon
                        vCon.render(self.lineLayer)
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
        if factor > 0.8:
            showAndHide([self.nodeLayer, self.slotLabelLayer, self.nodeLabelLayer, self.lineLayer], [])
        elif factor > 0.4:
            showAndHide([self.nodeLayer, self.nodeLabelLayer, self.lineLayer], [self.slotLabelLayer])
        elif factor > 0.2:
            showAndHide([self.nodeLayer, self.lineLayer], [self.slotLabelLayer, self.nodeLabelLayer])
        else:
            showAndHide([self.nodeLayer], [self.slotLabelLayer, self.nodeLabelLayer, self.lineLayer])

    def mousePressEvent(self, event):
        self.mouse.pressEvent(event)

    def leftClick(self, event):
        # print 'leftClick'
        pass

    def rightClick(self, event):
        pos = event.pos()
        item = self.itemAt(pos)
        if item:
            data = str(item.data(0).toString())
            if data:
                # print 'rightClick data:{}'.format(data)
                obj = json.loads(data)
                vNode = None
                tp = obj['type']
                if tp in ('Task', 'File', 'Link'):
                    vNode = self.vNodeDict[tuple(obj['id'])]
                elif tp == 'Slot':
                    vNode = self.vNodeDict[tuple(obj['prnt'])]
                if vNode:
                    self.selectedVNode = vNode
                    self.nodePopup.exec_(QtGui.QCursor.pos())
            else:
                pass
                # print 'rightClick no data'
        else:
            pass
            # print 'rightClick'

    def actSelectWithDepends(self):
        # print str(self.conList)
        def selectVNode(vNode):
            # print 'selectVNode('
            if not vNode.selected:
                vNode.select()
                self.selectedVisEntList.append(vNode)
                for con in vNode.node.rightCons:
                    rn = con.rightNode
                    vCon = self.conList[vNode.colIdx + 1][(vNode.node.order, rn.order)]
                    selectVCon(vCon)
        
        def selectVCon(vCon):
            if not vCon.selected:
                vCon.select()
                self.selectedVisEntList.append(vCon)
                vNode = self.vNodeDict[(vCon.rCol, vCon.rOrd)]
                selectVNode(vNode)
    
        if self.selectedVNode:
            self.nodePopup.deselectAction.setEnabled(True)
            selectVNode(self.selectedVNode)

    def actDeselectAll(self):
        # print 'actDeselectAll()'
        self.nodePopup.deselectAction.setEnabled(False)
        for ent in self.selectedVisEntList:
            ent.deselect()
        self.selectedVisEntList = []

    def closeEvent(self, event):
        # print('Close Event')
        exit()

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