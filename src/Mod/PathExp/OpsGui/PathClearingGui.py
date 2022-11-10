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
import Path.Base.Gui.Util as PathGui
import OpsGui.PathOpGui2 as PathOpGui
import Ops.PathClearing as PathClearing
import Taskpanels.PathTaskPanelPage as PathTaskPanelPage

from PySide import QtCore

__title__ = "Path Clearing Operation UI"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Clearing operation page controller and command implementation."


def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class TaskPanelOpPage(PathTaskPanelPage.TaskPanelPage):
    """Page controller class for Clearing operations"""

    def initPage(self, obj):
        """initPage(obj) ... Pseudo-extension of parent constructor class
        used to customize UI for specific model.
        Note that this function is invoked after all page controllers have been created."""
        self.setTitle("Clearing - " + obj.Label)
        self.materialAllowance = PathGui.QuantitySpinBox(
            self.form.materialAllowance, obj, "MaterialAllowance"
        )
        self.cutPatternAngle = PathGui.QuantitySpinBox(
            self.form.cutPatternAngle, obj, "CutPatternAngle"
        )
        self.stepOverPercent = PathGui.QuantitySpinBox(
            self.form.stepOverPercent, obj, "StepOver"
        )
        self.sampleInterval = PathGui.QuantitySpinBox(
            self.form.sampleInterval, obj, "SampleInterval"
        )
        self.linearDeflection = PathGui.QuantitySpinBox(
            self.form.linearDeflection, obj, "LinearDeflection"
        )
        self.angularDeflection = PathGui.QuantitySpinBox(
            self.form.angularDeflection, obj, "AngularDeflection"
        )
        self.depthOffset = PathGui.QuantitySpinBox(
            self.form.depthOffset, obj, "DepthOffset"
        )

    def getForm(self):
        """getForm() ... returns UI"""
        # return FreeCADGui.PySideUic.loadUi(":/panels/PageOpClearingEdit.ui")
        uiFilePath = (
            FreeCAD.getUserAppDataDir()
            + "Mod\\PathExp\\GuiSupport\\PageOpClearingEdit.ui"
        )
        form = FreeCADGui.PySideUic.loadUi(uiFilePath)
        #comboToPropertyMap = [("Side", "Side"), ("OperationType", "OperationType")]
        #enumTups = PathAdaptive.PathAdaptive.propertyEnumerations(dataType="raw")
        #self.populateCombobox(form, enumTups, comboToPropertyMap)
        return form

    def getFields(self, obj):
        """getFields(obj) ... transfers values from UI to obj's proprties"""

        if obj.Label != self.form.objectLabel.text():
            obj.Label != self.form.objectLabel.text()
        # self.updateTargetShape(obj, self.form.targetShape)
        if obj.TargetShape:
            if obj.TargetShape.Name != str(self.form.targetShape.currentData()):
                obj.TargetShape = FreeCAD.ActiveDocument.getObject(
                    str(self.form.targetShape.currentData())
                )
        else:
            obj.TargetShape = FreeCAD.ActiveDocument.getObject(
                str(self.form.targetShape.currentData())
            )

        self.updateToolController(obj, self.form.toolController)
        self.updateCoolant(obj, self.form.coolantController)

        if obj.UseComp != self.form.useCompensation.isChecked():
            obj.UseComp = self.form.useCompensation.isChecked()

        if obj.CutDirection != str(self.form.cutDirection.currentText()):
            obj.CutDirection = str(self.form.cutDirection.currentText())

        self.stepOverPercent.updateProperty()

        if obj.CutPattern != str(self.form.cutPattern.currentText()):
            obj.CutPattern = str(self.form.cutPattern.currentText())

        self.cutPatternAngle.updateProperty()

        self.materialAllowance.updateProperty()

        if obj.CutPatternReversed != self.form.cutPatternReversed.isChecked():
            obj.CutPatternReversed = self.form.cutPatternReversed.isChecked()

        if obj.UseStartPoint != self.form.useStartPoint.isChecked():
            obj.UseStartPoint = self.form.useStartPoint.isChecked()

        if obj.MinTravel != self.form.minTravel.isChecked():
            obj.MinTravel = self.form.minTravel.isChecked()

        if obj.Cut3DPocket != self.form.cut3DPocket.isChecked():
            obj.Cut3DPocket = self.form.cut3DPocket.isChecked()

        if obj.UseOCL != self.form.useOCL.isChecked():
            obj.UseOCL = self.form.useOCL.isChecked()

        if obj.KeepToolDown != self.form.keepToolDown.isChecked():
            obj.KeepToolDown = self.form.keepToolDown.isChecked()

        if obj.CutSide != str(self.form.cutSide.currentText()):
            obj.CutSide = str(self.form.cutSide.currentText())

        # From PathAdaptiveGui
        if obj.OperationType != str(self.form.adaptiveOperationType.currentText()):
            obj.OperationType = str(self.form.adaptiveOperationType.currentText())

        if obj.Tolerance != self.form.accuracyPerformance.value() / 100.0:
            obj.Tolerance = self.form.accuracyPerformance.value() / 100.0

        obj.HelixAngle = self.form.helixRampAngle.value()
        obj.HelixConeAngle = self.form.helixConeAngle.value()
        obj.HelixDiameterLimit = self.form.helixDiameterLimit.value()
        obj.LiftDistance = self.form.liftDistance.value()

        obj.KeepToolDownRatio = self.form.keepToolDownRatio.value()

        if obj.DisableHelixEntry != self.form.disableHelixEntry.isChecked():
            obj.DisableHelixEntry = self.form.disableHelixEntry.isChecked()

        obj.ForceInsideOut = self.form.forceInsideOut.isChecked()
        obj.FinishingProfile = self.form.includeFinishingProfile.isChecked()
        obj.Stopped = self.form.stopButton.isChecked()
        if obj.Stopped:
            self.form.stopButton.setChecked(False)  # reset the button
            obj.StopProcessing = True

        if obj.CutMode != str(self.form.cutMode.currentText()):
            obj.CutMode = str(self.form.cutMode.currentText())

        self.sampleInterval.updateProperty()
        self.linearDeflection.updateProperty()
        self.angularDeflection.updateProperty()
        self.depthOffset.updateProperty()

    def setFields(self, obj):
        """setFields(obj) ... transfers obj's property values to UI"""

        self.form.objectLabel.setText(obj.Label)
        # self.setupTargetShape(obj, self.form.targetShape)
        self._populateTargetShapes(obj)
        self.selectInComboBox(obj.TargetShape.Name, self.form.targetShape)

        self.setupToolController(obj, self.form.toolController)
        self.setupCoolant(obj, self.form.coolantController)

        self.stepOverPercent.updateSpinBox()
        self.materialAllowance.updateSpinBox()
        self.form.useStartPoint.setChecked(obj.UseStartPoint)

        self.cutPatternAngle.updateSpinBox()

        self.form.minTravel.setChecked(obj.MinTravel)
        self.form.useCompensation.setChecked(obj.UseComp)

        self.selectInComboBox(obj.CutDirection, self.form.cutDirection)
        self.selectInComboBox(obj.CutPattern, self.form.cutPattern)
        self.form.cutPatternReversed.setChecked(obj.CutPatternReversed)
        self.form.cut3DPocket.setChecked(obj.Cut3DPocket)
        self.form.useOCL.setChecked(obj.UseOCL)
        self.form.keepToolDown.setChecked(obj.KeepToolDown)

        # From PathAdaptiveGui
        self.selectInComboBox(obj.CutSide, self.form.cutSide)
        self.selectInComboBox(obj.OperationType, self.form.adaptiveOperationType)
        self.form.accuracyPerformance.setValue(int(obj.Tolerance * 100))
        self.form.helixRampAngle.setValue(obj.HelixAngle)
        self.form.helixConeAngle.setValue(obj.HelixConeAngle)
        self.form.helixDiameterLimit.setValue(obj.HelixDiameterLimit)
        self.form.liftDistance.setValue(obj.LiftDistance)
        self.form.keepToolDownRatio.setValue(obj.KeepToolDownRatio)

        self.form.disableHelixEntry.setChecked(obj.DisableHelixEntry)
        self.form.forceInsideOut.setChecked(obj.ForceInsideOut)
        self.form.includeFinishingProfile.setChecked(obj.FinishingProfile)
        self.form.stopButton.setChecked(obj.Stopped)

        self.selectInComboBox(obj.CutMode, self.form.cutMode)
        self.sampleInterval.updateSpinBox()
        self.linearDeflection.updateSpinBox()
        self.angularDeflection.updateSpinBox()
        self.depthOffset.updateSpinBox()

        self._manageOCLOptions()
        self._manageClearingOptions()

    def getSignalsForUpdate(self, obj):
        """getSignalsForUpdate(obj) ... return list of signals for updating obj"""
        signals = []

        signals.append(self.form.toolController.currentIndexChanged)
        signals.append(self.form.coolantController.currentIndexChanged)
        signals.append(self.form.targetShape.currentIndexChanged)
        signals.append(self.form.cutDirection.currentIndexChanged)
        signals.append(self.form.cutPattern.currentIndexChanged)

        signals.append(self.form.stepOverPercent.editingFinished)
        signals.append(self.form.cutPatternAngle.editingFinished)
        signals.append(self.form.materialAllowance.editingFinished)
        signals.append(self.form.useStartPoint.stateChanged)
        signals.append(self.form.cutPatternReversed.stateChanged)

        signals.append(self.form.minTravel.stateChanged)
        signals.append(self.form.cut3DPocket.stateChanged)
        signals.append(self.form.useOCL.stateChanged)

        # Copied from PathAdaptiveGui
        signals.append(self.form.cutSide.currentIndexChanged)
        signals.append(self.form.adaptiveOperationType.currentIndexChanged)
        signals.append(self.form.accuracyPerformance.valueChanged)
        signals.append(self.form.helixRampAngle.valueChanged)
        signals.append(self.form.helixConeAngle.valueChanged)
        signals.append(self.form.helixDiameterLimit.valueChanged)
        signals.append(self.form.liftDistance.valueChanged)
        signals.append(self.form.keepToolDownRatio.valueChanged)

        # signals.append(self.form.ProcessHoles.stateChanged)
        signals.append(self.form.disableHelixEntry.stateChanged)
        signals.append(self.form.forceInsideOut.stateChanged)
        signals.append(self.form.includeFinishingProfile.stateChanged)
        signals.append(self.form.stopButton.toggled)

        signals.append(self.form.cutMode.currentIndexChanged)
        signals.append(self.form.angularDeflection.editingFinished)
        signals.append(self.form.linearDeflection.editingFinished)
        signals.append(self.form.sampleInterval.editingFinished)
        signals.append(self.form.depthOffset.editingFinished)

        return signals

    def registerSignalHandlers(self, obj):
        """registerSignalHandlers(obj) ... overwrite to register custom signal handlers.
        In case an update of a model is not the desired operation of a signal invocation
        (see getSignalsForUpdate(obj)) this function can be used to register signal handlers
        manually."""
        # pylint: disable=unused-argument
        self.form.cutPattern.currentIndexChanged.connect(self._manageClearingOptions)
        self.form.disableHelixEntry.stateChanged.connect(self._helixOptionsVisibility)
        self.form.useOCL.stateChanged.connect(self._manageOCLOptions)
        self.form.cut3DPocket.stateChanged.connect(self._manage3DPocketOptions)

    def _manageOCLOptions(self):
        if self.form.useOCL.isChecked():
            # Disable 3D Pocket
            self.form.cut3DPocket.setChecked(False)
            self.form.oclOptions.setEnabled(True)
            self.form.oclOptions.show()
        else:
            self.form.oclOptions.setEnabled(False)
            self.form.oclOptions.hide()

    def _manage3DPocketOptions(self):
        if self.form.cut3DPocket.isChecked():
            # Disable OCL usage
            self.form.useOCL.setChecked(False)

    def _manageClearingOptions(self):
        pattern = self.form.cutPattern.currentText()
        if pattern == "Adaptive":
            self.form.adaptiveOptions.setEnabled(True)
            self.form.adaptiveOptions.show()
        else:
            self.form.adaptiveOptions.setEnabled(False)
            self.form.adaptiveOptions.hide()

        if pattern in ["Offset", "Spiral", "Adaptive"]:
            self.form.cutPatternAngle.setEnabled(False)
            self.form.cutPatternAngle.hide()
            self.form.cutPatternAngle_label.hide()
        else:
            self.form.cutPatternAngle.setEnabled(True)
            self.form.cutPatternAngle.show()
            self.form.cutPatternAngle_label.show()

        self.form.useCompensation.setEnabled(False)
        self.form.useCompensation.hide()

    def _helixOptionsVisibility(self):
        if self.form.disableHelixEntry.isChecked():
            self.form.helixRampAngle.setEnabled(False)
            self.form.helixConeAngle.setEnabled(False)
            self.form.helixDiameterLimit.setEnabled(False)
        else:
            self.form.helixRampAngle.setEnabled(True)
            self.form.helixConeAngle.setEnabled(True)
            self.form.helixDiameterLimit.setEnabled(True)

    # TargetShape helper methods
    '''
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
    '''


# Eclass


Command = PathOpGui.SetupOperation(
    "Clearing",
    PathClearing.Create,
    TaskPanelOpPage,
    "LinkSub",
    QtCore.QT_TRANSLATE_NOOP("Path_Clearing", "Clearing"),
    QtCore.QT_TRANSLATE_NOOP(
        "Path_Clearing",
        "Creates a Path Clearing operation from edges, wires, faces or solids.",
    ),
    PathClearing.SetupProperties,
)

FreeCAD.Console.PrintLog("Loading PathClearingGui... done\n")
