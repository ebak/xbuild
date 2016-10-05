from PyQt4 import QtGui, QtCore

class NodePopup(QtGui.QMenu):

    def __init__(self, parent):
        super(self.__class__, self).__init__(parent)
        self.parent = parent
        ha = self.selectAction = self.addAction('Select with depends')
        ha.triggered.connect(parent.actSelectWithDepends)
        hb = self.deselectAction = self.addAction('De-select all')
        hb.triggered.connect(parent.actDeselectAll)
        