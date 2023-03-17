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

import Part
import Path
import FreeCAD
import datetime
import Path.Log as PathLog
import Path.Geom as PathGeom
import PathScripts.PathUtils as PathUtils
import Ops.PathOp2 as PathOp2
import Generators.PathStrategySlicing as PathStrategySlicing
import Generators.PathStrategyClearing as PathStrategyClearing

from PySide import QtCore


__title__ = "Path Clearing Operation"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Class and implementation of Clearing operation."


PathStrategyAdaptive = PathStrategyClearing.PathStrategyAdaptive

PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
translate = FreeCAD.Qt.translate


class ObjectClearing(PathOp2.ObjectOp2):
    """Proxy object for Clearing operation."""

    @classmethod
    def propDefinitions(cls):
        """propDefinitions() ... returns a tuples.
        Each tuple contains property declaration information in the
        form of (prototype, name, section, tooltip)."""
        definitions = [
            # Operation properties
            (
                "App::PropertyBool",
                "UseMesh",
                "Operation",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property", "Set to True to use meshed shapes."
                ),
            ),
            (
                "App::PropertyBool",
                "Cut3DPocket",
                "Operation",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Enable to cut a 3D pocket instead of the standard 2D pocket",
                ),
            ),
            (
                "App::PropertyBool",
                "UseOCL",
                "Operation",
                QtCore.QT_TRANSLATE_NOOP("App::Property", "Enable to use OpenCAM Lib"),
            ),
            (
                "App::PropertyBool",
                "MakeRestShape",
                "Operation",
                QtCore.QT_TRANSLATE_NOOP("App::Property", "Enable to use OpenCAM Lib"),
            ),
            # Path option properties
            (
                "App::PropertyEnumeration",
                "CutMode",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "The clearing mode to be used: Single-pass or Multi-pass.",
                ),
            ),
            (
                "App::PropertyEnumeration",
                "CutDirection",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "The direction that the toolpath should go around the part: Climb or Conventional.",
                ),
            ),
            (
                "App::PropertyDistance",
                "MaterialAllowance",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Extra offset to apply to the operation. Direction is operation dependent.",
                ),
            ),
            (
                "App::PropertyDistance",
                "StepOver",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Percent of cutter diameter to step over on each pass",
                ),
            ),
            (
                "App::PropertyFloat",
                "CutPatternAngle",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property", "Angle of the zigzag pattern"
                ),
            ),
            (
                "App::PropertyEnumeration",
                "CutPattern",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP("App::Property", "Clearing pattern to use"),
            ),
            (
                "App::PropertyBool",
                "MinTravel",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP("App::Property", "Use 3D Sorting of Path"),
            ),
            (
                "App::PropertyBool",
                "KeepToolDown",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property", "Attempts to avoid unnecessary retractions."
                ),
            ),
            (
                "App::PropertyBool",
                "CutPatternReversed",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Reverse the cut order of the stepover paths. For circular cut patterns, begin at the outside and work toward the center.",
                ),
            ),
            (
                "App::PropertyBool",
                "ProfileOutside",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property", "Profile outside of target shape."
                ),
            ),
            (
                "App::PropertyVectorDistance",
                "PatternCenterCustom",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property", "Set the start point for the cut pattern."
                ),
            ),
            (
                "App::PropertyEnumeration",
                "PatternCenterAt",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Choose location of the center point for starting the cut pattern.",
                ),
            ),
            (
                "App::PropertyBool",
                "UseComp",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property", "Make True, if using Cutter Radius Compensation"
                ),
            ),
            # OCL Properties
            (
                "App::PropertyDistance",
                "SampleInterval",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Set the sampling resolution. Smaller values quickly increase processing time.",
                ),
            ),
            (
                "App::PropertyDistance",
                "DepthOffset",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Set the Z-axis depth offset from the target surface.",
                ),
            ),
            (
                "App::PropertyDistance",
                "AngularDeflection",
                "MeshConversion",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Smaller values yield a finer, more accurate mesh. Smaller values increase processing time a lot.",
                ),
            ),
            (
                "App::PropertyDistance",
                "LinearDeflection",
                "MeshConversion",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Smaller values yield a finer, more accurate mesh. Smaller values do not increase processing time much.",
                ),
            ),
            # Debug Properties
            (
                "Part::PropertyPartShape",
                "CutPatternShape",
                "Debug",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Debug property that stores copy of the cut pattern shape used in the clearing strategy for this operation.",
                ),
            ),
            (
                "App::PropertyString",
                "AreaParams",
                "Debug",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Debug property that stores parameters passed to Path.Area() for this operation.",
                ),
            ),
            (
                "App::PropertyString",
                "PathParams",
                "Debug",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Debug property that stores parameters passed to Path.fromShapes() for this operation.",
                ),
            ),
            (
                "App::PropertyBool",
                "ShowDebugShapes",
                "Debug",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Show the temporary path construction objects when module is in DEBUG mode.",
                ),
            ),
            (
                "App::PropertyBool",
                "ShowCutPattern",
                "Debug",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Toggle True to show cut pattern in object tree.",
                ),
            ),
            (
                "App::PropertyBool",
                "ShowRemovalShape",
                "Debug",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Toggle True to show removal shape in object tree.",
                ),
            ),
        ]
        definitions.extend(
            PathStrategyAdaptive.StrategyAdaptive.adaptivePropertyDefinitions()
        )
        return definitions

    @classmethod
    def propEnumerations(cls, dataType="data"):
        """propEnumerations() ... returns a dictionary of enumeration lists
        for the operation's enumeration type properties."""
        # Enumeration lists for App::PropertyEnumeration properties
        enums = {
            "CutMode": [
                (translate("Path", "Single-pass"), "Single-pass"),
                (translate("Path", "Multi-pass"), "Multi-pass"),
            ],
            "CutDirection": [
                (translate("Path", "Climb"), "Climb"),
                (translate("Path", "Conventional"), "Conventional"),
            ],
            "CutPattern": [
                (translate("Path", "Adaptive"), "Adaptive"),
                (translate("Path", "Circular"), "Circular"),
                (translate("Path", "Circular Zig-Zag"), "CircularZigZag"),
                (translate("Path", "Grid"), "Grid"),
                (translate("Path", "Line"), "Line"),
                (translate("Path", "Line Offset"), "LineOffset"),
                (translate("Path", "Offset"), "Offset"),
                (translate("Path", "Profile"), "Profile"),
                (translate("Path", "Multi-Profile"), "MultiProfile"),
                (translate("Path", "Spiral"), "Spiral"),
                (translate("Path", "Triangle"), "Triangle"),
                (translate("Path", "Zig-Zag"), "ZigZag"),
                (translate("Path", "Zig-Zag Offset"), "ZigZagOffset"),
            ],
            "PatternCenterAt": [
                (translate("Path", "Center Of Mass"), "CenterOfMass"),
                (translate("Path", "Center Of Bound Box"), "CenterOfBoundBox"),
                (translate("Path", "X-min Y-min"), "XminYmin"),
                (translate("Path", "Custom"), "Custom"),
            ],
        }

        for (k, v,) in PathStrategyAdaptive.StrategyAdaptive.propEnumerations(
            dataType="raw"
        ).items():
            enums[k] = v

        if dataType == "raw":
            return enums

        data = []
        idx = 0 if dataType == "translated" else 1

        Path.Log.debug(enums)

        for k, v in enumerate(enums):
            data.append((v, [tup[idx] for tup in enums[v]]))
        Path.Log.debug(data)

        return data

    @classmethod
    def propDefaults(cls, obj, job):
        """propDefaults(obj, job) ... returns a dictionary of default values
        for the operation's properties."""
        defaults = {
            "CutMode": "Single-pass",
            "CutDirection": "Conventional",
            "MaterialAllowance": 0.0,
            "StepOver": 95.0,
            "CutPatternAngle": 0.0,
            "CutPattern": "Line",
            "UseComp": True,
            "MinTravel": False,
            "KeepToolDown": False,
            "Cut3DPocket": False,
            "CutPatternReversed": False,
            "ProfileOutside": True,
            "PatternCenterCustom": FreeCAD.Vector(0.0, 0.0, 0.0),
            "PatternCenterAt": "CenterOfBoundBox",
            "AreaParams": "",
            "PathParams": "",
            "UseOCL": False,
            "MakeRestShape": False,
            "SampleInterval": 1.0,
            "AngularDeflection": 0.25,  # AngularDeflection is unused
            "LinearDeflection": 0.001,  # Reasonable compromise between speed & precision
            "DepthOffset": 0.0,
            "ShowDebugShapes": False,
            "ShowCutPattern": False,
            "ShowRemovalShape": False,
            "UseMesh": False,
        }
        for (k, v,) in PathStrategyAdaptive.StrategyAdaptive.adaptivePropertyDefaults(
            obj, job
        ).items():
            defaults[k] = v
        return defaults

    # Regular methods
    def opFeatures(self, obj):
        """opFeatures(obj) ... returns the base features supported by all Path.Area based operations."""
        return (
            PathOp2.FeatureTool
            | PathOp2.FeatureHeightsDepths
            | PathOp2.FeatureStepDown
            | PathOp2.FeatureFinishDepth
            | PathOp2.FeatureStartPoint
            | PathOp2.FeatureCoolant
        )

    def initOperation(self, obj):
        """initOperation(obj) ... implement to extend class `__init__()` contructor,
        like create additional properties."""
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        self.targetShapes = []

    def opPropertyDefinitions(self):
        return ObjectClearing.propDefinitions()

    def opPropertyEnumerations(self):
        # Return list of tuples (prop, enumeration_list) as default
        return ObjectClearing.propEnumerations()

    def opPropertyDefaults(cls, obj, job):
        return ObjectClearing.propDefaults(obj, job)

    def opSetDefaultValues(self, obj, job):
        """opSetDefaultValues(obj) ... base implementation, do not overwrite.
        The base implementation sets the depths and heights based on the
        opShapeForDepths() return value."""
        PathLog.debug("opSetDefaultValues(%s, %s)" % (obj.Label, job.Label))

        targetShps = [None]
        for o in job.Operations.Group:
            if o.Name.startswith("TargetShape"):
                targetShps.append(o)
            elif hasattr(o, "TargetShape") and o.TargetShape is not None:
                targetShps.append(o.TargetShape)
        obj.TargetShape = targetShps[-1]

        shape = None
        try:
            shape = self.opShapeForDepths(obj, job)
        except Exception as ee:  # pylint: disable=broad-except
            PathLog.error(ee)

        # Set initial start and final depths
        if shape is None:
            PathLog.debug("shape is None")
            startDepth = 1.0
            finalDepth = 0.0
        else:
            bb = job.Stock.Shape.BoundBox
            startDepth = bb.ZMax
            finalDepth = bb.ZMin

        obj.OpStartDepth.Value = startDepth
        obj.OpFinalDepth.Value = finalDepth

    def opSetEditorModes(self, obj):
        """opSetEditorModes(obj, porp) ... Process operation-specific changes to properties visibility."""

        # Always hidden
        if PathLog.getLevel(PathLog.thisModule()) != 4:
            obj.setEditorMode("ShowDebugShapes", 2)
        # obj.setEditorMode('JoinType', 2)
        # obj.setEditorMode('MiterLimit', 2)
        hide = (
            False
            if hasattr(obj, "CutPattern") and obj.CutPattern == "Adaptive"
            else True
        )
        PathStrategyAdaptive.StrategyAdaptive.adaptiveSetEditorModes(obj, hide)

    def opShapeForDepths(self, obj, job):
        """opShapeForDepths(obj) ... returns the shape used to make an initial calculation for the depths being used.
        The default implementation returns the job's Base.Shape"""
        if obj.TargetShape:
            return obj.TargetShape
        elif job:
            if job.Stock:
                PathLog.debug(
                    "job=%s base=%s shape=%s" % (job, job.Stock, job.Stock.Shape)
                )
                return job.Stock.Shape
            else:
                PathLog.warning(
                    translate("PathAreaOp", "job %s has no Base.") % job.Label
                )
        else:
            PathLog.warning(
                translate("PathAreaOp", "no job for op %s found.") % obj.Label
            )
        return None

    def opUpdateDepths(self, obj):
        # PathLog.debug("opUpdateDepths()")

        if obj.UseOCL:
            if obj.TargetShape is not None:
                obj.OpFinalDepth.Value = obj.TargetShape.FinalDepth.Value

        if obj.TargetShape is not None:
            # obj.setExpression(
            #    "OpStockZMax", "{} mm".format(obj.TargetShape.StartDepth.Value)
            # )
            # obj.setExpression(
            #    "OpStartDepth", "{} mm".format(obj.TargetShape.StartDepth.Value)
            # )
            # obj.setExpression(
            #    "OpFinalDepth", "{} mm".format(obj.TargetShape.FinalDepth.Value)
            # )
            # obj.OpStartDepth = "{} mm".format(obj.TargetShape.StartDepth.Value)
            # obj.OpFinalDepth = "{} mm".format(obj.TargetShape.FinalDepth.Value)
            obj.OpStartDepth = obj.TargetShape.StartDepth
            obj.OpFinalDepth = obj.TargetShape.FinalDepth

        """if obj.UseOCL:
            zMins = []
            if not hasattr(obj, "Base") or not obj.Base:
                zMins = [
                    min([base.Shape.BoundBox.ZMin for base in self.job.Model.Group])
                ]
            else:
                for base, subsList in obj.Base:
                    zMins.append(
                        min([base.Shape.getElement(s).BoundBox.ZMin for s in subsList])
                    )
            obj.OpFinalDepth.Value = min(zMins)
            PathLog.debug(
                "Cut 3D pocket update final depth: {} mm\n".format(
                    obj.OpFinalDepth.Value
                )
            )
        # Eif"""
        pass

    def opOnDocumentRestored(self, obj):
        """opOnDocumentRestored(obj) ... implement if an op needs special handling."""
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        if not hasattr(self, "targetShapes"):
            self.targetShapes = []

    def buildRestShape(self, removalShape, useShape, obj):
        PathLog.info("buildRestShape()")
        cont = True
        # Make and save REST shape
        if len(removalShape.SubShapes) == 1:
            adjustedShape = getHeightAdjustedShape(useShape, obj.StartDepth.Value)
            rawRestShape = adjustedShape.cut(removalShape.SubShapes)
        elif len(removalShape.SubShapes) > 1:
            adjustedShape = getHeightAdjustedShape(useShape, obj.StartDepth.Value)
            rawRestShape = adjustedShape.cut(removalShape.SubShapes[0])
            for ss in removalShape.SubShapes[1:]:
                cut = rawRestShape.cut(ss)
                rawRestShape = cut
        elif obj.UseOCL:
            rawRestShape = useShape.cut(removalShape)
        else:
            cont = False
            PathLog.error("restShapeEnabled error.  Showing removalShape.")
            # Part.show(removalShape, "RemovalShape")
        # Part.show(rawRestShape, "RawRestShape")

        if cont:
            return cleanVolume(rawRestShape)

        return None

    def getClearingPaths(self, obj, baseObj, shape, startPoint):
        PathLog.debug("getClearingPaths()")

        # Part.show(shape, "Shape")
        rotatedStockShape = self.getRotatedShape(obj.TargetShape, self.job.Stock.Shape)
        slices = sliceShape(shape, [d for d in self.depthparams])
        noAdaptivePreview = True

        PathLog.debug(f"slices present: {True if slices else False}")

        strategy = PathStrategyClearing.StrategyClearVolume(
            self,
            baseObj,
            shape,
            obj.DepthOffset.Value,
            obj.PatternCenterAt,
            obj.PatternCenterCustom,
            obj.CutPatternReversed,
            obj.CutPatternAngle,
            obj.CutPattern,
            obj.CutDirection,
            obj.StepOver.Value if hasattr(obj.StepOver, "Value") else obj.StepOver,
            obj.MaterialAllowance.Value,
            obj.ProfileOutside,
            obj.MinTravel,
            obj.KeepToolDown,
            obj.ToolController,
            startPoint,
            self.depthparams,
            self.job.GeometryTolerance.Value,
        )

        if not baseObj:
            PathLog.info("no baseObj in PathClearing")
        strategy.baseShape = baseObj.Shape
        strategy.rotatedShape = self.getRotatedShape(obj.TargetShape, baseObj.Shape)
        strategy.rotatedStock = self.getRotatedShape(
            obj.TargetShape, self.job.Stock.Shape
        )
        strategy.rotations = self.atfRotations
        strategy.useMesh = obj.UseMesh

        if obj.CutPattern == "Adaptive":
            PathLog.debug("Passing Adaptive-specific values to clearing strategy.")
            stockType = (
                "CreateCylinder"
                if hasattr(self.stock, "StockType")
                and self.stock.StockType == "CreateCylinder"
                else ""
            )
            # set adaptive-dependent attributes
            strategy.setAdaptiveAttributes(
                obj.OperationType,
                obj.CutSide,
                obj.DisableHelixEntry,
                obj.ForceInsideOut,
                obj.LiftDistance.Value,
                obj.FinishingProfile,
                obj.HelixAngle.Value,
                obj.HelixConeAngle.Value,
                obj.UseHelixArcs,
                obj.HelixDiameterLimit.Value,
                obj.KeepToolDownRatio.Value,
                obj.Stopped,
                obj.StopProcessing,
                obj.Tolerance,
                stockType,
                rotatedStockShape,
                self.job,
                obj.AdaptiveOutputState,
                obj.AdaptiveInputState,
                None if noAdaptivePreview else getattr(obj, "ViewObject", None),
            )

        # OCL dependencies
        strategy.useOCL = obj.UseOCL
        strategy.job = self.job

        # Transfer debug status
        strategy.isDebug = self.isDebug

        if obj.UseOCL and obj.KeepToolDown:
            # strategy.safeBaseShape = obj.Base[0][
            #    0
            # ].Shape  # Set safe base shape used to check
            PathLog.warning(
                "MIGHT need to set strategy.safeBaseShape in PathClearing module if OCL requires it."
            )

        if obj.UseOCL:
            success = strategy.executeOCL(baseObj, obj)
        else:
            success = strategy.execute()

        if success:
            # Transfer some values from strategy class back to operation
            if obj.PatternCenterAt != "Custom" and strategy.centerOfPattern is not None:
                obj.PatternCenterCustom = strategy.centerOfPattern
            self.endVector = strategy.endVector
            obj.AreaParams = strategy.areaParams  # save area parameters
            obj.PathParams = strategy.pathParams  # save path parameters
            # if getsim:
            #    sims.append(strategy.simObj)
            return (strategy.commandList, strategy.pathGeometry)
        else:
            PathLog.error("strategy.execute() FAILED")
            return None

    def getTargetShape(self, obj, isPreview=False):
        """getTargetShape(obj) ... returns envelope for all base shapes or wires for Arch.Panels."""
        PathLog.info("PathClearing.getTargetShape()")
        PathLog.track()
        baseShapes = []
        shape_types = ["2D Extrusion", "3D Volume"]
        if obj.UseOCL:
            shape_types = ["2D Area"]
        # Identify working shapes for Profile operation
        if obj.TargetShape is not None:
            PathLog.info("... Using TargetShape provided! ...")
            baseShapes = obj.TargetShape.Proxy.getTargetGeometry(
                obj.TargetShape, shapeTypes=shape_types
            )
        else:
            PathLog.error("Set TargetShape for operation.")

        return baseShapes

    def opExecute(self, obj, getsim=False):  # pylint: disable=arguments-differ
        """opExecute(obj, getsim=False) ... implementation of Path.Area ops.
        determines the parameters for _buildPathArea().
        """
        PathLog.track()
        PathLog.warning("opExecute()")

        pathGeometry = []
        self.targetShapes = []
        removalShapes = []
        restShapes = []
        pathGeometryLists = []
        startTime = datetime.datetime.now()
        self.endVector = None
        restShapeEnabled = (
            True if obj.StepOver.Value < 99.9 and obj.MakeRestShape else False
        )

        # Set start point
        startPoint = None
        if obj.UseStartPoint:
            startPoint = obj.StartPoint

        if obj.UseComp:
            self.commandlist.append(
                Path.Command(
                    "(Compensated Tool Path. Diameter: " + str(self.radius * 2) + ")"
                )
            )
        else:
            self.commandlist.append(Path.Command("(Uncompensated Tool Path)"))

        # Initiate depthparams and calculate operation heights for operation
        finish_step = obj.FinishDepth.Value if hasattr(obj, "FinishDepth") else 0.0
        self.depthparams = PathUtils.depth_params(
            clearance_height=obj.ClearanceHeight.Value,
            safe_height=obj.SafeHeight.Value,
            start_depth=obj.StartDepth.Value,
            step_down=obj.StepDown.Value,
            z_finish_step=finish_step,
            final_depth=obj.FinalDepth.Value,
            user_depths=None,
        )
        depths = [d for d in self.depthparams]
        depths.insert(0, self.depthparams.start_depth)

        shapes = getWorkingShapes(obj.TargetShape, obj.CutSide)

        # Apply any rotation for object
        self.commandlist.extend(self._getRotationCommands(obj))

        shpCnt = 0
        # process each shape provided
        for shape, isHole, baseObj in shapes:
            shpCnt += 1
            useShape = shape
            PathLog.info(f"Processing shape # {shpCnt}")
            # targetShapes.append(shape)

            ###############################
            # Calculate path commands
            commands_pathGeom_tuple = self.getClearingPaths(
                obj, baseObj, shape, startPoint
            )
            if commands_pathGeom_tuple is None:
                break
            # Save path commands to operation command list
            self.commandlist.extend(commands_pathGeom_tuple[0])
            # Save path
            pathGeometryLists.append(commands_pathGeom_tuple[1])
            pathGeom = Part.makeCompound(commands_pathGeom_tuple[1])
            pathGeometry.append(pathGeom)
            PathLog.debug("Path geometry saved.")

            # Show path geometry (wires)
            # Part.show(Part.makeCompound(commands_pathGeom_tuple[1]), "PathGeometry")

            if obj.UseOCL:
                useShape = shape.extrude(
                    FreeCAD.Vector(
                        0.0, 0.0, obj.StartDepth.Value - obj.FinalDepth.Value
                    )
                )
                useShape.translate(
                    FreeCAD.Vector(
                        0.0, 0.0, obj.FinalDepth.Value - useShape.BoundBox.ZMin
                    )
                )

            if obj.MakeRestShape:
                # Make and save removal shape
                # removalShape = makeRemovalShape(pathGeom, obj.ToolController, depths)
                removalShape = makeRemovalShape_new(
                    commands_pathGeom_tuple[1], obj.ToolController, depths
                )
                if removalShape and obj.MakeRestShape:
                    removalShapes.append(removalShape)
                    # Part.show(removalShape, "RemovalShape")
                else:
                    PathLog.error("No removalShape returned")
                    # Part.show(Part.makeCompound(commands_pathGeom_tuple[1]), "PathGeometry")
                    # Part.show(useShape, "TargetShape")

            if restShapeEnabled and removalShape:
                # restShape = self.buildRestShape(removalShape, useShape, obj)
                restShape = None
                if restShape is not None:
                    restShapes.append(restShape)
                    self.targetShapes.append((restShape, baseObj, "pathClearing"))
                    # Part.show(restShape, "RestShape")

            ###############################

            if self.endVector is not None and len(self.commandlist) > 1:
                # self.endVector[2] = obj.ClearanceHeight.Value
                self.commandlist.append(
                    Path.Command(
                        "G0", {"Z": obj.ClearanceHeight.Value, "F": self.vertRapid}
                    )
                )
        # Efor

        # Reset rotation
        self.commandlist.extend(self._getRotationCommands(obj, reverse=True))

        if len(self.commandlist) == 0:
            PathLog.debug("No path commands produced.")
            PathLog.error("No path commands produced.")

        if removalShapes:
            PathLog.info("removalShapes is True")
            obj.RemovalShape = Part.makeCompound(removalShapes)
            if obj.ShowRemovalShape:
                PathLog.info("Showing removal shape...")
                name = "{}_Removal_Shape".format(obj.Name)
                if FreeCAD.ActiveDocument.getObject(name):
                    FreeCAD.ActiveDocument.removeObject(name)
                ors = FreeCAD.ActiveDocument.addObject("Part::Feature", name)
                ors.Shape = Part.makeCompound(removalShapes)
                ors.purgeTouched()
            # self.removalShapes = removalShapes
        else:
            PathLog.info("No removal shapes in PathClearing.")
        obj.ShowRemovalShape = False

        if pathGeometry:
            obj.CutPatternShape = Part.makeCompound(pathGeometry)

        if restShapeEnabled:
            if restShapes:
                PathLog.info("Rest Shape exists.")
                obj.Shape = Part.makeCompound(restShapes)
        else:
            PathLog.warning(
                "Rest shape disabled due to 100% step over, or Make Rest Shape property disabled."
            )

        if obj.ShowCutPattern and obj.CutPatternShape:
            showPattern(obj)

        printElapsedTime(startTime)

    # Public methods
    def getTargetGeometry(self, obj, shapeTypes=["3D Volume"]):
        PathLog.info("PathClearing.getTargetGeometry()")
        if "3D Volume" not in shapeTypes:
            PathLog.error("Incorrect target shape type.")
            return list()

        if not obj.Shape:
            PathLog.error("No obj.Shape to return")
            # self.opExecute(obj)
            return list()

        if not self.targetShapes:
            PathLog.error("No self.targetShapes to return")
            self.execute(obj)

        return self.targetShapes


# Eclass
def getWorkingShapes(targetShapeObj, cutSide):
    shapes = []
    if targetShapeObj:
        for s in targetShapeObj.Shape.Solids:
            isHole = True if cutSide == "Inside" else False
            shp = s.copy()
            tup = shp, isHole, targetShapeObj
            shapes.append(tup)

    # Sort operations
    if len(shapes) > 1:
        jobs = []
        for s in shapes:
            shp = s[0]
            jobs.append({"x": shp.BoundBox.XMax, "y": shp.BoundBox.YMax, "shape": s})

        jobs = PathUtils.sort_locations(jobs, ["x", "y"])

        shapes = [j["shape"] for j in jobs]

    return shapes


def makeRemovalShape(pathGeom, ToolController, depths):
    removalShapes = []
    toolDiameter = (
        ToolController.Tool.Diameter.Value
        if hasattr(ToolController.Tool.Diameter, "Value")
        else float(ToolController.Tool.Diameter)
    )

    subShapes = [ss for ss in pathGeom.SubShapes]
    subShapes.reverse()

    for comp in subShapes:
        top = None
        bottom = comp.BoundBox.ZMin
        for i in range(1, len(depths)):
            d = depths[i]
            if PathGeom.isRoughly(bottom, d):
                top = depths[i - 1]

        if top is not None:
            # Part.show(comp, "subShapeComp")
            pathArea = PathStrategySlicing.wiresToPathFace(comp.Wires, toolDiameter)
            pathArea.translate(FreeCAD.Vector(0.0, 0.0, comp.BoundBox.ZMin))
            removalShapes.append(
                # pathArea.extrude(FreeCAD.Vector(0.0, 0.0, top - bottom + 0.00001))
                pathArea.extrude(FreeCAD.Vector(0.0, 0.0, top - bottom))
            )

    return Part.makeCompound(removalShapes)


def makeRemovalShape_new_orig(pathGeomList, ToolController, depths):
    removalShapes = []
    toolDiameter = (
        ToolController.Tool.Diameter.Value
        if hasattr(ToolController.Tool.Diameter, "Value")
        else float(ToolController.Tool.Diameter)
    )

    pathGeomList.reverse()

    cnt = 0
    for comp in pathGeomList:
        cnt += 1
        top = None
        bottom = comp.BoundBox.ZMin
        for i in range(1, len(depths)):
            d = depths[i]
            if PathGeom.isRoughly(bottom, d):
                top = depths[i - 1]

        if top is not None:
            # Part.show(comp, "subShapeComp")
            pathArea = PathStrategySlicing.wiresToPathFace(comp.Wires, toolDiameter)
            pathArea.translate(FreeCAD.Vector(0.0, 0.0, comp.BoundBox.ZMin - 0.00001))
            # Part.show(pathArea, "PathArea_" + str(cnt))
            removalShapes.append(
                # pathArea.extrude(FreeCAD.Vector(0.0, 0.0, top - bottom + 0.00001))
                pathArea.extrude(FreeCAD.Vector(0.0, 0.0, top - bottom + 0.00002))
            )

    return Part.makeCompound(removalShapes)


def makeRemovalShape_new(pathGeomList, ToolController, depths):
    removalShapes = []
    toolDiameter = (
        ToolController.Tool.Diameter.Value
        if hasattr(ToolController.Tool.Diameter, "Value")
        else float(ToolController.Tool.Diameter)
    )

    bottomList = [
        (i, pathGeomList[i].BoundBox.ZMin) for i in range(0, len(pathGeomList))
    ]
    bottomList.reverse()

    cnt = 0
    for idx, btm in bottomList:
        cnt += 1
        top = None
        for i in range(1, len(depths)):
            d = depths[i]
            if PathGeom.isRoughly(btm, d):
                top = depths[i - 1]

        if top is not None:
            comp = pathGeomList[idx]
            pathArea = PathStrategySlicing.wiresToPathFace(comp.Wires, toolDiameter)
            pathArea.translate(FreeCAD.Vector(0.0, 0.0, btm - 0.00001))
            # Part.show(pathArea, "PathArea_" + str(cnt))
            removalShapes.append(
                # pathArea.extrude(FreeCAD.Vector(0.0, 0.0, top - bottom + 0.00001))
                pathArea.extrude(FreeCAD.Vector(0.0, 0.0, top - btm + 0.00002))
            )

    if removalShapes:
        return Part.makeCompound(removalShapes)

    return None


def sliceShape(shape, depths):
    """sliceShape(shape, depths) ..."""
    PathLog.debug(f"sliceShape(shape, depths: {depths})")

    if len(depths) == 0:
        PathLog.error("No depth parameters")
        return list()

    # Verify input shape has volume (is an envelope)
    if hasattr(shape, "Volume") and PathGeom.isRoughly(shape.Volume, 0.0):
        PathLog.error("StrategyClearing: No volume in working shape.")
        return list()

    slices = PathStrategySlicing.sliceShape(shape, depths, None, True)

    if not slices:
        PathLog.debug("sliceShape() No slices returned.")
        return list()

    # for s in slices:
    #    Part.show(s, "slice")

    return slices


def printElapsedTime(startTime):
    # Calculate and print elapsed time for operation
    elapsed = datetime.datetime.now() - startTime
    times = [
        "%02d day  " % (elapsed.days),
        "%02d hr.  " % (elapsed.seconds / 3600),
        "%02d min.  " % (elapsed.seconds / 60 % 60),
        "%02d sec.  " % (elapsed.seconds % 60),
    ]
    timeTextLabel = "Elapsed operation time: "
    timeText = ""
    prnt = False
    for t in times:
        if "00" not in t:
            prnt = True
        if prnt:
            timeText += t
    if timeText:
        print(timeTextLabel + timeText)
    else:
        print(timeTextLabel + " < 1.0 second")


def showPattern(obj):
    obj.ShowCutPattern = False  # Reset boolean
    Part.show(obj.CutPatternShape)
    shape = FreeCAD.ActiveDocument.ActiveObject
    shape.Label = obj.Name + "_Pattern"
    shape.purgeTouched()


def cleanVolume(volume):
    vbb = volume.BoundBox
    bbFace = PathGeom.makeBoundBoxFace(vbb, offset=5.0)
    bbExt = bbFace.extrude(FreeCAD.Vector(0.0, 0.0, vbb.ZLength))
    bbExt.translate(FreeCAD.Vector(0.0, 0.0, vbb.ZMin))
    negative = bbExt.cut(volume)
    negative.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - negative.BoundBox.ZMin))
    # Part.show(negative, "Negative")

    cleanFace = PathGeom.makeBoundBoxFace(vbb, offset=10.0)
    cleanExt = cleanFace.extrude(FreeCAD.Vector(0.0, 0.0, vbb.ZLength + 2.0))
    cleanExt.translate(FreeCAD.Vector(0.0, 0.0, -1.0))
    clean = negative.cut(cleanExt)
    clean.translate(FreeCAD.Vector(0.0, 0.0, vbb.ZMin))
    if PathGeom.isRoughly(clean.Volume, 0.0):
        # Cleaning failed
        return volume
    return clean


def getHeightAdjustedShape(shape, startDepth):
    bbFace = PathGeom.makeBoundBoxFace(shape.BoundBox, offset=5.0)
    faceExt = bbFace.extrude(FreeCAD.Vector(0.0, 0.0, shape.BoundBox.ZLength + 1.0))
    faceExt.translate(FreeCAD.Vector(0.0, 0.0, startDepth - faceExt.BoundBox.ZMin))
    return shape.cut(faceExt).copy()


def SetupProperties():
    setup = []
    setup.extend([tup[1] for tup in ObjectClearing.propDefinitions()])
    setup.extend(
        [
            tup[1]
            for tup in PathStrategyAdaptive.StrategyAdaptive.adaptivePropertyDefinitions()
        ]
    )
    return setup


def Create(name, obj=None, parentJob=None):
    """Create(name) ... Creates and returns a Clearing operation."""
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectClearing(obj, name, parentJob)
    return obj
