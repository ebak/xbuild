import PyQt4
import sys
from collections import defaultdict
from PyQt4 import QtGui, QtCore
from model import Model, FileNode, TaskNode, CrossLinkNode

# http://doc.qt.io/qt-4.8/qgraphicsview.html

class MyView(QtGui.QGraphicsView):

    NodeFontName = 'Sans'
    NodeFontSize = 12
    ConSpacing = 10
    NodeSpacing = 20

    def __init__(self, model):
        font = QtGui.QFont(MyView.NodeFontName, MyView.NodeFontSize)
    
        def getText(node):
            if isinstance(node, TaskNode):
                return 'Task: ' + node.id
            elif isinstance(node, FileNode):
                return 'File: ' + node.id
            return None

        def getMaxTextWidth(nodes):
            maxW = 0
            for n in nodes:
                text = getText(n)
                if text:
                    fm = QtGui.QFontMetrics(font)
                    w = fm.width(text)
                    if w > maxW:
                        maxW = w
            return maxW
                
        QtGui.QGraphicsView.__init__(self)

        self.scene = QtGui.QGraphicsScene(self)
        xPos = 0
        rightConDict = defaultdict(list) # {(nodeId, rightNodeId): [(x, y)]}
        leftConDict = defaultdict(list)  # {(leftNodeId, nodeId): [(x, y)]}
        for nodes in model.columns:
            w = getMaxTextWidth(nodes)
            rectW = w + 20
            rectH = 30
            yPos = 0
            # print 'col'
            for node in nodes:
                # print 'node: {}'.format(node.id)
                if isinstance(node, CrossLinkNode):
                    # print 'CrossLinkNode!!!'
                    self.scene.addLine(xPos, yPos, xPos + rectW, yPos)
                    lwy0, rwy0 = yPos, yPos
                    yPos += MyView.NodeSpacing
                else:
                    leftWallH = MyView.ConSpacing * (len(node.leftCons) - 1)
                    rightWallH = MyView.ConSpacing * (len(node.rightCons) - 1)
                    boxH = max(leftWallH, rightWallH, rectH)
                    lwy0 = yPos + 0.5 * (boxH - leftWallH)
                    rwy0 = yPos + 0.5 * (boxH - rightWallH)
                    ry0 = yPos + 0.5 * (boxH - rectH)
                    self.scene.addLine(xPos, lwy0, xPos, lwy0 + leftWallH)
                    xPosR = xPos + rectW
                    self.scene.addLine(xPosR, rwy0, xPosR, rwy0 + rightWallH)
                    self.scene.addRect(xPos, ry0, rectW, rectH)
                    textItem = self.scene.addText(getText(node), font)
                    br = textItem.boundingRect()
                    textItem.setX(xPos + 0.5 * (rectW - br.width()))
                    textItem.setY(ry0 + 0.5 * (rectH - br.height()))
                    yPos += boxH + MyView.NodeSpacing
                # connect left nodes
                y0 = lwy0
                x0 = xPos
                # print 'node: {}'.format(node)
                for lCon in node.leftCons:
                    # print 'lCon: {}'.format(lCon)
                    # print 'leftConDict.keys()={}'.format(leftConDict.keys())
                    # if rCon.rightNodeId in rightConDict:
                    # print 'lCon.leftNode.id={} has:{}'.format(lCon.leftNode.id, lCon.leftNode.id in leftConDict)
                    for (x1, y1) in leftConDict[(lCon.leftNode.id, node.id)]:
                        # print 'hey {}, {} -> {}, {}'.format(x0, y0, x1, y1)
                        self.scene.addLine(x0, y0, x1, y1)
                    y0 += MyView.ConSpacing
                # create rightConDict which is the next leftConDict
                y = rwy0
                x = xPos + rectW
                print '{} rightCons: {}'.format(node, node.rightCons)
                for con in node.rightCons:
                    #print 'node.id = {}, con.rightNode.id = {} ({}, {})'.format(
                    #    node.id, con.rightNode.id, x, y)
                    # print 'node = {}, con.rightNode = {} ({}, {})'.format(
                    #    node, con.rightNode, x, y)
                    rightConDict[node.id, con.rightNode.id].append((x, y))
                    y += MyView.ConSpacing
            leftConDict.clear()
            leftConDict.update(rightConDict)
            rightConDict.clear()        
            print 'leftConDict={}'.format(leftConDict.items())
                        
            xPos += rectW + 100
        self.setScene(self.scene)

    def wheelEvent(self, event):
        # print 'wheelEvent: delta:{}'.format(event.delta())  # +- 120
        d = event.delta()
        s = 1.1 if d > 0 else 0.9
        self.scale(s, s)

    def mousePressEvent(self, event):
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