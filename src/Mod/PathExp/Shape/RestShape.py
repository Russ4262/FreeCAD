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
import Macros.Macro_AlignToFeature as AlignToFeature
import Generators.PathStrategySlicing as PathStrategySlicing
import Path.Geom as PathGeom
import PathScripts.PathUtils as PathUtils

__doc__ = "Class and implementation of a Target Shape."


if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


translate = FreeCAD.Qt.translate


class RestShape(PathOp2.ObjectOp2):
    def opFeatures(self, obj):
        """opFeatures(obj) ... returns the OR'ed list of features used and supported by the operation.
        The default implementation returns "FeatureTool | FeatureDepths | FeatureHeights | FeatureStartPoint"
        Should be overwritten by subclasses."""
        return 0

    def initOperation(self, obj):
        """initOperation(obj) ... implement to create additional properties.
        Should be overwritten by subclasses."""
        obj.setEditorMode("Shape", 1)  # read-only

        for n in self.propertyEnumerations():
            setattr(obj, n[0], n[1])

    def opPropertyDefinitions(self):
        """opPropertyDefinitions(obj) ... Store operation specific properties"""

        return [
            (
                "App::PropertyString",
                "Model",
                "Operation",
                translate("Path", "Source operation name."),
            ),
            (
                "App::PropertyLink",
                "BaseObj",
                "Operation",
                translate(
                    "Path",
                    "Base object for rest shape operation.",
                ),
            ),
            (
                "App::PropertyBool",
                "RemoveSplitters",
                "Operation",
                translate(
                    "Path",
                    "Set True to remove splitters from faces. May introduce bugs in shape.",
                ),
            ),
        ]

    def opPropertyDefaults(self, obj, job):
        """opPropertyDefaults(obj, job) ... returns a dictionary of default values
        for the operation's properties."""
        model = ""
        if len(job.Operations.Group) > 0:
            models = [
                op.Name
                for op in job.Operations.Group
                if op.Name != obj.Name and not op.Name.startswith("RestShape")
            ]
            model = models[-1]

        # defaults = {
        #    "Model": model,
        # }
        defaults = {"Model": "None", "RemoveSplitters": False}

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
        return

    def opOnDocumentRestored(self, obj):
        return

    def opUpdateDepths(self, obj):
        """opUpdateDepths(obj) ... Implement special depths calculation."""
        return

    # Main executable method
    def opExecute(self, obj):
        """opExecute(obj) ..."""
        # PathLog.debug("RestShape.opExecute()")
        PathLog.info("RestShape.opExecute()")
        PathLog.info(f"Base object name: {obj.Model}")

        if obj.Model == "None":
            PathLog.info("No source operation provided.")
            return

        removalShapes = []

        op = FreeCAD.ActiveDocument.getObject(obj.Model)
        obj.BaseObj = op

        toolcontroller = op.ToolController

        # Initiate depthparams and calculate operation heights for operation
        finish_step = op.FinishDepth.Value if hasattr(op, "FinishDepth") else 0.0
        self.depthparams = PathUtils.depth_params(
            clearance_height=op.ClearanceHeight.Value,
            safe_height=op.SafeHeight.Value,
            start_depth=op.StartDepth.Value,
            step_down=op.StepDown.Value,
            z_finish_step=finish_step,
            final_depth=op.FinalDepth.Value,
            user_depths=None,
        )
        depths = [d for d in self.depthparams]
        depths.insert(0, self.depthparams.start_depth)
        # Part.show(op.CutPatternShape, "Op_CutPatternShape")

        # Make and save removal shape
        removalShapes = [
            makeRemovalShape(c.Wires, toolcontroller, depths, useMethod=2)
            for c in op.CutPatternShape.Compounds
        ]

        # if first op, prevRestShape will be job stock
        prevRestObj = getPreviousRestObj(self.job, obj.Name)
        # obj.TargetShape = prevRestObj
        prevRestShape = prevRestObj.Shape

        # removalShape = Part.makeCompound(removalShapes)  # This method functions correctly with workflow
        if len(removalShapes) == 0:
            PathLog.error("No removal shapes created.")
            obj.ShowShape = False
            return

        if len(removalShapes) == 1:
            restShape = prevRestShape.cut(removalShapes[0])
        else:
            # orient removal to natural model position
            removalShape = putRotatedShape(removalShapes[0], op)
            restShape = prevRestShape.cut(removalShape)
            for rs in removalShapes[1:]:
                rotated = putRotatedShape(rs, op)
                cut = restShape.cut(rotated)
                restShape = cut

        if obj.RemoveSplitters:
            # smooth = restShape.removeSplitter()
            # shell = Part.Solid(Part.Shell([f.copy() for f in smooth.Faces]))
            # obj.Shape = shell
            obj.Shape = restShape.removeSplitter()
        else:
            obj.Shape = restShape

        rstObj = FreeCAD.ActiveDocument.addObject("Part::Feature", "RestShape")
        rstObj.Shape = obj.Shape
        rstObj.Label = f"RestShape_{op.Label}"
        rstObj.purgeTouched()

        if obj.ShowShape:
            rstShp = FreeCAD.ActiveDocument.addObject(
                "Part::Feature", f"Shape_{op.Label}"
            )
            rstShp.Shape = restShape
            rstShp.purgeTouched()
        obj.ShowShape = False

    def opExecute_2_best(self, obj):
        """opExecute(obj) ..."""
        # PathLog.debug("RestShape.opExecute()")
        PathLog.info("RestShape.opExecute()")
        PathLog.info(f"Base object name: {obj.Model}")

        if obj.Model == "None":
            PathLog.info("No source operation provided.")
            return

        removalShapes = []

        op = FreeCAD.ActiveDocument.getObject(obj.Model)
        obj.BaseObj = op

        toolcontroller = op.ToolController

        # Initiate depthparams and calculate operation heights for operation
        finish_step = op.FinishDepth.Value if hasattr(op, "FinishDepth") else 0.0
        self.depthparams = PathUtils.depth_params(
            clearance_height=op.ClearanceHeight.Value,
            safe_height=op.SafeHeight.Value,
            start_depth=op.StartDepth.Value,
            step_down=op.StepDown.Value,
            z_finish_step=finish_step,
            final_depth=op.FinalDepth.Value,
            user_depths=None,
        )
        depths = [d for d in self.depthparams]
        depths.insert(0, self.depthparams.start_depth)
        # Part.show(op.CutPatternShape, "Op_CutPatternShape")

        # Make and save removal shape
        removalShapes = [
            makeRemovalShape(c.Wires, toolcontroller, depths)
            for c in op.CutPatternShape.Compounds
        ]
        # removalShape = Part.makeCompound(removalShapes)  # This method functions correctly with workflow
        if len(removalShapes) == 0:
            PathLog.error("No removal shapes created.")
        else:
            removed = fuseShapes(removalShapes, method=2)
            removalShape = putRotatedShape(
                removed, op
            )  # orient removal to natural model position

            prevRestObj = getPreviousRestObj(
                self.job, obj.Name
            )  # if first op, prevRestObj will be job stock
            restShape = prevRestObj.Shape.cut(removalShape)

            if obj.RemoveSplitters:
                smooth = restShape.removeSplitter()
                shell = Part.Solid(Part.Shell([f.copy() for f in smooth.Faces]))
                obj.Shape = shell
            else:
                obj.Shape = restShape

            rstObj = FreeCAD.ActiveDocument.addObject("Part::Feature", "RestShape")
            rstObj.Shape = obj.Shape
            rstObj.Label = f"RestShape_{op.Label}"
            rstObj.purgeTouched()

        if obj.ShowShape:
            rstShp = FreeCAD.ActiveDocument.addObject(
                "Part::Feature", f"Shape_{op.Label}"
            )
            rstShp.Shape = restShape
            rstShp.purgeTouched()
        obj.ShowShape = False

    def opExecute_1(self, obj):
        """opExecute(obj) ... called whenever the receiver needs to be recalculated.
        See documentation of execute() for a list of base functionality provided."""
        # PathLog.debug("TargetShape.opExecute()")
        PathLog.info("RestShape.opExecute()")
        PathLog.info(f"Base object name: {obj.Model}")

        if obj.Model == "None":
            PathLog.info("No obj.Model provided.")
            return

        op = FreeCAD.ActiveDocument.getObject(obj.Model)

        toolcontroller = op.ToolController

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

        # Make and save removal shape
        # removalShape = makeRemovalShape(pathGeom, obj.ToolController, depths)
        removalShape = makeRemovalShape(op.CutPatternShape, toolcontroller, depths)
        Part.show(removalShape, f"{op.Name}_RestShape")
        """
        if removalShape and obj.MakeRestShape:
            removalShapes.append(removalShape)
            # Part.show(removalShape, "RemovalShape")
        else:
            PathLog.error("No removalShape returned")
            # Part.show(Part.makeCompound(commands_pathGeom_tuple[1]), "PathGeometry")
            # Part.show(useShape, "TargetShape")

        restShape = self.buildRestShape(removalShape, useShape, obj)
        if restShape is not None:
            restShapes.append(restShape)
            self.targetShapes.append((restShape, baseObj, "pathClearing"))
            # Part.show(restShape, "RestShape")
        """

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
            Part.show(removalShape, "RemovalShape")
        # Part.show(rawRestShape, "RawRestShape")

        if cont:
            return cleanVolume(rawRestShape)

        return None


# Eclass


def getPreviousOperation(job, opName):
    ops = job.Operations.Group
    if len(ops) < 2:
        return None
    prevOp = ops[0]
    for op in job.Operations.Group[1:]:
        if op.Name == opName:
            return prevOp


def getPreviousRestObj(job, opName):
    ops = job.Operations.Group
    if len(ops) < 2:
        return None
    prevRest = None
    for op in job.Operations.Group[1:]:
        if op.Name == opName:
            break  # Do not look past current RestShape object
        if op.Name.startswith("RestShape") and op.Name != opName:
            prevRest = op
            PathLog.info(f"previous rest shape is '{op.Name}'")

    if prevRest is None:
        return job.Stock

    return prevRest


def getRotatedShape(shape, refObj):
    """getRotatedShape(shape, refObj) ... get shape in rotated orientation ready for path generation."""
    AlignToFeature.CENTER_OF_ROTATION = refObj.TargetShape.CenterOfRotation
    rotations, __ = AlignToFeature.getRotationsForObject(refObj.TargetShape)
    # PathLog.info(f"Rotations: {rotations}")
    rotatedShape = AlignToFeature.rotateShapeWithList(shape, rotations)
    rotatedShape.translate(refObj.TargetShape.CenterOfRotation.negative())
    return rotatedShape


def putRotatedShape(shape, refObj):
    """putRotatedShape(shape, refObj) ... restores a rotated shape to original, natural position."""
    AlignToFeature.CENTER_OF_ROTATION = refObj.TargetShape.CenterOfRotation
    rots, __ = AlignToFeature.getRotationsForObject(refObj.TargetShape)
    rotations = AlignToFeature.reverseRotationsList(rots)
    # PathLog.info(f"Rotations: {rotations}")
    rotatedShape = AlignToFeature.rotateShapeWithList(shape, rotations)
    rotatedShape.translate(refObj.TargetShape.CenterOfRotation.negative())
    return rotatedShape


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
    # print("clean.Volume: {}".format(clean.Volume))
    # print("clean.BB.XLength: {}".format(clean.BoundBox.XLength))
    # print("clean.BB.YLength: {}".format(clean.BoundBox.YLength))
    if PathGeom.isRoughly(clean.Volume, 0.0):
        # Cleaning failed
        return volume
    return clean


def getHeightAdjustedShape(shape, startDepth):
    bbFace = PathGeom.makeBoundBoxFace(shape.BoundBox, offset=5.0)
    faceExt = bbFace.extrude(FreeCAD.Vector(0.0, 0.0, shape.BoundBox.ZLength + 1.0))
    faceExt.translate(FreeCAD.Vector(0.0, 0.0, startDepth - faceExt.BoundBox.ZMin))
    return shape.cut(faceExt).copy()


def makeRemovalShape(pathGeomList, ToolController, depths, useMethod=3):
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

    return fuseShapes(removalShapes, method=useMethod)


def fuseShapes(shapeList, method=1):
    if len(shapeList) == 0:
        return None
    elif len(shapeList) == 1:
        return shapeList[0]

    if method == 1:
        return Part.makeCompound(shapeList)
    if method == 2 or method == 3:
        seed = shapeList[0]
        if len(shapeList) > 1:
            for s in shapeList[1:]:
                fused = seed.fuse(s)
                seed = fused
        if method == 2:
            return seed
        if method == 3:
            return seed.removeSplitter()
    PathLog.error("fuseShapes() error")
    return None


def SetupProperties():
    setup = []

    return setup


def Create(name, obj=None, parentJob=None):
    """Create(name) ... Creates and returns a Target Shape object."""
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = RestShape(obj, name, parentJob)
    return obj


FreeCAD.Console.PrintMessage("Imported RestShape module from PathExp workbench.\n")
