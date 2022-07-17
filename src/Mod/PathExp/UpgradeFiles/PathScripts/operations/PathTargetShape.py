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
import Path
import PathScripts.PathLog as PathLog

# import PathScripts.PathOp as PathOp
import PathScripts.operations.PathOp2 as PathOp2
import PathScripts.PathUtils as PathUtils
import PathScripts.strategies.PathStrategyClearing as PathStrategyClearing
import PathScripts.strategies.PathTarget3DShape as PathTarget3DShape
import PathScripts.strategies.PathTarget2DArea as PathTarget2DArea
import PathScripts.PathUtils as PathUtils
import Part

from PySide import QtCore


__title__ = "Path Target Shape"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Class and implementation of Target Shape object."


PathStrategyAdaptive = PathStrategyClearing.PathStrategyAdaptive

PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class ObjectTargetShape(PathOp2.ObjectOp):
    """Proxy object for Clearing operation."""

    def opFeatures(self, obj):
        """opFeatures(obj) ... returns the base features supported by all Path.Area based operations."""
        return (
            # PathOp2.FeatureTool
            PathOp2.FeatureHeightsDepths
            # | PathOp2.FeatureStepDown
            # | PathOp2.FeatureFinishDepth
            # | PathOp2.FeatureStartPoint
            # | PathOp2.FeatureCoolant
            | PathOp2.FeatureBaseEdges
            | PathOp2.FeatureBaseFaces
            | PathOp2.FeatureExtensions
            | PathOp2.FeatureIndexedRotation
        )

    def initOperation(self, obj):
        """initOperation(obj) ... implement to extend class `__init__()` contructor,
        like create additional properties."""
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        self.isTargetShape = True
        self.targetShapes = list()

    def opPropertyDefinitions(self):
        """opProperties() ... returns a tuples.
        Each tuple contains property declaration information in the
        form of (prototype, name, section, tooltip)."""
        props = [
            (
                "App::PropertyEnumeration",
                "ShapeType",
                "SelectionOptions",
                QtCore.QT_TRANSLATE_NOOP("App::Property", "Intended target shape type"),
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
                "App::PropertyEnumeration",
                "HandleMultipleFeatures",
                "SelectionOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Choose how to process multiple Base Geometry features.",
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
                "ProcessPerimeter",
                "SelectionOptions",
                QtCore.QT_TRANSLATE_NOOP("App::Property", "Profile the outline"),
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
                "ProcessCircles",
                "SelectionOptions",
                QtCore.QT_TRANSLATE_NOOP("App::Property", "Profile round holes"),
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
        ]
        return props

    def opPropertyEnumerations(self):
        """opPropertyEnumerations() ... returns a dictionary of enumeration lists
        for the operation's enumeration type properties."""
        # Enumeration lists for App::PropertyEnumeration properties
        enums = {
            "ShapeType": ["2D Wire", "2D Area", "2D Extrusion", "3D Volume"],
            "HandleMultipleFeatures": ["Collectively", "Individually"],
            "BoundaryShape": ["Boundbox", "Face Region", "Perimeter", "Stock"],
        }
        return enums

    def opPropertyDefaults(self, obj, job):
        """opPropertyDefaults(obj, job) ... returns a dictionary of default values
        for the operation's properties."""
        defaults = {
            "ShapeType": "2D Extrusion",
            "HandleMultipleFeatures": "Collectively",
            "BoundaryShape": "Face Region",
            "ProcessPerimeter": True,
            "ProcessHoles": True,
            "ProcessCircles": True,
            "UseBasesOnly": False,
            "ShowDebugShapes": False,
        }
        return defaults

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

    def opSetEditorModes(self, obj):
        """opSetEditorModes(obj, porp) ... Process operation-specific changes to properties visibility."""

        # Always hidden
        if PathLog.getLevel(PathLog.thisModule()) != 4:
            obj.setEditorMode("ShowDebugShapes", 2)

    def opShapeForDepths(self, obj, job):
        """opShapeForDepths(obj) ... returns the shape used to make an initial calculation for the depths being used.
        The default implementation returns the job's Base.Shape"""
        if job:
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
        if obj.ShapeType == "2D Area":
            zMins = list()
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
            # PathLog.debug("Cut 3D pocket update final depth: {} mm\n".format(obj.OpFinalDepth.Value))

    def opOnDocumentRestored(self, obj):
        """opOnDocumentRestored(obj) ... implement if an op needs special handling."""
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        self.targetShapes = list()

    def opExecute(self, obj, getsim=False):  # pylint: disable=arguments-differ
        """opExecute(obj, getsim=False) ... implementation of Path.Area ops.
        determines the parameters for _buildPathArea().
        """
        PathLog.track()
        removalShapes = list()
        self.targetShapes = self.getTargetShape(obj)

        for shape, __, __ in self.targetShapes:
            removalShapes.append(shape)

        # PathLog.debug("obj.Name: {}".format(obj.Name))
        if removalShapes:
            obj.RemovalShape = Part.makeCompound(removalShapes)

    def getTargetShape(self, obj, isPreview=False, facesOnly=False):
        """getTargetShape(obj) ... return shapes representing the solids to be removed."""
        PathLog.track()
        removalShapes = []
        extensions = None
        baseDataExists = True if obj.Base and len(obj.Base) > 0 else False

        self._setMisingClassVariables(obj)
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False

        # self.isDebug = True  # FORCE  DEBUG

        if baseDataExists:
            if obj.UseBasesOnly:
                baseObjList = [(base, list()) for base, subsList in obj.Base]
                # extensions = PathOp2.PathFeatureExtensions.getExtensions(obj)
            else:
                baseObjList = obj.Base
                extensions = PathOp2.PathFeatureExtensions.getExtensions(obj)
        else:
            baseObjList = [(base, list()) for base in self.model]

        # Process user inputs via Base Geometry and Extensions into pocket areas
        if obj.ShapeType == "3D Volume":
            PathLog.debug("getTargetShape() for 3D pocket")
            if isPreview:
                self.opUpdateDepths(obj)
            depthDiff = obj.StartDepth.Value <= obj.FinalDepth.Value
            if depthDiff <= 0.0:
                depthDiff = 1.0

            pac = PathTarget3DShape.Target3DShape(
                baseObjList,
                extensions,
                obj.ProcessPerimeter,
                obj.ProcessHoles,
                obj.ProcessCircles,
                obj.HandleMultipleFeatures,
                startDepth=obj.StartDepth.Value + depthDiff,
                finalDepth=obj.FinalDepth.Value,
            )
        elif obj.ShapeType in ["2D Area", "2D Extrusion"]:
            PathLog.debug("getTargetShape() 2D")
            pac = PathTarget2DArea.Target2DArea(
                baseObjList,
                extensions,
                obj.ProcessPerimeter,
                obj.ProcessHoles,
                obj.ProcessCircles,
                obj.HandleMultipleFeatures,
                obj.BoundaryShape,
                stockShape=self.job.Stock.Shape,
                finalDepth=obj.FinalDepth.Value,
            )
        else:
            PathLog.error(
                "No Target Shape created for Shape Type: {}".format(obj.ShapeType)
            )
            return removalShapes

        pac.isDebug = self.isDebug  #  Pass isDebug flag
        pac.showDebugShapes = obj.ShowDebugShapes  #  Pass showDebugShapes flag
        pac.buildTargetShapes(avoidOverhead=True)
        pac.applyMaterialAllowance(
            0.0
        )  # pac.applyMaterialAllowance(obj.MaterialAllowance)
        self.exts = pac.getExtensionFaces()

        if pac.targetOpenEdgeTups:
            if obj.ShapeType == "2D Area":
                removalShapes.extend(
                    [(wire, base, "OpenEdge") for base, wire in pac.targetOpenEdgeTups]
                )
            else:
                # Translate pocket area faces to final depth plus envelope padding
                # The padding is a buffer for later internal rounding issues - *path data are unaffected*
                envPad = 0.001
                envDepth = obj.FinalDepth.Value - envPad
                extent = FreeCAD.Vector(
                    0, 0, (obj.StartDepth.Value - obj.FinalDepth.Value) + 2 * envPad
                )

                for base, f in pac.targetOpenEdgeTups:
                    f.translate(FreeCAD.Vector(0.0, 0.0, envDepth - f.BoundBox.ZMin))
                    # extrude all pocket area faces up to StartDepth plus padding and those are the removal shapes with padding
                    removalShapes.append(
                        (f.removeSplitter().extrude(extent), base, "OpenEdge")
                    )

        if pac.targetAreaTups:
            if obj.ShapeType == "2D Area":
                removalShapes.extend(
                    [(wa, base, "pathClearing") for base, wa in pac.targetAreaTups]
                )
            elif obj.ShapeType == "2D Extrusion":
                # Translate pocket area faces to final depth plus envelope padding
                # The padding is a buffer for later internal rounding issues - *path data are unaffected*
                envPad = 0.001
                envDepth = obj.FinalDepth.Value - envPad
                extent = FreeCAD.Vector(
                    0, 0, (obj.StartDepth.Value - obj.FinalDepth.Value) + 2 * envPad
                )

                for base, f in pac.targetAreaTups:
                    f.translate(FreeCAD.Vector(0.0, 0.0, envDepth - f.BoundBox.ZMin))
                    # extrude all pocket area faces up to StartDepth plus padding and those are the removal shapes with padding
                    removalShapes.append(
                        (f.removeSplitter().extrude(extent), base, "pathClearing")
                    )

        if pac.targetSolidTups:
            # add working solids as prepared envelopes for 3D Pocket
            removalShapes.extend(
                [(env, base, "pocket3D") for base, env in pac.targetSolidTups]
            )

        return removalShapes

    # Public methods
    def getTargetShapes(self, obj, shapeType="2D Area"):
        if obj.ShapeType != shapeType:
            PathLog.error(translate("PathTargetShape", "Incorrect target shape type."))
            return list()

        if self.targetShapes:
            return self.targetShapes
        else:
            return self.getTargetShape(obj)


# Eclass


def SetupProperties():
    setup = list()
    setup.extend([tup[1] for tup in ObjectTargetShape.opPropertyDefinitions(None)])
    return setup


def Create(name, obj=None, parentJob=None):
    """Create(name) ... Creates and returns a Target Shape object."""
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectTargetShape(obj, name, parentJob)
    return obj
