# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2019 sliptonic <shopinthewoods@gmail.com>               *
# *   Copyright (c) 2023 Russell Johnson (russ4262) <russ4262@gmail.com>    *
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
import PathScripts.PathUtils as PathUtils
import Part
import shapebuilder.ShapeBuilderUtils as ShapeBuilderUtils
import time
from PySide.QtCore import QT_TRANSLATE_NOOP

__title__ = "Shape Builder"
__author__ = "Russell Johnson (russ4262) <russ4262@gmail.com>"
__doc__ = "Using selected features, builds a shape purposed for a target shape."
__usage__ = "Import this module.  Run the 'Create(features)' function, passing it the desired features parameter,\
    as a list of tuples (base, features_list)."
__url__ = ""
__Wiki__ = ""
__date__ = "2023.04.22"
__version__ = 1.0

if False:
    Path.Log.setLevel(Path.Log.Level.DEBUG, Path.Log.thisModule())
    Path.Log.trackModule(Path.Log.thisModule())
else:
    Path.Log.setLevel(Path.Log.Level.INFO, Path.Log.thisModule())


translate = FreeCAD.Qt.translate


class ShapeBuilder(object):
    def __init__(self, obj, features, job):
        self.obj = obj
        self.job = job
        self.features = features
        self.baseReady = False

        """
        obj.addProperty(
            "App::PropertyBool",
            "Active",
            "Base",
            QT_TRANSLATE_NOOP(
                "App::Property", "Make False, to prevent dressup from generating code"
            ),
        )
        """
        obj.addProperty(
            "App::PropertyLinkSubListGlobal",
            "Base",
            "Shape",
            QT_TRANSLATE_NOOP("App::Property", "The base geometry for this operation"),
        )
        obj.addProperty(
            "App::PropertyDistance",
            "StartDepth",
            "Shape",
            QT_TRANSLATE_NOOP(
                "App::Property", "Starting Depth of Tool- first cut depth in Z"
            ),
        )
        obj.addProperty(
            "App::PropertyDistance",
            "FinalDepth",
            "Shape",
            QT_TRANSLATE_NOOP(
                "App::Property", "Final Depth of Tool- lowest value in Z"
            ),
        )

        obj.addProperty(
            "App::PropertyDistance",
            "OpStartDepth",
            "Op Values",
            QT_TRANSLATE_NOOP(
                "App::Property", "Holds the calculated value for the StartDepth"
            ),
        )
        obj.addProperty(
            "App::PropertyDistance",
            "OpFinalDepth",
            "Op Values",
            QT_TRANSLATE_NOOP(
                "App::Property", "Holds the calculated value for the FinalDepth"
            ),
        )

        obj.setEditorMode("OpStartDepth", 1)  # read-only
        obj.setEditorMode("OpFinalDepth", 1)  # read-only

        # Set default values
        # obj.Active = True
        obj.Base = []
        obj.StartDepth = 0.0
        obj.FinalDepth = -1.0

        if self.applyExpression(obj, "StartDepth", job.SetupSheet.StartDepthExpression):
            obj.OpStartDepth = 1.0
        else:
            obj.StartDepth = 1.0
        if self.applyExpression(obj, "FinalDepth", job.SetupSheet.FinalDepthExpression):
            obj.OpFinalDepth = 0.0
        else:
            obj.FinalDepth = 0.0

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

    def onDocumentRestored(self, obj):
        self.obj = obj

    def onDelete(self, obj, args):
        return True

    def onChanged(self, obj, prop):
        """onChanged(obj, prop) ... base implementation of the FC notification framework.
        Do not overwrite, overwrite opOnChanged() instead."""

        def sanitizeBase(obj):
            """sanitizeBase(obj) ... check if Base is valid and clear on errors."""
            if hasattr(obj, "Base"):
                try:
                    for (o, sublist) in obj.Base:
                        for sub in sublist:
                            o.Shape.getElement(sub)
                except Part.OCCError:
                    Path.Log.error(
                        "{} - stale base geometry detected - clearing.".format(
                            obj.Label
                        )
                    )
                    obj.Base = []
                    return True
            return False

        # there's a bit of cycle going on here, if sanitizeBase causes the transaction to
        # be cancelled we end right here again with the unsainitized Base - if that is the
        # case, stop the cycle and return immediately
        if prop == "Base" and sanitizeBase(obj):
            return

        if "Restore" not in obj.State and prop in ["Base", "StartDepth", "FinalDepth"]:
            self.updateDepths(obj, True)

    def applyExpression(self, obj, prop, expr):
        """applyExpression(obj, prop, expr) ... set expression expr on obj.prop if expr is set"""
        if expr:
            obj.setExpression(prop, expr)
            return True
        return False

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

        stockBB = self.job.Stock.Shape.BoundBox
        zmin = stockBB.ZMin
        zmax = stockBB.ZMax

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
                        Path.Log.error(e)

        else:
            # clearing with stock boundaries
            job = PathUtils.findParentJob(obj)
            zmax = stockBB.ZMax
            zmin = job.Proxy.modelBoundBox(job).ZMax

        # first set update final depth, it's value is not negotiable
        if not Path.Geom.isRoughly(obj.OpFinalDepth.Value, zmin):
            obj.OpFinalDepth = zmin
        zmin = obj.OpFinalDepth.Value

        def minZmax(z):
            if hasattr(obj, "StepDown") and not Path.Geom.isRoughly(
                obj.StepDown.Value, 0
            ):
                return z + obj.StepDown.Value
            else:
                return z + 1

        # ensure zmax is higher than zmin
        if (zmax - 0.0001) <= zmin:
            zmax = minZmax(zmin)

        # update start depth if requested and required
        if not Path.Geom.isRoughly(obj.OpStartDepth.Value, zmax):
            obj.OpStartDepth = zmax

    def execute(self, obj):
        startTime = time.time()

        edges, faces = ShapeBuilderUtils.getSelectedEdgesAndFaces()
        comp = Part.makeCompound(edges + faces)
        zHeight = comp.BoundBox.ZMax
        print(f"zHeight: {zHeight}")

        edgeFaces, openWires = ShapeBuilderUtils.edgesToFaces(edges)
        allFaces = faces + edgeFaces
        region = ShapeBuilderUtils.combineFaces(allFaces, zHeight)
        if region:
            Part.show(region, "Region")
            obj.Shape = region
        else:
            obj.Shape = None

        timeStr = time.strftime("%H:%M:%S", time.gmtime(time.time() - startTime))
        Path.Log.info("Processing time: " + timeStr + "\n")


# Eclass


def Create(features, obj=None, name="ShapeBuilder"):
    """Create(features, obj=None, name="ShapeBuilder") ... Creates a target shape for Path operation."""

    if not isinstance(features, list):
        Path.Log.error(
            translate(
                "Path_ShapeBuilder",
                "The features parameter is not a list.",
            )
            + "\n"
        )
        return None

    # obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", name)
    job = PathUtils.findParentJob(obj)
    obj.Proxy = ShapeBuilder(obj, features, job)
    job.Proxy.addOperation(obj)
    return obj
