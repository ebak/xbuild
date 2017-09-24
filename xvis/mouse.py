# Copyright (c) 2016 Endre Bak
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import time
from PyQt4 import QtGui, QtCore
Qt = QtCore.Qt


def millis():
    return int(round(time.time() * 1000))

class Pos(object):

    def __init__(self, x=0, y=0):
        self.set(x, y)

    def set(self, x=0, y=0):
        self.x, self.y = x, y

    def setQPos(self, qPos):
        self.x, self.y = qPos.x(), qPos.y()
        
    def setMax(self, x, y):
        ax, ay = abs(x), abs(y)
        if ax > self.x:
            self.x = ax
        if ay > self.y:
            self.y = ay


class Mouse(object):

    def __init__(self):
        self.leftPressPos, self.leftPressTime = Pos(), 0
        self.rightPressPos, self.rightPressTime = Pos(), 0
        self.prevPos = None
        self.maxLeftDelta = Pos() # max delta relative to press position
        self.maxRightDelta = Pos()

    def pressEvent(self, event):
        button = event.button()
        self.prevPos = event.pos()
        if button == Qt.LeftButton:
            self.leftPressTime = millis()
            self.leftPressPos.setQPos(event.pos())
            self.maxLeftDelta.set(0, 0)
        elif button == Qt.RightButton:
            self.rightPressTime = millis()
            self.rightPressPos.setQPos(event.pos())
            self.maxRightDelta.set(0, 0)

    def releaseEvent(self, event, clickHandler):
        button = event.button()
        now = millis()

        def handleClick(bConst, pressTime, pressDelta, handlerFn):
            if button == bConst:
                delta = now - pressTime
                pd = pressDelta
                if delta <= 200 and handlerFn and pd.x < 5 and pd.y < 5:
                    # print 'delta={}'.format(delta)
                    handlerFn(event)

        handleClick(Qt.LeftButton, self.leftPressTime, self.maxLeftDelta, clickHandler.leftClick if clickHandler else None)
        handleClick(Qt.RightButton, self.rightPressTime, self.maxRightDelta, clickHandler.rightClick if clickHandler else None)
            

    def moveEvent(self, event, moveHandler):
        
        def setMaxDelta(maxDelta, curQPos, pressPos):
            dx = curQPos.x() - pressPos.x
            dy = curQPos.y() - pressPos.y
            maxDelta.setMax(dx, dy)

        buttons = event.buttons()
        p = event.pos()
        if Qt.LeftButton & buttons:
            setMaxDelta(self.maxLeftDelta, p, self.leftPressPos)
            if moveHandler:
                moveHandler.leftPressMove(event)
        if Qt.RightButton & buttons:
            setMaxDelta(self.maxRightDelta, p, self.rightPressPos)
            if moveHandler:
                moveHandler.rightPressMove(event)
        self.prevPos = p
