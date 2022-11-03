# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2018 Kresimir Tusek <kresimir.tusek@gmail.com>          *
# *   Copyright (c) 2019-2021 Schildkroet                                   *
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
import Path
import Path.Log as PathLog
import PathScripts.PathUtils as PathUtils
import Part
import Path.Geom as PathGeom
import Path.Op.Util as PathOpTools
import Generator_Utilities
import math
import area


__title__ = "Path Adaptive Path Geometry Generator"
__author__ = "Kresimir Tusek"
__url__ = "http://www.freecadweb.org"
__doc__ = "Path strategies available for path generation."
__contributors__ = "Schildkroet"


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())

PATHTYPES = ["2D", "3D"]
PATHTYPE = "2D"

IS_MACRO = False

isDebug = True  # True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
showDebugShapes = False

_face = None
_centerOfMass = None
_centerOfPattern = None
_halfDiag = None
_halfPasses = None
_isCenterSet = False
_startPoint = None
_toolRadius = None
_rawPathGeometry = None
patternCenterAtChoices = ("CenterOfMass", "CenterOfBoundBox", "XminYmin", "Custom")

_useStaticCenter = True  # Set True to use static center for all faces created by offsets and step downs.  Set False for dynamic centers based on PatternCenterAt
_targetFace = None
_retractHeight = None
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

# Adaptive-specific attributes
_adaptiveResults = None
_operationType = None
_cutSide = None
_forceInsideOut = None
_liftDistance = None
_finishingProfile = None
_helixAngle = None
_helixConeAngle = None
_useHelixArcs = None
_helixDiameterLimit = None
_keepToolDownRatio = None
_adaptiveTolerance = None
_stockObj = None
_clearanceHeight = None
_safeHeight = None
_startDepth = None
_useHelixEntry = False
_finalDepth = None


def _debugMsg(msg, isError=False):
    """_debugMsg(msg)
    If `self.isDebug` flag is True, the provided message is printed in the Report View.
    If not, then the message is assigned a debug status.
    """
    if isError:
        PathLog.error("PathGeometryGenerator: " + msg + "\n")
        return

    if isDebug:
        # PathLog.info(msg)
        FreeCAD.Console.PrintMessage("PathGeometryGenerator: " + msg + "\n")
    else:
        PathLog.debug(msg)


def _addDebugShape(shape, name="debug"):
    if isDebug and showDebugShapes:
        do = FreeCAD.ActiveDocument.addObject("Part::Feature", "debug_" + name)
        do.Shape = shape
        do.purgeTouched()


# Raw cut pattern geometry generation methods
def discretizeFace_unused(face):
    edges = []
    for w in _targetFace.Wires:
        for e in w.Edges:
            edges.append([_discretize(e)])
    return edges


def _Adaptive():
    """_Adaptive()...
    Returns raw set of Adaptive wires at Z=0.0 using a condensed version of code from the Adaptive operation.
    Currently, no helix entry wires are included, only the clearing portion of wires.
    """
    global _adaptiveResults
    _adaptiveResults = []
    # PathLog.info("*** Adaptive path geometry generation started...")
    # startTime = time.time()

    pathArray = []
    _targetFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - _targetFace.BoundBox.ZMin))
    for w in _targetFace.Wires:
        for e in w.Edges:
            pathArray.append([_discretize(e)])

    path2d = _convertTo2d(pathArray)

    stockPaths = []
    if hasattr(_stockObj, "StockType") and _stockObj.StockType == "CreateCylinder":
        stockPaths.append([_discretize(_stockObj.Shape.Edges[0])])

    else:
        stockBB = _stockObj.Shape.BoundBox
        v = []
        v.append(FreeCAD.Vector(stockBB.XMin, stockBB.YMin, 0))
        v.append(FreeCAD.Vector(stockBB.XMax, stockBB.YMin, 0))
        v.append(FreeCAD.Vector(stockBB.XMax, stockBB.YMax, 0))
        v.append(FreeCAD.Vector(stockBB.XMin, stockBB.YMax, 0))
        v.append(FreeCAD.Vector(stockBB.XMin, stockBB.YMin, 0))
        stockPaths.append([v])

    stockPath2d = _convertTo2d(stockPaths)

    opType = area.AdaptiveOperationType.ClearingInside
    if _operationType == "Clearing":
        if _cutSide == "Outside":
            opType = area.AdaptiveOperationType.ClearingOutside
        else:
            opType = area.AdaptiveOperationType.ClearingInside
    else:  # profile
        if _cutSide == "Outside":
            opType = area.AdaptiveOperationType.ProfilingOutside
        else:
            opType = area.AdaptiveOperationType.ProfilingInside

    a2d = area.Adaptive2d()
    a2d.stepOverFactor = 0.01 * _stepOver
    a2d.toolDiameter = _toolRadius * 2.0
    a2d.helixRampDiameter = _helixDiameterLimit
    a2d.keepToolDownDistRatio = _keepToolDownRatio
    a2d.stockToLeave = 0.0  # _materialAllowance
    a2d.tolerance = _adaptiveTolerance
    a2d.forceInsideOut = _forceInsideOut
    a2d.finishingProfile = _finishingProfile
    a2d.opType = opType

    def progressFn(tpaths):
        """progressFn(tpaths)... progress callback fn, if return true it will stop processing"""
        return False

    # EXECUTE
    adaptiveGeometry = []
    try:
        results = a2d.Execute(stockPath2d, path2d, progressFn)
    except Exception as ee:
        FreeCAD.Console.PrintError(str(ee) + "\n")
        return []
    else:
        # need to convert results to python object to be JSON serializable
        _adaptiveResults = []
        for result in results:
            _adaptiveResults.append(
                {
                    "HelixCenterPoint": result.HelixCenterPoint,
                    "StartPoint": result.StartPoint,
                    "AdaptivePaths": result.AdaptivePaths,
                    "ReturnMotionType": result.ReturnMotionType,
                }
            )

        # Generate geometry
        # PathLog.debug("Extracting wires from Adaptive data...")
        wires = []
        motionCutting = area.AdaptiveMotionType.Cutting
        for region in _adaptiveResults:
            for pth in region["AdaptivePaths"]:
                motion = pth[0]  # [0] contains motion type
                if motion == motionCutting:
                    edges = []
                    sp = pth[1][0]
                    x = sp[0]
                    y = sp[1]
                    p1 = FreeCAD.Vector(x, y, 0.0)
                    for pt in pth[1][1:]:  # [1] contains list of points
                        xx = pt[0]
                        yy = pt[1]
                        p2 = FreeCAD.Vector(xx, yy, 0.0)
                        if not PathGeom.isRoughly(p1.sub(p2).Length, 0.0):
                            edges.append(Part.makeLine(p1, p2))
                            p1 = p2
                    wires.append(Part.Wire(Part.__sortEdges__(edges)))
        adaptiveGeometry = wires
        # PathLog.info("*** Done. Elapsed time: %f sec" % (time.time()-startTime))
        return adaptiveGeometry


# Path linking methods
def _Link_Regular(rawPathGeometry):
    """_Link_Regular(rawPathGeometry)... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
    # No linking required.
    return rawPathGeometry.Wires


# 3D projected wire linking methods
def _Link_Projected(wireList, cutDirection, cutReversed=False):
    """_Link_Projected(wireList, cutDirection, cutReversed=False)... Apply necessary linking and orientation to 3D wires."""
    FreeCAD.Console.PrintError("_Link_Projected() `cutReversed` flag not active.\n")
    if cutDirection == "Clockwise":
        wires = []
        for w in wireList:
            wires.append(Generator_Utilities.orientWire(w, False))
        return wires
    else:
        wires = []
        for w in wireList:
            wires.append(Generator_Utilities.orientWire(w, True))
        wires.reverse()
        return wires


# Support methods
def _generatePathGeometry():
    """_generatePathGeometry()... Control function that generates path geometry wire sets."""
    _debugMsg("_generatePathGeometry()")

    _rawGeoList = _Adaptive()

    # Create compound object to bind all geometry
    geomShape = Part.makeCompound(_rawGeoList)

    _addDebugShape(geomShape, "rawPathGeomShape")  # Debugging

    # Identify intersection of cross-section face and lineset
    # rawWireSet = Part.makeCompound(geomShape.Wires)
    # _rawPathGeometry = _face.common(rawWireSet)
    rawPathGeometry = _face.common(geomShape)

    _addDebugShape(rawPathGeometry, "rawPathGeometry")  # Debugging

    linkedPathGeom = _Link_Regular(rawPathGeometry)

    return linkedPathGeom


# Private adaptive support methods
def _generateGCodeWithHelix(
    toolController, clearanceHeight, safeHeight, startDepth, finalDepth
):
    """_generateGCodeWithHelix(toolController, clearanceHeight, safeHeight, startDepth, finalDepth) ...
    Converts raw Adaptive algorithm data into gcode.
    Not currently active.  Will be modified to extract helix data as wires.
    Will be used for Adaptive cut pattern."""
    commandList = []
    _vertFeed = toolController.VertFeed.Value
    _vertRapid = toolController.VertRapid.Value
    _horizFeed = toolController.HorizFeed.Value
    _horizRapid = toolController.HorizRapid.Value
    motionCutting = area.AdaptiveMotionType.Cutting
    motionLinkClear = area.AdaptiveMotionType.LinkClear
    motionLinkNotClear = area.AdaptiveMotionType.LinkNotClear

    # pylint: disable=unused-argument
    if len(_adaptiveResults) == 0 or len(_adaptiveResults[0]["AdaptivePaths"]) == 0:
        return

    helixRadius = 0
    for region in _adaptiveResults:
        p1 = region["HelixCenterPoint"]
        p2 = region["StartPoint"]
        r = math.sqrt(
            (p1[0] - p2[0]) * (p1[0] - p2[0]) + (p1[1] - p2[1]) * (p1[1] - p2[1])
        )
        if r > helixRadius:
            helixRadius = r

    passStartDepth = startDepth

    length = 2 * math.pi * helixRadius

    helixAngleRad = math.pi * _helixAngle / 180.0
    depthPerOneCircle = length * math.tan(helixAngleRad)
    # print("Helix circle depth: {}".format(depthPerOneCircle))

    stepUp = _liftDistance
    if stepUp < 0:
        stepUp = 0

    # ml: this is dangerous because it'll hide all unused variables hence forward
    #     however, I don't know what lx and ly signify so I'll leave them for now
    # russ4262: I think that the `l` in `lx, ly, and lz` stands for `last`.

    # lx = _adaptiveResults[0]["HelixCenterPoint"][0]
    # ly = _adaptiveResults[0]["HelixCenterPoint"][1]
    lz = passStartDepth  # lz is likely `last Z depth`
    step = 0

    passEndDepth = finalDepth
    step = step + 1

    for region in _adaptiveResults:
        startAngle = math.atan2(
            region["StartPoint"][1] - region["HelixCenterPoint"][1],
            region["StartPoint"][0] - region["HelixCenterPoint"][0],
        )

        # lx = region["HelixCenterPoint"][0]
        # ly = region["HelixCenterPoint"][1]

        passDepth = passStartDepth - finalDepth  # passEndDepth

        p1 = region["HelixCenterPoint"]
        p2 = region["StartPoint"]
        helixRadius = math.sqrt(
            (p1[0] - p2[0]) * (p1[0] - p2[0]) + (p1[1] - p2[1]) * (p1[1] - p2[1])
        )

        # Helix ramp
        if helixRadius > 0.01:
            r = helixRadius - 0.01

            maxfi = passDepth / depthPerOneCircle * 2 * math.pi
            fi = 0
            offsetFi = -maxfi + startAngle - math.pi / 16

            helixStart = [
                region["HelixCenterPoint"][0] + r * math.cos(offsetFi),
                region["HelixCenterPoint"][1] + r * math.sin(offsetFi),
            ]

            commandList.append(Path.Command("(Helix to depth: %f)" % passEndDepth))

            if not _useHelixArcs:
                # rapid move to start point
                commandList.append(Path.Command("G0", {"Z": clearanceHeight}))
                commandList.append(
                    Path.Command(
                        "G0",
                        {
                            "X": helixStart[0],
                            "Y": helixStart[1],
                            "Z": clearanceHeight,
                        },
                    )
                )

                # rapid move to safe height
                commandList.append(
                    Path.Command(
                        "G0",
                        {
                            "X": helixStart[0],
                            "Y": helixStart[1],
                            "Z": safeHeight,
                        },
                    )
                )

                # move to start depth
                commandList.append(
                    Path.Command(
                        "G1",
                        {
                            "X": helixStart[0],
                            "Y": helixStart[1],
                            "Z": passStartDepth,
                            "F": _vertFeed,
                        },
                    )
                )

                if _helixConeAngle == 0:
                    while fi < maxfi:
                        x = region["HelixCenterPoint"][0] + r * math.cos(fi + offsetFi)
                        y = region["HelixCenterPoint"][1] + r * math.sin(fi + offsetFi)
                        z = passStartDepth - fi / maxfi * (
                            passStartDepth - passEndDepth
                        )
                        commandList.append(
                            Path.Command(
                                "G1",
                                {"X": x, "Y": y, "Z": z, "F": _vertFeed},
                            )
                        )
                        # lx = x
                        # ly = y
                        fi = fi + math.pi / 16

                    # one more circle at target depth to make sure center is cleared
                    maxfi = maxfi + 2 * math.pi
                    while fi < maxfi:
                        x = region["HelixCenterPoint"][0] + r * math.cos(fi + offsetFi)
                        y = region["HelixCenterPoint"][1] + r * math.sin(fi + offsetFi)
                        z = passEndDepth
                        commandList.append(
                            Path.Command(
                                "G1",
                                {"X": x, "Y": y, "Z": z, "F": _horizFeed},
                            )
                        )
                        # lx = x
                        # ly = y
                        fi = fi + math.pi / 16

                else:
                    # Cone
                    _HelixAngle = 360.0 - (_helixAngle * 4.0)

                    if _helixConeAngle > 6:
                        _helixConeAngle = 6

                    helixRadius *= 0.9

                    # Calculate everything
                    helix_height = passStartDepth - passEndDepth
                    r_extra = helix_height * math.tan(math.radians(_helixConeAngle))
                    HelixTopRadius = helixRadius + r_extra
                    helix_full_height = HelixTopRadius * (
                        math.cos(math.radians(_helixConeAngle))
                        / math.sin(math.radians(_helixConeAngle))
                    )

                    # Start height
                    z = passStartDepth
                    i = 0

                    # Default step down
                    z_step = 0.05

                    # Bigger angle, smaller step down
                    if _HelixAngle > 120:
                        z_step = 0.025
                    if _HelixAngle > 240:
                        z_step = 0.015

                    p = None
                    # Calculate conical helix
                    while z >= passEndDepth:
                        if z < passEndDepth:
                            z = passEndDepth

                        p = _calcHelixConePoint(
                            helix_full_height, i, HelixTopRadius, _HelixAngle
                        )
                        commandList.append(
                            Path.Command(
                                "G1",
                                {
                                    "X": p["X"] + region["HelixCenterPoint"][0],
                                    "Y": p["Y"] + region["HelixCenterPoint"][1],
                                    "Z": z,
                                    "F": _vertFeed,
                                },
                            )
                        )
                        z = z - z_step
                        i = i + z_step

                    # Calculate some stuff for arcs at bottom
                    p["X"] = p["X"] + region["HelixCenterPoint"][0]
                    p["Y"] = p["Y"] + region["HelixCenterPoint"][1]
                    x_m = (
                        region["HelixCenterPoint"][0]
                        - p["X"]
                        + region["HelixCenterPoint"][0]
                    )
                    y_m = (
                        region["HelixCenterPoint"][1]
                        - p["Y"]
                        + region["HelixCenterPoint"][1]
                    )
                    i_off = (x_m - p["X"]) / 2
                    j_off = (y_m - p["Y"]) / 2

                    # One more circle at target depth to make sure center is cleared
                    commandList.append(
                        Path.Command(
                            "G3",
                            {
                                "X": x_m,
                                "Y": y_m,
                                "Z": passEndDepth,
                                "I": i_off,
                                "J": j_off,
                                "F": _horizFeed,
                            },
                        )
                    )
                    commandList.append(
                        Path.Command(
                            "G3",
                            {
                                "X": p["X"],
                                "Y": p["Y"],
                                "Z": passEndDepth,
                                "I": -i_off,
                                "J": -j_off,
                                "F": _horizFeed,
                            },
                        )
                    )

            else:
                # Use arcs for helix - no conical shape support
                helixStart = [
                    region["HelixCenterPoint"][0] + r,
                    region["HelixCenterPoint"][1],
                ]

                # rapid move to start point
                commandList.append(Path.Command("G0", {"Z": clearanceHeight}))
                commandList.append(
                    Path.Command(
                        "G0",
                        {
                            "X": helixStart[0],
                            "Y": helixStart[1],
                            "Z": clearanceHeight,
                        },
                    )
                )

                # rapid move to safe height
                commandList.append(
                    Path.Command(
                        "G0",
                        {
                            "X": helixStart[0],
                            "Y": helixStart[1],
                            "Z": safeHeight,
                        },
                    )
                )

                # move to start depth
                commandList.append(
                    Path.Command(
                        "G1",
                        {
                            "X": helixStart[0],
                            "Y": helixStart[1],
                            "Z": passStartDepth,
                            "F": _vertFeed,
                        },
                    )
                )

                x = region["HelixCenterPoint"][0] + r
                y = region["HelixCenterPoint"][1]

                curDep = passStartDepth
                while curDep > (passEndDepth + depthPerOneCircle):
                    commandList.append(
                        Path.Command(
                            "G2",
                            {
                                "X": x - (2 * r),
                                "Y": y,
                                "Z": curDep - (depthPerOneCircle / 2),
                                "I": -r,
                                "F": _vertFeed,
                            },
                        )
                    )
                    commandList.append(
                        Path.Command(
                            "G2",
                            {
                                "X": x,
                                "Y": y,
                                "Z": curDep - depthPerOneCircle,
                                "I": r,
                                "F": _vertFeed,
                            },
                        )
                    )
                    curDep = curDep - depthPerOneCircle

                lastStep = curDep - passEndDepth
                if lastStep > (depthPerOneCircle / 2):
                    commandList.append(
                        Path.Command(
                            "G2",
                            {
                                "X": x - (2 * r),
                                "Y": y,
                                "Z": curDep - (lastStep / 2),
                                "I": -r,
                                "F": _vertFeed,
                            },
                        )
                    )
                    commandList.append(
                        Path.Command(
                            "G2",
                            {
                                "X": x,
                                "Y": y,
                                "Z": passEndDepth,
                                "I": r,
                                "F": _vertFeed,
                            },
                        )
                    )
                else:
                    commandList.append(
                        Path.Command(
                            "G2",
                            {
                                "X": x - (2 * r),
                                "Y": y,
                                "Z": passEndDepth,
                                "I": -r,
                                "F": _vertFeed,
                            },
                        )
                    )
                    commandList.append(
                        Path.Command(
                            "G1",
                            {
                                "X": x,
                                "Y": y,
                                "Z": passEndDepth,
                                "F": _vertFeed,
                            },
                        )
                    )

                # one more circle at target depth to make sure center is cleared
                commandList.append(
                    Path.Command(
                        "G2",
                        {
                            "X": x - (2 * r),
                            "Y": y,
                            "Z": passEndDepth,
                            "I": -r,
                            "F": _horizFeed,
                        },
                    )
                )
                commandList.append(
                    Path.Command(
                        "G2",
                        {
                            "X": x,
                            "Y": y,
                            "Z": passEndDepth,
                            "I": r,
                            "F": _horizFeed,
                        },
                    )
                )
                # lx = x
                # ly = y
        else:
            FreeCAD.Console.PrintError("Helix Radius must be greater than 0.01 mm.\n")
            break

        lz = passEndDepth
        z = clearanceHeight
        commandList.append(Path.Command("(Adaptive - depth: %f)" % passEndDepth))

        # add adaptive paths
        for pth in region["AdaptivePaths"]:
            motionType = pth[0]  # [0] contains motion type

            for pt in pth[1]:  # [1] contains list of points
                x = pt[0]
                y = pt[1]

                # dist = math.sqrt((x-lx)*(x-lx) + (y-ly)*(y-ly))

                if motionType == motionCutting:
                    z = passEndDepth
                    if z != lz:
                        commandList.append(
                            Path.Command("G1", {"Z": z, "F": _vertFeed})
                        )  # plunge at feed rate

                    commandList.append(
                        Path.Command("G1", {"X": x, "Y": y, "F": _horizFeed})
                    )  # feed to point

                elif motionType == motionLinkClear:
                    z = passEndDepth + stepUp
                    if z != lz:
                        commandList.append(
                            Path.Command("G0", {"Z": z})
                        )  # rapid to previous pass depth

                    commandList.append(
                        Path.Command("G0", {"X": x, "Y": y})
                    )  # rapid to point

                elif motionType == motionLinkNotClear:
                    z = clearanceHeight
                    if z != lz:
                        commandList.append(
                            Path.Command("G0", {"Z": z})
                        )  # rapid to clearance height

                    commandList.append(
                        Path.Command("G0", {"X": x, "Y": y})
                    )  # rapid to point

                # elif motionType == area.AdaptiveMotionType.LinkClearAtPrevPass:
                #     if lx!=x or ly!=y:
                #         commandList.append(Path.Command("G0", { "X": lx, "Y":ly, "Z":passStartDepth+stepUp}))
                #     commandList.append(Path.Command("G0", { "X": x, "Y":y, "Z":passStartDepth+stepUp}))

                # rotate values: current values become last for next loop
                # lx = x
                # ly = y
                lz = z

        # return to clearance height in this Z pass
        z = clearanceHeight
        if z != lz:
            commandList.append(Path.Command("G0", {"Z": z}))

        lz = z
    # Efor

    passStartDepth = passEndDepth

    # return to safe height in this Z pass
    z = clearanceHeight
    if z != lz:
        commandList.append(Path.Command("G0", {"Z": z}))
    lz = z

    return commandList


def _generateGCode(toolController, clearanceHeight, safeHeight, startDepth, finalDepth):
    """_generateGCode(toolController, clearanceHeight, safeHeight, startDepth, finalDepth) ...
    Converts raw Adaptive algorithm data into gcode.
    Not currently active.  Will be modified to extract helix data as wires.
    Will be used for Adaptive cut pattern."""

    if _useHelixEntry:
        return _generateGCodeWithHelix(_adaptiveResults, toolController)

    commandList = []
    _vertFeed = toolController.VertFeed.Value
    _vertRapid = toolController.VertRapid.Value
    _horizFeed = toolController.HorizFeed.Value
    _horizRapid = toolController.HorizRapid.Value

    motionCutting = area.AdaptiveMotionType.Cutting
    motionLinkClear = area.AdaptiveMotionType.LinkClear
    motionLinkNotClear = area.AdaptiveMotionType.LinkNotClear

    # pylint: disable=unused-argument
    if len(_adaptiveResults) == 0 or len(_adaptiveResults[0]["AdaptivePaths"]) == 0:
        return

    helixRadius = 0
    for region in _adaptiveResults:
        p1 = region["HelixCenterPoint"]
        p2 = region["StartPoint"]
        r = math.sqrt(
            (p1[0] - p2[0]) * (p1[0] - p2[0]) + (p1[1] - p2[1]) * (p1[1] - p2[1])
        )
        if r > helixRadius:
            helixRadius = r

    passStartDepth = startDepth

    length = 2 * math.pi * helixRadius

    helixAngleRad = math.pi * _helixAngle / 180.0
    depthPerOneCircle = length * math.tan(helixAngleRad)
    # print("Helix circle depth: {}".format(depthPerOneCircle))

    stepUp = _liftDistance
    if stepUp < 0:
        stepUp = 0

    # ml: this is dangerous because it'll hide all unused variables hence forward
    #     however, I don't know what lx and ly signify so I'll leave them for now
    # russ4262: I think that the `l` in `lx, ly, and lz` stands for `last`.

    # lx = _adaptiveResults[0]["HelixCenterPoint"][0]
    # ly = _adaptiveResults[0]["HelixCenterPoint"][1]
    lz = passStartDepth  # lz is likely `last Z depth`
    step = 0

    passEndDepth = finalDepth
    step = step + 1

    for region in _adaptiveResults:
        startAngle = math.atan2(
            region["StartPoint"][1] - region["HelixCenterPoint"][1],
            region["StartPoint"][0] - region["HelixCenterPoint"][0],
        )

        # lx = region["HelixCenterPoint"][0]
        # ly = region["HelixCenterPoint"][1]

        passDepth = passStartDepth - passEndDepth

        p1 = region["HelixCenterPoint"]
        p2 = region["StartPoint"]
        helixRadius = math.sqrt(
            (p1[0] - p2[0]) * (p1[0] - p2[0]) + (p1[1] - p2[1]) * (p1[1] - p2[1])
        )

        # rapid move to clearance height
        commandList.append(Path.Command("G0", {"Z": clearanceHeight}))
        commandList.append(
            Path.Command(
                "G0",
                {
                    "X": region["StartPoint"][0],
                    "Y": region["StartPoint"][1],
                    "Z": clearanceHeight,
                },
            )
        )
        # straight plunge to target depth
        commandList.append(
            Path.Command(
                "G1",
                {
                    "X": region["StartPoint"][0],
                    "Y": region["StartPoint"][1],
                    "Z": passEndDepth,
                    "F": _vertFeed,
                },
            )
        )

        lz = passEndDepth
        z = clearanceHeight
        commandList.append(Path.Command("(Adaptive - depth: %f)" % passEndDepth))

        # add adaptive paths
        for pth in region["AdaptivePaths"]:
            motionType = pth[0]  # [0] contains motion type

            for pt in pth[1]:  # [1] contains list of points
                x = pt[0]
                y = pt[1]

                # dist = math.sqrt((x-lx)*(x-lx) + (y-ly)*(y-ly))

                if motionType == motionCutting:
                    z = passEndDepth
                    if z != lz:
                        commandList.append(
                            Path.Command("G1", {"Z": z, "F": _vertFeed})
                        )  # plunge at feed rate

                    commandList.append(
                        Path.Command("G1", {"X": x, "Y": y, "F": _horizFeed})
                    )  # feed to point

                elif motionType == motionLinkClear:
                    z = passEndDepth + stepUp
                    if z != lz:
                        commandList.append(
                            Path.Command("G0", {"Z": z})
                        )  # rapid to previous pass depth

                    commandList.append(
                        Path.Command("G0", {"X": x, "Y": y})
                    )  # rapid to point

                elif motionType == motionLinkNotClear:
                    z = clearanceHeight
                    if z != lz:
                        commandList.append(
                            Path.Command("G0", {"Z": z})
                        )  # rapid to clearance height

                    commandList.append(
                        Path.Command("G0", {"X": x, "Y": y})
                    )  # rapid to point

                # elif motionType == area.AdaptiveMotionType.LinkClearAtPrevPass:
                #     if lx!=x or ly!=y:
                #         commandList.append(Path.Command("G0", { "X": lx, "Y":ly, "Z":passStartDepth+stepUp}))
                #     commandList.append(Path.Command("G0", { "X": x, "Y":y, "Z":passStartDepth+stepUp}))

                # rotate values: current values become last for next loop
                # lx = x
                # ly = y
                lz = z
        # Efor

        # return to clearance height in this Z pass
        z = clearanceHeight
        if z != lz:
            commandList.append(Path.Command("G0", {"Z": z}))

        lz = z
    # Efor

    passStartDepth = passEndDepth

    # return to safe height in this Z pass
    z = clearanceHeight
    if z != lz:
        commandList.append(Path.Command("G0", {"Z": z}))
    lz = z

    return commandList


# Private adaptive support methods
def _convertTo2d(pathArray):
    """_convertTo2d() ... Converts array of edge lists into list of point list pairs. Used for Adaptive cut pattern."""
    output = []
    for path in pathArray:
        pth2 = []
        for edge in path:
            for pt in edge:
                pth2.append([pt[0], pt[1]])
        output.append(pth2)
    return output


def _discretize(edge, flipDirection=False):
    """_discretize(edge, flipDirection=False) ... Discretizes an edge into a set of points. Used for Adaptive cut pattern."""
    pts = edge.discretize(Deflection=0.0001)
    if flipDirection:
        pts.reverse()

    return pts


# Geometry to paths methods
def _buildStartPath(toolController):
    """_buildStartPath() ... Convert Offset pattern wires to paths."""
    _debugMsg("_buildStartPath()")

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
    _debugMsg("_buildLinePaths()")

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

    _debugMsg("_buildLinePaths() path count: {}".format(len(paths)))
    return paths


def geometryToGcode3D(lineGeometry, toolController, retractHeight, finalDepth=None):
    """geometryToGcode(lineGeometry) Return line geometry converted to Gcode"""
    _debugMsg("geometryToGcode()")
    global _retractHeight
    global _finalDepth

    # Argument validation
    if not type(retractHeight) is float:
        raise ValueError("Retract height must be a float")

    if not type(finalDepth) is float and finalDepth is not None:
        raise ValueError("Final depth must be a float")

    if finalDepth is not None and finalDepth > retractHeight:
        raise ValueError("Retract height must be greater than or equal to final depth")

    _retractHeight = retractHeight
    _finalDepth = finalDepth

    commandList = _buildLinePaths(lineGeometry, toolController)
    if len(commandList) > 0:
        commands = _buildStartPath(toolController)
        commands.extend(commandList)
        return commands
    else:
        _debugMsg("No commands in commandList")
    return []


# Public functions
def setAdaptiveAttributes(
    useHelixEntry=True,
    materialAllowance=0.0,
    operationType="Clearing",
    cutSide="Inside",
    forceInsideOut=True,
    liftDistance=1.0,
    finishingProfile=True,
    helixAngle=10.0,
    helixConeAngle=0.0,
    useHelixArcs=False,
    helixDiameterLimit=2.5,
    keepToolDownRatio=2.0,
    adaptiveTolerance=0.1,
    clearanceHeight=10.0,
    safeHeight=5.0,
    startDepth=1.0,
    stockObj=None,
):
    """Call this method with appropriate argument values to prepare for Adaptive path geometry and path generation."""
    # Adaptive-specific attributes
    global _useHelixEntry
    global _materialAllowance
    global _operationType
    global _cutSide
    global _forceInsideOut
    global _liftDistance
    global _finishingProfile
    global _helixAngle
    global _helixConeAngle
    global _useHelixArcs
    global _helixDiameterLimit
    global _keepToolDownRatio
    global _adaptiveTolerance
    global _clearanceHeight
    global _safeHeight
    global _startDepth
    global _stockObj

    _useHelixEntry = useHelixEntry
    _materialAllowance = materialAllowance
    _operationType = operationType
    _cutSide = cutSide
    _forceInsideOut = forceInsideOut
    _liftDistance = liftDistance
    _finishingProfile = finishingProfile
    _helixAngle = helixAngle
    _helixConeAngle = helixConeAngle
    _useHelixArcs = useHelixArcs
    _helixDiameterLimit = helixDiameterLimit
    _keepToolDownRatio = keepToolDownRatio
    _adaptiveTolerance = adaptiveTolerance
    _clearanceHeight = clearanceHeight
    _safeHeight = safeHeight
    _startDepth = startDepth
    _stockObj = stockObj

    # if not useHelixEntry:
    #    _helixDiameterLimit = 0.01
    #    _helixAngle = 89.0

    # Apply limits to argument values
    if _adaptiveTolerance < 0.001:
        _adaptiveTolerance = 0.001

    if _helixAngle < 1.0:
        _helixAngle = 1.0
    if _helixAngle > 89.0:
        _helixAngle = 89.0

    if _helixConeAngle < 0.0:
        _helixConeAngle = 0.0
    if _helixConeAngle > 89.0:
        _helixConeAngle = 89.0


def geometryToGcode(lines, toolController, retractHeight, finalDepth):
    global _toolController
    global _retractHeight
    # global _finalDepth

    _toolController = toolController
    _retractHeight = retractHeight
    # _finalDepth = finalDepth

    return _generateGCode(
        toolController, _clearanceHeight, _safeHeight, _startDepth, finalDepth
    )


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
                cutDirection,
                stepOver,
                minTravel,
                keepToolDown,
                jobTolerance)...
    PathGeometryGenerator class constructor method.
    """
    """
    PathGeometryGenerator() class...
    Generates a path geometry shape from an assigned pattern for conversion to tool paths.
    Arguments:
        targetFace:         face shape to serve as base for path geometry generation
        patternCenterAt:    choice of centering options
        patternCenterCustom: custom (x, y, 0.0) center point
        cutPatternReversed: boolean to reverse cut pattern from inside-out to outside-in
        cutPatternAngle:    rotation angle applied to rotatable patterns
        cutDirection:       conventional or climb
        stepOver:           step over percentage
        materialAllowance:  positive material to allow(leave), negative additional material to remove
        minTravel:          boolean to enable minimum travel (feature not enabled at this time)
        keepToolDown:       boolean to enable keeping tool down (feature not enabled at this time)
        jobTolerance:       job tolerance value
    Available Patterns:
        - Adaptive, Circular, CircularZigZag, Grid, Line, LineOffset, Offset, Spiral, Triangle, ZigZag, ZigZagOffset
    Usage:
        - Instantiate this class.
        - Call the `setAdaptiveAttributes()` method with required attributes if you intend to use Adaptive cut pattern.
        - Call the `execute()` method to generate the path geometry. The path geometry has correctional linking applied.
        - The path geometry in now available in the `pathGeometry` attribute.
    Notes:
        - Grid and Triangle patterns are not rotatable at this time.
    """
    PathLog.debug("Generator_Adaptive.generatePathGeometry()")

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

    _face = None
    # _centerOfMass = None
    # _centerOfPattern = None
    # _halfDiag = None
    ##_halfPasses = None
    # _workingPlane = Part.makeCircle(2.0)  # make circle for workplane
    # _rawPathGeometry = None
    # _pathGeometry = []
    # _useStaticCenter = True  # Set True to use static center for all faces created by offsets and step downs.  Set False for dynamic centers based on PatternCenterAt
    _offsetDirection = -1.0  # 1.0=outside;  -1.0=inside
    # _targetFaceHeight = 0.0

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
    _cutOut = toolRadius * 2.0 * (_stepOver / 100.0)

    """execute()...
    Call this method to execute the path generation code in PathGeometryGenerator class.
    Returns True on success.  Access class instance `pathGeometry` attribute for path geometry.
    """
    _debugMsg("StrategyClearing.execute()")

    pathGeometry = []  # Reset list

    if hasattr(_targetFace, "Area") and PathGeom.isRoughly(_targetFace.Area, 0.0):
        _debugMsg("PathGeometryGenerator: No area in working shape.")
        return False

    _targetFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - _targetFace.BoundBox.ZMin))

    #  Apply simple radius shrinking offset for clearing pattern generation.
    ofstVal = _offsetDirection * (
        _toolRadius - (_jobTolerance / 10.0)  #  + _materialAllowance
    )
    offsetWF = PathUtils.getOffsetArea(_targetFace, ofstVal)
    if not offsetWF:
        _debugMsg("getOffsetArea() failed")
    elif len(offsetWF.Faces) == 0:
        _debugMsg("No offset faces to process for path geometry.")
    else:
        for fc in offsetWF.Faces:
            # fc.translate(FreeCAD.Vector(0.0, 0.0, _targetFaceHeight))

            useFaces = fc
            if useFaces.Faces:
                for f in useFaces.Faces:
                    f.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - f.BoundBox.ZMin))
                    _face = f
                    # _prepareAttributes()
                    pathGeom = _generatePathGeometry()
                    pathGeometry.extend(pathGeom)
            else:
                _debugMsg("No offset faces after cut with base shape.")

    # _debugMsg("Path with params: {}".format(_pathParams))

    return pathGeometry


print("Imported Generator_Adaptive")
