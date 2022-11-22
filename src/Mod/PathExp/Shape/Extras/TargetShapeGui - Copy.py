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
import Path.Base.Gui.Util as PathGui
import Part

from PySide import QtCore


class TaskPanelOpPage(PathTaskPanelPage.TaskPanelPage):
    def initPage(self, obj):
        # self.depthAllowance = PathGui.QuantitySpinBox(
        #    self.form.depthAllowance, obj, "DepthAllowance"
        # )
        self._populateModel()
        self.rotations = None

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
        return signals

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
        print(f"setFields() Applying Yaw-Pitch-Roll: {self.rotations}")
        _alignModel(self.rotations, modelName, self.obj.Proxy.job)

    def getFields(self, obj):
        """getFields(obj) ... Transfer values from UI to obj's properties.
        Called with OK or Apply button activation."""
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
        # self.depthAllowance.updateProperty()

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

    def pagePreCleanup(self):
        """pagePreCleanup() called upon accept or reject of task panel"""
        FreeCAD.Console.PrintMessage(
            "pagePreCleanup() Reseting each model's rotation.\n"
        )
        self._resetModelStockRotation()

    def pagePreApply(self):
        """pagePreApply() called upon apply button of task panel, before recompute, after getFields"""
        pass

    def pagePostApply(self):
        """pagePostApply() called upon Apply button of task panel, after recompute"""
        # Return stock to current working rotations for task panel
        r = TargetShape.rotationsToVector(self.rotations)
        print(f"pagePostApply() Applying Yaw-Pitch-Roll: {r}")
        modelName = str(self.form.model.currentData())
        model = FreeCAD.ActiveDocument.getObject(modelName)
        model.Placement.Rotation.setYawPitchRoll(r.z, r.y, r.x)
        # self.obj.Proxy.job.Stock.Placement.Rotation.setYawPitchRoll(r.z, r.y, r.x)
        print("pagePostApply() Stock.purgeTouched()")
        self.obj.Proxy.job.Stock.purgeTouched()

    def previewTargetShape(self):
        self._removePreviewType("preview")

        if self.form.previewTargetShape.isChecked():
            label = "preview"
            shp = self.obj.Shape
            # indexedShp = _applyShapeRotation(shp, self.obj.Proxy.rotationsToApply)
            # ds = PreviewShape.PreviewShape(indexedShp)
            ds = PreviewShape.PreviewShape(shp)
            self.parent.switch.addChild(ds.root)
            self.targetShapeList.append((self.title, label, ds))
        else:
            # Clear all visuals from screen
            self._removePreviewType("preview")
            self._removePreviewType("rotation_reference")

    # Helper methods
    def _resetModelStockRotation(self):
        # Reset each model to original rotation
        print(
            f"_resetModelStockRotation() Applying Yaw-Pitch-Roll: {FreeCAD.Vector(0.0, 0.0, 0.0)}"
        )
        for m in self.obj.Proxy.job.Model.Group:
            m.Placement.Rotation.setYawPitchRoll(0.0, 0.0, 0.0)
        self.obj.Proxy.job.Stock.Placement.Rotation.setYawPitchRoll(0.0, 0.0, 0.0)

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
            FreeCAD.Console.PrintWarning("Only select one edge.\n")
            return
        subCnt = len(sel[0].SubObjects)
        if subCnt != 1 and subCnt != 0:
            FreeCAD.Console.PrintWarning("Only select one edge.\n")
            return

        # subShp = sel[0].SubObjects[0]
        modelName = sel[0].Object.Name
        featName = sel[0].SubElementNames[0]
        self._setModelAndEdge(modelName, featName)
        self._setRotationsAttr(modelName, featName)
        # self._showRotationReference()
        _alignModel(self.rotations, modelName, self.obj.Proxy.job)

    def _setRotationsAttr(self, modelName, featName):
        self._resetModelStockRotation()
        rotations, isPlanar = TargetShape._getRotationsToApplyFull(
            modelName, featName, self.form.invertDirection.isChecked()
        )
        if not isPlanar:
            FreeCAD.Console.PrintWarning("Selection must be planar.\n")
            return
        # print(f"feature rotations: {rotations}")
        self.rotations = rotations

    def _getModelAndFeatureNames(self):
        modelName = str(self.form.model.currentData())
        edgeName = str(self.form.edge.currentText())
        faceName = str(self.form.face.currentText())
        if edgeName == "None":
            return modelName, faceName
        return modelName, edgeName

    def _setModelAndEdge(self, modelName, featName):
        """_setModelAndEdge()"""
        # Set model
        self.selectInComboBox(modelName, self.form.model)
        self._populateFeatures()

        if featName.startswith("Face"):
            # Set Face
            self.selectInComboBox("None", self.form.edge)
            self.selectInComboBox(featName, self.form.face)
            print(f"Setting to {modelName}:{featName}")
        else:
            # Set edge
            self.selectInComboBox("None", self.form.face)
            self.selectInComboBox(featName, self.form.edge)
            print(f"Setting to {modelName}:{featName}")

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
        _alignModel(self.rotations, modelName, self.obj.Proxy.job)

    def _updateEdge(self):
        self._showEdgeSelection()
        self.selectInComboBox("None", self.form.face)
        modelName, featName = self._getModelAndFeatureNames()
        self._setRotationsAttr(modelName, featName)
        _alignModel(self.rotations, modelName, self.obj.Proxy.job)

    def _invertAlignment(self):
        modelName, featName = self._getModelAndFeatureNames()
        self._setRotationsAttr(modelName, featName)
        _alignModel(self.rotations, modelName, self.obj.Proxy.job)

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

    '''def _showRotationReference(self):
        self._removePreviewType("rotation_reference")
        label = "rotation_reference"
        direction, start = self._getArrowDirectionAndStart()
        arrowShape = _makeArrowShape(direction, start)
        ds = PreviewShape.PreviewShape(arrowShape)
        self.parent.switch.addChild(ds.root)
        self.targetShapeList.append((self.title, label, ds))

    def _getArrowDirectionAndStart(self):
        """_getArrowDirectionAndStart()"""
        modelName, featName = self._getModelAndFeatureNames()
        model = FreeCAD.ActiveDocument.getObject(modelName)
        subShp = model.Shape.getElement(featName)

        if featName.startswith("Face"):
            direction = subShp.normalAt(0.0, 0.0)
            start = subShp.CenterOfMass
            print(f"Setting to {modelName}:{featName}")
        else:
            direction = _getRotationDirection(subShp)
            start = subShp.valueAt(subShp.FirstParameter)
            print(f"Setting to {modelName}:{featName}")

        if self.form.invertDirection.isChecked():
            direction.multiply(-1.0)

        return direction, start'''


# Helper functions
def _alignModel(rotationsList, modelName, job):
    r = TargetShape.rotationsToVector(rotationsList)
    print(f"_alignModel() Applying Yaw-Pitch-Roll: {r}")
    FreeCAD.ActiveDocument.getObject(modelName).Placement.Rotation.setYawPitchRoll(
        r.z, r.y, r.x
    )
    job.Stock.Placement.Rotation.setYawPitchRoll(r.z, r.y, r.x)


def _applyShapeRotation(shape, rotations):
    # vector values are negative to restore the shape to correspond with original model orientation
    rot_vects = {
        "X": FreeCAD.Vector(-1.0, 0.0, 0.0),
        "Y": FreeCAD.Vector(0.0, -1.0, 0.0),
        "Z": FreeCAD.Vector(0.0, 0.0, -1.0),
    }

    rotated = shape.copy()
    for rot_vect, angle in rotations:
        rotated.rotate(FreeCAD.Vector(0.0, 0.0, 0.0), rot_vects[rot_vect], angle)
    return rotated


def _getRotationDirection(edge):
    # Part.show(edge, "ReferenceEdge")
    p0 = edge.valueAt(edge.FirstParameter)
    p1 = edge.valueAt(edge.LastParameter)
    return p1.sub(p0).normalize()


def _makeArrowShape(direction, start):
    """_makeArrowShape(direction, start)... Create arrow shape with midpoint at start point"""
    size = 20.0
    length = 100.0
    shaftPnt = FreeCAD.Vector(0.0, 0.0, 0.0)
    shaft = Part.makeCylinder(size / 8.0, length, shaftPnt, direction, 360.0)
    tipPnt = direction.add(shaftPnt).multiply(length)
    tip = Part.makeCone(size / 2.0, 0.0, size, tipPnt, direction, 360.0)
    arrow = shaft.fuse(tip)
    midPnt = FreeCAD.Vector(direction.x, direction.y, direction.z).multiply(
        (size + length) * -0.5
    )
    arrow.translate(midPnt)
    arrow.translate(start)
    # Part.show(arrow, "Arrow")
    return arrow


Command = PathShapeGui.SetupOperation(
    "TargetShape",
    TargetShape.Create,
    TaskPanelOpPage,
    "Path_Simulator",
    QtCore.QT_TRANSLATE_NOOP("TargetShape", "Build Shape"),
    QtCore.QT_TRANSLATE_NOOP("TargetShape", "Build target shape."),
    TargetShape.SetupProperties,
)
