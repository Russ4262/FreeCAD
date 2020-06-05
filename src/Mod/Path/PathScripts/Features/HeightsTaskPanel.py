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
import PathScripts.PathGui as PathGui
import PathScripts.PathLog as PathLog
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


class TaskPanelHeightsPage(PathOpGui.TaskPanelPage):
    '''Page controller for heights.'''

    def __init__(self, obj, features):
        super(TaskPanelHeightsPage, self).__init__(obj, features)

        # members initialized later
        self.clearanceHeight = None
        self.safeHeight = None
        self.panelTitle = 'Heights'

    def getForm(self):
        return FreeCADGui.PySideUic.loadUi(":/panels/PageHeightsEdit.ui")

    def initPage(self, obj):
        self.safeHeight = PathGui.QuantitySpinBox(self.form.safeHeight, obj, 'SafeHeight')
        self.clearanceHeight = PathGui.QuantitySpinBox(self.form.clearanceHeight, obj, 'ClearanceHeight')

    def getTitle(self, obj):
        return translate("Path", "Heights")

    def getFields(self, obj):
        self.safeHeight.updateProperty()
        self.clearanceHeight.updateProperty()

    def setFields(self,  obj):
        self.safeHeight.updateSpinBox()
        self.clearanceHeight.updateSpinBox()

    def getSignalsForUpdate(self, obj):
        signals = []
        signals.append(self.form.safeHeight.editingFinished)
        signals.append(self.form.clearanceHeight.editingFinished)
        return signals

    def pageUpdateData(self, obj, prop):
        if prop in ['SafeHeight', 'ClearanceHeight']:
            self.setFields(obj)


FreeCAD.Console.PrintLog("Loading HeightsTaskPanel... done\n")
