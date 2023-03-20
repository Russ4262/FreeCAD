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


import DraftGeomUtils
import FreeCAD
import Generator_Utilities as GenUtils
import math
import Part
import Path
import Path.Geom as PathGeom
import Path.Log as PathLog
import Path.Op.Util as PathOpTools
import PathScripts.PathUtils as PathUtils
import time


__title__ = "Circle Path Generator"
__author__ = "russ4262 (Russell Johnson)"
__url__ = ""
__doc__ = "Generates the circle clearing toolpath for a 2D or 3D face"

if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
showDebugShapes = False

IS_MACRO = False
MODULE_NAME = "Generator_Circle"
PATHTYPES = ["2D", "3D"]
PATHTYPE = "2D"
FEED_VERT = 0.0
FEED_HORIZ = 0.0
RAPID_VERT = 0.0
RAPID_HORIZ = 0.0

_face = None
_centerOfPattern = None
_isCenterSet = False
_startPoint = None
_toolRadius = None
_rawPathGeometry = None

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


# Raw cut pattern geometry generation methods
def _Circle(
    radialPasses, stepOver, cutOut, centerOfPattern, cutDirection, cutPatternReversed
):
    """_Circle(radialPasses, stepOver, cutOut, centerOfPattern, cutDirection, cutPatternReversed)... Returns raw set of Circular wires at Z=0.0."""
    geomList = []
    minRad = _toolRadius * 0.95

    if (cutDirection == "Clockwise" and not cutPatternReversed) or (
        cutDirection != "Clockwise" and cutPatternReversed
    ):
        direction = FreeCAD.Vector(0.0, 0.0, 1.0)
    else:
        direction = FreeCAD.Vector(0.0, 0.0, -1.0)

    # Make small center circle to start pattern
    if stepOver > 50.0:
        circle = Part.makeCircle(minRad, centerOfPattern, direction)
        geomList.append(circle)

    for lc in range(1, radialPasses + 1):
        rad = lc * cutOut
        if rad >= minRad:
            wire = Part.Wire([Part.makeCircle(rad, centerOfPattern, direction)])
            geomList.append(wire)

    if not cutPatternReversed:
        geomList.reverse()

    return geomList


# Path linking method
def _Link_Regular(rawPathGeometry, centerOfPattern, cutPatternReversed):
    """_Link_Regular(centerOfPattern, cutPatternReversed)... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
    # PathLog.debug("_Link_Regular()")

    def combineAdjacentArcs(grp):
        """combineAdjacentArcs(arcList)...
        Combine two adjacent arcs in list into single.
        The two arcs in the original list are replaced by the new single. The modified list is returned.
        """
        # PathLog.debug("combineAdjacentArcs()")

        i = 1
        limit = len(grp)
        arcs = []
        saveLast = False

        arc = grp[0]
        aP0 = arc.Vertexes[0].Point
        aP1 = arc.Vertexes[1].Point

        while i < limit:
            nArc = grp[i]
            naP0 = nArc.Vertexes[0].Point
            naP1 = nArc.Vertexes[1].Point
            if abs(arc.Curve.AngleXU) == 0.0:
                reversed = False
            else:
                reversed = True
            # Check if arcs are connected
            if naP1.sub(aP0).Length < 0.00001:
                # PathLog.debug("combining arcs")
                # Create one continuous arc
                cent = arc.Curve.Center
                vect0 = aP1.sub(cent)
                vect1 = naP0.sub(cent)
                radius = arc.Curve.Radius
                direct = FreeCAD.Vector(0.0, 0.0, 1.0)
                angle0 = math.degrees(math.atan2(vect1.y, vect1.x))
                angle1 = math.degrees(math.atan2(vect0.y, vect0.x))
                if reversed:
                    newArc = Part.makeCircle(
                        radius,
                        cent,
                        direct.multiply(-1.0),
                        360.0 - angle0,
                        360 - angle1,
                    )  # makeCircle(radius,[pnt,dir,angle1,angle2])
                else:
                    newArc = Part.makeCircle(
                        radius, cent, direct, angle0, angle1
                    )  # makeCircle(radius,[pnt,dir,angle1,angle2])
                ang = aP0.sub(cent).normalize()
                line = Part.makeLine(cent, aP0.add(ang))
                touch = DraftGeomUtils.findIntersection(newArc, line)
                if not touch:
                    if reversed:
                        newArc = Part.makeCircle(
                            radius,
                            cent,
                            direct.multiply(-1.0),
                            360.0 - angle1,
                            360 - angle0,
                        )  # makeCircle(radius,[pnt,dir,angle1,angle2])
                    else:
                        newArc = Part.makeCircle(
                            radius, cent, direct, angle1, angle0
                        )  # makeCircle(radius,[pnt,dir,angle1,angle2])
                arcs.append(newArc)
                i += 1
                if i < limit:
                    arc = grp[i]
                    aP0 = arc.Vertexes[0].Point
                    aP1 = arc.Vertexes[1].Point
                    saveLast = True
                else:
                    saveLast = False
                    break
            else:
                arcs.append(arc)
                arc = nArc
                aP0 = arc.Vertexes[0].Point
                aP1 = arc.Vertexes[1].Point
                saveLast = True
            i += 1

        if saveLast:
            arcs.append(arc)

        return arcs

    allGroups = []
    allWires = []
    if cutPatternReversed:  # inside to out
        edges = sorted(
            rawPathGeometry.Edges,
            key=lambda e: e.Curve.Center.sub(centerOfPattern).Length,
        )
    else:
        edges = sorted(
            rawPathGeometry.Edges,
            key=lambda e: e.Curve.Center.sub(centerOfPattern).Length,
            reverse=True,
        )
    limit = len(edges)

    if limit == 0:
        return allWires

    e = edges[0]
    rad = e.Curve.Radius
    group = [e]

    if limit > 1:
        for i in range(1, limit):
            # get next edge
            ne = edges[i]
            nRad = ne.Curve.Radius

            # Check if prev and next are colinear
            if abs(nRad - rad) < 0.000001:
                group.append(ne)
            else:
                allGroups.append(group)
                e = ne
                rad = nRad
                group = [ne]

    allGroups.append(group)

    # Process last remaining group of edges
    for g in allGroups:
        if len(g) < 2:
            allWires.append(Part.Wire(g[0]))
        else:
            wires = [Part.Wire(arc) for arc in combineAdjacentArcs(g)]
            allWires.extend(wires)

    return allWires


# 3D projected wire linking methods
def _Link_Projected(wireList, cutDirection, cutReversed=False):
    """_Link_Projected(wireList, cutDirection, cutReversed=False)... Apply necessary linking and orientation to 3D wires."""
    FreeCAD.Console.PrintError("_Link_Projected() `cutReversed` flag not active.\n")
    if cutDirection == "Clockwise":
        return _link_circle_projected_clockwise(wireList)
    else:
        return _link_circle_projected_counterclockwise(wireList)


def _link_circle_projected_clockwise(wireList):
    """_link_circle_projected_clockwise(wireList)... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
    # PathLog.debug("_link_circle_projected_clockwise()")

    allWires = []
    dataTups = []
    # Create data tuples for sorting wires
    for w in wireList:
        v0 = w.Vertexes[0].Point
        dataTups.append(
            (
                w,
                round(FreeCAD.Vector(v0.x, v0.y, 0.0).sub(_centerOfPattern).Length, 6),
            )
        )

    # Sort dataTups by distance to center of pattern
    if _cutPatternReversed:  # inside to out
        dataTups.sort(key=lambda tup: tup[1], reverse=True)
    else:
        dataTups.sort(key=lambda tup: tup[1])

    # Group dataTups by distance to center of pattern
    ringGroups = []
    w = dataTups[0]
    if GenUtils._isArcClockwise(w[0], _centerOfPattern):
        ring = [w]
    else:
        ring = [(GenUtils.flipWire(w[0]), w[1])]
    dist = w[1]

    for w in dataTups[1:]:
        if w[1] == dist:
            if GenUtils._isArcClockwise(w[0], _centerOfPattern):
                ring.append(w)
            else:
                ring.append((GenUtils.flipWire(w[0]), w[1]))
        else:
            ring.sort(
                key=lambda tup: GenUtils.getAngle(
                    tup[0].Edges[0].valueAt(tup[0].Edges[0].FirstParameter),
                    _centerOfPattern,
                ),
                reverse=True,
            )
            ringGroups.append(ring)
            if GenUtils._isArcClockwise(w[0], _centerOfPattern):
                ring = [w]
            else:
                ring = [(GenUtils.flipWire(w[0]), w[1])]
            dist = w[1]
    ring.sort(
        key=lambda tup: GenUtils.getAngle(
            tup[0].Edges[0].valueAt(tup[0].Edges[0].FirstParameter), _centerOfPattern
        ),
        reverse=True,
    )
    ringGroups.append(ring)

    for r in ringGroups:
        allWires.extend([w for w, __ in r])

    return allWires


def _link_circle_projected_counterclockwise(wireList):
    """_link_circle_projected_counterclockwise(wireList)... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
    # PathLog.debug("_link_circle_projected_counterclockwise()")

    allWires = []
    dataTups = []
    # Create data tuples for sorting wires
    for w in wireList:
        v0 = w.Vertexes[0].Point
        dataTups.append(
            (
                w,
                round(FreeCAD.Vector(v0.x, v0.y, 0.0).sub(_centerOfPattern).Length, 6),
            )
        )

    # Sort dataTups by distance to center of pattern
    if _cutPatternReversed:  # inside to out
        dataTups.sort(key=lambda tup: tup[1], reverse=True)
    else:
        dataTups.sort(key=lambda tup: tup[1])

    # Group dataTups by distance to center of pattern
    ringGroups = []
    w = dataTups[0]
    if not GenUtils._isArcClockwise(w[0], _centerOfPattern):
        ring = [w]
    else:
        ring = [(GenUtils.flipWire(w[0]), w[1])]
    dist = w[1]

    for w in dataTups[1:]:
        if w[1] == dist:
            if not GenUtils._isArcClockwise(w[0], _centerOfPattern):
                ring.append(w)
            else:
                ring.append((GenUtils.flipWire(w[0]), w[1]))
        else:
            ring.sort(
                key=lambda tup: GenUtils.getAngle(
                    tup[0].Edges[0].valueAt(tup[0].Edges[0].FirstParameter),
                    _centerOfPattern,
                ),
            )
            ringGroups.append(ring)
            if not GenUtils._isArcClockwise(w[0], _centerOfPattern):
                ring = [w]
            else:
                ring = [(GenUtils.flipWire(w[0]), w[1])]
            dist = w[1]
    ring.sort(
        key=lambda tup: GenUtils.getAngle(
            tup[0].Edges[0].valueAt(tup[0].Edges[0].FirstParameter), _centerOfPattern
        ),
    )
    ringGroups.append(ring)

    for r in ringGroups:
        allWires.extend([w for w, __ in r])

    return allWires


# Support methods
def _generatePathGeometry(
    radialPasses, stepOver, cutOut, centerOfPattern, cutDirection, cutPatternReversed
):
    """_generatePathGeometry(radialPasses, centerOfPattern, cutDirection, cutPatternReversed)
    Control function that generates path geometry wire sets."""
    GenUtils._debugMsg(MODULE_NAME, "_generatePathGeometry()")
    global _rawPathGeometry

    _rawGeoList = _Circle(
        radialPasses,
        stepOver,
        cutOut,
        centerOfPattern,
        cutDirection,
        cutPatternReversed,
    )

    # Create compound object to bind all geometry
    geomShape = Part.makeCompound(_rawGeoList)

    GenUtils._addDebugShape(geomShape, "rawPathGeomShape")  # Debugging

    """# Position and rotate the Line and ZigZag geometry
    if _cutPatternAngle != 0.0:
        geomShape.Placement.Rotation = FreeCAD.Rotation(
            FreeCAD.Vector(0, 0, 1), _cutPatternAngle
        )
    cop = _centerOfPattern
    geomShape.Placement.Base = FreeCAD.Vector(
        cop.x, cop.y, 0.0 - geomShape.BoundBox.ZMin
    )

    addDebugShape(geomShape, "tmpGeometrySet")  # Debugging
    """

    # Identify intersection of cross-section face and lineset
    # rawWireSet = Part.makeCompound(geomShape.Wires)
    # _rawPathGeometry = _face.common(rawWireSet)
    _rawPathGeometry = _face.common(geomShape)

    GenUtils._addDebugShape(_rawPathGeometry, "rawPathGeometry")  # Debugging

    _linkedPathGeom = _Link_Regular(
        _rawPathGeometry, centerOfPattern, cutPatternReversed
    )

    return _linkedPathGeom


# Gcode production method
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


def _buildCirclePaths(pathGeometry):
    """_buildCirclePaths(pathGeometry) ... Convert Line-based wires to paths."""
    GenUtils._debugMsg(MODULE_NAME, "_buildCirclePaths()")

    paths = []
    wireList = pathGeometry

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
                    "F": RAPID_HORIZ,
                },
            )
        )
        paths.append(
            # Path.Command("G0", {"Z": self.prevDepth + 0.1, "F": self.vertRapid})
            Path.Command("G0", {"Z": _retractHeight, "F": RAPID_VERT})
        )
        paths.append(Path.Command("G1", {"Z": finalDepth, "F": FEED_VERT}))

        for e in wire.Edges:
            paths.extend(PathGeom.cmdsForEdge(e, hSpeed=FEED_HORIZ, vSpeed=FEED_VERT))

        paths.append(
            # Path.Command("G0", {"Z": self.safeHeight, "F": self.vertRapid})
            Path.Command("G0", {"Z": _retractHeight, "F": RAPID_VERT})
        )

    GenUtils._debugMsg(
        MODULE_NAME, "_buildCirclePaths() path count: {}".format(len(paths))
    )
    return paths


# Public functions
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
    """generatePathGeometry(targetFace,
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
        jobTolerance:       job tolerance value
    Available Patterns:
        - Adaptive, Circular, CircularZigZag, Grid, Line, LineOffset, Offset, Spiral, Triangle, ZigZag, ZigZagOffset
    Usage:
        - Instantiate this class.
        - Call the `generate()` method to generate the path geometry. The path geometry has correctional linking applied.
        - The path geometry in now available in the `pathGeometry` attribute.
    """
    GenUtils._debugMsg(MODULE_NAME, "Generator_Circle.generatePathGeometry()")
    GenUtils._debugMsg(
        MODULE_NAME,
        f"(step over {stepOver}\n pattern center at {patternCenterAt}\n pattern center custom {patternCenterCustom}\n cut pattern angle {cutPatternAngle}\n cutPatternReversed {cutPatternReversed}\n cutDirection {cutDirection}\n minTravel {minTravel}\n keepToolDown {keepToolDown}\n jobTolerance {jobTolerance})",
    )

    if hasattr(targetFace, "Area") and PathGeom.isRoughly(targetFace.Area, 0.0):
        GenUtils._debugMsg(MODULE_NAME, "Generator_Circle: No area in working shape.")
        return None

    # Argument validation
    # if not type(retractHeight) is float:
    #    raise ValueError("Retract height must be a float")

    # if not type(finalDepth) is float:
    #    raise ValueError("Final depth must be a float")

    # if finalDepth > retractHeight:
    #    raise ValueError("Retract height must be greater than or equal to final depth\n")

    if not type(stepOver) is float:
        raise ValueError("Step over must be a float")

    if stepOver < 0.1 or stepOver > 100.0:
        raise ValueError("Step over exceeds limits")

    if patternCenterAt not in [tup[1] for tup in GenUtils.PATTERNCENTERS]:
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
    global _isCenterSet
    global _toolRadius
    global _face
    global _useStaticCenter

    global _centerOfPattern

    _useStaticCenter = True  # Set True to use static center for all faces created by offsets and step downs.  Set False for dynamic centers based on PatternCenterAt
    _isCenterSet = False

    # Save argument values to class instance
    _targetFace = targetFace.copy()
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

    _targetFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - _targetFace.BoundBox.ZMin))

    pathGeometry = []
    centerOfPattern = None
    halfDiag = 0.0
    cutPasses = 0.0
    halfPasses = 0.0
    isCenterSet = _isCenterSet
    cutOut = _toolRadius * 2.0 * (_stepOver / 100.0)

    for fc in _targetFace.Faces:
        fc.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - fc.BoundBox.ZMin))
        if fc.Faces:
            for f in fc.Faces:
                f.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - f.BoundBox.ZMin))
                _face = f
                # _prepareAttributes()
                attributes = GenUtils._prepareAttributes(
                    f,
                    toolRadius,
                    cutOut,
                    isCenterSet,
                    _useStaticCenter,
                    patternCenterAt,
                    patternCenterCustom,
                )
                if attributes is not None:
                    (centerOfPattern, halfDiag, cutPasses, halfPasses) = attributes
                    _centerOfPattern = centerOfPattern  # save it for later use
                pathGeom = _generatePathGeometry(
                    cutPasses,
                    stepOver,
                    cutOut,
                    centerOfPattern,
                    cutDirection,
                    cutPatternReversed,
                )
                pathGeometry.extend(pathGeom)
        else:
            GenUtils._debugMsg(
                MODULE_NAME, "No offset faces after cut with base shape."
            )

    return pathGeometry


def geometryToGcode(
    pathGeometry,
    retractHeight,
    finalDepth,
    keepToolDown,
    keepToolDownThreshold,
    startPoint,
    toolRadius,
):
    """geometryToGcode(pathGeometry) Return line geometry converted to Gcode"""
    GenUtils._debugMsg(MODULE_NAME, "geometryToGcode()")
    global _retractHeight
    global _finalDepth

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

    commandList = _buildCirclePaths(pathGeometry)
    if len(commandList) > 0:
        commands = _buildStartPath()
        commands.extend(commandList)
        return commands
    else:
        GenUtils._debugMsg(MODULE_NAME, "No commands in commandList")
    return []


# Auxillary functions
def getFacesFromSelection():
    if not FreeCAD.GuiUp:
        return []

    faces = []
    selection = FreeCADGui.Selection.getSelectionEx()
    if len(selection) == 0:
        print("No selection.")
        return []
    # process user selection
    for sel in selection:
        # print(f"Object.Name: {sel.Object.Name}")
        for feat in sel.SubElementNames:
            # print(f"Processing: {sel.Object.Name}::{feat}")
            if feat.startswith("Face"):
                # face = sel.Object.Shape.getElement(feat)
                faces.append(sel.Object.Shape.getElement(feat))

    return faces


def getUserInput():
    if not FreeCAD.GuiUp:
        return None

    # Get path type from user
    guiInput = Gui_Input.GuiInput()
    guiInput.setWindowTitle("Path Details")
    guiInput.addComboBox("Path Type", PATHTYPES)

    # Get cut pattern from user
    guiInput.addDoubleSpinBox("Step over %", 100.0)
    guiInput.addDoubleSpinBox("Sample interval", 1.0)
    return guiInput.execute()


def runMacro():
    global PATHTYPE

    targetFaces = getFacesFromSelection()
    if len(targetFaces) == 0:
        return

    PATHTYPE, stepOver, sampleInterval = getUserInput()
    timeStart = time.time()

    # Set tool controller from Job object
    tc = Tool_Controller.getToolController()
    job = None
    for obj in FreeCAD.ActiveDocument.Objects:
        if obj.Name == "Job":
            job = obj
            break

    tolerance = 0.1
    # combine faces into horizontal regions
    region = CombineRegions.combineRegions(targetFaces, saveExistingHoles=True)
    # Part.show(region, "Region")

    # fuse faces together for projection of path geometry
    if len(targetFaces) == 1:
        faceShape = targetFaces[0]
    else:
        faceShape = targetFaces[0]
        for f in targetFaces:
            fused = faceShape.fuse(f)
            faceShape = fused

    compFaces = Part.makeCompound(targetFaces)
    retractHeight = compFaces.BoundBox.ZMax + 5.0
    finalDepth = compFaces.BoundBox.ZMax

    # Process faces for path geometry
    toolDiameter = (
        tc.Tool.Diameter.Value
        if hasattr(tc.Tool.Diameter, "Value")
        else float(tc.Tool.Diameter)
    )
    toolRadius = toolDiameter / 2.0

    print(f"Tool radius: {toolRadius},  Step-over: {stepOver}")

    pathGeomList = generatePathGeometry(
        region,
        tc,
        retractHeight,
        finalDepth,
        stepOver=stepOver,
        cutDirection="Clockwise",
        patternCenterAt="CenterOfBoundBox",
        patternCenterCustom=FreeCAD.Vector(0.0, 0.0, 0.0),
        cutPatternAngle=0.0,
        cutPatternReversed=False,
        minTravel=False,
        keepToolDown=False,
        jobTolerance=0.001,
    )

    Part.show(Part.makeCompound(pathGeomList), "PathGeomList")

    workTime = time.time() - timeStart
    print(f"Processing time: {workTime}")


print("Imported Generator_Circle")

if IS_MACRO:
    import Tool_Controller
    import CombineRegions

    if FreeCAD.GuiUp:
        import Gui_Input
        import FreeCADGui

    runMacro()
