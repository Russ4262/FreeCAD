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
import Path.Log as PathLog
import Ops.PathOp2 as PathOp2
import Taskpanels.PathTaskPanelPage as PathTaskPanelPage

from PySide import QtCore, QtGui


__title__ = "Path UI Task Panel Pages base classes"
__author__ = "sliptonic (Brad Collette)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Base classes for UI features within Path operations"


translate = PathTaskPanelPage.translate


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


class TaskPanelIndexRotationPage(PathTaskPanelPage.TaskPanelPage):
    """Page controller for the index rotation."""

    DataObject = QtCore.Qt.ItemDataRole.UserRole
    DataObjectSub = QtCore.Qt.ItemDataRole.UserRole + 1

    def __init__(self, obj, features):
        super(TaskPanelIndexRotationPage, self).__init__(obj, features)

        self.OpIcon = ":/icons/Path_BaseGeometry.svg"
        self.setIcon(self.OpIcon)

    def getForm(self):
        # panel = FreeCADGui.PySideUic.loadUi(":/panels/PageBaseGeometryEdit.ui")
        panel = FreeCADGui.PySideUic.loadUi(
            FreeCAD.getUserAppDataDir()
            + "Mod\\PathExp\\GuiSupport\\PageIndexRotationGeometryEdit.ui"
        )
        self.form.deleteBase.hide()

        self.modifyPanel(panel)
        return panel

    def modifyPanel(self, panel):
        """modifyPanel(self, panel) ...
        Helper method to modify the current form immediately after
        it is loaded."""
        # Determine if Job operations are available with Base Geometry
        availableOps = list()
        ops = self.job.Operations.Group
        for op in ops:
            if hasattr(op, "Base") and isinstance(op.Base, list):
                if len(op.Base) > 0:
                    availableOps.append(op.Label)

        # Load available operations into combobox
        if len(availableOps) > 0:
            # Populate the operations list
            panel.geometryImportList.blockSignals(True)
            panel.geometryImportList.clear()
            availableOps.sort()
            for opLbl in availableOps:
                panel.geometryImportList.addItem(opLbl)
            panel.geometryImportList.blockSignals(False)
        else:
            panel.geometryImportList.hide()
            panel.geometryImportButton.hide()

    def initPage(self, obj):
        self.title = "Index Rotation Geometry"

    def getTitle(self, obj):
        return translate("PathOp2", "Index Rotation Geometry")

    def getFields(self, obj):
        if self.form.modelOnly.isChecked() != obj.ModelOnly:
            obj.ModelOnly = self.form.modelOnly.isChecked()

    def setFields(self, obj):
        self.form.modelOnly.setChecked(obj.ModelOnly)
        self.form.baseList.blockSignals(True)
        self.form.baseList.clear()
        for base in self.obj.Index:
            for sub in base[1]:
                item = QtGui.QListWidgetItem("%s.%s" % (base[0].Label, sub))
                item.setData(self.DataObject, base[0])
                item.setData(self.DataObjectSub, sub)
                self.form.baseList.addItem(item)
        self.form.baseList.blockSignals(False)

    def getSignalsForUpdate(self, obj):
        """getSignalsForUpdate(obj) ... return list of signals for updating obj"""
        signals = []
        signals.append(self.form.modelOnly.stateChanged)
        return signals

    def itemActivated(self):
        FreeCADGui.Selection.clearSelection()
        for item in self.form.baseList.selectedItems():
            obj = item.data(self.DataObject)
            sub = item.data(self.DataObjectSub)
            if sub:
                FreeCADGui.Selection.addSelection(obj, sub)
            else:
                FreeCADGui.Selection.addSelection(obj)

    def supportsEdges(self):
        # return self.features & PathOp2.FeatureBaseEdges
        return True

    def supportsFaces(self):
        # return self.features & PathOp2.FeatureBaseFaces
        return True

    def featureName(self):
        if self.supportsEdges() and self.supportsFaces():
            return "features"
        if self.supportsFaces():
            return "faces"
        if self.supportsEdges():
            return "edges"
        return "nothing"

    def selectionSupportedAsBaseGeometry(self, selection, ignoreErrors):
        if len(selection) != 1:
            if not ignoreErrors:
                msg = translate(
                    "PathProject",
                    "Please select %s from a single solid" % self.featureName(),
                )
                FreeCAD.Console.PrintError(msg + "\n")
                PathLog.debug(msg)
            return False
        sel = selection[0]
        if sel.HasSubObjects:
            if selection[0].SubObjects[0].ShapeType == "Vertex":
                if not ignoreErrors:
                    PathLog.error(
                        translate("PathProject", "Vertexes are not supported")
                    )
                return False
            if (
                not self.supportsEdges()
                and selection[0].SubObjects[0].ShapeType == "Edge"
            ):
                if not ignoreErrors:
                    PathLog.error(translate("PathProject", "Edges are not supported"))
                return False
            if (
                not self.supportsFaces()
                and selection[0].SubObjects[0].ShapeType == "Face"
            ):
                if not ignoreErrors:
                    PathLog.error(translate("PathProject", "Faces are not supported"))
                return False
        else:
            if not ignoreErrors:
                PathLog.error(
                    translate(
                        "PathProject",
                        "Please select %s of a solid" % self.featureName(),
                    )
                )
            return False
        return True

    def setIndexGeometry(self, selection):
        PathLog.track(selection)
        if self.selectionSupportedAsBaseGeometry(selection, False):
            sel = selection[0]
            # Only use first sub feature in list
            sub = sel.SubElementNames[0]
            self.obj.Index = []  # Clear Base
            self.obj.Proxy.addBase(self.obj, sel.Object, sub)
            return True

        return False

    def setBase(self):
        PathLog.track()
        if self.setIndexGeometry(FreeCADGui.Selection.getSelectionEx()):
            # self.obj.Proxy.execute(self.obj)
            self.setFields(self.obj)
            self.setDirty()
            self.updatePanelVisibility("Operation", self.obj)

    def updateBase(self):
        newlist = []
        for i in range(self.form.baseList.count()):
            item = self.form.baseList.item(i)
            obj = item.data(self.DataObject)
            sub = item.data(self.DataObjectSub)
            if sub:
                base = (obj, str(sub))
                newlist.append(base)
        PathLog.debug("Setting new base: %s -> %s" % (self.obj.Index, newlist))
        self.obj.Index = newlist

    def clearBase(self):
        self.obj.Index = []
        self.setDirty()
        self.updatePanelVisibility("Operation", self.obj)

    def importBaseGeometry(self):
        opLabel = str(self.form.geometryImportList.currentText())
        ops = FreeCAD.ActiveDocument.getObjectsByLabel(opLabel)
        if len(ops) > 1:
            msg = translate("PathOpGui", "Mulitiple operations are labeled as")
            msg += " {}\n".format(opLabel)
            FreeCAD.Console.PrintWarning(msg)
        (base, subList) = ops[0].Base[0]
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(base, subList)
        self.setBase()

    def registerSignalHandlers(self, obj):
        self.form.baseList.itemSelectionChanged.connect(self.itemActivated)
        self.form.addBase.clicked.connect(self.setBase)
        self.form.clearBase.clicked.connect(self.clearBase)
        self.form.geometryImportButton.clicked.connect(self.importBaseGeometry)

    def pageUpdateData(self, obj, prop):
        if prop in ["Base"]:
            self.setFields(obj)

    def updateSelection(self, obj, sel):
        if self.selectionSupportedAsBaseGeometry(sel, True):
            self.form.addBase.setEnabled(True)
        else:
            self.form.addBase.setEnabled(False)


FreeCAD.Console.PrintLog("Loading PathTaskPanelBaseGeometryPage... done\n")
