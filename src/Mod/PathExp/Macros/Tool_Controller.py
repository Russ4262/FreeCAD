# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2021 Russell Johnson (russ4262) <russ4262@gmail.com>    *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
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

if FreeCAD.GuiUp:
    import Gui_Input


__title__ = "Path Line Clearing Generator"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Generates the line-clearing toolpath for a single 2D face"


class Tool:
    def __init__(self):
        self.Diameter = FreeCAD.Units.Quantity("2.0 mm")


class ToolController:
    def __init__(self):
        self.VertFeed = FreeCAD.Units.Quantity("30.0 mm/min")
        self.VertRapid = FreeCAD.Units.Quantity("60.0 mm/min")
        self.HorizFeed = FreeCAD.Units.Quantity("120.0 mm/min")
        self.HorizRapid = FreeCAD.Units.Quantity("240.0 mm/min")
        self.Tool = Tool()
        self.Label = "Custom Tool Controller"
        print("Using a Custom Tool Controller")


# Auxillary functions
def getToolFromUser(toolLabels):
    # Get tool controller from user
    guiInput = Gui_Input.GuiInput()
    guiInput.setWindowTitle("Tool Controller Selection")
    guiInput.addComboBox("Tool controller", toolLabels)
    toolLabel = guiInput.execute()
    return toolLabel[0]


def getToolController(job=None):
    tcIdx = 0
    if job:
        tools = job.Tools.Group
        if len(tools) > 1:
            toolLabels = [t.Label for t in tools]
            toolLabel = getToolFromUser(toolLabels)
            tcIdx = toolLabels.index(toolLabel)
        return tools[tcIdx], job

    allTools = []
    for obj in FreeCAD.ActiveDocument.Objects:
        if obj.Name == "Job":
            allTools.extend(
                [(tc, obj) for tc in FreeCAD.ActiveDocument.Job.Tools.Group]
            )
    if len(allTools) > 1:
        toolLabels = [t.Label + f"_{j.Name}" for t, j in allTools]
        toolLabel = getToolFromUser(toolLabels)
        tcIdx = toolLabels.index(toolLabel)
        return allTools[tcIdx]

    return ToolController(), None


print("Imported Tool_Controller")
