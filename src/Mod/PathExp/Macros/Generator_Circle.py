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
import Path.Geom as PathGeom
import Path.Op.Util as PathOpTools
import DraftGeomUtils
import Path
import Part
import math
import time


__title__ = "Path Circle Clearing Generator"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Generates the circle clearing toolpath for a 2D or 3D face"

if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())

# PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
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


if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


def _debugMsg(msg, isError=False):
    """_debugMsg(msg)
    If `_isDebug` flag is True, the provided message is printed in the Report View.
    If not, then the message is assigned a debug status.
    """
    if isError:
        FreeCAD.Console.PrintError("Generator_Circle: " + msg + "\n")
        return

    if isDebug:
        # PathLog.info(msg)
        FreeCAD.Console.PrintMessage("Generator_Circle: " + msg + "\n")
    else:
        PathLog.debug(msg)


def _addDebugShape(shape, name="debug"):
    if isDebug and showDebugShapes:
        do = FreeCAD.ActiveDocument.addObject("Part::Feature", "debug_" + name)
        do.Shape = shape
        do.purgeTouched()


# Raw cut pattern geometry generation methods
def _Circle():
    """_Circle()... Returns raw set of Circular wires at Z=0.0."""
    geomList = []
    radialPasses = _getRadialPasses()
    # minRad = _toolRadius * 2.0 * 0.45
    minRad = _toolRadius * 0.95

    if (_cutDirection == "Conventional" and not _cutPatternReversed) or (
        _cutDirection != "Conventional" and _cutPatternReversed
    ):
        direction = FreeCAD.Vector(0.0, 0.0, 1.0)
    else:
        direction = FreeCAD.Vector(0.0, 0.0, -1.0)

    # Make small center circle to start pattern
    if _stepOver > 50.0:
        circle = Part.makeCircle(minRad, _centerOfPattern, direction)
        geomList.append(circle)

    for lc in range(1, radialPasses + 1):
        rad = lc * _cutOut
        if rad >= minRad:
            wire = Part.Wire([Part.makeCircle(rad, _centerOfPattern, direction)])
            geomList.append(wire)

    if not _cutPatternReversed:
        geomList.reverse()

    return geomList


def _CircularZigZag():
    """_CircularZigZag()... Returns raw set of Circular ZigZag wires at Z=0.0."""
    geomList = []
    radialPasses = _getRadialPasses()
    minRad = _toolRadius * 2.0 * 0.45
    dirForward = FreeCAD.Vector(0, 0, 1)
    dirReverse = FreeCAD.Vector(0, 0, -1)

    if (_cutDirection == "CounterClockwise" and _cutPatternReversed) or (
        _cutDirection != "CounterClockwise" and not _cutPatternReversed
    ):
        activeDir = dirForward
        direction = 1
    else:
        activeDir = dirReverse
        direction = -1

    # Make small center circle to start pattern
    if _stepOver > 50:
        circle = Part.makeCircle(minRad, _centerOfPattern, activeDir)
        geomList.append(circle)
        direction *= -1  # toggle direction
        activeDir = (
            dirForward if direction > 0 else dirReverse
        )  # update active direction after toggle

    for lc in range(1, radialPasses + 1):
        rad = lc * _cutOut
        if rad >= minRad:
            wire = Part.Wire([Part.makeCircle(rad, _centerOfPattern, activeDir)])
            geomList.append(wire)
            direction *= -1  # toggle direction
            activeDir = (
                dirForward if direction > 0 else dirReverse
            )  # update active direction after toggle
    # Efor

    if not _cutPatternReversed:
        geomList.reverse()

    return geomList


# Path linking method
def _Link_Regular():
    """_Link_Regular()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
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
    if _cutPatternReversed:  # inside to out
        edges = sorted(
            _rawPathGeometry.Edges,
            key=lambda e: e.Curve.Center.sub(_centerOfPattern).Length,
        )
    else:
        edges = sorted(
            _rawPathGeometry.Edges,
            key=lambda e: e.Curve.Center.sub(_centerOfPattern).Length,
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
    if _isArcClockwise(w[0]):
        ring = [w]
    else:
        ring = [(flipWire(w[0]), w[1])]
    dist = w[1]

    for w in dataTups[1:]:
        if w[1] == dist:
            if _isArcClockwise(w[0]):
                ring.append(w)
            else:
                ring.append((flipWire(w[0]), w[1]))
        else:
            ring.sort(
                key=lambda tup: getAngle(
                    tup[0].Edges[0].valueAt(tup[0].Edges[0].FirstParameter)
                ),
                reverse=True,
            )
            ringGroups.append(ring)
            if _isArcClockwise(w[0]):
                ring = [w]
            else:
                ring = [(flipWire(w[0]), w[1])]
            dist = w[1]
    ring.sort(
        key=lambda tup: getAngle(
            tup[0].Edges[0].valueAt(tup[0].Edges[0].FirstParameter)
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
    if not _isArcClockwise(w[0]):
        ring = [w]
    else:
        ring = [(flipWire(w[0]), w[1])]
    dist = w[1]

    for w in dataTups[1:]:
        if w[1] == dist:
            if not _isArcClockwise(w[0]):
                ring.append(w)
            else:
                ring.append((flipWire(w[0]), w[1]))
        else:
            ring.sort(
                key=lambda tup: getAngle(
                    tup[0].Edges[0].valueAt(tup[0].Edges[0].FirstParameter)
                ),
            )
            ringGroups.append(ring)
            if not _isArcClockwise(w[0]):
                ring = [w]
            else:
                ring = [(flipWire(w[0]), w[1])]
            dist = w[1]
    ring.sort(
        key=lambda tup: getAngle(
            tup[0].Edges[0].valueAt(tup[0].Edges[0].FirstParameter)
        ),
    )
    ringGroups.append(ring)

    for r in ringGroups:
        allWires.extend([w for w, __ in r])

    return allWires


# Support methods
def _prepareAttributes():
    """_prepareAttributes()... Prepare instance attribute values for path generation."""
    global _isCenterSet
    global _centerOfPattern
    global _halfPasses
    global _centerOfMass
    global _halfDiag

    if _isCenterSet:
        if _useStaticCenter:
            return

    # Compute weighted center of mass of all faces combined
    if _patternCenterAt == "CenterOfMass":
        comF = _face.CenterOfMass
        _centerOfMass = FreeCAD.Vector(comF.x, comF.y, 0.0)
    _centerOfPattern = _getPatternCenter()

    # calculate line length
    deltaC = _targetFace.BoundBox.DiagonalLength
    lineLen = deltaC + (
        4.0 * _toolRadius
    )  # Line length to span boundbox diag with 2x cutter diameter extra on each end
    if _patternCenterAt == "Custom":
        distToCent = _face.BoundBox.Center.sub(_centerOfPattern).Length
        lineLen += distToCent
    _halfDiag = math.ceil(lineLen / 2.0)

    # Calculate number of passes
    cutPasses = (
        math.ceil(lineLen / _cutOut) + 1
    )  # Number of lines(passes) required to cover boundbox diagonal
    if _patternCenterAt == "Custom":
        _halfPasses = math.ceil(cutPasses)
    else:
        _halfPasses = math.ceil(cutPasses / 2.0)

    _isCenterSet = True


def _getPatternCenter():
    """_getPatternCenter()... Determine center of cut pattern and save in instance attribute."""
    centerAt = _patternCenterAt

    if centerAt == "CenterOfMass":
        cntrPnt = FreeCAD.Vector(_centerOfMass.x, _centerOfMass.y, 0.0)
    elif centerAt == "CenterOfBoundBox":
        cent = _face.BoundBox.Center
        cntrPnt = FreeCAD.Vector(cent.x, cent.y, 0.0)
    elif centerAt == "XminYmin":
        cntrPnt = FreeCAD.Vector(_face.BoundBox.XMin, _face.BoundBox.YMin, 0.0)
    elif centerAt == "Custom":
        cntrPnt = FreeCAD.Vector(_patternCenterCustom.x, _patternCenterCustom.y, 0.0)

    return cntrPnt


def _getRadialPasses():
    """_getRadialPasses()... Return number of radial passes required for circular and spiral patterns."""
    # recalculate number of passes, if need be
    radialPasses = _halfPasses
    if _patternCenterAt != "CenterOfBoundBox":
        # make 4 corners of boundbox in XY plane, find which is greatest distance to new circular center
        EBB = _face.BoundBox
        CORNERS = [
            FreeCAD.Vector(EBB.XMin, EBB.YMin, 0.0),
            FreeCAD.Vector(EBB.XMin, EBB.YMax, 0.0),
            FreeCAD.Vector(EBB.XMax, EBB.YMax, 0.0),
            FreeCAD.Vector(EBB.XMax, EBB.YMin, 0.0),
        ]
        dMax = 0.0
        for c in range(0, 4):
            dist = CORNERS[c].sub(_centerOfPattern).Length
            if dist > dMax:
                dMax = dist
        diag = dMax + (
            4.0 * _toolRadius
        )  # Line length to span boundbox diag with 2x cutter diameter extra on each end
        radialPasses = (
            math.ceil(diag / _cutOut) + 1
        )  # Number of lines(passes) required to cover boundbox diagonal

    return radialPasses


def getAngle(pnt):
    p = pnt.sub(_centerOfPattern)
    angle = math.degrees(math.atan2(p.y, p.x))
    if angle < 0.0:
        angle += 360.0
    return angle


def _edgeValueAtLength(edge, length):
    edgeLen = edge.Length
    typeId = edge.Curve.TypeId
    if typeId == "Part::GeomBSplineCurve":
        return edge.valueAt(length / edgeLen)
    elif typeId == "Part::GeomCircle":
        return edge.valueAt(
            edge.FirstParameter
            + length / edgeLen * (edge.LastParameter - edge.FirstParameter)
        )
    elif typeId == "Part::GeomLine":
        return edge.valueAt(edge.FirstParameter + length)
    elif typeId == "Part::GeomEllipse":
        return edge.valueAt(
            edge.FirstParameter
            + length / edgeLen * (edge.LastParameter - edge.FirstParameter)
        )
    else:
        print(f"_edgeValueAtLength() edge.Curve.TypeId, {typeId}, is not available.")
        return None


def _wireMidpoint(wire):
    wireLength = wire.Length
    halfLength = wireLength / 2.0

    if len(wire.Edges) == 1:
        return _edgeValueAtLength(wire.Edges[0], halfLength)

    dist = 0.0
    for e in wire.Edges:
        eLen = e.Length
        newDist = dist + eLen
        if PathGeom.isRoughly(newDist, halfLength):
            return e.valueAt(e.LastParameter)
        elif newDist > halfLength:
            return _edgeValueAtLength(e, halfLength - dist)
        dist = newDist


def _wireQuartilePoint(wire):
    wireLength = wire.Length
    quartileLength = wireLength / 4.0

    if len(wire.Edges) == 1:
        return _edgeValueAtLength(wire.Edges[0], quartileLength)

    dist = 0.0
    for e in wire.Edges:
        eLen = e.Length
        newDist = dist + eLen
        if PathGeom.isRoughly(newDist, quartileLength):
            return e.valueAt(e.LastParameter)
        elif newDist > quartileLength:
            return _edgeValueAtLength(e, quartileLength - dist)
        dist = newDist


def _isArcClockwise(wire):
    """_isArcClockwise(wire) Return True if arc is oriented clockwise.
    Incomming wire is assumed to be an arc shape (single arc edge, or discretized version)."""
    if wire.isClosed():
        # This method is not reliable for open wires
        # return PathOpTools._isWireClockwise(wire)
        p1 = wire.Edges[0].valueAt(wire.Edges[0].FirstParameter)
        p2 = _wireQuartilePoint(wire)

        a1 = getAngle(p1)
        if PathGeom.isRoughly(a1, 360.0):
            a1 = 0.0
        a2 = getAngle(p2) - a1
        if a2 < 0.0:
            a2 += 360.0

        if PathGeom.isRoughly(a2, 90.0):
            return True

        return False

    p1 = wire.Edges[0].valueAt(wire.Edges[0].FirstParameter)
    p2 = _wireQuartilePoint(wire)  # _wireMidpoint(wire)
    p3 = wire.Edges[-1].valueAt(wire.Edges[-1].LastParameter)

    a1 = getAngle(p1)
    if PathGeom.isRoughly(a1, 360.0):
        a1 = 0.0
    a2 = getAngle(p2)
    a3 = getAngle(p3)

    a2 -= a1
    if a2 < 0.0:
        a2 += 360.0
    a3 -= a1
    if a3 < 0.0:
        a3 += 360.0

    if a3 > a2 and a2 > 0.0:
        return False

    if a3 < a2 and a2 < 360.0:
        return True

    FreeCAD.Console.PrintError(
        f"ERROR _isArcClockwise() a1: {round(a1, 2)},  a2: {round(a2, 2)},  a3: {round(a3, 2)}\n"
    )

    return None


def _generatePathGeometry():
    """_generatePathGeometry()... Control function that generates path geometry wire sets."""
    _debugMsg("_generatePathGeometry()")
    global _rawPathGeometry

    _rawGeoList = _Circle()

    # Create compound object to bind all geometry
    geomShape = Part.makeCompound(_rawGeoList)

    _addDebugShape(geomShape, "rawPathGeomShape")  # Debugging

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

    _addDebugShape(_rawPathGeometry, "rawPathGeometry")  # Debugging

    _linkedPathGeom = _Link_Regular()

    return _linkedPathGeom


# Gcode production method
def _buildStartPath(toolController):
    """_buildStartPath() ... Convert Offset pattern wires to paths."""
    _debugMsg("_buildStartPath()")

    _vertFeed = toolController.VertFeed.Value
    _vertRapid = toolController.VertRapid.Value
    _horizFeed = toolController.HorizFeed.Value
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


# Support functions
def _flipLine(edge):
    """_flipLine(edge)
    Flips given edge around so the new Vertexes[0] was the old Vertexes[-1] and vice versa, without changing the shape.
    Currently only lines, line segments, circles and arcs are supported."""

    if not edge.Vertexes:
        return Part.Edge(
            Part.Line(
                edge.valueAt(edge.LastParameter), edge.valueAt(edge.FirstParameter)
            )
        )

    return Part.Edge(Part.LineSegment(edge.Vertexes[-1].Point, edge.Vertexes[0].Point))


def _flipLineSegment(edge):
    """_flipLineSegment(edge)
    Flips given edge around so the new Vertexes[0] was the old Vertexes[-1] and vice versa, without changing the shape.
    Currently only lines, line segments, circles and arcs are supported."""

    return Part.Edge(Part.LineSegment(edge.Vertexes[-1].Point, edge.Vertexes[0].Point))


def _flipCircle(edge):
    """_flipCircle(edge)
    Flips given edge around so the new Vertexes[0] was the old Vertexes[-1] and vice versa, without changing the shape.
    Currently only lines, line segments, circles and arcs are supported."""

    # Create an inverted circle
    circle = Part.Circle(edge.Curve.Center, -edge.Curve.Axis, edge.Curve.Radius)
    # Rotate the circle appropriately so it starts at edge.valueAt(edge.LastParameter)
    circle.rotate(
        FreeCAD.Placement(
            circle.Center,
            circle.Axis,
            180 - math.degrees(edge.LastParameter + edge.Curve.AngleXU),
        )
    )
    # Now the edge always starts at 0 and LastParameter is the value range
    arc = Part.Edge(circle, 0, edge.LastParameter - edge.FirstParameter)
    return arc


def _flipBSplineBezier(edge):
    """_flipBSplineBezier(edge)
    Flips given edge around so the new Vertexes[0] was the old Vertexes[-1] and vice versa, without changing the shape.
    Currently only lines, line segments, circles and arcs are supported."""
    if type(edge.Curve) == Part.BSplineCurve:
        spline = edge.Curve
    else:
        spline = edge.Curve.toBSpline()

    mults = spline.getMultiplicities()
    weights = spline.getWeights()
    knots = spline.getKnots()
    poles = spline.getPoles()
    perio = spline.isPeriodic()
    ratio = spline.isRational()
    degree = spline.Degree

    ma = max(knots)
    mi = min(knots)
    knots = [ma + mi - k for k in knots]

    mults.reverse()
    weights.reverse()
    poles.reverse()
    knots.reverse()

    flipped = Part.BSplineCurve()
    flipped.buildFromPolesMultsKnots(poles, mults, knots, perio, degree, weights, ratio)

    return Part.Edge(flipped)


def _flipEllipse(edge, deflection=0.001):
    """_flipEllipse(edge)
    Flips given edge around so the new Vertexes[0] was the old Vertexes[-1] and vice versa, without changing the shape.
    Currently only lines, line segments, circles and arcs are supported."""

    edges = []
    points = edge.discretize(Deflection=deflection)
    prev = points[0]
    for i in range(1, len(points)):
        now = points[i]
        edges.append(_flipLine(Part.makeLine(prev, now)))
        prev = now
    return edges


def flipWire(wire, deflection=0.001):
    """Flip the entire wire and all its edges so it is being processed the other way around."""
    edges = []
    for e in wire.Edges:
        if Part.Line == type(e.Curve):
            edges.append(_flipLine(e))
        elif Part.LineSegment == type(e.Curve):
            edges.append(_flipLineSegment(e))
        elif Part.Circle == type(e.Curve):
            edges.append(_flipCircle(e))
        elif type(e.Curve) in [Part.BSplineCurve, Part.BezierCurve]:
            edges.append(_flipBSplineBezier(e))
        elif type(e.Curve) == Part.OffsetCurve:
            edges.append(e.reversed())
        elif type(e.Curve) == Part.Ellipse:
            edges.extend(_flipEllipse(e, deflection))
        else:
            PathLog.warning("%s not supported for flipping" % type(e.Curve))
            edges.append(None)

    edges.reverse()
    PathLog.debug(edges)
    return Part.Wire(edges)


# Public functions
def generatePathGeometry(
    targetFace,
    toolRadius,
    stepOver=50.0,
    patternCenterAt="CenterOfBoundBox",
    patternCenterCustom=FreeCAD.Vector(0.0, 0.0, 0.0),
    cutPatternAngle=0.0,
    cutPatternReversed=False,
    cutDirection="Clockwise",
    minTravel=False,
    keepToolDown=False,
    jobTolerance=0.001,
):
    """generatePathGeometry(targetFace,
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
    _debugMsg("Generator_Circle.generatePathGeometry()")
    _debugMsg(
        f"(step over {stepOver}\n pattern center at {patternCenterAt}\n pattern center custom {patternCenterCustom}\n cut pattern angle {cutPatternAngle}\n cutPatternReversed {cutPatternReversed}\n cutDirection {cutDirection}\n minTravel {minTravel}\n keepToolDown {keepToolDown}\n jobTolerance {jobTolerance})"
    )

    if hasattr(targetFace, "Area") and PathGeom.isRoughly(targetFace.Area, 0.0):
        _debugMsg("Generator_Circle: No area in working shape.")
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
    global _useStaticCenter

    _useStaticCenter = True  # Set True to use static center for all faces created by offsets and step downs.  Set False for dynamic centers based on PatternCenterAt
    _isCenterSet = False

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
    _cutOut = _toolRadius * 2.0 * (_stepOver / 100.0)

    _targetFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - _targetFace.BoundBox.ZMin))

    pathGeometry = []

    #  Apply simple radius shrinking offset for clearing pattern generation.
    ofstVal = -1.0 * (_toolRadius - (_jobTolerance / 10.0))
    offsetFace = PathUtils.getOffsetArea(_targetFace, ofstVal)
    if not offsetFace:
        _debugMsg("getOffsetArea() failed")
    elif len(offsetFace.Faces) == 0:
        _debugMsg("No offset faces to process for path geometry.")
    else:
        for fc in offsetFace.Faces:
            fc.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - fc.BoundBox.ZMin))

            useFaces = fc
            if useFaces.Faces:
                for f in useFaces.Faces:
                    f.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - f.BoundBox.ZMin))
                    _face = f
                    _prepareAttributes()
                    pathGeom = _generatePathGeometry()
                    pathGeometry.extend(pathGeom)
            else:
                _debugMsg("No offset faces after cut with base shape.")

    return pathGeometry


def geometryToGcode(pathGeometry, toolController, retractHeight, finalDepth=None):
    """geometryToGcode(pathGeometry) Return line geometry converted to Gcode"""
    _debugMsg("geometryToGcode()")
    global _retractHeight
    global _finalDepth
    global _toolController

    # Argument validation
    if not type(retractHeight) is float:
        raise ValueError("Retract height must be a float")

    if not type(finalDepth) is float and finalDepth is not None:
        raise ValueError("Final depth must be a float")

    if finalDepth is not None and finalDepth > retractHeight:
        raise ValueError("Retract height must be greater than or equal to final depth\n")

    _toolController = toolController
    _retractHeight = retractHeight
    _finalDepth = finalDepth

    commandList = _buildLinePaths(pathGeometry, toolController)
    if len(commandList) > 0:
        commands = _buildStartPath(toolController)
        commands.extend(commandList)
        return commands
    else:
        _debugMsg("No commands in commandList")
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
