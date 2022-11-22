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
                "Rotation",
                translate("Path", "Base model name."),
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
        ]

    def opPropertyDefaults(self, obj, job):
        """opPropertyDefaults(obj, job) ... returns a dictionary of default values
        for the operation's properties."""
        model = "None"
        if len(job.Operations.Group) > 0:
            models = [op.Name for op in job.Operations.Group if op.Name != obj.Name]
            model = models[-1]

        defaults = {
            "Model": model,
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
        return

    def opOnDocumentRestored(self, obj):
        return

    def opUpdateDepths(self, obj):
        """opUpdateDepths(obj) ... Implement special depths calculation."""
        return

    # Main executable method
    def opExecute(self, obj):
        """opExecute(obj) ... called whenever the receiver needs to be recalculated.
        See documentation of execute() for a list of base functionality provided."""
        # PathLog.debug("TargetShape.opExecute()")
        print("RestShape.opExecute()")
        print(f"Base object name: {obj.Model}")

        if obj.Model == "None":
            PathLog.info("No obj.Model provided.")
            return

        removalShapes = []
        restShapes = []

        op = FreeCAD.ActiveDocument.getObject(obj.Model)
        PathLog.info(f"Base op: {op.Name}.")
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
        removalShape = Part.makeCompound(removalShapes)
        # Part.show(removalShape, "RemovalShape")
        restShape = op.TargetShape.Shape.cut(removalShape)
        obj.Shape = restShape
        Part.show(restShape, f"{op.Label}_RestShape")
        obj.Label = f"RestShape_{op.Label}"

        if obj.ShowShape:
            rstShp = FreeCAD.ActiveDocument.addObject(
                "Part::Feature", f"Shape_{op.Label}"
            )
            rstShp.Shape = restShape
            rstShp.purgeTouched()
            obj.ShowShape = False

    def opExecute_orig(self, obj):
        """opExecute(obj) ... called whenever the receiver needs to be recalculated.
        See documentation of execute() for a list of base functionality provided."""
        # PathLog.debug("TargetShape.opExecute()")
        print("RestShape.opExecute()")
        print(f"Base object name: {obj.Model}")

        if obj.Model == "None":
            PathLog.info("No obj.Model provided.")
            return

        removalShapes = []
        restShapes = []

        op = FreeCAD.ActiveDocument.getObject(obj.Model)
        PathLog.info(f"Base op: {op.Name}.")

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


def makeRemovalShape(pathGeomList, ToolController, depths):
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

    return fuseShapes(removalShapes, method=2)


def fuseShapes(shapeList, method=1):
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
    PathLog.error()
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
