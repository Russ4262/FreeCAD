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
import Path.Geom as PathGeom
import Path
import Part
import math
import Macros.Generator_Utilities as GenUtils
import Generator_DropCut as DropCut
import Macro_CombineRegions


__title__ = "Line Geometry and Path Generator"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Generates the line-clearing toolpath for a single 2D face"


if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())

# PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())

IS_MACRO = True  # Set to True to use as macro
IS_TEST_MODE = False
TARGET_REGION = None  # 2D cross-section of target faces
RESET_ATTRIBUTES = True
USE_STATIC_CENTER = True  # Set True to use static center for all faces created by offsets and step downs.  Set False for dynamic centers based on PatternCenterAt
IS_CENTER_SET = False
GEOM_ATTRIBUTES = None
PATH_TYPE = "2D"
FEED_VERT = 0.0
FEED_HORIZ = 0.0
RAPID_VERT = 0.0
RAPID_HORIZ = 0.0


# geometry functions
def _line(
    halfDiag, patternCenterAt, halfPasses, cutOut, cutDirection, cutPatternReversed
):
    """_line()... Returns raw set of raw Part.Line wires at Z=0.0."""
    GenUtils._debugMsg("_line()")
    geomList = []
    centRot = FreeCAD.Vector(
        0.0, 0.0, 0.0
    )  # Bottom left corner of face/selection/model
    segLength = halfDiag
    if patternCenterAt in ["XminYmin", "Custom"]:
        segLength = 2.0 * halfDiag

    # Create end points for set of lines to intersect with cross-section face
    pntTuples = []
    for lc in range((-1 * (halfPasses - 1)), halfPasses + 1):
        x1 = centRot.x - segLength
        x2 = centRot.x + segLength
        y1 = centRot.y + (lc * cutOut)
        # y2 = y1
        p1 = FreeCAD.Vector(x1, y1, 0.0)
        p2 = FreeCAD.Vector(x2, y1, 0.0)
        pntTuples.append((p1, p2))

    # Convert end points to lines

    if (cutDirection == "Clockwise" and not cutPatternReversed) or (
        cutDirection != "Clockwise" and cutPatternReversed
    ):
        for (p2, p1) in pntTuples:
            wire = Part.Wire([Part.makeLine(p1, p2)])
            geomList.append(wire)
    else:
        for (p1, p2) in pntTuples:
            wire = Part.Wire([Part.makeLine(p1, p2)])
            geomList.append(wire)

    if cutPatternReversed:
        geomList.reverse()

    return geomList


def _generatePathGeometry(face, rawGeoList, cutPatternAngle, centerOfPattern):
    """_generatePathGeometry()... Control function that generates path geometry wire sets."""
    GenUtils._debugMsg("_generatePathGeometry()")

    # Create compound object to bind all geometry
    geomShape = Part.makeCompound(rawGeoList)

    # GenUtils._addDebugShape(geomShape, "rawPathGeomShape")  # Debugging

    # Position and rotate the Line geometry
    if cutPatternAngle != 0.0:
        geomShape.Placement.Rotation = FreeCAD.Rotation(
            FreeCAD.Vector(0, 0, 1), cutPatternAngle
        )
    cop = centerOfPattern
    geomShape.Placement.Base = FreeCAD.Vector(
        cop.x, cop.y, 0.0 - geomShape.BoundBox.ZMin
    )

    GenUtils._addDebugShape(geomShape, "tmpGeometrySet")  # Debugging

    # Identify intersection of cross-section face and lineset
    rawWireSet = Part.makeCompound(geomShape.Wires)
    rawPathGeometry = face.common(rawWireSet)

    GenUtils._addDebugShape(rawPathGeometry, "rawPathGeometry")  # Debugging

    return rawPathGeometry


# Regular wire linking function
def _Link_Regular(rawPathGeometry):
    """_Link_Regular()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
    GenUtils._debugMsg("_Link_Regular()")

    allGroups = []
    allWires = []

    def isOriented(direction, p0, p1):
        oriented = p1.sub(p0).normalize()
        if PathGeom.isRoughly(direction.sub(oriented).Length, 0.0):
            return True
        return False

    i = 0
    edges = rawPathGeometry.Edges
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


# 3D projected wire linking function
def _Link_Projected(wireList, cutDirection, cutReversed=False):
    """_Link_Projected(wireList, cutDirection, cutReversed=False)... Apply necessary linking and orientation to 3D wires."""
    # FreeCAD.Console.PrintError("_Link_Projected() `cutReversed` flag not active.\n")
    allWires = []
    allGroups = []
    flipped = 0

    # Group collinear wires
    w = wireList[0]
    v1 = w.Vertexes[0].Point
    v2 = w.Vertexes[-1].Point
    p1 = FreeCAD.Vector(v1.x, v1.y, 0.0)
    p2 = FreeCAD.Vector(v2.x, v2.y, 0.0)
    collinearGroup = [w]
    drctn = p2.sub(p1).normalize()
    for wire in wireList[1:]:
        v3 = wire.Vertexes[0].Point
        p3 = FreeCAD.Vector(v3.x, v3.y, 0.0)
        # Check if first vertex of next wire is collinear
        if GenUtils._isCollinear(p1, p2, p3):
            # Wire is in line with current group
            if GenUtils._isOrientedTheSame(drctn, wire):
                collinearGroup.append(wire)
            else:
                collinearGroup.append(GenUtils.flipWire(wire))
        else:
            # Save current group and restart collinear group with rotate reference points
            allGroups.append(collinearGroup)
            p1 = p3
            v2 = wire.Vertexes[-1].Point
            p2 = FreeCAD.Vector(v2.x, v2.y, 0.0)
            if GenUtils._isOrientedTheSame(drctn, wire):
                collinearGroup = [wire]
            else:
                collinearGroup = [GenUtils.flipWire(wire)]
    if len(collinearGroup) > 0:
        allGroups.append(collinearGroup)

    # Order and orient wires as needed
    if cutDirection == "Clockwise":
        for g in allGroups:
            allWires.extend(g)
    else:
        for g in allGroups:
            if cutReversed and len(g) > 1:
                g.reverse()
            flipped = [GenUtils.flipWire(w) for w in g]
            flipped.reverse()
            allWires.extend(flipped)

    return allWires


# Geometry to paths methods
def _buildStartPath(retractHeight, startPoint=None):
    """_buildStartPath(retractHeight, startPoint=None) ... Convert Offset pattern wires to paths."""
    GenUtils._debugMsg("_buildStartPath()")

    paths = [Path.Command("G0", {"Z": retractHeight, "F": RAPID_VERT})]
    if startPoint is not None:
        paths.append(
            Path.Command(
                "G0",
                {
                    "X": startPoint.x,
                    "Y": startPoint.y,
                    "F": RAPID_HORIZ,
                },
            )
        )

    return paths


def _buildLinePaths(
    wireList, retractHeight, finalDepth, keepToolDown, keepToolDownThreshold, toolRadius
):
    """_buildLinePaths() ... Convert Line-based wires to paths."""
    GenUtils._debugMsg("_buildLinePaths()")
    paths = []
    lastEdge = None

    for wire in wireList:
        if finalDepth is not None:
            wire.translate(FreeCAD.Vector(0, 0, finalDepth))

        e0 = wire.Edges[0]

        if finalDepth is None:
            finalDep = e0.Vertexes[0].Z
        else:
            finalDep = finalDepth

        if keepToolDown and lastEdge is not None:
            # Make transition if keep tool down
            # p1 =
            # p2 =
            # if isMoveInRegion(toolRadius, TARGET_REGION, p1, p2, maxWidth=0.0002):
            pass

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
        paths.append(Path.Command("G0", {"Z": retractHeight, "F": RAPID_VERT}))
        paths.append(Path.Command("G1", {"Z": finalDep, "F": FEED_VERT}))

        for e in wire.Edges:
            paths.extend(PathGeom.cmdsForEdge(e, hSpeed=FEED_HORIZ, vSpeed=FEED_VERT))
            lastEdge = e

        paths.append(Path.Command("G0", {"Z": retractHeight, "F": RAPID_VERT}))

    # GenUtils._debugMsg("_buildLinePaths() path count: {}".format(len(paths)))
    return paths


# Public functions
def generatePathGeometry(
    flatFace,
    toolRadius,
    cutOutWidth,
    patternCenterAt="CenterOfBoundBox",
    patternCenterCustom=FreeCAD.Vector(0.0, 0.0, 0.0),
    cutPatternAngle=0.0,
    cutPatternReversed=False,
    cutDirection="Clockwise",
):
    """
    Generates a path geometry shape from an assigned pattern for conversion to tool paths.
    Arguments:
        flatFace:             face shape to serve as base for path geometry generation
        toolRadius:         tool radius
        stepOver:           step over percentage
        patternCenterAt:    choice of centering options
        patternCenterCustom: custom (x, y, 0.0) center point
        cutPatternAngle:    rotation angle applied to rotatable patterns
        cutPatternReversed: boolean to reverse cut pattern from inside-out to outside-in
        cutDirection:       conventional or climb

    Call this method to execute the path generation code in LineClearingGenerator class.
    Returns True on success.  Access class instance `pathGeometry` attribute for path geometry.
    """
    GenUtils._debugMsg("generatePathGeometry()")
    PathLog.track(
        f"(\ntool radius: {toolRadius} mm\n step over {cutOutWidth}%\n pattern center at {patternCenterAt}\n pattern center custom {patternCenterCustom}\n cut pattern angle {cutPatternAngle}\n cutPatternReversed {cutPatternReversed}\n cutDirection {cutDirection})"
    )

    # Argument validation
    if not type(cutOutWidth) is float:
        raise ValueError("Cutout width must be a float")

    if cutOutWidth < 0.0:
        raise ValueError("Cutout width less than zero")

    if patternCenterAt not in GenUtils.patternCenterAtChoices:
        raise ValueError("Invalid value for 'patternCenterAt' argument")

    if not type(patternCenterCustom) is FreeCAD.Vector:
        raise ValueError("Pattern center custom must be a FreeCAD vector")

    if not type(cutPatternAngle) is float:
        raise ValueError("Cut pattern angle must be a float")

    if not type(cutPatternReversed) is bool:
        raise ValueError("Cut pattern reversed must be a boolean")

    if cutDirection not in ("Clockwise", "CounterClockwise"):
        raise ValueError("Invalid value for 'cutDirection' argument")

    if hasattr(flatFace, "Area") and PathGeom.isRoughly(flatFace.Area, 0.0):
        raise ValueError("Target face has no area.")

    if not PathGeom.isRoughly(flatFace.BoundBox.ZLength, 0.0):
        raise ValueError("Target face is not horizontal plane.")

    if not PathGeom.isRoughly(flatFace.BoundBox.ZMin, 0.0):
        raise ValueError("Target face is not at Z=0.0 height.")

    global IS_CENTER_SET
    global GEOM_ATTRIBUTES
    pathGeometry = []

    geomAttributes = GenUtils._prepareAttributes(
        flatFace,
        toolRadius,
        cutOutWidth,
        IS_CENTER_SET,
        USE_STATIC_CENTER,
        patternCenterAt,
        patternCenterCustom,
    )
    if geomAttributes is not None:
        GEOM_ATTRIBUTES = geomAttributes
    (centerOfPattern, halfDiag, __, halfPasses) = GEOM_ATTRIBUTES  # __ is cutPasses

    rawGeoList = _line(
        halfDiag,
        patternCenterAt,
        halfPasses,
        cutOutWidth,
        cutDirection,
        cutPatternReversed,
    )

    rawPathGeometry = _generatePathGeometry(
        flatFace, rawGeoList, cutPatternAngle, centerOfPattern
    )

    pathGeom = _Link_Regular(rawPathGeometry)
    pathGeometry.extend(pathGeom)
    IS_CENTER_SET = True

    # GenUtils._showGeom(pathGeometry)

    return pathGeometry


def geometryToGcode(
    lineGeometry,
    retractHeight,
    finalDepth,
    keepToolDown,
    keepToolDownThreshold,
    startPoint,
    toolRadius,
    minTravel=False,
):
    """geometryToGcode(lineGeometry, retractHeight, finalDepth, keepToolDown, keepToolDownThreshold, startPoint, minTravel=False) Return line geometry converted to Gcode"""
    GenUtils._debugMsg("geometryToGcode()")

    # Argument validation
    if not type(retractHeight) is float:
        raise ValueError("Retract height must be a float")

    if not type(finalDepth) is float and finalDepth is not None:
        raise ValueError("Final depth must be a float")

    if finalDepth is not None and finalDepth > retractHeight:
        raise ValueError("Retract height must be greater than or equal to final depth")

    if not type(keepToolDown) is bool:
        raise ValueError("Keep tool down must be a boolean")

    if not type(keepToolDownThreshold) is float:
        raise ValueError("Keep tool down must be a boolean")

    if not type(minTravel) is bool:
        raise ValueError("Min travel must be a boolean")

    commandList = _buildLinePaths(
        lineGeometry,
        retractHeight,
        finalDepth,
        keepToolDown,
        keepToolDownThreshold,
        toolRadius,
    )

    if len(commandList) > 0:
        commands = _buildStartPath(retractHeight, startPoint)
        commands.extend(commandList)

        return commands
    else:
        GenUtils._debugMsg("No commands in commandList")
    return []


def generate(
    fusedFace,
    toolController,
    finalDepth,
    retractHeight,
    region,
    toolRadius,
    pathType,
    stepOver,
    depthOffset,
    cutDirection,
    cutPatternAngle,
    cutPatternCenterAt,
    cutPatternCenterCustom,
    sampleInterval,
    dropTolerance,
    cutPatternReversed,
    optimizePaths,
    keepToolDown,
    keepToolDownThreshold,
    startPoint,
    jobTolerance,
):
    global TARGET_REGION
    global PATH_TYPE
    global FEED_VERT
    global FEED_HORIZ
    global RAPID_VERT
    global RAPID_HORIZ
    global IS_CENTER_SET
    allWires = []
    allPaths = []

    # Argument validation
    if not type(stepOver) is float:
        raise ValueError("Step over must be a float")

    if stepOver < 0.1 or stepOver > 100.0:
        raise ValueError("Step over exceeds limits")

    PATH_TYPE = pathType
    FEED_VERT = toolController.VertFeed.Value
    FEED_HORIZ = toolController.HorizFeed.Value
    RAPID_VERT = toolController.VertRapid.Value
    RAPID_HORIZ = toolController.HorizRapid.Value
    cutOutWidth = 2.0 * toolRadius * (stepOver / 100.0)
    offsetValue = -1.0 * (toolRadius - (jobTolerance / 10.0))
    offsetFaces = GenUtils._offsetFaceRegion(region, offsetValue)

    for face in offsetFaces:
        TARGET_REGION = face
        if RESET_ATTRIBUTES:
            IS_CENTER_SET = False
        GenUtils._addDebugShape(face, "Face")
        pathGeomList = generatePathGeometry(
            face,
            toolRadius,
            cutOutWidth,
            cutPatternCenterAt,
            cutPatternCenterCustom,
            cutPatternAngle,
            cutPatternReversed,
            cutDirection,
        )

        if PATH_TYPE == "3D":
            # Project path geometry onto origninal faces
            projectionWires = DropCut.getProjectedGeometry(fusedFace, pathGeomList)
            projWires = _Link_Projected(
                projectionWires, cutDirection, cutPatternReversed
            )
            # Apply drop cut to 3D projected wires to get point set
            toolShape = GenUtils.getToolShape(toolController)
            pointsLists = DropCut.dropCutWires(
                projWires,
                fusedFace,
                toolShape,
                sampleInterval,
                dropTolerance,
                optimizePaths,
            )

            lines = DropCut.pointsToLines(pointsLists, depthOffset)
            paths = geometryToGcode(
                lines,
                retractHeight,
                finalDepth,
                keepToolDown,
                keepToolDownThreshold,
                startPoint,
                toolRadius,
            )

        else:
            if finalDepth is None:
                finalDep = fusedFace.BoundBox.ZMax + depthOffset
            else:
                finalDep = finalDepth + depthOffset

            lines = pathGeomList
            paths = geometryToGcode(
                lines,
                retractHeight,
                finalDep,
                keepToolDown,
                keepToolDownThreshold,
                startPoint,
                toolRadius,
            )

        allWires.extend(lines)
        allPaths.extend(paths)
        IS_CENTER_SET = USE_STATIC_CENTER
    # Efor

    return allWires, allPaths


# Macro usage functions
def _getUserInput():
    # Get cut pattern settings from user
    guiInput = GenUtils.Gui_Input.GuiInput()
    guiInput.setWindowTitle("Line Pattern Settings")
    guiInput.addComboBox("Path Type", GenUtils.PATHTYPES)
    so = guiInput.addDoubleSpinBox("Step over %", 100.0)
    so.setMaximum(100.0)
    so.setValue(100.0)
    do = guiInput.addDoubleSpinBox("Depth Offset", 0.0)
    do.setMinimum(-99999999)
    do.setMaximum(99999999)
    guiInput.addComboBox("Cut Direction", GenUtils.CUTDIRECTIONS)
    cpa = guiInput.addDoubleSpinBox("Cut Pattern Angle", 0.0)
    cpa.setMinimum(0.0)
    cpa.setMaximum(360.0)
    guiInput.addComboBox("Cut Pattern Center At", GenUtils.PATTERNCENTERS)
    x, y, z = guiInput.addDoubleVector(
        "Pattern Center Custom", FreeCAD.Vector(0.0, 0.0, 0.0)
    )
    x.setMinimum(-999999999.9)
    x.setMaximum(999999999.9)
    y.setMinimum(-999999999.9)
    y.setMaximum(999999999.9)
    z.setMinimum(-999999999.9)
    z.setMaximum(999999999.9)
    si = guiInput.addDoubleSpinBox("Sample Interval (0.1 to 10)", 1.0)
    si.setMinimum(0.1)
    si.setMaximum(10.0)
    dt = guiInput.addDoubleSpinBox("Dropcut Tolerance (0.001 to 10)", 0.1)
    dt.setMinimum(0.001)
    dt.setMaximum(10.0)
    guiInput.addCheckBox("Reverse Cut Pattern")
    guiInput.addCheckBox("Optimize paths")
    return guiInput.execute()


def _getUserTestInput():
    # Get cut pattern settings from user
    guiInput = GenUtils.Gui_Input.GuiInput()
    guiInput.setWindowTitle("Run Macro Tests")
    guiInput.addCheckBox("Test Line Macro")
    guiInput.addCheckBox("Debug Mode")
    co = guiInput.addCheckBox("Create operations")
    co.setChecked(True)
    return guiInput.execute()


def executeAsMacro():
    import time

    timeStart = time.time()
    # GenUtils.isDebug = True
    # GenUtils.showDebugShapes = True

    job, tc = GenUtils.getJobAndToolController()
    if job is None:
        print("No Job returned.")
        return

    # Get selected faces and combine regions
    region, fusedFace = Macro_CombineRegions._executeAsMacro()
    if region is None:
        print("No combined region returned")
        return
    GenUtils._addDebugShape(region, "Region")

    values = _getUserInput()
    if values is None:
        print("No cut pattern settings returned from user")
        return
    (
        pathType,
        stepOver,
        depthOffset,
        cutDirection,
        cutPatternAngle,
        cutPatternCenterAt,
        cutPatternCenterCustom,
        sampleInterval,
        dropTolerance,
        cutPatternReversed,
        optimizePaths,
    ) = values

    toolDiameter = (
        tc.Tool.Diameter.Value
        if hasattr(tc.Tool.Diameter, "Value")
        else float(tc.Tool.Diameter)
    )
    toolRadius = toolDiameter / 2.0
    retractHeight = fusedFace.BoundBox.ZMax + 5.0
    finalDepth = None
    keepToolDown = False
    keepToolDownThreshold = 2.5
    startPoint = None
    jobTolerance = 0.001

    lines, paths = generate(
        fusedFace,
        tc,
        finalDepth,
        retractHeight,
        region,
        toolRadius,
        pathType,
        stepOver,
        depthOffset,
        cutDirection,
        cutPatternAngle,
        cutPatternCenterAt,
        cutPatternCenterCustom,
        sampleInterval,
        dropTolerance,
        cutPatternReversed,
        optimizePaths,
        keepToolDown,
        keepToolDownThreshold,
        startPoint,
        jobTolerance,
    )

    # GenUtils._showGeom(lines)

    op = GenUtils.addCustomOpToJob(job, tc)
    op.Label = "Line_" + pathType
    op.Comment = f"tool radius: {toolRadius} mm;  step over {stepOver} %;  pattern center at {cutPatternCenterAt};  pattern center custom {cutPatternCenterCustom};  cut pattern angle {cutPatternAngle};  cutPatternReversed {cutPatternReversed};  cutDirection {cutDirection}"
    if isinstance(paths, list):
        op.Gcode = ["G90"] + [c.toGCode() for c in paths]
    else:
        op.Gcode = ["G90"] + [c.toGCode() for c in paths.Commands]

    FreeCAD.ActiveDocument.recompute()
    workTime = time.time() - timeStart
    print(f"Processing time: {workTime}")


def testMacro(debug=False, createOps=True):
    global IS_TEST_MODE
    import time

    timeStart = time.time()
    IS_TEST_MODE = True
    if debug:
        GenUtils.isDebug = True
        GenUtils.showDebugShapes = True
    else:
        GenUtils.isDebug = False
        GenUtils.showDebugShapes = False

    job, tc = GenUtils.getJobAndToolController()
    if job is None:
        print("No Job returned.")
        return

    # Get selected faces and combine regions
    region, fusedFace = Macro_CombineRegions._executeAsMacro()
    if region is None:
        print("No combined region returned")
        return
    GenUtils._addDebugShape(region, "Region")

    tests = [
        (
            # finalDepth,
            # retractHeight,
            # pathType,
            # stepOver,
            # depthOffset,
            # cutDirection,
            # cutPatternAngle,
            # cutPatternCenterAt,
            # cutPatternCenterCustom,
            # sampleInterval,
            # dropTolerance,
            # cutPatternReversed,
            # optimizePaths,
        ),
        (
            None,  # finalDepth
            fusedFace.BoundBox.ZMax + 5.0,  # retractHeight
            "2D",  # pathType
            50.0,  # stepOver
            0.0,  # depthOffset
            "Clockwise",  # cutDirection
            0.0,  # cutPatternAngle
            "CenterOfBoundBox",  # cutPatternCenterAt
            FreeCAD.Vector(0.0, 0.0, 0.0),  # cutPatternCenterCustom
            1.0,  # sampleInterval
            0.1,  # dropTolerance
            False,  # cutPatternReversed
            False,  # optimizePaths
        ),
        (
            None,  # finalDepth
            fusedFace.BoundBox.ZMax + 15.0,  # retractHeight
            "2D",  # pathType
            75.0,  # stepOver
            0.0,  # depthOffset
            "Clockwise",  # cutDirection
            20.0,  # cutPatternAngle
            "CenterOfBoundBox",  # cutPatternCenterAt
            FreeCAD.Vector(0.0, 0.0, 0.0),  # cutPatternCenterCustom
            1.0,  # sampleInterval
            0.1,  # dropTolerance
            False,  # cutPatternReversed
            False,  # optimizePaths
        ),
        (
            None,  # finalDepth
            fusedFace.BoundBox.ZMax + 15.0,  # retractHeight
            "2D",  # pathType
            75.0,  # stepOver
            0.0,  # depthOffset
            "CounterClockwise",  # cutDirection CounterClockwise
            115.0,  # cutPatternAngle
            "CenterOfBoundBox",  # cutPatternCenterAt
            FreeCAD.Vector(0.0, 0.0, 0.0),  # cutPatternCenterCustom
            0.5,  # sampleInterval
            0.05,  # dropTolerance
            True,  # cutPatternReversed
            False,  # optimizePaths
        ),
        (
            None,  # finalDepth
            fusedFace.BoundBox.ZMax + 15.0,  # retractHeight
            "3D",  # pathType
            80.0,  # stepOver
            5.0,  # depthOffset
            "Clockwise",  # cutDirection
            70.0,  # cutPatternAngle
            "CenterOfBoundBox",  # cutPatternCenterAt
            FreeCAD.Vector(0.0, 0.0, 0.0),  # cutPatternCenterCustom
            0.5,  # sampleInterval
            0.05,  # dropTolerance
            False,  # cutPatternReversed
            False,  # optimizePaths
        ),
        (
            None,  # finalDepth
            fusedFace.BoundBox.ZMax + 15.0,  # retractHeight
            "3D",  # pathType
            70.0,  # stepOver
            0.0,  # depthOffset
            "Clockwise",  # cutDirection
            25.0,  # cutPatternAngle
            "CenterOfBoundBox",  # cutPatternCenterAt
            FreeCAD.Vector(0.0, 0.0, 0.0),  # cutPatternCenterCustom
            0.5,  # sampleInterval
            0.05,  # dropTolerance
            False,  # cutPatternReversed
            False,  # optimizePaths
        ),
        (
            None,  # finalDepth
            fusedFace.BoundBox.ZMax + 15.0,  # retractHeight
            "3D",  # pathType
            75.0,  # stepOver
            0.0,  # depthOffset
            "Clockwise",  # cutDirection CounterClockwise
            115.0,  # cutPatternAngle
            "CenterOfBoundBox",  # cutPatternCenterAt
            FreeCAD.Vector(0.0, 0.0, 0.0),  # cutPatternCenterCustom
            0.5,  # sampleInterval
            0.05,  # dropTolerance
            True,  # cutPatternReversed
            False,  # optimizePaths
        ),
        (
            None,  # finalDepth
            fusedFace.BoundBox.ZMax + 15.0,  # retractHeight
            "3D",  # pathType
            75.0,  # stepOver
            0.0,  # depthOffset
            "CounterClockwise",  # cutDirection CounterClockwise
            115.0,  # cutPatternAngle
            "CenterOfBoundBox",  # cutPatternCenterAt
            FreeCAD.Vector(0.0, 0.0, 0.0),  # cutPatternCenterCustom
            0.5,  # sampleInterval
            0.05,  # dropTolerance
            True,  # cutPatternReversed
            False,  # optimizePaths
        ),
    ]

    toolDiameter = (
        tc.Tool.Diameter.Value
        if hasattr(tc.Tool.Diameter, "Value")
        else float(tc.Tool.Diameter)
    )
    toolRadius = toolDiameter / 2.0
    retractHeight = fusedFace.BoundBox.ZMax + 5.0
    finalDepth = None
    keepToolDown = False
    keepToolDownThreshold = 2.5
    startPoint = None
    jobTolerance = 0.001

    for values in tests[1:]:
        # unpack values
        (
            finalDepth,
            retractHeight,
            pathType,
            stepOver,
            depthOffset,
            cutDirection,
            cutPatternAngle,
            cutPatternCenterAt,
            cutPatternCenterCustom,
            sampleInterval,
            dropTolerance,
            cutPatternReversed,
            optimizePaths,
        ) = values

        # execute macro for given values
        lines, paths = generate(
            fusedFace,
            tc,
            finalDepth,
            retractHeight,
            region,
            toolRadius,
            pathType,
            stepOver,
            depthOffset,
            cutDirection,
            cutPatternAngle,
            cutPatternCenterAt,
            cutPatternCenterCustom,
            sampleInterval,
            dropTolerance,
            cutPatternReversed,
            optimizePaths,
            keepToolDown,
            keepToolDownThreshold,
            startPoint,
            jobTolerance,
        )

        if createOps:
            op = GenUtils.addCustomOpToJob(job, tc)
            op.Label = "Line_" + pathType
            op.Comment = f"tool radius: {toolRadius} mm;  step over {stepOver} %;  pattern center at {cutPatternCenterAt};  pattern center custom {cutPatternCenterCustom};  cut pattern angle {cutPatternAngle};  cutPatternReversed {cutPatternReversed};  cutDirection {cutDirection}"
            if isinstance(paths, list):
                op.Gcode = ["G90"] + [c.toGCode() for c in paths]
            else:
                op.Gcode = ["G90"] + [c.toGCode() for c in paths.Commands]

        FreeCAD.ActiveDocument.recompute()
    # Efor
    workTime = time.time() - timeStart
    print(f"Processing time: {workTime}")


print("Imported Generator_Line")

if IS_MACRO and FreeCAD.GuiUp:
    isTestValues = _getUserTestInput()
    if isTestValues[0]:
        testMacro(isTestValues[1], isTestValues[2])
    else:
        executeAsMacro()
