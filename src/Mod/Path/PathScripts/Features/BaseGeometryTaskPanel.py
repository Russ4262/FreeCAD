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


class TaskPanelBaseGeometryPage(PathOpGui.TaskPanelPage):
    '''Page controller for the base geometry.'''
    DataObject = QtCore.Qt.ItemDataRole.UserRole
    DataObjectSub = QtCore.Qt.ItemDataRole.UserRole + 1

    def __init__(self, obj, features):
        super(TaskPanelBaseGeometryPage, self).__init__(obj, features)

        self.panelTitle = 'Base Geometry'

    def getForm(self):
        panel = FreeCADGui.PySideUic.loadUi(":/panels/PageBaseGeometryEdit.ui")
        self.modifyPanel(panel)
        return panel

    def modifyPanel(self, panel):
        # Determine if possible operations are available
        availableOps = list()
        ops = self.job.Operations.Group
        for op in ops:
            if hasattr(op, 'Base') and isinstance(op.Base, list):
                if len(op.Base) > 0:
                    availableOps.append(op.Label)

        if len(availableOps) > 0:
            # Populate the operations list
            addInputs = True
            panel.geometryImportList.blockSignals(True)
            panel.geometryImportList.clear()
            availableOps.sort()
            for opLbl in availableOps:
                panel.geometryImportList.addItem(opLbl)
            panel.geometryImportList.blockSignals(False)
        else:
            panel.geometryImportList.hide()
            panel.geometryImportButton.hide()

    def getTitle(self, obj):
        return translate("PathOp", "Base Geometry")

    def getFields(self, obj):
        pass

    def setFields(self, obj):
        self.form.baseList.blockSignals(True)
        self.form.baseList.clear()
        for base in self.obj.Base:
            for sub in base[1]:
                item = QtGui.QListWidgetItem("%s.%s" % (base[0].Label, sub))
                item.setData(self.DataObject, base[0])
                item.setData(self.DataObjectSub, sub)
                self.form.baseList.addItem(item)
        self.form.baseList.blockSignals(False)

    def itemActivated(self):
        FreeCADGui.Selection.clearSelection()
        for item in self.form.baseList.selectedItems():
            obj = item.data(self.DataObject)
            sub = item.data(self.DataObjectSub)
            if sub:
                FreeCADGui.Selection.addSelection(obj, sub)
            else:
                FreeCADGui.Selection.addSelection(obj)
        # FreeCADGui.updateGui()

    def supportsVertexes(self):
        return self.features & PathOp.FeatureBaseVertexes

    def supportsEdges(self):
        return self.features & PathOp.FeatureBaseEdges

    def supportsFaces(self):
        return self.features & PathOp.FeatureBaseFaces

    def supportsPanels(self):
        return self.features & PathOp.FeatureBasePanels

    def featureName(self):
        if self.supportsEdges() and self.supportsFaces():
            return 'features'
        if self.supportsFaces():
            return 'faces'
        if self.supportsEdges():
            return 'edges'
        return 'nothing'

    def selectionSupportedAsBaseGeometry(self, selection, ignoreErrors):
        if len(selection) != 1:
            if not ignoreErrors:
                msg = translate("PathProject", "Please select %s from a single solid" % self.featureName())
                FreeCAD.Console.PrintError(msg + '\n')
                PathLog.debug(msg)
            return False
        sel = selection[0]
        if sel.HasSubObjects:
            if not self.supportsVertexes() and selection[0].SubObjects[0].ShapeType == "Vertex":
                if not ignoreErrors:
                    PathLog.error(translate("PathProject", "Vertexes are not supported"))
                return False
            if not self.supportsEdges() and selection[0].SubObjects[0].ShapeType == "Edge":
                if not ignoreErrors:
                    PathLog.error(translate("PathProject", "Edges are not supported"))
                return False
            if not self.supportsFaces() and selection[0].SubObjects[0].ShapeType == "Face":
                if not ignoreErrors:
                    PathLog.error(translate("PathProject", "Faces are not supported"))
                return False
        else:
            if not self.supportsPanels() or not 'Panel' in sel.Object.Name:
                if not ignoreErrors:
                    PathLog.error(translate("PathProject", "Please select %s of a solid" % self.featureName()))
                return False
        return True

    def addBaseGeometry(self, selection):
        PathLog.track(selection)
        if self.selectionSupportedAsBaseGeometry(selection, False):
            sel = selection[0]
            for sub in sel.SubElementNames:
                self.obj.Proxy.addBase(self.obj, sel.Object, sub)
            return True
        return False

    def addBase(self):
        if self.addBaseGeometry(FreeCADGui.Selection.getSelectionEx()):
            # self.obj.Proxy.execute(self.obj)
            self.setFields(self.obj)
            self.setDirty()
            self.updatePanelVisibility('Operation', self.obj)

    def deleteBase(self):
        PathLog.track()
        selected = self.form.baseList.selectedItems()
        for item in selected:
            self.form.baseList.takeItem(self.form.baseList.row(item))
            self.setDirty()
            self.updatePanelVisibility('Operation', self.obj)
        self.updateBase()
        # self.obj.Proxy.execute(self.obj)
        # FreeCAD.ActiveDocument.recompute()

    def updateBase(self):
        newlist = []
        for i in range(self.form.baseList.count()):
            item = self.form.baseList.item(i)
            obj = item.data(self.DataObject)
            sub = item.data(self.DataObjectSub)
            if sub:
                base = (obj, str(sub))
                newlist.append(base)
        PathLog.debug("Setting new base: %s -> %s" % (self.obj.Base, newlist))
        self.obj.Base = newlist

        # self.obj.Proxy.execute(self.obj)
        # FreeCAD.ActiveDocument.recompute()

    def clearBase(self):
        self.obj.Base = []
        self.setDirty()
        self.updatePanelVisibility('Operation', self.obj)

    def importBaseGeometry(self):
        opLabel = str(self.form.geometryImportList.currentText())
        ops = FreeCAD.ActiveDocument.getObjectsByLabel(opLabel)
        if ops.__len__() > 1:
            msg = translate('PathOpGui', 'Mulitiple operations are labeled as')
            msg += " {}\n".format(opLabel)
            FreeCAD.Console.PrintWarning(msg)
        for (base, subList) in ops[0].Base:
            FreeCADGui.Selection.addSelection(base, subList)
        self.addBase()

    def registerSignalHandlers(self, obj):
        self.form.baseList.itemSelectionChanged.connect(self.itemActivated)
        self.form.addBase.clicked.connect(self.addBase)
        self.form.deleteBase.clicked.connect(self.deleteBase)
        self.form.clearBase.clicked.connect(self.clearBase)
        self.form.geometryImportButton.clicked.connect(self.importBaseGeometry)

    def pageUpdateData(self, obj, prop):
        if prop in ['Base']:
            self.setFields(obj)

    def updateSelection(self, obj, sel):
        if self.selectionSupportedAsBaseGeometry(sel, True):
            self.form.addBase.setEnabled(True)
        else:
            self.form.addBase.setEnabled(False)

FreeCAD.Console.PrintLog("Loading BaseGeometryTaskPanel... done\n")
