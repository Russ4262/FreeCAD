# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2016 sliptonic <shopinthewoods@gmail.com>               *
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

__title__ = "Path Experimental Workbench Commands Registry "
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Commands registry for Path Experimental workbench."

translate = FreeCAD.Qt.translate
OPS = {
    "Adaptive": (
        "OpsGui.PathAdaptiveGui",
        translate("PathExp", "Adaptive"),
        "Path_Adaptive",
    ),
    "3D Pocket": (
        "OpsGui.PathPocketGui",
        translate("PathExp", "3D Pocket"),
        "Path_3DPocket",
    ),
    "Pocket": (
        "OpsGui.PathPocketShapeGui",
        translate("PathExp", "Pocket"),
        "Path_Pocket",
    ),
    "3D Surface": (
        "PathScripts.PathSurfaceGui",
        translate("PathExp", "3D Surface"),
        "Path_3DSurface",
    ),
    "Profile": (
        "OpsGui.PathProfileGui",
        translate("PathExp", "Profile"),
        "Path_Profile",
    ),
    "Helix": (
        "PathScripts.PathHelixGui",
        translate("PathExp", "Helix"),
        "Path_Helix",
    ),
    "Drilling": (
        "PathScripts.PathDrillingGui",
        translate("PathExp", "Drilling"),
        "Path_Drilling",
    ),
    "Facing": (
        "PathScripts.PathMillFaceGui",
        translate("PathExp", "Facing"),
        "Path_Face",
    ),
    "Slot": ("OpsGui.PathSlotGui", translate("PathExp", "Slot"), "Path_Slot"),
}

FreeCAD.Console.PrintMessage("Loaded the Ops registry.\n")
