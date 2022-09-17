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
import Features.PathFeatureExtensions as FeatureExtensions
import Macros.Macro_CombineRegions as CombineRegions
import Macros.Macro_AlignToFeature as AlignToFeature
import PathScripts.PathUtils as PathUtils
import PathScripts.drillableLib as drillableLib


__doc__ = "Class and implementation of a Target Shape."


if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


translate = FreeCAD.Qt.translate


class TargetShape(PathOp2.ObjectOp2):
    def opFeatures(self, obj):
        """opFeatures(obj) ... returns the OR'ed list of features used and supported by the operation.
        The default implementation returns "FeatureTool | FeatureDepths | FeatureHeights | FeatureStartPoint"
        Should be overwritten by subclasses."""
        return (
            PathOp2.FeatureBaseGeometry
            | PathOp2.FeatureHoleGeometry
            # | PathOp2.FeatureBaseEdges
            | PathOp2.FeatureHeightsDepths
            | PathOp2.FeatureExtensions
            | PathOp2.FeatureLocations
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
                "App::PropertyStringList",
                "Disabled",
                "Base",
                translate("Path", "List of disabled features"),
            ),
            (
                "App::PropertyVectorList",
                "PointLocations",
                "Base",
                translate(
                    "Path", "List of locations for vertical, point-milling operations."
                ),
            ),
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
                "App::PropertyLink",
                "RotationReference",
                "Rotation",
                translate("Path", "Feature reference for rotation to be applied."),
            ),
            (
                "App::PropertyLinkSubListGlobal",
                "RotationReferenceLink",
                "Rotation",
                translate("Path", "Feature reference for rotation to be applied."),
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
                "App::PropertyVector",
                "RotationsValues",
                "Rotation",
                translate(
                    "Path",
                    "Rotations applied to the model to access this target shape. Values",
                ),
            ),
            (
                "App::PropertyString",
                "RotationsOrder",
                "Rotation",
                translate(
                    "Path",
                    "Rotations applied to the model to access this target shape. Order",
                ),
            ),
            (
                "App::PropertyVector",
                "CenterOfRotation",
                "Rotation",
                translate(
                    "Path",
                    "Center of rotation for rotations applied.",
                ),
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
            "RotationsValues": FreeCAD.Vector(0.0, 0.0, 0.0),
            "RotationsOrder": "",
            "CenterOfRotation": FreeCAD.Vector(0.0, 0.0, 0.0),
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
        # self._printCurrentDepths(obj, "Pre-opUpdateDepths")
        AlignToFeature.CENTER_OF_ROTATION = obj.CenterOfRotation
        rotations, __ = AlignToFeature.getRotationsForObject(obj)
        # print(f"opUpdateDepths() rotations: {rotations}")
        mins = []
        if not obj.Base or len(obj.Base) == 0:
            for m in self.job.Model.Group:
                rotatedBase = AlignToFeature.rotateShapeWithList(m.Shape, rotations)
                rotatedBase.translate(obj.CenterOfRotation.negative())
                mins.append(rotatedBase.BoundBox.ZMin)
                # m.purgeTouched()
            finDep = min(mins)
        else:
            for base, subs in obj.Base:
                rotatedBase = AlignToFeature.rotateShapeWithList(base.Shape, rotations)
                rotatedBase.translate(obj.CenterOfRotation.negative())
                base.purgeTouched()
                for s in subs:
                    mins.append(rotatedBase.getElement(s).BoundBox.ZMin)
            finDep = min(mins)

        # Rotate stock and adjust start height
        rotatedStock = AlignToFeature.rotateShapeWithList(
            self.job.Stock.Shape, rotations
        )
        rotatedStock.translate(obj.CenterOfRotation.negative())
        # self.job.Stock.purgeTouched()
        strDep = rotatedStock.BoundBox.ZMax

        # print(f"opUpdateDepths() strDep: {strDep};  finDep: {finDep}")
        obj.setExpression("OpStockZMax", "{} mm".format(strDep))
        obj.setExpression("OpStartDepth", "{} mm".format(strDep))
        obj.setExpression("OpFinalDepth", "{} mm".format(finDep))
        # self.applyExpression(obj, "OpStartDepth", "{} mm".format(strDep))
        # self.applyExpression(obj, "OpFinalDepth", "{} mm".format(finDep))
        self.applyExpression(obj, "StartDepth", "OpStartDepth")
        self.applyExpression(obj, "FinalDepth", "OpFinalDepth")
        obj.OpStartDepth = "{} mm".format(strDep)
        obj.OpFinalDepth = "{} mm".format(finDep)

        # self._printCurrentDepths(obj, "Post-opUpdateDepths")
        pass

    def showShape(self, obj):
        shpObj = Part.show(obj.Shape, "TargetShape")
        shpObj.Label = f"Target Shape - {obj.Name}"
        shpObj.purgeTouched()

    def _getRotationsList(self, obj, mapped=False):
        axisMap = {"x": "A", "y": "B", "z": "C"}
        rotations = []
        for i in range(len(obj.RotationsOrder)):
            axis = obj.RotationsOrder[i]
            useAxis = axis.upper()
            if mapped:
                useAxis = axisMap[axis]

            rotations.append(
                (
                    useAxis,
                    getattr(obj.RotationsValues, axis),
                )
            )
        return rotations

    # Hole-related methods
    def holeDiameter(self, obj, base, sub):
        """holeDiameter(obj, base, sub) ... returns the diameter of the specified hole."""
        try:
            shape = base.Shape.getElement(sub)
            if shape.ShapeType == "Vertex":
                return 0

            if shape.ShapeType == "Edge" and type(shape.Curve) == Part.Circle:
                return shape.Curve.Radius * 2

            if shape.ShapeType == "Face":
                for i in range(len(shape.Edges)):
                    if (
                        type(shape.Edges[i].Curve) == Part.Circle
                        and shape.Edges[i].Curve.Radius * 2
                        < shape.BoundBox.XLength * 1.1
                        and shape.Edges[i].Curve.Radius * 2
                        > shape.BoundBox.XLength * 0.9
                    ):
                        return shape.Edges[i].Curve.Radius * 2

            # for all other shapes the diameter is just the dimension in X.
            # This may be inaccurate as the BoundBox is calculated on the tessellated geometry
            PathLog.warning(
                translate(
                    "Path",
                    "Hole diameter may be inaccurate due to tessellation on face. Consider selecting hole edge.",
                )
            )
            return shape.BoundBox.XLength
        except Part.OCCError as e:
            PathLog.error(e)

        return 0

    def holePosition(self, obj, base, sub):
        """holePosition(obj, base, sub) ... returns a Vector for the position defined by the given features.
        Note that the value for Z is set to 0."""

        try:
            shape = base.Shape.getElement(sub)
            if shape.ShapeType == "Vertex":
                return FreeCAD.Vector(shape.X, shape.Y, 0)

            if shape.ShapeType == "Edge" and hasattr(shape.Curve, "Center"):
                return FreeCAD.Vector(shape.Curve.Center.x, shape.Curve.Center.y, 0)

            if shape.ShapeType == "Face":
                if hasattr(shape.Surface, "Center"):
                    return FreeCAD.Vector(
                        shape.Surface.Center.x, shape.Surface.Center.y, 0
                    )
                if len(shape.Edges) == 1 and type(shape.Edges[0].Curve) == Part.Circle:
                    return shape.Edges[0].Curve.Center
        except Part.OCCError as e:
            PathLog.error(e)

        PathLog.error(
            translate(
                "Path",
                "Feature %s.%s cannot be processed as a circular hole - please remove from Base geometry list.",
            )
            % (base.Label, sub)
        )
        return None

    def isHoleEnabled(self, obj, base, sub):
        """isHoleEnabled(obj, base, sub) ... return true if hole is enabled."""
        name = "%s.%s" % (base.Name, sub)
        return name not in obj.Disabled

    def findAllHoles(self, obj):
        """findAllHoles(obj) ... find all holes of all base models and assign as features."""
        PathLog.track()
        job = self.getJob(obj)
        if not job:
            return

        # matchvector = None if job.JobType == "Multiaxis" else FreeCAD.Vector(0, 0, 1)
        # tooldiameter = obj.ToolController.Tool.Diameter

        matchvector = FreeCAD.Vector(0, 0, 1)
        tooldiameter = 0.1

        features = []
        for base in self.model:
            features.extend(
                drillableLib.getDrillableTargets(
                    base, ToolDiameter=tooldiameter, vector=matchvector
                )
            )
        obj.Hole = features
        obj.Disabled = []

    def _processHoles(self, obj):
        """_processHoles(obj) ... processes all Base features and Locations and collects
        them in a list of positions and radii which is then passed to circularHoleExecute(obj, holes).
        If no Base geometries and no Locations are present, the job's Base is inspected and all
        drillable features are added to Base. In this case appropriate values for depths are also
        calculated and assigned.
        Do not overwrite, implement circularHoleExecute(obj, holes) instead."""
        PathLog.track()

        holes = []
        for base, subs in obj.Hole:
            for sub in subs:
                PathLog.debug("processing {} in {}".format(sub, base.Name))
                if self.isHoleEnabled(obj, base, sub):
                    pos = self.holePosition(obj, base, sub)
                    if pos:
                        holes.append(
                            FreeCAD.Vector(
                                pos.x, pos.y, self.holeDiameter(obj, base, sub)
                            )
                        )

        for loc in obj.Locations:
            holes.append(FreeCAD.Vector(loc.x, loc.y, 0.0))

        # if len(holes) > 0:
        #    self.circularHoleExecute(obj, holes)

        return holes

    # Main executable method
    def opExecute(self, obj):
        """opExecute(obj) ... called whenever the receiver needs to be recalculated.
        See documentation of execute() for a list of base functionality provided."""
        # PathLog.debug("TargetShape.opExecute()")
        hasGeometry = False
        avoidFeatures = []
        sourceGeometry = []
        targetRegions = []
        targetShapes = []
        AlignToFeature.CENTER_OF_ROTATION = obj.CenterOfRotation

        if obj.Face == "None" and obj.Edge == "None":
            rotations = []
        else:
            rotations, isPlanar = AlignToFeature.getRotationsForObject(obj)
            if not isPlanar:
                FreeCAD.Console.PrintError(
                    f"TargetShape.opExecute() Feature not planar: {obj.Face}/{obj.Edge}\n"
                )
                return

        # Store for reference by other objects
        rOrder, rVals = AlignToFeature._rotationsToOrderAndValues(rotations)
        obj.RotationsOrder = rOrder
        obj.RotationsValues = rVals
        # print(
        #    f"TargetShape.opExecute()\nobj.RotationsValues: {obj.RotationsValues};  \nobj.RotationsOrder: {obj.RotationsOrder};  \nobj.InvertDirection: {obj.InvertDirection}\nSD: {obj.StartDepth.Value};  FD: {obj.FinalDepth.Value}"
        # )
        # print(f"restore rotations as: {self._getRotationsList(obj)}")
        # print(f"actual rotations: {rotations}")

        # Get extensions and identify faces to avoid
        extensions = FeatureExtensions.getExtensions(obj)
        for e in extensions:
            if e.extType == "Avoid":
                avoidFeatures.append(e.feature)

        if rotations:
            rotatedStockShp = AlignToFeature.rotateShapeWithList(
                self.job.Stock.Shape, rotations
            )
            rotatedStockShp.translate(obj.CenterOfRotation.negative())
            # Part.show(rotatedStockShp, "RotStock")
        else:
            rotatedStockShp = self.job.Stock.Shape

        if obj.Base:
            # PathLog.info("Processing base items ...")
            for (base, subList) in obj.Base:
                rawFaces = []
                if rotations:
                    rotatedBaseShp = AlignToFeature.rotateShapeWithList(
                        base.Shape, rotations
                    )
                    rotatedBaseShp.translate(obj.CenterOfRotation.negative())
                    # Part.show(rotatedBaseShp, "RotBase")
                else:
                    rotatedBaseShp = base.Shape

                for sub in subList:
                    if sub.startswith("Face"):
                        rawFaces.append(rotatedBaseShp.getElement(sub).copy())
                        # Add applicable extension
                        for ext in extensions:
                            if ext.feature == sub:
                                # Set indexed base shape for extension
                                ext.rotatedBaseShp = rotatedBaseShp
                                wire = ext.getWire()
                                if wire:
                                    faces = ext.getExtensionFaces(wire)
                                    for f in faces:
                                        rawFaces.append(f)
                                        # Part.show(f, "ExtFace")
                                        # self.exts.append(f)
                            else:
                                PathLog.debug(f"No extension found for {ext.feature}")
                    else:
                        PathLog.error(
                            f"Build Shape does not support {base.Label}.{sub}"
                        )
                # Efor

                # region, fusedFaces = CombineRegions._executeAsMacro2(rawFaces)  # Uses Gui if available
                region, fusedFaces = CombineRegions._executeAsMacro3(
                    rawFaces, obj.RespectFeatureHoles, obj.RespectMergedHoles
                )
                if region is None:
                    # No region to process. Perhaps vertically oriented faces and model needs rotation
                    FreeCAD.Console.PrintError(
                        "No 'region' to process from CombineRegions module.\n"
                    )
                    continue

                region.translate(FreeCAD.Vector(0.0, 0.0, obj.FinalDepth.Value))
                targetRegions.append(region)
                sourceGeometry.append(fusedFaces)

                # stockTop = rotatedStockShp.BoundBox.ZMax
                stockThickness = rotatedStockShp.BoundBox.ZLength
                extLen = obj.StartDepth.Value - obj.FinalDepth.Value
                # print(f"TargetShape extLen: {extLen}")
                if extLen > 0.0:
                    extReg = region.extrude(FreeCAD.Vector(0.0, 0.0, extLen))
                    extSrc = fusedFaces.extrude(
                        FreeCAD.Vector(0.0, 0.0, -1.0 * stockThickness)
                    )
                    trimWithFaces = extReg.cut(extSrc)
                    trimWithBase = trimWithFaces.cut(rotatedBaseShp).removeSplitter()
                    # trimWithBase = trimWithFaces.cut(base.Shape)
                    # shape = trimWithBase.common(self.job.Stock.Shape)
                    # targetShapes.append(shape)
                    targetShapes.append(trimWithBase)
                else:
                    PathLog.warning("stock top - final depth - depth allowance < 0.0")

                # Reset rotations
                del rotatedBaseShp
            # Efor
            del rotatedStockShp

            # Efor

            # obj.Shape = Part.makeCompound(targetShapes)
            hasGeometry = True

        holes = self._processHoles(obj)
        if holes:
            hasGeometry = True
            obj.PointLocations = holes
            print(f"holes: {holes}")
            dep = obj.StartDepth.Value - obj.FinalDepth.Value
            for v in holes:
                rad = v.z * 0.5
                if rad <= 0.001:
                    print(f"Setting a small hole radius ({rad}) to 0.5 mm.")
                    rad = 0.5
                cyl = Part.makeCylinder(rad, dep)
                cyl.translate(FreeCAD.Vector(v.x, v.y, obj.FinalDepth.Value))
                targetShapes.append(cyl)

        if not hasGeometry:
            for m in self.job.Model.Group:
                rotatedBaseShp = AlignToFeature.rotateShapeWithList(m.Shape, rotations)
                rotatedBaseShp.translate(obj.CenterOfRotation.negative())
                modelEnv = PathUtils.getEnvelope(
                    rotatedBaseShp, subshape=None, depthparams=self.depthparams
                )
                targetShapes.append(modelEnv)

        obj.Shape = Part.makeCompound(targetShapes)

    # Proxy method for Extensions feature
    def rotateShapeWithList(self, shape, rotations):
        return AlignToFeature.rotateShapeWithList(shape, rotations)


# Eclass


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
