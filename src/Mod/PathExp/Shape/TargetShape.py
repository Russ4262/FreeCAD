# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2022 Russell Johnson (russ4262) <russ4262@gmail.com>    *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
# *                                                                         *
# *   This library is free software; you can redistribute it and/or         *
# *   modify it under the terms of the GNU Library General Public           *
# *   License as published by the Free Software Foundation; either          *
# *   version 2 of the License, or (at your option) any later version.      *
# *                                                                         *
# *   This library  is distributed in the hope that it will be useful,      *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this library; see the file COPYING.LIB. If not,    *
# *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
# *   Suite 330, Boston, MA  02111-1307, USA                                *
# *                                                                         *
# ***************************************************************************

import FreeCAD
import Part
import Ops.PathOp2 as PathOp2
import PathScripts.PathLog as PathLog
import PathScripts.PathGeom as PathGeom
import Features.PathFeatureExtensions as FeatureExtensions
import Macros.Macro_CombineRegions as CombineRegions
import math


__doc__ = "Class and implementation of a Target Shape."


if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


translate = FreeCAD.Qt.translate
ROT_VECTS = {
    "X": FreeCAD.Vector(1.0, 0.0, 0.0),
    "Y": FreeCAD.Vector(0.0, 1.0, 0.0),
    "Z": FreeCAD.Vector(0.0, 0.0, 1.0),
}


class TargetShape(PathOp2.ObjectOp2):
    def opFeatures(self, obj):
        """opFeatures(obj) ... returns the OR'ed list of features used and supported by the operation.
        The default implementation returns "FeatureTool | FeatureDepths | FeatureHeights | FeatureStartPoint"
        Should be overwritten by subclasses."""
        return (
            PathOp2.FeatureBaseGeometry
            | PathOp2.FeatureBaseEdges
            | PathOp2.FeatureHeightsDepths
            | PathOp2.FeatureExtensions
        )

    def initOperation(self, obj):
        """initOperation(obj) ... implement to create additional properties.
        Should be overwritten by subclasses."""
        # obj.addProperty("Part::PropertyPartShape", "Shape", "Path")
        obj.setEditorMode("Shape", 1)  # read-only

        for n in self.propertyEnumerations():
            setattr(obj, n[0], n[1])

        FeatureExtensions.initialize_properties(obj)

    def opPropertyDefinitions(self):
        """opPropertyDefinitions(obj) ... Store operation specific properties"""

        return [
            (
                "App::PropertyDistance",
                "DepthAllowance",
                "Shape",
                translate(
                    "Path",
                    "Set the material depth allowance for the target shape.",
                ),
            ),
            (
                "App::PropertyBool",
                "RespectFeatureHoles",
                "Shape",
                translate("Path", "Set True to respect feature holes."),
            ),
            (
                "App::PropertyBool",
                "RespectMergedHoles",
                "Shape",
                translate(
                    "Path",
                    "Set True to respect holes formed by merger of faces or regions.",
                ),
            ),
            (
                "App::PropertyBool",
                "InvertDirection",
                "Rotation",
                translate("Path", "Invert direction of reference."),
            ),
            (
                "App::PropertyString",
                "Model",
                "Rotation",
                translate("Path", "Base model name."),
            ),
            (
                "App::PropertyString",
                "Face",
                "Rotation",
                translate("Path", "Base model face name."),
            ),
            (
                "App::PropertyString",
                "Edge",
                "Rotation",
                translate("Path", "Base model edge name."),
            ),
            (
                "App::PropertyDistance",
                "OpToolDiameter",
                "Op Values",
                translate("PathOp", "Holds the diameter of the tool"),
            ),
        ]

    def opPropertyDefaults(self, obj, job):
        """opPropertyDefaults(obj, job) ... returns a dictionary of default values
        for the operation's properties."""
        defaults = {
            "RespectFeatureHoles": True,
            "RespectMergedHoles": True,
            "Model": job.Model.Group[0].Name,
            "Face": "None",
            "Edge": "None",
            "OpToolDiameter": "5 mm",
            "ExtensionLengthDefault": "2.5 mm",
        }

        return defaults

    @classmethod
    def propertyEnumerations(self, dataType="data"):
        """helixOpPropertyEnumerations(dataType="data")... return property enumeration lists of specified dataType.
        Args:
            dataType = 'data', 'raw', 'translated'
        Notes:
        'data' is list of internal string literals used in code
        'raw' is list of (translated_text, data_string) tuples
        'translated' is list of translated string literals
        """

        # Enumeration lists for App::PropertyEnumeration properties
        enums = {}

        if dataType == "raw":
            return enums

        data = list()
        idx = 0 if dataType == "translated" else 1

        PathLog.debug(enums)

        for k, v in enumerate(enums):
            data.append((v, [tup[idx] for tup in enums[v]]))
        PathLog.debug(data)

        return data

    def opSetDefaultValues(self, obj, job):
        FeatureExtensions.set_default_property_values(obj, job)

    def opOnDocumentRestored(self, obj):
        FeatureExtensions.initialize_properties(obj)

    def opUpdateDepths(self, obj):
        """opUpdateDepths(obj) ... Implement special depths calculation."""
        # Set Final Depth to bottom of model if whole model is used
        if not obj.Base or len(obj.Base) == 0:
            if len(self.job.Model.Group) == 1:
                finDep = self.job.Model.Group[0].Shape.BoundBox.ZMin
            else:
                finDep = min([m.Shape.BoundBox.ZMin for m in self.job.Model.Group])
        else:
            finDep = obj.Base[0][0].Shape.getElement(obj.Base[0][1][0]).BoundBox.ZMax
            for base, subs in obj.Base:
                for s in subs:
                    finDep = min(finDep, base.Shape.getElement(s).BoundBox.ZMin)
        obj.setExpression("OpFinalDepth", "{} mm".format(finDep))

    def showShape(self, obj):
        shpObj = Part.show(obj.Shape, "Shape")
        shpObj.Label = f"Target Shape - {obj.Name}"

    def _getRotatedBaseShape(self, obj, base):
        if obj.Face == "None":
            rotationsToApply = _getRotationsToApply(obj.Model, obj.Edge)
        else:
            rotationsToApply = _getRotationsToApply(obj.Model, obj.Face)
        return rotationsToApply, _rotateShape(base.Shape, rotationsToApply)

    def opExecute(self, obj):
        """opExecute(obj) ... called whenever the receiver needs to be recalculated.
        See documentation of execute() for a list of base functionality provided."""
        # PathLog.debug("TargetShape.opExecute()")
        avoidFeatures = []
        sourceGeometry = []
        targetRegions = []
        targetShapes = []

        # Get extensions and identify faces to avoid
        extensions = FeatureExtensions.getExtensions(obj)
        for e in extensions:
            if e.extType == "Avoid":
                avoidFeatures.append(e.feature)

        if obj.Face == "None":
            self.rotationsToApply = _getRotationsToApply(obj.Model, obj.Edge)
        else:
            self.rotationsToApply = _getRotationsToApply(obj.Model, obj.Face)

        if obj.Base:
            # PathLog.info("Processing base items ...")
            for (base, subList) in obj.Base:
                indexedBase = _rotateShape(base.Shape, self.rotationsToApply)
                indexedStock = _rotateShape(self.job.Stock.Shape, self.rotationsToApply)
                rawFaces = []
                for sub in subList:
                    if sub.startswith("Face"):
                        rawFaces.append(indexedBase.getElement(sub).copy())
                        # Add applicable extension
                        for ext in extensions:
                            if ext.feature == sub:
                                wire = ext.getWire()
                                if wire:
                                    faces = ext.getExtensionFaces(wire)
                                    for f in faces:
                                        rawFaces.append(f)
                                        # self.exts.append(f)
                            else:
                                PathLog.debug(f"No extension found for {ext.feature}")
                    else:
                        PathLog.error(
                            f"Build Shape does not support {base.Label}.{sub}"
                        )
                # Efor

                Part.show(Part.makeCompound(rawFaces), "RawFaces")

                # region, fusedFaces = CombineRegions._executeAsMacro2(rawFaces)  # Uses Gui if available
                region, fusedFaces = CombineRegions._executeAsMacro3(
                    rawFaces, obj.RespectFeatureHoles, obj.RespectMergedHoles
                )
                if region is None:
                    # No region to process. Perhaps vertically oriented faces and model needs rotation
                    continue

                region.translate(FreeCAD.Vector(0.0, 0.0, obj.FinalDepth.Value))
                targetRegions.append(region)
                sourceGeometry.append(fusedFaces)

                stockTop = indexedStock.BoundBox.ZMax
                stockThickness = indexedStock.BoundBox.ZLength
                extLen = stockTop - obj.FinalDepth.Value
                if extLen > 0.0:
                    extReg = region.extrude(FreeCAD.Vector(0.0, 0.0, extLen))
                    extSrc = fusedFaces.extrude(
                        FreeCAD.Vector(0.0, 0.0, -1.0 * stockThickness)
                    )
                    # baseCopy = base.Shape.copy()
                    trimWithFaces = extReg.cut(extSrc)
                    trimWithBase = trimWithFaces.cut(indexedBase)
                    shape = trimWithBase.common(self.job.Stock.Shape)
                    targetShapes.append(shape)
                else:
                    PathLog.warning("stock top - final depth - depth allowance < 0.0")
            # Efor

            obj.Shape = Part.makeCompound(targetShapes)


# Eclass


def _getRotationsToApply(modelName, featureName):
    if featureName == "None":
        return []
    if featureName.startswith("Edge"):
        (rotations, __) = getRotationToLine(modelName, featureName)
    else:
        (rotations, __) = getRotationToPlanarFace(modelName, featureName)
    return rotations


def _rotateShape(shape, rotations):
    rotated = shape.copy()
    for rot_vect, angle in rotations:
        rotated.rotate(FreeCAD.Vector(0.0, 0.0, 0.0), ROT_VECTS[rot_vect], angle)
    return rotated


def getRotationToLine(modelName, edgeName):
    rotations = []
    cycles = 4
    malAligned = True
    origin = FreeCAD.Vector(0.0, 0.0, 0.0)

    model = FreeCAD.ActiveDocument.getObject(modelName)
    edge = model.Shape.getElement(edgeName)  # 1, 6, 4
    e = edge.copy()
    com = e.valueAt(e.FirstParameter)
    trans = com.add(FreeCAD.Vector(0.0, 0.0, 0.0)).multiply(-1.0)
    e.translate(trans)

    while malAligned:
        cycles -= 1
        norm = e.valueAt(e.LastParameter).sub(e.valueAt(e.FirstParameter)).normalize()
        # print(f"--NORM: {norm}")
        x0 = PathGeom.isRoughly(norm.x, 0.0)
        y0 = PathGeom.isRoughly(norm.y, 0.0)
        z1 = PathGeom.isRoughly(norm.z, 1.0)
        z_1 = PathGeom.isRoughly(norm.z, -1.0)
        if not (z1 or z_1):
            if not x0:
                ang = math.degrees(math.atan2(norm.x, norm.z))
                if ang < 0.0:
                    ang = 0.0 - ang
                elif ang > 0.0:
                    ang = 180.0 - ang
                e.rotate(origin, FreeCAD.Vector(0.0, 1.0, 0.0), ang)
                rotations.append(("Y", ang))
                # print(f"  ang: {ang}")
                continue
            elif not y0:
                ang = math.degrees(math.atan2(norm.z, norm.y))
                ang = 90.0 - ang
                e.rotate(origin, FreeCAD.Vector(1.0, 0.0, 0.0), ang)
                rotations.append(("X", ang))
                # print(f"  ang: {ang}")
                continue
        elif x0 and y0 and z_1:
            e.rotate(origin, FreeCAD.Vector(1.0, 0.0, 0.0), 180.0)
            continue

        malAligned = False
        if cycles < 1:
            print("Break for cycles")
            break

    # norm = e.valueAt(e.LastParameter).sub(e.valueAt(e.FirstParameter)).normalize()
    # print(f"  {edgeName} norm: {norm}\n  rotations: {rotations}")
    # Part.show(e, edgeName)

    return (rotations, False)


def getRotationToPlanarFace(modelName, faceName):
    rotations = []
    cycles = 4
    malAligned = True
    origin = FreeCAD.Vector(0.0, 0.0, 0.0)

    model = FreeCAD.ActiveDocument.getObject(modelName)
    face = model.Shape.getElement(faceName)  # 1, 6, 4
    f = face.copy()
    com = face.CenterOfMass
    trans = com.add(FreeCAD.Vector(0.0, 0.0, 0.0)).multiply(-1.0)
    f.translate(trans)

    while malAligned:
        cycles -= 1
        norm = f.normalAt(0, 0)
        # print(f"--NORM: {norm}")
        x0 = PathGeom.isRoughly(norm.x, 0.0)
        y0 = PathGeom.isRoughly(norm.y, 0.0)
        z1 = PathGeom.isRoughly(norm.z, 1.0)
        z_1 = PathGeom.isRoughly(norm.z, -1.0)
        if not (z1 or z_1):
            if not x0:
                ang = math.degrees(math.atan2(norm.x, norm.z))
                if ang < 0.0:
                    ang = 0.0 - ang
                elif ang > 0.0:
                    ang = 180.0 - ang
                f.rotate(origin, FreeCAD.Vector(0.0, 1.0, 0.0), ang)
                rotations.append(("Y", ang))
                # print(f"  ang: {ang}")
                continue
            elif not y0:
                ang = math.degrees(math.atan2(norm.z, norm.y))
                ang = 90.0 - ang
                f.rotate(origin, FreeCAD.Vector(1.0, 0.0, 0.0), ang)
                rotations.append(("X", ang))
                # print(f"  ang: {ang}")
                continue
        elif x0 and y0 and z_1:
            f.rotate(origin, FreeCAD.Vector(1.0, 0.0, 0.0), 180.0)
            continue

        malAligned = False
        if cycles < 1:
            break

    # norm = f.normalAt(0, 0)
    # print(f"  {faceName} norm: {norm}\n  rotations: {rotations}")
    # print(f"  center of mass: {com}")
    # Part.show(f, faceName)

    isFlat = PathGeom.isRoughly(f.BoundBox.ZLength, 0.0)

    return (rotations, isFlat)


def SetupProperties():
    setup = ["RespectFeatureHoles", "RespectMergedHoles", "DepthAllowance"]
    # Add properties from Extensions Feature
    setup.extend(FeatureExtensions.SetupProperties())

    return setup


def Create(name, obj=None, parentJob=None):
    """Create(name) ... Creates and returns a Target Shape object."""
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = TargetShape(obj, name, parentJob)
    return obj


FreeCAD.Console.PrintMessage("Imported TargetShape module from PathExp workbench.\n")
