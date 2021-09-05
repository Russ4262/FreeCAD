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
import FreeCAD
import Path
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

__title__ = "Path ZigZag Clearing Generator"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Generates the zigzag clearing toolpath for a single 2D face"


if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class ZigZagClearingGenerator:
    """ZigZagClearingGenerator() class...
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
        ZigZagClearingGenerator class constructor method.
        """
        PathLog.debug("ZigZagClearingGenerator.__init__()")
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
        self.stepDown = 0.0

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
        self.keepDownThreshold = self.toolDiameter * 0.8

        self.targetFace.translate(
            FreeCAD.Vector(0.0, 0.0, 0.0 - self.targetFace.BoundBox.ZMin)
        )

    def _debugMsg(self, msg, isError=False):
        """_debugMsg(msg)
        If `self.isDebug` flag is True, the provided message is printed in the Report View.
        If not, then the message is assigned a debug status.
        """
        if isError:
            PathLog.error("ZigZagClearingGenerator: " + msg + "\n")
            return

        if self.isDebug:
            # PathLog.info(msg)
            FreeCAD.Console.PrintMessage("ZigZagClearingGenerator: " + msg + "\n")
        else:
            PathLog.debug(msg)

    def _addDebugShape(self, shape, name="debug"):
        if self.isDebug and self.showDebugShapes:
            do = FreeCAD.ActiveDocument.addObject("Part::Feature", "debug_" + name)
            do.Shape = shape
            do.purgeTouched()

    # Raw cut pattern geometry generation methods
    def _ZigZag(self):
        """_ZigZag()... Returns raw set of ZigZag wires at Z=0.0."""
        geomList = list()
        centRot = FreeCAD.Vector(
            0.0, 0.0, 0.0
        )  # Bottom left corner of face/selection/model
        segLength = self.halfDiag
        if self.patternCenterAt == "XminYmin":
            segLength = 2.0 * self.halfDiag

        # Create end points for set of lines to intersect with cross-section face
        pntTuples = list()
        direction = 1
        for lc in range((-1 * (self.halfPasses - 1)), self.halfPasses + 1):
            x1 = centRot.x - segLength
            x2 = centRot.x + segLength
            y1 = centRot.y + (lc * self.cutOut)
            # y2 = y1
            if direction == 1:
                p1 = FreeCAD.Vector(x1, y1, 0.0)
                p2 = FreeCAD.Vector(x2, y1, 0.0)
            else:
                p1 = FreeCAD.Vector(x2, y1, 0.0)
                p2 = FreeCAD.Vector(x1, y1, 0.0)
            pntTuples.append((p1, p2))
            # swap direction
            direction *= -1

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

        self.rawGeoList = self._ZigZag()

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

    def _linkRectangular(self, upHeight, trgtX, trgtY, downHeight):
        paths = list()
        prevDepth = self.prevDepth + 0.5  # 1/2 mm buffer
        # Rapid retraction
        paths.append(Path.Command("G0", {"Z": upHeight, "F": self.vertRapid}))
        # Rapid lateral move
        paths.append(Path.Command("G0", {"X": trgtX, "Y": trgtY, "F": self.horizRapid}))
        if self.stepDown:
            # Rapid decent to previous depth
            paths.append(Path.Command("G0", {"Z": prevDepth, "F": self.vertRapid}))
        paths.append(
            Path.Command("G1", {"Z": downHeight, "F": self.vertFeed})
        )  # Plunge at vertical feed rate
        return paths

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

    def _buildZigZagPaths(self):
        """_buildZigZagPaths() ... Convert ZigZag-based wires to paths."""
        self._debugMsg("_buildZigZagPaths()")

        if not self.keepToolDown:
            return self._buildLinePaths()

        # Proceed with KeepToolDown proceedure
        paths = []
        height = self.finalDepth
        wireList = self.pathGeometry
        self._buildStartPath()

        lastPnt = None
        for wire in wireList:
            wire.translate(FreeCAD.Vector(0, 0, height))
            eCnt = len(wire.Edges)
            e0 = wire.Edges[0]
            pnt0 = e0.Vertexes[0].Point

            if lastPnt:
                if lastPnt.sub(
                    pnt0
                ).Length < self.keepDownThreshold and isHorizontalCutSafe(
                    self.toolDiameter, self.targetFace, lastPnt, pnt0, maxWidth=0.0002
                ):
                    paths.append(
                        Path.Command(
                            "G1",
                            {
                                "X": pnt0.x,
                                "Y": pnt0.y,
                                "F": self.horizFeed,
                            },
                        )
                    )
                else:
                    paths.extend(
                        self._linkRectangular(
                            self.retractHeight, pnt0.x, pnt0.y, height
                        )
                    )
            else:
                paths.append(
                    Path.Command("G0", {"Z": self.retractHeight, "F": self.vertFeed})
                )
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
                paths.append(Path.Command("G1", {"Z": height, "F": self.vertFeed}))

            for i in range(0, eCnt):
                paths.extend(PathGeom.cmdsForEdge(wire.Edges[i], hSpeed=self.horizFeed))

            # Save last point
            lastEdgeVertexes = wire.Edges[eCnt - 1].Vertexes
            lastPnt = lastEdgeVertexes[len(lastEdgeVertexes) - 1].Point
        # Efor

        self._debugMsg("_buildZigZagPaths() path count: {}".format(len(paths)))

        return paths

    # Public methods
    def generate(self):
        """generate()...
        Call this method to execute the path generation code in ZigZagClearingGenerator class.
        Returns True on success.  Access class instance `pathGeometry` attribute for path geometry.
        """
        self._debugMsg("StrategyClearing.generate()")

        self.commandList = list()  # Reset list
        self.pathGeometry = list()  # Reset list
        self.isCenterSet = False

        if hasattr(self.targetFace, "Area") and PathGeom.isRoughly(
            self.targetFace.Area, 0.0
        ):
            self._debugMsg("ZigZagClearingGenerator: No area in working shape.")
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

        return self.startCommands + self._buildZigZagPaths()

    # Eclass


def isHorizontalCutSafe(toolDiameter, face, p1, p2, maxWidth=0.0002):
    """Make simple circle with diameter of tool, at start and end points, then fuse with rectangle.
    Check for collision using face.
    maxWidth=0.0002 might need adjustment."""
    # Make path travel of tool as 3D solid.
    rad = toolDiameter / 2.0 - 0.000001

    def getPerp(p1, p2, dist):
        toEnd = p2.sub(p1)
        perp = FreeCAD.Vector(-1 * toEnd.y, toEnd.x, 0.0)
        if perp.x == 0 and perp.y == 0:
            return perp
        perp.normalize()
        perp.multiply(dist)
        return perp

    # Make first cylinder
    ce1 = Part.Wire(Part.makeCircle(rad, p1).Edges)
    C1 = Part.Face(ce1)
    C1.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - C1.BoundBox.ZMin))
    startShp = C1

    if p2.sub(p1).Length > 0:
        # Make second cylinder
        ce2 = Part.Wire(Part.makeCircle(rad, p2).Edges)
        C2 = Part.Face(ce2)
        C2.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - C2.BoundBox.ZMin))
        endShp = C2

        # Make extruded rectangle to connect cylinders
        perp = getPerp(p1, p2, rad)
        v1 = p1.add(perp)
        v2 = p1.sub(perp)
        v3 = p2.sub(perp)
        v4 = p2.add(perp)
        e1 = Part.makeLine(v1, v2)
        e2 = Part.makeLine(v2, v3)
        e3 = Part.makeLine(v3, v4)
        e4 = Part.makeLine(v4, v1)
        edges = Part.__sortEdges__([e1, e2, e3, e4])
        rectFace = Part.Face(Part.Wire(edges))
        rectFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - rectFace.BoundBox.ZMin))
        boxShp = rectFace

        # Fuse two cylinders and box together
        part1 = startShp.fuse(boxShp)
        pathTravel = part1.fuse(endShp).removeSplitter()
    else:
        pathTravel = startShp

    # Check for collision with model
    vLen = p2.sub(p1).Length
    try:
        cmn = face.common(pathTravel)
        width = abs(pathTravel.Area - cmn.Area) / vLen
        if width < maxWidth:
            return True
    except Exception:
        PathLog.debug("Failed to complete path collision check.")

    return False


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
    lcg = ZigZagClearingGenerator(
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
