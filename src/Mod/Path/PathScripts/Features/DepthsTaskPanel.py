# -*- coding: utf-8 -*-

# ***************************************************************************
# *                                                                         *
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
import PathScripts.PathGeom as PathGeom
import PathScripts.PathGui as PathGui
import PathScripts.PathLog as PathLog
import PathScripts.PathOp as PathOp
import PathScripts.PathOpGui as PathOpGui
from PySide import QtCore, QtGui

__title__ = "Path Operation UI base classes"
__author__ = "sliptonic (Brad Collette)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Base classes and framework for Path operation's UI"

LOGLEVEL = False

if LOGLEVEL:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class TaskPanelDepthsPage(PathOpGui.TaskPanelPage):
    '''Page controller for depths.'''

    def __init__(self, obj, features):
        super(TaskPanelDepthsPage, self).__init__(obj, features)

        # members initialized later
        self.startDepth = None
        self.finalDepth = None
        self.finishDepth = None
        self.stepDown = None
        self.panelTitle = 'Depths'

    def getForm(self):
        return FreeCADGui.PySideUic.loadUi(":/panels/PageDepthsEdit.ui")

    def haveStartDepth(self):
        return PathOp.FeatureDepths & self.features

    def haveFinalDepth(self):
        return PathOp.FeatureDepths & self.features and not PathOp.FeatureNoFinalDepth & self.features

    def haveFinishDepth(self):
        return PathOp.FeatureDepths & self.features and PathOp.FeatureFinishDepth & self.features

    def haveStepDown(self):
        return PathOp.FeatureStepDown & self. features

    def initPage(self, obj):

        if self.haveStartDepth():
            self.startDepth = PathGui.QuantitySpinBox(self.form.startDepth, obj, 'StartDepth')
        else:
            self.form.startDepth.hide()
            self.form.startDepthLabel.hide()
            self.form.startDepthSet.hide()

        if self.haveFinalDepth():
            self.finalDepth = PathGui.QuantitySpinBox(self.form.finalDepth, obj, 'FinalDepth')
        else:
            if self.haveStartDepth():
                self.form.finalDepth.setEnabled(False)
                self.form.finalDepth.setToolTip(translate('PathOp', 'FinalDepth cannot be modified for this operation.\nIf it is necessary to set the FinalDepth manually please select a different operation.'))
            else:
                self.form.finalDepth.hide()
                self.form.finalDepthLabel.hide()
            self.form.finalDepthSet.hide()

        if self.haveStepDown():
            self.stepDown = PathGui.QuantitySpinBox(self.form.stepDown, obj, 'StepDown')
        else:
            self.form.stepDown.hide()
            self.form.stepDownLabel.hide()

        if self.haveFinishDepth():
            self.finishDepth = PathGui.QuantitySpinBox(self.form.finishDepth, obj, 'FinishDepth')
        else:
            self.form.finishDepth.hide()
            self.form.finishDepthLabel.hide()

    def getTitle(self, obj):
        return translate("PathOp", "Depths")

    def getFields(self, obj):
        if self.haveStartDepth():
            self.startDepth.updateProperty()
        if self.haveFinalDepth():
            self.finalDepth.updateProperty()
        if self.haveStepDown():
            self.stepDown.updateProperty()
        if self.haveFinishDepth():
            self.finishDepth.updateProperty()

    def setFields(self, obj):
        if self.haveStartDepth():
            self.startDepth.updateSpinBox()
        if self.haveFinalDepth():
            self.finalDepth.updateSpinBox()
        if self.haveStepDown():
            self.stepDown.updateSpinBox()
        if self.haveFinishDepth():
            self.finishDepth.updateSpinBox()
        self.updateSelection(obj, FreeCADGui.Selection.getSelectionEx())

    def getSignalsForUpdate(self, obj):
        signals = []
        if self.haveStartDepth():
            signals.append(self.form.startDepth.editingFinished)
        if self.haveFinalDepth():
            signals.append(self.form.finalDepth.editingFinished)
        if self.haveStepDown():
            signals.append(self.form.stepDown.editingFinished)
        if self.haveFinishDepth():
            signals.append(self.form.finishDepth.editingFinished)
        return signals

    def registerSignalHandlers(self, obj):
        if self.haveStartDepth():
            self.form.startDepthSet.clicked.connect(lambda: self.depthSet(obj, self.startDepth, 'StartDepth'))
        if self.haveFinalDepth():
            self.form.finalDepthSet.clicked.connect(lambda: self.depthSet(obj, self.finalDepth, 'FinalDepth'))

    def pageUpdateData(self, obj, prop):
        if prop in ['StartDepth', 'FinalDepth', 'StepDown', 'FinishDepth']:
            self.setFields(obj)

    def depthSet(self, obj, spinbox, prop):
        z = self.selectionZLevel(FreeCADGui.Selection.getSelectionEx())
        if z is not None:
            PathLog.debug("depthSet(%s, %s, %.2f)" % (obj.Label, prop, z))
            if spinbox.expression():
                obj.setExpression(prop, None)
                self.setDirty()
            spinbox.updateSpinBox(FreeCAD.Units.Quantity(z, FreeCAD.Units.Length))
            if spinbox.updateProperty():
                self.setDirty()
        else:
            PathLog.info("depthSet(-)")

    def selectionZLevel(self, sel):
        if len(sel) == 1 and len(sel[0].SubObjects) == 1:
            sub = sel[0].SubObjects[0]
            if 'Vertex' == sub.ShapeType:
                return sub.Z
            if PathGeom.isHorizontal(sub):
                if 'Edge' == sub.ShapeType:
                    return sub.Vertexes[0].Z
                if 'Face' == sub.ShapeType:
                    return sub.BoundBox.ZMax
        return None

    def updateSelection(self, obj, sel):
        if self.selectionZLevel(sel) is not None:
            self.form.startDepthSet.setEnabled(True)
            self.form.finalDepthSet.setEnabled(True)
        else:
            self.form.startDepthSet.setEnabled(False)
            self.form.finalDepthSet.setEnabled(False)


FreeCAD.Console.PrintLog("Loading DepthsTaskPanel... done\n")
