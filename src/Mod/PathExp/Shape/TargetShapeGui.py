# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2022 Russell Johnson (russ4262) <russ4262@gmail.com>    *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
# *                                                                         *
# *   This library is free software; you can redistribute it and/or         *
# *   modify it under the terms of the GNU Library General Public           *
# *   License as published by the Free Software Foundation; either          *
# *   version 2 of the License, or (at your option) any later version.      *
# *                                                                         *
# *   This library  is distributed in the hope that it will be useful,      *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this library; see the file COPYING.LIB. If not,    *
# *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
# *   Suite 330, Boston, MA  02111-1307, USA                                *
# *                                                                         *
# ***************************************************************************

import FreeCAD
import FreeCADGui
import OpsGui.PathOpGui2 as PathShapeGui
import GuiSupport.PreviewShape as PreviewShape
import Taskpanels.PathTaskPanelPage as PathTaskPanelPage
import Shape.TargetShape as TargetShape

# import PathScripts.PathGui as PathGui

from PySide import QtCore


class TaskPanelOpPage(PathTaskPanelPage.TaskPanelPage):
    # Standard methods
    def initPage(self, obj):
        # self.depthAllowance = PathGui.QuantitySpinBox(
        #    self.form.depthAllowance, obj, "DepthAllowance"
        # )
        self.jobModels = obj.Proxy.job.Model.Group
        self.jobStock = obj.Proxy.job.Stock
        self._populateModel()
        self.rotations = []
        self.initialYawPitchRollValues = {}
        self.roatedShapes = {}
        self._saveModelAndStockPositions()

    def _saveModelAndStockPositions(self):
        for m in self.obj.Proxy.job.Model.Group:
            self.initialYawPitchRollValues[m.Name] = (
                m,
                m.Placement.Rotation.getYawPitchRoll(),
            )
        self.initialYawPitchRollValues["Stock"] = (
            self.obj.Proxy.job.Stock,
            self.obj.Proxy.job.Stock.Placement.Rotation.getYawPitchRoll(),
        )

    def getForm(self):
        """getForm() ... return UI"""
        uiFilePath = (
            FreeCAD.getUserAppDataDir()
            + "Mod\\PathExp\\GuiSupport\\PageTargetShapeEdit.ui"
        )
        form = FreeCADGui.PySideUic.loadUi(uiFilePath)
        # form.depthAllowance.setEnabled(False)
        # form.depthAllowance_label.setEnabled(False)
        return form

    def setFields(self, obj):
        """setFields(obj) ... Transfers obj's property values to UI."""
        self.form.respectFeatureHoles.setChecked(obj.RespectFeatureHoles)
        self.form.respectMergedHoles.setChecked(obj.RespectMergedHoles)
        self.selectInComboBox(obj.Model, self.form.model)
        self.selectInComboBox(obj.Face, self.form.face)
        self.selectInComboBox(obj.Edge, self.form.edge)
        self.form.invertDirection.setChecked(obj.InvertDirection)

        self.updateQuantitySpinBoxes()

        modelName, featName = self._getModelAndFeatureNames()
        if featName == "None":
            # New instance of Target Shape object
            return
        self._setRotationsAttr(modelName, featName)
        print(f"setFields() Applying these rotations: {self.rotations}")
        if obj.Edge == "None":
            self.form.invertDirection.setEnabled(False)
            self.form.invertDirection.hide()

    def getFields(self, obj):
        """getFields(obj) ... Transfer values from UI to obj's properties.
        Called with OK or Apply button activation."""
        # print("getFields()")
        if self.form.respectFeatureHoles.isChecked() != obj.RespectFeatureHoles:
            obj.RespectFeatureHoles = self.form.respectFeatureHoles.isChecked()

        if self.form.respectMergedHoles.isChecked() != obj.RespectMergedHoles:
            obj.RespectMergedHoles = self.form.respectMergedHoles.isChecked()

        if str(self.form.model.currentData()) != obj.Model:
            obj.Model = str(self.form.model.currentData())

        if str(self.form.face.currentText()) != obj.Face:
            obj.Face = str(self.form.face.currentText())

        if str(self.form.edge.currentText()) != obj.Edge:
            obj.Edge = str(self.form.edge.currentText())

        if self.form.invertDirection.isChecked() != obj.InvertDirection:
            obj.InvertDirection = self.form.invertDirection.isChecked()

        if obj.Face != "None" or obj.Edge != "None":
            if obj.Face == "None":
                feat = obj.Edge
            else:
                feat = obj.Face
            baseObj = FreeCAD.ActiveDocument.getObject(obj.Model)
            obj.RotationReferenceLink = [(baseObj, (f"{obj.Model}.{feat}"))]
        else:
            obj.RotationReferenceLink = []

        # self.depthAllowance.updateProperty()
        pass

    def updateQuantitySpinBoxes(self, index=None):
        # self.depthAllowance.updateSpinBox()
        pass

    def registerSignalHandlers(self, obj):
        """registerSignalHandlers(obj) ... overwrite to register custom signal handlers.
        In case an update of a model is not the desired operation of a signal invocation
        (see getSignalsForUpdate(obj)) this function can be used to register signal handlers
        manually."""
        self.form.previewTargetShape.clicked.connect(self.previewTargetShape)
        self.form.model.currentIndexChanged.connect(self._populateFeatures)
        self.form.face.currentIndexChanged.connect(self._updateFace)
        self.form.edge.currentIndexChanged.connect(self._updateEdge)
        self.form.useSelectedFeature.clicked.connect(self._useSelectedModelAndFeature)
        self.form.invertDirection.clicked.connect(self._invertAlignment)

    def getSignalsForUpdate(self, obj):
        """getSignalsForUpdate(obj) ... return list of signals for updating obj"""
        signals = []
        signals.append(self.form.respectFeatureHoles.stateChanged)
        signals.append(self.form.respectMergedHoles.stateChanged)
        # signals.append(self.form.depthAllowance.editingFinished)
        signals.append(self.form.model.currentIndexChanged)
        signals.append(self.form.face.currentIndexChanged)
        signals.append(self.form.edge.currentIndexChanged)
        signals.append(self.form.invertDirection.stateChanged)
        signals.append(self.form.useSelectedFeature.clicked)
        return signals

    # Helper methods
    def previewTargetShape(self):
        self._removePreviewType("preview")

        if self.form.previewTargetShape.isChecked():
            label = "preview"
            # shp = self.obj.Shape
            negRotations = [(a, -1.0 * d) for a, d in self.rotations]

            shp = TargetShape.AlignToFeature.rotateShapeWithList(
                self.obj.Shape, negRotations
            )
            ds = PreviewShape.PreviewShape(shp, color=(1.0, 0.5, 0.0), transparency=0.4)
            self.parent.switch.addChild(ds.root)
            self.targetShapeList.append((self.title, label, ds))
        else:
            # Clear all visuals from screen
            self._removePreviewType("preview")
            self._removePreviewType("rotation_reference")

    def _resetModelStockRotation(self):
        # Reset each model to original rotation
        for obj, (y, p, r) in self.initialYawPitchRollValues.values():
            obj.Placement.Rotation.setYawPitchRoll(y, p, r)
            print(
                f"_resetModelStockRotation() Setting '{obj.Name}' Yaw-Pitch-Roll to : {FreeCAD.Vector(r, p, y)}"
            )

    def _removePreviewType(self, previewType):
        # Clear visuals from viewport per type
        if len(self.targetShapeList) == 0:
            return
        remList = []
        for i in range(len(self.targetShapeList)):
            if self.targetShapeList[i][1] == previewType:
                remList.append(i)
        if len(remList) == 0:
            return
        remList.sort(reverse=True)
        for i in remList:
            __, __, ds = self.targetShapeList.pop(i)
            self.parent.switch.removeChild(ds.root)

    def _useSelectedModelAndFeature(self):
        """_useSelectedModelAndFeature()"""
        # Verify selection is singular and a line
        sel = FreeCADGui.Selection.getSelectionEx()
        if len(sel) != 1:
            FreeCAD.Console.PrintWarning("Select one face or edge.\n")
            return
        subCnt = len(sel[0].SubObjects)
        if subCnt != 1 and subCnt != 0:
            FreeCAD.Console.PrintWarning("Only select one edge.\n")
            return

        # subShp = sel[0].SubObjects[0]
        modelName = sel[0].Object.Name
        featName = sel[0].SubElementNames[0]
        self._setModelAndEdgeInTaskPanel(modelName, featName)
        self._setRotationsAttr(modelName, featName)

    def _setRotationsAttr_orig(self, modelName, featName):
        # print("_setRotationsAttr()")
        rotVect, isPlanar = TargetShape.AlignToFeature.getRotationsByName(
            modelName, featName, self.form.invertDirection.isChecked()
        )
        if not isPlanar:
            FreeCAD.Console.PrintWarning("Selection must be planar.\n")
            return
        print(f"_setRotationsAttr() rotations: {rotVect}")
        self.rotations = rotVect
        self.rotatedShapes = {}
        rotSum = abs(rotVect.x) + abs(rotVect.y) + abs(rotVect.z)
        if rotSum == 0.0:
            for m in self.jobModels:
                self.rotatedShapes[m.Name] = m.Shape.copy()
            self.rotatedShapes["Stock"] = self.jobStock.Shape.copy()
            return

        for m in self.jobModels:
            self.rotatedShapes[
                m.Name
            ] = TargetShape.AlignToFeature.rotateShapeWithVector(m.Shape, rotVect)
        self.rotatedShapes["Stock"] = TargetShape.AlignToFeature.rotateShapeWithVector(
            self.jobStock.Shape, rotVect
        )

    def _setRotationsAttr(self, modelName, featName):
        # print("_setRotationsAttr()")
        rotations, isPlanar = TargetShape.AlignToFeature.getRotationsByName(
            modelName, featName, self.form.invertDirection.isChecked()
        )
        if not isPlanar:
            FreeCAD.Console.PrintWarning("Selection must be planar.\n")
            return
        print(f"_setRotationsAttr() rotations: {rotations}")
        self.rotations = rotations
        self.rotatedShapes = {}
        rotSum = 0.0
        for (__, deg) in rotations:
            rotSum += abs(deg)
        if rotSum == 0.0:
            for m in self.jobModels:
                self.rotatedShapes[m.Name] = m.Shape.copy()
            self.rotatedShapes["Stock"] = self.jobStock.Shape.copy()
            return

        for m in self.jobModels:
            self.rotatedShapes[m.Name] = TargetShape.AlignToFeature.rotateShapeWithList(
                m.Shape, rotations
            )
        self.rotatedShapes["Stock"] = TargetShape.AlignToFeature.rotateShapeWithList(
            self.jobStock.Shape, rotations
        )

    def _getModelAndFeatureNames(self):
        modelName = str(self.form.model.currentData())
        edgeName = str(self.form.edge.currentText())
        faceName = str(self.form.face.currentText())
        if edgeName == "None":
            return modelName, faceName
        return modelName, edgeName

    def _setModelAndEdgeInTaskPanel(self, modelName, featName):
        """_setModelAndEdgeInTaskPanel()"""
        # Set model
        self.selectInComboBox(modelName, self.form.model)
        self._populateFeatures()

        if featName.startswith("Face"):
            # Set Face
            self.selectInComboBox("None", self.form.edge)
            self.selectInComboBox(featName, self.form.face)
            self.form.invertDirection.setEnabled(False)
            self.form.invertDirection.hide()
        else:
            # Set edge
            self.selectInComboBox("None", self.form.face)
            self.selectInComboBox(featName, self.form.edge)
            self.form.invertDirection.show()
            self.form.invertDirection.setEnabled(True)
        # print(f"Setting to {modelName}:{featName}")
        pass

    def _populateModel(self):
        cbox = self.form.model
        cbox.blockSignals(True)
        cbox.clear()
        models = self.obj.Proxy.job.Model.Group
        for mdl in models:
            cbox.addItem(mdl.Label, mdl.Name)
        cbox.blockSignals(False)
        if len(models) == 1:
            self._populateFeatures()

    def _populateFeatures(self):
        mName = str(self.form.model.currentData())
        mdl = FreeCAD.ActiveDocument.getObject(mName)
        # Populate faces
        cbox = self.form.face
        cbox.blockSignals(True)
        cbox.clear()
        cbox.addItem("None")
        for i in range(1, len(mdl.Shape.Faces) + 1):
            cbox.addItem("Face" + str(i))
        cbox.blockSignals(False)
        # Populate edges
        cbox = self.form.edge
        cbox.blockSignals(True)
        cbox.clear()
        cbox.addItem("None")
        for i in range(1, len(mdl.Shape.Edges) + 1):
            cbox.addItem("Edge" + str(i))
        cbox.blockSignals(False)

    def _updateFace(self):
        self._showFaceSelection()
        self.selectInComboBox("None", self.form.edge)
        modelName, featName = self._getModelAndFeatureNames()
        self._setRotationsAttr(modelName, featName)
        self.form.invertDirection.setEnabled(False)
        self.form.invertDirection.hide()

    def _updateEdge(self):
        self._showEdgeSelection()
        self.selectInComboBox("None", self.form.face)
        modelName, featName = self._getModelAndFeatureNames()
        self._setRotationsAttr(modelName, featName)
        self.form.invertDirection.show()
        self.form.invertDirection.setEnabled(True)

    def _invertAlignment(self):
        modelName, featName = self._getModelAndFeatureNames()
        if featName == "None":
            return
        self._setRotationsAttr(modelName, featName)

    def _showEdgeSelection(self):
        mName = str(self.form.model.currentData())
        mdl = FreeCAD.ActiveDocument.getObject(mName)
        eName = str(self.form.edge.currentText())
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(mdl, (eName))

    def _showFaceSelection(self):
        mName = str(self.form.model.currentData())
        mdl = FreeCAD.ActiveDocument.getObject(mName)
        fName = str(self.form.face.currentText())
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(mdl, (fName))


Command = PathShapeGui.SetupOperation(
    "TargetShape",
    TargetShape.Create,
    TaskPanelOpPage,
    "Path_Simulator",
    QtCore.QT_TRANSLATE_NOOP("TargetShape", "Build Shape"),
    QtCore.QT_TRANSLATE_NOOP("TargetShape", "Build target shape."),
    TargetShape.SetupProperties,
)
