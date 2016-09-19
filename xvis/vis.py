import PyQt4
import sys
from PyQt4 import QtGui, QtCore
from model import Model, FileNode, TaskNode, CrossLinkNode

# http://doc.qt.io/qt-4.8/qgraphicsview.html

class MyView(QtGui.QGraphicsView):

    NodeFontName = 'Sans'
    NodeFontSize = 20

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
        for nodes in model.columns:
            w = getMaxTextWidth(nodes)
            rectW = w + 20
            rectH = 30
            yPos = 0
            # print 'col'
            for node in nodes:
                # print 'node: {}'.format(node.id)
                if isinstance(node, CrossLinkNode):
                    print 'CrossLinkNode!!!'
                    self.scene.addLine(xPos, yPos, xPos + rectW, yPos)
                    yPos += 10
                else:
                    leftWallH = 10 * len(node.leftCons)
                    rightWallH = 10 * len(node.rightCons)
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
                    yPos += boxH + 10
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