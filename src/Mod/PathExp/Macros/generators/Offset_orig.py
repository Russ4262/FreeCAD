# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2021 Russell Johnson (russ4262) <russ4262@gmail.com>    *
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
import generators.Utilities as GenUtils
import Path.Geom as PathGeom
import Path.Op.Util as PathOpTools
import Path
import Part
import math


__title__ = "Path Offset Clearing Generator"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Generates the line-clearing toolpath for a single 2D face"


if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())

isDebug = True  # True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
showDebugShapes = False


IS_MACRO = False
MODULE_NAME = "Generator_Offset"
FEED_VERT = 0.0
FEED_HORIZ = 0.0
RAPID_VERT = 0.0
RAPID_HORIZ = 0.0

_face = None
_centerOfMass = None
_centerOfPattern = None
_halfDiag = None
_halfPasses = None
_isCenterSet = False
_startPoint = None
_toolRadius = None
_keepDownThreshold = None
_workingPlane = Part.makeCircle(5.0, FreeCAD.Vector(0.0, 0.0, 0.0))
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


# Support functions
def _offset_original():
    """_offset()...
    Returns raw set of Offset wires at Z=0.0.
    Direction of cut is taken into account.
    Additional offset loop ordering is handled in the linking method.
    """
    GenUtils._debugMsg(MODULE_NAME, "_offset()")

    wires = []
    shape = _face
    offset = -1.0 * (_toolRadius - (_jobTolerance / 10.0))  # 0.0
    direction = 0
    doLast = 0
    loop = 1

    def _get_direction(w):
        if PathOpTools._isWireClockwise(w):
            return 1
        return -1

    def _reverse_wire(w):
        rev_list = []
        for e in w.Edges:
            rev_list.append(PathUtils.reverseEdge(e))
        rev_list.reverse()
        return Part.Wire(Part.__sortEdges__(rev_list))

    if _stepOver > 49.0:
        doLast += 1

    while True:
        offsetArea = PathUtils.getOffsetArea(shape, offset, plane=_workingPlane)
        if not offsetArea:
            # Attempt clearing of residual area
            if doLast:
                doLast += 1
                offset += _cutOut / 2.0
                offsetArea = PathUtils.getOffsetArea(shape, offset, plane=_workingPlane)
                if not offsetArea:
                    # Area fully consumed
                    break
            else:
                # Area fully consumed
                break

        # set initial cut direction
        if direction == 0:
            first_face_wire = offsetArea.Faces[0].Wires[0]
            direction = _get_direction(first_face_wire)
            if direction == 1:
                direction = -1

        # process each wire within face
        for f in offsetArea.Faces:
            for w in f.Wires:
                use_direction = direction
                if _cutPatternReversed:
                    use_direction = -1 * direction
                wire_direction = _get_direction(w)
                # Process wire
                if wire_direction == use_direction:  # direction is correct
                    wire = w
                else:  # incorrect direction, so reverse wire
                    wire = _reverse_wire(w)
                wires.append(wire)

        offset -= _cutOut
        loop += 1
        if doLast > 1:
            break
    # Ewhile

    return wires


def _offset():
    """_offset()...
    Returns raw set of Offset wires at Z=0.0.
    Direction of cut is taken into account.
    Additional offset loop ordering is handled in the linking method.
    """
    GenUtils._debugMsg(MODULE_NAME, "_offset()")

    wires = []
    shape = _face
    offset = -1.0 * (_toolRadius - (_jobTolerance / 10.0))  # 0.0
    direction = 0
    doLast = 0
    loop = 1

    if _stepOver > 49.0:
        doLast += 1
    cont = True
    while cont:
        offsetArea = PathUtils.getOffsetArea(shape, offset, plane=_workingPlane)
        if not offsetArea:
            # Attempt clearing of residual area
            if doLast:
                doLast += 1
                offset += _cutOut / 2.0
                offsetArea = PathUtils.getOffsetArea(shape, offset, plane=_workingPlane)
                if not offsetArea:
                    # Area fully consumed
                    break
            else:
                # Area fully consumed
                break

        # process each wire within face
        for f in offsetArea.Faces:
            for w in f.Wires:
                wires.append(w)

        offset -= _cutOut
        loop += 1
        if doLast > 1:
            break
    # Ewhile

    return wires


def _Link_Regular(rawPathGeometry):
    """_Link_Offset()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
    sortedWires = []
    cutPatternReversed = _cutPatternReversed

    for wireGroup in rawPathGeometry:
        if cutPatternReversed:
            sortedWires.extend(sorted(wireGroup, key=lambda wire: Part.Face(wire).Area))
        else:
            sortedWires.extend(
                sorted(
                    wireGroup,
                    key=lambda wire: Part.Face(wire).Area,
                    reverse=True,
                )
            )
    return sortedWires


# 3D projected wire linking methods
def _Link_Projected(wireList, cutDirection, cutReversed=False):
    """_Link_Projected(wireList, cutDirection, cutReversed=False)... Apply necessary linking and orientation to 3D wires."""
    FreeCAD.Console.PrintError("_Link_Projected() `cutReversed` flag not active.\n")
    return wireList


# Geometry to paths methods
def _buildStartPath():
    """_buildStartPath() ... Convert Offset pattern wires to paths."""
    GenUtils._debugMsg(MODULE_NAME, "_buildStartPath()")

    useStart = False
    if _startPoint:
        useStart = True

    paths = [Path.Command("G0", {"Z": _retractHeight, "F": RAPID_VERT})]
    if useStart:
        paths.append(
            Path.Command(
                "G0",
                {
                    "X": _startPoint.x,
                    "Y": _startPoint.y,
                    "F": RAPID_HORIZ,
                },
            )
        )

    return paths


def _buildPaths(pathGeometry):
    """_buildPaths(pathGeometry) ... Convert wires to paths."""
    GenUtils._debugMsg(MODULE_NAME, "_buildPaths()")

    paths = []
    for wire in pathGeometry:
        w = wire.copy()
        if _finalDepth is not None:
            w.translate(FreeCAD.Vector(0, 0, _finalDepth))
        toolPath = Path.fromShapes(w, preamble=False)
        paths.extend(toolPath.Commands)
    return paths


# Main method to call
def generatePathGeometry(
    targetFace,
    toolRadius,
    stepOver=50.0,
    cutDirection="Clockwise",
    patternCenterAt="CenterOfBoundBox",
    patternCenterCustom=FreeCAD.Vector(0.0, 0.0, 0.0),
    cutPatternAngle=0.0,
    cutPatternReversed=False,
    minTravel=False,
    keepToolDown=False,
    jobTolerance=0.001,
):
    """generatePathGeometry()...
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
        toolRadius:         tool radius
        jobTolerance:       job tolerance value
    Available Patterns:
        - Adaptive, Circular, CircularZigZag, Grid, Line, LineOffset, Offset, Spiral, Triangle, ZigZag, ZigZagOffset
    Usage:
        - Instantiate this class.
        - Call the `generatePathGeometry()` method to generatePathGeometry the path geometry. The path geometry has correctional linking applied.
        - The path geometry in now available in the `pathGeometry` attribute.

    Call this method to execute the path generation code in LineClearingGenerator class.
    Returns True on success.  Access class instance `pathGeometry` attribute for path geometry.
    """

    GenUtils._debugMsg(MODULE_NAME, "generatePathGeometry()")
    PathLog.track(
        f"(tool radius: {toolRadius} mm\n step over {stepOver}\n pattern center at {patternCenterAt}\n pattern center custom {patternCenterCustom}\n cut pattern angle {cutPatternAngle}\n cutPatternReversed {cutPatternReversed}\n cutDirection {cutDirection}\n minTravel {minTravel}\n keepToolDown {keepToolDown}\n jobTolerance {jobTolerance})"
    )

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

    # Argument validation
    if not type(stepOver) is float:
        raise ValueError("Step over must be a float")

    if stepOver < 0.1 or stepOver > 100.0:
        raise ValueError("Step over exceeds limits")

    if patternCenterAt not in patternCenterAtChoices:
        raise ValueError("Invalid value for 'patternCenterAt' argument")

    if not type(patternCenterCustom) is FreeCAD.Vector:
        raise ValueError("Pattern center custom must be a FreeCAD vector")

    if not type(cutPatternAngle) is float:
        raise ValueError("Cut pattern angle must be a float")

    if not type(cutPatternReversed) is bool:
        raise ValueError("Cut pattern reversed must be a boolean")

    if not type(minTravel) is bool:
        raise ValueError("Min travel must be a boolean")

    if cutDirection not in ("Clockwise", "CounterClockwise"):
        raise ValueError("Invalid value for 'cutDirection' argument")

    if not type(keepToolDown) is bool:
        raise ValueError("Keep tool down must be a boolean")

    if hasattr(targetFace, "Area") and PathGeom.isRoughly(targetFace.Area, 0.0):
        raise ValueError("Target face has no area.")

    if not PathGeom.isRoughly(targetFace.BoundBox.ZLength, 0.0):
        raise ValueError("Target face is not horizontal plane.")

    region = targetFace.copy()
    region.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - region.BoundBox.ZMin))

    # Save argument values to class instance
    _targetFace = region
    _toolRadius = toolRadius
    _patternCenterAt = patternCenterAt
    _patternCenterCustom = patternCenterCustom
    _cutPatternReversed = cutPatternReversed
    _cutPatternAngle = cutPatternAngle
    _cutDirection = cutDirection
    _stepOver = stepOver
    _minTravel = minTravel
    _keepToolDown = keepToolDown
    _jobTolerance = jobTolerance

    _cutOut = 2.0 * _toolRadius * (_stepOver / 100.0)

    _face = targetFace
    rawPathGeometry = []
    for face in targetFace.Faces:
        rawPathGeometry.append(_offset_original())

    _pathGeometry = _Link_Regular(rawPathGeometry)
    _isCenterSet = False

    #  Apply simple radius shrinking offset for clearing pattern generation.
    # ofstVal = -1.0 * (_toolRadius - (_jobTolerance / 10.0))
    # offsetFace = PathUtils.getOffsetArea(_targetFace, ofstVal)
    # if not offsetFace:
    #    GenUtils._debugMsg(MODULE_NAME,  "getOffsetArea() failed")

    return _pathGeometry


def geometryToGcode(
    pathGeometry,
    retractHeight,
    finalDepth,
    keepToolDown,
    keepToolDownThreshold,
    startPoint,
    toolRadius,
):
    """geometryToGcode(pathGeometry, retractHeight, finalDepth=None)
    Return line geometry converted to Gcode"""
    GenUtils._debugMsg(MODULE_NAME, "geometryToGcode()")
    global _retractHeight
    global _finalDepth
    global _keepDownThreshold

    # Argument validation
    if not type(retractHeight) is float:
        raise ValueError("Retract height must be a float")

    if not type(finalDepth) is float and finalDepth is not None:
        raise ValueError("Final depth must be a float")

    if finalDepth is not None and finalDepth > retractHeight:
        raise ValueError(
            "Retract height must be greater than or equal to final depth\n"
        )

    _retractHeight = retractHeight
    _finalDepth = finalDepth
    _keepDownThreshold = 2.0 * _toolRadius * 0.8

    # commandList = _buildLinePaths(pathGeometry)
    # commandList = _buildOffsetPaths(pathGeometry)  # Need to fix FinalDepth issue
    commandList = _buildPaths(pathGeometry)  # Need to fix FinalDepth issue
    if len(commandList) > 0:
        commands = _buildStartPath()
        commands.extend(commandList)
        return commands
    else:
        GenUtils._debugMsg(MODULE_NAME, "No commands in commandList")
    return []


def generate(
    targetFace,
    toolController,
    retractHeight,
    finalDepth,
    stepOver=50.0,
    cutDirection="Clockwise",
    patternCenterAt="CenterOfBoundBox",
    patternCenterCustom=FreeCAD.Vector(0.0, 0.0, 0.0),
    cutPatternAngle=0.0,
    cutPatternReversed=False,
    minTravel=False,
    keepToolDown=False,
    jobTolerance=0.001,
):
    global FEED_VERT
    global FEED_HORIZ
    global RAPID_VERT
    global RAPID_HORIZ

    FEED_VERT = toolController.VertFeed.Value
    FEED_HORIZ = toolController.HorizFeed.Value
    RAPID_VERT = toolController.VertRapid.Value
    RAPID_HORIZ = toolController.HorizRapid.Value

    toolDiameter = (
        toolController.Tool.Diameter.Value
        if hasattr(toolController.Tool.Diameter, "Value")
        else float(toolController.Tool.Diameter)
    )
    toolRadius = toolDiameter / 2.0

    pathGeom = generatePathGeometry(
        targetFace,
        toolRadius,
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

    paths = geometryToGcode(pathGeom, retractHeight, finalDepth)

    return (paths, pathGeom)


# Raw cut pattern geometry generation methods
def _Offset_orig(self):
    """_Offset()...
    Returns raw set of Offset wires at Z=0.0.
    Direction of cut is taken into account.
    Additional offset loop ordering is handled in the linking method.
    """
    PathLog.debug("_Offset()")

    wires = []
    shape = _face
    offset = 0.0
    direction = 0
    doLast = 0
    loop = 1

    def _get_direction(w):
        if PathOpTools._isWireClockwise(w):
            return 1
        return -1

    def _reverse_wire(w):
        rev_list = []
        for e in w.Edges:
            rev_list.append(PathUtils.reverseEdge(e))
        rev_list.reverse()
        return Part.Wire(Part.__sortEdges__(rev_list))

    if _stepOver > 49.0:
        doLast += 1

    while True:
        offsetArea = PathUtils.getOffsetArea(shape, offset, plane=_workingPlane)
        if not offsetArea:
            # Attempt clearing of residual area
            if doLast:
                doLast += 1
                offset += _cutOut / 2.0
                offsetArea = PathUtils.getOffsetArea(shape, offset, plane=_workingPlane)
                if not offsetArea:
                    # Area fully consumed
                    break
            else:
                # Area fully consumed
                break

        # set initial cut direction
        if direction == 0:
            first_face_wire = offsetArea.Faces[0].Wires[0]
            direction = _get_direction(first_face_wire)
            if direction == 1:
                direction = -1

        # process each wire within face
        for f in offsetArea.Faces:
            for w in f.Wires:
                use_direction = direction
                if _cutPatternReversed:
                    use_direction = -1 * direction
                wire_direction = _get_direction(w)
                # Process wire
                if wire_direction == use_direction:  # direction is correct
                    wire = w
                else:  # incorrect direction, so reverse wire
                    wire = _reverse_wire(w)
                wires.append(wire)

        offset -= _cutOut
        loop += 1
        if doLast > 1:
            break
    # Ewhile

    return wires


def _Offset_alt(self):
    """_Offset()...
    Returns raw set of Offset wires at Z=0.0.
    Direction of cut is taken into account.
    Additional offset loop ordering is handled in the linking method.
    """
    PathLog.debug("_Offset()")

    wires = []
    # shape = _face
    shape = Part.Face(_face.Wires[0])
    holes = Part.makeCompound([Part.Face(w) for w in _face.Wires[1:]])
    offset = 0.0
    direction = 0
    doLast = 0
    loop = 1

    def _get_direction(w):
        if PathOpTools._isWireClockwise(w):
            return 1
        return -1

    def _reverse_wire(w):
        rev_list = []
        for e in w.Edges:
            rev_list.append(PathUtils.reverseEdge(e))
        rev_list.reverse()
        return Part.Wire(Part.__sortEdges__(rev_list))

    if _stepOver > 49.0:
        doLast += 1

    while True:
        offsetArea = PathUtils.getOffsetArea(shape, offset, plane=_workingPlane)
        if not offsetArea:
            # Attempt clearing of residual area
            if doLast:
                doLast += 1
                offset += _cutOut / 2.0
                offsetArea = PathUtils.getOffsetArea(shape, offset, plane=_workingPlane)
                if not offsetArea:
                    # Area fully consumed
                    break
            else:
                # Area fully consumed
                break

        # set initial cut direction
        if direction == 0:
            first_face_wire = offsetArea.Faces[0].Wires[0]
            direction = _get_direction(first_face_wire)
            if direction == 1:
                direction = -1

        # process each wire within face
        # for f in offsetArea.Faces:
        useFace = offsetArea.cut(holes)
        # Part.show(useFace)
        for f in useFace.Faces:
            w = f.Wires[0]
            use_direction = direction
            if _cutPatternReversed:
                use_direction = -1 * direction
            wire_direction = _get_direction(w)
            # Process wire
            if wire_direction == use_direction:  # direction is correct
                wire = w
            else:  # incorrect direction, so reverse wire
                wire = _reverse_wire(w)
            Part.show(wire)
            wires.append(wire)

            """for w in f.Wires:
                use_direction = direction
                if _cutPatternReversed:
                    use_direction = -1 * direction
                wire_direction = _get_direction(w)
                # Process wire
                if wire_direction == use_direction:  # direction is correct
                    wire = w
                else:  # incorrect direction, so reverse wire
                    wire = _reverse_wire(w)
                wires.append(wire)
            # Efor"""

        offset -= _cutOut
        loop += 1
        if doLast > 1:
            break
    # Ewhile

    return wires


def _Offset(self):
    """_Offset()...
    Returns raw set of Offset wires at Z=0.0.
    Direction of cut is taken into account.
    Additional offset loop ordering is handled in the linking method.
    """
    PathLog.debug("_Offset()")

    wires = []
    # shape = _face
    outerWire = Part.Wire(Part.__sortEdges__(_face.Wires[0].Edges))
    shape = Part.Face(outerWire)
    holes = Part.makeCompound([Part.Face(w) for w in _face.Wires[1:]])
    offset = 0.0
    direction = 0
    doLast = 0
    loop = 1

    def _get_direction(w):
        if PathOpTools._isWireClockwise(w):
            print("Clockwise, {}".format(w.Orientation))
            return 1
        print("Counterclockwise, {}".format(w.Orientation))
        return -1

    if _stepOver > 49.0:
        doLast += 1

    while True:
        offsetArea = PathUtils.getOffsetArea(shape, offset, plane=_workingPlane)
        if not offsetArea:
            # Attempt clearing of residual area
            if doLast:
                doLast += 1
                offset += _cutOut / 2.0
                offsetArea = PathUtils.getOffsetArea(shape, offset, plane=_workingPlane)
                if not offsetArea:
                    # Area fully consumed
                    break
            else:
                # Area fully consumed
                break

        # set initial cut direction
        if direction == 0:
            first_face_wire = offsetArea.Faces[0].Wires[0]
            direction = _get_direction(first_face_wire)
            if direction == 1:
                direction = -1

        # process each wire within face
        # for f in offsetArea.Faces:
        useFace = offsetArea.cut(holes)
        # Part.show(useFace)
        for f in useFace.Faces:
            w = f.Wires[0]
            use_direction = direction
            if _cutPatternReversed:
                use_direction = -1 * direction
            wire_direction = _get_direction(w)
            # Process wire
            if wire_direction != use_direction:  # direction is correct
                w.reverse()
            # Part.show(wire)
            wires.append(w)

            """for w in f.Wires:
                use_direction = direction
                if _cutPatternReversed:
                    use_direction = -1 * direction
                wire_direction = _get_direction(w)
                # Process wire
                if wire_direction == use_direction:  # direction is correct
                    wire = w
                else:  # incorrect direction, so reverse wire
                    wire = _reverse_wire(w)
                wires.append(wire)
            # Efor"""

        offset -= _cutOut
        loop += 1
        if doLast > 1:
            break
    # Ewhile

    return wires


# Path linking method
def _buildOffsetPaths_new(self):
    """_buildOffsetPaths(height, wireList) ... Convert Offset pattern wires to paths."""
    GenUtils._debugMsg(MODULE_NAME, "_buildOffsetPaths()")

    height = _finalDepth
    wireList = _pathGeometry

    if _keepToolDown:
        return _buildKeepOffsetDownPaths()

    paths = []
    _buildStartPath()

    if _cutDirection == "Climb":
        print("Cut Direction = Climb")
        for wire in wireList:
            wire.translate(FreeCAD.Vector(0, 0, height))

            e0 = wire.Edges[len(wire.Edges) - 1]
            paths.append(
                Path.Command(
                    "G0",
                    {
                        "X": e0.Vertexes[1].X,
                        "Y": e0.Vertexes[1].Y,
                        "F": RAPID_HORIZ,
                    },
                )
            )
            paths.append(Path.Command("G1", {"Z": height, "F": FEED_VERT}))

            for i in range(len(wire.Edges) - 1, -1, -1):
                e = wire.Edges[i]
                paths.extend(PathGeom.cmdsForEdge(e, flip=True, hSpeed=FEED_HORIZ))

            paths.append(Path.Command("G0", {"Z": _retractHeight, "F": RAPID_VERT}))

    else:
        print("Cut Direction = Clockwise")
        for wire in wireList:
            wire.translate(FreeCAD.Vector(0, 0, height))
            print("wire.Orientation: {}".format(wire.Orientation))

            e0 = wire.Edges[0]
            paths.append(
                Path.Command(
                    "G0",
                    {
                        "X": e0.Vertexes[0].X,
                        "Y": e0.Vertexes[0].Y,
                        "F": RAPID_HORIZ,
                    },
                )
            )
            paths.append(Path.Command("G1", {"Z": height, "F": FEED_VERT}))

            for e in wire.Edges:
                paths.extend(PathGeom.cmdsForEdge(e, hSpeed=FEED_HORIZ))

            paths.append(Path.Command("G0", {"Z": _retractHeight, "F": RAPID_VERT}))

    return paths


def _buildKeepOffsetDownPaths(self):
    """_buildKeepOffsetDownPaths(height, wireList) ... Convert Offset pattern wires to paths."""
    GenUtils._debugMsg(MODULE_NAME, "_buildKeepOffsetDownPaths()")

    paths = []
    height = _finalDepth
    wireList = _pathGeometry
    _buildStartPath()

    lastPnt = None
    if _cutDirection == "Climb":
        for wire in wireList:
            wire.translate(FreeCAD.Vector(0, 0, height))
            e0 = wire.Edges[len(wire.Edges) - 1]
            pnt0 = e0.Vertexes[1].Point

        if lastPnt:
            if lastPnt.sub(pnt0).Length < _keepDownThreshold and isHorizontalCutSafe(
                _toolDiameter, _targetFace, lastPnt, pnt0, maxWidth=0.0002
            ):
                paths.append(
                    Path.Command(
                        "G1",
                        {
                            "X": pnt0.x,
                            "Y": pnt0.y,
                            "F": FEED_HORIZ,
                        },
                    )
                )
            else:
                paths.extend(_linkRectangular(_retractHeight, pnt0.x, pnt0.y, height))
        else:
            paths.append(Path.Command("G0", {"Z": _retractHeight, "F": FEED_VERT}))
            paths.append(
                Path.Command(
                    "G0",
                    {
                        "X": e0.Vertexes[0].X,
                        "Y": e0.Vertexes[0].Y,
                        "F": RAPID_HORIZ,
                    },
                )
            )
            paths.append(Path.Command("G1", {"Z": height, "F": FEED_VERT}))

            for i in range(len(wire.Edges) - 1, -1, -1):
                e = wire.Edges[i]
                paths.extend(PathGeom.cmdsForEdge(e, flip=True, hSpeed=FEED_HORIZ))

            # Save last point
            lastPnt = wire.Edges[0].Vertexes[0].Point

    else:
        for wire in wireList:
            wire.translate(FreeCAD.Vector(0, 0, height))
            eCnt = len(wire.Edges)
            e0 = wire.Edges[0]
            pnt0 = e0.Vertexes[0].Point

        if lastPnt:
            if lastPnt.sub(pnt0).Length < _keepDownThreshold and isHorizontalCutSafe(
                _toolDiameter, _targetFace, lastPnt, pnt0, maxWidth=0.0002
            ):
                paths.append(
                    Path.Command(
                        "G1",
                        {
                            "X": pnt0.x,
                            "Y": pnt0.y,
                            "F": FEED_HORIZ,
                        },
                    )
                )
            else:
                paths.extend(_linkRectangular(_retractHeight, pnt0.x, pnt0.y, height))
        else:
            paths.append(Path.Command("G0", {"Z": _retractHeight, "F": FEED_VERT}))
            paths.append(
                Path.Command(
                    "G0",
                    {
                        "X": e0.Vertexes[0].X,
                        "Y": e0.Vertexes[0].Y,
                        "F": RAPID_HORIZ,
                    },
                )
            )
            paths.append(Path.Command("G1", {"Z": height, "F": FEED_VERT}))

            for i in range(0, eCnt):
                paths.extend(PathGeom.cmdsForEdge(wire.Edges[i], hSpeed=FEED_HORIZ))

            # Save last point
            lastEdgeVertexes = wire.Edges[eCnt - 1].Vertexes
            lastPnt = lastEdgeVertexes[len(lastEdgeVertexes) - 1].Point
    # Eif

    return paths


# Macro functions ####################
def getFacesFromSelection():
    import FreeCADGui

    faces = []
    selection = FreeCADGui.Selection.getSelectionEx()
    # process user selection
    for sel in selection:
        # print(f"Object.Name: {sel.Object.Name}")
        for feat in sel.SubElementNames:
            # print(f"Processing: {sel.Object.Name}::{feat}")
            if feat.startswith("Face"):
                # face = sel.Object.Shape.getElement(feat)
                faces.append(sel.Object.Shape.getElement(feat))
    return faces


def guiGetValues():
    global PATHTYPE
    global PATTERN
    import Gui_ComboBox

    # Get path type from user
    ptGui = Gui_ComboBox.ComboBox("Path Type", PATHTYPES)
    ptGui.setWindowTitle("Path Type Selection")
    PATHTYPE = ptGui.execute()

    # Get cut pattern from user
    ptrnGui = Gui_ComboBox.ComboBox("Cut Pattern", PATTERNS)
    ptrnGui.setWindowTitle("Cut Pattern Selection")
    PATTERN = ptrnGui.execute()


def getRegion(faces, finalDepth=None):

    import CombineRegions

    if len(faces) == 0:
        return None

    # combine faces into horizontal regions
    region = CombineRegions.combineRegions(faces, saveExistingHoles=True)
    # Part.show(region, "Region")

    # fuse faces together for projection of path geometry
    if len(faces) == 1:
        faceShape = faces[0]
    else:
        faceShape = faces.pop(0)
        for f in faces:
            fused = faceShape.fuse(f)
            faceShape = fused

    return region, faceShape


def runMacro():
    # guiGetValues()
    toolRadius = 5.0
    targetFaces = getFacesFromSelection()

    region, faceShape = getRegion(targetFaces)

    reg = region.copy()
    reg.translate(FreeCAD.Vector(0.0, 0.0, faceShape.BoundBox.ZMax))
    Part.show(reg, "Region")

    pathGeom = generatePathGeometry(
        region,
        toolRadius,
        stepOver=20.0,
        cutDirection="Clockwise",
        patternCenterAt="CenterOfBoundBox",
        patternCenterCustom=FreeCAD.Vector(0.0, 0.0, 0.0),
        cutPatternAngle=0.0,
        cutPatternReversed=False,
        minTravel=False,
        keepToolDown=False,
        jobTolerance=0.001,
    )

    compPathGeom = Part.makeCompound(pathGeom)
    compPathGeom.translate(FreeCAD.Vector(0.0, 0.0, faceShape.BoundBox.ZMax))
    Part.show(compPathGeom, "CompPathGeom")


print("Imported Generator_Offset")
if IS_MACRO:
    runMacro()
