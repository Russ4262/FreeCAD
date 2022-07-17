# -*- coding: utf-8 -*-
# Creates a Gui input window with user-added inputs and returns values.
#
# (c) Russell Johnson <russ4262>

__Name__ = "Gui Input"
__Comment__ = "Creates a Gui input window with user-added inputs and returns values"
__doc__ = "Creates a Gui input window with user-added inputs and returns values"
__Author__ = "russ4262"
__Version__ = "1.0"
__Date__ = "2022-06-05"
__License__ = ""
__Web__ = ""
__Wiki__ = ""
__Icon__ = ""
__Help__ = ""
__Status__ = "stable"
__Requires__ = "Freecad >= 0.19"
__Communication__ = ""
__Files__ = ""


import FreeCAD
from PySide import QtCore, QtGui

IS_MACRO = False


def selectInComboBox(name, combo):
    """selectInComboBox(name, combo) ...
    helper function to select a specific value in a combo box."""
    blocker = QtCore.QSignalBlocker(combo)
    index = combo.currentIndex()  # Save initial index

    # Search using currentData and return if found
    newindex = combo.findData(name)
    if newindex >= 0:
        combo.setCurrentIndex(newindex)
        return

    # if not found, search using current text
    newindex = combo.findText(name, QtCore.Qt.MatchFixedString)
    if newindex >= 0:
        combo.setCurrentIndex(newindex)
        return

    # not found, return unchanged
    combo.setCurrentIndex(index)
    return


def populateCombobox(form, enumTups, comboBoxesPropertyMap):
    """populateCombobox(form, enumTups, comboBoxesPropertyMap) ... populate comboboxes with translated enumerations
    ** comboBoxesPropertyMap will be unnecessary if UI files use strict combobox naming protocol.
    Args:
        form = UI form
        enumTups = list of (translated_text, data_string) tuples
        comboBoxesPropertyMap = list of (translated_text, data_string) tuples
    """
    # Load appropriate enumerations in each combobox
    for cb, prop in comboBoxesPropertyMap:
        box = getattr(form, cb)  # Get the combobox
        box.clear()  # clear the combobox
        for text, data in enumTups[prop]:  #  load enumerations
            box.addItem(text, data)


class GuiInput:
    def __init__(self, windowTitle=""):
        self.dialog = None
        self.comboBox_1 = None
        self.returnValues = None
        self.labels = []
        self.inputs = []

        # Make dialog window and set layout type
        self.dialog = QtGui.QDialog()
        # self.dialog.resize(350, 100)
        if windowTitle:
            self.dialog.setWindowTitle(windowTitle)
        # self.windowLayout = QtGui.QVBoxLayout(self.dialog)
        # Grid layout info at https://www.pythonguis.com/tutorials/pyside-layouts/
        self.windowLayout = QtGui.QGridLayout(self.dialog)

    # Input Methods
    def addRadioButton(self, label, isChecked=False):
        if label == "":
            return
        radio_label = QtGui.QLabel("")
        # Add QRadio buttons
        radio = QtGui.QRadioButton(label)
        radio.setChecked(isChecked)
        self.inputs.append(("radio", radio))
        self.labels.append(radio_label)
        self.addToLayout(radio)
        return radio

    def addCheckBox(self, label, isChecked=False):
        if label == "":
            return
        checkbox_label = QtGui.QLabel("")
        # Add QRadio buttons
        checkbox = QtGui.QCheckBox(label)
        checkbox.setCheckable(True)
        checkbox.setChecked(isChecked)
        self.inputs.append(("checkbox", checkbox))
        self.labels.append(checkbox_label)
        self.addToLayout(checkbox)
        return checkbox

    def addSpinBox(self, label, value=0):
        if label == "" or not isinstance(value, int):
            return
        # self.insertHorizontalLine()
        # Add QDoubleSpinBox
        spinbox_label = QtGui.QLabel(label)
        # spinbox_label.setAlignment(QtCore.Qt.AlignRight)
        spinbox = QtGui.QSpinBox()
        spinbox.setValue(value)
        self.inputs.append(("spinbox", spinbox))
        self.labels.append(spinbox_label)
        self.addToLayout(spinbox_label, spinbox)
        return spinbox

    def addDoubleSpinBox(self, label, value=0.0):
        if label == "" or not isinstance(value, float):
            return
        # self.insertHorizontalLine()
        # Add QDoubleSpinBox
        spinbox_label = QtGui.QLabel(label)
        # spinbox_label.setAlignment(QtCore.Qt.AlignRight)
        spinbox = QtGui.QDoubleSpinBox()
        spinbox.setDecimals(3)
        spinbox.setValue(value)
        self.inputs.append(("doublespinbox", spinbox))
        self.labels.append(spinbox_label)
        self.addToLayout(spinbox_label, spinbox)
        return spinbox

    def addComboBox(
        self,
        label,
        choices=[
            ("Cat_Translation", "Cat"),
            ("Dog_Translation", "Dog"),
            ("Zebra_Translation", "Zebra"),
        ],
    ):
        if label == "" or len(choices) == 0:
            return
        # self.insertHorizontalLine()
        # Add QComboBox
        comboBox_label = QtGui.QLabel(label)
        # comboBox_label.setAlignment(QtCore.Qt.AlignRight)
        combobox = QtGui.QComboBox()
        for trans, data in choices:
            combobox.addItem(trans, data)
        self.inputs.append(("combobox", combobox))
        self.labels.append(comboBox_label)
        self.addToLayout(comboBox_label, combobox)
        return combobox

    def addIconComboBox(
        self,
        label,
        icons=[
            QtGui.QIcon(":/icons/Path_Stop"),
            QtGui.QIcon(":/icons/Path_Stop"),
            QtGui.QIcon(":/icons/Path_Stop"),
        ],
        texts=["Cat", "Dog", "Zebra"],
        data=["cat", "dog", "zebra"],
    ):
        if (
            label == ""
            or len(texts) != len(data)
            or len(texts) != len(icons)
            or len(data) != len(icons)
        ):
            return
        # self.insertHorizontalLine()
        # Add QComboBox
        comboBox_label = QtGui.QLabel(label)
        # comboBox_label.setAlignment(QtCore.Qt.AlignRight)
        combobox = QtGui.QComboBox()
        for i in range(len(icons)):
            combobox.addItem(icons[i], texts[i], data[i])
        self.inputs.append(("combobox", combobox))
        self.labels.append(comboBox_label)
        self.addToLayout(comboBox_label, combobox)
        return combobox

    def addDoubleVector(self, label, value=FreeCAD.Vector(0.0, 0.0, 0.0)):
        if label == "" or not isinstance(value, FreeCAD.Vector):
            return
        # self.insertHorizontalLine()
        self.insertHorizontalLineDouble()

        spinbox_label_spacer = QtGui.QLabel(" ----- ")
        spinbox_label = QtGui.QLabel(label)
        self.inputs.append(("none", None))
        self.labels.append(spinbox_label)
        self.addToLayout(spinbox_label_spacer, spinbox_label)

        # Add QDoubleSpinBoxes for X, Y, and Z values
        # Make X value input
        spinbox_label_x = QtGui.QLabel(" X ")
        spinbox_label_x.setAlignment(QtCore.Qt.AlignRight)
        spinbox_x = QtGui.QDoubleSpinBox()
        spinbox_x.setDecimals(3)
        spinbox_x.setValue(value.x)
        self.inputs.append(("doublevectorx", spinbox_x))
        self.addToLayout(spinbox_label_x, spinbox_x)
        # Make Y value input
        spinbox_label_y = QtGui.QLabel(" Y ")
        spinbox_label_y.setAlignment(QtCore.Qt.AlignRight)
        spinbox_y = QtGui.QDoubleSpinBox()
        spinbox_y.setDecimals(3)
        spinbox_y.setValue(value.y)
        self.inputs.append(("doublevectory", spinbox_y))
        self.addToLayout(spinbox_label_y, spinbox_y)
        # Make Z value input
        spinbox_label_z = QtGui.QLabel(" Z ")
        spinbox_label_z.setAlignment(QtCore.Qt.AlignRight)
        spinbox_z = QtGui.QDoubleSpinBox()
        spinbox_z.setDecimals(3)
        spinbox_z.setValue(value.z)
        self.inputs.append(("doublevectorz", spinbox_z))
        self.addToLayout(spinbox_label_z, spinbox_z)
        return (spinbox_x, spinbox_y, spinbox_z)

    # Support Methods
    def addToLayout(self, widget1, widget2=None):
        row = len(self.inputs)
        if widget2:
            self.windowLayout.addWidget(widget1, row, 0)
            self.windowLayout.addWidget(widget2, row, 1)
        else:
            self.windowLayout.addWidget(widget1, row, 1)

    def insertHorizontalLine(self):
        if len(self.inputs) < 1:
            return
        line = QtGui.QFrame()
        line.setFrameShape(QtGui.QFrame.HLine)
        self.windowLayout.addWidget(line)

    def insertHorizontalLineDouble(self):
        line1 = QtGui.QFrame()
        line1.setFrameShape(QtGui.QFrame.HLine)
        line2 = QtGui.QFrame()
        line2.setFrameShape(QtGui.QFrame.HLine)
        self.inputs.append(("line", None))
        self.addToLayout(line1, line2)

    def addStandardButtons(self):
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

    def getValues(self):
        values = []
        x = 0.0
        y = 0.0
        for (inputType, input) in self.inputs:
            if inputType == "radio":
                values.append(input.isChecked())
            elif inputType == "checkbox":
                values.append(input.isChecked())
            elif inputType == "combobox":
                values.append(input.currentData())
            elif inputType == "spinbox":
                values.append(input.value())
            elif inputType == "doublespinbox":
                values.append(input.value())
            elif inputType == "doublevectorx":
                x = input.value()
            elif inputType == "doublevectory":
                y = input.value()
            elif inputType == "doublevectorz":
                values.append(FreeCAD.Vector(x, y, input.value()))
                x = 0.0
                y = 0.0
        return tuple(values)

    def getLabels(self):
        return self.labels

    def setWindowTitle(self, title):
        self.dialog.setWindowTitle(title)

    def getInputByIndex(self, index):
        return self.inputs[index][1]

    def getLabelByIndex(self, index):
        return self.labels[index]

    def execute(self):
        self.addStandardButtons()
        self.dialog.show()
        self.dialog.exec_()
        return self.returnValues

    def proceed(self):
        # print(f"Combo Box 1: {self.comboBox_1.currentText()}")
        self.returnValues = self.getValues()
        self.close()  # close the window

    def close(self):
        # self.dialog.hide()
        self.dialog.done(0)


if FreeCAD.GuiUp and IS_MACRO:
    gcb = GuiInput()
    gcb.addComboBox("LABEL_COMBO_1")
    gcb.addRadioButton("LABEL_RADIO_1")
    gcb.addCheckBox("LABEL_CHECK_1")
    gcb.addSpinBox("LABEL_SPIN_1")
    gcb.addDoubleSpinBox("LABEL_SPIN_2")
    values = gcb.execute()
    if values is not None:
        print(f"Values: {values}")
