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
import PathScripts.PathLog as PathLog

# import PathScripts.PathOp as PathOp
import PathScripts.operations.PathOp2 as PathOp2
import PathScripts.strategies.PathStrategyClearing as PathStrategyClearing
import PathScripts.strategies.PathTarget3DShape as PathTarget3DShape
import PathScripts.strategies.PathTarget2DArea as PathTarget2DArea
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


class ObjectTargetGeometry(PathOp2.ObjectOp2):
    """Proxy object for Clearing operation."""

    @classmethod
    def propDefinitions(cls):
        """opProperties() ... returns a tuples.
        Each tuple contains property declaration information in the
        form of (prototype, name, section, tooltip)."""
        definitions = [
            (
                "Part::PropertyPartShape",
                "Shape",
                "Operation",
                QtCore.QT_TRANSLATE_NOOP("App::Property", "Intended target shape type"),
            ),
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
                "App::PropertyInteger",
                "AvoidXFeatures",
                "SelectionOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Extra offset to apply to the operation. Direction is operation dependent.",
                ),
            ),
            (
                "App::PropertyBool",
                "ForceFinalDepthLow",
                "SelectionOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property", "Enable to force Final Depth calculation to lowest Base Geometry point."
                ),
            ),
            (
                "App::PropertyDistance",
                "MaterialAllowance",
                "SelectionOptions",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Extra offset to apply to the operation. Direction is operation dependent.",
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
            "ShapeType": ["2D Wire", "2D Area", "2D Extrusion", "3D Volume"],
            "HandleMultipleFeatures": ["Collectively", "Individually"],
            "BoundaryShape": ["Boundbox", "Face Region", "Perimeter", "Stock"],
        }
        return enums

    @classmethod
    def propDefaults(cls, obj, job):
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
            "AvoidXFeatures": 0,
            "ForceFinalDepthLow": False,
            "MaterialAllowance": 0.0,
        }
        return defaults

    # Regular methods
    def opFeatures(self, obj):
        """opFeatures(obj) ... returns the base features supported by all Path.Area based operations."""
        return (
            PathOp2.FeatureHeightsDepths
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
        self.targetShapes = []

    def opPropertyDefinitions(cls):
        return ObjectTargetGeometry.propDefinitions()

    def opPropertyEnumerations(cls):
        return ObjectTargetGeometry.propEnumerations()

    def opPropertyDefaults(cls, obj, job):
        return ObjectTargetGeometry.propDefaults(obj, job)

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

    def opSetEditorModes(self, obj):
        """opSetEditorModes(obj, porp) ... Process operation-specific changes to properties visibility."""
        pass

    def opUpdateDepths(self, obj):
        # PathLog.debug("opUpdateDepths()")
        if False and obj.ShapeType == "2D Area":
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

        if obj.ShapeType == "3D Volume":
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

        if obj.ForceFinalDepthLow:
            zMins = []
            if hasattr(obj, "Base") and len(obj.Base) > 0:
                for base, subsList in obj.Base:
                    zMins.append(
                        min([base.Shape.getElement(s).BoundBox.ZMin for s in subsList])
                    )
            obj.OpFinalDepth.Value = min(zMins)

    def opOnDocumentRestored(self, obj):
        """opOnDocumentRestored(obj) ... implement if an op needs special handling."""
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        self.isTargetShape = True
        self.targetShapes = []

    def opExecute(self, obj, getsim=False, shapeType=None):  # pylint: disable=arguments-differ
        """opExecute(obj, getsim=False) ... implementation of Path.Area ops.
        determines the parameters for _buildPathArea().
        """
        PathLog.track()

        removalShapes = []

        buildShapeType = obj.ShapeType if shapeType is None else shapeType
        self.targetShapes = self._buildTargetShape(obj, buildShapeType)

        for shape, __, __ in self.targetShapes:
            removalShapes.append(shape)

        # PathLog.debug("obj.Name: {}".format(obj.Name))
        if removalShapes:
            obj.Shape = Part.makeCompound(removalShapes)
        else:
            PathLog.error(translate("Path_Clearning", "{}: No removal shape produced.".format(obj.Label)))

    def _buildTargetShape(self, obj, buildShapeType, isPreview=False, facesOnly=False):
        """_buildTargetShape(obj, buildShapeType, isPreview=False, facesOnly=False) ...
        return shapes representing the solids to be removed."""
        PathLog.track()
        removalShapes = []
        avoidObjList = []
        featureObjList = []
        avoid = None
        extensions = None
        baseDataExists = True if obj.Base and len(obj.Base) > 0 else False

        self._setMisingClassVariables(obj)
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False

        # self.isDebug = True  # FORCE  DEBUG

        if baseDataExists:
            (featureObjList, avoidObjList) = self._filterBase(obj)

            if obj.UseBasesOnly:
                baseObjList = [(base, list()) for base, __ in featureObjList]
                # extensions = PathOp2.PathFeatureExtensions.getExtensions(obj)
            else:
                baseObjList = featureObjList
                extensions = PathOp2.PathFeatureExtensions.getExtensions(obj)
        else:
            baseObjList = [(base, list()) for base in self.model]

        # Process user inputs via Base Geometry and Extensions into pocket areas
        if buildShapeType == "3D Volume":
            PathLog.debug("_buildTargetShape() for 3D pocket")
            if isPreview:
                self.opUpdateDepths(obj)
            if obj.StartDepth.Value - obj.FinalDepth.Value <= 0.0:
                PathLog.error("Invalid clearing depth: {}".format(obj.StartDepth.Value - obj.FinalDepth.Value))
                return removalShapes

            pac = PathTarget3DShape.Target3DShape(
                baseObjList,
                extensions,
                obj.ProcessPerimeter,
                obj.ProcessHoles,
                obj.ProcessCircles,
                obj.HandleMultipleFeatures,
                startDepth=obj.StartDepth.Value,
                finalDepth=obj.FinalDepth.Value,
            )
            if avoidObjList:
                avoid = PathTarget3DShape.Target3DShape(
                    avoidObjList,
                    None,
                    True,
                    True,
                    True,
                    "Collectively",
                    startDepth=obj.StartDepth.Value,
                    finalDepth=obj.FinalDepth.Value,
                )
        elif buildShapeType in ["2D Area", "2D Extrusion"]:
            PathLog.debug("_buildTargetShape() 2D")
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
                "No Target Shape created for Shape Type: {}".format(buildShapeType)
            )
            return removalShapes

        pac.isDebug = self.isDebug  #  Pass isDebug flag
        pac.showDebugShapes = obj.ShowDebugShapes  #  Pass showDebugShapes flag
        pac.buildTargetShapes(avoidOverhead=True)
        pac.applyMaterialAllowance(
            0.0
        )  # pac.applyMaterialAllowance(obj.MaterialAllowance)
        self.exts = pac.getExtensionFaces()

        if hasattr(pac, "targetOpenEdgeTups") and pac.targetOpenEdgeTups:
            if buildShapeType == "2D Area":
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
            if buildShapeType == "2D Area":
                removalShapes.extend(
                    [(wa, base, "pathClearing") for base, wa in pac.targetAreaTups]
                )
            elif buildShapeType == "2D Extrusion":
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

    def _filterBase(self, obj):
        """_filterBase(obj) ... """
        if obj.AvoidXFeatures == 0:
            return (obj.Base, list())

        avoidObjList = []
        featureObjList = []

        baseCnt = len(obj.Base)
        avoidCnt = abs(obj.AvoidXFeatures)
        if avoidCnt > baseCnt:
            avoidCnt = baseCnt
        if obj.AvoidXFeatures < 0:
            avoidCnt = -1 * avoidCnt

        print("avoidCnt: {}".format(avoidCnt))
        if obj.AvoidXFeatures > 0:
            print("obj.AvoidXFeatures > 0")
            for base, subs in obj.Base:
                baseGrp = []
                avoidGrp = []
                for s in subs:
                    if avoidCnt > 0:
                        avoidGrp.append(s)
                        avoidCnt -= 1
                    else:
                        baseGrp.append(s)
                avoidObjList.append((base, avoidGrp))
                featureObjList.append((base, baseGrp))
        else:
            print("obj.AvoidXFeatures < 0")
            rev = [tup for tup in obj.Base]
            rev.reverse()
            for base, subs in rev:
                revSubs = [s for s in subs]
                revSubs.reverse()
                baseGrp = []
                avoidGrp = []
                for s in revSubs:
                    if avoidCnt < 0:
                        avoidGrp.append(s)
                        avoidCnt += 1
                    else:
                        baseGrp.append(s)
                avoidObjList.append((base, avoidGrp))
                featureObjList.append((base, baseGrp))

        for base, subs in avoidObjList:
            for s in subs:
                print("Avoiding: {}.{}".format(base.Name, s))

        return (featureObjList, avoidObjList)

    # Public methods
    def getTargetGeometry(self, obj, shapeTypes=["2D Area"]):
        if obj.ShapeType not in shapeTypes:
            PathLog.error(translate("PathTargetShape", "Incorrect target shape type."))
            PathLog.error("TG ShapeType: {};  Requested: {}".format(obj.ShapeType, shapeTypes))
            return list()

        if not obj.Shape or not self.targetShapes:
            self.opExecute(obj)

        return self.targetShapes


# Eclass


def SetupProperties():
    setup = []
    setup.extend([tup[1] for tup in ObjectTargetGeometry.propDefinitions()])
    return setup


def Create(name, obj=None, parentJob=None):
    """Create(name) ... Creates and returns a Target Shape object."""
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectTargetGeometry(obj, name, parentJob)
    return obj
