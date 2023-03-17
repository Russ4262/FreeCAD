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
import Shape.RestShape as RestShape

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

    def getForm(self):
        """getForm() ... return UI"""
        uiFilePath = (
            FreeCAD.getUserAppDataDir()
            + "Mod\\PathExp\\GuiSupport\\PageRestShapeEdit.ui"
        )
        form = FreeCADGui.PySideUic.loadUi(uiFilePath)
        return form

    def setFields(self, obj):
        """setFields(obj) ... Transfers obj's property values to UI."""
        self.selectInComboBox(obj.Model, self.form.model)
        self.form.removeSplitters.setChecked(obj.RemoveSplitters)

    def getFields(self, obj):
        """getFields(obj) ... Transfer values from UI to obj's properties.
        Called with OK or Apply button activation."""
        # print("getFields()")
        if str(self.form.model.currentData()) != obj.Model:
            obj.Model = str(self.form.model.currentData())

        if self.form.removeSplitters.isChecked() != obj.RemoveSplitters:
            obj.RemoveSplitters = self.form.removeSplitters.isChecked()

    def updateQuantitySpinBoxes(self, index=None):
        # self.depthAllowance.updateSpinBox()
        pass

    def registerSignalHandlers(self, obj):
        """registerSignalHandlers(obj) ... overwrite to register custom signal handlers.
        In case an update of a model is not the desired operation of a signal invocation
        (see getSignalsForUpdate(obj)) this function can be used to register signal handlers
        manually."""
        self.form.previewTargetShape.clicked.connect(self.previewTargetShape)

    def getSignalsForUpdate(self, obj):
        """getSignalsForUpdate(obj) ... return list of signals for updating obj"""
        signals = []
        signals.append(self.form.model.currentIndexChanged)
        signals.append(self.form.removeSplitters.stateChanged)
        return signals

    # Helper methods
    def previewTargetShape(self):
        self._removePreviewType("preview")

        if self.form.previewTargetShape.isChecked():
            label = "preview"
            # shp = self.obj.Shape
            negRotations = [(a, -1.0 * d) for a, d in self.rotations]
            negRotations.reverse()

            shp = RestShape.AlignToFeature.rotateShapeWithList(
                self.obj.Shape, negRotations
            )
            ds = PreviewShape.PreviewShape(shp, color=(1.0, 0.5, 0.0), transparency=0.4)
            self.parent.switch.addChild(ds.root)
            self.targetShapeList.append((self.title, label, ds))
        else:
            # Clear all visuals from screen
            self._removePreviewType("preview")
            self._removePreviewType("rotation_reference")

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

    def _populateModel(self):
        cbox = self.form.model
        cbox.blockSignals(True)
        cbox.clear()
        models = [
            op
            for op in self.obj.Proxy.job.Operations.Group
            if op.Name != self.obj.Name and not op.Name.startswith("RestShape")
        ]
        cbox.addItem("None", "None")
        if len(models) > 0:
            for mdl in models:
                cbox.addItem(mdl.Label, mdl.Name)
        cbox.blockSignals(False)


Command = PathShapeGui.SetupOperation(
    "RestShape",
    RestShape.Create,
    TaskPanelOpPage,
    "Path_Simulator",
    QtCore.QT_TRANSLATE_NOOP("RestShape", "Make Rest Shape"),
    QtCore.QT_TRANSLATE_NOOP("RestShape", "Make rest shape."),
    RestShape.SetupProperties,
)
