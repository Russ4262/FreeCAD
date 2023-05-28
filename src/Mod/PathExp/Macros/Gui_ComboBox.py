# The macro provides a simple Gui window for making a combo box selection.
#
# (c) Russell Johnson <russ4262>

__Name__ = "Gui Combo Box"
__Comment__ = "Creates a Gui combo box and returns selection"
__Author__ = "russ4262"
__Version__ = "1.0"
__Date__ = "2022-06-05"
__License__ = ""
__Web__ = ""
__Wiki__ = ""
__Icon__ = (
    "https://www.freecadweb.org/wiki/images/0/0c/Macro_Airfoil_Import_%26_Scale.png"
)
__Help__ = ""
__Status__ = "stable"
__Requires__ = "Freecad >= 0.19"
__Communication__ = ""
__Files__ = ""


import FreeCAD
from PySide import QtCore, QtGui

IS_MACRO = False
WINDOW_TITLE = "Window Title"
LABEL_LINEEDIT_1 = "Label Line Edit 1"
LABEL_COMBO_1 = "Label Combo 1"
CHOICES_COMBO_1 = ["Cat", "Dog", "Zebra"]


class ComboBox:
    def __init__(self, label, choices):
        self.dialog = None
        self.comboBox_1 = None
        self.returnValue = None
        self.windowTitle = WINDOW_TITLE

        # Make dialog window and set layout type
        self.dialog = QtGui.QDialog()
        self.dialog.resize(350, 100)
        self.dialog.setWindowTitle(self.windowTitle)
        self.windowLayout = QtGui.QVBoxLayout(self.dialog)

        # Add QComboBox
        if len(choices) > 0:
            comboBox_1_label = QtGui.QLabel(label)
            self.windowLayout.addWidget(comboBox_1_label)
            self.comboBox_1 = QtGui.QComboBox()
            for c in choices:
                self.comboBox_1.addItem(c)
            self.windowLayout.addWidget(self.comboBox_1)

    def setWindowTitle(self, title):
        self.windowTitle = title
        self.dialog.setWindowTitle(title)

    def appendStandardButtons(self):
        # Add OK / Cancel buttons
        self.standardButtons = QtGui.QDialogButtonBox(self.dialog)
        self.standardButtons.setOrientation(QtCore.Qt.Horizontal)
        self.standardButtons.setStandardButtons(
            QtGui.QDialogButtonBox.Cancel | QtGui.QDialogButtonBox.Ok
        )
        self.windowLayout.addWidget(self.standardButtons)

        # Connect slots
        QtCore.QObject.connect(
            self.standardButtons, QtCore.SIGNAL("accepted()"), self.proceed
        )
        QtCore.QObject.connect(
            self.standardButtons, QtCore.SIGNAL("rejected()"), self.close
        )
        QtCore.QMetaObject.connectSlotsByName(self.dialog)

    def execute(self):
        self.appendStandardButtons()
        self.dialog.show()
        self.dialog.exec_()
        return self.returnValue

    def proceed(self):
        # print(f"Combo Box 1: {self.comboBox_1.currentText()}")
        self.returnValue = self.comboBox_1.currentText()
        self.close()  # close the window

    def close(self):
        # self.dialog.hide()
        self.dialog.done(0)


if FreeCAD.GuiUp and IS_MACRO:
    gcb = ComboBox(LABEL_COMBO_1, CHOICES_COMBO_1)
    value = gcb.execute()
    print(f"Value 1: {value}")
    gcb = ComboBox(LABEL_COMBO_1, CHOICES_COMBO_1)
    value = gcb.execute()
    print(f"Value 2: {value}")
    # startWindow()
