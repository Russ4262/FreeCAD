# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2014 Yorik van Havre <yorik@uncreated.net>              *
# *   Copyright (c) 2016 sliptonic <shopinthewoods@gmail.com>               *
# *   Copyright (c) 2020 Schildkroet                                        *
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
import Path
import PathScripts.PathLog as PathLog
import PathScripts.operations.PathOp2 as PathOp2
import PathScripts.PathUtils as PathUtils
import PathScripts.strategies.PathStrategyProfile as StrategyProfile
import PathScripts.strategies.PathTarget2DArea as PathTarget2DArea
import PathScripts.strategies.PathTargetOpenEdge as PathTargetOpenEdge

from PySide import QtCore

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader

Part = LazyLoader("Part", globals(), "Part")


__title__ = "Path Profile Operation"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Class and implementation of Path Perimeter operation."


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class ObjectPerimeter(PathOp2.ObjectOp2):
    """Proxy object for Profile operations based on faces."""

    @classmethod
    def propDefinitions(cls):
        """opProperties(obj) ... returns a tuples.
        Each tuple contains property declaration information in the
        form of (prototype, name, section, tooltip)."""
        definitions = [
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
                "App::PropertyEnumeration",
                "JoinType",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Controls how tool moves around corners. Default=Round",
                ),
            ),
            (
                "App::PropertyFloat",
                "MiterLimit",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property", "Maximum distance before a miter join is truncated"
                ),
            ),
            (
                "App::PropertyDistance",
                "MaterialAllowance",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Extra value to stay away from final profile- good for roughing toolpath",
                ),
            ),
            (
                "App::PropertyEnumeration",
                "CutSide",
                "PathOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property", "Side of edge that tool should cut"
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
            (
                "App::PropertyEnumeration",
                "HandleMultipleFeatures",
                "SelectionOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathPocket",
                    "Choose how to process multiple Base Geometry features.",
                ),
            ),
            (
                "App::PropertyEnumeration",
                "BoundaryShape",
                "SelectionOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property", "Shape to use for calculating Boundary"
                ),
            ),
            (
                "App::PropertyBool",
                "UseBasesOnly",
                "SelectionOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property", "Enable to use only bases of selected features."
                ),
            ),
            (
                "App::PropertyBool",
                "ProcessHoles",
                "SelectionOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property", "Profile holes as well as the outline"
                ),
            ),
            (
                "App::PropertyBool",
                "ProcessPerimeter",
                "SelectionOptions",
                QtCore.QT_TRANSLATE_NOOP("App::Property", "Profile the outline"),
            ),
            (
                "App::PropertyBool",
                "ProcessCircles",
                "SelectionOptions",
                QtCore.QT_TRANSLATE_NOOP("App::Property", "Profile round holes"),
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
        ]
        return definitions

    @classmethod
    def propEnumerations(cls):
        """opPropertyEnumerations() ... returns a dictionary of enumeration lists
        for the operation's enumeration type properties."""
        # Enumeration lists for App::PropertyEnumeration properties
        enums = {
            "CutDirection": ["Climb", "Conventional"],
            "HandleMultipleFeatures": ["Collectively", "Individually"],
            "BoundaryShape": ["Boundbox", "Face Region", "Perimeter", "Stock"],
            "JoinType": ["Round", "Square", "Miter"],
            "CutSide": ["Outside", "Inside"],
        }
        return enums

    @classmethod
    def propDefaults(cls, obj, job):
        """opPropertyDefaults(obj, job) ... returns a dictionary of default values
        for the operation's properties."""
        defaults = {
            "CutDirection": "Conventional",
            "HandleMultipleFeatures": "Collectively",
            "BoundaryShape": "Face Region",
            "JoinType": "Round",
            "MiterLimit": 0.1,
            "MaterialAllowance": 0.0,
            "CutSide": "Outside",
            "UseComp": True,
            "UseBasesOnly": False,
            "ProcessCircles": False,
            "ProcessHoles": False,
            "ProcessPerimeter": True,
        }
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
            | PathOp2.FeatureBaseEdges
            | PathOp2.FeatureBaseFaces
            | PathOp2.FeatureExtensions
            | PathOp2.FeatureIndexedRotation
        )

    def initOperation(self, obj):
        """initOperation(obj) ... implement to extend class `__init__()` contructor,
        like create additional properties."""
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        self.targetShapes = list()

    def opPropertyDefinitions(self):
        return ObjectPerimeter.propDefinitions()

    def opPropertyEnumerations(self):
        return ObjectPerimeter.propEnumerations()

    def opPropertyDefaults(self, obj, job):
        return ObjectPerimeter.propDefaults(obj, job)

    def opSetDefaultValues(self, obj, job):
        """opSetDefaultValues(obj) ... base implementation, do not overwrite.
        The base implementation sets the depths and heights based on the
        opShapeForDepths() return value."""
        PathLog.debug("opSetDefaultValues(%s, %s)" % (obj.Label, job.Label))

        """
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
        """

    def opShapeForDepths(self, obj, job):
        """opShapeForDepths(obj) ... returns the shape used to make an initial calculation for the depths being used.
        The default implementation returns the job's Base.Shape"""
        if obj.TargetShape:
            return obj.TargetShape.Proxy.getTargetGeometry(
                obj.TargetShape, shapeTypes=["2D Area", "2D Extrusion"]
            )
        elif job:
            if job.Stock:
                PathLog.debug(
                    "job=%s base=%s shape=%s" % (job, job.Stock, job.Stock.Shape)
                )
                return job.Stock.Shape
            else:
                PathLog.warning(
                    translate("PathProfile", "job %s has no Base.") % job.Label
                )
        else:
            PathLog.warning(
                translate("PathProfile", "no job for op %s found.") % obj.Label
            )
        return None

    def opSetEditorModes(self, obj):
        """opSetEditorModes(obj, porp) ... Process operation-specific changes to properties visibility."""

        # Always hidden
        obj.setEditorMode("AreaParams", 2)  # hide
        obj.setEditorMode("PathParams", 2)  # hide
        obj.setEditorMode("JoinType", 2)
        obj.setEditorMode("MiterLimit", 2)  # ml

    def opUpdateDepths(self, obj):
        if False and hasattr(obj, "Base") and len(obj.Base) == 0:
            obj.OpStartDepth = obj.OpStockZMax
            obj.OpFinalDepth = obj.OpStockZMin

    def opOnDocumentRestored(self, obj):
        """opOnDocumentRestored(obj) ... implement if an op needs special handling."""
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        self.targetShapes = list()

    def opExecute(self, obj, getsim=False):  # pylint: disable=arguments-differ
        """opExecute(obj, getsim=False) ... implementation of Path.Area ops.
        determines the parameters for _buildPathArea().
        """
        PathLog.track()

        # Instantiate class variables for operation reference
        self.endVector = None  # pylint: disable=attribute-defined-outside-init
        opFeatures = self.opFeatures(obj)
        startPoint = None
        opUseProjection = True
        opRetractTool = True

        self.printDepthParams(obj)

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

        # Set start point
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

        shapes = self.getTargetShape(obj)
        # shapes = self.getTargetShape_ORIG(obj)

        # Sort shapes to be processed
        if len(shapes) == 0:
            return list()
        if len(shapes) > 1:
            jobs = list()
            for s in shapes:
                if s[2] == "OpenEdge":
                    shp = Part.makeCompound(s[0])
                else:
                    shp = s[0]
                jobs.append(
                    {"x": shp.BoundBox.XMax, "y": shp.BoundBox.YMax, "shape": s}
                )

            jobs = PathUtils.sort_jobs(jobs, ["x", "y"])

            shapes = [j["shape"] for j in jobs]

        print("target shapes are now sorted")
        sims = []
        for shape, isHole, sub in shapes:
            if sub == "OpenEdge":
                strategy = StrategyProfile.StrategyProfileOpenEdge(
                    shape,
                    startPoint,
                    self.depthparams,
                    self.horizFeed,
                    self.vertFeed,
                    self.endVector,
                    self.radius,
                    obj.SafeHeight.Value,
                    obj.ClearanceHeight.Value,
                    obj.CutDirection,
                )
            else:
                strategy = StrategyProfile.StrategyProfile(
                    shape,
                    isHole,
                    startPoint,
                    getsim,
                    self.depthparams,
                    self.horizFeed,
                    self.vertFeed,
                    self.endVector,
                    self.radius,
                    opFeatures,
                    obj.SafeHeight.Value,
                    obj.ClearanceHeight.Value,
                    obj.MaterialAllowance.Value,
                    obj.CutDirection,
                    obj.CutSide,
                    obj.UseComp,
                    obj.JoinType,
                    obj.MiterLimit,
                    opUseProjection,
                    opRetractTool,
                )

            try:
                # Generate the path commands
                strategy.generateCommands()

                if sub == "OpenEdge":
                    if obj.UseStartPoint:
                        osp = obj.StartPoint
                        self.commandlist.append(
                            Path.Command(
                                "G0", {"X": osp.x, "Y": osp.y, "F": self.horizRapid}
                            )
                        )
                self.endVector = strategy.endVector
                # Save gcode commands to object command list
                self.commandlist.extend(strategy.commandList)
                if getsim:
                    sims.append(strategy.simObj)
                obj.PathParams = strategy.pathParams  # save path parameters
                obj.AreaParams = strategy.areaParams  # save area parameters
            except Exception as e:  # pylint: disable=broad-except
                PathLog.error(e)
                PathLog.error(
                    "Something unexpected happened. Check project and tool config."
                )

            if self.endVector is not None and len(self.commandlist) > 1:
                self.endVector[2] = obj.ClearanceHeight.Value
                self.commandlist.append(
                    Path.Command(
                        "G0", {"Z": obj.ClearanceHeight.Value, "F": self.vertRapid}
                    )
                )

        PathLog.debug("obj.Name: " + str(obj.Name) + "\n\n")
        if shapes:
            # Save working shapes to operation's removalshape attribute
            targetShapes = list()
            for shp, __, __ in shapes:
                if isinstance(shp, list):
                    targetShapes.extend(shp)
                else:
                    targetShapes.append(shp)
            obj.RemovalShape = Part.makeCompound(targetShapes)

        return sims

    def getTargetShape(self, obj, isPreview=False):
        """getTargetShape(obj) ... returns envelope for all base shapes or wires for Arch.Panels."""
        PathLog.track()
        baseShapes = list()
        # Identify working shapes for Profile operation
        if obj.TargetShape is not None:
            print("... Using TargetShape provided! ...")
            baseShapes = obj.TargetShape.Proxy.getTargetShapes(
                obj.TargetShape, shapeType="2D Extrusion"
            )
        else:
            print("Building target shapes from Base Geometry.")
            # baseShapes = self.getTargetShape_ORIG(obj)
            PathLog.error("Set TargetShape for operation.")
            return list()

        shapes = self._processOpenEdges(obj, baseShapes)
        return shapes

    # support methods
    def _processOpenEdges(self, obj, shapeTups):
        shapes = list()
        for tup in shapeTups:
            if tup[2] == "OpenEdge":
                targetWires = self._buildOpenEdges(obj, tup[2])
                for wire in targetWires:
                    wire.translate(
                        FreeCAD.Vector(
                            0.0, 0.0, obj.FinalDepth.Value - wire.BoundBox.ZMin
                        )
                    )
                shapes.append((targetWires, False, "OpenEdge"))
            else:
                shapes.append(tup)
        return shapes

    def _buildOpenEdges(self, obj, openEdgeList):
        """_buildOpenEdges(toolRadius, offsetRadius, jobTolerance, jobLabel='Job')...
        Call this method with arguments after calling `buildTargetShapes()` method.
        This method processes any identified open edges, returning a list
        of offset wires ready for path processing.
        """
        PathLog.debug("_buildOpenEdges()")
        openEdgeTups = list()

        offsetExtra = obj.MaterialAllowance.Value
        offsetRadius = offsetExtra
        openEdgeToolRadius = self.radius

        if obj.CutSide == "Inside":
            openEdgeToolRadius *= -1.0

        if obj.UseComp:
            offsetRadius = self.radius + offsetExtra

        for (base, wire) in openEdgeList:
            oe = PathTargetOpenEdge.OpenEdge(
                base.Shape,
                wire,
                obj.FinalDepth.Value,
                self.radius,
                offsetRadius,
                obj.UseComp,
                self.job.GeometryTolerance.Value,
                self.job.Label,
            )
            oe.isDebug = self.isDebug  # Transfer debug status
            oe.showDebugShapes = obj.ShowDebugShapes
            openEdges = oe.getOpenEdges()
            if openEdges:
                openEdgeTups.extend(openEdges)
            else:
                print("_buildOpenEdges(): no open edges returned in loop")

        return openEdgeTups


# Eclass


def SetupProperties():
    setup = list()
    # setup.extend(PathOp2.PathFeatureExtensions.SetupProperties())
    setup.extend([tup[1] for tup in ObjectPerimeter.propDefinitions()])
    return setup


def Create(name, obj=None, parentJob=None):
    """Create(name) ... Creates and returns a Profile based on faces operation."""
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectPerimeter(obj, name, parentJob)
    return obj
