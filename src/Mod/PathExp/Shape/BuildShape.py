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

# import Ops.PathOp as PathOp
# import Shape.PathShape as PathShape
import Ops.PathOp2 as PathShape
import PathScripts.PathLog as PathLog
import FreeCAD
import Part
import Features.PathFeatureExtensions as FeatureExtensions
import Macros.Macro_CombineRegions as CombineRegions


__doc__ = "Class and implementation of the Adaptive path operation."


if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


translate = FreeCAD.Qt.translate


class BuildShape(PathShape.ObjectOp2):
    def opFeatures(self, obj):
        """opFeatures(obj) ... returns the OR'ed list of features used and supported by the operation.
        The default implementation returns "FeatureTool | FeatureDepths | FeatureHeights | FeatureStartPoint"
        Should be overwritten by subclasses."""
        return (
            PathShape.FeatureBaseGeometry
            | PathShape.FeatureBaseEdges
            | PathShape.FeatureHeightsDepths
            | PathShape.FeatureExtensions
            | PathShape.FeatureTool
        )

    def initOperation(self, obj):
        """initOperation(obj) ... implement to create additional properties.
        Should be overwritten by subclasses."""
        # obj.addProperty("Part::PropertyPartShape", "Shape", "Path")
        obj.setEditorMode("Shape", 1)  # read-only

        for n in self.propertyEnumerations():
            setattr(obj, n[0], n[1])

        FeatureExtensions.initialize_properties(obj)

    def opPropertyDefinitions(self):
        """opPropertyDefinitions(obj) ... Store operation specific properties"""

        return [
            (
                "App::PropertyDistance",
                "DepthAllowance",
                "Shape",
                translate(
                    "Path",
                    "Set the material depth allowance for the target shape.",
                ),
            ),
            (
                "App::PropertyBool",
                "RespectFeatureHoles",
                "Shape",
                translate("Path", "Set True to respect feature holes."),
            ),
            (
                "App::PropertyBool",
                "RespectMergedHoles",
                "Shape",
                translate(
                    "Path",
                    "Set True to respect holes formed by merger of faces or regions.",
                ),
            ),
        ]

    def opPropertyDefaults(self, obj, job):
        """opPropertyDefaults(obj, job) ... returns a dictionary of default values
        for the operation's properties."""
        defaults = {
            "RespectFeatureHoles": True,
            "RespectMergedHoles": True,
            "DepthAllowance": 0.0,
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
        FeatureExtensions.set_default_property_values(obj, job)

    def opOnDocumentRestored(self, obj):
        FeatureExtensions.initialize_properties(obj)

    def opUpdateDepths(self, obj):
        """opUpdateDepths(obj) ... Implement special depths calculation."""
        # Set Final Depth to bottom of model if whole model is used
        if not obj.Base or len(obj.Base) == 0:
            if len(self.job.Model.Group) == 1:
                finDep = self.job.Model.Group[0].Shape.BoundBox.ZMin
            else:
                finDep = min([m.Shape.BoundBox.ZMin for m in self.job.Model.Group])
        else:
            finDep = obj.Base[0][0].Shape.getElement(obj.Base[0][1][0]).BoundBox.ZMax
            for base, subs in obj.Base:
                for s in subs:
                    finDep = min(finDep, base.Shape.getElement(s).BoundBox.ZMin)
        obj.setExpression("OpFinalDepth", "{} mm".format(finDep))

    def showShape(self, obj):
        shpObj = Part.show(obj.Shape, "Shape")
        shpObj.Label = f"Target Shape - {obj.Name}"

    def opExecute(self, obj):
        """opExecute(obj) ... called whenever the receiver needs to be recalculated.
        See documentation of execute() for a list of base functionality provided."""
        PathLog.info("BuildShape.opExecute()")
        avoidFeatures = []
        sourceGeometry = []
        targetRegions = []
        targetShapes = []
        stockTop = self.job.Stock.Shape.BoundBox.ZMax
        stockThickness = self.job.Stock.Shape.BoundBox.ZLength

        # Get extensions and identify faces to avoid
        extensions = FeatureExtensions.getExtensions(obj)
        for e in extensions:
            if e.extType == "Avoid":
                avoidFeatures.append(e.feature)

        if obj.Base:
            # PathLog.info("Processing base items ...")
            for (base, subList) in obj.Base:
                rawFaces = []
                for sub in subList:
                    if sub.startswith("Face"):
                        rawFaces.append(base.Shape.getElement(sub))
                        # Add applicable extension
                        for ext in extensions:
                            if ext.feature == sub:
                                wire = ext.getWire()
                                if wire:
                                    faces = ext.getExtensionFaces(wire)
                                    for f in faces:
                                        rawFaces.append(f)
                                        # self.exts.append(f)
                            else:
                                PathLog.debug(f"No extension found for {ext.feature}")
                    else:
                        PathLog.error(
                            f"Build Shape does not support {base.Label}.{sub}"
                        )
                # Efor

                # region, fusedFaces = CombineRegions._executeAsMacro2(rawFaces)  # Uses Gui if available
                region, fusedFaces = CombineRegions._executeAsMacro3(
                    rawFaces, obj.RespectFeatureHoles, obj.RespectMergedHoles
                )
                region.translate(FreeCAD.Vector(0.0, 0.0, obj.FinalDepth.Value))
                targetRegions.append(region)
                sourceGeometry.append(fusedFaces)

                extLen = stockTop - obj.FinalDepth.Value
                if extLen > 0.0:
                    extReg = region.extrude(FreeCAD.Vector(0.0, 0.0, extLen))
                    extSrc = fusedFaces.extrude(
                        FreeCAD.Vector(0.0, 0.0, -1.0 * stockThickness)
                    )
                    baseCopy = base.Shape.copy()
                    trimWithFaces = extReg.cut(extSrc)
                    trimWithBase = trimWithFaces.cut(baseCopy)
                    shape = trimWithBase.common(self.job.Stock.Shape)
                    targetShapes.append(shape)
                else:
                    PathLog.warning("stock top - final depth - depth allowance < 0.0")
            # Efor

            obj.Shape = Part.makeCompound(targetShapes)


# Eclass


def SetupProperties():
    setup = ["RespectFeatureHoles", "RespectMergedHoles", "DepthAllowance"]
    # Add properties from Extensions Feature
    setup.extend(FeatureExtensions.SetupProperties())

    return setup


def Create(name, obj=None, parentJob=None):
    """Create(name) ... Creates and returns a Target Shape object."""
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = BuildShape(obj, name, parentJob)
    return obj


FreeCAD.Console.PrintMessage("Imported BuildShape module from PathExp workbench.\n")
