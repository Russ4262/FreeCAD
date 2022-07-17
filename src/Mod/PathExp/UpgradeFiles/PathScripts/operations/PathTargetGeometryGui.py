# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2021 Russell Johnson (russ4262) <russ4262@gmail.com>    *
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
import PathScripts.operations.PathTargetGeometry as PathTargetGeometry
import PathScripts.taskpanels.PathTaskPanelPage as PathTaskPanelPage

from PySide import QtCore

__title__ = "Path TargetGeometry Operation UI"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "TargetGeometry object page controller and command implementation."


def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class TaskPanelOpPage(PathTaskPanelPage.TaskPanelPage):
    """Page controller class for TargetGeometry object"""

    def initPage(self, obj):
        """initPage(obj) ... Pseudo-extension of parent constructor class
        used to customize UI for specific model.
        Note that this function is invoked after all page controllers have been created."""
        self.setTitle("TargetGeometry - " + obj.Label)
        self.materialAllowance = PathGui.QuantitySpinBox(
            self.form.materialAllowance, obj, "MaterialAllowance"
        )

    def getForm(self):
        """getForm() ... returns UI"""
        return FreeCADGui.PySideUic.loadUi(":/panels/PageOpTargetShapeEdit.ui")

    def getFields(self, obj):
        """getFields(obj) ... transfers values from UI to obj's proprties"""

        if obj.UseBasesOnly != self.form.useBasesOnly.isChecked():
            obj.UseBasesOnly = self.form.useBasesOnly.isChecked()

        if obj.ProcessPerimeter != self.form.processPerimeter.isChecked():
            obj.ProcessPerimeter = self.form.processPerimeter.isChecked()

        if obj.ProcessHoles != self.form.processHoles.isChecked():
            obj.ProcessHoles = self.form.processHoles.isChecked()

        if obj.ProcessCircles != self.form.processCircles.isChecked():
            obj.ProcessCircles = self.form.processCircles.isChecked()

        if obj.ForceFinalDepthLow != self.form.forceFinalDepthLow.isChecked():
            obj.ForceFinalDepthLow = self.form.forceFinalDepthLow.isChecked()

        if obj.HandleMultipleFeatures != str(
            self.form.handleMultipleFeatures.currentText()
        ):
            obj.HandleMultipleFeatures = str(
                self.form.handleMultipleFeatures.currentText()
            )

        if obj.BoundaryShape != str(self.form.boundaryShape.currentText()):
            obj.BoundaryShape = str(self.form.boundaryShape.currentText())

        if obj.ShapeType != str(self.form.shapeType.currentText()):
            obj.ShapeType = str(self.form.shapeType.currentText())

        if obj.AvoidXFeatures != self.form.avoidXFeatures.value():
            obj.AvoidXFeatures = self.form.avoidXFeatures.value()

        self.materialAllowance.updateProperty()

    def setFields(self, obj):
        """setFields(obj) ... transfers obj's property values to UI"""

        self.form.useBasesOnly.setChecked(obj.UseBasesOnly)
        self.form.processPerimeter.setChecked(obj.ProcessPerimeter)
        self.form.processHoles.setChecked(obj.ProcessHoles)
        self.form.processCircles.setChecked(obj.ProcessCircles)
        self.form.forceFinalDepthLow.setChecked(obj.ForceFinalDepthLow)
        self.selectInComboBox(
            obj.HandleMultipleFeatures, self.form.handleMultipleFeatures
        )
        self.selectInComboBox(obj.BoundaryShape, self.form.boundaryShape)
        self.selectInComboBox(obj.ShapeType, self.form.shapeType)
        self.form.avoidXFeatures.setValue(obj.AvoidXFeatures)

        self.materialAllowance.updateSpinBox()

    def getSignalsForUpdate(self, obj):
        """getSignalsForUpdate(obj) ... return list of signals for updating obj"""
        signals = []

        signals.append(self.form.useBasesOnly.stateChanged)
        signals.append(self.form.processPerimeter.stateChanged)
        signals.append(self.form.processHoles.stateChanged)
        signals.append(self.form.processCircles.stateChanged)
        signals.append(self.form.forceFinalDepthLow.stateChanged)
        signals.append(self.form.handleMultipleFeatures.currentIndexChanged)
        signals.append(self.form.boundaryShape.currentIndexChanged)
        signals.append(self.form.shapeType.currentIndexChanged)
        signals.append(self.form.materialAllowance.editingFinished)
        signals.append(self.form.avoidXFeatures.valueChanged)

        return signals

    def registerSignalHandlers(self, obj):
        """registerSignalHandlers(obj) ... overwrite to register custom signal handlers.
        In case an update of a model is not the desired operation of a signal invocation
        (see getSignalsForUpdate(obj)) this function can be used to register signal handlers
        manually."""
        # pylint: disable=unused-argument
        self.form.visualizeTargetShape.clicked.connect(self.previewTargetShape)

    # Method for previewing working shapes
    def previewTargetShape(self):
        targetShapes = self.targetShapeList
        if targetShapes:
            for (__, __, ds) in targetShapes:
                self.parent.switch.removeChild(ds.root)

        if self.form.visualizeTargetShape.isChecked():
            shapes = self.obj.Proxy._buildTargetShape(self.obj, self.obj.ShapeType, isPreview=True)
            cnt = 0
            for (shp, __, __) in shapes:
                cnt += 1
                label = "shape_{}".format(cnt)
                shp.translate(
                    FreeCAD.Vector(
                        0.0, 0.0, self.obj.FinalDepth.Value - shp.BoundBox.ZMin
                    )
                )
                ds = PathGui.PreviewShape(shp)
                self.parent.switch.addChild(ds.root)
                targetShapes.append((self.title, label, ds))


# Eclass


Command = PathOpGui.SetupOperation(
    "TargetGeometry",
    PathTargetGeometry.Create,
    TaskPanelOpPage,
    "Path_OpCopy",
    QtCore.QT_TRANSLATE_NOOP("Path_TargetGeometry", "TargetGeometry"),
    QtCore.QT_TRANSLATE_NOOP(
        "Path_TargetGeometry",
        "Creates a Path TargetGeometry operation from edges, wires, faces or solids.",
    ),
    PathTargetGeometry.SetupProperties,
)

FreeCAD.Console.PrintLog("Loading PathTargetGeometryGui... done\n")
