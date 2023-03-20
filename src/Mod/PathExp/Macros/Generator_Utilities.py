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
import Path.Geom as PathGeom
import PathScripts.PathUtils as PathUtils
import Part
import math

if FreeCAD.GuiUp:
    import FreeCADGui
    import Gui_Input


__title__ = "Path Generator Utilities"
__author__ = "russ4262 (Russell Johnson)"
__url__ = ""
__doc__ = "Utilities for clearing path generation."

if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())

isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
showDebugShapes = False


IS_MACRO = False
MODULE_NAME = "Generator_Utilities"
OPTIMIZE = False
PATTERNS = [
    ("Line", "Line"),
    ("Adaptive", "Adaptive"),
    ("Spiral", "Spiral"),
    ("CircleZigZag", "CircleZigZag"),
    ("Circle", "Circle"),
    ("Profile", "Profile"),
    ("ZigZag", "ZigZag"),
    ("Offset", "Offset"),
]
PATTERNCENTERS = [
    ("CenterOfBoundBox", "CenterOfBoundBox"),
    ("CenterOfMass", "CenterOfMass"),
    ("XminYmin", "XminYmin"),
    ("Custom", "Custom"),
]
PATHTYPES = [
    ("3D", "3D"),
    ("2D", "2D"),
]
LINEARDEFLECTION = FreeCAD.Units.Quantity("0.0001 mm")
CUTDIRECTIONS = [
    ("Clockwise", "Clockwise"),
    ("CounterClockwise", "CounterClockwise"),
]


def _debugMsg(moduleName, msg, isError=False):
    """_debugMsg(moduleName, msg, isError=False)
    If `_isDebug` flag is True, the provided message is printed in the Report View.
    If not, then the message is assigned a debug status.
    """
    if isError:
        FreeCAD.Console.PrintError(f"{moduleName}: {msg}\n")
        return

    if isDebug:
        # PathLog.info(msg)
        FreeCAD.Console.PrintMessage(f"{moduleName}: {msg}\n")
    else:
        PathLog.debug(f"{moduleName}: {msg}\n")


def _addDebugShape(shape, name="debug"):
    if showDebugShapes:
        do = FreeCAD.ActiveDocument.addObject("Part::Feature", "debug_" + name)
        do.Shape = shape
        do.purgeTouched()


def _showGeom(wireList, label=""):
    g = FreeCAD.ActiveDocument.addObject("App::DocumentObjectGroup", "Group")
    totalCnt = 0
    for w in wireList:
        p0 = w.Vertexes[0].Point
        # line = Part.makeLine(p0, FreeCAD.Vector(p0.x, p0.y, p0.z + 5.0))
        # Part.show(line, "StartLine")
        eCnt = len(w.Edges)
        totalCnt += eCnt
        # print(f"_showGeom() Wire edge count: {eCnt}")
        w = Part.show(w, "GeomWire")
        g.addObject(w)
    if len(label) > 0:
        g.Label = f"Group_{label}"

    print(f"_showGeom() {len(wireList)} wires have {totalCnt} total edges")


def _showGeomList(wireList):
    for wires in wireList:
        for w in wires:
            p0 = w.Vertexes[0].Point
            line = Part.makeLine(p0, FreeCAD.Vector(p0.x, p0.y, p0.z + 5.0))
            Part.show(line, "StartLine")


def _showGeomOpen(wireList):
    g = FreeCAD.ActiveDocument.addObject("App::DocumentObjectGroup", "Group")
    totalCnt = 0
    for w in wireList:
        if not w.isClosed():
            p0 = w.Vertexes[0].Point
            # line = Part.makeLine(p0, FreeCAD.Vector(p0.x, p0.y, p0.z + 5.0))
            # Part.show(line, "StartLine")
            eCnt = len(w.Edges)
            totalCnt += eCnt
            # print(f"_showGeom() Wire edge count: {eCnt}")
            w = Part.show(w, "GeomWire")
            g.addObject(w)

    print(f"_showGeom() {len(wireList)} wires have {totalCnt} total edges")


# Support methods
def _prepareAttributes(
    face,
    toolRadius,
    cutOut,
    isCenterSet,
    useStaticCenter,
    patternCenterAt,
    patternCenterCustom,
):
    """_prepareAttributes()... Prepare instance attribute values for path generation."""
    _debugMsg(MODULE_NAME, "_prepareAttributes()")
    if isCenterSet:
        if useStaticCenter:
            PathLog.debug(
                "_prepareAttributes() Both `isCenterSet` and `useStaticCenter` are True."
            )
            return None

    divisor = 2.0
    # Compute weighted center of mass of all faces combined
    if patternCenterAt == "CenterOfMass":
        comF = face.CenterOfMass
        centerOfMass = FreeCAD.Vector(comF.x, comF.y, 0.0)
        centerOfPattern = FreeCAD.Vector(centerOfMass.x, centerOfMass.y, 0.0)

    elif patternCenterAt == "CenterOfBoundBox":
        cent = face.BoundBox.Center
        centerOfPattern = FreeCAD.Vector(cent.x, cent.y, 0.0)

    elif patternCenterAt == "Custom":
        divisor = 1.0
        centerOfPattern = FreeCAD.Vector(
            patternCenterCustom.x, patternCenterCustom.y, 0.0
        )
    elif patternCenterAt == "XminYmin":
        centerOfPattern = FreeCAD.Vector(face.BoundBox.XMin, face.BoundBox.YMin, 0.0)
    else:
        FreeCAD.Console.PrintError(
            f"_prepareAttributes() `patternAtCenter not recognized: {patternCenterAt}"
        )
        return None

    # calculate line length
    # Line length to span boundbox diag with 2x cutter diameter extra on each end
    deltaC = face.BoundBox.DiagonalLength
    lineLen = deltaC + (4.0 * toolRadius)
    if patternCenterAt == "Custom":
        distToCent = face.BoundBox.Center.sub(centerOfPattern).Length
        lineLen += distToCent

    halfDiag = math.ceil(lineLen / 2.0)

    # Calculate number of passes
    # Number of lines(passes) required to cover boundbox diagonal
    cutPasses = math.ceil(lineLen / cutOut) + 1
    halfPasses = math.ceil(cutPasses / divisor)

    return (centerOfPattern, halfDiag, cutPasses, halfPasses)


def getAngle(pnt, centerOfPattern):
    p = pnt.sub(centerOfPattern)
    angle = math.degrees(math.atan2(p.y, p.x))
    if angle < 0.0:
        angle += 360.0
    return angle


def _isOrientedTheSame(directionVector, wire):
    v1 = wire.Edges[0].Vertexes[0].Point
    v2 = wire.Edges[-1].Vertexes[-1].Point
    p1 = FreeCAD.Vector(v1.x, v1.y, 0.0)
    p2 = FreeCAD.Vector(v2.x, v2.y, 0.0)
    drctn = p2.sub(p1).normalize()
    if PathGeom.isRoughly(directionVector.x, drctn.x) and PathGeom.isRoughly(
        directionVector.y, drctn.y
    ):
        return True
    return False


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


def _isArcClockwise(wire, centerOfPattern):
    """_isArcClockwise(wire) Return True if arc is oriented clockwise.
    Incomming wire is assumed to be an arc shape (single arc edge, or discretized version)."""
    if wire.isClosed():
        # This method is not reliable for open wires
        p1 = wire.Edges[0].valueAt(wire.Edges[0].FirstParameter)
        p2 = _wireQuartilePoint(wire)

        a1 = getAngle(p1, centerOfPattern)
        if PathGeom.isRoughly(a1, 360.0):
            a1 = 0.0
        a2 = getAngle(p2, centerOfPattern) - a1
        if a2 < 0.0:
            a2 += 360.0

        if PathGeom.isRoughly(a2, 90.0):
            return True

        return False

    p1 = wire.Edges[0].valueAt(wire.Edges[0].FirstParameter)
    p2 = _wireQuartilePoint(wire)  # _wireMidpoint(wire)
    p3 = wire.Edges[-1].valueAt(wire.Edges[-1].LastParameter)

    a1 = getAngle(p1, centerOfPattern)
    if PathGeom.isRoughly(a1, 360.0):
        a1 = 0.0
    a2 = getAngle(p2, centerOfPattern)
    a3 = getAngle(p3, centerOfPattern)

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


def _isCollinear(p1, p2, p3):
    deltaY = p2.y - p1.y
    deltaX = p2.x - p1.x

    if PathGeom.isRoughly(deltaX, 0.0):
        # Vertical line p1 -> p2
        if PathGeom.isRoughly(p3.x, (p2.x + p1.x) / 2.0):
            return True
    else:
        m = deltaY / deltaX
        b = p1.y - m * p1.x
        if PathGeom.isRoughly(p3.y, m * p3.x + b):
            return True
    return False


def isMoveInRegion(toolDiameter, workingRegion, p1, p2, maxWidth=0.0002):
    """Make simple circle with diameter of tool, at start and end points, then fuse with rectangle.
    Check for collision with working region.
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
        cmn = workingRegion.common(pathTravel)
        width = abs(pathTravel.Area - cmn.Area) / vLen
        if width < maxWidth:
            return True
    except Exception:
        PathLog.debug("Failed to complete path collision check.")

    return False


def getToolShape(toolController):
    """getToolShape(toolController) Return tool shape with shank removed."""
    full = toolController.Tool.Shape.copy()
    vertEdges = [
        e
        for e in full.Edges
        if len(e.Vertexes) == 2
        and PathGeom.isRoughly(e.Vertexes[0].X, e.Vertexes[1].X)
        and PathGeom.isRoughly(e.Vertexes[0].Y, e.Vertexes[1].Y)
    ]
    vertEdges.sort(key=lambda e: e.BoundBox.ZMax)
    topVertEdge = vertEdges.pop()
    top = full.BoundBox.ZMax + 2.0
    face = PathGeom.makeBoundBoxFace(full.BoundBox, 5.0, top)
    dist = -1.0 * (top - topVertEdge.BoundBox.ZMin)
    faceExt = face.extrude(FreeCAD.Vector(0.0, 0.0, dist))
    # Part.show(full, "Full")
    # Part.show(faceExt, "FaceExt")
    return full.cut(faceExt)


# Offset face function
def _offsetFaceRegion(face, offsetValue):
    #  Apply simple radius shrinking offset for clearing pattern generation.
    offsetFace = PathUtils.getOffsetArea(face, offsetValue)
    if not offsetFace:
        _debugMsg(MODULE_NAME, f"getOffsetArea() failed; ofstVal: {offsetValue}")
        return []
    elif len(offsetFace.Faces) == 0:
        _debugMsg(MODULE_NAME, "No offset faces to process for path geometry.")
        return []

    return [f.copy() for f in offsetFace.Faces]


######################################################
# Improved support functions for orienting and flipping wires and edges
def _flipLine(edge):
    """_flipLine(edge)
    Flips given edge around so the new Vertexes[0] was the old Vertexes[-1] and vice versa, without changing the shape."""

    if not edge.Vertexes:
        return Part.Edge(
            Part.Line(
                edge.valueAt(edge.LastParameter), edge.valueAt(edge.FirstParameter)
            )
        )

    return Part.Edge(Part.LineSegment(edge.Vertexes[-1].Point, edge.Vertexes[0].Point))


def _flipLineSegment(edge):
    """_flipLineSegment(edge)
    Flips given edge around so the new Vertexes[0] was the old Vertexes[-1] and vice versa, without changing the shape."""

    return Part.Edge(Part.LineSegment(edge.Vertexes[-1].Point, edge.Vertexes[0].Point))


def _flipCircle(edge):
    """_flipCircle(edge)
    Flips given edge around so the new Vertexes[0] was the old Vertexes[-1] and vice versa, without changing the shape."""

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
    Flips given edge around so the new Vertexes[0] was the old Vertexes[-1] and vice versa, without changing the shape."""
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
    knotsRev = [ma + mi - k for k in knots]

    mults.reverse()
    weights.reverse()
    poles.reverse()
    knotsRev.reverse()

    flipped = Part.BSplineCurve()
    flipped.buildFromPolesMultsKnots(
        poles, mults, knotsRev, perio, degree, weights, ratio
    )

    firstParam = 0.0
    lastParam = 1.0
    if not PathGeom.isRoughly(edge.LastParameter, 1.0):
        firstParam = 1.0 - edge.LastParameter
    if not PathGeom.isRoughly(edge.FirstParameter, 0.0):
        lastParam = 1.0 - edge.FirstParameter

    return Part.Edge(flipped, firstParam, lastParam)


def _flipEllipse(edge, deflection=0.001):
    """_flipEllipse(edge)
    Flips given edge around so the new Vertexes[0] was the old Vertexes[-1] and vice versa, without changing the shape."""

    edges = []
    points = edge.discretize(Deflection=deflection)
    prev = points[0]
    for i in range(1, len(points)):
        now = points[i]
        edges.append(_flipLine(Part.makeLine(prev, now)))
        prev = now
    return edges


def _flipEdge(e, deflection=0.001):
    if Part.Line == type(e.Curve):
        return _flipLine(e)
    elif Part.LineSegment == type(e.Curve):
        return _flipLineSegment(e)
    elif Part.Circle == type(e.Curve):
        return _flipCircle(e)
    elif type(e.Curve) in [Part.BSplineCurve, Part.BezierCurve]:
        return _flipBSplineBezier(e)
    elif type(e.Curve) == Part.OffsetCurve:
        return e.reversed()
    elif type(e.Curve) == Part.Ellipse:
        return _flipEllipse(e, deflection)

    PathLog.warning("%s not supported for flipping" % type(e.Curve))
    return None


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
    # return Part.Wire(edges)
    return Part.Wire(Part.__sortEdges__(edges))


def _orientEdges(inEdges):
    """_orientEdges(inEdges) ... internal worker function to orient edges so the last vertex of one edge connects to the first vertex of the next edge.
    Assumes the edges are in an order so they can be connected."""
    PathLog.track()
    # orient all edges of the wire so each edge's last value connects to the next edge's first value
    e0 = inEdges[0]
    # well, even the very first edge could be misoriented, so let's try and connect it to the second
    if 1 < len(inEdges):
        last = e0.valueAt(e0.LastParameter)
        e1 = inEdges[1]
        if not PathGeom.pointsCoincide(
            last, e1.valueAt(e1.FirstParameter)
        ) and not PathGeom.pointsCoincide(last, e1.valueAt(e1.LastParameter)):
            # debugEdge("#  _orientEdges - flip first", e0)
            # e0 = PathGeom.flipEdge(e0)
            e0 = _flipEdge(e0)

    if isinstance(e0, list):
        edges = e0
        e0 = edges[0]
    else:
        edges = [e0]

    last = e0.valueAt(e0.LastParameter)
    for e in inEdges[1:]:
        edge = (
            e
            if PathGeom.pointsCoincide(last, e.valueAt(e.FirstParameter))
            # else PathGeom.flipEdge(e)
            else _flipEdge(e)
        )
        if isinstance(edge, list):
            edges.extend(edge)
            last = edge[-1].valueAt(edge[-1].LastParameter)
        else:
            edges.append(edge)
            last = edge.valueAt(edge.LastParameter)
    return edges


def _isWireClockwise(w):
    """_isWireClockwise(w) ... return True if wire is oriented clockwise.
    Assumes the edges of w are already properly oriented - for generic access use isWireClockwise(w)."""
    # handle wires consisting of a single circle or 2 edges where one is an arc.
    # in both cases, because the edges are expected to be oriented correctly, the orientation can be
    # determined by looking at (one of) the circle curves.
    if 2 >= len(w.Edges) and Part.Circle == type(w.Edges[0].Curve):
        return 0 > w.Edges[0].Curve.Axis.z
    if 2 == len(w.Edges) and Part.Circle == type(w.Edges[1].Curve):
        return 0 > w.Edges[1].Curve.Axis.z

    # for all other wires we presume they are polygonial and refer to Gauss
    # https://en.wikipedia.org/wiki/Shoelace_formula
    area = 0
    for e in w.Edges:
        v0 = e.valueAt(e.FirstParameter)
        v1 = e.valueAt(e.LastParameter)
        area = area + (v0.x * v1.y - v1.x * v0.y)
    PathLog.track(area)
    return area < 0


def isWireClockwise(w):
    """isWireClockwise(w) ... returns True if the wire winds clockwise."""
    return _isWireClockwise(Part.Wire(_orientEdges(w.Edges)))


def orientWire(w, forward=True):
    """orientWire(w, forward=True) ... orients given wire in a specific direction.
    If forward = True (the default) the wire is oriented clockwise, looking down the negative Z axis.
    If forward = False the wire is oriented counter clockwise.
    If forward = None the orientation is determined by the order in which the edges appear in the wire."""
    PathLog.debug("orienting forward: {}: {} edges".format(forward, len(w.Edges)))
    wire = Part.Wire(_orientEdges(w.Edges))
    if forward is not None:
        if forward != _isWireClockwise(wire):
            PathLog.track("orientWire - needs flipping")
            # return PathGeom.flipWire(wire)
            return flipWire(wire)
        PathLog.track("orientWire - ok")
    return wire


def _edgeValueAtLength(edge, length):
    edgeLen = edge.Length
    # if PathGeom.isRoughly(edgeLen, 0.0):
    if edgeLen == 0.0:
        pnt = edge.Vertexes[0].Point
        return FreeCAD.Vector(pnt.x, pnt.y, pnt.z)

    if hasattr(edge, "Curve"):
        typeId = edge.Curve.TypeId
    elif hasattr(edge, "TypeId"):
        typeId = edge.TypeId

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
    elif typeId == "Part::GeomParabola":
        return edge.valueAt(
            edge.FirstParameter
            + length / edgeLen * (edge.LastParameter - edge.FirstParameter)
        )
    elif typeId == "Part::GeomHyperbola":
        return edge.valueAt(
            edge.FirstParameter
            + length / edgeLen * (edge.LastParameter - edge.FirstParameter)
        )
    else:
        print(f"_edgeValueAtLength() edge.Curve.TypeId, {typeId}, is not available.")
        return None


######################################################

# Auxillary functions
def getFacesFromSelection(selections=[]):
    populateSelection(selections)

    faces = []
    wires = []
    edges = []
    selection = FreeCADGui.Selection.getSelectionEx()
    # process user selection
    for sel in selection:
        # print(f"Object.Name: {sel.Object.Name}")
        for feat in sel.SubElementNames:
            # print(f"Processing: {sel.Object.Name}::{feat}")
            if feat.startswith("Face"):
                # face = sel.Object.Shape.getElement(feat)
                faces.append(sel.Object.Shape.getElement(feat))
            elif feat.startswith("Edge"):
                # face = sel.Object.Shape.getElement(feat)
                edges.append(sel.Object.Shape.getElement(feat))
    if len(edges) > 0:
        wires = [Part.Wire(grp) for grp in Part.sortEdges(edges)]
    return faces, wires


def populateSelection(selections=[]):
    if len(selections) == 0:
        return
    for objName, features in selections:
        if hasattr(FreeCAD.ActiveDocument, objName):
            obj = FreeCAD.ActiveDocument.getObject(objName)
            for f in features:
                FreeCADGui.Selection.addSelection(obj, f)
        else:
            print(f"No '{objName}' object in active document.")


def combineFacesToRegion(faces, saveOldHoles=True, saveNewHoles=True):
    # combine faces into horizontal regions
    import Macro_CombineRegions

    region = Macro_CombineRegions.combineRegions(
        faces, saveExistingHoles=saveOldHoles, saveMergedHoles=saveNewHoles
    )
    # Part.show(region, "Region")

    # fuse faces together for projection of path geometry
    faceShape = faces[0].copy()
    if len(faces) > 1:
        for f in faces[1:]:
            fused = faceShape.fuse(f.copy())
            faceShape = fused
    # faceShape.tessellate(0.05)

    return region, faceShape


def combineSelectedFaces(saveOldHoles=True, saveNewHoles=True):
    selectedFaces, __ = getFacesFromSelection()
    if len(selectedFaces) == 0:
        return None

    # combine faces into horizontal regions
    region, faceShape = combineFacesToRegion(
        selectedFaces, saveOldHoles=True, saveNewHoles=True
    )

    return region, faceShape


def getJob():
    jobs = [obj for obj in FreeCAD.ActiveDocument.Objects if obj.Name.startswith("Job")]
    if len(jobs) == 1:
        return jobs[0]
    # Prompt user to select a Job object
    jobLabels = [j.Label for j in jobs]
    guiInput = Gui_Input.GuiInput()
    guiInput.setWindowTitle("Job Selection")
    guiInput.addComboBox("Job", jobLabels)
    jobLabel = guiInput.execute()
    jIdx = jobLabels.index(jobLabel[0])
    return jobs[jIdx]


def addCustomOpToJob(job, tc):
    import Path.Op.Gui.Custom as PathCustomGui

    op = PathCustomGui.PathCustom.Create("Custom")
    op.ToolController = tc
    op.ViewObject.Proxy = PathCustomGui.PathOpGui.ViewProvider(
        op.ViewObject, PathCustomGui.Command.res
    )
    op.ViewObject.Proxy.deleteOnReject = False
    FreeCAD.ActiveDocument.recompute()
    return op


def getToolControllerFromJob(job):
    import Tool_Controller

    # Set tool controller from Job object
    tc, __ = Tool_Controller.getToolController(job)
    return tc


def getJobAndToolController():
    # Get Job, Custom operation, and Tool Controller
    job = getJob()
    if job is None:
        print("No Job found")
        return None, None

    return job, getToolControllerFromJob(job)


# print("Imported Generator_Utilities")
