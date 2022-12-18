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
import Path.Log as PathLog
import PathScripts.PathUtils as PathUtils
import Path
import Part
import Path.Geom as PathGeom
import math
import Generator_Utilities


__title__ = "Path Spiral Path Generator"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "."


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())

isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
showDebugShapes = False


_face = None
_centerOfMass = None
_centerOfPattern = None
_halfDiag = None
_halfPasses = None
_isCenterSet = False
_startPoint = None
_toolRadius = None
patternCenterAtChoices = ("CenterOfMass", "CenterOfBoundBox", "XminYmin", "Custom")

_useStaticCenter = True  # Set True to use static center for all faces created by offsets and step downs.  Set False for dynamic centers based on PatternCenterAt
_targetFace = None
_retractHeight = None
_finalDepth = None
_patternCenterAt = None
_patternCenterCustom = None
_cutPatternReversed = None
_cutPatternAngle = None
_cutDirection = None
_stepOver = None
_minTravel = None  # Inactive feature
_keepToolDown = None
_jobTolerance = None
_cutOut = None


# Raw cut pattern geometry generation methods
def _Spiral():
    """_Spiral()... Returns raw set of Spiral wires at Z=0.0."""
    geomList = []
    allEdges = []
    draw = True
    loopRadians = 0.0  # Used to keep track of complete loops/cycles
    sumRadians = 0.0
    loopCnt = 0
    segCnt = 0
    twoPi = 2.0 * math.pi
    maxDist = math.ceil(
        _cutOut
        * Generator_Utilities._getRadialPasses(
            _face, _toolRadius, _cutOut, _patternCenterAt, _centerOfPattern, _halfPasses
        )
    )
    move = _centerOfPattern  # Use to translate the center of the spiral
    # FreeCAD.Console.PrintWarning(f"_Spiral() center of pattern: {_centerOfPattern}\n")
    lastPoint = _centerOfPattern

    # Set tool properties and calculate cutout
    cutOut = _cutOut / twoPi
    segLen = _cutOut / 2.0  # _sampleInterval
    stepAng = segLen / ((loopCnt + 1) * _cutOut)
    stopRadians = maxDist / cutOut

    if _cutPatternReversed:
        PathLog.debug("_Spiral() regular pattern")
        if _cutDirection == "Climb":
            getPoint = _makeRegSpiralPnt
        else:
            getPoint = _makeOppSpiralPnt

        while draw:
            radAng = sumRadians + stepAng
            p1 = lastPoint
            p2 = getPoint(
                move, cutOut, radAng
            )  # cutOut is 'b' in the equation r = b * radAng
            sumRadians += stepAng  # Increment sumRadians
            loopRadians += stepAng  # Increment loopRadians
            if loopRadians > twoPi:
                loopCnt += 1
                loopRadians -= twoPi
                stepAng = segLen / (
                    (loopCnt + 1) * _cutOut
                )  # adjust stepAng with each loop/cycle
            # Create line and show in Object tree
            lineSeg = Part.makeLine(p1, p2)
            allEdges.append(lineSeg)
            # increment loop items
            segCnt += 1
            lastPoint = p2
            if sumRadians > stopRadians:
                draw = False
        # Ewhile
    else:
        PathLog.debug("_Spiral() REVERSED pattern")
        if _cutDirection == "Conventional":
            getPoint = _makeOppSpiralPnt
        else:
            getPoint = _makeRegSpiralPnt

        while draw:
            radAng = sumRadians + stepAng
            p1 = lastPoint
            p2 = getPoint(
                move, cutOut, radAng
            )  # cutOut is 'b' in the equation r = b * radAng
            sumRadians += stepAng  # Increment sumRadians
            loopRadians += stepAng  # Increment loopRadians
            if loopRadians > twoPi:
                loopCnt += 1
                loopRadians -= twoPi
                stepAng = segLen / (
                    (loopCnt + 1) * _cutOut
                )  # adjust stepAng with each loop/cycle
            segCnt += 1
            lastPoint = p2
            if sumRadians > stopRadians:
                draw = False
            # Create line and show in Object tree
            lineSeg = Part.makeLine(p2, p1)
            allEdges.append(lineSeg)
        # Ewhile
        allEdges.reverse()
    # Eif

    spiral = Part.Wire(allEdges)
    geomList.append(spiral)

    return geomList


def _makeRegSpiralPnt(move, b, radAng):
    """_makeRegSpiralPnt(move, b, radAng)... Return next point on regular spiral pattern."""
    x = b * radAng * math.cos(radAng)
    y = b * radAng * math.sin(radAng)
    return FreeCAD.Vector(x, y, 0.0).add(move)


def _makeOppSpiralPnt(move, b, radAng):
    """_makeOppSpiralPnt(move, b, radAng)... Return next point on opposite(reversed) spiral pattern."""
    x = b * radAng * math.cos(radAng)
    y = b * radAng * math.sin(radAng)
    return FreeCAD.Vector(-1 * x, y, 0.0).add(move)


def _generatePathGeometry():
    """_generatePathGeometry()... Control function that generates path geometry wire sets."""
    Generator_Utilities._debugMsg("_generatePathGeometry()")
    global _rawPathGeometry

    rawGeoList = _Spiral()

    # Create compound object to bind all geometry
    # geomShape = Part.makeCompound(_rawGeoList)

    # Generator_Utilities._addDebugShape(geomShape, "rawPathGeomShape")  # Debugging

    # Identify intersection of cross-section face and lineset
    # rawWireSet = Part.makeCompound(geomShape.Wires)
    rawWireSet = Part.makeCompound(rawGeoList)
    _rawPathGeometry = _face.common(rawWireSet)

    Generator_Utilities._addDebugShape(_rawPathGeometry, "rawPathGeometry")  # Debugging

    return _Link_Regular(_rawPathGeometry)


# Path linking function
def _Link_Regular(rawPathGeometry):
    """_Link_Regular()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""

    def sortWires0(wire):
        return wire.Edges[0].Vertexes[0].Point.sub(_centerOfPattern).Length

    def sortWires1(wire):
        eIdx = len(wire.Edges) - 1
        return wire.Edges[eIdx].Vertexes[1].Point.sub(_centerOfPattern).Length

    if _cutPatternReversed:
        # Center outward
        return sorted(rawPathGeometry.Wires, key=sortWires0)
    else:
        # Outside inward
        return sorted(rawPathGeometry.Wires, key=sortWires1, reverse=True)


# 3D projected wire linking functions
def _Link_Projected(wireList, cutDirection, cutReversed=False):
    """_Link_Projected(wireList, cutDirection, cutReversed=False)... Apply necessary linking and orientation to 3D wires."""
    FreeCAD.Console.PrintError("_Link_Projected() `cutReversed` flag not active.\n")
    if cutDirection == "Clockwise":
        return _link_spiral_projected_clockwise(wireList)
    else:
        return _link_spiral_projected_counterclockwise(wireList)


def _link_spiral_projected_clockwise(projectionWires):
    sortedWires = []
    # return sortedWires
    return projectionWires


def _link_spiral_projected_counterclockwise(projectionWires):
    sortedWires = []
    # return sortedWires
    return projectionWires


# Geometry to paths methods
def _buildStartPath(toolController):
    """_buildStartPath() ... Convert Offset pattern wires to paths."""
    Generator_Utilities._debugMsg("_buildStartPath()")

    _vertRapid = toolController.VertRapid.Value
    _horizRapid = toolController.HorizRapid.Value

    useStart = False
    if _startPoint:
        useStart = True

    paths = [Path.Command("G0", {"Z": _retractHeight, "F": _vertRapid})]
    if useStart:
        paths.append(
            Path.Command(
                "G0",
                {
                    "X": _startPoint.x,
                    "Y": _startPoint.y,
                    "F": _horizRapid,
                },
            )
        )

    return paths


def _buildLinePaths(pathGeometry, toolController):
    """_buildLinePaths() ... Convert Line-based wires to paths."""
    Generator_Utilities._debugMsg("_buildLinePaths()")

    paths = []
    wireList = pathGeometry
    _vertFeed = toolController.VertFeed.Value
    _vertRapid = toolController.VertRapid.Value
    _horizFeed = toolController.HorizFeed.Value
    _horizRapid = toolController.HorizRapid.Value

    for wire in wireList:
        if _finalDepth is not None:
            wire.translate(FreeCAD.Vector(0, 0, _finalDepth))

        e0 = wire.Edges[0]

        if _finalDepth is None:
            finalDepth = e0.Vertexes[0].Z
        else:
            finalDepth = _finalDepth

        paths.append(
            Path.Command(
                "G0",
                {
                    "X": e0.Vertexes[0].X,
                    "Y": e0.Vertexes[0].Y,
                    "F": _horizRapid,
                },
            )
        )
        paths.append(
            # Path.Command("G0", {"Z": self.prevDepth + 0.1, "F": self.vertRapid})
            Path.Command("G0", {"Z": _retractHeight, "F": _vertRapid})
        )
        paths.append(Path.Command("G1", {"Z": finalDepth, "F": _vertFeed}))

        for e in wire.Edges:
            paths.extend(PathGeom.cmdsForEdge(e, hSpeed=_horizFeed, vSpeed=_vertFeed))

        paths.append(
            # Path.Command("G0", {"Z": self.safeHeight, "F": self.vertRapid})
            Path.Command("G0", {"Z": _retractHeight, "F": _vertRapid})
        )

    Generator_Utilities._debugMsg("_buildLinePaths() path count: {}".format(len(paths)))
    return paths


def geometryToGcode(lineGeometry, toolController, retractHeight, finalDepth=None):
    """geometryToGcode(lineGeometry) Return line geometry converted to Gcode"""
    Generator_Utilities._debugMsg("geometryToGcode()")
    global _retractHeight
    global _finalDepth

    # Argument validation
    if not type(retractHeight) is float:
        raise ValueError("Retract height must be a float")

    if not type(finalDepth) is float and finalDepth is not None:
        raise ValueError("Final depth must be a float")

    if finalDepth is not None and finalDepth > retractHeight:
        raise ValueError("Retract height must be greater than or equal to final depth\n")

    _retractHeight = retractHeight
    _finalDepth = finalDepth

    commandList = _buildLinePaths(lineGeometry, toolController)
    if len(commandList) > 0:
        commands = _buildStartPath(toolController)
        commands.extend(commandList)
        return commands
    else:
        Generator_Utilities._debugMsg("No commands in commandList")
    return []


def generatePathGeometry(
    targetFace,
    toolRadius,
    stepOver,
    patternCenterAt,
    patternCenterCustom,
    cutPatternAngle,
    cutPatternReversed,
    cutDirection,
    minTravel,
    keepToolDown,
    jobTolerance,
):
    """_init_(
                targetFace,
                patternCenterAt,
                patternCenterCustom,
                cutPatternReversed,
                cutPatternAngle,
                cutPattern,
                cutDirection,
                stepOver,
                materialAllowance,
                minTravel,
                keepToolDown,
                toolController,
                jobTolerance)...
    PathGeometryGenerator class constructor method.
    """
    """PathGeometryGenerator() class...
    Generates a path geometry shape from an assigned pattern for conversion to tool paths.
    Arguments:
        targetFace:         face shape to serve as base for path geometry generation
        toolRadius:         tool radius used for calculations
        stepOver:           step over percentage
        patternCenterAt:    choice of centering options
        patternCenterCustom: custom (x, y, 0.0) center point
        cutPatternReversed: boolean to reverse cut pattern from inside-out to outside-in
        cutPatternAngle:    rotation angle applied to rotatable patterns
        cutPattern:         cut pattern choice
        cutDirection:       conventional or climb
        minTravel:          boolean to enable minimum travel (feature not enabled at this time)
        keepToolDown:       boolean to enable keeping tool down (feature not enabled at this time)
        jobTolerance:       job tolerance value
    Usage:
        - Instantiate this class.
        - Call the `execute()` method to generate the path geometry. The path geometry has correctional linking applied.
        - The path geometry in now available in the `pathGeometry` attribute.
    """
    PathLog.debug("PathGeometryGenerator._init_()")

    global _targetFace
    global _patternCenterAt
    global _patternCenterCustom
    global _cutPatternReversed
    global _cutPatternAngle
    global _cutDirection
    global _stepOver
    global _minTravel
    global _keepToolDown
    global _jobTolerance
    global _cutOut
    global _isCenterSet
    global _toolRadius
    global _face
    global _centerOfPattern
    global _halfDiag
    global _cutPasses
    global _halfPasses
    global _centerOfMass

    _face = None
    _centerOfMass = None
    _centerOfPattern = None
    _halfDiag = None
    _halfPasses = None
    _rawPathGeometry = None
    _isCenterSet = False
    _offsetDirection = -1.0  # 1.0=outside;  -1.0=inside
    _endVector = None
    _targetFaceHeight = 0.0

    # Save argument values to class instance
    _targetFace = targetFace
    _patternCenterAt = patternCenterAt
    _patternCenterCustom = patternCenterCustom
    _cutPatternReversed = cutPatternReversed
    _cutPatternAngle = cutPatternAngle
    _cutDirection = cutDirection
    _stepOver = stepOver
    _minTravel = minTravel
    _keepToolDown = keepToolDown
    _jobTolerance = jobTolerance
    _toolRadius = toolRadius
    _cutOut = 2.0 * toolRadius * (_stepOver / 100.0)

    """execute()...
    Call this method to execute the path generation code in PathGeometryGenerator class.
    Returns True on success.  Access class instance `pathGeometry` attribute for path geometry.
    """
    Generator_Utilities._debugMsg("StrategyClearing.execute()")

    pathGeometry = []

    if hasattr(_targetFace, "Area") and PathGeom.isRoughly(_targetFace.Area, 0.0):
        Generator_Utilities._debugMsg(
            "PathGeometryGenerator: No area in working shape."
        )
        return pathGeometry

    if _targetFace.BoundBox.ZMin != 0.0:
        _targetFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - _targetFace.BoundBox.ZMin))

    #  Apply simple radius shrinking offset for clearing pattern generation.
    ofstVal = _offsetDirection * (_toolRadius - (_jobTolerance / 10.0))
    offsetWF = PathUtils.getOffsetArea(_targetFace, ofstVal)
    if not offsetWF:
        Generator_Utilities._debugMsg("getOffsetArea() failed")
    elif len(offsetWF.Faces) == 0:
        Generator_Utilities._debugMsg("No offset faces to process for path geometry.")
    else:
        for fc in offsetWF.Faces:
            # fc.translate(FreeCAD.Vector(0.0, 0.0, _targetFaceHeight))

            useFaces = fc
            if useFaces.Faces:
                for f in useFaces.Faces:
                    f.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - f.BoundBox.ZMin))
                    _face = f
                    (
                        _centerOfPattern,
                        _halfDiag,
                        _cutPasses,
                        _halfPasses,
                        _centerOfMass,
                    ) = Generator_Utilities._prepareAttributes(
                        _face,
                        _toolRadius,
                        _cutOut,
                        _isCenterSet,
                        _useStaticCenter,
                        _patternCenterAt,
                        _patternCenterCustom,
                    )
                    pathGeom = _generatePathGeometry()
                    pathGeometry.extend(pathGeom)
            else:
                Generator_Utilities._debugMsg(
                    "No offset faces after cut with base shape."
                )

    # Generator_Utilities._debugMsg("Path with params: {}".format(_pathParams))

    return pathGeometry
