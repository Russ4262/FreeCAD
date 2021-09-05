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


import PathScripts.PathLog as PathLog
import Path
import numpy

__title__ = "Path Line Clearing Generator"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Generates the line-clearing toolpath for a single 2D face"


if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


def generate_orig(edge, dwelltime=0.0, peckdepth=0.0, repeat=1):

    startPoint = edge.Vertexes[0].Point
    endPoint = edge.Vertexes[1].Point

    PathLog.debug(startPoint)
    PathLog.debug(endPoint)

    PathLog.debug(numpy.isclose(startPoint.sub(endPoint).x, 0, rtol=1e-05, atol=1e-06))
    PathLog.debug(numpy.isclose(startPoint.sub(endPoint).y, 0, rtol=1e-05, atol=1e-06))
    PathLog.debug(endPoint)

    if repeat < 1:
        raise ValueError("repeat must be 1 or greater")

    if not type(repeat) is int:
        raise ValueError("repeat value must be an integer")

    if not type(peckdepth) is float:
        raise ValueError("peckdepth must be a float")

    if not type(dwelltime) is float:
        raise ValueError("dwelltime must be a float")

    if not (
        numpy.isclose(startPoint.sub(endPoint).x, 0, rtol=1e-05, atol=1e-06)
        and (numpy.isclose(startPoint.sub(endPoint).y, 0, rtol=1e-05, atol=1e-06))
    ):
        raise ValueError("edge is not aligned with Z axis")

    cmdParams = {}
    cmdParams["X"] = startPoint.x
    cmdParams["Y"] = startPoint.y
    cmdParams["Z"] = endPoint.z
    cmdParams["R"] = startPoint.z

    if repeat > 1:
        cmdParams["L"] = repeat

    if peckdepth == 0.0:
        if dwelltime > 0.0:
            cmd = "G82"
            cmdParams["P"] = dwelltime
        else:
            cmd = "G81"
    else:
        cmd = "G83"
        cmdParams["Q"] = peckdepth

    return [Path.Command(cmd, cmdParams)]


import FreeCAD
import Path
import PathScripts.PathLog as PathLog
import PathScripts.PathUtils as PathUtils

from PySide import QtCore

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader

Part = LazyLoader("Part", globals(), "Part")
DraftGeomUtils = LazyLoader("DraftGeomUtils", globals(), "DraftGeomUtils")
PathGeom = LazyLoader("PathScripts.PathGeom", globals(), "PathScripts.PathGeom")
PathOpTools = LazyLoader(
    "PathScripts.PathOpTools", globals(), "PathScripts.PathOpTools"
)
# time = LazyLoader('time', globals(), 'time')
json = LazyLoader("json", globals(), "json")
math = LazyLoader("math", globals(), "math")
area = LazyLoader("area", globals(), "area")

if FreeCAD.GuiUp:
    coin = LazyLoader("pivy.coin", globals(), "pivy.coin")
    FreeCADGui = LazyLoader("FreeCADGui", globals(), "FreeCADGui")


__title__ = "Path Strategies"
__author__ = "Yorik van Havre; sliptonic (Brad Collette)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Path strategies available for path generation."
__contributors__ = ""


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class LineClearingGenerator:
    """LineClearingGenerator() class...
    Generates a path geometry shape from an assigned pattern for conversion to tool paths.
    Arguments:
        targetFace:         face shape to serve as base for path geometry generation
        patternCenterAt:    choice of centering options
        patternCenterCustom: custom (x, y, 0.0) center point
        cutPatternReversed: boolean to reverse cut pattern from inside-out to outside-in
        cutPatternAngle:    rotation angle applied to rotatable patterns
        cutDirection:       conventional or climb
        stepOver:           step over percentage
        minTravel:          boolean to enable minimum travel (feature not enabled at this time)
        keepToolDown:       boolean to enable keeping tool down (feature not enabled at this time)
        toolController:     instance of tool controller to be used
        jobTolerance:       job tolerance value
    Available Patterns:
        - Adaptive, Circular, CircularZigZag, Grid, Line, LineOffset, Offset, Spiral, Triangle, ZigZag, ZigZagOffset
    Usage:
        - Instantiate this class.
        - Call the `generate()` method to generate the path geometry. The path geometry has correctional linking applied.
        - The path geometry in now available in the `pathGeometry` attribute.
    """

    patternCenterAtChoices = ("CenterOfMass", "CenterOfBoundBox", "XminYmin", "Custom")

    def __init__(
        self,
        targetFace,
        toolController,
        retractHeight,
        finalDepth,
        stepOver=40.0,
        cutDirection="Conventional",
        patternCenterAt="CenterOfBoundBox",
        patternCenterCustom=FreeCAD.Vector(0.0, 0.0, 0.0),
        cutPatternAngle=0.0,
        cutPatternReversed=False,
        minTravel=False,
        keepToolDown=False,
        jobTolerance=0.001,
    ):
        """__init__(targetFace,
                toolController,
                retractHeight,
                finalDepth,
                stepOver,
                cutDirection,
                patternCenterAt,
                patternCenterCustom,
                cutPatternAngle,
                cutPatternReversed,
                minTravel,
                keepToolDown,
                jobTolerance)...
        LineClearingGenerator class constructor method.
        """
        PathLog.debug("LineClearingGenerator.__init__()")
        PathLog.track(
            "(tool controller: {}\n final depth {}\n step over {}\n pattern center at {}\n pattern center custom ({}, {}, {})\n cut pattern angle {}\n cutPatternReversed {}\n cutDirection {}\n minTravel {}\n keepToolDown {}\n jobTolerance {})".format(
                toolController.Label,
                finalDepth,
                stepOver,
                patternCenterAt,
                patternCenterCustom.x,
                patternCenterCustom.y,
                patternCenterCustom.z,
                cutPatternAngle,
                cutPatternReversed,
                cutDirection,
                minTravel,
                keepToolDown,
                jobTolerance,
            )
        )

        # Argument validation
        if not type(retractHeight) is float:
            raise ValueError("Retract height must be a float")

        if not type(finalDepth) is float:
            raise ValueError("Final depth must be a float")

        if finalDepth > retractHeight:
            raise ValueError(
                "Retract height must be greater than or equal to final depth"
            )

        if not type(stepOver) is float:
            raise ValueError("Step over must be a float")

        if stepOver < 0.1 or stepOver > 100.0:
            raise ValueError("Step over exceeds limits")

        if patternCenterAt not in self.patternCenterAtChoices:
            raise ValueError("Invalid value for 'patternCenterAt' argument")

        if not type(patternCenterCustom) is FreeCAD.Vector:
            raise ValueError("Pattern center custom must be a FreeCAD vector")

        if not type(cutPatternAngle) is float:
            raise ValueError("Cut pattern angle must be a float")

        if not type(cutPatternReversed) is bool:
            raise ValueError("Cut pattern reversed must be a boolean")

        if not type(minTravel) is bool:
            raise ValueError("Min travel must be a boolean")

        if cutDirection not in ("Conventional", "Climb"):
            raise ValueError("Invalid value for 'cutDirection' argument")

        if not type(keepToolDown) is bool:
            raise ValueError("Keep tool down must be a boolean")

        # Debugging attributes
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        self.showDebugShapes = False

        self.face = None
        self.rawGeoList = None
        self.centerOfMass = None
        self.centerOfPattern = None
        self.halfDiag = None
        self.halfPasses = None
        self.workingPlane = Part.makeCircle(2.0)  # make circle for workplane
        self.rawPathGeometry = None
        self.linkedPathGeom = None
        self.pathGeometry = list()
        self.commandList = list()
        self.useStaticCenter = True  # Set True to use static center for all faces created by offsets and step downs.  Set False for dynamic centers based on PatternCenterAt
        self.isCenterSet = False
        self.endVector = None
        self.startCommands = list()
        self.startPoint = None

        # Save argument values to class instance
        self.targetFace = targetFace
        self.toolController = toolController
        self.retractHeight = retractHeight
        self.finalDepth = finalDepth
        self.patternCenterAt = patternCenterAt
        self.patternCenterCustom = patternCenterCustom
        self.cutPatternReversed = cutPatternReversed
        self.cutPatternAngle = cutPatternAngle
        self.cutDirection = cutDirection
        self.stepOver = stepOver
        self.minTravel = minTravel
        self.keepToolDown = keepToolDown
        self.jobTolerance = jobTolerance
        self.prevDepth = retractHeight

        self.vertFeed = toolController.VertFeed.Value
        self.vertRapid = toolController.VertRapid.Value
        self.horizFeed = toolController.HorizFeed.Value
        self.horizRapid = toolController.HorizRapid.Value
        self.toolDiameter = (
            toolController.Tool.Diameter.Value
            if hasattr(toolController.Tool.Diameter, "Value")
            else float(toolController.Tool.Diameter)
        )

        self.toolRadius = self.toolDiameter / 2.0
        self.cutOut = self.toolDiameter * (self.stepOver / 100.0)

        self.targetFace.translate(
            FreeCAD.Vector(0.0, 0.0, 0.0 - self.targetFace.BoundBox.ZMin)
        )

    def _debugMsg(self, msg, isError=False):
        """_debugMsg(msg)
        If `self.isDebug` flag is True, the provided message is printed in the Report View.
        If not, then the message is assigned a debug status.
        """
        if isError:
            PathLog.error("LineClearingGenerator: " + msg + "\n")
            return

        if self.isDebug:
            # PathLog.info(msg)
            FreeCAD.Console.PrintMessage("LineClearingGenerator: " + msg + "\n")
        else:
            PathLog.debug(msg)

    def _addDebugShape(self, shape, name="debug"):
        if self.isDebug and self.showDebugShapes:
            do = FreeCAD.ActiveDocument.addObject("Part::Feature", "debug_" + name)
            do.Shape = shape
            do.purgeTouched()

    # Raw cut pattern geometry generation methods
    def _Line(self):
        """_Line()... Returns raw set of Line wires at Z=0.0."""
        geomList = list()
        centRot = FreeCAD.Vector(
            0.0, 0.0, 0.0
        )  # Bottom left corner of face/selection/model
        segLength = self.halfDiag
        if self.patternCenterAt in ["XminYmin", "Custom"]:
            segLength = 2.0 * self.halfDiag

        # Create end points for set of lines to intersect with cross-section face
        pntTuples = list()
        for lc in range((-1 * (self.halfPasses - 1)), self.halfPasses + 1):
            x1 = centRot.x - segLength
            x2 = centRot.x + segLength
            y1 = centRot.y + (lc * self.cutOut)
            # y2 = y1
            p1 = FreeCAD.Vector(x1, y1, 0.0)
            p2 = FreeCAD.Vector(x2, y1, 0.0)
            pntTuples.append((p1, p2))

        # Convert end points to lines

        if (self.cutDirection == "Climb" and not self.cutPatternReversed) or (
            self.cutDirection != "Climb" and self.cutPatternReversed
        ):
            for (p2, p1) in pntTuples:
                wire = Part.Wire([Part.makeLine(p1, p2)])
                geomList.append(wire)
        else:
            for (p1, p2) in pntTuples:
                wire = Part.Wire([Part.makeLine(p1, p2)])
                geomList.append(wire)

        if self.cutPatternReversed:
            geomList.reverse()

        return geomList

    # Path linking method
    def _Link_Line(self):
        """_Link_Line()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
        allGroups = list()
        allWires = list()

        def isOriented(direction, p0, p1):
            oriented = p1.sub(p0).normalize()
            if PathGeom.isRoughly(direction.sub(oriented).Length, 0.0):
                return True
            return False

        i = 0
        edges = self.rawPathGeometry.Edges
        limit = len(edges)

        if limit == 0:
            PathLog.debug("no edges to link")
            return allWires

        e = edges[0]
        p0 = e.Vertexes[0].Point
        p1 = e.Vertexes[1].Point
        vect = p1.sub(p0)
        targetAng = math.atan2(vect.y, vect.x)
        group = [(edges[0], vect.Length)]
        direction = p1.sub(p0).normalize()

        for i in range(1, limit):
            # get next edge
            ne = edges[i]
            np0 = ne.Vertexes[0].Point  # Next point 0
            np1 = ne.Vertexes[1].Point  # Next point 1
            diff = np1.sub(p0)
            nxtAng = math.atan2(diff.y, diff.x)

            # Check if prev and next are colinear
            angDiff = abs(nxtAng - targetAng)
            if 0.000001 > angDiff:
                if isOriented(direction, np0, np1):
                    group.append((ne, np1.sub(p0).Length))
                else:
                    # PathLog.info("flipping line")
                    line = Part.makeLine(np1, np0)  # flip line segment
                    group.append((line, np1.sub(p0).Length))
            else:
                # Save current group
                allGroups.append(group)
                # Rotate edge and point value
                e = ne
                p0 = np0
                # Create new group
                group = [(ne, np1.sub(p0).Length)]

        allGroups.append(group)

        for g in allGroups:
            if len(g) == 1:
                wires = [Part.Wire([g[0][0]])]
            else:
                g.sort(key=lambda grp: grp[1])
                wires = [Part.Wire([edg]) for edg, __ in g]
            allWires.extend(wires)

        return allWires

    # Support methods
    def _prepareAttributes(self):
        """_prepareAttributes()... Prepare instance attribute values for path generation."""
        if self.isCenterSet:
            if self.useStaticCenter:
                return

        # Compute weighted center of mass of all faces combined
        if self.patternCenterAt == "CenterOfMass":
            comF = self.face.CenterOfMass
            self.centerOfMass = FreeCAD.Vector(comF.x, comF.y, 0.0)
        self.centerOfPattern = self._getPatternCenter()

        # calculate line length
        deltaC = self.targetFace.BoundBox.DiagonalLength
        lineLen = deltaC + (
            2.0 * self.toolDiameter
        )  # Line length to span boundbox diag with 2x cutter diameter extra on each end
        if self.patternCenterAt == "Custom":
            distToCent = self.face.BoundBox.Center.sub(self.centerOfPattern).Length
            lineLen += distToCent
        self.halfDiag = math.ceil(lineLen / 2.0)

        # Calculate number of passes
        cutPasses = (
            math.ceil(lineLen / self.cutOut) + 1
        )  # Number of lines(passes) required to cover boundbox diagonal
        if self.patternCenterAt == "Custom":
            self.halfPasses = math.ceil(cutPasses)
        else:
            self.halfPasses = math.ceil(cutPasses / 2.0)

        self.isCenterSet = True

    def _getPatternCenter(self):
        """_getPatternCenter()... Determine center of cut pattern and save in instance attribute."""
        centerAt = self.patternCenterAt

        if centerAt == "CenterOfMass":
            cntrPnt = FreeCAD.Vector(self.centerOfMass.x, self.centerOfMass.y, 0.0)
        elif centerAt == "CenterOfBoundBox":
            cent = self.face.BoundBox.Center
            cntrPnt = FreeCAD.Vector(cent.x, cent.y, 0.0)
        elif centerAt == "XminYmin":
            cntrPnt = FreeCAD.Vector(
                self.face.BoundBox.XMin, self.face.BoundBox.YMin, 0.0
            )
        elif centerAt == "Custom":
            cntrPnt = FreeCAD.Vector(
                self.patternCenterCustom.x, self.patternCenterCustom.y, 0.0
            )

        self.centerOfPattern = cntrPnt

        return cntrPnt

    def _generatePathGeometry(self):
        """_generatePathGeometry()... Control function that generates path geometry wire sets."""
        self._debugMsg("_generatePathGeometry()")

        self.rawGeoList = self._Line()

        # Create compound object to bind all geometry
        geomShape = Part.makeCompound(self.rawGeoList)

        self._addDebugShape(geomShape, "rawPathGeomShape")  # Debugging

        # Position and rotate the Line and ZigZag geometry
        if self.cutPatternAngle != 0.0:
            geomShape.Placement.Rotation = FreeCAD.Rotation(
                FreeCAD.Vector(0, 0, 1), self.cutPatternAngle
            )
        cop = self.centerOfPattern
        geomShape.Placement.Base = FreeCAD.Vector(
            cop.x, cop.y, 0.0 - geomShape.BoundBox.ZMin
        )

        self._addDebugShape(geomShape, "tmpGeometrySet")  # Debugging

        # Identify intersection of cross-section face and lineset
        rawWireSet = Part.makeCompound(geomShape.Wires)
        self.rawPathGeometry = self.face.common(rawWireSet)

        self._addDebugShape(self.rawPathGeometry, "rawPathGeometry")  # Debugging

        self.linkedPathGeom = self._Link_Line()

        return self.linkedPathGeom

    # Gcode production method
    def _buildStartPath(self):
        """_buildStartPath() ... Convert Offset pattern wires to paths."""
        self._debugMsg("_buildStartPath()")

        if len(self.startCommands) > 0:
            return

        useStart = False
        if self.startPoint:
            useStart = True

        paths = [Path.Command("G0", {"Z": self.retractHeight, "F": self.vertRapid})]
        if useStart:
            paths.append(
                Path.Command(
                    "G0",
                    {
                        "X": self.startPoint.x,
                        "Y": self.startPoint.y,
                        "F": self.horizRapid,
                    },
                )
            )

        self.startCommands = paths

    def _buildLinePaths(self):
        """_buildLinePaths() ... Convert Line-based wires to paths."""
        self._debugMsg("_buildLinePaths()")

        paths = []
        height = self.finalDepth
        wireList = self.pathGeometry
        self._buildStartPath()

        for wire in wireList:
            wire.translate(FreeCAD.Vector(0, 0, height))

            e0 = wire.Edges[0]
            paths.append(
                Path.Command(
                    "G0",
                    {
                        "X": e0.Vertexes[0].X,
                        "Y": e0.Vertexes[0].Y,
                        "F": self.horizRapid,
                    },
                )
            )
            paths.append(
                # Path.Command("G0", {"Z": self.prevDepth + 0.1, "F": self.vertRapid})
                Path.Command("G0", {"Z": self.retractHeight, "F": self.vertRapid})
            )
            paths.append(Path.Command("G1", {"Z": height, "F": self.vertFeed}))

            for e in wire.Edges:
                paths.extend(PathGeom.cmdsForEdge(e, hSpeed=self.horizFeed))

            paths.append(
                # Path.Command("G0", {"Z": self.safeHeight, "F": self.vertRapid})
                Path.Command("G0", {"Z": self.retractHeight, "F": self.vertRapid})
            )

        self._debugMsg("_buildLinePaths() path count: {}".format(len(paths)))
        return paths

    # Public methods
    def generate(self):
        """generate()...
        Call this method to execute the path generation code in LineClearingGenerator class.
        Returns True on success.  Access class instance `pathGeometry` attribute for path geometry.
        """
        self._debugMsg("StrategyClearing.generate()")

        self.commandList = list()  # Reset list
        self.pathGeometry = list()  # Reset list
        self.isCenterSet = False

        if hasattr(self.targetFace, "Area") and PathGeom.isRoughly(
            self.targetFace.Area, 0.0
        ):
            self._debugMsg("LineClearingGenerator: No area in working shape.")
            return False

        #  Apply simple radius shrinking offset for clearing pattern generation.
        ofstVal = -1.0 * (self.toolRadius - (self.jobTolerance / 10.0))
        offsetFace = PathUtils.getOffsetArea(self.targetFace, ofstVal)
        if not offsetFace:
            self._debugMsg("getOffsetArea() failed")
        elif len(offsetFace.Faces) == 0:
            self._debugMsg("No offset faces to process for path geometry.")
        else:
            for fc in offsetFace.Faces:
                fc.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - fc.BoundBox.ZMin))

                useFaces = fc
                if useFaces.Faces:
                    for f in useFaces.Faces:
                        f.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - f.BoundBox.ZMin))
                        self.face = f
                        self._prepareAttributes()
                        pathGeom = self._generatePathGeometry()
                        self.pathGeometry.extend(pathGeom)
                else:
                    self._debugMsg("No offset faces after cut with base shape.")

        commandList = self._buildLinePaths()
        if len(commandList) > 0:
            self.commandList = self.startCommands + commandList
        else:
            self._debugMsg("No commands in commandList")

        return self.commandList


# Eclass


def generate(
    face,
    toolController,
    retractHeight,
    finalDepth,
    stepOver=40.0,
    patternCenterAt="CenterOfBoundBox",
    patternCenterCustom=FreeCAD.Vector(0.0, 0.0, 0.0),
    cutPatternAngle=0.0,
    cutPatternReversed=False,
    cutDirection="Conventional",
    minTravel=False,
    keepToolDown=False,
    jobTolerance=0.001,
):
    lcg = LineClearingGenerator(
        face,
        toolController,
        retractHeight,
        finalDepth,
        stepOver,
        cutDirection,
        patternCenterAt,
        patternCenterCustom,
        cutPatternAngle,
        cutPatternReversed,
        minTravel,
        keepToolDown,
        jobTolerance,
    )
    return lcg.generate()
