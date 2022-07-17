# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2022 Russell Johnson (russ4262) <russ4262@gmail.com>    *
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
from PySide import QtGui
from PySide import QtCore
from PySide.QtCore import QT_TRANSLATE_NOOP
import importlib
import GuiSupport.Gui_Input as Gui_Input
import CommandsRegistry


__title__ = "FreeCAD Path Exp workbench commands"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Module to contain commands for Path Exp workbench."

translate = FreeCAD.Qt.translate

"""
class _Toggle:
    "command definition to toggle Operation Active state"

    def GetResources(self):
        return {
            "Pixmap": "Path_OpActive",
            "MenuText": QT_TRANSLATE_NOOP(
                "PathExp_Toggle", "Toggle the visibility the object"
            ),
            "Accel": "P, X",
            "ToolTip": QT_TRANSLATE_NOOP(
                "PathExp_Toggle", "Toggle the visibility the object"
            ),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        return True

    def Activated(self):
        for sel in FreeCADGui.Selection.getSelectionEx():
            op = sel.Object
            if op.ViewObject.Visibility:
                op.ViewObject.Visibility = False
            else:
                op.ViewObject.Visibility = True

        FreeCAD.ActiveDocument.recompute()


class _ProfileOperation:
    "command definition to create Path Profile operation"

    def GetResources(self):
        return {
            "Pixmap": "Path_Profile",
            "MenuText": QT_TRANSLATE_NOOP(
                "PathExp_Profile", "Create current Profile operation"
            ),
            "Accel": "P, P",
            "ToolTip": QT_TRANSLATE_NOOP(
                "PathExp_Profile", "Create current Profile operation."
            ),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        return True

    def Activated(self):
        import PathScripts.PathProfileGui as ProfileGui

        ProfileGui.Command.Activated()

        FreeCAD.ActiveDocument.recompute()


class _SampleOperation:
    "command definition to toggle Operation Active state"

    def GetResources(self):
        return {
            "Pixmap": "Path_Stop",
            "MenuText": QT_TRANSLATE_NOOP("PathExp_Sample", "Sample operation"),
            "Accel": "P, S",
            "ToolTip": QT_TRANSLATE_NOOP("PathExp_Sample", "Sample operation."),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        return True

    def Activated(self):
        import Ops.PathExp_Test as PPT

        PPT.execute()

        FreeCAD.ActiveDocument.recompute()


class _SlotOperation:
    "command definition to create Slot+ operation"

    def GetResources(self):
        return {
            "Pixmap": "Path_Slot",
            "MenuText": QT_TRANSLATE_NOOP(
                "PathExp_Profile", "Create Slot Plus operation"
            ),
            "Accel": "P, P",
            "ToolTip": QT_TRANSLATE_NOOP(
                "PathExp_Profile", "Create Slot Plus operation."
            ),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        return True

    def Activated(self):
        import OpsGui.PathSlotGui as SlotGui

        SlotGui.Command.Activated()

        FreeCAD.ActiveDocument.recompute()

"""


class _LoadPathWorkbench:
    "command definition to load the Path workbench"

    def GetResources(self):
        return {
            # "Pixmap": "PathWorkbench",
            "Pixmap": FreeCAD.getUserAppDataDir()
            + "Mod/PathExp/GuiSupport/PathWorkbench.svg",
            "MenuText": QT_TRANSLATE_NOOP("PathExp_PathWB", "Load Path WB"),
            "Accel": "P, C",
            "ToolTip": QT_TRANSLATE_NOOP("PathExp_PathWB", "Load the Path workbench."),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        return True

    def Activated(self):
        FreeCADGui.activateWorkbench("PathWorkbench")


class _TargetShape:
    "command definition to build a target shape"

    def GetResources(self):
        return {
            "Pixmap": "Path_Simulator",  # Path_SelectLoop
            "MenuText": QT_TRANSLATE_NOOP("PathExp", "Target Shape"),
            "Accel": "P, B",
            "ToolTip": QT_TRANSLATE_NOOP(
                "PathExp",
                "Build a target shape as a basis for a subsequent cutting operation.",
            ),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        return True

    def Activated(self):
        import Shape.TargetShapeGui as TargetShapeGui

        TargetShapeGui.Command.Activated()

        FreeCAD.ActiveDocument.recompute()


class _StartOperation:
    "command definition to choose an operation"

    def _getOpCommandModule(self):
        """_getOpCommandModule()... Return module associated with user-selected operation."""
        icons = []
        texts = []
        data = []
        gi = Gui_Input.GuiInput("Start Operation")
        for k in CommandsRegistry.OPS.keys():
            op = CommandsRegistry.OPS[k]
            icons.append(QtGui.QIcon(f":/icons/{op[2]}"))
            texts.append(op[1])
            data.append(k)
        gi.addIconComboBox("Select an operation: ", icons, texts, data)
        l = gi.getLabelByIndex(0)
        l.setAlignment(QtCore.Qt.AlignRight)
        values = gi.execute()
        if not values:
            return None
        return CommandsRegistry.OPS[values[0]][0]

    def GetResources(self):
        return {
            "Pixmap": "Path_Probe",
            "MenuText": QT_TRANSLATE_NOOP("PathExp", "Start operation."),
            "Accel": "P, S",
            "ToolTip": QT_TRANSLATE_NOOP(
                "PathExp", "Create menu selection to choose an operation."
            ),
            "CmdType": "ForEdit",
        }

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        return True

    def Activated(self):
        modName = self._getOpCommandModule()
        if modName:
            mod = importlib.import_module(modName)
            mod.Command.Activated()
        FreeCAD.ActiveDocument.recompute()


# FreeCADGui.addCommand("PathExp_Toggle", _Toggle())
# FreeCADGui.addCommand("PathExp_Profile", _ProfileOperation())
# FreeCADGui.addCommand("PathExp_Sample", _SampleOperation())


FreeCAD.Console.PrintMessage("Loading Commands module of Path Exp workbench...\n")
