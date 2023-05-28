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


__title__ = "Path Slice Solid Macro"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Path slicing macro for 3D shapes with regional efficiency included."


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())

IS_MACRO = True


# Support functions
def removeTopFaceFromSlice(slice):
    faces = []
    zMax = slice.BoundBox.ZMax
    for f in slice.Faces:
        if not PathGeom.isRoughly(f.BoundBox.ZMin, zMax):
            faces.append(f)

    return faces


def _getBottomFaces(shape):
    faces = []
    zMax = min([f.BoundBox.ZMax for f in shape.Faces])
    # print("{} faces in shape & ZMin: {}".format(len(shape.Faces), round(zMax, 6)))
    for f in shape.Faces:
        # print("f.BB.ZMax: {}".format(round(f.BoundBox.ZMax, 6)))
        if PathGeom.isRoughly(f.BoundBox.ZMax, zMax):
            faces.append(f)

    return faces


def _makeSliceShape(shape, zmin, thickness):
    try:
        face = PathGeom.makeBoundBoxFace(shape.BoundBox, 5.0, zmin)
    except Exception as ee:
        PathLog.error(f"{ee}")
        return None
    return face.extrude(FreeCAD.Vector(0.0, 0.0, thickness))


def _sliceSolid(solid, depths, region=None):
    if not isinstance(depths, list):
        PathLog.error("sliceSolid() `depths` is not list object")
        return []

    # print("depths: {}".format(depths))
    solids = []
    lenDP = len(depths)

    # prep region
    if region:
        region.translate(
            FreeCAD.Vector(0.0, 0.0, solid.BoundBox.ZMin - 1.0 - region.BoundBox.ZMin)
        )
        regExt = region.extrude(FreeCAD.Vector(0.0, 0.0, solid.BoundBox.ZLength + 2.0))
        shape = solid.common(regExt)
    else:
        shape = solid

    for i in range(1, lenDP):
        d = depths[i]
        thickness = depths[i - 1] - depths[i]
        # PathLog.info("slicing at {} mm with thickness of {} mm".format(d, thickness))
        # print("Layer Depth: {}".format(round(d, 6)))

        sliceTool = _makeSliceShape(shape, d, thickness)
        if sliceTool is None:
            # print("Slice tool is None.")
            break
        common = shape.common(sliceTool).removeSplitter()
        if len(common.Solids) > 1:
            useDepths = depths[i - 1 :]
            for s in common.Solids:
                bottomFaces = _getBottomFaces(s)
                for bf in bottomFaces:
                    subSolids = _sliceSolid(shape, useDepths, region=bf)
                    solids.extend(subSolids)
            # print("Breaking main loop after processing multiple solids.")
            break
        else:
            # print("Processed single solid.")
            solids.extend(common.Solids)

    return solids


def _slicesToCrossSections(slices):
    faces = []
    for s in slices:
        faces.extend([f.copy() for f in _getBottomFaces(s)])
    return faces


def _slicesTo3DShells(slices):
    faces = []
    for s in slices:
        nonTopFaces = [f.copy() for f in removeTopFaceFromSlice(s)]
        fusion = nonTopFaces[0]
        for ntf in nonTopFaces[1:]:
            fused = fusion.fuse(ntf)
            fusion = fused
        faces.append(fusion)
    return faces


# Public function
def sliceSolid(solid, depths, output="Solids"):
    """sliceSolid(solid, depths, output="Solids")
    Return slices of a solid as set of solids, cross-sections, or 3D shells.  The shapes returned are provided
    in order of region, for efficiency's sake.
    Arguments:
        solid = Shape object containing one or more `Solids` in Shape.Solids attribute
        depths = slice depths with first depth being top of first slice, and second value being
                 the bottom of the first slice.
        output = Type of shapes list to return
    """
    if output not in ["Solids", "CrossSections", "3DShells"]:
        PathLog.error("output value not in list: Solids, CrossSections, 3DShells")
        raise ValueError
    if not isinstance(depths, list):
        PathLog.error("depths is not list")
        raise ValueError
    if len(depths) < 2:
        PathLog.error("depths list is too short")
        raise ValueError

    slices = _sliceSolid(solid, depths)

    if output == "CrossSections":
        return _slicesToCrossSections(slices)
    if output == "3DShells":
        return _slicesTo3DShells(slices)

    return slices


if IS_MACRO:
    print("\n\n\n\n")
    doc = FreeCAD.ActiveDocument
    obj = doc.Solid
    bb = obj.Shape.BoundBox
    safeHeight = bb.ZMax + 5.0
    step = -5.0  # Must be negative to step down
    start = bb.ZMax + step
    final = bb.ZMin
    depths = [safeHeight, start]
    while start > final:
        start += step
        if start < final:
            start = final
        depths.append(start)
    print(f"depths: {depths}")

    solids = sliceSolid(obj.Shape, depths, "Solids")
    group = doc.addObject("App::DocumentObjectGroup", "Group")
    group.Label = "Solids"
    group2 = doc.addObject("App::DocumentObjectGroup", "Group")
    group2.Label = "Cross-sections"
    for s in solids:
        slc = Part.show(s, "Solid")
        group.addObject(slc)
        fcs = _getBottomFaces(s)
        for f in fcs:
            fc = Part.show(f, "Face")
            group2.addObject(fc)

    shells = _slicesTo3DShells(solids)
    group = doc.addObject("App::DocumentObjectGroup", "Group")
    group.Label = "Shells"
    for s in shells:
        slc = Part.show(s, "Shell")
        group.addObject(slc)

    doc.recompute()
