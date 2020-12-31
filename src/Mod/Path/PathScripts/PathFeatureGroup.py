# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2014 Yorik van Havre <yorik@uncreated.net>              *
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

from PySide import QtCore
import FreeCAD
import PathScripts.PathOp as PathOp

__title__ = "Path Feature Group"
__author__ = "Russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Path Feature Group non-operation object. \
           The purpose is to provide the user some feature selction utilities \
           to assist with large, multi-feature selections."


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class ObjectFeatureGroup(PathOp.ObjectOp):
    def opFeatures(self, obj):
        return PathOp.FeatureBaseGeometry

    def initOperation(self, obj):
        pass

    def opExecute(self, obj):
        """opExecute(obj)...
        Main code to be executed. This operation produces no g-code commands."""
        pass


def SetupProperties():
    setup = []
    return setup


def Create(name, obj=None):
    '''Create(name) ... Creates and returns a Feature Group object.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectFeatureGroup(obj, name)
    return obj
