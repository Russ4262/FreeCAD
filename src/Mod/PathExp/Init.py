# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2020 Russell Johnson (russ4262) <russ4262@gmail.com>    *
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

__title__ = "Path Experimental Workbench"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Init.py module for Path Experimental workbench."
__contributors__ = ""


# Load the Parameter Group for this module
ParGrp = App.ParamGet("System parameter:Modules").GetGroup("PathExp")

# Set the Parameter Group details
ParGrp.SetString("HelpIndex", "PathExp/Help/index.html")
ParGrp.SetString("WorkBenchName", "PathExp")
ParGrp.SetString("WorkBenchModule", "PathExpWorkbench.py")

FreeCAD.__unit_test__ += ["TestPathExpApp"]

FreeCAD.Console.PrintMessage("Loading Path Experimental workbench...\n")
