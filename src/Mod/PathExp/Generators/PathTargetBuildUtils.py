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
import Part
import Path.Geom as PathGeom
import Path.Log as PathLog
import math
from PySide import QtCore
import MeshPart

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader

DraftGeomUtils = LazyLoader("DraftGeomUtils", globals(), "DraftGeomUtils")
PathUtils = LazyLoader("PathScripts.PathUtils", globals(), "PathScripts.PathUtils")
TechDraw = LazyLoader("TechDraw", globals(), "TechDraw")


__title__ = "Path Selection Processing"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "http://www.freecadweb.org"
__doc__ = (
    "Collection of classes and functions used to process and refine user selections."
)
__contributors__ = ""


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())

isRoughly = PathGeom.isRoughly
Tolerance = PathGeom.Tolerance
isVertical = PathGeom.isVertical
isHorizontal = PathGeom.isHorizontal

# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


def makeBoundBoxFace(bBox, offset=0.0, zHeight=0.0):
    """makeBoundBoxFace(bBox, offset=0.0, zHeight=0.0)...
    Function to create boundbox face, with possible extra offset and custom Z-height."""
    p1 = FreeCAD.Vector(bBox.XMin - offset, bBox.YMin - offset, zHeight)
    p2 = FreeCAD.Vector(bBox.XMax + offset, bBox.YMin - offset, zHeight)
    p3 = FreeCAD.Vector(bBox.XMax + offset, bBox.YMax + offset, zHeight)
    p4 = FreeCAD.Vector(bBox.XMin - offset, bBox.YMax + offset, zHeight)

    L1 = Part.makeLine(p1, p2)
    L2 = Part.makeLine(p2, p3)
    L3 = Part.makeLine(p3, p4)
    L4 = Part.makeLine(p4, p1)

    return Part.Face(Part.Wire([L1, L2, L3, L4]))


def findInternalPartHoles(partObject):
    # projection = Draft.makeShape2DView(partObject, FreeCAD.Vector(0, 0, 1))
    # wires = DraftGeomUtils.findWires(projection.Edges)
    pass


def combineHorizontalFaces(faces, avoidRegions=None):
    """combineHorizontalFaces(faces, avoidRegions=None)...
    This function successfully identifies and combines multiple connected faces and
    works on multiple independent faces with multiple connected faces within the list.
    The return value is list of simplifed faces.
    The Adaptive op is not concerned with which hole edges belong to which face.

    Attempts to do the same shape connecting failed with TechDraw.findShapeOutline() and
    PathGeom.combineConnectedShapes(), so this algorithm was created.
    """
    horizontal = list()
    offset = 10.0
    topFace = None
    innerFaces = list()

    if not faces:
        return horizontal

    # Verify all incomming faces are at Z=0.0
    for f in faces:
        if f.BoundBox.ZMin != 0.0:
            f.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - f.BoundBox.ZMin))

    # Make offset compound boundbox solid and cut incoming face extrusions from it
    allFaces = Part.makeCompound(faces)
    if hasattr(allFaces, "Area") and isRoughly(allFaces.Area, 0.0):
        msg = translate(
            "PathGeom",
            "Zero working area to process. Check your selection and settings.",
        )
        PathLog.info(msg)
        return horizontal

    afbb = allFaces.BoundBox
    bboxFace = makeBoundBoxFace(afbb, offset, -5.0)
    bboxSolid = bboxFace.extrude(FreeCAD.Vector(0.0, 0.0, 10.0))
    extrudedFaces = list()
    for f in faces:
        extrudedFaces.append(f.extrude(FreeCAD.Vector(0.0, 0.0, 6.0)))

    # Fuse all extruded faces together
    allFacesSolid = extrudedFaces.pop()
    for i in range(len(extrudedFaces)):
        temp = extrudedFaces.pop().fuse(allFacesSolid)
        allFacesSolid = temp
    cut = bboxSolid.cut(allFacesSolid)

    # Identify top face and floating inner faces that are the holes in incoming faces
    for f in cut.Faces:
        fbb = f.BoundBox
        if isRoughly(fbb.ZMin, 5.0) and isRoughly(fbb.ZMax, 5.0):
            if (
                isRoughly(afbb.XMin - offset, fbb.XMin)
                and isRoughly(afbb.XMax + offset, fbb.XMax)
                and isRoughly(afbb.YMin - offset, fbb.YMin)
                and isRoughly(afbb.YMax + offset, fbb.YMax)
            ):
                topFace = f
            else:
                innerFaces.append(f)

    if not topFace:
        PathLog.debug("combineHorizontalFaces() not topFace")
        return horizontal

    outer = [Part.Face(w) for w in topFace.Wires[1:]]

    if outer:
        for f in outer:
            f.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - f.BoundBox.ZMin))

        if innerFaces:
            inner = innerFaces

            for f in inner:
                f.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - f.BoundBox.ZMin))
            innerComp = Part.makeCompound(inner)
            outerComp = Part.makeCompound(outer)
            cut = outerComp.cut(innerComp)
            for f in cut.Faces:
                horizontal.append(f)
        else:
            horizontal = outer

    # Verify all incomming avoid faces are at Z=0.0
    if avoidRegions:
        for f in avoidRegions:
            if f.BoundBox.ZMin != 0.0:
                f.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - f.BoundBox.ZMin))
        allAvoid = Part.makeCompound(avoidRegions)
        horiz = Part.makeCompound(horizontal)
        horizontal = [f for f in horiz.cut(allAvoid).Faces]

    return horizontal


def cleanFace(face):
    wires = face.Wires
    outer = Part.Face(Part.Wire(Part.__sortEdges__(wires[0].Edges)))
    if len(wires) == 1:
        return outer

    new = outer
    for w in wires[1:]:
        inner = Part.Face(Part.Wire(Part.__sortEdges__(w.Edges)))
        temp = new.cut(inner)
        new = temp

    return new


def flattenWireSingleLoop(wire, trgtDep=0.0):
    """_flattenWire(wire, trgtDep=0.0)...
    Return a flattened version of the wire loop passed in.
    It is assumed that when flattened, the wire contain no more
    than a single loop."""

    if not wire.isClosed():
        msg = translate("PathGeom", "Wire received is not closed.")
        PathLog.debug("flattenWireSingleLoop(): " + msg)

    wBB = wire.BoundBox
    if isRoughly(wBB.ZLength, 0.0):
        # Return copy of horizontal wire
        srtWire = Part.Wire(Part.__sortEdges__(wire.Edges))
        srtWire.translate(FreeCAD.Vector(0, 0, trgtDep - srtWire.BoundBox.ZMin))
        return srtWire

    # Extrude non-horizontal wire
    extFwdLen = (wBB.ZLength + 2.0) * 2.0
    wireExtrude = wire.extrude(FreeCAD.Vector(0, 0, extFwdLen))

    # Create cross-section of extrusion
    sliceZ = wire.BoundBox.ZMin + (extFwdLen / 2)
    sectionWires = wireExtrude.slice(FreeCAD.Vector(0, 0, 1), sliceZ)
    if len(sectionWires) == 0:
        return None

    # return translated wire
    flatWire = sectionWires[0]
    flatWire.translate(FreeCAD.Vector(0, 0, trgtDep - flatWire.BoundBox.ZMin))
    return flatWire


def getHorizFaceFromVertFaceLoop(vertFaces):
    """getHorizFaceFromVertFaceLoop(vertFaces)...
    Return the horizontal cross-section from a loop of vertical faces."""

    # Check if selected vertical faces form a loop
    if len(vertFaces) == 0:
        return list()

    horizFaces = list()
    vertical = PathGeom.combineConnectedShapes(vertFaces)
    vWires = [
        TechDraw.findShapeOutline(shape, 1, FreeCAD.Vector(0, 0, 1))
        for shape in vertical
    ]
    for wire in vWires:
        w = PathGeom.removeDuplicateEdges(wire)
        if w.isClosed():
            face = Part.Face(w)
            # face.tessellate(0.1)
            if isRoughly(face.Area, 0):
                PathLog.debug(
                    translate(
                        "PathPocket", "Vertical face(s) do not form a loop - ignoring"
                    )
                )
            else:
                horizFaces.append(face)
        else:
            PathLog.debug(translate("PathPocket", "Vertical face(s) loop not closed."))

    return horizFaces


def isVerticalExtrusionFace(face):
    """isVerticalExtrusionFace(face)...
    Return True if the face provided exhibits characteristics of a wire
    that has been vertically extruded, creating a vertical extrusion face.
    This method also attempts to identify bsplines that are vertically extruded.
    This method may require additional refinement at a later date."""

    fBB = face.BoundBox
    if isRoughly(fBB.ZLength, 0.0):
        return False
    if isRoughly(face.normalAt(0, 0).z, 0.0):
        return True

    extr = face.extrude(FreeCAD.Vector(0.0, 0.0, fBB.ZLength)).removeSplitter()
    if hasattr(extr, "Volume"):
        if isRoughly(extr.Volume, 0.0):
            return True
        if extr.Volume < face.Area * Tolerance:
            PathLog.debug(
                "isVerticalExtrusionFace() Check if extruded face is vertical"
            )
            return True
        else:
            # PathLog.debug("extr.Volume: {}".format(extr.Volume))
            # PathLog.debug("face.Area: {}".format(face.Area))
            # PathLog.debug("extr.Volume < face.Area * Tolerance: {}".format(face.Area * Tolerance))
            # PathLog.debug("Face count: {}".format(len(extr.Faces)))
            PathLog.debug("Face.normalAt(): {}".format(face.normalAt(0, 0)))

    return False


def isVerticalFace(face):
    if type(face.Surface) == Part.Cylinder or type(face.Surface) == Part.Cone:
        return not isVertical(face.Surface.normal(0, 0))
    elif isVertical(face):
        return True
    return False


def extrudeNonVerticalFaces(faceList, extent):
    extVect = FreeCAD.Vector(0.0, 0.0, extent)
    extrudedFaces = list()
    for f in faceList:
        if not isVerticalFace(f):
            Part.show(f)
            print("extrudeNonVerticalFaces() non-vertical face")
            extrudedFaces.append(f.extrude(extVect))
    return extrudedFaces


def fuseShapes(shapeList):
    fCnt = len(shapeList)
    if fCnt == 0:
        return None
    if fCnt == 1:
        return shapeList[0]
    fusion = shapeList[0]
    for i in range(1, fCnt):
        try:
            fused = fusion.fuse(shapeList[i])
            fusion = fused
        except Exception as ee:
            PathLog.error(str(ee))
    # return fusion.removeSplitter()
    return fusion


def extrudeFacesToSolid(faceList, extent):
    # Extrude well beyond start depth
    extVect = FreeCAD.Vector(0.0, 0.0, extent)
    extrudeFaces = [shp.extrude(extVect) for shp in faceList]

    # Fuse faces together
    if len(faceList) == 1:
        return extrudeFaces[0]
    else:
        fused = fuseShapes(extrudeFaces)
        if fused:
            return fused.removeSplitter()
    return None


def get3DEnvelope(baseShape, faceList, envTargetHeight):
    """get3DEnvelope(baseShape, faceList, envTargetHeight)...
    Take list of faces pertaining to base shape provided and extrude them upward to envelop target height.
    Returns the envelope of extruded faces as a fused solid.
    """
    bsBB = baseShape.BoundBox

    # Extrude all non-vertical faces upward
    extrudedFaces = list()
    zLen = bsBB.ZLength
    extrLen = math.floor((2.0 * zLen) + 20.0)
    extVect = FreeCAD.Vector(0.0, 0.0, extrLen)
    for f in faceList:
        if not isVertical(f):
            extrudedFaces.append(f.extrude(extVect))
    extCnt = len(extrudedFaces)
    if extCnt == 0:
        return None

    # Fuse extrusions together into single solid
    if extCnt == 1:
        solid = extrudedFaces
    else:
        solid = extrudedFaces.pop()
        for i in range(extCnt - 1):
            fusion = solid.fuse(extrudedFaces.pop())
            solid = fusion

    # Cut off the top of the solid safely above original baseShape.ZMax height
    topBox = Part.makeBox(bsBB.XLength + 10.0, bsBB.YLength + 10.0, extrLen)
    topBox.translate(FreeCAD.Vector(bsBB.XMin - 5.0, bsBB.YMin - 5.0, envTargetHeight))
    targetShape = solid.cut(
        topBox
    )  # was `clean.cut(topBox)`, but removeSplitter() is causing issues

    return targetShape


def flattenFace(shape, force=False):
    """flattenFace(shape)...
    This method attempts to return a horizontal cross-section of a single face - a vertical projection of the face.
    """
    if not isinstance(shape, Part.Face) and not force:
        PathLog.error(f"PTBU.flattenFace() face is not 'Part.Face': {type(shape)}")
        # Part.show(shape, "PTBU_Error_Shp")
        return None

    fBB = shape.BoundBox
    zLen = fBB.ZLength
    extrLen = math.floor((2.0 * zLen) + 10.0)
    extrusion = shape.extrude(FreeCAD.Vector(0.0, 0.0, extrLen))

    clean = extrusion.removeSplitter()

    # Cut off the top of the extrusion safely above original baseShape.ZMax height
    topBox = Part.makeBox(fBB.XLength + 10.0, fBB.YLength + 10.0, extrLen)
    cutZ = math.floor(fBB.ZMin + (extrLen / 2.0))
    topBox.translate(FreeCAD.Vector(fBB.XMin - 5.0, fBB.YMin - 5.0, cutZ))
    targetShape = clean.cut(topBox).removeSplitter()

    for f in targetShape.Faces:
        if isRoughly(f.BoundBox.ZMin, cutZ):
            f.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - f.BoundBox.ZMin))
            return f

    return getCrossSectionFace(shape)


def flattenVerticalFace(face):
    """flattenVerticalFace(shape)...
    This method attempts to return a horizontal cross-section of a single vertical face - a vertical projection of the face.
    """
    if not isinstance(face, Part.Face):
        return None

    wire = TechDraw.findShapeOutline(face, 1, FreeCAD.Vector(0, 0, 1))
    wire.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - wire.BoundBox.ZMin))
    return wire


def getBaseCrossSection_ORIG(baseShape, includeInternals=True, isDebug=False):
    bsBB = baseShape.BoundBox
    extrLen = math.floor(bsBB.ZLength * 4.0 + 10.0)
    extrudedFaces = extrudeNonVerticalFaces(baseShape.Faces, extrLen)
    fusion = fuseShapes(extrudedFaces)

    Part.show(fusion)
    print("getBaseCrossSection() fusion")

    if not fusion:
        if isDebug:
            PathLog.error("no fusion")
        return None

    # Cut off the top of the solid safely above original baseShape.ZMax height
    xLen = bsBB.XLength + 10.0
    yLen = bsBB.YLength + 10.0
    extrLen2 = math.floor(extrLen / 2.0)
    topBox = Part.makeBox(xLen, yLen, extrLen)
    topBox.translate(
        FreeCAD.Vector(bsBB.XMin - 5.0, bsBB.YMin - 5.0, bsBB.ZMin + extrLen2)
    )

    if includeInternals:
        cut = fusion.cut(topBox).removeSplitter()
        cut.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - cut.BoundBox.ZMax))

        faceComp = None
        faceList = [f for f in cut.Faces if isRoughly(f.BoundBox.ZMin, 0.0)]
        if faceList:
            faceComp = Part.makeCompound(faceList)
        return faceComp
    else:
        cut = topBox.cut(fusion).removeSplitter()
        cut.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - cut.BoundBox.ZMin))
        Part.show(cut)
        print("getBaseCrossSection() cut")

        faceComp = None
        for f in cut.Faces:
            # Part.show(f)
            # print("getBaseCrossSection() face")
            fBB = f.BoundBox
            if (
                isRoughly(fBB.ZMin, 0.0)
                and isRoughly(fBB.XLength, xLen)
                and isRoughly(fBB.YLength, yLen)
            ):
                Part.show(f)
                print("getBaseCrossSection() face")

                if len(f.Wires) > 1:
                    faceComp = Part.makeCompound([Part.Face(f.Wires[1])])
                    break
        return faceComp


def getBaseCrossSection(baseShape, includeInternals=True, isDebug=False):
    baseHoles = list()
    topFace = None
    bsBB = baseShape.BoundBox
    baseEnv = getEnvelope(baseShape)
    # Identify top face of envelope
    envBB = baseEnv.BoundBox
    for f in baseEnv.Faces:
        fBB = f.BoundBox
        if isRoughly(fBB.ZMin, envBB.ZMax):
            topFace = Part.Face(f.Wires[0])
            topFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - topFace.BoundBox.ZMin))
            break

    negative = baseEnv.cut(baseShape)
    sliceZ = (bsBB.ZMin + bsBB.ZMax) / 2.0
    sectionWires = negative.slice(FreeCAD.Vector(0, 0, 1), sliceZ)
    for wire in sectionWires:
        wire.translate(FreeCAD.Vector(0.0, 0.0, (bsBB.ZMin - 1.0) - wire.BoundBox.ZMin))
        wireFace = Part.Face(wire)
        extWireFace = wireFace.extrude(FreeCAD.Vector(0.0, 0.0, bsBB.ZLength + 2.0))
        cmn = baseShape.common(extWireFace)
        if isRoughly(cmn.Volume, 0.0):
            wireFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - wireFace.BoundBox.ZMin))
            baseHoles.append(wireFace)

    if baseHoles and topFace:
        return topFace.cut(Part.makeCompound(baseHoles))

    return topFace


def getBaseHoles(baseShape, includeInternals=True, isDebug=False):
    baseHoles = list()
    bsBB = baseShape.BoundBox
    baseEnv = getEnvelope(baseShape)
    negative = baseEnv.cut(baseShape)
    sliceZ = (bsBB.ZMin + bsBB.ZMax) / 2.0
    sectionWires = negative.slice(FreeCAD.Vector(0, 0, 1), sliceZ)
    for wire in sectionWires:
        wire.translate(FreeCAD.Vector(0.0, 0.0, (bsBB.ZMin - 1.0) - wire.BoundBox.ZMin))
        wireFace = Part.Face(wire)
        extWireFace = wireFace.extrude(FreeCAD.Vector(0.0, 0.0, bsBB.ZLength + 2.0))
        cmn = baseShape.common(extWireFace)
        if isRoughly(cmn.Volume, 0.0):
            wireFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - wireFace.BoundBox.ZMin))
            baseHoles.append(wireFace)
    if baseHoles:
        return Part.makeCompound(baseHoles)

    return None


def splitClosedWireAtTwoVertexes(closedWire, vertA, vertB, tolerance):
    """splitClosedWireAtTwoVertexes(self, wire, vertA, vertB) ...
    Returns two parts of a closed wire, split at the provided vertexes.  The vertexes must now be the same.
    """
    PathLog.track()

    if not closedWire.isClosed():
        PathLog.debug("closedWire is not closed")
        return (None, None)

    pnt_A = vertA.Point
    pnt_B = vertB.Point

    # Check if points are the same
    if isRoughly(pnt_A.sub(pnt_B).Length, 0.0):
        PathLog.debug("Two vertexes are roughly the same point")
        return (closedWire, closedWire)

    lenE = len(closedWire.Edges)
    edgesIdxs = [i for i in range(0, lenE)]
    indexesA = list()
    missingVertA = -1
    missingVertB = -1

    # Cycle through edges in wire to identify the edge that aligns with point A
    for idx in range(lenE):
        i = edgesIdxs.pop(0)
        edge = closedWire.Edges[i]
        # Check if first edge vertex matches first point
        if edge.Vertexes[0].Point.sub(pnt_A).Length <= tolerance:
            # PathLog.debug("missingVertA: {}".format(i))
            indexesA.append(i)
            missingVertA = i
            # Check if target wire section is a single edge
            if edge.Vertexes[1].Point.sub(pnt_B).Length <= tolerance:
                wireA = Part.Wire([edge])
                wireB = Part.Wire(
                    Part.__sortEdges__([closedWire.Edges[i] for i in edgesIdxs])
                )
                return (wireA, wireB)
            break
        else:
            edgesIdxs.append(i)

    # Exit on failure
    if missingVertA == -1:
        PathLog.debug("Did not find vertA")
        return (None, None)

    # Cycle through edges in wire to identify the edge that aligns with point B
    for idx in range(len(edgesIdxs)):
        i = edgesIdxs.pop(0)
        edge = closedWire.Edges[i]
        indexesA.append(i)
        # Check if last edge vertex matches second point
        if edge.Vertexes[1].Point.sub(pnt_B).Length <= tolerance:
            # PathLog.debug("missingVertB: {}".format(i))
            missingVertB = i
            break

    # Exit on failure
    if missingVertB == -1:
        PathLog.debug("Did not find vertB")
        return (None, None)

    wireA = Part.Wire(Part.__sortEdges__([closedWire.Edges[i] for i in indexesA]))
    wireB = Part.Wire(Part.__sortEdges__([closedWire.Edges[i] for i in edgesIdxs]))

    return (wireA, wireB)


def getCrossSectionFace(shape, sliceZ=None):
    """getCrossSectionFace(shape)... Return a cross-sectional
    face of the shape provided."""

    stockEnv = getEnvelope(shape)
    if sliceZ is None:
        sliceZ = (stockEnv.BoundBox.ZMax + stockEnv.BoundBox.ZMin) / 2.0
    sectionWires = stockEnv.slice(FreeCAD.Vector(0, 0, 1), sliceZ)
    sectFace = Part.Face(sectionWires[0])
    sectFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - sectFace.BoundBox.ZMin))
    return sectFace


def get3dCrossSectionFace(shape, sliceZ=None):
    """get3dCrossSectionFace(shape)... Return a cross-sectional
    face of the 3D shape provided, at sliceZ height or mid-point."""

    if sliceZ is None:
        sliceZ = (shape.BoundBox.ZMax + shape.BoundBox.ZMin) / 2.0
    PathLog.info(f"sliceZ: {sliceZ}")
    sectionWires = shape.slice(FreeCAD.Vector(0, 0, 1), sliceZ)
    if len(sectionWires) > 0:
        if sectionWires[0].isClosed():
            sectFace = Part.Face(sectionWires[0])
            sectFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - sectFace.BoundBox.ZMin))
            return sectFace
        Part.show(sectionWires[0], "OpenSectionWire")
    return None


def getEnvelope(shape):
    """getCrossSectionFace(shape)... Return a cross-sectional
    face of the 3D shape provided."""

    shapeBB = shape.BoundBox
    max = shapeBB.ZMin + (shapeBB.ZMax * 2.0 + 2.0)
    tmpDepthParams = PathUtils.depth_params(
        clearance_height=max + 5.0,
        safe_height=max + 3.0,
        start_depth=max,
        step_down=5.0,
        z_finish_step=0.0,
        final_depth=shapeBB.ZMin,
        user_depths=None,
    )
    return PathUtils.getEnvelope(partshape=shape, depthparams=tmpDepthParams)


# Collision avoidance related method
def getOverheadRegionsAboveHeight(baseShape, height, isDebug=False):
    """getOverheadRegionsAboveHeight(baseShape, height)...
    This method tries to determine if any overhead regions exist on the baseShape above provided height.
    Determine vertical projection of entire baseShape down to height provided.
    The face(s) are used for collision avoidance.
    Return value is None or a Part.Compound() object.
    """
    bsBB = baseShape.BoundBox
    extra = 10.0

    if height <= bsBB.ZMin:
        return getBaseCrossSection(baseShape)

    if height >= bsBB.ZMax:
        return None

    # Cut off all baseShape below height
    extDist1 = height - (bsBB.ZMin - extra)
    bottomBox = Part.makeBox(bsBB.XLength + 2.0, bsBB.YLength + 2.0, extDist1)
    bottomBox.translate(
        FreeCAD.Vector(bsBB.XMin - 1.0, bsBB.YMin - 1.0, bsBB.ZMin - extra)
    )
    overheadShape = baseShape.cut(
        bottomBox
    )  # base shape cut off bottom portion at height

    # If nothing remains above final depth, return None
    if not hasattr(overheadShape, "Volume"):
        return None
    if isRoughly(overheadShape.Volume, 0.0):
        return None

    if isDebug:
        Part.show(overheadShape)
        FreeCAD.ActiveDocument.ActiveObject.Label = "overheadShape"
        FreeCAD.ActiveDocument.ActiveObject.purgeTouched()

    # Relocate bottom of overhead shape to Z=0.0
    overheadShape.translate(
        FreeCAD.Vector(0.0, 0.0, 0.0 - overheadShape.BoundBox.ZMin)
    )  # Place bottom at zero

    # Extrude all non-vertical faces upward
    zLen = bsBB.ZLength
    extrLen = math.floor((4.0 * zLen) + 20.0)
    extrudedFaces = extrudeNonVerticalFaces(overheadShape.Faces, extrLen)
    extCnt = len(extrudedFaces)
    if extCnt == 0:
        return None

    # Fuse extrusions together into single solid and remove splitters
    if extCnt == 1:
        solid = extrudedFaces[0]
    else:
        solid = extrudedFaces.pop()
        for i in range(extCnt - 1):
            fusion = solid.fuse(extrudedFaces.pop())
            solid = fusion

    if isDebug:
        Part.show(solid)
        FreeCAD.ActiveDocument.ActiveObject.Label = "solid"
        FreeCAD.ActiveDocument.ActiveObject.purgeTouched()

    # Cut off the top of the solid safely above original baseShape.ZMax height
    topBox = Part.makeBox(bsBB.XLength + 10.0, bsBB.YLength + 10.0, extrLen)
    cutZ = math.floor(height + (extrLen / 2.0))
    topBox.translate(FreeCAD.Vector(bsBB.XMin - 5.0, bsBB.YMin - 5.0, cutZ))
    targetShape = solid.cut(topBox)

    # DO NOT REMOVE
    # This `addObject()` seems to be required in order to force internal shape recompute/update of targetShape
    obj = FreeCAD.ActiveDocument.addObject("Part::Feature", "TmpShape")
    obj.Shape = targetShape
    obj.purgeTouched()
    FreeCAD.ActiveDocument.removeObject(obj.Name)

    if isDebug:
        Part.show(targetShape)
        FreeCAD.ActiveDocument.ActiveObject.Label = "targetShape"
        FreeCAD.ActiveDocument.ActiveObject.purgeTouched()

    targetShape.translate(
        FreeCAD.Vector(0.0, 0.0, 0.0 - targetShape.BoundBox.ZMax)
    )  # Place target face(s) at Z=0.0
    # filter out only top horizontal faces of interest
    overheadFaces = list()
    for f in targetShape.Faces:
        if isRoughly(f.BoundBox.ZMin, 0.0):
            overheadFaces.append(f)

    if overheadFaces:
        comp = Part.makeCompound(overheadFaces)
        return comp

    return None


def getRegionsBelowHeight(baseShape, height, isDebug=False):
    """getRegionsBelowHeight(baseShape, height)...
    This method returns a solid representing all regions that exist on the baseShape below provided height.
    Determine vertical projection of entire baseShape starting at height provided.
    The face(s) are used for collision avoidance.
    Return value is None or a Part.Compound() object.
    """
    bsBB = baseShape.BoundBox
    extra = 10.0

    if height >= bsBB.ZMax:
        return getBaseCrossSection(baseShape)

    if height <= bsBB.ZMin:
        return None

    # Cut off all baseShape below height
    extDist1 = (bsBB.ZMax - height) + extra
    bottomBox = Part.makeBox(bsBB.XLength + 2.0, bsBB.YLength + 2.0, extDist1)
    bottomBox.translate(FreeCAD.Vector(bsBB.XMin - 1.0, bsBB.YMin - 1.0, height))
    lowerShape = baseShape.cut(bottomBox)  # base shape cut off bottom portion at height

    # If nothing remains above final depth, return None
    if not hasattr(lowerShape, "Volume"):
        return None
    if isRoughly(lowerShape.Volume, 0.0):
        return None

    if isDebug:
        Part.show(lowerShape)
        FreeCAD.ActiveDocument.ActiveObject.Label = "lowerShape"
        FreeCAD.ActiveDocument.ActiveObject.purgeTouched()

    # Relocate bottom of overhead shape to Z=0.0
    lowerShape.translate(
        FreeCAD.Vector(0.0, 0.0, -10.0 - lowerShape.BoundBox.ZMax)
    )  # Place top at -10

    # Extrude all non-vertical faces upward
    zLen = bsBB.ZLength
    extrLen = math.floor((4.0 * zLen) + 20.0)
    extrudedFaces = extrudeNonVerticalFaces(lowerShape.Faces, extrLen)
    extCnt = len(extrudedFaces)
    if extCnt == 0:
        return None

    # Fuse extrusions together into single solid and remove splitters
    if extCnt == 1:
        solid = extrudedFaces[0]
    else:
        solid = extrudedFaces.pop()
        for i in range(extCnt - 1):
            fusion = solid.fuse(extrudedFaces.pop())
            solid = fusion

    if isDebug:
        Part.show(solid)
        FreeCAD.ActiveDocument.ActiveObject.Label = "solid"
        FreeCAD.ActiveDocument.ActiveObject.purgeTouched()

    # clean = solid.removeSplitter()  # removeSplitter() causes errors with some shapes

    # Cut off the top of the solid safely above original baseShape.ZMax height
    topBox = Part.makeBox(bsBB.XLength + 10.0, bsBB.YLength + 10.0, extrLen)
    # cutZ = math.floor(height + (extrLen / 2.0))
    # topBox.translate(FreeCAD.Vector(bsBB.XMin - 5.0, bsBB.YMin - 5.0, cutZ))
    targetShape = solid.cut(topBox)

    # DO NOT REMOVE
    # This `addObject()` seems to be required in order to force internal shape recompute/update of targetShape
    obj = FreeCAD.ActiveDocument.addObject("Part::Feature", "TmpShape")
    obj.Shape = targetShape
    obj.purgeTouched()
    FreeCAD.ActiveDocument.removeObject(obj.Name)

    if isDebug:
        Part.show(targetShape)
        FreeCAD.ActiveDocument.ActiveObject.Label = "targetShape"
        FreeCAD.ActiveDocument.ActiveObject.purgeTouched()

    # targetShape.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - targetShape.BoundBox.ZMax))  # Place target face(s) at Z=0.0
    # filter out only top horizontal faces of interest
    overheadFaces = list()
    for f in targetShape.Faces:
        if isRoughly(f.BoundBox.ZMin, 0.0):
            overheadFaces.append(f)

    if overheadFaces:
        comp = Part.makeCompound(overheadFaces)
        return comp

    return None


def getThickCrossSection(baseShape, bottom, top, isDebug=False):
    """getThickCrossSection(baseShape, bottom, top, isDebug=False)...
    This method returns a solid representing all regions that exist on the baseShape below provided height.
    Determine vertical projection of entire baseShape starting at height provided.
    The face(s) are used for collision avoidance.
    Return value is None or a Part.Compound() object.
    """
    bsBB = baseShape.BoundBox

    if top < bottom:
        return None
    if bottom > top:
        return None

    if bottom <= bsBB.ZMin:
        return getRegionsBelowHeight(baseShape, top)

    if top >= bsBB.ZMax:
        return getOverheadRegionsAboveHeight(baseShape, bottom)

    # Cut off all baseShape below height
    extDist1 = top - bottom
    bottomBox = Part.makeBox(bsBB.XLength + 2.0, bsBB.YLength + 2.0, extDist1)
    bottomBox.translate(FreeCAD.Vector(bsBB.XMin - 1.0, bsBB.YMin - 1.0, bottom))
    return baseShape.common(bottomBox)


def getOverheadRegions3D(baseShape, faceList):
    faceComp = Part.makeCompound(faceList)
    bsBB = baseShape.BoundBox

    # extrude faces downward and cut away from base
    extent1 = -1 * math.floor(faceComp.BoundBox.ZMax - bsBB.ZMin + 10.0)
    removalSolid = extrudeFacesToSolid(faceList, extent1)
    if not removalSolid:
        return None

    voidBase = baseShape.cut(removalSolid)

    # move voided base down
    startDep = math.floor(bsBB.ZMin - (bsBB.ZLength / 2.0) - faceComp.BoundBox.ZMax)
    voidBase.translate(FreeCAD.Vector(0.0, 0.0, startDep - voidBase.BoundBox.ZMin))

    # extrude nonvertical faces upward at least twice height, and fuse.
    extent2 = math.floor(bsBB.ZLength * 10.0)
    extrudedFaces = extrudeNonVerticalFaces(voidBase.Faces, extent2)
    fused = fuseShapes(extrudedFaces)
    if fused:
        return fused

    return None


def getCrossSectionOfSolid(baseShape, height):
    """getCrossSectionOfSolid(baseShape, height)..."""
    bsBB = baseShape.BoundBox

    if height < bsBB.ZMin:
        return None

    if height > bsBB.ZMax:
        return None

    cuttingFace = makeBoundBoxFace(bsBB, offset=2.0, zHeight=height)
    return baseShape.common(cuttingFace)


def getCrossSectionOfSolid_2(baseShape, height):
    """getCrossSectionOfSolid_2(baseShape, height)..."""
    bsBB = baseShape.BoundBox

    if height < bsBB.ZMin:
        return None

    if height > bsBB.ZMax:
        return None

    cuttingFace = makeBoundBoxFace(bsBB, offset=4.0, zHeight=height)
    cuttingFace2 = makeBoundBoxFace(bsBB, offset=2.0, zHeight=height)
    negative = cuttingFace.cut(baseShape)
    cs = cuttingFace2.cut(negative)
    cs.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - cs.BoundBox.ZMin))
    return cs


# Solid correction using mesh
def sanitizeShape(
    shape,
    linearDeflection=0.05,
    angularDeflection=0.0174533,
    relative=False,
    sewShape=False,
    sewingTolerance=0.1,
):
    # __part__=__doc__.getObject("TargetShape001_Shape")
    # __shape__=Part.getShape(__part__,"")
    # __mesh__.Mesh=MeshPart.meshFromShape(Shape=shape, LinearDeflection=linearDeflection, AngularDeflection=angularDeflection, Relative=relative)
    mesh = MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=linearDeflection,
        AngularDeflection=angularDeflection,
        Relative=relative,
    )
    # __shape__ = Part.Shape()
    # __shape__.makeShapeFromMesh(FreeCAD.getDocument('Dropcut_3D_Test_1').getObject('Mesh').Mesh.Topology, 0.100000, False)
    newShape = Part.Shape()
    newShape.makeShapeFromMesh(mesh.Topology, sewingTolerance, sewShape)

    # __s__=App.ActiveDocument.debug_SanitizedShape.Shape.Faces
    # __s__=Part.Solid(Part.Shell(__s__))

    solid = Part.Solid(Part.Shell(newShape.Faces))
    return solid


def meshShape(
    shape,
    linearDeflection=0.03,
    angularDeflection=0.015,
    relative=False,
):
    return MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=linearDeflection,
        AngularDeflection=angularDeflection,
        Relative=relative,
    )


def cutShapeAsMesh(
    shape,
    height,
    linearDeflection=0.05,
    angularDeflection=0.0174533,
    relative=False,
    sewShape=False,
    sewingTolerance=0.1,
):
    mesh = MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=linearDeflection,
        AngularDeflection=angularDeflection,
        Relative=relative,
    )
    base = FreeCAD.Vector(0.0, 0.0, height)
    norm = FreeCAD.Vector(0.0, 0.0, 1.0)
    mesh.trimByPlane(base, norm)
    newShape = Part.Shape()
    newShape.makeShapeFromMesh(mesh.Topology, sewingTolerance, sewShape)
    # solid = Part.Solid(Part.Shell(newShape.Faces))
    topFaces = [
        f.copy() for f in newShape.Faces if PathGeom.isRoughly(f.BoundBox.ZMin, height)
    ]
    return fuseShapes(topFaces).removeSplitter()


def getRimEdge(facet, val):
    lp = None
    for i in range(0, 3):
        p = facet.Points[i]
        if PathGeom.isRoughly(p[2], val):
            if lp:
                p1 = FreeCAD.Vector(lp[0], lp[1], lp[2])
                p2 = FreeCAD.Vector(p[0], p[1], p[2])
                return Part.makeLine(p1, p2)
            else:
                lp = p
    return None


def getRimWiresOfMesh(mesh, top=True):
    """Assumption is that mesh has flat top or bottom"""
    if top:
        val = mesh.BoundBox.ZMax
    else:
        val = mesh.BoundBox.ZMin

    edges = []
    for f in mesh.Facets:
        e = getRimEdge(f, val)
        if e:
            edges.append(e)

    wires = []
    if len(edges) > 0:
        for lst in Part.sortEdges(edges):
            wires.append(Part.Wire(lst))
    return wires


def trimMeshAtHeight(mesh, height, crossSection=False):
    # Mesh has to be copied
    m = mesh.copy()
    base = FreeCAD.Vector(0.0, 0.0, height)
    norm = FreeCAD.Vector(0.0, 0.0, 1.0)
    m.trimByPlane(base, norm)
    mObj = FreeCAD.ActiveDocument.addObject("Mesh::Feature", "MeshSect")
    mObj.Mesh = m
    if crossSection:
        faces = []
        rimWires = getRimWiresOfMesh(m)
        for w in rimWires:
            if w.isClosed():
                faces.append(Part.Face(w))
            else:
                Part.show(w, "OpenWire")
        return fuseShapes(faces)
    return m


# Cross-section mesh at height
def printFacetPoints(f):
    p0 = f.Points[0]
    p1 = f.Points[1]
    p2 = f.Points[2]
    print(f"p0.z, p1.z, p2.z: {p0[2]},  {p1[2]},  {p2[2]}")


def showFacet(f, height):
    p0 = f.Points[0]
    p1 = f.Points[1]
    p2 = f.Points[2]
    v0 = FreeCAD.Vector(p0[0], p0[1], p0[2])
    v1 = FreeCAD.Vector(p1[0], p1[1], p1[2])
    v2 = FreeCAD.Vector(p2[0], p2[1], p2[2])
    w = Part.makePolygon([v0, v1, v2, v0])
    triFace = Part.Face(w)
    bbf = makeBoundBoxFace(triFace.BoundBox, offset=2.0, zHeight=height)
    Part.show(triFace, "__triFace")
    Part.show(bbf, "__bbf")
    return None


def findLine(f, height):
    p0 = f.Points[0]
    p1 = f.Points[1]
    p2 = f.Points[2]
    v0 = FreeCAD.Vector(p0[0], p0[1], p0[2])
    v1 = FreeCAD.Vector(p1[0], p1[1], p1[2])
    v2 = FreeCAD.Vector(p2[0], p2[1], p2[2])
    w = Part.makePolygon([v0, v1, v2, v0])
    triFace = Part.Face(w)
    bbf = makeBoundBoxFace(triFace.BoundBox, offset=2.0, zHeight=height)
    splitFace = triFace.cut(bbf)
    for e in splitFace.Faces[0].Edges:
        p1 = e.Vertexes[0].Point
        p2 = e.Vertexes[1].Point
        if PathGeom.isRoughly(p1.z, height) and PathGeom.isRoughly(p2.z, height):
            return e.copy()
    # Part.show(triFace, "triFace")
    # Part.show(bbf, "bbf")
    print("findLine() failed")
    return None


def lineFromFacetPoints(p1, p2):
    v1 = FreeCAD.Vector(p1[0], p1[1], p1[2])
    v2 = FreeCAD.Vector(p2[0], p2[1], p2[2])
    return Part.makeLine(v1, v2)


def crossSectionMesh(mesh, height):
    edges = []
    for f in mesh.Facets:
        p0 = f.Points[0]
        p1 = f.Points[1]
        p2 = f.Points[2]
        z0 = p0[2]
        z1 = p1[2]
        z2 = p2[2]
        hz0 = PathGeom.isRoughly(z0, height)
        hz1 = PathGeom.isRoughly(z1, height)
        hz2 = PathGeom.isRoughly(z2, height)
        if z0 > height and z1 > height and z2 > height:
            # ignore all above
            pass
        elif z0 < height and z1 < height and z2 < height:
            # ignore all below
            pass
        elif hz0:
            # check for horiz line
            if hz1:
                edges.append(lineFromFacetPoints(p0, p1))
            elif hz2:
                edges.append(lineFromFacetPoints(p0, p2))
            elif z1 > height and z2 > height:
                pass  # triangle rising from height
            elif z1 < height and z2 < height:
                pass  # triangle falling from height
            else:
                print("no Z0 horiz line")
                e = findLine(f, height)
                if e:
                    edges.append(e)
                else:
                    # showFacet(f, height)
                    pass
        elif hz1:
            # check for horiz line
            if hz2:
                edges.append(lineFromFacetPoints(p1, p2))
            elif z0 > height and z2 > height:
                pass  # triangle rising from height
            elif z0 < height and z2 < height:
                pass  # triangle falling from height
            else:
                print("no Z1 horiz line")
                e = findLine(f, height)
                if e:
                    edges.append(e)
                else:
                    # showFacet(f, height)
                    pass

        elif hz1 and z0 > height and z2 > height:
            pass  # triangle falling from height
        elif hz2 and z0 < height and z1 < height:
            pass  # triangle falling from height

        # elif z0 < height and z1 > height and z2 > height:
        #    pass  # triangle falling from height

        else:
            e = findLine(f, height)
            if e:
                edges.append(e)
            else:
                print(f"height: {height}")
                printFacetPoints(f)

    faces = []
    if len(edges) > 0:
        edgeLists = Part.sortEdges(edges)
        for lst in edgeLists:
            w = Part.Wire(lst)
            if w.isClosed():
                faces.append(Part.Face(w))
            else:
                ep0 = w.Vertexes[0].Point
                ep1 = w.Vertexes[-1].Point
                seg = Part.makeLine(ep1, ep0)
                lst.append(seg)
                w1 = Part.Wire(lst)
                if w1.isClosed():
                    faces.append(Part.Face(w1))
                else:
                    """ep0 = w1.Vertexes[0].Point
                    ln0 = Part.makeLine(ep0, FreeCAD.Vector(ep0.x, ep0.y, ep0.z + 3.0))
                    ep1 = w1.Vertexes[-1].Point
                    ln1 = Part.makeLine(ep1, FreeCAD.Vector(ep1.x, ep1.y, ep1.z + 5.0))
                    Part.show(w1, "OpenWire1")
                    Part.show(ln0, "OpenStart1")
                    Part.show(ln1, "OpenEnd1")"""
                    pass

    if len(faces) > 0:
        for fc in faces:
            fc.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - fc.BoundBox.ZMin))
        fused = fuseShapes(faces)
        # Part.show(fused, "CSMesh")
        return fused
    return None
