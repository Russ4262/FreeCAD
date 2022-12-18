# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2017 sliptonic <shopinthewoods@gmail.com>               *
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

import time
import math

from PySide import QtCore

from PathScripts.PathUtils import waiting_effects
import Path
import Path.Geom as PathGeom
import Path.Log as PathLog
import Path.Base.Util as PathUtil
import PathScripts.PathUtils as PathUtils

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader

FreeCAD = LazyLoader("FreeCAD", globals(), "FreeCAD")
Part = LazyLoader("Part", globals(), "Part")
PathFeatureExtensions = LazyLoader(
    "Features.PathFeatureExtensions", globals(), "Features.PathFeatureExtensions"
)

__title__ = "Base class for all operations."
__author__ = "sliptonic (Brad Collette)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Base class and properties implementation for all Path operations."

PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule()


# Qt translation handling
translate = FreeCAD.Qt.translate


FeatureTool = 0x0001  # ToolController
FeatureHeightsDepths = 0x0002  # Heights and Depths combined
FeatureStartPoint = 0x0004  # StartPoint
FeatureFinishDepth = 0x0008  # FinishDepth
FeatureStepDown = 0x0010  # StepDown
FeatureNoFinalDepth = 0x0020  # edit or not edit FinalDepth
FeatureBaseVertexes = 0x0040  # Base
FeatureBaseEdges = 0x0080  # Base
FeatureBaseFaces = 0x0100  # Base
FeatureLocations = 0x0200  # Locations
FeatureCoolant = 0x0400  # Coolant
FeatureDiameters = 0x0800  # Turning Diameters
FeatureExtensions = 0x1000  # Extensions
FeatureBasePanels = 0x4000
FeatureHoleGeometry = 0x8000
FeatureBaseGeometry = (
    FeatureBaseVertexes | FeatureBaseFaces | FeatureBaseEdges | FeatureBasePanels
)


class ObjectOp2(object):
    """
    Base class for proxy objects of all Path operations.

    Use this class as a base class for new operations. It provides properties
    and some functionality for the standard properties each operation supports.
    By OR'ing features from the feature list an operation can select which ones
    of the standard features it requires and/or supports.

    The currently supported features are:
        FeatureTool          ... Use of a ToolController
        FeatureHeightsDepths        ... Depths, for start, final
        # FeatureHeights       ... Heights, safe and clearance - Combined with FeatureHeightsDepths
        FeatureStartPoint    ... Supports setting a start point
        FeatureFinishDepth   ... Operation supports a finish depth
        FeatureStepDown      ... Support for step down
        FeatureNoFinalDepth  ... Disable support for final depth modifications
        FeatureBaseVertexes  ... Base geometry support for vertexes
        FeatureBaseEdges     ... Base geometry support for edges
        FeatureBaseFaces     ... Base geometry support for faces
        FeatureLocations     ... Base location support
        FeatureCoolant       ... Support for operation coolant
        FeatureDiameters     ... Support for turning operation diameters

    The base class handles all base API and forwards calls to subclasses with
    an op prefix. For instance, an op is not expected to overwrite onChanged(),
    but implement the function opOnChanged().
    If a base class overwrites a base API function it should call the super's
    implementation - otherwise the base functionality might be broken.
    """

    def __init__(self, obj, name, parentJob=None):
        PathLog.debug("ObjectOp2.__init__()")

        self.obj = obj
        notOpPrototype = (
            True
            if not hasattr(obj, "DoNotSetDefaultValues")
            or not obj.DoNotSetDefaultValues
            else False
        )

        self._initAttributes(obj)

        if notOpPrototype:
            self._assignToJob(obj, parentJob)
            if self.job and hasattr(self.job, "EnableRotation"):
                self.canDoRotation = self.job.EnableRotation

        # initialize database-style operation properties if formatted in this manner
        self.initProperties(obj)
        self.initOperation(obj)  # call to sub-class for constructor instructions

        # Set default property values
        if notOpPrototype:
            self.setDefaultValues(obj)
            if self.job:
                self.job.SetupSheet.Proxy.setOperationProperties(obj, name)
                obj.recompute()
                obj.Proxy = self
            else:
                PathLog.error("self.job DOES NOT EXIST in NON-prototype op")

            self.setEditorModes(obj)

        self.propertiesReady = True

    def _initAttributes(self, obj):
        self.features = self.opFeatures(self.obj)
        self.propertiesReady = False
        self.addNewProps = list()
        self.isDebug = False
        self.canDoRotation = None
        self.isTargetShape = False

        # members being set later
        self.commandlist = None
        self.tool = None
        self.depthparams = None
        self.horizFeed = None
        self.horizRapid = None
        self.vertFeed = None
        self.vertRapid = None
        self.axialFeed = 0.0
        self.axialRapid = 0.0
        self.model = None
        self.radius = None
        self.stock = None
        self.job = None
        self.resetRotationCommands = list()

    def initProperties(self, obj, inform=False):
        """initProperties(obj, inform=False) ... create operation specific properties.
        Do not overwrite."""
        PathLog.track()
        addNewProps = list()

        for (propType, propName, group, tooltip) in self.propertyDefinitions():
            if not hasattr(obj, propName):
                obj.addProperty(propType, propName, group, tooltip)
                addNewProps.append(propName)

        if len(addNewProps) > 0:
            # Set enumeration lists for enumeration properties
            propEnums = self.propertyEnumerations()
            # PathLog.info(f"propEnums:\n{propEnums}")
            # for n in propEnums:
            for n, enums in propEnums:
                if n in addNewProps:
                    # PathLog.info(f"Setting {n} enums.")
                    # setattr(obj, n, propEnums[n])
                    setattr(obj, n, enums)
            if inform:
                newPropMsg = translate("PathProfile", "New property added to")
                newPropMsg += ' "{}": {}'.format(obj.Label, addNewProps) + ". "
                newPropMsg += translate("PathProfile", "Check its default value.")
                PathLog.info(newPropMsg)

        if addNewProps:
            self.addNewProps = addNewProps

    def propertyDefinitions(self):
        PathLog.track()
        features = self.features

        # Standard properties
        definitions = [
            (
                "App::PropertyBool",
                "Active",
                "Operation",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp", "Make False, to prevent operation from generating code"
                ),
            ),
            (
                "App::PropertyString",
                "Comment",
                "Operation",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp", "An optional comment for this Operation"
                ),
            ),
            (
                "App::PropertyString",
                "UserLabel",
                "Operation",
                QtCore.QT_TRANSLATE_NOOP("PathOp", "User Assigned Label"),
            ),
            (
                "App::PropertyString",
                "CycleTime",
                "Operation",
                QtCore.QT_TRANSLATE_NOOP("PathOp", "Operations Cycle Time Estimation"),
            ),
            (
                "App::PropertyDistance",
                "OpStockZMax",
                "Op Values",
                QtCore.QT_TRANSLATE_NOOP("PathOp", "Holds the max Z value of Stock"),
            ),
            (
                "App::PropertyDistance",
                "OpStockZMin",
                "Op Values",
                QtCore.QT_TRANSLATE_NOOP("PathOp", "Holds the min Z value of Stock"),
            ),
            (
                "Part::PropertyPartShape",
                "Shape",
                "Operation",
                QtCore.QT_TRANSLATE_NOOP("App::Property", "REST shape"),
            ),
            (
                "Part::PropertyPartShape",
                "RemovalShape",
                "Debug",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Debug property that stores copy of the working shape passed to the strategy for this operation.",
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
                "ShowShape",
                "Debug",
                QtCore.QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Enable to add Target Geometry to object tree for debug purposes.",
                ),
            ),
        ]

        if not self.isTargetShape:
            definitions.append(
                (
                    "App::PropertyLink",
                    "TargetShape",
                    "Operation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "The target shape object for an operation"
                    ),
                )
            )

        # Add operation-specific property definitions
        definitions.extend(self.opPropertyDefinitions())

        # Add operation feature property definitions
        if FeatureBaseGeometry & features:
            definitions.append(self._getBasePropertyDefenition())

        if FeatureHoleGeometry & features:
            definitions.append(self._getHolePropertyDefenition())

        if FeatureLocations & features:
            definitions.append(
                (
                    "App::PropertyVectorList",
                    "Locations",
                    "Path",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "Base locations for this operation"
                    ),
                )
            )

        if FeatureTool & features:
            definitions.append(
                (
                    "App::PropertyLink",
                    "ToolController",
                    "Operation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp",
                        "The tool controller that will be used to calculate the path",
                    ),
                )
            )
            definitions.append(
                (
                    "App::PropertyDistance",
                    "OpToolDiameter",
                    "Op Values",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "Holds the diameter of the tool"
                    ),
                )
            )

        if FeatureCoolant & features:
            definitions.append(
                (
                    "App::PropertyString",
                    "CoolantMode",
                    "Operation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "Coolant mode for this operation"
                    ),
                )
            )

        if FeatureHeightsDepths & features:
            definitions.append(
                (
                    "App::PropertyDistance",
                    "ClearanceHeight",
                    "Depth",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "The height needed to clear clamps and obstructions"
                    ),
                )
            )
            definitions.append(
                (
                    "App::PropertyDistance",
                    "SafeHeight",
                    "Depth",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "Rapid Safety Height between locations."
                    ),
                )
            )
            definitions.append(
                (
                    "App::PropertyDistance",
                    "StartDepth",
                    "Depth",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "Starting Depth of Tool- first cut depth in Z"
                    ),
                )
            )
            definitions.append(
                (
                    "App::PropertyDistance",
                    "FinalDepth",
                    "Depth",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "Final Depth of Tool- lowest value in Z"
                    ),
                )
            )
            definitions.append(
                (
                    "App::PropertyDistance",
                    "OpStartDepth",
                    "Op Values",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "Holds the calculated value for the StartDepth"
                    ),
                )
            )
            definitions.append(
                (
                    "App::PropertyDistance",
                    "OpFinalDepth",
                    "Op Values",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "Holds the calculated value for the FinalDepth"
                    ),
                )
            )
        else:
            # StartDepth has become necessary for expressions on other properties
            definitions.append(
                (
                    "App::PropertyDistance",
                    "StartDepth",
                    "Depth",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "Starting Depth internal use only for derived values"
                    ),
                )
            )

        if FeatureStepDown & features:
            definitions.append(
                (
                    "App::PropertyDistance",
                    "StepDown",
                    "Depth",
                    QtCore.QT_TRANSLATE_NOOP("PathOp", "Incremental Step Down of Tool"),
                )
            )

        if FeatureFinishDepth & features:
            definitions.append(
                (
                    "App::PropertyDistance",
                    "FinishDepth",
                    "Depth",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "Maximum material removed on final pass."
                    ),
                )
            )

        if FeatureStartPoint & features:
            definitions.append(
                (
                    "App::PropertyVectorDistance",
                    "StartPoint",
                    "Start Point",
                    QtCore.QT_TRANSLATE_NOOP("PathOp", "The start point of this path"),
                )
            )
            definitions.append(
                (
                    "App::PropertyBool",
                    "UseStartPoint",
                    "Start Point",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "Make True, if specifying a Start Point"
                    ),
                )
            )

        if FeatureDiameters & features:
            definitions.append(
                (
                    "App::PropertyDistance",
                    "MinDiameter",
                    "Diameter",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "Lower limit of the turning diameter"
                    ),
                )
            )
            definitions.append(
                (
                    "App::PropertyDistance",
                    "MaxDiameter",
                    "Diameter",
                    QtCore.QT_TRANSLATE_NOOP(
                        "PathOp", "Upper limit of the turning diameter."
                    ),
                )
            )

        if FeatureExtensions & features:
            definitions.extend(PathFeatureExtensions.extensionsPropertyDefinitions())

        return definitions

    def _addBaseProperty(self, obj):
        obj.addProperty(
            "App::PropertyLinkSubListGlobal",
            "Base",
            "Operation",
            QtCore.QT_TRANSLATE_NOOP("PathOp", "The base geometry for this operation"),
        )

    def _getBasePropertyDefenition(self):
        return (
            "App::PropertyLinkSubListGlobal",
            "Base",
            "Operation",
            QtCore.QT_TRANSLATE_NOOP("PathOp", "The base geometry for this operation"),
        )

    def _getHolePropertyDefenition(self):
        return (
            "App::PropertyLinkSubListGlobal",
            "Hole",
            "Operation",
            QtCore.QT_TRANSLATE_NOOP("PathOp", "The hole geometry for this operation"),
        )

    def propertyDefaults(self, obj, job):
        defaults = {"Active": True, "ShowDebugShapes": False, "ShowShape": False}

        for k, v in self.opPropertyDefaults(obj, job).items():
            defaults[k] = v

        return defaults

    def propertyEnumerations_old(self):
        """propertyEnumerations() ... Returns operation-specific property enumeration lists as a dictionary.
        Each property name is a key and the enumeration list is the value.
        Should be overwritten by subclasses."""
        # Enumeration lists for App::PropertyEnumeration properties
        propEnums = {}

        for k, v in self.opPropertyEnumerations().items():
            propEnums[k] = v

        return propEnums

    def propertyEnumerations(self):
        """propertyEnumerations() ... Returns operation-specific property enumeration lists as a dictionary.
        Each property name is a key and the enumeration list is the value.
        Should be overwritten by subclasses."""
        # Enumeration lists for App::PropertyEnumeration properties
        return self.opPropertyEnumerations()

    def _assignToJob(self, obj, parentJob=None):
        """_assignToJob(obj) ... base implementation.
        Do not overwrite, overwrite opSetDefaultValues() instead."""
        if not self.job:
            if parentJob:
                self.job = PathUtils.addToJob(obj, jobname=parentJob.Name)
            else:
                self.job = PathUtils.addToJob(obj)

    def setDefaultValues(self, obj):
        """setDefaultValues(obj) ... base implementation.
        Do not overwrite, overwrite opSetDefaultValues() instead."""
        PathLog.debug("setDefaultValues()")

        if not self.job:
            PathLog.error("PathOp2.setDefaultValues() No Job.")
            return

        features = self.opFeatures(self.obj)

        if FeatureTool & features:
            opCnt = len(self.job.Operations.Group)
            if opCnt > 1:
                # Check
                idx = 0
                while opCnt > 0:
                    opCnt -= 1
                    idx -= 1
                    obj.ToolController = PathUtil.toolControllerForOp(
                        self.job.Operations.Group[idx]
                    )
                    if obj.ToolController:
                        break
            if not obj.ToolController:
                obj.ToolController = PathUtils.findToolController(obj, self)
            if not obj.ToolController:
                PathLog.error("No ToolController found.")
                return None
            obj.OpToolDiameter = obj.ToolController.Tool.Diameter

        if FeatureCoolant & features:
            obj.CoolantMode = self.job.SetupSheet.CoolantMode

        if FeatureHeightsDepths & features:
            if self.job.SetupSheet.ClearanceHeightExpression:
                if not self.applyExpression(
                    obj,
                    "ClearanceHeight",
                    self.job.SetupSheet.ClearanceHeightExpression,
                ):
                    obj.ClearanceHeight = "5 mm"

            if self.job.SetupSheet.SafeHeightExpression:
                if not self.applyExpression(
                    obj, "SafeHeight", self.job.SetupSheet.SafeHeightExpression
                ):
                    obj.SafeHeight = "3 mm"

            if self.applyExpression(
                obj, "StartDepth", self.job.SetupSheet.StartDepthExpression
            ):
                obj.OpStartDepth = 1.0
            else:

                obj.StartDepth = 1.0
            if self.applyExpression(
                obj, "FinalDepth", self.job.SetupSheet.FinalDepthExpression
            ):
                obj.OpFinalDepth = 0.0
            else:
                obj.FinalDepth = 0.0
        else:
            obj.StartDepth = 1.0

        if FeatureStepDown & features:
            if not self.applyExpression(
                obj, "StepDown", self.job.SetupSheet.StepDownExpression
            ):
                obj.StepDown = "1 mm"

        if FeatureDiameters & features:
            obj.MinDiameter = "0 mm"
            obj.MaxDiameter = "0 mm"
            if self.job.Stock:
                obj.MaxDiameter = self.job.Stock.Shape.BoundBox.XLength

        if FeatureStartPoint & features:
            obj.UseStartPoint = False

        if FeatureExtensions & features:
            PathFeatureExtensions.setDefaultPropertyValues(obj, self.job)

        # Apply defaults to new properties
        if self.addNewProps and len(self.addNewProps) > 0:
            self.applyPropertyDefaults(obj, self.job, self.addNewProps)

        # call operation-specific method to apply additional default values
        self.opSetDefaultValues(obj, self.job)

        # self.propertiesReady = True

    def setEditorModes(self, obj):
        """Editor modes are not preserved during document store/restore, set editor modes for all properties"""
        features = self.features

        for prop in [
            "OpStartDepth",
            "OpFinalDepth",
            "OpToolDiameter",
            "CycleTime",
            "OpStockZMax",
            "OpStockZMin",
        ]:
            if hasattr(obj, prop):
                obj.setEditorMode(prop, 1)  # read-only

        if FeatureHeightsDepths & features:
            if FeatureNoFinalDepth & features:
                obj.setEditorMode("OpFinalDepth", 2)

        if FeatureExtensions & features:
            PathFeatureExtensions.extensionsSetEditorModes(obj)

        # Set editor mode to hidden for these properties
        for prop in ["AreaParams", "PathParams", "RemovalShape", "Shape"]:
            if hasattr(obj, prop):
                obj.setEditorMode(prop, 2)

        obj.setEditorMode("CycleTime", 1)  # read-only

        self.opSetEditorModes(obj)

    def onDocumentRestored(self, obj):
        self.obj = obj
        self._initAttributes(obj)

        self.getJob(obj)

        if self.job and hasattr(self.job, "EnableRotation"):
            self.canDoRotation = self.job.EnableRotation

        # add missing standard and feature properties if missing, and get job
        self.initProperties(obj, inform=True)

        # add new(missing) properties and set default values for the same
        if self.addNewProps and len(self.addNewProps) > 0:
            # PathLog.info(f"self.addNewProps:\n{self.addNewProps}")
            self.applyPropertyDefaults(obj, self.job, self.addNewProps)

        # Update older `Base' property type to newer global version
        if (
            FeatureBaseGeometry & self.features
            and "App::PropertyLinkSubList" == obj.getTypeIdOfProperty("Base")
        ):
            PathLog.info("Replacing link property with global link (%s)." % obj.State)
            base = obj.Base
            obj.removeProperty("Base")
            self._addBaseProperty(obj)
            obj.Base = base
            obj.touch()
            obj.Document.recompute()

        self.setEditorModes(obj)
        self.opOnDocumentRestored(obj)
        self.propertiesReady = True

    def onChanged(self, obj, prop):
        """onChanged(obj, prop) ... base implementation of the FC notification framework.
        Do not overwrite, overwrite opOnChanged() instead."""

        # there's a bit of cycle going on here, if sanitizeBase causes the transaction to
        # be cancelled we end right here again with the unsainitized Base - if that is the
        # case, stop the cycle and return immediately
        if prop == "Base" and self.sanitizeBase(obj):
            return

        if "Restore" not in obj.State and prop in ["Base", "StartDepth", "FinalDepth"]:
            self.updateDepths(obj, True)

        if hasattr(self, "features"):
            self.setEditorModes(obj)

        self.opOnChanged(obj, prop)

    def _setBaseAndStock(self, obj, ignoreErrors=False):
        job = PathUtils.findParentJob(obj)
        if not job:
            if not ignoreErrors:
                PathLog.error(translate("Path", "No parent job found for operation."))
            return False
        if not job.Model.Group:
            if not ignoreErrors:
                PathLog.error(
                    translate("Path", "Parent job %s doesn't have a base object")
                    % job.Label
                )
            return False
        self.job = job
        self.model = job.Model.Group
        self.stock = job.Stock
        return True

    def updateDepths(self, obj, ignoreErrors=False):
        """updateDepths(obj) ... base implementation calculating depths depending on base geometry.
        Should not be overwritten."""

        def faceZmin(bb, fbb):
            if fbb.ZMax == fbb.ZMin and fbb.ZMax == bb.ZMax:  # top face
                return fbb.ZMin
            elif fbb.ZMax > fbb.ZMin and fbb.ZMax == bb.ZMax:  # vertical face, full cut
                return fbb.ZMin
            elif fbb.ZMax > fbb.ZMin and fbb.ZMin > bb.ZMin:  # internal vertical wall
                return fbb.ZMin
            elif fbb.ZMax == fbb.ZMin and fbb.ZMax > bb.ZMin:  # face/shelf
                return fbb.ZMin
            return bb.ZMin

        if not self._setBaseAndStock(obj, ignoreErrors):
            return False

        stockBB = self.stock.Shape.BoundBox
        zmin = stockBB.ZMin
        zmax = stockBB.ZMax

        obj.OpStockZMin = zmin
        obj.OpStockZMax = zmax

        if hasattr(obj, "Base") and obj.Base:
            for base, sublist in obj.Base:
                bb = base.Shape.BoundBox
                zmax = max(zmax, bb.ZMax)
                for sub in sublist:
                    try:
                        if sub:
                            fbb = base.Shape.getElement(sub).BoundBox
                        else:
                            fbb = base.Shape.BoundBox
                        zmin = max(zmin, faceZmin(bb, fbb))
                        zmax = max(zmax, fbb.ZMax)
                    except Part.OCCError as e:
                        PathLog.error(e)

        else:
            # clearing with stock boundaries
            job = PathUtils.findParentJob(obj)
            zmax = stockBB.ZMax
            zmin = job.Proxy.modelBoundBox(job).ZMax

        if FeatureHeightsDepths & self.features:
            # first set update final depth, it's value is not negotiable
            if not PathGeom.isRoughly(obj.OpFinalDepth.Value, zmin):
                obj.OpFinalDepth = zmin
            zmin = obj.OpFinalDepth.Value

            def minZmax(z):
                if hasattr(obj, "StepDown") and not PathGeom.isRoughly(
                    obj.StepDown.Value, 0
                ):
                    return z + obj.StepDown.Value
                else:
                    return z + 1

            # ensure zmax is higher than zmin
            if (zmax - 0.0001) <= zmin:
                zmax = minZmax(zmin)

            # update start depth if requested and required
            if not PathGeom.isRoughly(obj.OpStartDepth.Value, zmax):
                obj.OpStartDepth = zmax
        else:
            # every obj has a StartDepth
            if obj.StartDepth.Value != zmax:
                obj.StartDepth = zmax

        self.opUpdateDepths(obj)

    def _printCurrentDepths(self, obj, label):
        print(
            f"current depths at {label}:\n OpSD: {obj.OpStartDepth};  SD: {obj.StartDepth};  SDval: {obj.StartDepth.Value}\n OpFD: {obj.OpFinalDepth};  FD: {obj.FinalDepth};  FDval: {obj.FinalDepth.Value}"
        )

    def applyPropertyDefaults(self, obj, job, propList):
        # PathLog.debug("applyPropertyDefaults(obj, job, propList={})".format(propList))
        # Set standard property defaults
        propDefaults = self.propertyDefaults(obj, job)
        for n in propDefaults:
            if n in propList:
                prop = getattr(obj, n)
                val = propDefaults[n]
                setVal = False
                if hasattr(prop, "Value"):
                    if isinstance(val, int) or isinstance(val, float):
                        setVal = True
                if setVal:
                    # propVal = getattr(prop, 'Value')
                    # Need to check if `val` below should be `propVal` commented out above
                    setattr(prop, "Value", val)
                else:
                    setattr(obj, n, val)

    # Support methods
    def initTargetShapeGroup(self, obj):
        obj.addProperty(
            "App::PropertyLink",
            "TargetShapeGroup",
            "Base",
            QtCore.QT_TRANSLATE_NOOP(
                "PathOp", "The group of target shapes for an operation"
            ),
        )
        shapes = FreeCAD.ActiveDocument.addObject(
            "App::DocumentObjectGroup", "TargetShapeGroup"
        )
        shapes.Label = "TargetShapes_{}".format(obj.Name)
        if shapes.ViewObject:
            shapes.ViewObject.Visibility = False
        obj.TargetShapeGroup = shapes

    def applyExpression(self, obj, prop, expr):
        """applyExpression(obj, prop, expr) ... set expression expr on obj.prop if expr is set"""
        if expr:
            obj.setExpression(prop, expr)
            PathLog.debug("applyExpression({}) True".format(prop))
            return True
        PathLog.debug("__ applyExpression({}) FALSE __".format(prop))
        return False

    def getJob(self, obj):
        """getJob(obj) ... return the job this operation is part of."""
        PathLog.debug("getJob({})".format(obj.Name))
        if not hasattr(self, "job") or self.job is None:
            if not self._setBaseAndStock(obj):
                return None
        return self.job

    def sanitizeBase(self, obj):
        """sanitizeBase(obj) ... check if Base is valid and clear on errors."""
        # PathLog.debug("sanitizeBase({})".format(obj.Name))

        if hasattr(obj, "Base"):
            try:
                for (o, sublist) in obj.Base:
                    for sub in sublist:
                        e = o.Shape.getElement(sub)
            except Part.OCCError as e:
                PathLog.error(
                    "{} - stale base geometry detected - clearing.".format(obj.Label)
                )
                obj.Base = []
                return True
        return False

    def _setMisingClassVariables(self, obj):
        """_setMisingClassVariables(obj)... This method is necessary for the `getTargetShape()` method."""
        if not hasattr(self, "isDebug"):
            self.isDebug = False

        self._setFeatureValues(obj)

    def _setFeatureValues(self, obj):
        PathLog.debug("_setFeatureValues()")

        if FeatureCoolant & self.features:
            PathLog.debug("_setFeatureValues() FeatureCoolant")
            if not hasattr(obj, "CoolantMode"):
                PathLog.error(
                    translate(
                        "Path", "No coolant property found. Please recreate operation."
                    )
                )

        if FeatureTool & self.features:
            PathLog.debug("_setFeatureValues() FeatureTool")
            tc = obj.ToolController
            if tc is None or tc.ToolNumber == 0:
                PathLog.error(
                    translate(
                        "Path",
                        "No Tool Controller is selected. We need a tool to build a Path.",
                    )
                )
                return
            else:
                tool = tc.Proxy.getTool(tc)
                if not tool or float(tool.Diameter) == 0:
                    PathLog.error(
                        translate(
                            "Path",
                            "No Tool found or diameter is zero. We need a tool to build a Path.",
                        )
                    )
                    return
                self.radius = float(tool.Diameter) / 2.0
                self.tool = tool
                self.vertFeed = tc.VertFeed.Value
                self.horizFeed = tc.HorizFeed.Value
                self.vertRapid = tc.VertRapid.Value
                self.horizRapid = tc.HorizRapid.Value
                obj.OpToolDiameter = tool.Diameter

        if FeatureHeightsDepths & self.features:
            PathLog.debug("_setFeatureValues() FeatureHeightsDepths")
            finish_step = obj.FinishDepth.Value if hasattr(obj, "FinishDepth") else 0.0
            step_down = (
                obj.StepDown.Value
                if (hasattr(obj, "StepDown") and obj.StepDown.Value > 0.0)
                else 1.0
            )
            PathLog.debug(
                "_setFeatureValues() FeatureHeightsDepths setting self.depthparams"
            )
            # self.printDepthParams(obj)
            self.depthparams = PathUtils.depth_params(
                clearance_height=obj.ClearanceHeight.Value,
                safe_height=obj.SafeHeight.Value,
                start_depth=obj.StartDepth.Value,
                step_down=step_down,
                z_finish_step=finish_step,
                final_depth=obj.FinalDepth.Value,
                user_depths=None,
            )
        PathLog.debug("_setFeatureValues() returning")

    def addBase(self, obj, base, sub):
        PathLog.track(obj, base, sub)
        base = PathUtil.getPublicObject(base)

        if self._setBaseAndStock(obj):
            for model in self.job.Model.Group:
                if base == self.job.Proxy.baseObject(self.job, model):
                    base = model
                    break

            baselist = obj.Base
            if baselist is None:
                baselist = []

            for p, el in baselist:
                if p == base and sub in el:
                    PathLog.notice(
                        (
                            translate("Path", "Base object %s.%s already in the list")
                            + "\n"
                        )
                        % (base.Label, sub)
                    )
                    return

            if not self.opRejectAddBase(obj, base, sub):
                baselist.append((base, sub))
                obj.Base = baselist
            else:
                PathLog.notice(
                    (
                        translate("Path", "Base object %s.%s rejected by operation")
                        + "\n"
                    )
                    % (base.Label, sub)
                )

    def addHole(self, obj, base, sub):
        PathLog.track(obj, base, sub)
        base = PathUtil.getPublicObject(base)

        if self._setBaseAndStock(obj):
            for model in self.job.Model.Group:
                if base == self.job.Proxy.baseObject(self.job, model):
                    base = model
                    break

            baselist = obj.Hole
            if baselist is None:
                baselist = []

            for p, el in baselist:
                if p == base and sub in el:
                    PathLog.notice(
                        (
                            translate("Path", "Base object %s.%s already in the list")
                            + "\n"
                        )
                        % (base.Label, sub)
                    )
                    return

            if not self.opRejectAddBase(obj, base, sub):
                baselist.append((base, sub))
                obj.Hole = baselist
            else:
                PathLog.notice(
                    (
                        translate("Path", "Base object %s.%s rejected by operation")
                        + "\n"
                    )
                    % (base.Label, sub)
                )

    def isToolSupported(self, obj, tool):
        """toolSupported(obj, tool) ... Returns true if the op supports the given tool.
        This function can safely be overwritten by subclasses."""

        return True

    def showRemovalShape(self):
        """showRemovalShape() ... Used to add a copy of the operation's removal shape to the object tree"""
        if hasattr(self.obj, "RemovalShape"):
            Part.show(self.obj.RemovalShape)
            FreeCAD.ActiveDocument.ActiveObject.Label = "RemovalShape_" + self.obj.Name
            FreeCAD.ActiveDocument.ActiveObject.purgeTouched()
        else:
            PathLog.info(translate("PathOp", "No removal shape property."))

    def showShape(self):
        """showRemovalShape() ... Used to add a copy of the operation's REST shape to the object tree"""
        if hasattr(self.obj, "Shape"):
            Part.show(self.obj.Shape)
            FreeCAD.ActiveDocument.ActiveObject.Label = "Shape_" + self.obj.Name
            FreeCAD.ActiveDocument.ActiveObject.purgeTouched()
        else:
            PathLog.info(translate("PathOp", "No removal shape property."))

    def printDepthParams(self, obj):
        PathLog.debug("printDepthParams()")
        for a in [
            "ClearanceHeight",
            "SafeHeight",
            "StartDepth",
            "StepDown",
            "FinishDepth",
            "FinalDepth",
        ]:
            if hasattr(obj, a):
                attr = getattr(obj, a)
                val = getattr(attr, "Value")
                PathLog.debug(f"obj.{a}: {val}")

    # Cleanup operation children upon op deletion
    def onDelete(self, obj, arg2=None):
        doc = obj.Document
        # base doesn't depend on anything inside op
        if hasattr(obj, "TargetShapeGroup"):
            if getattr(obj, "TargetShapeGroup", None):
                for base in obj.TargetShapeGroup.Group:
                    PathLog.debug("taking down target shapes %s" % base.Label)
                    obj.TargetShapeGroup.removeObject(base)
                    obj.Document.removeObject(base.Name)
                obj.TargetShapeGroup.Group = []
                doc.removeObject(obj.TargetShapeGroup.Name)
                obj.TargetShapeGroup = None
        # PathUtil.clearExpressionEngine(obj)
        pass

    # Working plane methods
    def _alignFaceToView(self, refFace):
        """_alignFaceToView(refFace)
        Copy of "Align_View_to_Face" macro in FreeCAD, with minor
        adaptation for this implementation"""
        # Set the current view perpendicular to the selected face
        # Place la vue perpendiculairement a la face selectionnee
        # 2013 Jonathan Wiedemann, 2016 Werner Mayer

        import FreeCADGui

        # from pivy import coin

        def pointAt(normal, up):
            z = normal
            y = up
            x = y.cross(z)
            y = z.cross(x)

            rot = FreeCAD.Matrix()
            rot.A11 = x.x
            rot.A21 = x.y
            rot.A31 = x.z

            rot.A12 = y.x
            rot.A22 = y.y
            rot.A32 = y.z

            rot.A13 = z.x
            rot.A23 = z.y
            rot.A33 = z.z

            return FreeCAD.Placement(rot).Rotation

        # s=FreeCADGui.Selection.getSelectionEx()
        # obj=s[0]
        # faceSel = obj.SubObjects[0]
        # dir = faceSel.normalAt(0,0)
        drctn = refFace.normalAt(0, 0)
        cam = FreeCADGui.ActiveDocument.ActiveView.getCameraNode()

        if drctn.z == 1:
            rot = pointAt(drctn, FreeCAD.Vector(0.0, 1.0, 0.0))
        elif drctn.z == -1:
            rot = pointAt(drctn, FreeCAD.Vector(0.0, 1.0, 0.0))
        else:
            rot = pointAt(drctn, FreeCAD.Vector(0.0, 0.0, 1.0))

        cam.orientation.setValue(rot.Q)
        FreeCADGui.SendMsgToActiveView("ViewSelection")

    def _getRotationCommands(self, obj, reverse=False):
        cmds = []
        if not hasattr(obj, "TargetShape"):
            return cmds

        if obj.TargetShape is None:
            return cmds

        rotations = obj.TargetShape.Proxy._getRotationsList(
            obj.TargetShape, mapped=True
        )
        if reverse:
            # useRotations = [(a, -1.0 * d) for a, d in rotations]
            # useRotations.reverse()
            useRotations = [(a, 0.0) for a, d in rotations]
        else:
            useRotations = rotations
            cmds.append(
                Path.Command(
                    "G0", {"Z": obj.ClearanceHeight.Value, "F": self.vertRapid}
                )
            )

        for axis, deg in useRotations:
            if not PathGeom.isRoughly(deg, 0.0):
                cmds.append(Path.Command("G1", {axis: deg, "F": self.vertFeed}))
        return cmds

    # Main public executable method called to complete the operation
    @waiting_effects
    def execute(self, obj):
        """execute(obj) ... base implementation - do not overwrite!
        Verifies that the operation is assigned to a job and that the job also has a valid Base.
        It also sets the following instance variables that can and should be safely be used by
        implementation of opExecute():
            self.model        ... List of base objects of the Job itself
            self.stock        ... Stock object for the Job itself
            self.vertFeed     ... vertical feed rate of assigned tool
            self.vertRapid    ... vertical rapid rate of assigned tool
            self.horizFeed    ... horizontal feed rate of assigned tool
            self.horizRapid   ... norizontal rapid rate of assigned tool
            self.tool         ... the actual tool being used
            self.radius       ... the main radius of the tool being used
            self.commandlist  ... a list for collecting all commands produced by the operation

        Once everything is validated and above variables are set the implementation calls
        opExecute(obj) - which is expected to add the generated commands to self.commandlist
        Finally the base implementation adds a rapid move to clearance height and assigns
        the receiver's Path property from the command list.
        """
        PathLog.track()

        if not obj.Active:
            path = Path.Path("(inactive target shape)")
            obj.Path = path
            return

        if obj.ShowShape and obj.Shape:
            showShape(obj)
            return

        if not self._setBaseAndStock(obj):
            return

        self.commandlist = []

        # make sure Base is still valid or clear it
        self.sanitizeBase(obj)

        # Set feature-specific values for instance and object variables
        self._setFeatureValues(obj)

        self.updateDepths(obj)
        # now that all op values are set make sure the user properties get updated accordingly,
        # in case they still have an expression referencing any op values
        obj.recompute()

        result = self.opExecute(obj)  # pylint: disable=assignment-from-no-return

        # obj.Path must be of type `Path`, so an empty list is passed if no Path data desired
        obj.Path = Path.Path(self.commandlist)

        if obj.ShowShape and obj.Shape:
            showShape(obj)

        return result

    # Temporary placeholder methods designed to be overwritten by child classes
    def __getstate__(self):
        """__getstat__(self) ... called when receiver is saved.
        Can safely be overwritten by subclasses."""
        return None

    def __setstate__(self, state):
        """__getstat__(self) ... called when receiver is restored.
        Can safely be overwritten by subclasses."""
        return None

    def opFeatures(self, obj):
        """opFeatures(obj) ... returns the OR'ed list of features used and supported by the operation.
        The default implementation returns
        "FeatureTool | FeatureHeightsDepths | FeatureStartPoint | FeatureBaseGeometry | FeatureFinishDepth | FeatureCoolant"
        Should be overwritten by subclasses."""
        # pylint: disable=unused-argument
        return (
            FeatureTool
            | FeatureHeightsDepths
            | FeatureStartPoint
            | FeatureBaseGeometry
            | FeatureFinishDepth
            | FeatureCoolant
        )

    def initOperation(self, obj):
        """initOperation(obj) ... implement to create additional properties.
        Should be overwritten by subclasses."""
        pass  # pylint: disable=unnecessary-pass

    def opPropertyDefinitions(self):
        """opPropertyDefinitions() ... Returns operation-specific property definitions in a list.
        Should be overwritten by subclasses."""
        return list()

    def opPropertyEnumerations(self):
        """opPropertyEnumerations() ... Returns operation-specific property enumeration lists as a dictionary.
        Each property name is a key and the enumeration list is the value.
        Should be overwritten by subclasses."""
        # Enumeration lists for App::PropertyEnumeration properties
        return {}

    def opPropertyDefaults(self, obj, job):
        """opPropertyDefaults(obj, job) ... Returns operation-specific default property values as a dictionary.
        Each property name is a key paired with its default value.
        Should be overwritten by subclasses."""
        return dict()

    def opOnDocumentRestored(self, obj):
        """opOnDocumentRestored(obj) ... implement if an op needs special handling like migrating the data model.
        Should be overwritten by subclasses."""
        pass  # pylint: disable=unnecessary-pass

    def opSetEditorModes(self, obj):
        """opSetEditorModes(obj) ... Implement to set custom property editor modes for the operation.
        Should be overwritten by subclasses."""
        pass  # pylint: disable=unnecessary-pass

    def opOnChanged(self, obj, prop):
        """opOnChanged(obj, prop) ... overwrite to process property changes.
        This is a callback function that is invoked each time a property of the
        receiver is assigned a value. Note that the FC framework does not
        distinguish between assigning a different value and assigning the same
        value again.
        Can safely be overwritten by subclasses."""
        pass  # pylint: disable=unnecessary-pass

    def opSetDefaultValues(self, obj, job):
        """opSetDefaultValues(obj, job) ... overwrite to set initial default values.
        Called after the receiver has been fully created with all properties.
        Can safely be overwritten by subclasses."""
        pass  # pylint: disable=unnecessary-pass

    def opUpdateDepths(self, obj):
        """opUpdateDepths(obj) ... overwrite to implement special depths calculation.
        Can safely be overwritten by subclass."""
        pass  # pylint: disable=unnecessary-pass

    def opExecute(self, obj):
        """opExecute(obj) ... called whenever the receiver needs to be recalculated.
        See documentation of execute() for a list of base functionality provided.
        Should be overwritten by subclasses."""
        pass  # pylint: disable=unnecessary-pass

    def opRejectAddBase(self, obj, base, sub):
        """opRejectAddBase(base, sub) ... if op returns True the addition of the feature is prevented.
        Should be overwritten by subclasses."""
        # pylint: disable=unused-argument
        return False

    def getTargetShape(self, obj, isPreview=False):
        """getTargetShape(obj, isPreview=False) ...
        Return list of shapes to be proccessed by selected op strategy.
        Should be overwritten by subclasses.
        When overwriting, it will likely need a call to `_setMisingClassVariables()` if you
        plan to preview the working shape in the viewport."""
        pass


def showShape(obj):
    obj.ShowShape = False  # Reset boolean
    name = obj.Name + "_Shape"
    # if hasattr(FreeCAD.ActiveDocument, name):
    #    # Remove existing version of obj.Shape in object tree
    #    FreeCAD.ActiveDocument.removeObject(name)
    shpObj = Part.show(obj.Shape, name)
    shpObj.purgeTouched()
