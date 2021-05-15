# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2019 Markus Lampert (mlamptert)                         *
# *   Copyright (c) 2020 Russell Johnson (russ4262) <russ4262@gmail.com>    *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

import FreeCAD
import FreeCADGui
import PathScripts.PathGeom as PathGeom
import PathScripts.PathLog as PathLog
import time

# lazily loaded modules
# from lazy_loader.lazy_loader import LazyLoader

from PySide import QtCore, QtGui

__title__ = "Path Selection Utilities GUI"
__author__ = "Russell Johnson (Russ4262)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Collection of GUI selection utilities to enhance Base Geometry feature."

PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class SelectionUtils():
    """
    """

    def __init__(self, obj):
        self.form = None
        self.obj = obj
        self.dockedWindow = None
        self.errorText = None
        self.selectionDefinition = None
        self.selectionDefinitionText = None
        self.comboOptions = {
            "featureType": ["Faces", "Wires", "Edges", "Vertexes"],
            "featureOrientation": ["Horizontal", "Vertical", "Neither", "Both", "All", "Custom Normal"]}
        # self.gui_show_form()

    def _gui_make_form(self):
        form = QtGui.QWidget()  # QtGui.QDialog()
        layout = QtGui.QVBoxLayout()
        formLayout = QtGui.QFormLayout()
        form.resize(300, 500)

        # Use QLabel for error text
        form.errorLabel = QtGui.QLabel("")
        font = form.errorLabel.font().family()
        pt = form.errorLabel.font().pointSize()
        form.errorLabel.setFont(QtGui.QFont(font, pt + 2.0))  # Increase font size
        form.errorLabel.setStyleSheet("QLabel { color:red; }")  # Set font color # background-color:red
        #formLayout.addWidget(form.errorLabel)  # Single column
        formLayout.addRow(form.errorLabel)  # Span two columns

        # assign base button and text
        form.baseLabel = QtGui.QLabel("No base assigned")
        font = form.baseLabel.font().family()
        pt = form.baseLabel.font().pointSize()
        form.baseLabel.setFont(QtGui.QFont(font, pt + 1.0))  # Increase font size
        form.assignBase = QtGui.QPushButton("Assign Base")
        form.assignBase.setCheckable(True)
        #formLayout.addWidget(form.baseLabel)
        #formLayout.addWidget(form.assignBase)
        formLayout.addRow(form.baseLabel)
        formLayout.addRow(form.assignBase)

        QtCore.QObject.connect(form.assignBase, QtCore.SIGNAL("clicked()"), self._assign_base)

        # feature selection type
        form.featureType = QtGui.QComboBox()
        form.featureType.addItem("Faces")
        form.featureType.addItem("Wires")
        form.featureType.addItem("Edges")
        form.featureType.addItem("Vertexes")
        form.featureType.setToolTip("Choose the features to select.")
        formLayout.addRow(QtGui.QLabel("Feature type: "), form.featureType)
        QtCore.QObject.connect(form.featureType, QtCore.SIGNAL("currentIndexChanged(QString)"), self._update_visibilities)

        # feature orientation
        form.featureOrientation = QtGui.QComboBox()
        form.featureOrientation.addItem("Horizontal")
        form.featureOrientation.addItem("Vertical")
        form.featureOrientation.addItem("Neither")
        form.featureOrientation.addItem("Both")
        form.featureOrientation.addItem("All")
        form.featureOrientation.addItem("Custom Normal")
        form.featureOrientation.setToolTip("Choose the orientation of the features.")
        form.featureOrientationLabel = QtGui.QLabel("Feature orientation: ")
        formLayout.addRow(form.featureOrientationLabel, form.featureOrientation)

        # selection definition
        form.selectionDefinitionLabel = QtGui.QLabel("Selection definition: ")
        form.selectionDefinition = QtGui.QLineEdit()
        form.selectionDefinition.setToolTip("Enter the selection definition text.")
        formLayout.addRow(form.selectionDefinitionLabel, form.selectionDefinition)

        # Checkboxes for modifications to selection
        form.modPlanar = QtGui.QCheckBox()
        form.modPlanar.setCheckable(True)
        form.modPlanar.setChecked(True)
        form.modPlanarLabel = QtGui.QLabel("Planar")
        formLayout.addRow(form.modPlanarLabel, form.modPlanar)

        form.modCircular = QtGui.QCheckBox()
        form.modCircular.setCheckable(True)
        form.modCircular.setChecked(False)
        form.modCircularLabel = QtGui.QLabel("Circular")
        formLayout.addRow(form.modCircularLabel, form.modCircular)

        form.modLinear = QtGui.QCheckBox()
        form.modLinear.setCheckable(True)
        form.modLinear.setChecked(True)
        form.modLinearLabel = QtGui.QLabel("Linear")
        formLayout.addRow(form.modLinearLabel, form.modLinear)

        form.modCylindrical = QtGui.QCheckBox()
        form.modCylindrical.setCheckable(True)
        form.modCylindrical.setChecked(False)
        form.modCylindricalLabel = QtGui.QLabel("Cylindrical")
        formLayout.addRow(form.modCylindricalLabel, form.modCylindrical)

        # Add and remove selection buttons
        form.addSelectionBtn = QtGui.QPushButton("Add")
        form.addSelectionBtn.setCheckable(True)
        form.removeSelectionBtn = QtGui.QPushButton("Subtract")
        form.removeSelectionBtn.setCheckable(True)
        formLayout.addRow(form.addSelectionBtn, form.removeSelectionBtn)
        QtCore.QObject.connect(form.addSelectionBtn, QtCore.SIGNAL("clicked()"), self._gui_add_selection)
        QtCore.QObject.connect(form.removeSelectionBtn, QtCore.SIGNAL("clicked()"), self._gui_remove_selection)

        layout.addLayout(formLayout)
        form.setLayout(layout)
        return form

    def _update_visibilities(self):
        # FreeCAD.Console.PrintMessage("_update_visibilities\n")
        featIdx = self.form.featureType.currentIndex()
        # featType = self.comboOptions["featureType"][featIdx]

        if featIdx == 0:  # Faces
            show = ["featureOrientation", "modPlanar", "modCircular", "modCylindrical"]
            hide = ["modLinear"]
        elif featIdx == 1:  # Wires
            # show = ["featureOrientation", "modPlanar", "modCircular"]
            # hide = ["modLinear", "modCylindrical"]
            show = list()
            hide = ["featureOrientation", "modPlanar", "modCircular", "modLinear", "modCylindrical"]
        elif featIdx == 2:  # Edges
            show = ["featureOrientation", "modCircular", "modLinear"]
            hide = [ "modPlanar", "modCylindrical"]
        elif featIdx == 3:  # Vertexes
            show = list()
            hide = ["featureOrientation", "modPlanar", "modCircular", "modLinear", "modCylindrical"]
        
        for s in show:
            exec("self.form.{}.show()".format(s))
            exec("self.form.{}Label.show()".format(s))
        for h in hide:
            exec("self.form.{}.hide()".format(h))
            exec("self.form.{}Label.hide()".format(h))

    def _gui_add_selection(self):
        # FreeCAD.Console.PrintMessage("_gui_add_selection\n")
        self._clearError()
        # Uncheck (release) button
        time.sleep(0.3)
        self.form.addSelectionBtn.setChecked(False)

        # verify selection base exists
        if not self.obj.base:
            self.form.errorLabel.setText("No active base.")
            return False

        (base, subsList) = self._select_features_in_gui()
        FreeCADGui.Selection.addSelection(base, subsList)

    def _gui_remove_selection(self):
        FreeCAD.Console.PrintMessage("_gui_remove_selection\n")
        self._clearError()
        # Uncheck (release) button
        time.sleep(0.3)
        self.form.removeSelectionBtn.setChecked(False)

        # verify selection base exists
        if not self.obj.base:
            self.form.errorLabel.setText("No active base.")
            return False

        (base, subsList) = self._select_features_in_gui()
        for sub in subsList:
            FreeCADGui.Selection.removeSelection(base, sub)

    def _select_features_in_gui(self):
        shpTypes = ["Face", "Wire", "Edge", "Vertex"]
        base = self.obj.base
        # doc = FreeCAD.ActiveDocument
        featIdx = self.form.featureType.currentIndex()
        featType = self.comboOptions["featureType"][featIdx]
        feats = getattr(base.Shape, featType)
        cnt = len(feats)
        ft = shpTypes[featIdx]
        subsList = list()
        if featType == "Wires":
            FreeCAD.Console.PrintError("No 'Wires' orientations or modifications available. See _is_wire_oriented_correctly().\n")
            FreeCAD.Console.PrintError("_update_visibilities() needs adjusted when orientations and modifications added.\n")
            
        else:
            for i in range(cnt):
                ftName = ft + str(i + 1)
                if self._meets_orientation_criteria(base, ftName):
                    subsList.append(ftName)
        return (base, subsList)

    def _meets_orientation_criteria(self, base, ftName):
        typ = ftName[:4]
        feat = getattr(base.Shape, ftName)
        if typ == "Vert":
            return True
        elif typ == "Edge":
            if self._is_edge_oriented_correctly(typ, feat):
                return True
        elif typ == "Wire":
            if self._is_wire_oriented_correctly(typ, feat):
                return True
        elif typ == "Face":
            if self._is_face_oriented_correctly(typ, feat):
                return True

    # Edge analysis methods
    def _is_edge_oriented_correctly(self, typ, feat):
        oIdx = self.form.featureOrientation.currentIndex()  # orientation
        bbx = feat.BoundBox

        if oIdx == 0:  # Horizontal index
            return self._is_edge_horizontal(feat, bbx)
        elif oIdx == 1:  # Vertical index
            return self._is_edge_vertical(feat, bbx)
        elif oIdx == 2:  # Neither index
            return self._is_edge_neither(feat, bbx)
        elif oIdx == 3:  # Both index
            if self._is_edge_horizontal(feat, bbx):
                return True
            if self._is_edge_vertical(feat, bbx):
                return True
        elif oIdx == 4:  # All index
            if self.form.modLinear.isChecked():
                if feat.Curve.TypeId == "Part::GeomLine":
                    return True
                lastCheck = False
            if self.form.modCircular.isChecked():
                if feat.Curve.TypeId == "Part::GeomCircle":
                    return True
                lastCheck = False
            if lastCheck:
                return True

        return False

    def _is_edge_horizontal(self, feat, bbx):
        if not PathGeom.isRoughly(bbx.ZMin, bbx.ZMax):
            return False
        if self.form.modLinear.isChecked():
            if feat.Curve.TypeId != "Part::GeomLine":
                return False
        if self.form.modCircular.isChecked():
            if feat.Curve.TypeId != "Part::GeomCircle":
                return False
        return True

    def _is_edge_vertical(self, feat, bbx):
        lastCheck = True
        if self.form.modLinear.isChecked() and not self.form.modCircular.isChecked():
            if feat.Curve.TypeId != "Part::GeomLine":
                return False
            p0 = feat.Vertexes[0].Point
            p1 = feat.valueAt(feat.FirstParameter + (feat.Length / 2.0))
            p2 = feat.Vertexes[1].Point
            if not PathGeom.isRoughly(p0.x, p1.x) or not PathGeom.isRoughly(p0.y, p1.y):
                return False
            elif not PathGeom.isRoughly(p2.x, p1.x) or not PathGeom.isRoughly(p2.y, p1.y):
                return False
            elif not PathGeom.isRoughly(p2.x, p0.x) or not PathGeom.isRoughly(p2.y, p0.y):
                return False
            lastCheck = False
        if self.form.modCircular.isChecked() and not self.form.modLinear.isChecked():
            if feat.Curve.TypeId != "Part::GeomCircle":
                return False
            norm = feat.normalAt(0.0)
            if not PathGeom.isRoughly(norm.z, 0.0):
                return False
            if PathGeom.isRoughly(bbx.ZMin, bbx.ZMax):
                return False
            lastCheck = False
        if lastCheck:
            if PathGeom.isRoughly(bbx.ZMin, bbx.ZMax):
                return False
        return True

    def _is_edge_neither(self, feat, bbx):
        if self.form.modLinear.isChecked():
            if feat.Curve.TypeId == "Part::GeomLine":
                if PathGeom.isRoughly(bbx.ZMin, bbx.ZMax):
                    return False
            p0 = feat.Vertexes[0].Point
            p1 = feat.valueAt(feat.FirstParameter + (feat.Length / 2.0))
            p2 = feat.Vertexes[1].Point
            if PathGeom.isRoughly(p0.x, p1.x) and PathGeom.isRoughly(p0.y, p1.y):
                return False
            elif PathGeom.isRoughly(p2.x, p1.x) and PathGeom.isRoughly(p2.y, p1.y):
                return False
            elif PathGeom.isRoughly(p2.x, p0.x) and PathGeom.isRoughly(p2.y, p0.y):
                return False
        if self.form.modCircular.isChecked():
            if feat.Curve.TypeId == "Part::GeomCircle":
                if PathGeom.isRoughly(bbx.ZMin, bbx.ZMax):
                    return False
                norm = feat.normalAt(0.0)
                if PathGeom.isRoughly(norm.z, 0.0):
                    return False
                if PathGeom.isRoughly(bbx.ZMin, bbx.ZMax):
                    return False
                return True
        return True

    # Wire analysis methods
    def _is_wire_oriented_correctly(self, typ, feat):
        # FreeCAD.Console.PrintMessage("_is_wire_oriented_correctly\n")
        return True
            
    # Face analysis methods
    def _is_face_oriented_correctly(self, typ, feat):
        oIdx = self.form.featureOrientation.currentIndex()  # orientation
        bbx = feat.BoundBox
        norm = feat.normalAt(0.0, 0.0)
        lastCheck = True

        if oIdx == 0:  # Horizontal index
            return self._is_face_horizontal(feat, bbx, norm)
        elif oIdx == 1:  # Vertical index
            return self._is_face_vertical(feat, bbx, norm)
        elif oIdx == 2:  # Neither index
            if self.form.modPlanar.isChecked():
                if PathGeom.isRoughly(abs(norm.z), 1.0):
                    return False
                if PathGeom.isRoughly(norm.z, 0.0):
                    return False
                if not self._is_face_planar(feat):
                    return False
                lastCheck = False
            if self.form.modCylindrical.isChecked():
                if not PathGeom.isRoughly(abs(norm.z), 1.0):
                    return False
                if not self._is_face_cylindrical(feat):
                    return False
                lastCheck = False
            if self.form.modCircular.isChecked():  # will be planar
                if PathGeom.isRoughly(abs(norm.z), 1.0):
                    return False
                if PathGeom.isRoughly(norm.z, 0.0):
                    return False
                if not self._is_face_circular(feat):
                    return False
                lastCheck = False
            if lastCheck:
                if PathGeom.isRoughly(abs(norm.z), 1.0):
                    return False
                if PathGeom.isRoughly(norm.z, 0.0):
                    return False
            return True
        elif oIdx == 3:  # Both index
            if self._is_face_horizontal(feat, bbx, norm):
                FreeCAD.Console.PrintMessage("_is_face_horizontal\n")
                return True
            if self._is_face_vertical(feat, bbx, norm):
                FreeCAD.Console.PrintMessage("_is_face_vertical\n")
                return True
        elif oIdx == 4:  # All index
            if self.form.modPlanar.isChecked():
                if self._is_face_planar(feat):
                    return True
                lastCheck = False
            if self.form.modCylindrical.isChecked():
                if self._is_face_cylindrical(feat):
                    return True
                lastCheck = False
            if self.form.modCircular.isChecked():  # will be planar
                if self._is_face_circular(feat):
                    return True
                lastCheck = False
            if lastCheck:
                return True
        return False

    def _is_face_horizontal(self, feat, bbx, norm):
        lastCheck = True
        if self.form.modPlanar.isChecked():
            if not PathGeom.isRoughly(bbx.ZMin, bbx.ZMax):  # geometrically flat and horizontal
                return False
            if not PathGeom.isRoughly(abs(norm.z), 1.0):
                return False
            lastCheck = False
        if self.form.modCylindrical.isChecked():
            if not PathGeom.isRoughly(abs(norm.z), 1.0):
                return False
            if not self._is_face_cylindrical(feat):
                return False
            lastCheck = False
        if self.form.modCircular.isChecked():  # will be planar
            if not PathGeom.isRoughly(abs(norm.z), 1.0):
                return False
            if not self._is_face_circular(feat):
                return False
            lastCheck = False
        if lastCheck:
            if not PathGeom.isRoughly(abs(norm.z), 1.0):
                return False
        return True

    def _is_face_vertical(self, feat, bbx, norm):
        lastCheck = True
        if self.form.modPlanar.isChecked():
            if not PathGeom.isRoughly(norm.z, 0.0):
                return False
            if not self._is_face_planar(feat):
                return False
            lastCheck = False
        if self.form.modCylindrical.isChecked():
            if not PathGeom.isRoughly(norm.z, 0.0):
                return False
            if not self._is_face_cylindrical(feat):
                return False
            lastCheck = False
        if self.form.modCircular.isChecked():  # will be planar
            if not PathGeom.isRoughly(norm.z, 0.0):
                return False
            if not self._is_face_circular(feat):
                return False
            lastCheck = False
        if lastCheck:
            if not PathGeom.isRoughly(norm.z, 0.0):
                return False
        return True

    def _is_face_circular(self, feat):
        if len(feat.Edges) > 1:
            return False
        if feat.Edge1.Curve.TypeId != "Part::GeomCircle":
            return False

        return True

    def _is_face_cylindrical(self, feat):
        FreeCAD.Console.PrintMessage("_is_face_cylindrical\n")
        circleEdgeCnt = 0
        for e in feat.Edges:
            if e.Curve.TypeId == "Part::GeomCircle":
                circleEdgeCnt += 1
        if circleEdgeCnt > 1:  #  ==2
            return True
        return False

    def _is_face_planar(self, feat):
        if PathGeom.isRoughly(feat.Volume, 0.0, 0.0000001):
            return True
        return False

    # Other methods
    def _assign_base(self):
        # FreeCAD.Console.PrintMessage("assign base\n")
        self._clearError()
        time.sleep(0.3)
        self.form.assignBase.setChecked(False)
        base = self._get_base_selected()
        if not base:
            return

        self.obj.base = base
        self.form.baseLabel.setText("Base: " + self.obj.base.Name)
        FreeCADGui.Selection.clearSelection()

    def _get_base_selected(self):
        # Get GUI face selection
        guiSel = FreeCADGui.Selection.getSelection()
        if not guiSel:
            self.form.errorLabel.setText("No base selected in viewport.")
            return None

        base = guiSel[0]
        tid = base.TypeId
        if tid[:12] == "PartDesign::":
            if tid[-6:] != "::Body":
                base = base.Parents[0][0]

        """
        # print(base.Name)
        subs_list = FreeCADGui.Selection.getSelectionEx()
        sub = subs_list[0]
        if len(sub.SubElementNames):
            for name in sub.SubElementNames:
                # print("subs: {}".format(subs_list))
                # print("sub: {}".format(sub))
                # print("name: {}".format(name))

                if hasattr(base, "Shape"):
                    base_shape = base.Shape.getElement(name)
                else:
                    base_shape = base.getElement(name)
        else:
            base_shape = base.Shape
        """

        return base

    def _clearError(self):
        self.form.errorLabel.setText("")

    # Unused methods
    def _is_clean_definition(self):
        text = self.form.selectionDefinition.text().strip()  # strip whitespace
        self.selectionDefinition = text
        error = None

        if not text:
            return True

        if len(text) < 3:
            # Check minimum definition length
            error = "short length"
        elif len(text) > 10:
            # Check minimum definition length
            error = "short length"
        elif text[:2] not in ["+ ", "- "]:
            # Check of add or subtract selection definition
           error = "add or subtract"
        elif text[2:3] not in ["_", "|", "/", "o", "."]:
            # Check of add or subtract selection definition
           error = "feature indicator"

        if error:
           self.form.defText.setText("! {}".format(error))
           return False

        return True

    def _refine_selection_features(self):
        FreeCAD.Console.PrintMessage("make defined selection\n")
        text = self.selectionDefinition
        if not text:
            return True

        act = self.selectionDefinition[:2]
        feat = self.selectionDefinition[2:3]

        if act == "+ ":
            self.selectionDefinitionText = "Add"
        else:
            self.selectionDefinitionText = "Sub"

        if feat == "_":
            self.selectionDefinitionText += " horiz faces"
        elif feat == "|":
            self.selectionDefinitionText += " vert faces"
        elif feat == "/":
            self.selectionDefinitionText += " other faces"
        elif feat == "o":
            self.selectionDefinitionText += " circle wires"
        elif feat == ".":
            self.selectionDefinitionText += " vertexes"
        else:
           self.form.defText.setText("! feature error")
           return False

        return True

    def _make_selection(self):
        FreeCAD.Console.PrintMessage("make selection\n")
        # Uncheck (release) button
        self.form.applySelection.setChecked(False)

        # verify selection base exists
        if not self.obj.base:
            self.form.errorLabel.setText("No active base.")
            return False

        # verify definition text
        if not self._is_clean_definition():
            return False

        # refine feature selection per definition
        if not self._refine_selection_features():
            return False

        # self.form.defText.setText(self.selectionDefinitionText)
        return True

    def _gui_accept(self):
        FreeCAD.Console.PrintMessage("accept\n")

    def _gui_close(self):
        # FreeCAD.Console.PrintMessage("reject\n")
        self.form.dock.close()  # close the dock window
        # self.form.hide()

    def _spare_form_elements(self):
        """
        # Apply selection button
        form.applySelection = QtGui.QPushButton("Apply Selection")
        form.applySelection.setCheckable(True)
        form.defText = QtGui.QLabel("DEFINITION")
        formLayout.addRow(form.defText, form.applySelection)
        QtCore.QObject.connect(form.applySelection, QtCore.SIGNAL("clicked()"), self._make_selection)

        # step over
        form.StepOver = QtGui.QSpinBox()
        form.StepOver.setMinimum(15)
        form.StepOver.setMaximum(75)
        form.StepOver.setSingleStep(1)
        form.StepOver.setValue(25)
        form.StepOver.setToolTip("Optimal value for tool stepover")
        formLayout.addRow(QtGui.QLabel("Step Over Percent"), form.StepOver)

        # helix angle
        form.HelixAngle = QtGui.QDoubleSpinBox()
        form.HelixAngle.setMinimum(1)
        form.HelixAngle.setMaximum(89)
        form.HelixAngle.setSingleStep(1)
        form.HelixAngle.setValue(5)
        form.HelixAngle.setToolTip("Angle of the helix ramp entry")
        formLayout.addRow(QtGui.QLabel("Helix Ramp Angle"), form.HelixAngle)

        # Force inside out
        form.ForceInsideOut = QtGui.QCheckBox()
        form.ForceInsideOut.setChecked(True)
        formLayout.addRow(QtGui.QLabel("Force Clearing Inside-Out"), form.ForceInsideOut)

        # Finishing profile
        form.FinishingProfile = QtGui.QCheckBox()
        form.FinishingProfile.setChecked(True)
        formLayout.addRow(QtGui.QLabel("Finishing Profile"), form.FinishingProfile)

        # Add OK / Cancel buttons
        form.okbox = QtGui.QDialogButtonBox(form)
        form.okbox.setOrientation(QtCore.Qt.Horizontal)
        # Add standard Qt buttons
        form.okbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        layout.addWidget(form.okbox)
        QtCore.QObject.connect(self.form.okbox, QtCore.SIGNAL("accepted()"), self._gui_accept)
        QtCore.QObject.connect(self.form.okbox, QtCore.SIGNAL("rejected()"), self._gui_close)
        """
        pass

    # Public methods
    def gui_show_form(self):
        self.form = self._gui_make_form()

        # Dock the selection utility window
        mainWindow = FreeCADGui.getMainWindow()  # parent window to recieve new dockable window
        self.form.dock = QtGui.QDockWidget("Selection Utilities", mainWindow)  # Create dock object with title and parent arguments
        self.form.dock.setWidget(self.form)  # set content of dock window
        mainWindow.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.form.dock,
                         QtCore.Qt.Orientation.Vertical)  # Add dock window to main window

        QtCore.QMetaObject.connectSlotsByName(self.form)
        self.dockedWindow = self.form.dock
        # self.form.show()
        # self.form.exec_()
        self._update_visibilities()
# Eclass

# obj = PsuedoObject()
# ms = SelectionUtils(obj)
# window = ms.gui_show_form()
