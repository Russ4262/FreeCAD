# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2019 sliptonic <shopinthewoods@gmail.com>               *
# *   Copyright (c) 2023 Russell Johnson (russ4262) <russ4262@gmail.com>    *
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

import PySide
import FreeCAD
import FreeCADGui
import Path

import offsetinsideout.OffsetInsideOut as DressupOffsetInsideOut

__title__ = "Offset Inside-out Dressup Gui"
__author__ = "Russell Johnson (russ4262) <russ4262@gmail.com>"
__doc__ = "Gui interface to create an Offset Inside-out dressup on a referenced Pocket operation."
__usage__ = "Import this module.  Run the 'Create(base)' function, passing it the desired Profile operation as the base parameter."
__url__ = ""
__Wiki__ = ""
__date__ = "2023.05.23"
__version__ = 1.0


if False:
    Path.Log.setLevel(Path.Log.Level.DEBUG, Path.Log.thisModule())
    Path.Log.trackModule(Path.Log.thisModule())
else:
    Path.Log.setLevel(Path.Log.Level.INFO, Path.Log.thisModule())


translate = FreeCAD.Qt.translate
PathUtils = DressupOffsetInsideOut.PathUtils


def selectInComboBox(name, combo):
    """selectInComboBox(name, combo) ...
    helper function to select a specific value in a combo box."""
    __ = PySide.QtCore.QSignalBlocker(combo)
    index = combo.currentIndex()  # Save initial index

    # Search using currentData and return if found
    newindex = combo.findData(name)
    if newindex >= 0:
        combo.setCurrentIndex(newindex)
        return

    # if not found, search using current text
    newindex = combo.findText(name, PySide.QtCore.Qt.MatchFixedString)
    if newindex >= 0:
        combo.setCurrentIndex(newindex)
        return

    # not found, return unchanged
    combo.setCurrentIndex(index)
    return


class TaskPanel(object):
    def __init__(self, obj, viewProvider):
        self.obj = obj
        self.viewProvider = viewProvider
        # formFile = FreeCAD.getHomePath() + "Mod/Path/Path/Dressup/Gui/DressupOffsetInsideOutEdit.ui"
        formFile = (
            FreeCAD.getUserAppDataDir()
            + "Macro/offsetinsideout/DressupOffsetInsideOutEdit.ui"
        )
        self.form = FreeCADGui.PySideUic.loadUi(formFile)

        self.buttonBox = None
        self.isDirty = False

    def getStandardButtons(self):
        return int(
            PySide.QtGui.QDialogButtonBox.Ok
            | PySide.QtGui.QDialogButtonBox.Apply
            | PySide.QtGui.QDialogButtonBox.Cancel
        )

    def modifyStandardButtons(self, buttonBox):
        self.buttonBox = buttonBox

    def setDirty(self):
        self.isDirty = True
        self.buttonBox.button(PySide.QtGui.QDialogButtonBox.Apply).setEnabled(True)

    def setClean(self):
        self.isDirty = False
        self.buttonBox.button(PySide.QtGui.QDialogButtonBox.Apply).setEnabled(False)

    def clicked(self, button):
        # callback for standard buttons
        if button == PySide.QtGui.QDialogButtonBox.Apply:
            self._updateDressup()
            FreeCAD.ActiveDocument.recompute()

    def abort(self):
        FreeCAD.ActiveDocument.abortTransaction()
        self.cleanup(False)

    def reject(self):
        FreeCAD.ActiveDocument.abortTransaction()
        self.cleanup(True)

    def accept(self):
        if self.isDirty:
            self._updateDressup()
        FreeCAD.ActiveDocument.commitTransaction()
        self.cleanup(True)

    def cleanup(self, gui):
        self.viewProvider.clearTaskPanel()
        if gui:
            FreeCADGui.ActiveDocument.resetEdit()
            FreeCADGui.Control.closeDialog()
            FreeCAD.ActiveDocument.recompute()

    def _populateBaseProfileCombo(self):
        job = PathUtils.findParentJob(self.obj)
        availableOps = [
            op.Name for op in job.Operations.Group if op.Name[:12] == "Pocket_Shape"
        ]
        if self.obj.Base.Name not in availableOps:
            availableOps.insert(0, self.obj.Base.Name)
        self.form.baseProfile.blockSignals(True)
        self.form.baseProfile.clear()
        # availableOps.sort()
        for n in availableOps:
            self.form.baseProfile.addItem(n)
        self.form.baseProfile.blockSignals(False)

    def _updateDressup(self):
        if self.obj.Base.Name != self.form.baseProfile.currentText():
            self.obj.Base = FreeCAD.ActiveDocument.getObject(
                self.form.baseProfile.currentText()
            )

        if self.obj.CutInsideOut != self.form.cutInsideOut.isChecked():
            self.obj.CutInsideOut = self.form.cutInsideOut.isChecked()

        self.setClean()

    def setupUi(self):
        self._populateBaseProfileCombo()

        selectInComboBox(self.obj.Base.Name, self.form.baseProfile)

        self.form.cutInsideOut.setChecked(self.obj.CutInsideOut)

        self.form.baseProfile.currentIndexChanged.connect(self.setDirty)
        self.form.cutInsideOut.stateChanged.connect(self.setDirty)


# Eclass


class DressupOffsetInsideOutViewProvider(object):
    def __init__(self, vobj):
        self.attach(vobj)

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

    def attach(self, vobj):
        self.vobj = vobj
        self.obj = vobj.Object
        self.panel = None

    def claimChildren(self):
        return [self.obj.Base]

    def onDelete(self, vobj, args=None):
        if vobj.Object and vobj.Object.Proxy:
            vobj.Object.Proxy.onDelete(vobj.Object, args)
        return True

    def setEdit(self, vobj, mode=0):
        panel = TaskPanel(vobj.Object, self)
        self.setupTaskPanel(panel)
        return True

    def unsetEdit(self, vobj, mode=0):
        if self.panel:
            self.panel.abort()

    def setupTaskPanel(self, panel):
        self.panel = panel
        FreeCADGui.Control.closeDialog()
        FreeCADGui.Control.showDialog(panel)
        panel.setupUi()

    def clearTaskPanel(self):
        self.panel = None


# Eclass


def Create(base, name="DressupOffsetInsideOut"):
    FreeCAD.ActiveDocument.openTransaction("Create a Offset Inside-out dressup")
    obj = DressupOffsetInsideOut.Create(base, name)
    obj.ViewObject.Proxy = DressupOffsetInsideOutViewProvider(obj.ViewObject)
    obj.Base.ViewObject.Visibility = False
    FreeCAD.ActiveDocument.commitTransaction()
    obj.ViewObject.Document.setEdit(obj.ViewObject, 0)
    return obj


class CommandDressupOffsetInsideOut:
    def GetResources(self):
        return {
            "Pixmap": "Path_Dressup",
            "MenuText": PySide.QtCore.QT_TRANSLATE_NOOP(
                "Path_DressupOffsetInsideOut", "Offset Inside-out"
            ),
            "ToolTip": PySide.QtCore.QT_TRANSLATE_NOOP(
                "Path_DressupOffsetInsideOut",
                "Creates a Path Offset Inside-out Dress-up object from a selected path",
            ),
        }

    def IsActive(self):
        if FreeCAD.ActiveDocument is not None:
            for o in FreeCAD.ActiveDocument.Objects:
                if o.Name[:7] == "Profile":
                    return True
        return False

    def Activated(self):
        # check that the selection contains exactly what we want
        selection = FreeCADGui.Selection.getSelection()
        if len(selection) != 1:
            Path.Log.error(
                translate(
                    "Path_DressupOffsetInsideOut", "Please select one path object"
                )
                + "\n"
            )
            return
        baseObject = selection[0]

        # everything ok!
        FreeCAD.ActiveDocument.openTransaction("Create Path Offset Inside-out Dress-up")
        FreeCADGui.addModule("Path.Dressup.Gui.OffsetInsideOut")
        FreeCADGui.doCommand(
            f"Path.Dressup.Gui.OffsetInsideOut.Create(App.ActiveDocument.{baseObject.Name})"
        )
        # FreeCAD.ActiveDocument.commitTransaction()  # Final `commitTransaction()` called via TaskPanel.accept()
        FreeCAD.ActiveDocument.recompute()


# Eclass

if FreeCAD.GuiUp:
    # register the FreeCAD command
    FreeCADGui.addCommand(
        "Path_DressupOffsetInsideOut", CommandDressupOffsetInsideOut()
    )
    # Path.Log.info("Path_DressupOffsetInsideOut command added...\n")

Path.Log.notice("Loading DressupOffsetInsideOutGui... done\n")
