# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2014 Yorik van Havre <yorik@uncreated.net>              *
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

from PathScripts.PathPostProcessor import PostProcessor
from PySide import QtCore
from PySide.QtCore import QT_TRANSLATE_NOOP
import FreeCAD
import PathScripts.PathLog as PathLog
import PathScripts.PathPreferences as PathPreferences
import PathScripts.PathSetupSheet as PathSetupSheet
import PathScripts.PathStock as PathStock
import PathScripts.PathToolController as PathToolController
import PathScripts.PathUtil as PathUtil
import PathScripts.job.PathJobRotation as PathJobRotation
import json
import time
import Path


# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader

Draft = LazyLoader("Draft", globals(), "Draft")
math = LazyLoader("math", globals(), "math")

__title__ = "Base class for all Path Jobs."
__author__ = "Yorik van Havre <yorik@uncreated.net>"
__url__ = "https://www.freecadweb.org"
__doc__ = "Base class and properties implementation for all Path Jobs."


if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())

translate = FreeCAD.Qt.translate


class JobTemplate:
    """Attribute and sub element strings for template export/import."""

    Description = "Desc"
    GeometryTolerance = "Tolerance"
    Job = "Job"
    PostProcessor = "Post"
    PostProcessorArgs = "PostArgs"
    PostProcessorOutputFile = "Output"
    Fixtures = "Fixtures"
    OrderOutputBy = "OrderOutputBy"
    SplitOutput = "SplitOutput"
    SetupSheet = "SetupSheet"
    Stock = "Stock"
    # TCs are grouped under Tools in a job, the template refers to them directly though
    ToolController = "ToolController"
    Version = "Version"


def isResourceClone(obj, propLink, resourceName):
    if hasattr(propLink, "PathResource") and (
        resourceName is None or resourceName == propLink.PathResource
    ):
        return True
    return False


def createResourceClone(obj, orig, name, icon):

    clone = Draft.clone(orig)
    clone.Label = "%s-%s" % (name, orig.Label)
    clone.addProperty("App::PropertyString", "PathResource")
    clone.PathResource = name
    if clone.ViewObject:
        import PathScripts.PathIconViewProvider

        PathScripts.PathIconViewProvider.Attach(clone.ViewObject, icon)
        clone.ViewObject.Visibility = False
        clone.ViewObject.Transparency = 80
    obj.Document.recompute()  # necessary to create the clone shape
    return clone


def createModelResourceClone(obj, orig):
    return createResourceClone(obj, orig, "Model", "BaseGeometry")


class NotificationClass(QtCore.QObject):
    updateTC = QtCore.Signal(object, object)


Notification = NotificationClass()


class ObjectJob:
    def __init__(self, obj, models, templateFile=None):
        PathLog.debug("start ObjectJob.__init__()")
        self.obj = obj
        obj.addProperty(
            "App::PropertyFile",
            "PostProcessorOutputFile",
            "Output",
            QT_TRANSLATE_NOOP("App::Property", "The NC output file for this project"),
        )
        obj.addProperty(
            "App::PropertyEnumeration",
            "PostProcessor",
            "Output",
            QT_TRANSLATE_NOOP("App::Property", "Select the Post Processor"),
        )
        obj.addProperty(
            "App::PropertyString",
            "PostProcessorArgs",
            "Output",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Arguments for the Post Processor (specific to the script)",
            ),
        )
        obj.addProperty(
            "App::PropertyString",
            "LastPostProcessDate",
            "Output",
            QT_TRANSLATE_NOOP("App::Property", "Last Time the Job was post-processed"),
        )
        obj.setEditorMode("LastPostProcessDate", 2)  # Hide
        obj.addProperty(
            "App::PropertyString",
            "LastPostProcessOutput",
            "Output",
            QT_TRANSLATE_NOOP("App::Property", "Last Time the Job was post-processed"),
        )
        obj.setEditorMode("LastPostProcessOutput", 2)  # Hide

        obj.addProperty(
            "App::PropertyString",
            "Description",
            "Path",
            QT_TRANSLATE_NOOP("App::Property", "An optional description for this job"),
        )
        obj.addProperty(
            "App::PropertyString",
            "CycleTime",
            "Path",
            QT_TRANSLATE_NOOP("App::Property", "Job Cycle Time Estimation"),
        )
        obj.setEditorMode("CycleTime", 1)  # read-only
        obj.addProperty(
            "App::PropertyDistance",
            "GeometryTolerance",
            "Geometry",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "For computing Paths; smaller increases accuracy, but slows down computation",
            ),
        )

        obj.addProperty(
            "App::PropertyLink",
            "Stock",
            "Base",
            QT_TRANSLATE_NOOP("App::Property", "Solid object to be used as stock."),
        )
        obj.addProperty(
            "App::PropertyLink",
            "Operations",
            "Base",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Compound path of all operations in the order they are processed.",
            ),
        )

        obj.addProperty(
            "App::PropertyEnumeration",
            "JobType",
            "Base",
            QT_TRANSLATE_NOOP("App::Property", "Select the Type of Job"),
        )
        obj.setEditorMode("JobType", 2)  # Hide

        obj.addProperty(
            "App::PropertyBool",
            "SplitOutput",
            "Output",
            QT_TRANSLATE_NOOP(
                "App::Property", "Split output into multiple gcode files"
            ),
        )
        obj.addProperty(
            "App::PropertyEnumeration",
            "OrderOutputBy",
            "WCS",
            QT_TRANSLATE_NOOP(
                "App::Property", "If multiple WCS, order the output this way"
            ),
        )
        obj.addProperty(
            "App::PropertyStringList",
            "Fixtures",
            "WCS",
            QT_TRANSLATE_NOOP(
                "App::Property", "The Work Coordinate Systems for the Job"
            ),
        )

        obj.Fixtures = ["G54"]

        for n in self.propertyEnumerations():
            setattr(obj, n[0], n[1])

        obj.PostProcessorOutputFile = PathPreferences.defaultOutputFile()
        obj.PostProcessor = postProcessors = PathPreferences.allEnabledPostProcessors()
        defaultPostProcessor = PathPreferences.defaultPostProcessor()
        # Check to see if default post processor hasn't been 'lost' (This can happen when Macro dir has changed)
        if defaultPostProcessor in postProcessors:
            obj.PostProcessor = defaultPostProcessor
        else:
            obj.PostProcessor = postProcessors[0]
        obj.PostProcessorArgs = PathPreferences.defaultPostProcessorArgs()
        obj.GeometryTolerance = PathPreferences.defaultGeometryTolerance()

        self.setupTargetShapesGroup(obj)
        self.setupOperations(obj)
        self.setupSetupSheet(obj)
        self.setupBaseModel(obj, models)
        self.setupRotation(obj)
        self.setupToolTable(obj)
        self.setFromTemplateFile(obj, templateFile)
        self.setupStock(obj)
        PathLog.debug("end ObjectJob.__init__()")

    @classmethod
    def propertyEnumerations(self, dataType="data"):
        """propertyEnumerations(dataType="data")... return property enumeration lists of specified dataType.
        Args:
            dataType = 'data', 'raw', 'translated'
        Notes:
        'data' is list of internal string literals used in code
        'raw' is list of (translated_text, data_string) tuples
        'translated' is list of translated string literals
        """

        enums = {
            "OrderOutputBy": [
                (translate("Path_Job", "Fixture"), "Fixture"),
                (translate("Path_Job", "Tool"), "Tool"),
                (translate("Path_Job", "Operation"), "Operation"),
            ],
            "JobType": [
                (translate("Path_Job", "2D"), "2D"),
                (translate("Path_Job", "2.5D"), "2.5D"),
                (translate("Path_Job", "Lathe"), "Lathe"),
                (translate("Path_Job", "Multiaxis"), "Multiaxis"),
            ],
        }

        if dataType == "raw":
            return enums

        data = list()
        idx = 0 if dataType == "translated" else 1

        PathLog.debug(enums)

        for k, v in enumerate(enums):
            data.append((v, [tup[idx] for tup in enums[v]]))
        PathLog.debug(data)

        return data

    # __init__() helper methods
    def setupTargetShapesGroup(self, obj):
        PathLog.debug("setupTargetShapesGroup()")
        if not hasattr(obj, "TargetShapes"):
            obj.addProperty(
                "App::PropertyLink",
                "TargetShapes",
                "Base",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathJob", "The target shape objects for all operations"
                ),
            )
            group = FreeCAD.ActiveDocument.addObject(
                "App::DocumentObjectGroup", "TargetShapes"
            )
            group.Label = "Target Shapes"
            if group.ViewObject:
                group.ViewObject.Visibility = False
            obj.TargetShapes = group

    def setupOperations(self, obj):
        """setupOperations(obj)... setup the Operations group for the Job object."""
        PathLog.debug("setupOperations()")
        # ops = FreeCAD.ActiveDocument.addObject(
        #     "Path::FeatureCompoundPython", "Operations"
        # )
        ops = FreeCAD.ActiveDocument.addObject("App::DocumentObjectGroup", "Operations")
        if ops.ViewObject:
            # ops.ViewObject.Proxy = 0
            ops.ViewObject.Visibility = True

        obj.Operations = ops
        obj.setEditorMode("Operations", 2)  # hide
        obj.setEditorMode("Placement", 2)

    def setupSetupSheet(self, obj):
        PathLog.debug("setupSetupSheet()")
        if not getattr(obj, "SetupSheet", None):
            if not hasattr(obj, "SetupSheet"):
                obj.addProperty(
                    "App::PropertyLink",
                    "SetupSheet",
                    "Base",
                    QT_TRANSLATE_NOOP(
                        "App::Property", "SetupSheet holding the settings for this job"
                    ),
                )
            obj.SetupSheet = PathSetupSheet.Create()
            if obj.SetupSheet.ViewObject:
                import PathScripts.PathIconViewProvider

                PathScripts.PathIconViewProvider.Attach(
                    obj.SetupSheet.ViewObject, "SetupSheet"
                )
            obj.SetupSheet.Label = "SetupSheet"
        self.setupSheet = obj.SetupSheet.Proxy

    def setupBaseModel(self, obj, models=None):
        PathLog.track(obj.Label, models)
        PathLog.debug("setupBaseModel()")
        addModels = False

        if not hasattr(obj, "Model"):
            obj.addProperty(
                "App::PropertyLink",
                "Model",
                "Base",
                QT_TRANSLATE_NOOP(
                    "App::Property", "The base objects for all operations"
                ),
            )
            addModels = True
        elif obj.Model is None:
            addModels = True

        if addModels:
            model = FreeCAD.ActiveDocument.addObject(
                "App::DocumentObjectGroup", "Model"
            )
            if model.ViewObject:
                model.ViewObject.Visibility = False
            if models:
                # model.addObjects(
                #    [createModelResourceClone(obj, base) for base in models]
                # )
                for base in models:
                    model.addObject(createModelResourceClone(obj, base))
                    # clone = FreeCAD.ActiveDocument.ActiveObject
                    clone = createModelResourceClone(obj, base)
                    model.addObject(clone)
                    self.setupInitialClonePlacement(clone)
            obj.Model = model
            obj.Model.Label = "Model"

        if hasattr(obj, "Base"):
            PathLog.info(
                "Converting Job.Base to new Job.Model for {}".format(obj.Label)
            )
            obj.Model.addObject(obj.Base)
            obj.Base = None
            obj.removeProperty("Base")

    def setupRotation(self, obj):
        PathLog.debug("setupRotation()")
        reset = False
        if not hasattr(obj, "Rotation"):
            obj.addProperty(
                "App::PropertyLink",
                "Rotation",
                "Rotation",
                QtCore.QT_TRANSLATE_NOOP("PathJob", "Rotation management object."),
            )
            obj.Rotation = FreeCAD.ActiveDocument.addObject(
                "Path::FeaturePython", "Rotation"
            )
            obj.Rotation.Label = "Rotation"
            # obj.Rotation.Proxy = PathJobRotation.ObjectRotation(obj)
            self.addedRotationFlag = True

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
            obj.EnableRotation = "Off"
            self.addedRotationFlag = True

        if not hasattr(obj, "ResetModelOrientation"):
            obj.addProperty(
                "App::PropertyBool",
                "ResetModelOrientation",
                "Rotation",
                QtCore.QT_TRANSLATE_NOOP(
                    "PathJob", "Resets the job model(s) to original orientation."
                ),
            )
            obj.ResetModelOrientation = False
            self.addedRotationFlag = True

        if reset:
            # self._resetModelOrientation(obj)
            pass

    def setupToolTable(self, obj):
        PathLog.debug("setupToolTable()")
        if not hasattr(obj, "Tools"):
            obj.addProperty(
                "App::PropertyLink",
                "Tools",
                "Base",
                QT_TRANSLATE_NOOP(
                    "App::Property", "Collection of all tool controllers for the job"
                ),
            )
            toolTable = FreeCAD.ActiveDocument.addObject(
                "App::DocumentObjectGroup", "Tools"
            )
            toolTable.Label = "Tools"
            if toolTable.ViewObject:
                toolTable.ViewObject.Visibility = False
            if hasattr(obj, "ToolController"):
                toolTable.addObjects(obj.ToolController)
                obj.removeProperty("ToolController")
            obj.Tools = toolTable

    def setFromTemplateFile(self, obj, template):
        """setFromTemplateFile(obj, template) ... extract the properties from the given template file and assign to receiver.
        This will also create any TCs stored in the template."""
        PathLog.debug("setFromTemplateFile()")
        tcs = []
        if template:
            with open(PathUtil.toUnicode(template), "rb") as fp:
                attrs = json.load(fp)

            if attrs.get(JobTemplate.Version) and 1 == int(attrs[JobTemplate.Version]):
                attrs = self.setupSheet.decodeTemplateAttributes(attrs)
                if attrs.get(JobTemplate.SetupSheet):
                    self.setupSheet.setFromTemplate(attrs[JobTemplate.SetupSheet])

                if attrs.get(JobTemplate.GeometryTolerance):
                    obj.GeometryTolerance = float(
                        attrs.get(JobTemplate.GeometryTolerance)
                    )
                if attrs.get(JobTemplate.PostProcessor):
                    obj.PostProcessor = attrs.get(JobTemplate.PostProcessor)
                    if attrs.get(JobTemplate.PostProcessorArgs):
                        obj.PostProcessorArgs = attrs.get(JobTemplate.PostProcessorArgs)
                    else:
                        obj.PostProcessorArgs = ""
                if attrs.get(JobTemplate.PostProcessorOutputFile):
                    obj.PostProcessorOutputFile = attrs.get(
                        JobTemplate.PostProcessorOutputFile
                    )
                if attrs.get(JobTemplate.Description):
                    obj.Description = attrs.get(JobTemplate.Description)

                if attrs.get(JobTemplate.ToolController):
                    for tc in attrs.get(JobTemplate.ToolController):
                        tcs.append(PathToolController.FromTemplate(tc))
                if attrs.get(JobTemplate.Stock):
                    obj.Stock = PathStock.CreateFromTemplate(
                        obj, attrs.get(JobTemplate.Stock)
                    )
                if hasattr(JobTemplate, "EnableRotation"):
                    if attrs.get(JobTemplate.EnableRotation):
                        obj.EnableRotation = attrs.get(JobTemplate.EnableRotation)
                else:
                    self.setupRotation(obj)

                if attrs.get(JobTemplate.Fixtures):
                    obj.Fixtures = [
                        x for y in attrs.get(JobTemplate.Fixtures) for x in y
                    ]

                if attrs.get(JobTemplate.OrderOutputBy):
                    obj.OrderOutputBy = attrs.get(JobTemplate.OrderOutputBy)

                if attrs.get(JobTemplate.SplitOutput):
                    obj.SplitOutput = attrs.get(JobTemplate.SplitOutput)

                PathLog.debug("setting tool controllers (%d)" % len(tcs))
                obj.Tools.Group = tcs
            else:
                PathLog.error(
                    "Unsupported PathJob template version {}".format(
                        attrs.get(JobTemplate.Version)
                    )
                )

        if not tcs:
            self.addToolController(PathToolController.Create())

    def setupStock(self, obj):
        """setupStock(obj)... setup the Stock for the Job object."""
        PathLog.debug("setupStock()")
        if not obj.Stock:
            stockTemplate = PathPreferences.defaultStockTemplate()
            if stockTemplate:
                obj.Stock = PathStock.CreateFromTemplate(obj, json.loads(stockTemplate))
            if not obj.Stock:
                obj.Stock = PathStock.CreateFromBase(obj)
        if obj.Stock.ViewObject:
            obj.Stock.ViewObject.Visibility = False

    # Other methods
    def removeBase(self, obj, base, removeFromModel):
        if isResourceClone(obj, base, None):
            PathUtil.clearExpressionEngine(base)
            if removeFromModel:
                obj.Model.removeObject(base)
            obj.Document.removeObject(base.Name)

    def modelBoundBox(self, obj):
        return PathStock.shapeBoundBox(obj.Model.Group)

    def onDelete(self, obj, arg2=None):
        """Called by the view provider, there doesn't seem to be a callback on the obj itself."""
        PathLog.track(obj.Label, arg2)
        doc = obj.Document

        if getattr(obj, "Operations", None):
            # the first to tear down are the ops, they depend on other resources
            PathLog.debug(
                "taking down ops: %s" % [o.Name for o in self.allOperations()]
            )
            while obj.Operations.Group:
                op = obj.Operations.Group[0]
                if (
                    not op.ViewObject
                    or not hasattr(op.ViewObject.Proxy, "onDelete")
                    or op.ViewObject.Proxy.onDelete(op.ViewObject, ())
                ):
                    PathUtil.clearExpressionEngine(op)
                    doc.removeObject(op.Name)

            obj.Operations.Group = []
            doc.removeObject(obj.Operations.Name)
            obj.Operations = None

        # stock could depend on Model, so delete it first
        if getattr(obj, "Stock", None):
            PathLog.debug("taking down stock")
            PathUtil.clearExpressionEngine(obj.Stock)
            doc.removeObject(obj.Stock.Name)
            obj.Stock = None

        # base doesn't depend on anything inside job
        if getattr(obj, "Model", None):
            for base in obj.Model.Group:
                PathLog.debug("taking down base %s" % base.Label)
                self.removeBase(obj, base, False)
            obj.Model.Group = []
            doc.removeObject(obj.Model.Name)
            obj.Model = None

        # Tool controllers might refer to either legacy tool or toolbit
        if getattr(obj, "Tools", None):
            PathLog.debug("taking down tool controller")
            for tc in obj.Tools.Group:
                if hasattr(tc.Tool, "Proxy"):
                    PathUtil.clearExpressionEngine(tc.Tool)
                    doc.removeObject(tc.Tool.Name)
                PathUtil.clearExpressionEngine(tc)
                tc.Proxy.onDelete(tc)
                doc.removeObject(tc.Name)
            obj.Tools.Group = []
            doc.removeObject(obj.Tools.Name)
            obj.Tools = None

        # SetupSheet
        if getattr(obj, "SetupSheet", None):
            PathUtil.clearExpressionEngine(obj.SetupSheet)
            doc.removeObject(obj.SetupSheet.Name)
            obj.SetupSheet = None

        # Rotation doesn't depend on anything inside job
        if getattr(obj, "Rotation", None):
            doc.removeObject(obj.Rotation.Name)
            obj.Rotation = None

        return True

    def fixupOperations(self, obj):
        if getattr(obj.Operations, "ViewObject", None):
            try:
                obj.Operations.ViewObject.DisplayMode
            except Exception:
                name = obj.Operations.Name
                label = obj.Operations.Label
                ops = FreeCAD.ActiveDocument.addObject(
                    "Path::FeatureCompoundPython", "Operations"
                )
                ops.ViewObject.Proxy = 0
                ops.Group = obj.Operations.Group
                obj.Operations.Group = []
                obj.Operations = ops
                FreeCAD.ActiveDocument.removeObject(name)
                ops.Label = label

    def _resetModelOrientation(self, obj):
        if len(obj.Model.Group) > 0:
            for mdl in obj.Model.Group:
                mdl.Placement.Base = mdl.InitBase
                mdl.Placement.Rotation = FreeCAD.Rotation(mdl.InitAxis, mdl.InitAngle)
                mdl.recompute()
                mdl.purgeTouched()
        if obj.Stock:
            obj.Stock.Placement.Base = obj.Stock.InitBase
            obj.Stock.Placement.Rotation = FreeCAD.Rotation(
                obj.Stock.InitAxis, obj.Stock.InitAngle
            )
            obj.Stock.purgeTouched()

    def onDocumentRestored(self, obj):
        self.addedRotationFlag = False
        self.setupTargetShapesGroup(obj)
        self.setupBaseModel(obj)
        self.fixupOperations(obj)
        self.setupSetupSheet(obj)
        self.setupToolTable(obj)
        self.integrityCheck(obj)

        self.setupRotation(obj)
        self.updateModelProperties(obj)
        obj.setEditorMode("Operations", 2)  # hide
        obj.setEditorMode("Placement", 2)

        if not hasattr(obj, "CycleTime"):
            obj.addProperty(
                "App::PropertyString",
                "CycleTime",
                "Path",
                QT_TRANSLATE_NOOP("App::Property", "Operations Cycle Time Estimation"),
            )
            obj.setEditorMode("CycleTime", 1)  # read-only

        if not hasattr(obj, "Fixtures"):
            obj.addProperty(
                "App::PropertyStringList",
                "Fixtures",
                "WCS",
                QT_TRANSLATE_NOOP(
                    "App::Property", "The Work Coordinate Systems for the Job"
                ),
            )
            obj.Fixtures = ["G54"]

        if not hasattr(obj, "OrderOutputBy"):
            obj.addProperty(
                "App::PropertyEnumeration",
                "OrderOutputBy",
                "WCS",
                QT_TRANSLATE_NOOP(
                    "App::Property", "If multiple WCS, order the output this way"
                ),
            )
            obj.OrderOutputBy = ["Fixture", "Tool", "Operation"]

        if not hasattr(obj, "SplitOutput"):
            obj.addProperty(
                "App::PropertyBool",
                "SplitOutput",
                "Output",
                QT_TRANSLATE_NOOP(
                    "App::Property", "Split output into multiple gcode files"
                ),
            )
            obj.SplitOutput = False

        if not hasattr(obj, "JobType"):
            obj.addProperty(
                "App::PropertyEnumeration",
                "JobType",
                "Base",
                QT_TRANSLATE_NOOP("App::Property", "Select the Type of Job"),
            )
            obj.setEditorMode("JobType", 2)  # Hide

        for n in self.propertyEnumerations():
            setattr(obj, n[0], n[1])

        if True in [isinstance(t.Tool, Path.Tool) for t in obj.Tools.Group]:
            FreeCAD.Console.PrintWarning(
                translate(
                    "Path",
                    "This job contains Legacy tools. Legacy tools are deprecated. They will be removed after version 0.20",
                )
            )

        if self.addedRotationFlag:
            self._resetModelOrientation(obj)

    def onChanged(self, obj, prop):
        # print("Job.onChanged({})".format(prop))
        if prop == "PostProcessor" and obj.PostProcessor:
            processor = PostProcessor.load(obj.PostProcessor)
            self.tooltip = processor.tooltip
            self.tooltipArgs = processor.tooltipArgs
        elif prop == "ResetModelOrientation" and obj.ResetModelOrientation is True:
            # print("Job.onChanged() reset model orientation")
            self._resetModelOrientation(obj)
            obj.ResetModelOrientation = False
        elif prop == "EnableRotation":
            if len(obj.Operations.Group) > 0:
                # msg = "Consider recomputing {}'s operations due to changing '{}.EnableRotation' property.".format(
                #    obj.Label, obj.Name
                # )
                # PathLog.warning(translate("Path", msg))
                for op in obj.Operations.Group:
                    if hasattr(op, "EnableRotation"):
                        op.EnableRotation = obj.EnableRotation
        elif prop == "Stock":
            if obj.Stock:
                self.setupInitialClonePlacement(obj.Stock)

    def baseObject(self, obj, base):
        """Return the base object, not its clone."""
        if isResourceClone(obj, base, "Model") or isResourceClone(obj, base, "Base"):
            return base.Objects[0]
        return base

    def baseObjects(self, obj):
        """Return the base objects, not their clones."""
        return [self.baseObject(obj, base) for base in obj.Model.Group]

    def resourceClone(self, obj, base):
        """resourceClone(obj, base) ... Return the resource clone for base if it exists."""
        if isResourceClone(obj, base, None):
            return base
        for b in obj.Model.Group:
            if base == b.Objects[0]:
                return b
        return None

    def templateAttrs(self, obj):
        """templateAttrs(obj) ... answer a dictionary with all properties of the receiver that should be stored in a template file."""
        attrs = {}
        attrs[JobTemplate.Version] = 1
        if obj.PostProcessor:
            attrs[JobTemplate.PostProcessor] = obj.PostProcessor
            attrs[JobTemplate.PostProcessorArgs] = obj.PostProcessorArgs
            attrs[JobTemplate.Fixtures] = [{f: True} for f in obj.Fixtures]
            attrs[JobTemplate.OrderOutputBy] = obj.OrderOutputBy
            attrs[JobTemplate.SplitOutput] = obj.SplitOutput
        if obj.PostProcessorOutputFile:
            attrs[JobTemplate.PostProcessorOutputFile] = obj.PostProcessorOutputFile
        attrs[JobTemplate.GeometryTolerance] = str(obj.GeometryTolerance.Value)
        if obj.Description:
            attrs[JobTemplate.Description] = obj.Description
        attrs[JobTemplate.EnableRotation] = obj.EnableRotation.Value
        return attrs

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        for obj in FreeCAD.ActiveDocument.Objects:
            if hasattr(obj, "Proxy") and obj.Proxy == self:
                self.obj = obj
                break
        return None

    def execute(self, obj):
        if getattr(obj, "Operations", None):
            # obj.Path = obj.Operations.Path
            self.getCycleTime()

    def getCycleTime(self):
        seconds = 0

        if len(self.obj.Operations.Group):
            for op in self.obj.Operations.Group:

                # Skip inactive operations
                if PathUtil.opProperty(op, "Active") is False:
                    continue

                # Skip operations that don't have a cycletime attribute
                if PathUtil.opProperty(op, "CycleTime") is None:
                    continue

                formattedCycleTime = PathUtil.opProperty(op, "CycleTime")
                opCycleTime = 0
                try:
                    # Convert the formatted time from HH:MM:SS to just seconds
                    opCycleTime = sum(
                        x * int(t)
                        for x, t in zip(
                            [1, 60, 3600], reversed(formattedCycleTime.split(":"))
                        )
                    )
                except Exception:
                    continue

                if opCycleTime > 0:
                    seconds = seconds + opCycleTime

        cycleTimeString = time.strftime("%H:%M:%S", time.gmtime(seconds))
        self.obj.CycleTime = cycleTimeString

    def addOperation(self, op, before=None, removeBefore=False):
        group = self.obj.Operations.Group
        if op not in group:
            if before:
                try:
                    group.insert(group.index(before), op)
                    if removeBefore:
                        group.remove(before)
                except Exception as e:
                    PathLog.error(e)
                    group.append(op)
            else:
                group.append(op)
            self.obj.Operations.Group = group
            # op.Path.Center = self.obj.Operations.Path.Center

    def addTargetGeometry(self, ts, before=None, removeBefore=False):
        group = self.obj.TargetShapes.Group
        if ts not in group:
            if before:
                try:
                    group.insert(group.index(before), ts)
                    if removeBefore:
                        group.remove(before)
                except Exception as e:  # pylint: disable=broad-except
                    PathLog.error(e)
                    group.append(ts)
            else:
                group.append(ts)
            self.obj.TargetShapes.Group = group

    def addTargetGeometry_copy(self, ts, before=None, removeBefore=False):
        group = self.obj.TargetShapes.Group
        if ts not in group:
            if before:
                try:
                    group.insert(group.index(before), ts)
                    if removeBefore:
                        group.remove(before)
                except Exception as e:  # pylint: disable=broad-except
                    PathLog.error(e)
                    group.append(ts)
            else:
                group.append(ts)
            self.obj.TargetShapes.Group = group

    def nextToolNumber(self):
        # returns the next available toolnumber in the job
        group = self.obj.Tools.Group
        return sorted([t.ToolNumber for t in group])[-1] + 1

    def addToolController(self, tc):
        group = self.obj.Tools.Group
        PathLog.debug(
            "addToolController(%s): %s" % (tc.Label, [t.Label for t in group])
        )
        if tc.Name not in [str(t.Name) for t in group]:
            tc.setExpression(
                "VertRapid",
                "%s.%s"
                % (
                    self.setupSheet.expressionReference(),
                    PathSetupSheet.Template.VertRapid,
                ),
            )
            tc.setExpression(
                "HorizRapid",
                "%s.%s"
                % (
                    self.setupSheet.expressionReference(),
                    PathSetupSheet.Template.HorizRapid,
                ),
            )
            self.obj.Tools.addObject(tc)
            Notification.updateTC.emit(self.obj, tc)

    def allOperations(self):
        ops = []

        def collectBaseOps(op):
            if hasattr(op, "TypeId"):
                if op.TypeId == "Path::FeaturePython":
                    ops.append(op)
                    if hasattr(op, "Base"):
                        collectBaseOps(op.Base)
                if op.TypeId == "Path::FeatureCompoundPython":
                    ops.append(op)
                    for sub in op.Group:
                        collectBaseOps(sub)

        if getattr(self.obj, "Operations", None) and getattr(
            self.obj.Operations, "Group", None
        ):
            for op in self.obj.Operations.Group:
                collectBaseOps(op)

        return ops

    def setCenterOfRotation(self, center):
        if center != self.obj.Path.Center:
            self.obj.Path.Center = center
            self.obj.Operations.Path.Center = center
            for op in self.allOperations():
                op.Path.Center = center

    def integrityCheck(self, job):
        """integrityCheck(job)... Return True if job has all expected children objects.  Attempts to restore any missing children."""
        PathLog.debug("integrityCheck()")
        suffix = ""
        if len(job.Name) > 3:
            suffix = job.Name[3:]

        def errorMessage(grp, job):
            PathLog.error("{} corrupt in {} job.".format(grp, job.Name))

        if not job.Operations:
            self.setupOperations(job)
            job.Operations.Label = "Operations" + suffix
            if not job.Operations:
                errorMessage("Operations", job)
                return False
        if not job.SetupSheet:
            self.setupSetupSheet(job)
            job.SetupSheet.Label = "SetupSheet" + suffix
            if not job.SetupSheet:
                errorMessage("SetupSheet", job)
                return False
        if not job.Model:
            self.setupBaseModel(job)
            job.Model.Label = "Model" + suffix
            if not job.Model:
                errorMessage("Model", job)
                return False
        if not job.Stock:
            self.setupStock(job)
            job.Stock.Label = "Stock" + suffix
            if not job.Stock:
                errorMessage("Stock", job)
                return False
        if not job.Tools:
            self.setupToolTable(job)
            job.Tools.Label = "Tools" + suffix
            if not job.Tools:
                errorMessage("Tools", job)
                return False
        return True

    def setupInitialClonePlacement(self, clone):
        PathLog.debug(f"setupInitialClonePlacement({clone.Name})")

        # print("Job.setupInitialClonePlacement()")
        if clone is None:
            # print("Job.setupInitialClonePlacement() clone is None")
            return
        if not hasattr(clone, "InitBase"):
            clone.addProperty(
                "App::PropertyVectorDistance",
                "InitBase",
                "InitialPlacement",
                translate(
                    "PathSetupSheet", "Initial base.Placement.Base values for model."
                ),
            )
        if not hasattr(clone, "InitAxis"):
            clone.addProperty(
                "App::PropertyVectorDistance",
                "InitAxis",
                "InitialPlacement",
                translate(
                    "PathSetupSheet",
                    "Initial base.Placement.Rotation.Axis values for model.",
                ),
            )
        if not hasattr(clone, "InitAngle"):
            clone.addProperty(
                "App::PropertyFloat",
                "InitAngle",
                "InitialPlacement",
                translate(
                    "PathSetupSheet",
                    "Initial base.Placement.Rotation.Angle value for model.",
                ),
            )
        if not hasattr(clone, "InitLock"):
            clone.addProperty(
                "App::PropertyBool",
                "InitLock",
                "InitialPlacement",
                translate(
                    "PathSetupSheet", "Initial base.Placement.Base values for model."
                ),
            )
        clone.setEditorMode("InitBase", 0)  # visible, read & write permission
        clone.setEditorMode("InitAxis", 0)
        clone.setEditorMode("InitAngle", 0)
        clone.setEditorMode("InitLock", 0)
        clone.InitBase.x = clone.Placement.Base.x
        clone.InitBase.y = clone.Placement.Base.y
        clone.InitBase.z = clone.Placement.Base.z
        clone.InitAxis.x = clone.Placement.Rotation.Axis.x
        clone.InitAxis.y = clone.Placement.Rotation.Axis.y
        clone.InitAxis.z = clone.Placement.Rotation.Axis.z
        clone.InitAngle = math.degrees(clone.Placement.Rotation.Angle)
        clone.setEditorMode("InitBase", 1)  # visible, read-only permission
        clone.setEditorMode("InitAxis", 1)
        clone.setEditorMode("InitAngle", 1)
        clone.setEditorMode("InitLock", 1)

    def updateModelProperties(self, obj):
        PathLog.debug("ObjectJob.updateModelProperties()")
        for m in obj.Model.Group:
            if not hasattr(m, "InitBase"):
                self.setupInitialClonePlacement(m)

    def showRestShape_ORIG(self, obj):
        restShape = obj.Stock.Shape
        for op in obj.Operations.Group:
            if hasattr(op, "RemovalShape") and op.RemovalShape:
                for ss in op.RemovalShape.SubShapes:
                    cut = restShape.cut(ss)
                    restShape = cut
        jrs = FreeCAD.ActiveDocument.addObject("Part::Feature", "Job_Rest_Shape")
        jrs.Shape = restShape
        jrs.purgeTouched()

    def showRestShape(self, obj):
        restShape = obj.Stock.Shape
        jrs = FreeCAD.ActiveDocument.addObject("Part::Feature", "Job_Rest_Shape")
        jrs.Shape = restShape
        jrs.purgeTouched()
        for op in obj.Operations.Group:
            if hasattr(op, "RemovalShape") and op.RemovalShape:
                opjrs = FreeCAD.ActiveDocument.addObject(
                    "Part::Feature", "Job_Rest_Shape"
                )
                opjrs.Shape = op.RemovalShape
                opjrs.purgeTouched()

    def showAllRestShapes(self, obj):
        restShape = obj.Stock.Shape
        jrs = FreeCAD.ActiveDocument.addObject("Part::Feature", "Job_Rest_Shape")
        jrs.Shape = restShape
        jrs.purgeTouched()
        for op in obj.Operations.Group:
            if hasattr(op, "RemovalShape") and op.RemovalShape:
                opjrs = FreeCAD.ActiveDocument.addObject(
                    "Part::Feature", "Job_Rest_Shape"
                )
                opjrs.Shape = op.RemovalShape
                opjrs.purgeTouched()

    @classmethod
    def baseCandidates(cls):
        """Answer all objects in the current document which could serve as a Base for a job."""
        return sorted(
            [obj for obj in FreeCAD.ActiveDocument.Objects if cls.isBaseCandidate(obj)],
            key=lambda o: o.Label,
        )

    @classmethod
    def isBaseCandidate(cls, obj):
        """Answer true if the given object can be used as a Base for a job."""
        return PathUtil.isValidBaseObject(obj)


def Instances():
    """Instances() ... Return all Jobs in the current active document."""
    if FreeCAD.ActiveDocument:
        return [
            job
            for job in FreeCAD.ActiveDocument.Objects
            if hasattr(job, "Proxy") and isinstance(job.Proxy, ObjectJob)
        ]
    return []


def Create(name, base, templateFile=None):
    """Create(name, base, templateFile=None) ... creates a new job and all it's resources.
    If a template file is specified the new job is initialized with the values from the template."""
    if isinstance(base[0], str):
        models = []
        for baseName in base:
            models.append(FreeCAD.ActiveDocument.getObject(baseName))
    else:
        models = base
    obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.addExtension("App::GroupExtensionPython")
    obj.Proxy = ObjectJob(obj, models, templateFile)
    return obj
