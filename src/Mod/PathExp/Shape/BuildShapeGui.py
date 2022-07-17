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
import Shape.BuildShape as BuildShape
import OpsGui.PathOpGui2 as PathShapeGui
import GuiSupport.PreviewShape as PreviewShape
import Taskpanels.PathTaskPanelPage as PathTaskPanelPage
import PathScripts.PathGui as PathGui

from PySide import QtCore


class TaskPanelOpPage(PathTaskPanelPage.TaskPanelPage):
    def initPage(self, obj):
        self.previewVisible = False
        self.depthAllowance = PathGui.QuantitySpinBox(
            self.form.depthAllowance, obj, "DepthAllowance"
        )

    def getForm(self):
        """getForm() ... return UI"""
        uiFilePath = (
            FreeCAD.getUserAppDataDir()
            + "Mod\\PathExp\\GuiSupport\\PageBuildShapeEdit.ui"
        )
        form = FreeCADGui.PySideUic.loadUi(uiFilePath)
        form.depthAllowance.setEnabled(False)
        form.depthAllowance_label.setEnabled(False)
        return form

    def getSignalsForUpdate(self, obj):
        """getSignalsForUpdate(obj) ... return list of signals for updating obj"""
        signals = []
        signals.append(self.form.toolController.currentIndexChanged)
        signals.append(self.form.respectFeatureHoles.stateChanged)
        signals.append(self.form.respectMergedHoles.stateChanged)
        signals.append(self.form.depthAllowance.editingFinished)
        return signals

    def setFields(self, obj):
        self.setupToolController(obj, self.form.toolController)
        self.form.respectFeatureHoles.setChecked(obj.RespectFeatureHoles)
        self.form.respectMergedHoles.setChecked(obj.RespectMergedHoles)
        self.updateQuantitySpinBoxes()

    def getFields(self, obj):
        self.updateToolController(obj, self.form.toolController)
        if self.form.respectFeatureHoles.isChecked() != obj.RespectFeatureHoles:
            obj.RespectFeatureHoles = self.form.respectFeatureHoles.isChecked()
        if self.form.respectMergedHoles.isChecked() != obj.RespectMergedHoles:
            obj.RespectMergedHoles = self.form.respectMergedHoles.isChecked()
        self.depthAllowance.updateProperty()

    def updateQuantitySpinBoxes(self, index=None):
        self.depthAllowance.updateSpinBox()

    def registerSignalHandlers(self, obj):
        """registerSignalHandlers(obj) ... overwrite to register custom signal handlers.
        In case an update of a model is not the desired operation of a signal invocation
        (see getSignalsForUpdate(obj)) this function can be used to register signal handlers
        manually."""
        self.form.previewTargetShape.clicked.connect(self.previewTargetShape)

    def previewTargetShape(self):
        if self.targetShapeList:
            # Clear target shape list
            for (__, __, ds) in self.targetShapeList:
                self.parent.switch.removeChild(ds.root)
            self.targetShapeList = []

        if not self.previewVisible:
            print("Stop button pressed")
            shp = self.obj.Shape.copy()
            label = "shape"
            shp.translate(
                FreeCAD.Vector(0.0, 0.0, self.obj.FinalDepth.Value - shp.BoundBox.ZMin)
            )
            ds = PreviewShape.PreviewShape(shp)
            self.parent.switch.addChild(ds.root)
            self.targetShapeList.append((self.title, label, ds))
            self.form.previewTargetShape.setChecked(True)
            self.previewVisible = True
        else:
            self.form.previewTargetShape.setChecked(False)
            self.previewVisible = False


Command = PathShapeGui.SetupOperation(
    "BuildShape",
    BuildShape.Create,
    TaskPanelOpPage,
    "Path_Simulator",
    QtCore.QT_TRANSLATE_NOOP("BuildShape", "Build Shape"),
    QtCore.QT_TRANSLATE_NOOP("BuildShape", "Build target shape."),
    BuildShape.SetupProperties,
)
