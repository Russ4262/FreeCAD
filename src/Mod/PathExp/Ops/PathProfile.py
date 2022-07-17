# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2014 Yorik van Havre <yorik@uncreated.net>              *
# *   Copyright (c) 2016 sliptonic <shopinthewoods@gmail.com>               *
# *   Copyright (c) 2020 Schildkroet                                        *
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
import Ops.PathAreaOp as PathAreaOp
import PathScripts.PathLog as PathLog
import PathScripts.PathOp as PathOp
import PathScripts.PathUtils as PathUtils
from PySide.QtCore import QT_TRANSLATE_NOOP

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader

Part = LazyLoader("Part", globals(), "Part")
DraftGeomUtils = LazyLoader("DraftGeomUtils", globals(), "DraftGeomUtils")

translate = FreeCAD.Qt.translate

__title__ = "Path Profile Operation"
__author__ = "sliptonic (Brad Collette)"
__url__ = "http://www.freecadweb.org"
__doc__ = (
    "Path Profile operation based on entire model, selected faces or selected edges."
)
__contributors__ = "Schildkroet"

if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


class ObjectProfile(PathAreaOp.ObjectOp):
    """Proxy object for Profile operations based on faces."""

    def areaOpFeatures_orig(self, obj):
        """areaOpFeatures(obj) ... returns operation-specific features"""
        return PathOp.FeatureBaseFaces | PathOp.FeatureBaseEdges

    def initAreaOp(self, obj):
        """initAreaOp(obj) ... creates all profile specific properties."""
        self.propertiesReady = False
        self.initAreaOpProperties(obj)

        obj.setEditorMode("MiterLimit", 2)
        obj.setEditorMode("JoinType", 2)

    def initAreaOpProperties(self, obj, warn=False):
        """initAreaOpProperties(obj) ... create operation specific properties"""
        self.addNewProps = []

        for (propertytype, propertyname, grp, tt) in self.areaOpProperties():
            if not hasattr(obj, propertyname):
                obj.addProperty(propertytype, propertyname, grp, tt)
                self.addNewProps.append(propertyname)

        if len(self.addNewProps) > 0:
            # Set enumeration lists for enumeration properties
            ENUMS = self.areaOpPropertyEnumerations()
            for n in ENUMS:
                if n[0] in self.addNewProps:
                    setattr(obj, n[0], n[1])
            if warn:
                newPropMsg = "New property added to"
                newPropMsg += ' "{}": {}'.format(obj.Label, self.addNewProps) + ". "
                newPropMsg += "Check its default value." + "\n"
                FreeCAD.Console.PrintWarning(newPropMsg)

        self.propertiesReady = True

    def areaOpProperties(self):
        """areaOpProperties(obj) ... returns a tuples.
        Each tuple contains property declaration information in the
        form of (prototype, name, section, tooltip)."""
        return [
            (
                "App::PropertyEnumeration",
                "Direction",
                "Profile",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "The direction that the toolpath should go around the part ClockWise (CW) or CounterClockWise (CCW)",
                ),
            ),
            (
                "App::PropertyEnumeration",
                "HandleMultipleFeatures",
                "Profile",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Choose how to process multiple Base Geometry features.",
                ),
            ),
            (
                "App::PropertyEnumeration",
                "JoinType",
                "Profile",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Controls how tool moves around corners. Default=Round",
                ),
            ),
            (
                "App::PropertyFloat",
                "MiterLimit",
                "Profile",
                QT_TRANSLATE_NOOP(
                    "App::Property", "Maximum distance before a miter join is truncated"
                ),
            ),
            (
                "App::PropertyDistance",
                "OffsetExtra",
                "Profile",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Extra value to stay away from final profile- good for roughing toolpath",
                ),
            ),
            (
                "App::PropertyBool",
                "processHoles",
                "Profile",
                QT_TRANSLATE_NOOP(
                    "App::Property", "Profile holes as well as the outline"
                ),
            ),
            (
                "App::PropertyBool",
                "processPerimeter",
                "Profile",
                QT_TRANSLATE_NOOP("App::Property", "Profile the outline"),
            ),
            (
                "App::PropertyBool",
                "processCircles",
                "Profile",
                QT_TRANSLATE_NOOP("App::Property", "Profile round holes"),
            ),
            (
                "App::PropertyEnumeration",
                "Side",
                "Profile",
                QT_TRANSLATE_NOOP("App::Property", "Side of edge that tool should cut"),
            ),
            (
                "App::PropertyBool",
                "UseComp",
                "Profile",
                QT_TRANSLATE_NOOP(
                    "App::Property", "Make True, if using Cutter Radius Compensation"
                ),
            ),
            (
                "App::PropertyLink",
                "TargetShape",
                "Profile",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Link to Target Shape object as basis for path generation",
                ),
            ),
        ]

    @classmethod
    def areaOpPropertyEnumerations(self, dataType="data"):

        """opPropertyEnumerations(dataType="data")... return property enumeration lists of specified dataType.
        Args:
            dataType = 'data', 'raw', 'translated'
        Notes:
        'data' is list of internal string literals used in code
        'raw' is list of (translated_text, data_string) tuples
        'translated' is list of translated string literals
        """

        # Enumeration lists for App::PropertyEnumeration properties
        enums = {
            "Direction": [
                (translate("PathProfile", "CW"), "CW"),
                (translate("PathProfile", "CCW"), "CCW"),
            ],  # this is the direction that the profile runs
            "HandleMultipleFeatures": [
                (translate("PathProfile", "Collectively"), "Collectively"),
                (translate("PathProfile", "Individually"), "Individually"),
            ],
            "JoinType": [
                (translate("PathProfile", "Round"), "Round"),
                (translate("PathProfile", "Square"), "Square"),
                (translate("PathProfile", "Miter"), "Miter"),
            ],  # this is the direction that the Profile runs
            "Side": [
                (translate("PathProfile", "Outside"), "Outside"),
                (translate("PathProfile", "Inside"), "Inside"),
            ],  # side of profile that cutter is on in relation to direction of profile
        }

        if dataType == "raw":
            return enums

        data = list()
        idx = 0 if dataType == "translated" else 1

        PathLog.debug(enums)

        for k, v in enumerate(enums):
            # data[k] = [tup[idx] for tup in v]
            data.append((v, [tup[idx] for tup in enums[v]]))
        PathLog.debug(data)

        return data

    def areaOpPropertyDefaults(self, obj, job):
        """areaOpPropertyDefaults(obj, job) ... returns a dictionary of default values
        for the operation's properties."""
        targetShps = [None] + [
            o for o in job.Operations.Group if o.Name.startswith("TargetShape")
        ]
        return {
            "Direction": "CW",
            "HandleMultipleFeatures": "Collectively",
            "JoinType": "Round",
            "MiterLimit": 0.1,
            "OffsetExtra": 0.0,
            "Side": "Outside",
            "UseComp": True,
            "processCircles": False,
            "processHoles": False,
            "processPerimeter": True,
            "TargetShape": targetShps[-1],
        }

    def areaOpApplyPropertyDefaults(self, obj, job, propList):
        # Set standard property defaults
        PROP_DFLTS = self.areaOpPropertyDefaults(obj, job)
        for n in PROP_DFLTS:
            if n in propList:
                prop = getattr(obj, n)
                val = PROP_DFLTS[n]
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

    def areaOpSetDefaultValues(self, obj, job):
        if self.addNewProps and self.addNewProps.__len__() > 0:
            self.areaOpApplyPropertyDefaults(obj, job, self.addNewProps)

    def setOpEditorProperties(self, obj):
        """setOpEditorProperties(obj, porp) ... Process operation-specific changes to properties visibility."""
        obj.setEditorMode("JoinType", 2)
        obj.setEditorMode("MiterLimit", 2)  # ml

    def areaOpOnDocumentRestored(self, obj):
        self.propertiesReady = False

        self.initAreaOpProperties(obj, warn=True)
        self.areaOpSetDefaultValues(obj, PathUtils.findParentJob(obj))
        self.setOpEditorProperties(obj)

    def areaOpOnChanged(self, obj, prop):
        """areaOpOnChanged(obj, prop) ... updates certain property visibilities depending on changed properties."""
        if prop in ["UseComp", "JoinType", "Base"]:
            if hasattr(self, "propertiesReady") and self.propertiesReady:
                self.setOpEditorProperties(obj)

    def areaOpAreaParams(self, obj, isHole):
        """areaOpAreaParams(obj, isHole) ... returns dictionary with area parameters.
        Do not overwrite."""
        params = {}
        params["Fill"] = 0
        params["Coplanar"] = 0
        params["SectionCount"] = -1

        offset = obj.OffsetExtra.Value  # 0.0
        if obj.UseComp:
            offset = self.radius + obj.OffsetExtra.Value
        # if obj.Side == "Inside":
        #    offset = 0 - offset
        if isHole:
            offset = 0 - offset
        params["Offset"] = offset

        jointype = ["Round", "Square", "Miter"]
        params["JoinType"] = jointype.index(obj.JoinType)

        if obj.JoinType == "Miter":
            params["MiterLimit"] = obj.MiterLimit

        if obj.SplitArcs:
            params["Explode"] = True
            params["FitArcs"] = False

        return params

    def areaOpPathParams(self, obj, isHole):
        """areaOpPathParams(obj, isHole) ... returns dictionary with path parameters.
        Do not overwrite."""
        params = {}

        # Reverse the direction for holes
        if isHole:
            direction = "CW" if obj.Direction == "CCW" else "CCW"
        else:
            direction = obj.Direction

        if direction == "CCW":
            params["orientation"] = 0
        else:
            params["orientation"] = 1

        if not obj.UseComp:
            if direction == "CCW":
                params["orientation"] = 1
            else:
                params["orientation"] = 0

        return params

    def areaOpUseProjection(self, obj):
        """areaOpUseProjection(obj) ... returns True"""
        # return True
        return False  # False forces sections of target shape

    def opUpdateDepths(self, obj):
        # print("ObjectProfile.opUpdateDepths()")
        if obj.TargetShape:
            obj.setExpression(
                "OpStockZMax", "{} mm".format(obj.TargetShape.StartDepth.Value)
            )
            obj.setExpression(
                "OpStartDepth", "{} mm".format(obj.TargetShape.StartDepth.Value)
            )
            obj.setExpression(
                "OpFinalDepth", "{} mm".format(obj.TargetShape.FinalDepth.Value)
            )

    def areaOpShapes(self, obj):
        """areaOpShapes(obj) ... returns envelope for all base shapes or wires"""

        shapes = []
        if obj.UseComp:
            self.commandlist.append(
                Path.Command(
                    "(Compensated Tool Path. Diameter: " + str(self.radius * 2) + ")"
                )
            )
        else:
            self.commandlist.append(Path.Command("(Uncompensated Tool Path)"))

        # print("No shapes to process... ")
        if obj.TargetShape:
            # print(f"SD: {obj.StartDepth.Value};  FD: {obj.FinalDepth.Value}")
            for s in obj.TargetShape.Shape.Solids:
                isHole = True if obj.Side == "Inside" else False
                # print(f"isHole: {isHole}")
                shp = s.copy()
                tup = shp, isHole, "Profile"
                shapes.append(tup)

        return shapes

    # Method to add temporary debug object
    def _addDebugObject(self, objName, objShape):
        if self.isDebug:
            newDocObj = FreeCAD.ActiveDocument.addObject(
                "Part::Feature", "tmp_" + objName
            )
            newDocObj.Shape = objShape
            newDocObj.purgeTouched()
            self.tmpGrp.addObject(newDocObj)


def SetupProperties():
    setup = PathAreaOp.SetupProperties()
    setup.extend([tup[1] for tup in ObjectProfile.areaOpProperties(False)])
    return setup


def Create(name, obj=None, parentJob=None):
    """Create(name) ... Creates and returns a Profile based on faces operation."""
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectProfile(obj, name, parentJob)
    return obj
