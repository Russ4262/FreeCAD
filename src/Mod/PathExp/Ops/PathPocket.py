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

from PySide.QtCore import QT_TRANSLATE_NOOP
import FreeCAD
import Part
import Path.Log as PathLog
import Path.Op.Base as PathOp
import Ops.PathPocketBase as PathPocketBase
import PathScripts.PathUtils as PathUtils

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader

PathGeom = LazyLoader("Path.Geom", globals(), "Path.Geom")
FeatureExtensions = LazyLoader(
    # "PathScripts.PathFeatureExtensions", globals(), "PathScripts.PathFeatureExtensions"
    "Path.Op.FeatureExtension",
    globals(),
    "Path.Op.FeatureExtension",
)

__title__ = "Path 3D Pocket Operation"
__author__ = "Yorik van Havre <yorik@uncreated.net>"
__url__ = "https://www.freecadweb.org"
__doc__ = "Class and implementation of the 3D Pocket operation."
__created__ = "2014"

if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


translate = FreeCAD.Qt.translate


class ObjectPocket(PathPocketBase.ObjectPocket):
    """Proxy object for Pocket operation."""

    def pocketOpFeatures(self, obj):
        return PathOp.FeatureNoFinalDepth

    def initPocketOp(self, obj):
        """initPocketOp(obj) ... setup receiver"""
        if not hasattr(obj, "HandleMultipleFeatures"):
            obj.addProperty(
                "App::PropertyEnumeration",
                "HandleMultipleFeatures",
                "Pocket",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Choose how to process multiple Base Geometry features.",
                ),
            )

        FeatureExtensions.initialize_properties(obj)

        if not hasattr(obj, "AdaptivePocketStart"):
            obj.addProperty(
                "App::PropertyBool",
                "AdaptivePocketStart",
                "Pocket",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Use adaptive algorithm to eliminate excessive air milling above planar pocket top.",
                ),
            )
        if not hasattr(obj, "AdaptivePocketFinish"):
            obj.addProperty(
                "App::PropertyBool",
                "AdaptivePocketFinish",
                "Pocket",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Use adaptive algorithm to eliminate excessive air milling below planar pocket bottom.",
                ),
            )
        if not hasattr(obj, "ProcessStockArea"):
            obj.addProperty(
                "App::PropertyBool",
                "ProcessStockArea",
                "Pocket",
                QT_TRANSLATE_NOOP(
                    "App::Property",
                    "Process the model and stock in an operation with no Base Geometry selected.",
                ),
            )

        # populate the property enumerations
        for n in self.propertyEnumerations():
            setattr(obj, n[0], n[1])

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
            "HandleMultipleFeatures": [
                (translate("Path_Pocket", "Collectively"), "Collectively"),
                (translate("Path_Pocket", "Individually"), "Individually"),
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

    def opOnDocumentRestored(self, obj):
        """opOnDocumentRestored(obj) ... adds the properties if they doesn't exist."""
        self.initPocketOp(obj)

    def pocketInvertExtraOffset(self):
        return False

    def areaOpChildSetDefaultValues(self, obj, job):
        """areaOpChildSetDefaultValues(obj, job) ... set default values"""
        obj.StepOver = 100
        obj.ZigZagAngle = 45
        obj.HandleMultipleFeatures = "Collectively"
        obj.AdaptivePocketStart = False
        obj.AdaptivePocketFinish = False
        obj.ProcessStockArea = False
        FeatureExtensions.set_default_property_values(obj, job)

    def areaOpShapes_orig(self, obj):
        """areaOpShapes(obj) ... return shapes representing the solids to be removed."""
        PathLog.track()

        subObjTups = []
        removalshapes = []

        avoidFeatures = list()

        # Get extensions and identify faces to avoid
        extensions = FeatureExtensions.getExtensions(obj)
        for e in extensions:
            if e.avoid:
                avoidFeatures.append(e.feature)

        if obj.Base:
            PathLog.debug("base items exist.  Processing... ")

            self.exts = []
            for base in obj.Base:
                baseDepth = base[0].Shape.BoundBox.ZLength
                PathLog.debug("obj.Base item: {}".format(base))
                allSubsFaceType = True
                Faces = []
                baseShapes = [base[0].Shape]

                # Check if all subs are faces
                for sub in base[1]:
                    # Add faces for extensions
                    for ext in extensions:
                        if not ext.avoid and ext.feature == sub:
                            wire = ext.getWire()
                            if wire:
                                faces = ext.getExtensionFaces(wire)
                                for f in faces:
                                    # self.horiz.append(f)
                                    Faces.append(f)
                                    baseShapes.append(
                                        f.extrude(FreeCAD.Vector(0, 0, -1 * baseDepth))
                                    )
                                    self.exts.append(f)

                    if "Face" in sub:
                        face = getattr(base[0].Shape, sub)
                        Faces.append(face)
                        subObjTups.append((sub, face))
                    else:
                        allSubsFaceType = False
                        break

                baseShape = Part.makeCompound(baseShapes)
                if len(Faces) == 0:
                    allSubsFaceType = False

                if (
                    allSubsFaceType is True
                    and obj.HandleMultipleFeatures == "Collectively"
                ):
                    (fzmin, fzmax) = self.getMinMaxOfFaces(Faces)
                    if obj.FinalDepth.Value < fzmin:
                        PathLog.warning(
                            translate(
                                "PathPocket",
                                "Final depth set below ZMin of face(s) selected.",
                            )
                        )

                    if (
                        obj.AdaptivePocketStart is True
                        or obj.AdaptivePocketFinish is True
                    ):
                        pocketTup = self.calculateAdaptivePocket(obj, base, subObjTups)
                        if pocketTup is not False:
                            obj.removalshape = pocketTup[0]
                            removalshapes.append(pocketTup)  # (shape, isHole, detail)
                    else:
                        shape = Part.makeCompound(Faces)
                        env = PathUtils.getEnvelope(
                            baseShape, subshape=shape, depthparams=self.depthparams
                        )
                        rawRemovalShape = env.cut(baseShape)  # base[0].Shape
                        faceExtrusions = [
                            f.extrude(FreeCAD.Vector(0.0, 0.0, 1.0)) for f in Faces
                        ]
                        obj.removalshape = _identifyRemovalSolids(
                            rawRemovalShape, faceExtrusions
                        )
                        removalshapes.append(
                            (obj.removalshape, False, "3DPocket")
                        )  # (shape, isHole, detail)
                else:
                    for sub in base[1]:
                        if "Face" in sub:
                            shape = Part.makeCompound([getattr(base[0].Shape, sub)])
                        else:
                            edges = [getattr(base[0].Shape, sub) for sub in base[1]]
                            shape = Part.makeFace(edges, "Part::FaceMakerSimple")

                        env = PathUtils.getEnvelope(
                            base[0].Shape, subshape=shape, depthparams=self.depthparams
                        )
                        rawRemovalShape = env.cut(base[0].Shape)
                        faceExtrusions = [shape.extrude(FreeCAD.Vector(0.0, 0.0, 1.0))]
                        obj.removalshape = _identifyRemovalSolids(
                            rawRemovalShape, faceExtrusions
                        )
                        removalshapes.append((obj.removalshape, False, "3DPocket"))

        else:  # process the job base object as a whole
            PathLog.debug("processing the whole job base object")
            for base in self.model:
                if obj.ProcessStockArea is True:
                    job = PathUtils.findParentJob(obj)

                    stockEnvShape = PathUtils.getEnvelope(
                        job.Stock.Shape, subshape=None, depthparams=self.depthparams
                    )

                    rawRemovalShape = stockEnvShape.cut(base.Shape)
                else:
                    env = PathUtils.getEnvelope(
                        base.Shape, subshape=None, depthparams=self.depthparams
                    )
                    rawRemovalShape = env.cut(base.Shape)

                # Identify target removal shapes after cutting envelope with base shape
                removalSolids = [
                    s
                    for s in rawRemovalShape.Solids
                    if PathGeom.isRoughly(
                        s.BoundBox.ZMax, rawRemovalShape.BoundBox.ZMax
                    )
                ]

                # Fuse multiple solids
                if len(removalSolids) > 1:
                    seed = removalSolids[0]
                    for tt in removalSolids[1:]:
                        fusion = seed.fuse(tt)
                        seed = fusion
                    removalShape = seed
                else:
                    removalShape = removalSolids[0]

                obj.removalshape = removalShape
                removalshapes.append((obj.removalshape, False, "3DPocket"))

        """removalTups = []
        for shp, isHole, detail in removalshapes:
            if hasattr(shp, "Solids") and len(shp.Solids) > 1:
                for s in shp.Solids:
                    removalTups.append((s.copy(), isHole, detail))
            else:
                removalTups.append((shp, isHole, detail))
        return removalTups"""
        return removalshapes

    def areaOpShapes(self, obj):
        """areaOpShapes(obj) ... returns envelope for all base shapes or wires"""

        shapes = []
        # print("No shapes to process... ")
        if obj.TargetShape:
            # obj.StartDepth = obj.TargetShape.StartDepth
            # obj.FinalDepth = obj.TargetShape.FinalDepth
            print(f"SD: {obj.StartDepth.Value};  FD: {obj.FinalDepth.Value}")
            for s in obj.TargetShape.Shape.Solids:
                isHole = True  # if obj.Side == "Inside" else False
                # print(f"isHole: {isHole}")
                shp = s.copy()
                shp.translate(obj.TargetShape.CenterOfRotation.negative())
                tup = shp, isHole, "3DPocket"
                shapes.append(tup)

        return shapes


def SetupProperties():
    setup = PathPocketBase.SetupProperties() + ["HandleMultipleFeatures"]
    setup.extend(
        FeatureExtensions.SetupProperties()
    )  # Add properties from Extensions Feature
    return setup


def Create(name, obj=None, parentJob=None):
    """Create(name) ... Creates and returns a Pocket operation."""
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectPocket(obj, name, parentJob)
    return obj
