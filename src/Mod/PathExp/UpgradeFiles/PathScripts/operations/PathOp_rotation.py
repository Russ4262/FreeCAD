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

import FreeCAD

from PySide import QtCore

import Path
import PathScripts.PathGeom as PathGeom
import PathScripts.PathLog as PathLog
import PathScripts.PathPreferences as PathPreferences
import PathScripts.PathUtil as PathUtil
import PathScripts.PathUtils as PathUtils
from PathScripts.PathUtils import waiting_effects
from PySide import QtCore
import time
import math

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader

Part = LazyLoader("Part", globals(), "Part")

__title__ = "Base class for all operations."
__author__ = "sliptonic (Brad Collette)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Base class and properties implementation for all Path operations."

PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule()


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


FeatureTool = 0x0001  # ToolController
FeatureDepths = 0x0002  # FinalDepth, StartDepth
FeatureHeights = 0x0004  # ClearanceHeight, SafeHeight
FeatureStartPoint = 0x0008  # StartPoint
FeatureFinishDepth = 0x0010  # FinishDepth
FeatureStepDown = 0x0020  # StepDown
FeatureNoFinalDepth = 0x0040  # edit or not edit FinalDepth
FeatureBaseVertexes = 0x0100  # Base
FeatureBaseEdges = 0x0200  # Base
FeatureBaseFaces = 0x0400  # Base
FeatureBasePanels = 0x0800  # Base
FeatureLocations = 0x1000  # Locations
FeatureCoolant = 0x2000  # Coolant
FeatureDiameters = 0x4000  # Turning Diameters
FeatureRotation = 0x8000  # Rotation
FeatureFixedRotation = 0x10000  # Feature Working Plane

FeatureBaseGeometry = (
    FeatureBaseVertexes | FeatureBaseFaces | FeatureBaseEdges | FeatureBasePanels
)


class ObjectOp(object):
    """
    Base class for proxy objects of all Path operations.

    Use this class as a base class for new operations. It provides properties
    and some functionality for the standard properties each operation supports.
    By OR'ing features from the feature list an operation can select which ones
    of the standard features it requires and/or supports.

    The currently supported features are:
        FeatureTool          ... Use of a ToolController
        FeatureDepths        ... Depths, for start, final
        FeatureHeights       ... Heights, safe and clearance
        FeatureStartPoint    ... Supports setting a start point
        FeatureFinishDepth   ... Operation supports a finish depth
        FeatureStepDown      ... Support for step down
        FeatureNoFinalDepth  ... Disable support for final depth modifications
        FeatureBaseVertexes  ... Base geometry support for vertexes
        FeatureBaseEdges     ... Base geometry support for edges
        FeatureBaseFaces     ... Base geometry support for faces
        FeatureBasePanels    ... Base geometry support for Arch.Panels
        FeatureLocations     ... Base location support
        FeatureCoolant       ... Support for operation coolant
        FeatureRotation      ... Rotation support (4th-axis)
        FeatureFixedRotation  ... operation's Working Plane
        FeatureDiameters     ... Support for turning operation diameters

    The base class handles all base API and forwards calls to subclasses with
    an op prefix. For instance, an op is not expected to overwrite onChanged(),
    but implement the function opOnChanged().
    If a base class overwrites a base API function it should call the super's
    implementation - otherwise the base functionality might be broken.
    """

    def addBaseProperty(self, obj):
        obj.addProperty(
            "App::PropertyLinkSubListGlobal",
            "Base",
            "Path",
            QtCore.QT_TRANSLATE_NOOP("PathOp", "The base geometry for this operation"),
        )

    def addOpValues(self, obj, values):
        if "start" in values:
            obj.addProperty(
                "App::PropertyDistance",
                "OpStartDepth",
                "Op Values",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp", "Holds the calculated value for the StartDepth"
                ),
            )
            obj.setEditorMode("OpStartDepth", 1)  # read-only
        if "final" in values:
            obj.addProperty(
                "App::PropertyDistance",
                "OpFinalDepth",
                "Op Values",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp", "Holds the calculated value for the FinalDepth"
                ),
            )
            obj.setEditorMode("OpFinalDepth", 1)  # read-only
        if "tooldia" in values:
            obj.addProperty(
                "App::PropertyDistance",
                "OpToolDiameter",
                "Op Values",
                QtCore.QT_TRANSLATE_NOOP("PathOp", "Holds the diameter of the tool"),
            )
            obj.setEditorMode("OpToolDiameter", 1)  # read-only
        if "stockz" in values:
            obj.addProperty(
                "App::PropertyDistance",
                "OpStockZMax",
                "Op Values",
                QtCore.QT_TRANSLATE_NOOP("PathOp", "Holds the max Z value of Stock"),
            )
            obj.setEditorMode("OpStockZMax", 1)  # read-only
            obj.addProperty(
                "App::PropertyDistance",
                "OpStockZMin",
                "Op Values",
                QtCore.QT_TRANSLATE_NOOP("PathOp", "Holds the min Z value of Stock"),
            )
            obj.setEditorMode("OpStockZMin", 1)  # read-only

    def __init__(self, obj, name):
        PathLog.track()

        # members being set later
        self.commandlist = None
        self.job = None
        self.model = None
        self.radius = None
        self.stock = None
        self.tool = None
        self.depthparams = None
        self.horizFeed = None
        self.horizRapid = None
        self.vertFeed = None
        self.vertRapid = None
        self.axialFeed = None
        self.axialRapid = None
        self.addNewProps = None

        features = self.opFeatures(obj)  # Get features requested by the operation
        job = PathUtils.addToJob(obj)  # Some properties are dependent on Job settings

        # Add properties based on operation's features
        obj.addProperty(
            "App::PropertyBool",
            "Active",
            "Path",
            QtCore.QT_TRANSLATE_NOOP(
                "PathOp", "Make False, to prevent operation from generating code"
            ),
        )
        obj.addProperty(
            "App::PropertyString",
            "Comment",
            "Path",
            QtCore.QT_TRANSLATE_NOOP(
                "PathOp", "An optional comment for this Operation"
            ),
        )
        obj.addProperty(
            "App::PropertyString",
            "UserLabel",
            "Path",
            QtCore.QT_TRANSLATE_NOOP("PathOp", "User Assigned Label"),
        )
        obj.addProperty(
            "App::PropertyString",
            "CycleTime",
            "Path",
            QtCore.QT_TRANSLATE_NOOP("PathOp", "Operations Cycle Time Estimation"),
        )
        obj.setEditorMode("CycleTime", 1)  # read-only

        if FeatureBaseGeometry & features:
            self.addBaseProperty(obj)

        if FeatureLocations & features:
            obj.addProperty(
                "App::PropertyVectorList",
                "Locations",
                "Path",
                QtCore.QT_TRANSLATE_NOOP("PathOp", "Base locations for this operation"),
            )

        if FeatureTool & features:
            obj.addProperty(
                "App::PropertyLink",
                "ToolController",
                "Path",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp",
                    "The tool controller that will be used to calculate the path",
                ),
            )
            obj.addProperty(
                "App::PropertyFloat",
                "FeedRateFactor",
                "Path",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp",
                    "Feed rate adjustment factor for the assigned Tool Controller.",
                ),
            )
            self.addOpValues(obj, ["tooldia"])

        if FeatureCoolant & features:
            obj.addProperty(
                "App::PropertyString",
                "CoolantMode",
                "Path",
                QtCore.QT_TRANSLATE_NOOP("PathOp", "Coolant mode for this operation"),
            )

        if FeatureDepths & features:
            obj.addProperty(
                "App::PropertyDistance",
                "StartDepth",
                "Depth",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp", "Starting Depth of Tool- first cut depth in Z"
                ),
            )
            obj.addProperty(
                "App::PropertyDistance",
                "FinalDepth",
                "Depth",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp", "Final Depth of Tool- lowest value in Z"
                ),
            )
            if FeatureNoFinalDepth & features:
                obj.setEditorMode("FinalDepth", 2)  # hide
            self.addOpValues(obj, ["start", "final"])
        else:
            # StartDepth has become necessary for expressions on other properties
            obj.addProperty(
                "App::PropertyDistance",
                "StartDepth",
                "Depth",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp", "Starting Depth internal use only for derived values"
                ),
            )
            obj.setEditorMode("StartDepth", 1)  # read-only

        self.addOpValues(obj, ["stockz"])

        if FeatureStepDown & features:
            obj.addProperty(
                "App::PropertyDistance",
                "StepDown",
                "Depth",
                QtCore.QT_TRANSLATE_NOOP("PathOp", "Incremental Step Down of Tool"),
            )

        if FeatureFinishDepth & features:
            obj.addProperty(
                "App::PropertyDistance",
                "FinishDepth",
                "Depth",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp", "Maximum material removed on final pass."
                ),
            )

        if FeatureHeights & features:
            obj.addProperty(
                "App::PropertyDistance",
                "ClearanceHeight",
                "Depth",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp", "The height needed to clear clamps and obstructions"
                ),
            )
            obj.addProperty(
                "App::PropertyDistance",
                "SafeHeight",
                "Depth",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp", "Rapid Safety Height between locations."
                ),
            )

        if FeatureStartPoint & features:
            obj.addProperty(
                "App::PropertyVectorDistance",
                "StartPoint",
                "Start Point",
                QtCore.QT_TRANSLATE_NOOP("PathOp", "The start point of this path"),
            )
            obj.addProperty(
                "App::PropertyBool",
                "UseStartPoint",
                "Start Point",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp", "Make True, if specifying a Start Point"
                ),
            )

        if FeatureDiameters & features:
            obj.addProperty(
                "App::PropertyDistance",
                "MinDiameter",
                "Diameter",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp", "Lower limit of the turning diameter"
                ),
            )
            obj.addProperty(
                "App::PropertyDistance",
                "MaxDiameter",
                "Diameter",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp", "Upper limit of the turning diameter."
                ),
            )

        # members being set later
        self.commandlist = None
        self.horizFeed = None
        self.horizRapid = None
        self.job = None
        self.model = None
        self.radius = None
        self.stock = None
        self.tool = None
        self.vertFeed = None
        self.vertRapid = None
        self.addNewProps = None
        # Only add properties to operation if EnableRotation set at Job level
        canDoRotation = False
        if hasattr(job, "EnableRotation"):
            canDoRotation = job.EnableRotation
        if canDoRotation:
            if FeatureFixedRotation & features:
                if not hasattr(obj, "EnableRotation"):
                    obj.addProperty(
                        "App::PropertyEnumeration",
                        "EnableRotation",
                        "Rotation",
                        QtCore.QT_TRANSLATE_NOOP(
                            "App::Property",
                            "Enable rotation to gain access to pockets/areas not normal to Z axis.",
                        ),
                    )
                    obj.EnableRotation = ["Off", "A(x)", "B(y)", "A & B"]
                obj.addProperty(
                    "App::PropertyVectorDistance",
                    "CustomPlaneBase",
                    "FixedIndexRotation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "Path", "Initial base.Placement.Base values for model."
                    ),
                )
                obj.addProperty(
                    "App::PropertyVector",
                    "CustomPlaneAxis",
                    "FixedIndexRotation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "Path", "Initial base.Placement.Rotation.Axis values for model."
                    ),
                )
                obj.addProperty(
                    "App::PropertyFloat",
                    "CustomPlaneAngle",
                    "FixedIndexRotation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "Path", "Initial base.Placement.Rotation.Angle value for model."
                    ),
                )
                obj.addProperty(
                    "App::PropertyEnumeration",
                    "MillIndexAxis",
                    "FixedIndexRotation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "Path", "Axis of rotation on the mill machine (read-only)."
                    ),
                )
                obj.addProperty(
                    "App::PropertyBool",
                    "InvertIndexRotation",
                    "FixedIndexRotation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "Path", "Invert the angle of the fixed index."
                    ),
                )
                obj.addProperty(
                    "App::PropertyBool",
                    "OppositeIndexAngle",
                    "FixedIndexRotation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "Path", "Reverse the angle of the fixed index."
                    ),
                )
                obj.addProperty(
                    "App::PropertyInteger",
                    "FaceOnReferenceObject",
                    "FixedIndexRotation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "Path",
                        "Face number on FixedIndexReference used to determining the fixed index.",
                    ),
                )
                obj.addProperty(
                    "App::PropertyEnumeration",
                    "FixedIndexReference",
                    "FixedIndexRotation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "Path", "Choose a working plane reference method or object."
                    ),
                )
                obj.addProperty(
                    "App::PropertyFloat",
                    "VerticalIndexOffset",
                    "FixedIndexRotation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "Path",
                        "Vertical angle offest to apply to selected working plane [+/- 360 degrees].",
                    ),
                )
                obj.addProperty(
                    "App::PropertyEnumeration",
                    "ResetIndexTo",
                    "FixedIndexRotation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "Path",
                        "Reset model to selected orientation after operation execution.",
                    ),
                )
                obj.addProperty(
                    "App::PropertyBool",
                    "VisualizeFixedIndex",
                    "FixedIndexRotation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "Path", "Display working plane in viewport."
                    ),
                )

                WPBO = []
                for O in FreeCAD.ActiveDocument.Objects:
                    if O.isDerivedFrom("PartDesign::Body") and not hasattr(
                        O, "InitBase"
                    ):
                        WPBO.append("__" + O.Name)
                    # elif O.isDerivedFrom('Part::FeaturePython') and not hasattr(O, 'InitBase'):
                    #    WPBO.append('__' + O.Name)
                    elif O.isDerivedFrom("Part::Feature") and not hasattr(
                        O, "InitBase"
                    ):
                        WPBO.append("__" + O.Name)
                WPBO.sort()
                obj.FixedIndexReference = [
                    "None",
                    "Previous",
                    "Custom Plane",
                    "First Base Geometry",
                ] + WPBO
                obj.ResetIndexTo = ["Initial", "Previous", "None"]
                obj.MillIndexAxis = ["A", "B", "C"]

            if FeatureRotation & features:
                if not hasattr(obj, "EnableRotation"):
                    obj.addProperty(
                        "App::PropertyEnumeration",
                        "EnableRotation",
                        "Rotation",
                        QtCore.QT_TRANSLATE_NOOP(
                            "App::Property",
                            "Enable rotation to gain access to pockets/areas not normal to Z axis.",
                        ),
                    )
                    obj.EnableRotation = ["Off", "A(x)", "B(y)", "A & B"]
                obj.addProperty(
                    "App::PropertyBool",
                    "ReverseDirection",
                    "Rotation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "App::Property", "Reverse direction of pocket operation."
                    ),
                )
                obj.addProperty(
                    "App::PropertyBool",
                    "InverseAngle",
                    "Rotation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "App::Property",
                        "Inverse the angle. Example: -22.5 -> 22.5 degrees.",
                    ),
                )
                obj.addProperty(
                    "App::PropertyBool",
                    "AttemptInverseAngle",
                    "Rotation",
                    QtCore.QT_TRANSLATE_NOOP(
                        "App::Property",
                        "Attempt the inverse angle for face access if original rotation fails.",
                    ),
                )

        # Process operation-specific __init__() related statements
        self.initOperation(obj)

        if not hasattr(obj, "DoNotSetDefaultValues") or not obj.DoNotSetDefaultValues:
            if self.setDefaultValues(job, obj):
                job.SetupSheet.Proxy.setOperationProperties(obj, name)
                obj.recompute()
                obj.Proxy = self

        self.setEditorModes(obj, features)

    def setEditorModes(self, obj, features):
        """Editor modes are not preserved during document store/restore, set editor modes for all properties"""

        for op in ["OpStartDepth", "OpFinalDepth", "OpToolDiameter", "CycleTime"]:
            if hasattr(obj, op):
                obj.setEditorMode(op, 1)  # read-only

        if FeatureDepths & features:
            if FeatureNoFinalDepth & features:
                obj.setEditorMode("OpFinalDepth", 2)

        if FeatureFixedRotation & features:
            obj.setEditorMode("EnableRotation", 1)
            obj.setEditorMode("MillIndexAxis", 2)
            self.updateFeatureFixedRotationEditorModes(obj, "FixedIndexReference")

        if FeatureRotation & features:
            obj.setEditorMode("EnableRotation", 1)

    def onDocumentRestored(self, obj):
        features = self.opFeatures(obj)
        if (
            FeatureBaseGeometry & features
            and "App::PropertyLinkSubList" == obj.getTypeIdOfProperty("Base")
        ):
            PathLog.info("Replacing link property with global link (%s)." % obj.State)
            base = obj.Base
            obj.removeProperty("Base")
            self.addBaseProperty(obj)
            obj.Base = base
            obj.touch()
            obj.Document.recompute()

        if FeatureTool & features and not hasattr(obj, "OpToolDiameter"):
            self.addOpValues(obj, ["tooldia"])

        if FeatureCoolant & features and not hasattr(obj, "CoolantMode"):
            obj.addProperty(
                "App::PropertyString",
                "CoolantMode",
                "Path",
                QtCore.QT_TRANSLATE_NOOP("PathOp", "Coolant option for this operation"),
            )

        if FeatureDepths & features and not hasattr(obj, "OpStartDepth"):
            self.addOpValues(obj, ["start", "final"])
            if FeatureNoFinalDepth & features:
                obj.setEditorMode("OpFinalDepth", 2)

        if not hasattr(obj, "OpStockZMax"):
            self.addOpValues(obj, ["stockz"])

        if not hasattr(obj, "CycleTime"):
            obj.addProperty(
                "App::PropertyString",
                "CycleTime",
                "Path",
                QtCore.QT_TRANSLATE_NOOP("PathOp", "Operations Cycle Time Estimation"),
            )

        if not hasattr(obj, "FeedRateFactor"):
            obj.addProperty(
                "App::PropertyFloat",
                "FeedRateFactor",
                "Path",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathOp",
                    "Feed rate adjustment factor for the assigned Tool Controller.",
                ),
            )

        self.setEditorModes(obj, features)
        self.opOnDocumentRestored(obj)

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
        The default implementation returns "FeatureTool | FeatureDepths | FeatureHeights | FeatureStartPoint"
        Should be overwritten by subclasses."""
        # pylint: disable=unused-argument
        return (
            FeatureTool
            | FeatureDepths
            | FeatureHeights
            | FeatureStartPoint
            | FeatureBaseGeometry
            | FeatureFinishDepth
            | FeatureCoolant
            | FeatureFixedRotation
        )

    def initOperation(self, obj):
        """initOperation(obj) ... implement to create additional properties.
        Should be overwritten by subclasses."""
        pass  # pylint: disable=unnecessary-pass

    def opOnDocumentRestored(self, obj):
        """opOnDocumentRestored(obj) ... implement if an op needs special handling like migrating the data model.
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

        if prop == "FixedIndexReference":
            self.updateFeatureFixedRotationEditorModes(obj, prop)
        elif prop == "FeedRateFactor":
            if obj.FeedRateFactor < 1:
                obj.FeedRateFactor = 1
            elif obj.FeedRateFactor > 200:
                obj.FeedRateFactor = 200

        self.opOnChanged(obj, prop)

    def applyExpression(self, obj, prop, expr):
        """applyExpression(obj, prop, expr) ... set expression expr on obj.prop if expr is set"""
        if expr:
            obj.setExpression(prop, expr)
            return True
        return False

    def setDefaultValues(self, job, obj):
        """setDefaultValues(job, obj) ... base implementation.
        Do not overwrite, overwrite opSetDefaultValues() instead."""
        # job = PathUtils.addToJob(obj)

        obj.Active = True

        features = self.opFeatures(obj)

        if FeatureTool & features:
            if 1 < len(job.Operations.Group):
                obj.ToolController = PathUtil.toolControllerForOp(
                    job.Operations.Group[-2]
                )
            else:
                obj.ToolController = PathUtils.findToolController(obj, self)
            if not obj.ToolController:
                return None
            obj.OpToolDiameter = obj.ToolController.Tool.Diameter
            obj.FeedRateFactor = 1.0

        if FeatureCoolant & features:
            obj.CoolantMode = job.SetupSheet.CoolantMode

        if FeatureDepths & features:
            if self.applyExpression(
                obj, "StartDepth", job.SetupSheet.StartDepthExpression
            ):
                obj.OpStartDepth = 1.0
            else:
                obj.StartDepth = 1.0
            if self.applyExpression(
                obj, "FinalDepth", job.SetupSheet.FinalDepthExpression
            ):
                obj.OpFinalDepth = 0.0
            else:
                obj.FinalDepth = 0.0
        else:
            obj.StartDepth = 1.0

        if FeatureStepDown & features:
            if not self.applyExpression(
                obj, "StepDown", job.SetupSheet.StepDownExpression
            ):
                obj.StepDown = "1 mm"

        if FeatureHeights & features:
            if job.SetupSheet.SafeHeightExpression:
                if not self.applyExpression(
                    obj, "SafeHeight", job.SetupSheet.SafeHeightExpression
                ):
                    obj.SafeHeight = "3 mm"
            if job.SetupSheet.ClearanceHeightExpression:
                if not self.applyExpression(
                    obj, "ClearanceHeight", job.SetupSheet.ClearanceHeightExpression
                ):
                    obj.ClearanceHeight = "5 mm"

        if FeatureDiameters & features:
            obj.MinDiameter = "0 mm"
            obj.MaxDiameter = "0 mm"
            if job.Stock:
                obj.MaxDiameter = job.Stock.Shape.BoundBox.XLength

        if FeatureStartPoint & features:
            obj.UseStartPoint = False

        canDoRotation = False
        if hasattr(job, "EnableRotation"):
            canDoRotation = job.EnableRotation
        if FeatureFixedRotation & features and canDoRotation:
            obj.EnableRotation = job.EnableRotation
            obj.CustomPlaneAngle = 0.0
            obj.CustomPlaneAxis = FreeCAD.Vector(0, 0, 0)
            obj.CustomPlaneBase = FreeCAD.Vector(0, 0, 0)
            obj.VisualizeFixedIndex = True
            obj.InvertIndexRotation = False
            obj.OppositeIndexAngle = False
            obj.ResetIndexTo = "Initial"
            obj.VerticalIndexOffset = 0.0
            obj.FixedIndexReference = "None"
            obj.FaceOnReferenceObject = 0
            obj.MillIndexAxis = "A"

        if FeatureRotation & features and canDoRotation:
            obj.EnableRotation = job.EnableRotation
            obj.ReverseDirection = False
            obj.InverseAngle = False
            obj.AttemptInverseAngle = False

        self.opSetDefaultValues(obj, job)
        # self.setEditorModes(obj, features)
        return True

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

    def getJob(self, obj):
        """getJob(obj) ... return the job this operation is part of."""
        if not hasattr(self, "job") or self.job is None:
            if not self._setBaseAndStock(obj):
                return None
        return self.job

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

        if FeatureDepths & self.opFeatures(obj):
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

    def sanitizeBase(self, obj):
        """sanitizeBase(obj) ... check if Base is valid and clear on errors."""
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

    def updateFeatureFixedRotationEditorModes(self, obj, prop):
        if prop == "FixedIndexReference" and hasattr(obj, "FixedIndexReference"):
            if obj.FixedIndexReference == "None":
                obj.setEditorMode("CustomPlaneAngle", 0)
                obj.setEditorMode("CustomPlaneAxis", 0)
                obj.setEditorMode("CustomPlaneBase", 2)  # hidden, no editing
                obj.setEditorMode("VisualizeFixedIndex", 2)
                obj.setEditorMode("InvertIndexRotation", 2)
                obj.setEditorMode("OppositeIndexAngle", 2)
                obj.setEditorMode("VerticalIndexOffset", 2)
                obj.setEditorMode("FaceOnReferenceObject", 2)
                obj.setEditorMode("ResetIndexTo", 2)
            if obj.FixedIndexReference == "Custom Plane":
                obj.setEditorMode("CustomPlaneAngle", 0)
                obj.setEditorMode("CustomPlaneAxis", 0)
                obj.setEditorMode("CustomPlaneBase", 2)  # hidden, no editing
                obj.setEditorMode("VisualizeFixedIndex", 0)
                obj.setEditorMode("InvertIndexRotation", 0)
                obj.setEditorMode("OppositeIndexAngle", 0)
                obj.setEditorMode("VerticalIndexOffset", 0)
                obj.setEditorMode("FaceOnReferenceObject", 2)
                obj.setEditorMode("ResetIndexTo", 0)
            if obj.FixedIndexReference == "Previous":
                obj.setEditorMode("CustomPlaneAngle", 1)
                obj.setEditorMode("CustomPlaneAxis", 1)
                obj.setEditorMode("CustomPlaneBase", 2)  # hidden, no editing
                obj.setEditorMode("VisualizeFixedIndex", 0)
                obj.setEditorMode("InvertIndexRotation", 2)
                obj.setEditorMode("OppositeIndexAngle", 2)
                obj.setEditorMode("VerticalIndexOffset", 2)
                obj.setEditorMode("FaceOnReferenceObject", 2)
                obj.setEditorMode("ResetIndexTo", 0)
            if obj.FixedIndexReference not in ["None", "Previous", "Custom Plane"]:
                obj.setEditorMode("CustomPlaneAngle", 1)
                obj.setEditorMode("CustomPlaneAxis", 1)
                obj.setEditorMode("CustomPlaneBase", 2)  # hidden, no editing
                obj.setEditorMode("VisualizeFixedIndex", 2)
                obj.setEditorMode("InvertIndexRotation", 0)
                obj.setEditorMode("OppositeIndexAngle", 0)
                obj.setEditorMode("VerticalIndexOffset", 0)
                obj.setEditorMode("FaceOnReferenceObject", 0)
                obj.setEditorMode("ResetIndexTo", 0)

    # Rotation-related methods
    def opDetermineRotationRadii(self, Job, obj, stock=None):
        """opDetermineRotationRadii(obj)
        Determine rotational radii for 4th-axis rotations, for clearance/safe heights"""

        # Job = PathUtils.findParentJob(obj)
        # bb = parentJob.Stock.Shape.BoundBox
        xlim = 0.0
        ylim = 0.0
        # zlim = 0.0
        if stock is None:
            stockBB = Job.Stock.Shape.BoundBox
        else:
            stockBB = stock.Shape.BoundBox

        # Determine boundbox radius based upon xzy limits data
        if abs(stockBB.ZMin) > abs(stockBB.ZMax):
            zlim = stockBB.ZMin
        else:
            zlim = stockBB.ZMax

        if obj.EnableRotation != "B(y)":
            # Rotation is around X-axis, cutter moves along same axis
            if abs(stockBB.YMin) > abs(stockBB.YMax):
                ylim = stockBB.YMin
            else:
                ylim = stockBB.YMax

        if obj.EnableRotation != "A(x)":
            # Rotation is around Y-axis, cutter moves along same axis
            if abs(stockBB.XMin) > abs(stockBB.XMax):
                xlim = stockBB.XMin
            else:
                xlim = stockBB.XMax

        xRotRad = math.sqrt(ylim ** 2 + zlim ** 2)
        yRotRad = math.sqrt(xlim ** 2 + zlim ** 2)
        zRotRad = math.sqrt(xlim ** 2 + ylim ** 2)

        clrOfst = Job.SetupSheet.ClearanceHeightOffset.Value
        safOfst = Job.SetupSheet.SafeHeightOffset.Value

        return [(xRotRad, yRotRad, zRotRad), (clrOfst, safOfst)]

    def _getFaceNormAndSurf(self, face):
        """_getFaceNormAndSurf(face)
        Return face.normalAt(0,0) or face.normal(0,0) and face.Surface.Axis vectors
        """
        n = None
        s = None
        norm = FreeCAD.Vector(0.0, 0.0, 0.0)
        surf = FreeCAD.Vector(0.0, 0.0, 0.0)

        if hasattr(face, "normalAt"):
            n = face.normalAt(0, 0)
        elif hasattr(face, "normal"):
            n = face.normal(0, 0)
        if hasattr(face.Surface, "Axis"):
            s = face.Surface.Axis
        else:
            s = n

        if n is not None and s is not None:
            norm.x = n.x
            norm.y = n.y
            norm.z = n.z
            surf.x = s.x
            surf.y = s.y
            surf.z = s.z
            return (norm, surf)
        else:
            PathLog.error("PathAreaOp._getFaceNormAndSurf()")
            return (None, None)

    def faceRotationAnalysis(self, enabRot, norm, surf, revDir):
        """faceRotationAnalysis(enabRot, norm, surf, revDir)
        Determine X and Y independent rotation necessary to make normalAt = Z=1 (0,0,1)"""
        PathLog.track()

        praInfo = "faceRotationAnalysis()"
        rtn = True
        orientation = "X"
        angle = 500.0
        precision = 6

        for i in range(0, 13):
            if PathGeom.Tolerance * (i * 10) == 1.0:
                precision = i
                break

        def roundRoughValues(precision, val):
            # Convert VALxe-15 numbers to zero
            if PathGeom.isRoughly(0.0, val) is True:
                return 0.0
            # Convert VAL.99999999 to next integer
            elif abs(val % 1) > 1.0 - PathGeom.Tolerance:
                return round(val)
            else:
                return round(val, precision)

        nX = roundRoughValues(precision, norm.x)
        nY = roundRoughValues(precision, norm.y)
        nZ = roundRoughValues(precision, norm.z)
        praInfo += "\n -normalAt(0,0): " + str(nX) + ", " + str(nY) + ", " + str(nZ)

        surf = norm
        saX = roundRoughValues(precision, surf.x)
        saY = roundRoughValues(precision, surf.y)
        saZ = roundRoughValues(precision, surf.z)
        praInfo += "\n -Surface.Axis: " + str(saX) + ", " + str(saY) + ", " + str(saZ)

        # Determine rotation needed and current orientation
        if saX == 0.0:
            praInfo += "_X=0"
            if saY == 0.0:
                praInfo += "_Z=0"
                orientation = "Z"
                if saZ == 1.0:
                    angle = 0.0
                elif saZ == -1.0:
                    angle = -180.0
                else:
                    praInfo += "_else_X" + str(saZ)
            elif saY == 1.0:
                orientation = "Y"
                angle = 90.0
            elif saY == -1.0:
                orientation = "Y"
                angle = -90.0
            else:
                if saZ != 0.0:
                    angle = math.degrees(math.atan(saY / saZ))
                    orientation = "Y"
        elif saY == 0.0:
            praInfo += "_Y=0"
            if saZ == 0.0:
                praInfo += "_Z=0"
                orientation = "X"
                if saX == 1.0:
                    angle = -90.0
                elif saX == -1.0:
                    angle = 90.0
                else:
                    praInfo += "_else_X" + str(saX)
            else:
                orientation = "X"
                ratio = saX / saZ
                angle = math.degrees(math.atan(ratio))
                if ratio < 0.0:
                    praInfo += " NEG-ratio"
                    # angle -= 90
                else:
                    praInfo += " POS-ratio"
                    angle = -1 * angle
                    if saX < 0.0:
                        angle = angle + 180.0
        elif saZ == 0.0:
            praInfo += "_Z=0"
            # if saY != 0.0:
            angle = math.degrees(math.atan(saX / saY))
            orientation = "Y"

        if saX + nX == 0.0:
            angle = -1 * angle
        if saY + nY == 0.0:
            angle = -1 * angle
        if saZ + nZ == 0.0:
            angle = -1 * angle

        if saY == -1.0 or saY == 1.0:
            if nX != 0.0:
                angle = -1 * angle

        # Enforce enabled rotation in settings
        praInfo += "\n -Initial orientation:  {}".format(orientation)
        if orientation == "Y":
            axis = "X"
            if enabRot == "B(y)":  # Required axis disabled
                if angle == 180.0 or angle == -180.0:
                    axis = "Y"
                else:
                    rtn = False
        elif orientation == "X":
            axis = "Y"
            if enabRot == "A(x)":  # Required axis disabled
                if angle == 180.0 or angle == -180.0:
                    axis = "X"
                else:
                    rtn = False
        elif orientation == "Z":
            axis = "X"

        if abs(angle) == 0.0:
            angle = 0.0
            rtn = False

        if angle == 500.0:
            angle = 0.0
            rtn = False

        if rtn is False:  # Handle special case when only 'B' axis enabled
            if orientation == "Z" and angle == 0.0 and revDir is True:
                if enabRot == "B(y)":
                    axis = "Y"
                rtn = True

        if rtn is True:
            if revDir is True:
                if angle < 180.0:
                    angle = angle + 180.0
                else:
                    angle = angle - 180.0
            angle = round(angle, precision)

        praInfo += (
            "\n -Rotation analysis:  angle: " + str(angle) + ",   axis: " + str(axis)
        )
        if rtn is True:
            praInfo += "\n - ... rotation triggered"
        else:
            praInfo += "\n - ... NO rotation triggered"

        PathLog.debug("\n" + str(praInfo))

        return (rtn, angle, axis, praInfo)

    # Working plane methods
    def orientModelToFixedIndex(self, obj):
        """orientModelToFixedIndex(self, obj)
        Orient the model(s) to user-specified fixed index for the operation.
        Returns tuple (isRotationActive, rotationGcodeCommands)"""
        PathLog.track()
        # https://forum.freecadweb.org/viewtopic.php?t=8187#p67122
        fail = (False, [])
        activeFixedIndex = False
        analyzeFace = False
        Job = PathUtils.findParentJob(obj)

        # Check for EnableRotation update from parent Job
        obj.EnableRotation = Job.EnableRotation

        # Enforce limits on VerticalIndexOffset
        if obj.VerticalIndexOffset < -360.0:
            obj.VerticalIndexOffset = -360.0
        elif obj.VerticalIndexOffset > 360.0:
            obj.VerticalIndexOffset = 360.0

        if obj.FixedIndexReference != "None":
            if obj.EnableRotation == "Off":
                PathLog.error(
                    translate(
                        "Path",
                        "To utilize the Fixed Index feature, you must 'Enable Rotation' for the Job.",
                    )
                )
                obj.FixedIndexReference = "None"
                return fail
            else:
                # self.resetModelToInitPlacement(obj, True)
                pass
        else:
            PathLog.debug("obj.FixedIndexReference == 'None'.")
            return fail

        # obj.FixedIndexReference == 'None' case is ignored
        if obj.FixedIndexReference == "Previous":
            (
                activeFixedIndex,
                rotAng,
                axisVect,
                millAxis,
            ) = self.__orientModelToPrevious(Job, obj)
        elif obj.FixedIndexReference == "Custom Plane":
            PathLog.error(
                "Custom Plane for Work Plane is unavailable (incomplete code)."
            )
            # obj.CustomPlaneAngle = 0.0
            # obj.CustomPlaneAxis = FreeCAD.Vector(0, 0, 0)
            # obj.CustomPlaneBase = FreeCAD.Vector(0, 0, 0)
        elif obj.FixedIndexReference == "First Base Geometry":
            PathLog.error(
                "Custom Plane for Work Plane is unavailable (incomplete code)."
            )
            bs = obj.Base[0][0]
            ftr = obj.Base[0][1][0]
            faceNum = int(ftr.replace("Face", ""))
            PathLog.info("First Base Geometry: {}.{}".format(bs.Name, ftr))
            refFace = bs.Shape.getElement(ftr)
            analyzeFace = True
        elif obj.FixedIndexReference[0:2] == "__":  # Reference object selected
            objName = obj.FixedIndexReference[2:]
            faceNum = obj.FaceOnReferenceObject

            if obj.FaceOnReferenceObject < 1:
                PathLog.error("Face On Reference Object must be > 0.")
                return fail

            try:
                # in case object has been deleted since property enumeration was created
                refObj = FreeCAD.ActiveDocument.getObject(objName)
            except Exception as e:
                PathLog.error(e)
                rmv = "__" + objName
                obj.FixedIndexReference.remove(rmv)
                return fail

            # Check if face number exists on refObj
            if obj.FaceOnReferenceObject > len(refObj.Shape.Faces):
                msg = "Reference object, {}, only contains {} faces.".format(
                    objName, len(refObj.Shape.Faces)
                )
                msg += "Verify face number with 'FaceOnReferenceObject' or change reference in 'FixedIndexReference'."
                PathLog.error(msg)
                return fail

            refFace = refObj.Shape.getElement("Face" + str(faceNum))
            analyzeFace = True
        else:
            PathLog.error("FixedIndexReference not found.")
            return fail

        if analyzeFace is True:
            (activeFixedIndex, rotAng, axisVect, millAxis) = self._analyzeRefFace(
                obj, refFace
            )

        if activeFixedIndex is True:
            rotCmds = self._applyFixedIndex(Job, obj, rotAng, axisVect, millAxis)
            return (True, rotCmds)  # (isRotationActive, rotationGcodeCommands)
        else:
            return fail

    def __orientModelToPrevious(self, job, obj):
        fail = (False, 0.0, FreeCAD.Vector(1, 0, 0), "A")
        if len(job.Operations.Group) > 1:
            for opi in range(0, len(job.Operations.Group)):
                if job.Operations.Group[opi].Name == obj.Name:
                    lst = opi - 1
            prevOp = job.Operations.Group[lst]
            if hasattr(prevOp, "FixedIndexReference"):
                if prevOp.FixedIndexReference == "None":
                    PathLog.debug("prevOp.FixedIndexReference == 'None'.")
                    # self.resetModelToInitPlacement(obj, True)
                    # obj.CustomPlaneAngle = 0.0
                    # obj.CustomPlaneAxis = FreeCAD.Vector(1, 0, 0)
                    # obj.MillIndexAxis = 'A'
                    return fail
                else:
                    rotAng = prevOp.CustomPlaneAngle
                    axisVect = prevOp.CustomPlaneAxis
                    millAxis = prevOp.MillIndexAxis
                    PathLog.debug(
                        "prevOp working plane: rotAng: {};  axisVect: {};  millAxis: {}.".format(
                            rotAng, axisVect, millAxis
                        )
                    )
                    if millAxis in obj.EnableRotation:
                        return (True, rotAng, axisVect, millAxis)
                    else:
                        msg = "EnableRotation not available for working plane of last operation."
                        msg += "  Enable Rotation for this operation and recompute."
                        PathLog.error(msg)
        else:
            PathLog.error("No previous operations from which to extract Working Plane.")
        return fail

    def _analyzeRefFace(self, obj, refFace):
        # Determine Surface.Axis and normalAt(0,0) values of reference face

        (norm, surf) = self._getFaceNormAndSurf(refFace)

        if surf is not None and norm is not None:
            (rtn, rotAng, cAxis, praInfo) = self.faceRotationAnalysis(
                obj.EnableRotation, norm, surf, obj.OppositeIndexAngle
            )
            if rtn is True:
                if cAxis == "X":
                    millAxis = "A"
                    axisVect = FreeCAD.Vector(1, 0, 0)
                elif cAxis == "Y":
                    millAxis = "B"
                    axisVect = FreeCAD.Vector(0, 1, 0)

                # Align_Face_to_View macro
                if FreeCAD.GuiUp:
                    # self._alignFaceToView(refFace)
                    pass

                if obj.InvertIndexRotation is True:
                    rotAng = -1 * rotAng

                return (True, rotAng, axisVect, millAxis)
        else:
            PathLog.error("surf: {};  norm: {}".format(surf, norm))
            return (False, 0.0, FreeCAD.Vector(1, 0, 0), "A")

    def _applyFixedIndex(self, Job, obj, rotAng, axisVect, millAxis):
        PathLog.debug("activeFixedIndex is True.")
        from Draft import rotate

        gcode = []

        # Reset model and stock to initial orientation, then apply fixed index
        self.resetModelToInitPlacement(obj, True)
        rotate(
            Job.Model.Group,
            rotAng,
            center=FreeCAD.Vector(0, 0, 0),
            axis=axisVect,
            copy=False,
        )
        if Job.Stock:
            rotate(
                [Job.Stock],
                rotAng,
                center=FreeCAD.Vector(0, 0, 0),
                axis=axisVect,
                copy=False,
            )
            Job.Stock.purgeTouched()
        for mdl in Job.Model.Group:
            mdl.recompute()
            mdl.purgeTouched()

        # Make visual representation of fixed index
        if obj.VisualizeFixedIndex is True:
            pass

        # save fixed index settings to operation
        obj.CustomPlaneAngle = rotAng
        obj.CustomPlaneAxis = axisVect
        obj.MillIndexAxis = millAxis

        gcode.append(Path.Command("N100 (Set fixed index or working plane)", {}))
        gcode.append(
            Path.Command("G0", {"Z": obj.SafeHeight.Value, "F": self.vertRapid})
        )
        if obj.VerticalIndexOffset == 0.0:
            gcode.append(Path.Command("G1", {millAxis: rotAng, "F": self.axialFeed}))
        PathLog.debug("  -- rotAng: {};  millAxis: {}".format(rotAng, millAxis))
        return gcode

    def resetModelToInitPlacement(self, obj, reset):
        PathLog.track()
        Job = PathUtils.findParentJob(obj)
        if len(Job.Model.Group) > 0:
            if reset is True:
                PathLog.debug("  --Reseting model placement to INITIAL.")
                for mdl in Job.Model.Group:
                    mdl.Placement.Base = mdl.InitBase
                    mdl.Placement.Rotation = FreeCAD.Rotation(
                        mdl.InitAxis, mdl.InitAngle
                    )
                    mdl.recompute()
                    mdl.purgeTouched()
                PathLog.debug("  --Reseting Stock placement to INITIAL.")
                Job.Stock.Placement.Base = Job.Stock.InitBase
                Job.Stock.Placement.Rotation = FreeCAD.Rotation(
                    Job.Stock.InitAxis, Job.Stock.InitAngle
                )
                Job.Stock.purgeTouched()
            elif obj.ResetIndexTo == "Initial":
                PathLog.debug("  --Reseting model placement to INITIAL.")
                for mdl in Job.Model.Group:
                    mdl.Placement.Base = mdl.InitBase
                    mdl.Placement.Rotation = FreeCAD.Rotation(
                        mdl.InitAxis, mdl.InitAngle
                    )
                    mdl.recompute()
                    mdl.purgeTouched()
                PathLog.debug("  --Reseting Stock placement to INITIAL.")
                Job.Stock.Placement.Base = Job.Stock.InitBase
                Job.Stock.Placement.Rotation = FreeCAD.Rotation(
                    Job.Stock.InitAxis, Job.Stock.InitAngle
                )
                Job.Stock.purgeTouched()
                if obj.CustomPlaneAngle != 0.0:
                    PathLog.debug("  --obj.CustomPlaneAngle != 0.0")
                    self.commandlist.append(
                        Path.Command(
                            "G0", {"Z": obj.SafeHeight.Value, "F": self.vertRapid}
                        )
                    )
                    if obj.VerticalIndexOffset == 0.0:
                        self.commandlist.append(
                            Path.Command(
                                "G1", {obj.MillIndexAxis: 0.0, "F": self.axialFeed}
                            )
                        )
            elif obj.ResetIndexTo == "Previous":
                PathLog.error(
                    "resetModelToInitPlacement to 'Previous' (incomplete code)."
                )
            elif obj.ResetIndexTo == "None":
                PathLog.debug(
                    "  --Not reseting model placement: resetModelToInitPlacement = 'None'."
                )
            else:
                PathLog.error("resetModelToInitPlacement()")

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
            self.horizRapid   ... horizontal rapid rate of assigned tool
            self.axialFeed    ... axial feed rate of assigned tool
            self.axialRapid   ... axial rapid rate of assigned tool
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
            path = Path.Path("(inactive operation)")
            obj.Path = path
            return

        if not self._setBaseAndStock(obj):
            return

        # make sure Base is still valid or clear it
        self.sanitizeBase(obj)

        if FeatureCoolant & self.opFeatures(obj):
            if not hasattr(obj, "CoolantMode"):
                PathLog.error(
                    translate(
                        "Path", "No coolant property found. Please recreate operation."
                    )
                )

        if FeatureTool & self.opFeatures(obj):
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
                self.vertFeed = (
                    tc.VertFeed.Value * abs(obj.FeedRateFactor)
                    if hasattr(obj, "FeedRateFactor")
                    else tc.VertFeed.Value
                )
                self.horizFeed = (
                    tc.HorizFeed.Value * abs(obj.FeedRateFactor)
                    if hasattr(obj, "FeedRateFactor")
                    else tc.HorizFeed.Value
                )
                self.axialFeed = 0.0
                self.vertRapid = tc.VertRapid.Value
                self.horizRapid = tc.HorizRapid.Value
                self.axialRapid = 0.0
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
                obj.OpToolDiameter = tool.Diameter

        self.updateDepths(obj)
        # now that all op values are set make sure the user properties get updated accordingly,
        # in case they still have an expression referencing any op values
        obj.recompute()

        self.commandlist = []
        self.commandlist.append(Path.Command("(%s)" % obj.Label))
        if obj.Comment:
            self.commandlist.append(Path.Command("(%s)" % obj.Comment))

        result = self.opExecute(obj)  # pylint: disable=assignment-from-no-return

        if self.commandlist and (FeatureHeights & self.opFeatures(obj)):
            # Let's finish by rapid to clearance...just for safety
            self.commandlist.append(
                Path.Command("G0", {"Z": obj.ClearanceHeight.Value})
            )

        path = Path.Path(self.commandlist)
        obj.Path = path
        obj.CycleTime = self.getCycleTimeEstimate(obj)
        self.job.Proxy.getCycleTime()
        return result

    def getCycleTimeEstimate(self, obj):

        tc = obj.ToolController

        if tc is None or tc.ToolNumber == 0:
            PathLog.error(translate("Path", "No Tool Controller selected."))
            return translate("Path", "Tool Error")

        hFeedrate = tc.HorizFeed.Value
        vFeedrate = tc.VertFeed.Value
        hRapidrate = tc.HorizRapid.Value
        vRapidrate = tc.VertRapid.Value

        if (
            hFeedrate == 0 or vFeedrate == 0
        ) and not PathPreferences.suppressAllSpeedsWarning():
            PathLog.warning(
                translate(
                    "Path",
                    "Tool Controller feedrates required to calculate the cycle time.",
                )
            )
            return translate("Path", "Feedrate Error")

        if (
            hRapidrate == 0 or vRapidrate == 0
        ) and not PathPreferences.suppressRapidSpeedsWarning():
            PathLog.warning(
                translate(
                    "Path",
                    "Add Tool Controller Rapid Speeds on the SetupSheet for more accurate cycle times.",
                )
            )

        # Get the cycle time in seconds
        seconds = obj.Path.getCycleTime(hFeedrate, vFeedrate, hRapidrate, vRapidrate)

        if not seconds:
            return translate("Path", "Cycletime Error")

        # Convert the cycle time to a HH:MM:SS format
        cycleTime = time.strftime("%H:%M:%S", time.gmtime(seconds))

        return cycleTime

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

    def isToolSupported(self, obj, tool):
        """toolSupported(obj, tool) ... Returns true if the op supports the given tool.
        This function can safely be overwritten by subclasses."""

        return True
