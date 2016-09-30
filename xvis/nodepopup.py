from PyQt4 import QtGui, QtCore

class NodePopup(QtGui.QMenu):

    def __init__(self, parent):
        super(self.__class__, self).__init__(parent)
        self.showAction = self.addAction('Show')
        