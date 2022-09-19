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
import PathScripts.PathLog as PathLog
import OpsGui.PathOpGui2 as PathOpGui2
import Taskpanels.PathTaskPanelPage as PathTaskPanelPage

from PySide import QtCore, QtGui

__title__ = "Base for Circular Hole based operations' UI"
__author__ = "sliptonic (Brad Collette)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Implementation of circular hole specific base geometry page controller."

LOGLEVEL = False

if LOGLEVEL:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.NOTICE, PathLog.thisModule())

# class TaskPanelOpPage(PathOpGui2.TaskPanelPage):
class TaskPanelOpPage(PathTaskPanelPage.TaskPanelPage):
    """Base class for circular hole based operation's page controller."""

    #def taskPanelBaseGeometryPage(self, obj, features):
    #    """taskPanelBaseGeometryPage(obj, features) ... Return circular hole specific page controller for Base Geometry."""
    #    return TaskPanelHoleGeometryPage(obj, features)
    pass
