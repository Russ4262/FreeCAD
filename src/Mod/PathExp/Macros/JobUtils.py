# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2023 Russell Johnson (russ4262) <russ4262@gmail.com>    *
# *                                                                         *
# *   This file is a supplement to the FreeCAD CAx development system.      *
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
import os
import Path
import glob
import json
import Path.Tool.Bit as Bit

if FreeCAD.GuiUp:
    import Path.Main.Gui.Job as JobGui

    Job = JobGui.PathJob
    GUI_UP = True
else:
    import Path.Main.Job as Job

    GUI_UP = False


__title__ = "Job Utilities"
__author__ = "russ4262 (Russell Johnson)"
__url__ = ""
__doc__ = (
    "Path workbench utility functions to aid in job and tool controller scripting."
)
__version__ = "2023-04-16"
__freecad_revision_base__ = "32821"
__contributors__ = ""

ToolController = Job.PathToolController
ToolBit = ToolController.PathToolBit

# Support functions
def _get_available_tool_library_paths():
    """
    Finds all the fctl files in a location
    Code based on Path.Tool.Gui.BitLibrary.ModelFactory.findLibraries()
    """

    path = Path.Preferences.lastPathToolLibrary()

    libraries = []
    if os.path.isdir(path):  # opening all tables in a directory
        libFiles = [f for f in glob.glob(path + os.path.sep + "*.fctl")]
        libFiles.sort()
        for libFile in libFiles:
            loc, fnlong = os.path.split(libFile)
            fn, ext = os.path.splitext(fnlong)
            libraries.append((loc, fn, libFile))

    # print(f"{libraries}")

    return libraries


def _read_library(path):
    """
    _read_library(path)
    Arguments:
        path:  path to library file
    Returns list of tuples, each containing toolbit information for the tool referenced in path file
    Code based on Path.Tool.Gui.BitLibrary.ModelFactory.__libraryLoad()
    """

    with open(path) as fp:
        library = json.load(fp)

    data = []
    for toolBit in library["tools"]:
        try:
            nr = toolBit["nr"]
            bit = ToolBit.findToolBit(toolBit["path"], path)
            if bit:
                tool = ToolBit.Declaration(bit)
                data.append((nr, tool, bit))
            else:
                FreeCAD.Console.PrintError(
                    "Could not find tool #{}: {}\n".format(nr, toolBit["path"])
                )
        except Exception as e:
            msg = "Error loading tool: {} : {}\n".format(toolBit["path"], e)
            FreeCAD.Console.PrintError(msg)

    return data


def _get_tool_by_number(number):
    """
    _get_tool_by_number(number)
    Arguments:
        number:  number of toolbit stored in tool library
    Returns a tool number and toolbit object as a tuple if the number is found.
    Taken from Path.Tool.Gui.BitLibrary.ModelFactory.findLibraries()
    """

    libraries = _get_available_tool_library_paths()

    for libLoc, libFN, libFile in libraries:
        for toolNum, toolDict, bitPath in _read_library(libFile):
            if toolNum == number:
                toolBit = Bit.Factory.CreateFromAttrs(toolDict)
                if hasattr(toolBit, "ViewObject") and hasattr(
                    toolBit.ViewObject, "Visibility"
                ):
                    toolBit.ViewObject.Visibility = False
                return (toolNum, toolBit)

    print(f"No tool found with number '{number}'")

    return None, None


def _get_tool_by_filename(name):
    """
    _get_tool_by_filename(name)
    Arguments:
        name: name of toolbit file without extension
    Returns a tool number and toolbit object as a tuple if the name file is found.
    Taken from Path.Tool.Gui.BitLibrary.ModelFactory.findLibraries()
    """

    libraries = _get_available_tool_library_paths()

    for libLoc, libFN, libFile in libraries:
        for toolNum, toolDict, bitPath in _read_library(libFile):
            loc, fnlong = os.path.split(bitPath)
            fn, ext = os.path.splitext(fnlong)
            if fn == name:
                toolBit = Bit.Factory.CreateFromAttrs(toolDict)
                if hasattr(toolBit, "ViewObject") and hasattr(
                    toolBit.ViewObject, "Visibility"
                ):
                    toolBit.ViewObject.Visibility = False
                return (toolNum, toolBit)

    print(f"No tool found with name '{name}'")

    return None, None


def _add_tool_to_job(job, tool):
    """
    _add_tool_to_job(job, tool)
    Arguments:
        job:  target parent job object for tool controller
        tool:  toolbit object as base for tool controller
    Adds a new tool controller based on the tool argument to the target job object provided.
    Code based on Path.Main.Gui.Controller.CommandPathToolController.Activated()
    """

    # Identify correct tool number
    toolNr = None
    for tc in job.Tools.Group:
        if tc.Tool == tool:
            toolNr = tc.ToolNumber
            break
    if not toolNr:
        toolNr = max([tc.ToolNumber for tc in job.Tools.Group]) + 1

    # Create tool controller object
    if GUI_UP:
        tc = ToolController.Create("TC: {}".format(tool.Label), tool, toolNr)
    else:
        tc = ToolController.Create(
            "TC: {}".format(tool.Label), tool, toolNr, assignViewProvider=False
        )

    # Add tool controller to job
    job.Proxy.addToolController(tc)
    FreeCAD.ActiveDocument.recompute()

    return tc


# Public functions
def add_job(models=[], templateFile=None, useGui=False):
    """
    add_job(models=[], templateFile=None, useGui=False)
    Arguments:
        models:  list of model objects, or names of model objects
        templateFile:  template file name to be used
        useGui:  set True to interact with GUI during Job creation
    Adds a new Job object to the active document.
    """

    if GUI_UP:
        job = JobGui.Create(models, templateFile, openTaskPanel=useGui)
    else:
        job = Job.Create("Job", models, templateFile)

    FreeCAD.ActiveDocument.recompute()

    return job


def add_toolcontroller_by_filename(job, name):
    """
    add_toolcontroller_by_filename(job, name)
    Arguments:
        job:  target parent job object for tool controller
        name:  filename (without extension) of file to be used as base for tool controller
    Adds a new tool controller based on the name argument to the target job object provided.
    """
    tn, tool = _get_tool_by_filename(name)

    return _add_tool_to_job(job, tool)


def add_toolcontroller_by_number(job, number):
    """
    add_toolcontroller_by_number(job, number)
    Arguments:
        job:  target parent job object for tool controller
        number:  number of tool as returned from 'available_tool_filenames()' to be used as base for tool controller
    Adds a new tool controller referenced by the number argument to the target job object provided.
    """
    tn, tool = _get_tool_by_number(number)

    return _add_tool_to_job(job, tool)


def available_tool_filenames():
    """
    available_tool_filenames()
    Finds all the '.fctl' (FC tool library) files in last tool library location saved to FreeCAD preferences.
    Code based on Path.Tool.Gui.BitLibrary.ModelFactory.findLibraries()
    """

    available = []
    print("Available tool files:")

    for libLoc, libFN, libFile in _get_available_tool_library_paths():
        for toolNum, toolDict, bitPath in _read_library(libFile):
            loc, fnlong = os.path.split(bitPath)
            fn, ext = os.path.splitext(fnlong)
            available.append(fn)
            print(f"     {toolNum} ::   {fn}")

    print(" ")

    return available


# Test functions
def test_00():
    """
    test_00()
    Simple test function to test functions in this macro.
    """

    doc = FreeCAD.ActiveDocument
    print(f"test_00 active document: {doc.Name}")

    # Create simple cube as base model for Job object
    cube = doc.addObject("Part::Box", "Box")
    cube.Label = "Cube"

    # Create new Job object
    job = add_job([cube])

    # Identify available tools
    toolNames = available_tool_filenames()
    if len(toolNames) == 0:
        print("No tool files found.")
        return

    # Add tool by file name
    print(f"test_00 tool by name: {toolNames[3]}")
    add_toolcontroller_by_filename(job, toolNames[3])

    # Add tool by number from available tools list, above
    print(f"test_00 tool by number: 5")
    add_toolcontroller_by_number(job, 5)


print(f"Job Utilities {__version__} module imported")
