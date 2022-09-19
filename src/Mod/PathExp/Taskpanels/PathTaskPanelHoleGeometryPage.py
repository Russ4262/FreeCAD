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
import PathGui as PGui  # ensure Path/Gui/Resources are loaded
import Ops.PathOp2 as PathOp2
import PathScripts.PathLog as PathLog
import Taskpanels.PathTaskPanelPage as PathTaskPanelPage
import Taskpanels.PathTaskPanelPage as PathTaskPanelPage

from PySide import QtCore, QtGui

__title__ = "Base for Circular Hole based operations' UI"
__author__ = "sliptonic (Brad Collette)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Implementation of circular hole specific base geometry page controller."

translate = PathTaskPanelPage.translate

LOGLEVEL = False

if LOGLEVEL:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.NOTICE, PathLog.thisModule())


class TaskPanelHoleGeometryPage(PathTaskPanelPage.TaskPanelPage):
    """Page controller for the base geometry."""

    # DataObject = QtCore.Qt.ItemDataRole.UserRole
    # DataObjectSub = QtCore.Qt.ItemDataRole.UserRole + 1

    DataFeatureName = QtCore.Qt.ItemDataRole.UserRole
    DataObject = QtCore.Qt.ItemDataRole.UserRole + 1
    DataObjectSub = QtCore.Qt.ItemDataRole.UserRole + 2

    InitBase = False

    def __init__(self, obj, features):
        # super(TaskPanelBaseGeometryPage, self).__init__(obj, features)
        super(TaskPanelHoleGeometryPage, self).__init__(obj, features)

        self.title = "Hole Geometry"
        self.OpIcon = ":/icons/Path_Drilling.svg"
        self.setIcon(self.OpIcon)

    def getForm_ORIG(self):
        panel = FreeCADGui.PySideUic.loadUi(":/panels/PageBaseGeometryEdit.ui")
        self.modifyPanel(panel)
        return panel

    def getForm(self):
        """getForm() ... load and return page"""
        # return FreeCADGui.PySideUic.loadUi(":/panels/PageBaseHoleGeometryEdit.ui")
        panel = FreeCADGui.PySideUic.loadUi(":/panels/PageBaseHoleGeometryEdit.ui")
        # self.modifyPanel(panel)
        return panel

    def modifyPanel(self, panel):
        """modifyPanel(self, panel) ...
        Helper method to modify the current form immediately after
        it is loaded."""
        # Determine if Job operations are available with Hole Geometry
        availableOps = []
        # ops = self.job.Operations.Group
        # for op in ops:
        #    if hasattr(op, "Hole") and isinstance(op.Hole, list):
        #        if len(op.Hole) > 0:
        #            availableOps.append(op.Label)

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
        self.updating = False

    def getTitle(self, obj):
        return translate("PathTaskPanelHoleGeometryPage", "Hole Geometry")

    def getFields(self, obj):
        pass

    def setFields_ORIG(self, obj):
        self.form.baseList.blockSignals(True)
        self.form.baseList.clear()
        for base in self.obj.Hole:
            for sub in base[1]:
                item = QtGui.QListWidgetItem("%s.%s" % (base[0].Label, sub))
                item.setData(self.DataObject, base[0])
                item.setData(self.DataObjectSub, sub)
                self.form.baseList.addItem(item)
        self.form.baseList.blockSignals(False)
        self.resizeBaseList()

    def setFields(self, obj):
        """setFields(obj) ... fill form with values from obj"""
        PathLog.track()
        self.form.baseList.blockSignals(True)
        self.form.baseList.clearContents()
        self.form.baseList.setRowCount(0)
        for (base, subs) in obj.Hole:
            for sub in subs:
                self.form.baseList.insertRow(self.form.baseList.rowCount())

                item = QtGui.QTableWidgetItem("%s.%s" % (base.Label, sub))
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                if obj.Proxy.isHoleEnabled(obj, base, sub):
                    item.setCheckState(QtCore.Qt.Checked)
                else:
                    item.setCheckState(QtCore.Qt.Unchecked)
                name = "%s.%s" % (base.Name, sub)
                item.setData(self.DataFeatureName, name)
                item.setData(self.DataObject, base)
                item.setData(self.DataObjectSub, sub)
                self.form.baseList.setItem(self.form.baseList.rowCount() - 1, 0, item)

                dia = obj.Proxy.holeDiameter(base, sub)
                item = QtGui.QTableWidgetItem("{:.3f}".format(dia))
                item.setData(self.DataFeatureName, name)
                item.setData(self.DataObject, base)
                item.setData(self.DataObjectSub, sub)
                item.setTextAlignment(QtCore.Qt.AlignHCenter)
                self.form.baseList.setItem(self.form.baseList.rowCount() - 1, 1, item)

        self.form.baseList.resizeColumnToContents(0)
        self.form.baseList.blockSignals(False)
        self.form.baseList.setSortingEnabled(True)
        self.itemActivated()

    def itemActivated_ORIG(self):
        FreeCADGui.Selection.clearSelection()
        for item in self.form.baseList.selectedItems():
            obj = item.data(self.DataObject)
            sub = item.data(self.DataObjectSub)
            if sub:
                FreeCADGui.Selection.addSelection(obj, sub)
            else:
                FreeCADGui.Selection.addSelection(obj)

    def itemActivated(self):
        """itemActivated() ... callback when item in table is selected"""
        PathLog.track()
        if self.form.baseList.selectedItems():
            self.form.deleteBase.setEnabled(True)
            FreeCADGui.Selection.clearSelection()
            activatedRows = []
            for item in self.form.baseList.selectedItems():
                row = item.row()
                if not row in activatedRows:
                    activatedRows.append(row)
                    obj = item.data(self.DataObject)
                    sub = str(item.data(self.DataObjectSub))
                    PathLog.debug("itemActivated() -> %s.%s" % (obj.Label, sub))
                    if sub:
                        FreeCADGui.Selection.addSelection(obj, sub)
                    else:
                        FreeCADGui.Selection.addSelection(obj)
        else:
            self.form.deleteBase.setEnabled(False)

    def supportsVertexes(self):
        return self.features & PathOp2.FeatureBaseVertexes

    def supportsEdges(self):
        return self.features & PathOp2.FeatureBaseEdges

    def supportsFaces(self):
        return self.features & PathOp2.FeatureBaseFaces

    def supportsPanels(self):
        return self.features & PathOp2.FeatureBasePanels

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
            if (
                not self.supportsVertexes()
                and selection[0].SubObjects[0].ShapeType == "Vertex"
            ):
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
            if not self.supportsPanels() or "Panel" not in sel.Object.Name:
                if not ignoreErrors:
                    PathLog.error(
                        translate(
                            "PathProject",
                            "Please select %s of a solid" % self.featureName(),
                        )
                    )
                return False
        return True

    def selectionSupportedAsTargetGeometry(self, selection, ignoreErrors):
        if len(selection) != 1:
            if not ignoreErrors:
                msg = translate(
                    "PathProject",
                    "Please select %s from a single solid" % self.featureName(),
                )
                FreeCAD.Console.PrintError(msg + "\n")
                PathLog.debug(msg)
            return False

        if selection[0].ObjectName.startswith("TargetGeometry"):
            return True

        if not ignoreErrors:
            PathLog.error(
                translate(
                    "PathProject",
                    "Please select TargetGeometry. %s is not TargetGeometry object."
                    % selection[0].ObjectName,
                )
            )
        return False

    def addBaseGeometry(self, selection):
        PathLog.track(selection)
        if self.selectionSupportedAsBaseGeometry(selection, False):
            sel = selection[0]
            for sub in sel.SubElementNames:
                # self.obj.Proxy.addBase(self.obj, sel.Object, sub)
                self.obj.Proxy.addHole(self.obj, sel.Object, sub)
            return True
        elif self.selectionSupportedAsTargetGeometry(selection, False):
            sel = selection[0].Object
            self.obj.TargetShape = sel
            PathLog.info(
                translate(
                    "PathTaskPanelHoleGeometryPage",
                    "Target shape set to {}".format(sel.Name),
                )
            )
        return False

    def addHole(self):
        PathLog.track()
        if self.addBaseGeometry(FreeCADGui.Selection.getSelectionEx()):
            self.setFields(self.obj)
            self.setDirty()
            self.updatePanelVisibility("Operation", self.obj)

    def deleteBase_ORIG(self):
        PathLog.track()
        selected = self.form.baseList.selectedItems()
        for item in selected:
            self.form.baseList.takeItem(self.form.baseList.row(item))
            self.setDirty()
        self.updateBase()
        self.updatePanelVisibility("Operation", self.obj)
        self.resizeBaseList()

    def deleteBase(self):
        """deleteBase() ... callback for push button"""
        PathLog.track()
        selected = [
            self.form.baseList.row(item) for item in self.form.baseList.selectedItems()
        ]
        self.form.baseList.blockSignals(True)
        for row in sorted(list(set(selected)), key=lambda row: -row):
            self.form.baseList.removeRow(row)
        self.updateBase()
        self.form.baseList.resizeColumnToContents(0)
        self.form.baseList.blockSignals(False)
        FreeCAD.ActiveDocument.recompute()
        self.setFields(self.obj)

    def updateBase_ORIG(self):
        newlist = []
        for i in range(self.form.baseList.count()):
            item = self.form.baseList.item(i)
            obj = item.data(self.DataObject)
            sub = item.data(self.DataObjectSub)
            if sub:
                base = (obj, str(sub))
                newlist.append(base)
        PathLog.debug("Setting new base: %s -> %s" % (self.obj.Hole, newlist))
        self.obj.Hole = newlist

    def updateBase(self):
        """updateBase() ... helper function to transfer current table to obj"""
        PathLog.track()
        newlist = []
        for i in range(self.form.baseList.rowCount()):
            item = self.form.baseList.item(i, 0)
            obj = item.data(self.DataObject)
            sub = str(item.data(self.DataObjectSub))
            base = (obj, sub)
            PathLog.debug("keeping (%s.%s)" % (obj.Label, sub))
            newlist.append(base)
        PathLog.debug("obj.Hole=%s newlist=%s" % (self.obj.Hole, newlist))
        self.updating = True
        self.obj.Hole = newlist
        self.updating = False

    def clearBase(self):
        self.obj.Hole = []
        self.setDirty()
        self.updatePanelVisibility("Operation", self.obj)
        self.resizeBaseList()

    def importBaseGeometry(self):
        opLabel = str(self.form.geometryImportList.currentText())
        ops = FreeCAD.ActiveDocument.getObjectsByLabel(opLabel)
        if len(ops) > 1:
            msg = translate(
                "PathTaskPanelHoleGeometryPage", "Mulitiple operations are labeled as"
            )
            msg += " {}\n".format(opLabel)
            FreeCAD.Console.PrintWarning(msg)
        (base, subList) = ops[0].Hole[0]
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(base, subList)
        self.addHole()

    def registerSignalHandlers_ORIG(self, obj):
        self.form.baseList.itemSelectionChanged.connect(self.itemActivated)
        self.form.addBase.clicked.connect(self.addHole)
        self.form.deleteBase.clicked.connect(self.deleteBase)
        self.form.clearBase.clicked.connect(self.clearBase)
        self.form.geometryImportButton.clicked.connect(self.importBaseGeometry)

    def registerSignalHandlers(self, obj):
        """registerSignalHandlers(obj) ... setup signal handlers"""
        self.form.baseList.itemSelectionChanged.connect(self.itemActivated)
        self.form.addBase.clicked.connect(self.addHole)
        self.form.deleteBase.clicked.connect(self.deleteBase)
        self.form.resetBase.clicked.connect(self.resetBase)
        self.form.baseList.itemChanged.connect(self.checkedChanged)

    def pageUpdateData(self, obj, prop):
        if prop in ["Hole"]:
            self.setFields(obj)

    def updateSelection(self, obj, sel):
        if self.selectionSupportedAsBaseGeometry(sel, True):
            self.form.addBase.setEnabled(True)
        else:
            self.form.addBase.setEnabled(False)

    def resizeBaseList(self):
        # Set base geometry list window to resize based on contents
        # Code reference:
        # https://stackoverflow.com/questions/6337589/qlistwidget-adjust-size-to-content
        # ml: disabling this logic because I can't get it to work on HPD monitor.
        #     On my systems the values returned by the list object are also incorrect on
        #     creation, leading to a list object of size 15. count() always returns 0 until
        #     the list is actually displayed. The same is true for sizeHintForRow(0), which
        #     returns -1 until the widget is rendered. The widget claims to have a size of
        #     (100, 30), once it becomes visible the size is (535, 192).
        #     Leaving the framework here in case somebody figures out how to set this up
        #     properly.
        qList = self.form.baseList
        row = (qList.count() + qList.frameWidth()) * 15
        # qList.setMinimumHeight(row)
        PathLog.debug(
            "baseList({}, {}) {} * {}".format(
                qList.size(), row, qList.count(), qList.sizeHintForRow(0)
            )
        )

    def checkedChanged(self):
        """checkeChanged() ... callback when checked status of a base feature changed"""
        PathLog.track()
        disabled = []
        for i in range(0, self.form.baseList.rowCount()):
            item = self.form.baseList.item(i, 0)
            if item.checkState() != QtCore.Qt.Checked:
                disabled.append(item.data(self.DataFeatureName))
        self.obj.Disabled = disabled
        FreeCAD.ActiveDocument.recompute()

    def resetBase(self):
        """resetBase() ... push button callback"""
        print("PathTaskPanelHoleGeometryPage.TaskPanelHoleGeometryPage.resetBase()")
        self.obj.Hole = []
        self.obj.Disabled = []
        self.obj.Proxy.findAllHoles(self.obj)

    def updateData(self, obj, prop):
        """updateData(obj, prop) ... callback whenever a property of the model changed"""
        if not self.updating and prop in ["Hole", "Disabled"]:
            self.setFields(obj)
