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
import Part
import PathScripts.PathGeom as PathGeom
import PathScripts.PathLog as PathLog
import PathScripts.strategies.PathTargetBuildUtils as PathTargetBuildUtils
import PathScripts.strategies.PathTargetOpenEdge as PathTargetOpenEdge
import math
from PySide import QtCore

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader

DraftGeomUtils = LazyLoader("DraftGeomUtils", globals(), "DraftGeomUtils")
PathUtils = LazyLoader("PathScripts.PathUtils", globals(), "PathScripts.PathUtils")
TechDraw = LazyLoader("TechDraw", globals(), "TechDraw")


__title__ = "Path Selection Processing"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "http://www.freecadweb.org"
__doc__ = (
    "Collection of classes and functions used to process and refine user selections."
)
__contributors__ = ""


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())

isRoughly = PathGeom.isRoughly
Tolerance = PathGeom.Tolerance
isVertical = PathGeom.isVertical
isHorizontal = PathGeom.isHorizontal

# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class AvoidCollision:
    """class AvoidCollision
    This class processes user inputs through both the Base Geometry and Extensions features,
    combining connected or overlapping regions when necessary, and returns a list
    of working areas represented by faces."""

    def __init__(
        self,
        baseObj,
        region,
        finalDepth,
        materialAllowance,
    ):
        """__init__(baseObj, region, finalDepth, materialAllowance)"""
        PathLog.debug("AvoidCollision.__init__()")

        self.baseObj = baseObj
        self.region = region
        self.finalDepth = finalDepth
        self.materialAllowance = materialAllowance

        # Debugging attributes
        self.isDebug = False
        self.showDebugShapes = False

    # Private methods
    def _debugMsg(self, msg):
        """_debugMsg(msg)
        If `self.isDebug` flag is True, the provided message is printed in the Report View.
        If not, then the message is assigned a debug status.
        """
        if self.isDebug:
            # PathLog.info(msg)
            FreeCAD.Console.PrintMessage(
                "PathAvoidCollision.Working2DAreas: " + msg + "\n"
            )
        else:
            PathLog.debug(msg)

    def _addDebugObject(self, objShape, objName="shape"):
        """_addDebugObject(objShape, objName='shape')
        If `self.isDebug` and `self.showDebugShapes` flags are True, the provided
        debug shape will be added to the active document with the provided name.
        """
        if self.isDebug and self.showDebugShapes:
            O = FreeCAD.ActiveDocument.addObject("Part::Feature", "debug_" + objName)
            O.Shape = objShape
            O.purgeTouched()

    def _applyAvoidOverhead(self, base):
        """_applyAvoidOverhead(base)...
        Create overhead regions and apply collision therewith to working shapes.
        """
        self._debugMsg("_applyAvoidOverhead({})".format(base.Name))

        if (
            not self.avoidOverhead
            or (not self.workingAreas and not self.workingHoles)
            or self.disableOverheadCheck
        ):
            return

        faceList = self.baseFacesDict[base.Name]
        faceComp = Part.makeCompound(faceList)
        self.zMin = faceComp.BoundBox.ZMax

        if isRoughly(self.finalDepth, base.Shape.BoundBox.ZMax):
            # cancel overhead collision if region is at top of model
            self._debugMsg("Canceling overhead collision check.")
            return

        overhead = self.getOverheadRegions(base, self.finalDepth)
        if not overhead:
            self._debugMsg("_applyAvoidOverhead() No overhead regions")
            return

        # self._addDebugObject(faceComp, objName="pre_overheadRegions_facesCompound")
        # self._addDebugObject(
        #    Part.makeCompound(self.workingAreas),
        #    objName="pre_overheadRegions_workingAreas",
        # )
        # self._addDebugObject(
        #    overhead, objName="{}_overheadRegions_{}".format(base.Name, self.finalDepth)
        # )

        # Cut overhead shape from working shapes
        self._debugMsg("pre-overhead area count: {}".format(len(self.workingAreas)))
        safeAreas = [ws.cut(overhead) for face in self.region.Faces]

    # Public method
    def getOverheadRegions(self, base, height):
        self._debugMsg("getOverheadRegions({}, height={}mm)".format(base.Name, height))
        # This version uses all above height collision avoidance

        if base.Name in self.overheadRegionsDict.keys():
            return self.overheadRegionsDict[base.Name]

        # orah = PathTargetBuildUtils.getOverheadRegionsAboveHeight(base.Shape, height, self.isDebug and self.showDebugShapes)
        orah = PathTargetBuildUtils.getOverheadRegionsAboveHeight(base.Shape, height)
        if orah:
            self._addDebugObject(orah, "overheadRegion_{}".format(base.Name))
        else:
            self._debugMsg("No overhead regions identified.")
        self.overheadRegionsDict[base.Name] = orah
        return orah

    def getOverheadRegions_3D(self, base, height):
        self._debugMsg(
            "getOverheadRegions_3D({}, height={}mm)".format(base.Name, height)
        )
        # This version uses 3D overhead collision

        if base.Name in self.overheadRegionsDict.keys():
            return self.overheadRegionsDict[base.Name]
        else:
            self.baseFacesDict[base.Name] = list()

        faceList = self.baseFacesDict[base.Name]
        if len(faceList) > 0:
            orah = PathTargetBuildUtils.getOverheadRegionsAboveHeight(
                base.Shape, height
            )
            # orah = getOverheadRegions3D(base.Shape, faceList)
            self.overheadRegionsDict[base.Name] = orah
            return orah
        else:
            PathLog.error("No faces for {}".format(base.Name))
        return None


# Eclass
