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
import Path.Geom as PathGeom
import Part
import math

from PySide import QtCore


__title__ = "Path Strategy Slicing"
__author__ = "russ4262 (Russell Johnson"
__url__ = "https://www.freecadweb.org"
__doc__ = "Path slicing strategy for 3D shapes."


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


# Slicing functions
def getTopFace(solid):
    zMax = solid.BoundBox.ZMax
    for f in solid.Faces:
        if PathGeom.isRoughly(f.BoundBox.ZMin, zMax):
            return f
    return None


def getBottomFaces(shape):
    faces = []
    zMax = min([f.BoundBox.ZMax for f in shape.Faces])
    # print("{} faces in shape & ZMin: {}".format(len(shape.Faces), round(zMax, 6)))
    for f in shape.Faces:
        # print("f.BB.ZMax: {}".format(round(f.BoundBox.ZMax, 6)))
        if PathGeom.isRoughly(f.BoundBox.ZMax, zMax):
            faces.append(f)
    if faces:
        # print("bottom face(s) identified")
        return Part.makeCompound(faces)
    return None


def getSliceShape(shape, zmin, thickness):
    try:
        face = PathGeom.makeBoundBoxFace(shape.BoundBox, 5.0, zmin)
    except Exception as ee:
        PathLog.error(f"{ee}")
        return None
    return face.extrude(FreeCAD.Vector(0.0, 0.0, thickness))


def getSliceProfile(shape):
    envelope = PathUtils.getEnvelope(shape)
    # Part.show(envelope, "Envelope")
    topEnvFace = getTopFace(envelope)
    topEnvFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - topEnvFace.BoundBox.ZMin))
    return topEnvFace


def sliceShape(fullShape, depthParams, region=None, findCommon=True):
    slices = []
    depths = [d for d in depthParams]
    if len(depthParams) < 2:
        depths.insert(0, depthParams[0] + fullShape.BoundBox.ZLength + 2.0)
    lenDP = len(depths)

    # PathLog.info("depths: {}".format(depths))
    lastDep = depths[lenDP - 1]
    shapeMin = fullShape.BoundBox.ZMin
    if shapeMin > lastDep:
        depths.pop()
        depths.append(shapeMin)

    PathLog.debug(
        "sliceShape() final depth: {};  shape depth: {}".format(
            lastDep,
            shapeMin,
        )
    )
    PathLog.debug(f"sliceShape() depths: {depths}")

    if region:
        # prep region
        region.translate(
            FreeCAD.Vector(
                0.0, 0.0, fullShape.BoundBox.ZMin - 1.0 - region.BoundBox.ZMin
            )
        )
        regExt = region.extrude(
            FreeCAD.Vector(0.0, 0.0, fullShape.BoundBox.ZLength + 2.0)
        )
        shape = fullShape.common(regExt)
    else:
        shape = fullShape
    
    # shapeZMin = shape.BoundBox.ZMin
    # shapeZMax = shape.BoundBox.ZMax
    
    # Part.show(shape, "SlicingSourceShape")

    thickness = depths[0] - depths[1]
    for i in range(0, lenDP):
        d = depths[i]
        # PathLog.info("slicing at {} mm with thickness of {} mm".format(d, thickness))
        # print("Layer Depth: {}".format(round(d, 6)))

        sliceLayer = getSliceShape(shape, d, thickness)
        if sliceLayer is None:
            break
        # Part.show(sliceLayer, f"SliceLayer-{round(d,1)}")

        if findCommon:
            common = shape.common(sliceLayer)  # .removeSplitter()
        else:
            common = sliceLayer.cut(shape).removeSplitter()

        # common.translate(FreeCAD.Vector(0.0, 0.0, d - common.BoundBox.ZMin))
        # print("Common ZMin: {}".format(round(common.BoundBox.ZMin, 6)))
        lenSolids = len(common.Solids)

        # PathLog.debug(f"Common solids count is {lenSolids}")

        if lenSolids == 1:
            bottomFaces = getBottomFaces(common.Solids[0].copy())
            if bottomFaces:
                # Check if bottom of slice solid has multiple protruding faces
                if len(bottomFaces.Faces) == 1:
                    # Add bottom face of slice solid.
                    slices.append(bottomFaces.Faces[0])
                else:
                    for f in bottomFaces.Faces:
                        subSlices = sliceShape(
                            fullShape, depths[i:], f.copy(), findCommon
                        )
                        if subSlices:
                            slices.extend(subSlices)
                    break
            else:
                Part.show(common.Solids[0], "No bottom solid")
        elif lenSolids > 1:
            for s in common.Solids:
                topFace = getTopFace(s)
                if topFace:
                    subSlices = sliceShape(
                        fullShape, depths[i:], topFace.copy(), findCommon
                    )
                    if subSlices:
                        slices.extend(subSlices)
                else:
                    PathLog.error("sliceShape() NoneType topFace")
                    Part.show(s, "NoneType topFace")
            if findCommon:
                break  # uncomment for regular use.
        else:
            # break
            pass

        # update thickness
        if i > 0:
            thickness = depths[i - 1] - d
    # Efor

    return slices


def getClearingArea(avoid, profile):
    p = avoid.copy()
    a = profile.copy()
    p.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - avoid.BoundBox.ZMin))
    a.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - profile.BoundBox.ZMin))
    # determine clearing area
    clearingArea = a.cut(p)
    clearingArea.translate(FreeCAD.Vector(0.0, 0.0, avoid.BoundBox.ZMin))

    return clearingArea


def sliceSolid(solid, depths):
    slices = sliceShape(solid, depths, None, True)
    # slices.reverse()

    if not slices:
        return None

    # for s in slices:
    #    Part.show(s, "slice")

    if False:
        sliceProfile = getSliceProfile(SHP.Shape)
        Part.show(sliceProfile, "sliceProfile")

        for s in slices:
            ca = getClearingArea(s, sliceProfile)
            if ca.Area > 0.0:
                Part.show(ca, "clearing area")

    return slices


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

    comp = Part.makeCompound(allFaces)
    enclosureFace = PathGeom.makeBoundBoxFace(comp.BoundBox, 5.0)
    for f in allFaces:
        cut = enclosureFace.cut(f)
        enclosureFace = cut.copy()
        
    enclosureFace2 = PathGeom.makeBoundBoxFace(comp.BoundBox, 4.0)

    return enclosureFace2.cut(enclosureFace)
