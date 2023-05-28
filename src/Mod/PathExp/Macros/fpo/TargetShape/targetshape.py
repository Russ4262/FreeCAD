# -*- coding: utf-8 -*-
# ***************************************************************************
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

# Project references:
# https://wiki.freecad.org/Create_a_FeaturePython_object_part_I/ru
# https://wiki.freecad.org/Create_a_FeaturePython_object_part_II/ru

import FreeCAD as App
import Part

if App.GuiUp:
    import fpo.TargetShape.gui_targetshape as gui_targetshape


def create(name=""):
    """
    Object creation method
    """

    # obj = App.ActiveDocument.addObject('App::FeaturePython', obj_name)
    if name != "":
        obj = App.ActiveDocument.addObject("Part::FeaturePython", name)
    else:
        obj = App.ActiveDocument.addObject("Part::FeaturePython", "target_shape")

    TargetShape(obj)

    if App.GuiUp:
        gui_targetshape.ViewProviderTargetShape(obj.ViewObject)
    App.ActiveDocument.recompute()
    return obj


class TargetShape:
    def __init__(self, obj):
        """
        Default constructor
        """

        self.Type = "targetshape"

        obj.Proxy = self
        obj.addProperty(
            "App::PropertyString", "Description", "Base", "Box description"
        ).Description = "Create a target shape object."
        obj.addProperty(
            "App::PropertyLength", "Length", "Dimensions", "Box length"
        ).Length = 10.0
        obj.addProperty(
            "App::PropertyLength", "Width", "Dimensions", "Box width"
        ).Width = "10 mm"
        obj.addProperty(
            "App::PropertyLength", "Height", "Dimensions", "Box height"
        ).Height = "1 cm"

    def execute(self, obj):
        """
        Called on document recompute
        """

        # Part.show(Part.makeBox(obj.Length, obj.Width, obj.Height))
        obj.Shape = Part.makeBox(obj.Length, obj.Width, obj.Height)

        print(f"Recomputing {obj.Name} ({self.Type})")
