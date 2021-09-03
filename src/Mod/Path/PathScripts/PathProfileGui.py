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
import PathScripts.PathOpGui as PathOpGui
import PathScripts.PathProfile as PathProfile

from PySide import QtCore, QtGui


__title__ = "Path Profile Operation UI"
__author__ = "sliptonic (Brad Collette)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Profile operation page controller and command implementation."


FeatureSide       = 0x01
FeatureProcessing = 0x02


def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class TaskPanelOpPage(PathOpGui.TaskPanelGui.TaskPanelPage):
    '''Base class for profile operation page controllers. Two sub features are supported:
        FeatureSide       ... Is the Side property exposed in the UI
        FeatureProcessing ... Are the processing check boxes supported by the operation
    '''

    def initPage(self, obj):
        '''initPage(obj) ... Pseudo-extension of parent constructor class
        used to customize UI for specific model.
        Note that this function is invoked after all page controllers have been created.'''
        self.setTitle("Profile - " + obj.Label)
        self.materialAllowance = PathGui.QuantitySpinBox(self.form.materialAllowance, obj, 'MaterialAllowance')

    def profileFeatures(self):
        '''profileFeatures() ... return which of the optional profile features are supported.
        Currently two features are supported and returned:
            FeatureSide       ... Is the Side property exposed in the UI
            FeatureProcessing ... Are the processing check boxes supported by the operation
        .'''
        return FeatureSide | FeatureProcessing

    def getForm(self):
        '''getForm() ... returns UI customized according to profileFeatures()'''
        return FreeCADGui.PySideUic.loadUi(":/panels/PageOpProfileEdit.ui")

    def getFields(self, obj):
        '''getFields(obj) ... transfers values from UI to obj's proprties'''
        self.updateToolController(obj, self.form.toolController)
        self.updateCoolant(obj, self.form.coolantController)

        if obj.CutSide != str(self.form.cutSide.currentText()):
            obj.CutSide = str(self.form.cutSide.currentText())
        if obj.CutDirection != str(self.form.cutDirection.currentText()):
            obj.CutDirection = str(self.form.cutDirection.currentText())

        # PathGui.updateInputField(obj, 'MaterialAllowance', self.form.materialAllowance)
        self.materialAllowance.updateProperty()

        if obj.UseComp != self.form.useCompensation.isChecked():
            obj.UseComp = self.form.useCompensation.isChecked()
        if obj.UseStartPoint != self.form.useStartPoint.isChecked():
            obj.UseStartPoint = self.form.useStartPoint.isChecked()

        if obj.ProcessHoles != self.form.processHoles.isChecked():
            obj.ProcessHoles = self.form.processHoles.isChecked()
        if obj.ProcessPerimeter != self.form.processPerimeter.isChecked():
            obj.ProcessPerimeter = self.form.processPerimeter.isChecked()
        if obj.ProcessCircles != self.form.processCircles.isChecked():
            obj.ProcessCircles = self.form.processCircles.isChecked()

    def setFields(self, obj):
        '''setFields(obj) ... transfers obj's property values to UI'''
        self.setupToolController(obj, self.form.toolController)
        self.setupCoolant(obj, self.form.coolantController)

        self.selectInComboBox(obj.CutSide, self.form.cutSide)
        self.selectInComboBox(obj.CutDirection, self.form.cutDirection)
        # self.form.materialAllowance.setText(FreeCAD.Units.Quantity(obj.MaterialAllowance.Value, FreeCAD.Units.Length).UserString)
        self.materialAllowance.updateSpinBox()

        self.form.useCompensation.setChecked(obj.UseComp)
        self.form.useStartPoint.setChecked(obj.UseStartPoint)
        self.form.processHoles.setChecked(obj.ProcessHoles)
        self.form.processPerimeter.setChecked(obj.ProcessPerimeter)
        self.form.processCircles.setChecked(obj.ProcessCircles)

    def getSignalsForUpdate(self, obj):
        '''getSignalsForUpdate(obj) ... return list of signals for updating obj'''
        signals = []
        signals.append(self.form.toolController.currentIndexChanged)
        signals.append(self.form.coolantController.currentIndexChanged)
        signals.append(self.form.cutSide.currentIndexChanged)
        signals.append(self.form.cutDirection.currentIndexChanged)
        signals.append(self.form.materialAllowance.editingFinished)
        signals.append(self.form.useCompensation.stateChanged)
        signals.append(self.form.useStartPoint.stateChanged)
        signals.append(self.form.processHoles.stateChanged)
        signals.append(self.form.processPerimeter.stateChanged)
        signals.append(self.form.processCircles.stateChanged)

        return signals

    def registerSignalHandlers(self, obj):
        '''registerSignalHandlers(obj) ... overwrite to register custom signal handlers.
        In case an update of a model is not the desired operation of a signal invocation
        (see getSignalsForUpdate(obj)) this function can be used to register signal handlers
        manually.'''
        # pylint: disable=unused-argument
        self.form.visualizeButton.clicked.connect(self.previewWorkingShape)

    # Method for previewing working shapes
    def previewWorkingShape(self):
        # FreeCAD.Console.PrintMessage("previewWorkingShape()\n")
        workingShapes = self.workingShapeList
        if workingShapes:
            for (__, __, ds) in workingShapes:
                self.parent.switch.removeChild(ds.root)

        if self.form.visualizeButton.isChecked():
            shapes = self.obj.Proxy.shapeIdentification(self.obj, isPreview=True)
            cnt = 0
            for (shp, __, detail) in shapes:
                cnt += 1
                label = "shape_{}".format(cnt)
                if detail == 'pathProfile':
                    shp.translate(FreeCAD.Vector(0.0, 0.0, self.obj.FinalDepth.Value - shp.BoundBox.ZMin))
                    ds = PathGui.PreviewShape(shp)
                    self.parent.switch.addChild(ds.root)
                    workingShapes.append((self.title, label, ds))
                elif detail == 'OpenEdge':
                    for edg in shp:
                        edg.translate(FreeCAD.Vector(0.0, 0.0, self.obj.FinalDepth.Value - edg.BoundBox.ZMin))
                        extent = self.obj.StartDepth.Value - self.obj.FinalDepth.Value
                        shape = edg.extrude(FreeCAD.Vector(0.0, 0.0, extent))
                        ds = PathGui.PreviewShape(shape)
                        self.parent.switch.addChild(ds.root)
                        workingShapes.append((self.title, label, ds))
# Eclass


Command = PathOpGui.SetupOperation('Profile',
        PathProfile.Create,
        TaskPanelOpPage,
        'Path_Contour',
        QtCore.QT_TRANSLATE_NOOP("Path_Profile", "Profile"),
        QtCore.QT_TRANSLATE_NOOP("Path_Profile", "Profile entire model, selected face(s) or selected edge(s)"),
        PathProfile.SetupProperties)

FreeCAD.Console.PrintLog("Loading PathProfileFacesGui... done\n")
