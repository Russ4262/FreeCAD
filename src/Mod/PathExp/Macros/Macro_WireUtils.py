# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2016 sliptonic <shopinthewoods@gmail.com>               *
# *   Copyright (c) 2018 sliptonic <shopinthewoods@gmail.com>               *
# *   Copyright (c) 2021 Schildkroet                                        *
# *   Copyright (c) 2022 Russell Johnson (russ4262) <russ4262@gmail.com>    *
# *                                                                         *
# *   This file is a supplement to the FreeCAD CAx development system.      *
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
import Part
import Path.Geom as PathGeom
import Path.Log as PathLog
import math

# Improved support functions for orienting and flipping wires and edges
# Work based on functions from Path.Op.Util and Path.Geom modules

# Support functions
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


def _flipOtherEdge(edge, deflection=0.001):
    """_flipOtherEdge(edge)
    Flips edge by creating a discretized wire first, then flipping the wire."""

    edges = []
    points = edge.discretize(Deflection=deflection)
    prev = points[0]
    for i in range(1, len(points)):
        now = points[i]
        edges.append(_flipLine(Part.makeLine(prev, now)))
        prev = now
    return edges


def _flipEdge(e, deflection=0.001):
    if type(e.Curve) == Part.Line:
        return _flipLine(e)
    elif type(e.Curve) == Part.LineSegment:
        return _flipLineSegment(e)
    elif type(e.Curve) == Part.Circle:
        return _flipCircle(e)
    elif type(e.Curve) in [Part.BSplineCurve, Part.BezierCurve]:
        return _flipBSplineBezier(e)
    elif type(e.Curve) == Part.OffsetCurve:
        return e.reversed()
    elif type(e.Curve) == Part.Ellipse:
        PathLog.warning("Discretizing elliptical edge before flipping")
        return _flipOtherEdge(e, deflection)

    PathLog.warning("%s not supported for flipping" % type(e.Curve))
    return None


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


# Public functions
def flipEdge(e, deflection=0.001):
    return _flipEdge(e, deflection)


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
            edges.extend(_flipOtherEdge(e, deflection))
        else:
            # PathLog.warning(f"{type(e.Curve)} not supported for flipping")
            # edges.append(None)
            PathLog.warning(f"{type(e.Curve)} will be discretized and flipped")
            edges.extend(_flipOtherEdge(e, deflection))

    edges.reverse()
    PathLog.debug(edges)
    # return Part.Wire(edges)
    return Part.Wire(Part.__sortEdges__(edges))


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


def isWireClockwise(w):
    """isWireClockwise(w) ... returns True if the wire winds clockwise."""
    return _isWireClockwise(Part.Wire(_orientEdges(w.Edges)))


def valueAtEdgeLength(edge, length):
    """valueAtEdgeLength(edge, length)
    Returns the point along the given edge at the given length."""

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
    elif typeId == "Part::GeomLine":
        return edge.valueAt(edge.FirstParameter + length)
    elif typeId in [
        "Part::GeomCircle",
        "Part::GeomEllipse",
        "Part::GeomParabola",
        "Part::GeomHyperbola",
    ]:
        return edge.valueAt(
            edge.FirstParameter
            + length / edgeLen * (edge.LastParameter - edge.FirstParameter)
        )
    else:
        PathLog.warning(
            f"valueAtEdgeLength() edge.Curve.TypeId, {typeId}, is not available."
        )
        return None
