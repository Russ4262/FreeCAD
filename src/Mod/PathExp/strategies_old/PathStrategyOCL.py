# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2021 russ4262 <russ4262@gmail.com>                      *
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

from __future__ import print_function

__title__ = "Path Strategy OCL"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Classes and functions for Open CAM Library(OCL) usage."
__contributors__ = ""

OCL = None

import FreeCAD
import PathScripts.PathLog as PathLog

from PySide import QtCore

PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class OCL_Tool:
    """The OCL_Tool class is designed to translate a FreeCAD standard ToolBit shape,
    or Legacy tool type, in the active Tool Controller, into an OCL tool type."""

    def __init__(self, toolController, safe=False):
        import ocl

        self.ocl = ocl
        self.toolController = toolController
        self.tool = None
        self.tiltCutter = False
        self.safe = safe
        self.oclTool = None
        self.toolType = None
        self.toolMode = None
        self.toolMethod = None

        self.diameter = -1.0
        self.cornerRadius = -1.0
        self.flatRadius = -1.0
        self.cutEdgeHeight = -1.0
        self.cutEdgeAngle = -1.0
        # Default to zero. ToolBit likely is without.
        self.lengthOffset = 0.0

        if hasattr(toolController, "Tool"):
            self.tool = toolController.Tool
            if hasattr(self.tool, "ShapeName"):
                self.toolType = self.tool.ShapeName  # Indicates ToolBit tool
                self.toolMode = "ToolBit"
            elif hasattr(self.tool, "ToolType"):
                self.toolType = self.tool.ToolType  # Indicates Legacy tool
                self.toolMode = "Legacy"

        if self.toolType:
            PathLog.debug(
                "OCL_Tool tool mode, type: {}, {}".format(self.toolMode, self.toolType)
            )

        """
            #### FreeCAD Legacy tool shape properties per tool type
            shape = EndMill
            Diameter
            CuttingEdgeHeight
            LengthOffset

            shape = Drill
            Diameter
            CuttingEdgeAngle  # TipAngle from above, center shaft. 180 = flat tip (endmill)
            CuttingEdgeHeight
            LengthOffset

            shape = CenterDrill
            Diameter
            FlatRadius
            CornerRadius
            CuttingEdgeAngle  # TipAngle from above, center shaft. 180 = flat tip (endmill)
            CuttingEdgeHeight
            LengthOffset

            shape = CounterSink
            Diameter
            FlatRadius
            CornerRadius
            CuttingEdgeAngle  # TipAngle from above, center shaft. 180 = flat tip (endmill)
            CuttingEdgeHeight
            LengthOffset

            shape = CounterBore
            Diameter
            FlatRadius
            CornerRadius
            CuttingEdgeAngle  # TipAngle from above, center shaft. 180 = flat tip (endmill)
            CuttingEdgeHeight
            LengthOffset

            shape = FlyCutter
            Diameter
            FlatRadius
            CornerRadius
            CuttingEdgeAngle  # TipAngle from above, center shaft. 180 = flat tip (endmill)
            CuttingEdgeHeight
            LengthOffset

            shape = Reamer
            Diameter
            FlatRadius
            CornerRadius
            CuttingEdgeAngle  # TipAngle from above, center shaft. 180 = flat tip (endmill)
            CuttingEdgeHeight
            LengthOffset

            shape = Tap
            Diameter
            FlatRadius
            CornerRadius
            CuttingEdgeAngle  # TipAngle from above, center shaft. 180 = flat tip (endmill)
            CuttingEdgeHeight
            LengthOffset

            shape = SlotCutter
            Diameter
            FlatRadius
            CornerRadius
            CuttingEdgeAngle  # TipAngle from above, center shaft. 180 = flat tip (endmill)
            CuttingEdgeHeight
            LengthOffset

            shape = BallEndMill
            Diameter
            FlatRadius
            CornerRadius
            CuttingEdgeAngle  # TipAngle from above, center shaft. 180 = flat tip (endmill)
            CuttingEdgeHeight
            LengthOffset

            shape = ChamferMill
            Diameter
            FlatRadius
            CornerRadius
            CuttingEdgeAngle  # TipAngle from above, center shaft. 180 = flat tip (endmill)
            CuttingEdgeHeight
            LengthOffset

            shape = CornerRound
            Diameter
            FlatRadius
            CornerRadius
            CuttingEdgeAngle  # TipAngle from above, center shaft. 180 = flat tip (endmill)
            CuttingEdgeHeight
            LengthOffset

            shape = Engraver
            Diameter
            CuttingEdgeAngle  # TipAngle from above, center shaft. 180 = flat tip (endmill)
            CuttingEdgeHeight
            LengthOffset


            #### FreeCAD packaged ToolBit named constraints per shape files
            shape = endmill
            Diameter; Endmill diameter
            Length; Overall length of the endmill
            ShankDiameter; diameter of the shank
            CuttingEdgeHeight

            shape = ballend
            Diameter; Endmill diameter
            Length; Overall length of the endmill
            ShankDiameter; diameter of the shank
            CuttingEdgeHeight

            shape = bullnose
            Diameter; Endmill diameter
            Length; Overall length of the endmill
            ShankDiameter; diameter of the shank
            FlatRadius;Radius of the bottom flat part.
            CuttingEdgeHeight

            shape = drill
            TipAngle; Full angle of the drill tip
            Diameter; Drill bit diameter
            Length; Overall length of the drillbit

            shape = v-bit
            Diameter; Overall diameter of the V-bit
            CuttingEdgeAngle;Full angle of the v-bit
            Length; Overall  bit length
            ShankDiameter
            FlatHeight;Height of the flat extension of the v-bit
            FlatRadius; Diameter of the flat end of the tip
        """

    # Private methods
    def _setDimensions(self):
        """_setDimensions() ... Set values for possible dimensions."""
        if hasattr(self.tool, "Diameter"):
            self.diameter = float(self.tool.Diameter)
        else:
            msg = translate(
                "PathSurfaceSupport", "Diameter dimension missing from ToolBit shape."
            )
            FreeCAD.Console.PrintError(msg + "\n")
            return False
        if hasattr(self.tool, "LengthOffset"):
            self.lengthOffset = float(self.tool.LengthOffset)
        if hasattr(self.tool, "FlatRadius"):
            self.flatRadius = float(self.tool.FlatRadius)
        if hasattr(self.tool, "CuttingEdgeHeight"):
            self.cutEdgeHeight = float(self.tool.CuttingEdgeHeight)
        if hasattr(self.tool, "CuttingEdgeAngle"):
            self.cutEdgeAngle = float(self.tool.CuttingEdgeAngle)
        return True

    def _makeSafeCutter(self):
        # Make safeCutter with 25% buffer around physical cutter
        if self.safe:
            self.diameter = self.diameter * 1.25
            if self.flatRadius == 0.0:
                self.flatRadius = self.diameter * 0.25
            elif self.flatRadius > 0.0:
                self.flatRadius = self.flatRadius * 1.25

    def _oclCylCutter(self):
        # Standard End Mill, Slot cutter, or Fly cutter
        # OCL -> CylCutter::CylCutter(diameter, length)
        if self.diameter == -1.0 or self.cutEdgeHeight == -1.0:
            return
        self.oclTool = self.ocl.CylCutter(
            self.diameter, self.cutEdgeHeight + self.lengthOffset
        )

    def _oclBallCutter(self):
        # Standard Ball End Mill
        # OCL -> BallCutter::BallCutter(diameter, length)
        if self.diameter == -1.0 or self.cutEdgeHeight == -1.0:
            return
        self.tiltCutter = True
        if self.cutEdgeHeight == 0:
            self.cutEdgeHeight = self.diameter / 2
        self.oclTool = self.ocl.BallCutter(
            self.diameter, self.cutEdgeHeight + self.lengthOffset
        )

    def _oclBullCutter(self):
        # Standard Bull Nose cutter
        # Reference: https://www.fine-tools.com/halbstabfraeser.html
        # OCL -> BullCutter::BullCutter(diameter, minor radius, length)
        if (
            self.diameter == -1.0
            or self.flatRadius == -1.0
            or self.cutEdgeHeight == -1.0
        ):
            return
        self.oclTool = self.ocl.BullCutter(
            self.diameter,
            self.diameter - self.flatRadius,
            self.cutEdgeHeight + self.lengthOffset,
        )

    def _oclConeCutter(self):
        # Engraver or V-bit cutter
        # OCL -> ConeCutter::ConeCutter(diameter, angle, length)
        if (
            self.diameter == -1.0
            or self.cutEdgeAngle == -1.0
            or self.cutEdgeHeight == -1.0
        ):
            return
        self.oclTool = self.ocl.ConeCutter(
            self.diameter, self.cutEdgeAngle / 2, self.lengthOffset
        )

    def _setToolMethod(self):
        toolMap = dict()

        if self.toolMode == "Legacy":
            # Set cutter details
            # https://www.freecadweb.org/api/dd/dfe/classPath_1_1Tool.html#details
            toolMap = {
                "EndMill": "CylCutter",
                "BallEndMill": "BallCutter",
                "SlotCutter": "CylCutter",
                "Engraver": "ConeCutter",
                "Drill": "ConeCutter",
                "CounterSink": "ConeCutter",
                "FlyCutter": "CylCutter",
                "CenterDrill": "None",
                "CounterBore": "None",
                "Reamer": "None",
                "Tap": "None",
                "ChamferMill": "None",
                "CornerRound": "None",
            }
        elif self.toolMode == "ToolBit":
            toolMap = {
                "endmill": "CylCutter",
                "ballend": "BallCutter",
                "bullnose": "BullCutter",
                "drill": "ConeCutter",
                "engraver": "ConeCutter",
                "v-bit": "ConeCutter",
                "chamfer": "None",
            }
        self.toolMethod = "None"
        if self.toolType in toolMap:
            self.toolMethod = toolMap[self.toolType]

    # Public methods
    def getOclTool(self):
        """getOclTool()... Call this method after class instantiation
        to return OCL tool object."""
        # Check for tool controller and tool object
        if not self.tool or not self.toolMode:
            msg = translate("PathSurface", "Failed to identify tool for operation.")
            FreeCAD.Console.PrintError(msg + "\n")
            return None

        if not self._setDimensions():
            return None

        self._setToolMethod()

        if self.toolMethod == "None":
            err = translate(
                "PathSurface", "Failed to map selected tool to an OCL tool type."
            )
            FreeCAD.Console.PrintError(err + "\n")
            return None
        else:
            PathLog.debug("OCL_Tool tool method: {}".format(self.toolMethod))
            oclToolMethod = getattr(self, "_ocl" + self.toolMethod)
            oclToolMethod()

        if self.oclTool:
            return self.oclTool

        # Set error messages
        err = translate(
            "PathSurface", "Failed to translate active tool to OCL tool type."
        )
        FreeCAD.Console.PrintError(err + "\n")
        return None

    def useTiltCutter(self):
        """useTiltCutter()... Call this method after getOclTool() method
        to return status of cutter tilt availability - generally this
        is for a ball end mill."""
        if not self.tool or not self.oclTool:
            err = translate(
                "PathSurface",
                "OCL tool not available. Cannot determine is cutter has tilt available.",
            )
            FreeCAD.Console.PrintError(err + "\n")
            return False
        return self.tiltCutter

    def __del__(self):
        self.ocl = None
        self.toolController = None
        self.tool = None
        self.oclTool = None
        del self.ocl
        del self.toolController
        del self.tool
        del self.oclTool


# Eclass


class OpenCAMLib:
    def __init__(
        self,
        oclCutter,
        modelObject,
        finalDepth,
        depthOffset,
        sampleInterval,
        linearDeflection,
        pdc=None,
    ):
        import ocl

        self.ocl = ocl
        self.modelObject = modelObject
        self.sampleInterval = sampleInterval  # obj.SampleInterval.Value,
        self.linearDeflection = linearDeflection  # self.obj.LinearDeflection.Value
        self.finalDepth = finalDepth
        self.depthOffset = depthOffset
        self.cutter = oclCutter
        self.stl = self._makeSTL()
        if pdc is None:
            self.pdc = self._planarGetPDC()
        else:
            self.pdc = pdc

    def _planarGetPDC(self):
        pdc = self.ocl.PathDropCutter()  # create a pdc [PathDropCutter] object
        pdc.setSTL(self.stl)  # add stl model
        pdc.setCutter(self.cutter)  # add cutter
        pdc.setZ(self.finalDepth)  # set minimumZ (final / target depth value)
        pdc.setSampling(self.sampleInterval)  # set sampling size
        # print("_planarGetPDC() finaldepth = {}".format(self.finalDepth))
        return pdc

    def _makeSTL(self):
        """Convert a mesh or shape into an OCL STL, using the tessellation
        tolerance specified in obj.LinearDeflection.
        Returns an self.ocl.STLSurf()."""

        if self.modelObject.TypeId.startswith("Mesh"):
            facets = self.modelObject.Mesh.Facets.Points
        else:
            if hasattr(self.modelObject, "Shape"):
                shape = self.modelObject.Shape
            else:
                shape = self.modelObject
            vertices, facet_indices = shape.tessellate(self.linearDeflection)
            facets = (
                (vertices[f[0]], vertices[f[1]], vertices[f[2]]) for f in facet_indices
            )
        stl = self.ocl.STLSurf()
        for tri in facets:
            v1, v2, v3 = tri
            t = self.ocl.Triangle(
                self.ocl.Point(v1[0], v1[1], v1[2]),
                self.ocl.Point(v2[0], v2[1], v2[2]),
                self.ocl.Point(v3[0], v3[1], v3[2]),
            )
            stl.addTriangle(t)
        return stl

    def linearDropCut(self, start, end):
        """The `start` and `end` arguments are tuple ordered pairs (x, y) for start and end points."""
        (x1, y1) = start
        (x2, y2) = end
        path = self.ocl.Path()  # create an empty path object
        p1 = self.ocl.Point(x1, y1, 0)  # start-point of line
        p2 = self.ocl.Point(x2, y2, 0)  # end-point of line
        lo = self.ocl.Line(p1, p2)  # line-object
        path.append(lo)  # add the line to the path
        self.pdc.setPath(path)
        self.pdc.run()  # run dropcutter algorithm on path
        clp = self.pdc.getCLPoints()

        if self.depthOffset == 0.0:
            return [FreeCAD.Vector(p.x, p.y, p.z) for p in clp]
        else:
            return [FreeCAD.Vector(p.x, p.y, p.z + self.depthOffset) for p in clp]

    def circularDropCut(self, arc, cMode):
        """The `arc` argument is a tuple of three (x, y) tuples: start, end, center.
        cMode is clockwise flag: True=clockwise, False=counterclockwise."""
        path = self.ocl.Path()  # create an empty path object
        (sp, ep, cp) = arc

        # process list of segment tuples (vect, vect)
        p1 = self.ocl.Point(sp[0], sp[1], 0)  # start point of arc
        p2 = self.ocl.Point(ep[0], ep[1], 0)  # end point of arc
        cent = self.ocl.Point(cp[0], cp[1], 0)  # center point of arc
        ao = self.ocl.Arc(p1, p2, cent, cMode)  # arc object
        path.append(ao)  # add the arc to the path
        self.pdc.setPath(path)
        self.pdc.run()  # run dropcutter algorithm on path
        clp = self.pdc.getCLPoints()

        if self.depthOffset == 0.0:
            return [FreeCAD.Vector(p.x, p.y, p.z) for p in clp]
        else:
            return [FreeCAD.Vector(p.x, p.y, p.z + self.depthOffset) for p in clp]

    def __del__(self):
        self.ocl = None
        self.modelObject = None
        self.cutter = None
        self.stl = None
        self.pdc = None
        del self.ocl
        del self.modelObject
        del self.cutter
        del self.stl
        del self.pdc


# Eclass
