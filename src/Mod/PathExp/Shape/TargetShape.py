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
import Path.Log as PathLog
import Features.PathFeatureExtensions as FeatureExtensions
import Macros.Macro_CombineRegions as CombineRegions
import Macros.Macro_AlignToFeature as AlignToFeature
import PathScripts.PathUtils as PathUtils
import Path.Base.Drillable as drillableLib
import DraftGeomUtils
import Path.Geom as PathGeom
import strategies.PathTargetBuildUtils as PathTargetBuildUtils
import math
import TechDraw


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
                "App::PropertyEnumeration",
                "FeatureBoundary",
                "Shape",
                translate("Path", "Boundary for base geometry features."),
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
            "FeatureBoundary": "Feature",
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
    def propertyEnumerations(cls, dataType="data"):
        """helixOpPropertyEnumerations(dataType="data")... return property enumeration lists of specified dataType.
        Args:
            dataType = 'data', 'raw', 'translated'
        Notes:
        'data' is list of internal string literals used in code
        'raw' is list of (translated_text, data_string) tuples
        'translated' is list of translated string literals
        """

        # Enumeration lists for App::PropertyEnumeration properties
        enums = {
            "FeatureBoundary": [
                (translate("Path", "Feature"), "Feature"),
                (translate("Path", "Feature Extended"), "FeatureExt"),
                (translate("Path", "BoundBox"), "Boundbox"),
                (translate("Path", "Stock"), "Stock"),
                (translate("Path", "Stock Extended"), "StockExt"),
                (translate("Path", "Waterline"), "Waterline"),
                (translate("Path", "Waterline Extended"), "WaterlineExt"),
            ]
        }

        if dataType == "raw":
            return enums

        data = []
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
        if len(rotations) > 0:
            print(f"opUpdateDepths() rotations: {rotations}")
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
                    rotatedBase = AlignToFeature.rotateShapeWithList(
                        base.Shape, rotations
                    )
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
    def holeDiameter(self, base, sub):
        """holeDiameter(base, sub) ... returns the diameter of the specified hole."""
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

    def holePosition_orig(self, base, sub):
        """holePosition(base, sub) ... returns a Vector for the position defined by the given features.
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

    def holePosition(self, baseShape, sub):
        """holePosition(base, sub) ... returns a Vector for the position defined by the given features.
        Note that the value for Z is set to 0."""

        try:
            shape = baseShape.getElement(sub)
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
                "Feature %s cannot be processed as a circular hole - please remove from Base geometry list.",
            )
            % sub
        )
        return None

    def isHoleEnabled(self, obj, base, sub):
        """isHoleEnabled(obj, base, sub) ... return true if hole is enabled."""
        name = "%s.%s" % (base.Name, sub)
        return name not in obj.Disabled

    def findAllHoles_ORIG(self, obj):
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

    def findAllHoles(self, obj):
        """findAllHoles(obj) ... find all holes of all base models and assign as features."""
        PathLog.track()
        PathLog.info("PathCircularHoleBase findAllHoles()")
        job = self.getJob(obj)
        if not job:
            return

        # matchvector = None if job.JobType == "Multiaxis" else FreeCAD.Vector(0, 0, 1)
        # tooldiameter = obj.ToolController.Tool.Diameter
        matchvector = FreeCAD.Vector(0, 0, 1)
        tooldiameter = 0.2

        if obj.Face == "None" and obj.Edge == "None":
            rotations = []
        else:
            rotations, isPlanar = AlignToFeature.getRotationsForObject(obj)
            if not isPlanar:
                FreeCAD.Console.PrintError(
                    f"ObjectOp.findAllHoles() Feature not planar: {obj.Face}/{obj.Edge}\n"
                )
                return

        features = []
        for base in job.Model.Group:
            if rotations:
                rotatedBaseShp = AlignToFeature.rotateShapeWithList(
                    base.Shape, rotations
                )
                rotatedBaseShp.translate(obj.CenterOfRotation.negative())
                # Part.show(rotatedBaseShp, "RotBase")
            else:
                rotatedBaseShp = base.Shape

            targetFaces = drillableLib.getDrillableTargets(
                rotatedBaseShp, ToolDiameter=tooldiameter, vector=matchvector
            )
            # targets = [(base, f) for f in targetFaces]
            targets = [(base, f) for f in targetFaces]
            features.extend(targets)
        # obj.Base = features
        obj.Hole = features
        obj.Disabled = []

    def _processHoles(self, obj):
        """_processHoles(obj) ... processes all Base features and Locations and collects
        them in a list of positions and radii which is then passed to circularHoleExecute(obj, holes).
        If no Base geometries and no Locations are present, the job's Base is inspected and all
        drillable features are added to Base. In this case appropriate values for depths are also
        calculated and assigned."""
        PathLog.track()

        if obj.Face == "None" and obj.Edge == "None":
            rotations = []
        else:
            rotations, isPlanar = AlignToFeature.getRotationsForObject(obj)
            if not isPlanar:
                FreeCAD.Console.PrintError(
                    f"ObjectOp.findAllHoles() Feature not planar: {obj.Face}/{obj.Edge}\n"
                )
                return

        holes = []
        for base, subs in obj.Hole:
            if rotations:
                rotatedBaseShp = AlignToFeature.rotateShapeWithList(
                    base.Shape, rotations
                )
                rotatedBaseShp.translate(obj.CenterOfRotation.negative())
                # Part.show(rotatedBaseShp, "RotBase")
            else:
                rotatedBaseShp = base.Shape

            for sub in subs:
                PathLog.debug("processing {} in {}".format(sub, base.Name))
                if self.isHoleEnabled(obj, base, sub):
                    pos = self.holePosition(rotatedBaseShp, sub)
                    if pos:
                        holes.append(
                            FreeCAD.Vector(pos.x, pos.y, self.holeDiameter(base, sub))
                        )

        for loc in obj.Locations:
            holes.append(FreeCAD.Vector(loc.x, loc.y, 0.0))

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

        if rotations:
            rotatedStockShp = AlignToFeature.rotateShapeWithList(
                self.job.Stock.Shape, rotations
            )
            rotatedStockShp.translate(obj.CenterOfRotation.negative())
            # Part.show(rotatedStockShp, "RotStock")
        else:
            rotatedStockShp = self.job.Stock.Shape

        # Get extensions and identify faces to avoid
        extensions = FeatureExtensions.getExtensions(obj)
        for e in extensions:
            if e.extType == "Avoid":
                avoidFeatures.append(e.feature)

        if obj.Base:
            # PathLog.info("Processing base items ...")
            for (base, subList) in obj.Base:
                rawFaces = []
                rawEdges = []
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
                        # rawFaces.append(rotatedBaseShp.getElement(sub).copy())
                        fc = applyFeatureBoundary(
                            obj.FeatureBoundary,
                            rotatedBaseShp.getElement(sub),
                            base.Shape,
                            self.stock.Shape,
                            obj.RespectFeatureHoles,
                            obj.ExtensionLengthDefault.Value,
                        )  # featureBoundary, face, baseShape, stockShape
                        rawFaces.append(fc)
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
                    elif sub.startswith("Edge"):
                        rawEdges.append(rotatedBaseShp.getElement(sub).copy())
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

                # Process all edges
                openEdges0 = []
                wires0 = DraftGeomUtils.findWires(rawEdges)
                for w in wires0:
                    if w.isClosed():
                        fc = applyFeatureBoundary(
                            obj.FeatureBoundary,
                            Part.Face(w),
                            base.Shape,
                            self.stock.Shape,
                            obj.RespectFeatureHoles,
                            obj.ExtensionLengthDefault.Value,
                        )  # featureBoundary, face, baseShape, stockShape
                        rawFaces.append(fc)
                    else:
                        # PathLog.error("Wire not closed.")
                        # Part.show(w, "OpenWireError 1")
                        openEdges0.extend(flattenOpenWire(w).Edges)
                wires1 = DraftGeomUtils.findWires(openEdges0)
                for w in wires1:
                    if w.isClosed():
                        fc = applyFeatureBoundary(
                            obj.FeatureBoundary,
                            Part.Face(w),
                            base.Shape,
                            self.stock.Shape,
                            obj.RespectFeatureHoles,
                            obj.ExtensionLengthDefault.Value,
                        )  # featureBoundary, face, baseShape, stockShape
                        rawFaces.append(fc)
                    else:
                        PathLog.error("Wire not closed.")
                        Part.show(w, "OpenWireError 2")

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

            hasGeometry = True

        else:
            # No base geometry provide
            pass

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
                mdlCS = PathTargetBuildUtils.getCrossSectionFace(modelEnv)
                mdlCS.translate(
                    FreeCAD.Vector(
                        0.0, 0.0, m.Shape.BoundBox.ZMin - mdlCS.BoundBox.ZMin
                    )
                )
                fc = applyFeatureBoundary(
                    obj.FeatureBoundary,
                    mdlCS,
                    m.Shape,
                    self.stock.Shape,
                    obj.RespectFeatureHoles,
                    obj.ExtensionLengthDefault.Value,
                )
                ftExt = fc.extrude(
                    FreeCAD.Vector(
                        0.0, 0.0, self.stock.Shape.BoundBox.ZMax - m.Shape.BoundBox.ZMin
                    )
                )
                targetShapes.append(ftExt)

        obj.Shape = Part.makeCompound(targetShapes)

    # Proxy method for Extensions feature
    def rotateShapeWithList(self, shape, rotations):
        return AlignToFeature.rotateShapeWithList(shape, rotations)


# Eclass


def edgesToFaces(edges):
    wires = DraftGeomUtils.findWires(edges)
    for w in wires:
        if w.isClosed():
            fc = applyFeatureBoundary(
                obj.FeatureBoundary,
                Part.Face(w),
                base.Shape,
                self.stock.Shape,
                obj.RespectFeatureHoles,
                obj.ExtensionLengthDefault.Value,
            )  # featureBoundary, face, baseShape, stockShape
            rawFaces.append(fc)
        else:
            PathLog.error("Wire not closed.")
            Part.show(ew, "OpenWireError")
            openWires.append(flattenOpenWire(ew))


def flattenOpenWire(wire, matchHeight=False):
    # Part.show(w, "WireToFlatten")
    wBB = wire.BoundBox
    face = PathGeom.makeBoundBoxFace(wBB, 2.0, wBB.ZMin - 2.0)
    flat = face.makeParallelProjection(wire, FreeCAD.Vector(0.0, 0.0, 1.0))
    if len(flat.Edges) == 0:
        return None
    if matchHeight:
        flat.translate(FreeCAD.Vector(0.0, 0.0, wBB.ZMin - flat.BoundBox.ZMin))
    else:
        flat.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - flat.BoundBox.ZMin))
    return flat


def applyFeatureBoundary(
    featureBoundary, face, baseShape, stockShape, respectFeatureHoles, extLength
):
    if featureBoundary == "Boundbox":
        newFace = PathGeom.makeBoundBoxFace(face.BoundBox, zHeight=face.BoundBox.ZMin)
    elif featureBoundary == "Stock":
        newFace = PathTargetBuildUtils.getCrossSectionFace(stockShape)
        newFace.translate(
            FreeCAD.Vector(0.0, 0.0, face.BoundBox.ZMin - stockShape.BoundBox.ZMin)
        )
    elif featureBoundary == "Waterline":
        newFace = getWaterlineFace(stockShape, baseShape, face)
        if newFace is None:
            PathLog.error("Waterline creation failed.  Using 'Feature' boundary.")
            newFace = face.copy()
    elif featureBoundary == "WaterlineExt":
        newFace = getWaterlineFace(stockShape, baseShape, face, extLength)
        if newFace is None:
            PathLog.error("Waterline creation failed.  Using 'Feature' boundary.")
            newFace = face.copy()
    elif featureBoundary == "StockExt":
        # wFace = PathGeom.makeBoundBoxFace(face.BoundBox, zHeight=face.BoundBox.ZMin)
        stockFace = PathTargetBuildUtils.getCrossSectionFace(stockShape)
        stockFace.translate(
            FreeCAD.Vector(0.0, 0.0, face.BoundBox.ZMin - stockFace.BoundBox.ZMin)
        )
        newFace = PathUtils.getOffsetArea(stockFace, extLength)
    elif featureBoundary == "FeatureExt":
        newFace = PathUtils.getOffsetArea(face, extLength)
    else:
        newFace = face.copy()

    # Part.show(newFace, "NewFace")

    if not respectFeatureHoles or len(face.Wires) == 1:
        return newFace

    PathLog.info("Respecting feature holes")
    rawInnerWires = [w.copy() for w in face.Wires[1:]]
    flatInnerWiresRaw = CombineRegions._flattenWires(rawInnerWires)
    extrusions = []
    for fiw in flatInnerWiresRaw:
        fiw.translate(
            FreeCAD.Vector(0.0, 0.0, newFace.BoundBox.ZMin - 1.0 - fiw.BoundBox.ZMin)
        )
        fc = Part.Face(fiw)
        extrusions.append(fc.extrude(FreeCAD.Vector(0.0, 0.0, 2.0)))
    extHoles = Part.makeCompound(extrusions)
    return newFace.cut(extHoles)


# Waterline extension face generation function
def getWaterlineFace(stockShape, baseShape, face, extLength=0.0):
    # Get stock cross-section and translate to face height
    if extLength != 0.0:
        cs = PathTargetBuildUtils.getCrossSectionFace(stockShape)
        stockCS = PathUtils.getOffsetArea(cs, extLength)
    else:
        stockCS = PathTargetBuildUtils.getCrossSectionFace(stockShape)
    stockCS.translate(
        FreeCAD.Vector(0.0, 0.0, face.BoundBox.ZMin - stockCS.BoundBox.ZMin)
    )

    # cut CS by base shape
    cutFace = stockCS.cut(baseShape)
    # fuse face with cut, removing splitters
    rawFace = cutFace.fuse(face.copy())
    connected = PathGeom.combineConnectedShapes(rawFace.Faces)
    # cycle through faces, identifying one common with face
    for f in connected:
        f.translate(FreeCAD.Vector(0.0, 0.0, face.BoundBox.ZMin - f.BoundBox.ZMin))
        cmn = f.common(face)
        if PathGeom.isRoughly(cmn.Area, face.Area):
            negative = stockCS.cut(f)
            return stockCS.cut(negative)

    return None


def getDrillableTargets(obj, ToolDiameter=None, vector=FreeCAD.Vector(0, 0, 1)):
    """
    Returns a list of tuples for drillable subelements from the given object
    [(obj,'Face1'),(obj,'Face3')]

    Finds cylindrical faces that are larger than the tool diameter (if provided) and
    oriented with the vector.  If vector is None, all drillables are returned

    """

    # shp = obj.Shape
    shp = obj

    results = []
    for i in range(1, len(shp.Faces)):
        fname = "Face{}".format(i)
        PathLog.debug(fname)
        # candidate = obj.getSubObject(fname)
        candidate = obj.getElement(fname)

        if not isinstance(candidate.Surface, Part.Cylinder):
            continue

        try:
            drillable = drillableLib.isDrillable(
                shp, candidate, tooldiameter=ToolDiameter, vector=vector
            )
            PathLog.debug("fname: {} : drillable {}".format(fname, drillable))
        except Exception as e:
            PathLog.debug(e)
            continue

        if drillable:
            # results.append((obj, fname))
            results.append(fname)

    return results


drillableLib.getDrillableTargets = getDrillableTargets


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
