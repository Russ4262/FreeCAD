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
import PathScripts.PathLog as PathLog
import PathScripts.PathGeom as PathGeom
import Part
import math

from PySide import QtCore


__title__ = "Path REST Face Macro"
__author__ = "russ4262 (Russell Johnson"
__url__ = "https://www.freecadweb.org"
__doc__ = "Path macro to create a REST face based upon path geometry provided."


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())

IS_MACRO = False


# REST milling functions
def getPerp(start, end, dist):
    toEnd = end.sub(start)
    perp = FreeCAD.Vector(-1 * toEnd.y, toEnd.x, 0.0)
    if perp.x == 0 and perp.y == 0:
        return perp
    perp.normalize()
    perp.multiply(dist)
    return perp


def makeLineFace(edge, toolRadius):
    """makeLineFace(edge, toolRadius) ..."""

    start = edge.Vertexes[0].Point
    end = edge.Vertexes[1].Point

    # Make first cylinder
    ce1 = Part.Wire(Part.makeCircle(toolRadius, start).Edges)
    cylinder1 = Part.Face(ce1)
    cylinder1.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - cylinder1.BoundBox.ZMin))

    # Make second cylinder
    ce2 = Part.Wire(Part.makeCircle(toolRadius, end).Edges)
    cylinder2 = Part.Face(ce2)
    cylinder2.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - cylinder2.BoundBox.ZMin))

    # Make extruded rectangle to connect cylinders
    perp = getPerp(start, end, toolRadius)
    v1 = start.add(perp)
    v2 = start.sub(perp)
    v3 = end.sub(perp)
    v4 = end.add(perp)
    e1 = Part.makeLine(v1, v2)
    e2 = Part.makeLine(v2, v3)
    e3 = Part.makeLine(v3, v4)
    e4 = Part.makeLine(v4, v1)
    edges = Part.__sortEdges__([e1, e2, e3, e4])
    rectFace = Part.Face(Part.Wire(edges))
    rectFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - rectFace.BoundBox.ZMin))

    # Fuse two cylinders and box together
    part1 = cylinder1.fuse(rectFace)
    pathTravel = part1.fuse(cylinder2)

    return pathTravel


def makeArcFace(edge, toolRadius):
    """makeLineFace(start, end, toolRadius) ..."""

    if len(edge.Vertexes) == 1:
        newRad = edge.Curve.Radius + toolRadius
        e1 = Part.makeCircle(
            newRad,
            edge.Curve.Center,
            FreeCAD.Vector(0.0, 0.0, 1.0),
        )
        outWire = Part.Wire([e1])
        outWire.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - outWire.BoundBox.ZMin))

        newRad = edge.Curve.Radius - toolRadius
        if newRad > toolRadius:
            e2 = Part.makeCircle(
                newRad,
                edge.Curve.Center,
                FreeCAD.Vector(0.0, 0.0, 1.0),
            )
            inWire = Part.Wire([e2])
            inWire.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - inWire.BoundBox.ZMin))
            inFace = Part.Face(inWire)
            outFace = Part.Face(outWire)
            arcFace = outFace.cut(inFace)
        else:
            arcFace = Part.Face(outWire)

        return arcFace

    start = edge.Vertexes[0].Point
    end = edge.Vertexes[1].Point

    # Make first cylinder
    ce1 = Part.Wire(Part.makeCircle(toolRadius, start).Edges)
    cylinder1 = Part.Face(ce1)
    cylinder1.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - cylinder1.BoundBox.ZMin))

    # Make second cylinder
    ce2 = Part.Wire(Part.makeCircle(toolRadius, end).Edges)
    cylinder2 = Part.Face(ce2)
    cylinder2.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - cylinder2.BoundBox.ZMin))

    edgeRad = edge.Curve.Radius
    arcOuter = scaleArc(edge, toolRadius)

    if edgeRad - toolRadius < 0.0:
        # only three segments
        seg1 = Part.makeLine(edge.Curve.Center, arcOuter.Vertexes[0].Point)
        seg3 = Part.makeLine(arcOuter.Vertexes[1].Point, edge.Curve.Center)
        wire = Part.Wire([seg1, arcOuter, seg3])
        arcFace = Part.Face(wire)
    else:
        arcInner = scaleArc(edge, -1.0 * toolRadius)
        seg1 = Part.makeLine(arcInner.Vertexes[1].Point, arcOuter.Vertexes[1].Point)
        seg3 = Part.makeLine(arcOuter.Vertexes[0].Point, arcInner.Vertexes[0].Point)
        wire = Part.Wire([seg1, arcOuter, seg3, arcInner])
        arcFace = Part.Face(wire)
    arcFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - arcFace.BoundBox.ZMin))
    # Part.show(arcFace)

    # Fuse two cylinders and box together
    part1 = cylinder1.fuse(arcFace)
    pathTravel = part1.fuse(cylinder2).removeSplitter()
    # Part.show(pathTravel)

    return pathTravel


def scaleArc(edge, radDiff):
    curve = edge.Curve
    startVect = edge.Vertexes[0].Point.sub(curve.Center)
    startAngle = math.degrees(math.atan2(startVect.y, startVect.x))
    endVect = edge.Vertexes[1].Point.sub(curve.Center)
    endAngle = math.degrees(math.atan2(endVect.y, endVect.x))
    return Part.makeCircle(
        curve.Radius + radDiff,
        curve.Center,
        FreeCAD.Vector(0.0, 0.0, 1.0),
        startAngle,
        endAngle,
    )


def cleanFace(face):
    # Part.show(face, "face")
    enclosureFace = PathGeom.makeBoundBoxFace(face.BoundBox, 5.0)
    negative = enclosureFace.cut(face)
    # Part.show(negative, "faceNegative")
    enclosureFace2 = PathGeom.makeBoundBoxFace(face.BoundBox, 4.0)
    clean = enclosureFace2.cut(negative)
    # Part.show(clean, "faceClean")
    return clean


def wiresToPathFace_orig(wires, toolDiameter):
    td = round(toolDiameter * 0.9995, 6)
    toolRadius = td / 2.0
    # print("wiresToPathFace() toolRadius: {}".format(toolRadius))
    allFaces = []
    for wire in wires:
        for e in wire.Edges:
            if e.Curve.TypeId.endswith("Line"):
                allFaces.append(makeLineFace(e, toolRadius))
            elif e.Curve.TypeId.endswith("Circle"):
                allFaces.append(makeArcFace(e, toolRadius))
            else:
                print(
                    "  ERROR ... Cannot make face from edge type: {}".format(
                        e.Curve.TypeId
                    )
                )

    if len(allFaces) == 0:
        return None

    if len(allFaces) == 1:
        return allFaces[0]

    seed = allFaces[0]
    for f in allFaces[1:]:
        fusion = seed.fuse(f)
        seed = fusion

    return cleanFace(seed)


def wiresToPathFace(wires, toolDiameter):
    """wiresToPathFace(wires, toolDiameter)...
    All `wires` should be at same `Z` height"""
    td = round(toolDiameter * 0.9996, 6)
    toolRadius = td / 2.0
    # print("wiresToPathFace() toolRadius: {}".format(toolRadius))
    allFaces = []
    for wire in wires:
        for e in wire.Edges:
            if e.Curve.TypeId.endswith("Line"):
                allFaces.append(makeLineFace(e, toolRadius))
            elif e.Curve.TypeId.endswith("Circle"):
                allFaces.append(makeArcFace(e, toolRadius))
            else:
                print(f"  ERROR ... Cannot make face from edge type: {e.Curve.TypeId}")

    if len(allFaces) == 0:
        return None

    if len(allFaces) == 1:
        return allFaces[0]

    comp = Part.makeCompound(allFaces)
    enclosureFace = PathGeom.makeBoundBoxFace(comp.BoundBox, 5.0)
    for f in allFaces:
        cut = enclosureFace.cut(f)
        enclosureFace = cut.copy()

    enclosureFace2 = PathGeom.makeBoundBoxFace(comp.BoundBox, 4.0)

    return enclosureFace2.cut(enclosureFace)


if IS_MACRO:
    print("\n\n\n\n")
    doc = FreeCAD.ActiveDocument
    group = doc.addObject("App::DocumentObjectGroup", "Group")
    obj = doc.Solid002
    start = 60.0
    final = 0.0
    step = -10.0  # Must be negative to step down
    depths = [start]
    while start > final:
        start += step
        if start < final:
            start = final
        depths.append(start)
    # depths.append(final)
    print(f"depths: {depths}")
