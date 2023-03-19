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
import Generator_Utilities as GenUtils
import Path.Geom as PathGeom
import Path.Op.Util as PathOpTools
import Path
import Part
import math


__title__ = "Path Profile Generator"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Generates the line-clearing toolpath for a single 2D face"


if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())

isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
showDebugShapes = False

MODULE_NAME = "Generator_Profile"
FEED_VERT = 0.0
FEED_HORIZ = 0.0
RAPID_VERT = 0.0
RAPID_HORIZ = 0.0

_face = None
_centerOfPattern = None
_isCenterSet = False
_startPoint = None
_toolRadius = None
_workingPlane = Part.makeCircle(5.0, FreeCAD.Vector(0.0, 0.0, 0.0))
patternCenterAtChoices = ("CenterOfMass", "CenterOfBoundBox", "XminYmin", "Custom")

_targetFace = None
_retractHeight = None
_finalDepth = None
_patternCenterAt = None
_patternCenterCustom = None
_cutPatternReversed = None
_cutPatternAngle = None
_cutDirection = None
_minTravel = None  # Inactive feature
_keepToolDown = None
_jobTolerance = None
_prevDepth = None


# Support methods
def _profile():
    """_profile()...
    Returns raw profile wires at Z=0.0.
    Direction of cut is taken into account.
    """
    GenUtils._debugMsg(MODULE_NAME, "_profile()")

    wires = []
    shape = _face
    offset = -1.0 * (_toolRadius - (_jobTolerance / 10.0))  # 0.0
    direction = 0

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

    offsetArea = PathUtils.getOffsetArea(shape, offset, plane=_workingPlane)
    if offsetArea is False:
        GenUtils._debugMsg(MODULE_NAME, "_profile() offsetArea is False")
        return wires

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
            # Change direction of wire as needed
            if _cutDirection == "CounterClockwise":
                saveWire = _reverse_wire(wire)
            else:
                saveWire = wire
            wires.append(saveWire)

    return wires


def _generatePathGeometry(rawGeoList):
    """_generatePathGeometry()... Control function that generates path geometry wire sets."""
    GenUtils._debugMsg(MODULE_NAME, "_generatePathGeometry()")

    # Create compound object to bind all geometry
    geomShape = Part.makeCompound(rawGeoList)

    GenUtils._addDebugShape(geomShape, "rawPathGeomShape")  # Debugging

    # Position and rotate the Line and ZigZag geometry
    if _cutPatternAngle != 0.0:
        geomShape.Placement.Rotation = FreeCAD.Rotation(
            FreeCAD.Vector(0, 0, 1), _cutPatternAngle
        )
    cop = _centerOfPattern
    geomShape.Placement.Base = FreeCAD.Vector(
        cop.x, cop.y, 0.0 - geomShape.BoundBox.ZMin
    )

    GenUtils._addDebugShape(geomShape, "tmpGeometrySet")  # Debugging

    # Identify intersection of cross-section face and lineset
    rawWireSet = Part.makeCompound(geomShape.Wires)
    rawPathGeometry = _face.common(rawWireSet)

    GenUtils._addDebugShape(rawPathGeometry, "rawPathGeometry")  # Debugging

    return rawPathGeometry


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


def _buildLinePaths(pathGeometry):
    """_buildLinePaths(pathGeometry) ... Convert Line-based wires to paths."""
    GenUtils._debugMsg(MODULE_NAME, "_buildLinePaths()")

    paths = []
    wireList = pathGeometry

    for wire in wireList:
        # print(f"wire length: {len(wire.Edges)}")
        if _finalDepth is not None:
            # wire.translate(FreeCAD.Vector(0, 0, _finalDepth - wire.BoundBox.ZMin))
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
                    "F": RAPID_HORIZ,
                },
            )
        )
        # paths.append(
        #    Path.Command("G0", {"Z": _retractHeight, "F": RAPID_VERT})
        # )
        paths.append(Path.Command("G1", {"Z": finalDepth, "F": FEED_VERT}))

        eIdx = 0
        for e in wire.Edges:
            # print(f"edge cnt: {eIdx}")
            paths.extend(PathGeom.cmdsForEdge(e, hSpeed=FEED_HORIZ, vSpeed=FEED_VERT))
            eIdx += 1

        paths.append(
            # Path.Command("G0", {"Z": self.safeHeight, "F": self.vertRapid})
            Path.Command("G0", {"Z": _retractHeight, "F": RAPID_VERT})
        )

    GenUtils._debugMsg(
        MODULE_NAME, "_buildLinePaths() path count: {}".format(len(paths))
    )
    return paths


def _buildPaths(pathGeometry):
    """_buildPaths() ... Convert wires to paths."""
    GenUtils._debugMsg(MODULE_NAME, "_buildPaths()")

    paths = []
    for w in pathGeometry:
        toolPath = Path.fromShapes(w, preamble=False)
        paths.extend(toolPath.Commands)
    return paths


# Main method to call
def generatePathGeometry(
    targetFace,
    toolRadius,
    stepOver,
    cutDirection,
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
        "(tool radius: {} mm\n pattern center at {}\n pattern center custom ({}, {}, {})\n cut pattern angle {}\n cutPatternReversed {}\n cutDirection {}\n minTravel {}\n keepToolDown {}\n jobTolerance {})".format(
            toolRadius,
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

    global _targetFace
    global _patternCenterAt
    global _patternCenterCustom
    global _cutPatternReversed
    global _cutPatternAngle
    global _cutDirection
    global _minTravel
    global _keepToolDown
    global _jobTolerance
    global _prevDepth
    global _isCenterSet
    global _toolRadius
    global _face

    if patternCenterAt not in patternCenterAtChoices:
        raise ValueError("Invalid value for 'patternCenterAt' argument")

    if not type(patternCenterCustom) is FreeCAD.Vector:
        raise ValueError("Pattern center custom must be a FreeCAD vector.\n")

    if not type(cutPatternAngle) is float:
        raise ValueError("Cut pattern angle must be a float.\n")

    if not type(cutPatternReversed) is bool:
        raise ValueError("Cut pattern reversed must be a boolean.\n")

    if not type(minTravel) is bool:
        raise ValueError("Min travel must be a boolean.\n")

    if cutDirection not in ("Clockwise", "CounterClockwise"):
        raise ValueError("Invalid value for 'cutDirection' argument.\n")

    if not type(keepToolDown) is bool:
        raise ValueError("Keep tool down must be a boolean.\n")

    if hasattr(targetFace, "Area") and PathGeom.isRoughly(targetFace.Area, 0.0):
        raise ValueError("Target face has no area.\n")

    if not PathGeom.isRoughly(targetFace.BoundBox.ZLength, 0.0):
        # Part.show(targetFace, "TargetFace_Error")
        raise ValueError(
            "generatePathGeometry() Target face is not horizontal plane.\n"
        )

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
    _minTravel = minTravel
    _keepToolDown = keepToolDown
    _jobTolerance = jobTolerance

    _face = targetFace
    _pathGeometry = _profile()  # retuns list of wires
    _isCenterSet = False

    #  Apply simple radius shrinking offset for clearing pattern generation.
    # ofstVal = -1.0 * (_toolRadius - (_jobTolerance / 10.0))
    # offsetFace = PathUtils.getOffsetArea(_targetFace, ofstVal)
    # if not offsetFace:
    #    GenUtils._debugMsg(MODULE_NAME,"getOffsetArea() failed")

    return _pathGeometry  # list of wires


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
    global _prevDepth

    # Argument validation
    if not type(retractHeight) is float:
        raise ValueError("Retract height must be a float")

    if not type(finalDepth) is float and finalDepth is not None:
        raise ValueError("Final depth must be a float")

    if finalDepth is not None and finalDepth > retractHeight:
        raise ValueError(
            f"Generator_Profile.geometryToGcode():\n     Retract height {retractHeight} must be greater than or equal to final depth {finalDepth}\n"
        )

    _retractHeight = retractHeight
    _finalDepth = finalDepth
    _prevDepth = retractHeight

    commandList = _buildLinePaths(pathGeometry)
    # commandList = _buildPaths(pathGeometry)
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
    cutDirection="Clockwise",
    patternCenterAt="CenterOfBoundBox",
    patternCenterCustom=FreeCAD.Vector(0.0, 0.0, 0.0),
    cutPatternAngle=0.0,
    cutPatternReversed=False,
    minTravel=False,
    keepToolDown=False,
    jobTolerance=0.001,
):
    toolDiameter = (
        toolController.Tool.Diameter.Value
        if hasattr(toolController.Tool.Diameter, "Value")
        else float(toolController.Tool.Diameter)
    )
    toolRadius = toolDiameter / 2.0
    stepOver = 50.0  # Not used for Profile

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


print("Imported Generator_Profile")
