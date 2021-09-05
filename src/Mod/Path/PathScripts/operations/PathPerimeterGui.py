# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2017 sliptonic <shopinthewoods@gmail.com>               *
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
import PathScripts.PathGui as PathGui
import PathScripts.operations.PathOpGui2 as PathOpGui
import PathScripts.operations.PathPerimeter as PathPerimeter
import PathScripts.taskpanels.PathTaskPanelPage as PathTaskPanelPage
import PathScripts.PathLog as PathLog

from PySide import QtCore


__title__ = "Path Profile Operation UI"
__author__ = "sliptonic (Brad Collette)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Profile operation page controller and command implementation."


FeatureSide = 0x01
FeatureProcessing = 0x02

PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class TaskPanelOpPage(PathTaskPanelPage.TaskPanelPage):
    """Base class for profile operation page controllers. Two sub features are supported:
    FeatureSide       ... Is the Side property exposed in the UI
    FeatureProcessing ... Are the processing check boxes supported by the operation
    """

    def initPage(self, obj):
        """initPage(obj) ... Pseudo-extension of parent constructor class
        used to customize UI for specific model.
        Note that this function is invoked after all page controllers have been created."""
        self.setTitle("Profile - " + obj.Label)
        self.materialAllowance = PathGui.QuantitySpinBox(
            self.form.materialAllowance, obj, "MaterialAllowance"
        )
        # print("PathPerimeterGui.initPage")
        # print("PathPerimeterGui.initPage() printing DepthParams")
        # obj.Proxy.printDepthParams(obj)

    def getForm(self):
        """getForm() ... returns UI form"""
        return FreeCADGui.PySideUic.loadUi(":/panels/PageOpPerimeterEdit.ui")

    def getFields(self, obj):
        """getFields(obj) ... transfers values from UI to obj's proprties"""
        if obj.Label != self.form.objectLabel.text():
            obj.Label != self.form.objectLabel.text()

        self.updateToolController(obj, self.form.toolController)
        self.updateCoolant(obj, self.form.coolantController)

        self.updateTargetShape(obj, self.form.targetShape)

        if obj.CutSide != str(self.form.cutSide.currentText()):
            obj.CutSide = str(self.form.cutSide.currentText())

        if obj.CutDirection != str(self.form.cutDirection.currentText()):
            obj.CutDirection = str(self.form.cutDirection.currentText())

        self.materialAllowance.updateProperty()

        if obj.UseComp != self.form.useCompensation.isChecked():
            obj.UseComp = self.form.useCompensation.isChecked()

        if obj.UseStartPoint != self.form.useStartPoint.isChecked():
            obj.UseStartPoint = self.form.useStartPoint.isChecked()

        if obj.ProcessInternalFeatures != self.form.processInternalFeatures.isChecked():
            obj.ProcessInternalFeatures = self.form.processInternalFeatures.isChecked()

        # if obj.UseBasesOnly != self.form.useBasesOnly.isChecked():
        #    obj.UseBasesOnly = self.form.useBasesOnly.isChecked()

        # if obj.ProcessPerimeter != self.form.processPerimeter.isChecked():
        #    obj.ProcessPerimeter = self.form.processPerimeter.isChecked()

        # if obj.ProcessHoles != self.form.processHoles.isChecked():
        #    obj.ProcessHoles = self.form.processHoles.isChecked()

        # if obj.ProcessCircles != self.form.processCircles.isChecked():
        #    obj.ProcessCircles = self.form.processCircles.isChecked()

        # if obj.HandleMultipleFeatures != str(
        #    self.form.handleMultipleFeatures.currentText()
        # ):
        #    obj.HandleMultipleFeatures = str(
        #        self.form.handleMultipleFeatures.currentText()
        #    )

        # if obj.BoundaryShape != str(self.form.boundaryShape.currentText()):
        #    obj.BoundaryShape = str(self.form.boundaryShape.currentText())
        # print("PathPerimeterGui.getFields_2")

    def setFields(self, obj):
        """setFields(obj) ... transfers obj's property values to UI"""
        self.form.objectLabel.setText(obj.Label)

        self.setupToolController(obj, self.form.toolController)
        self.setupCoolant(obj, self.form.coolantController)

        self.setupTargetShape(obj, self.form.targetShape)

        self.selectInComboBox(obj.CutSide, self.form.cutSide)
        self.selectInComboBox(obj.CutDirection, self.form.cutDirection)
        self.materialAllowance.updateSpinBox()

        self.form.useCompensation.setChecked(obj.UseComp)
        self.form.useStartPoint.setChecked(obj.UseStartPoint)
        self.form.processInternalFeatures.setChecked(obj.ProcessInternalFeatures)

        # self.form.useBasesOnly.setChecked(obj.UseBasesOnly)
        # self.form.processPerimeter.setChecked(obj.ProcessPerimeter)
        # self.form.processHoles.setChecked(obj.ProcessHoles)
        # self.form.processCircles.setChecked(obj.ProcessCircles)
        # self.selectInComboBox(
        #    obj.HandleMultipleFeatures, self.form.handleMultipleFeatures
        # )
        # self.selectInComboBox(obj.BoundaryShape, self.form.boundaryShape)
        # print("PathPerimeterGui.setFields_3")

    def getSignalsForUpdate(self, obj):
        """getSignalsForUpdate(obj) ... return list of signals for updating obj"""
        signals = []
        signals.append(self.form.toolController.currentIndexChanged)
        signals.append(self.form.coolantController.currentIndexChanged)
        signals.append(self.form.cutSide.currentIndexChanged)
        signals.append(self.form.cutDirection.currentIndexChanged)
        signals.append(self.form.materialAllowance.editingFinished)
        signals.append(self.form.useCompensation.stateChanged)
        signals.append(self.form.useStartPoint.stateChanged)
        signals.append(self.form.processInternalFeatures.stateChanged)

        # signals.append(self.form.useBasesOnly.stateChanged)
        # signals.append(self.form.processPerimeter.stateChanged)
        # signals.append(self.form.processHoles.stateChanged)
        # signals.append(self.form.processCircles.stateChanged)
        # signals.append(self.form.handleMultipleFeatures.currentIndexChanged)
        # signals.append(self.form.boundaryShape.currentIndexChanged)

        return signals

    def registerSignalHandlers(self, obj):
        """registerSignalHandlers(obj) ... overwrite to register custom signal handlers.
        In case an update of a model is not the desired operation of a signal invocation
        (see getSignalsForUpdate(obj)) this function can be used to register signal handlers
        manually."""
        # pylint: disable=unused-argument
        # self.form.visualizeTargetShape.clicked.connect(self.previewTargetShape)
        pass

    # Method for previewing working shapes
    def previewTargetShape(self):
        # FreeCAD.Console.PrintMessage("previewTargetShape()\n")
        targetShapes = self.targetShapeList
        if targetShapes:
            for (__, __, ds) in targetShapes:
                self.parent.switch.removeChild(ds.root)

        if self.form.visualizeTargetShape.isChecked():
            shapes = self.obj.Proxy.getTargetShape(self.obj, isPreview=True)
            cnt = 0
            for (shp, __, detail) in shapes:
                cnt += 1
                label = "shape_{}".format(cnt)
                if detail == "pathProfile":
                    shp.translate(
                        FreeCAD.Vector(
                            0.0, 0.0, self.obj.FinalDepth.Value - shp.BoundBox.ZMin
                        )
                    )
                    ds = PathGui.PreviewShape(shp)
                    self.parent.switch.addChild(ds.root)
                    targetShapes.append((self.title, label, ds))
                elif detail == "OpenEdge":
                    for edg in shp:
                        edg.translate(
                            FreeCAD.Vector(
                                0.0, 0.0, self.obj.FinalDepth.Value - edg.BoundBox.ZMin
                            )
                        )
                        extent = self.obj.StartDepth.Value - self.obj.FinalDepth.Value
                        shape = edg.extrude(FreeCAD.Vector(0.0, 0.0, extent))
                        ds = PathGui.PreviewShape(shape)
                        self.parent.switch.addChild(ds.root)
                        targetShapes.append((self.title, label, ds))

    # TargetShape helper methods
    def setupTargetShape(self, obj, combo):
        """setupTargetShape(obj, combo) ...
        helper function to setup obj's TargetShape options."""
        labels = [
            o.Label
            for o in obj.Proxy.job.TargetShapes.Group + obj.Proxy.job.Operations.Group
            if hasattr(o, "Shape") and o.Name != obj.Name
        ]
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(labels)
        combo.blockSignals(False)

        if obj.TargetShape:
            self.selectInComboBox(obj.TargetShape.Label, combo)

    def updateTargetShape(self, obj, combo):
        """updateTargetShape(obj, combo) ...
        helper function to update obj's Coolant property if a different
        one has been selected in the combo box."""
        option = combo.currentText()
        candidates = [
            c
            for c in obj.Proxy.job.TargetShapes.Group + obj.Proxy.job.Operations.Group
            if hasattr(c, "Shape") and c.Name != obj.Name
        ]
        for c in candidates:
            if c.Label == option:
                if obj.TargetShape != c:
                    obj.TargetShape = c
                break


# Eclass


Command = PathOpGui.SetupOperation(
    "Perimeter",
    PathPerimeter.Create,
    TaskPanelOpPage,
    "Path_Profile2",
    QtCore.QT_TRANSLATE_NOOP("Path_Perimeter", "Perimeter"),
    QtCore.QT_TRANSLATE_NOOP(
        "Path_Perimeter", "Profile entire model, selected face(s) or selected edge(s)"
    ),
    PathPerimeter.SetupProperties,
)

FreeCAD.Console.PrintLog("Loading PathPerimeterGui... done\n")
