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

import math

from PySide import QtCore

import Path
import PathScripts.PathGeom as PathGeom
import PathScripts.PathLog as PathLog
import PathScripts.PathUtils as PathUtils

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader

FreeCAD = LazyLoader("FreeCAD", globals(), "FreeCAD")
Part = LazyLoader("Part", globals(), "Part")
PathFeatureExtensions = LazyLoader(
    "PathScripts.PathFeatureExtensions", globals(), "PathScripts.PathFeatureExtensions"
)

__title__ = "Base rotation class for managing rotation-enabled jobs."
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Base rotation class for managing rotation-enabled jobs."

PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule()


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class ObjectRotation:
    """
    Base rotation class for managing rotation-enabled jobs.
    """

    def __init__(self, job):
        PathLog.track()

        self.job = job
        self.operations = job.Operations.Group
        self.model = job.Model.Group
        self.stock = job.Stock

    # Rotation-related methods
    def _applyRotation(self, obj):
        """_applyRotation(self, obj)
        Orient the model(s) to user-specified fixed index for the operation.
        Returns tuple (isRotationActive, rotationGcodeCommands)"""
        PathLog.track()
        # https://forum.freecadweb.org/viewtopic.php?t=8187#p67122

        if not FeatureFixedRotation & self.features or not self.canDoRotation:
            print("_applyRotation() No rotation enabled.")
            return

        if obj.RotationBase is None or not obj.RotationBase:
            # do not rotate stock and models
            print("_applyRotation() Ignoring rotation.")
            return

        if obj.RotationBaseFace < 1:
            PathLog.error("Face number on Rotation Base must be > 0.")
            return

        # Check if Face number exists on RotationBase
        if obj.RotationBaseFace > len(obj.RotationBase.Shape.Faces):
            msg = "Reference object, {}, only contains {} faces.".format(
                obj.RotationBase.Name, len(obj.RotationBase.Shape.Faces)
            )
            msg += "Verify face number with 'RotationBaseFace'."
            PathLog.error(msg)
            return

        refFace = obj.RotationBase.Shape.getElement(
            "Face{}".format(obj.RotationBaseFace)
        )

        rtn = False
        # self.job = PathUtils.findParentJob(obj)

        # (rtn, rotAng, axisVect, millAxis) = self._analyzeRefFace(obj, refFace)
        (norm, surf) = self._getFaceNormAndSurf(refFace)
        if surf is None or norm is None:
            print("_applyRotation() surf or norm is None.")
            return

        (rtn, rotAng, axis, praInfo) = self.faceRotationAnalysis(
            self.canDoRotation, norm, surf, False
        )

        if rtn:
            axisVectTup = self._getAxisVector(axis)
            if not axisVectTup:
                return
            (millAxis, axisVect) = axisVectTup
            rotCmds = self._applyFixedIndex(self.job, obj, rotAng, axisVect, millAxis)
            print("_applyRotation() added rotation commands")
            self.commandlist.extend(rotCmds)
            self.updateDepths(obj)
        else:
            print("No face rotation analysis returned.")

    def _restoreRotation(self, obj):
        if not FeatureFixedRotation & self.features or not self.canDoRotation:
            print("_restoreRotation() No rotation enabled.")
            return

        #  obj.ResetIndexTo = ["Initial", "Previous", "None"]
        if False and obj.ResetIndexTo == "None":
            # do not rotate stock and models
            print("_applyRotation() No index reset requested.")
            return

        self.resetModelToInitPlacement(obj, True)
        self.commandlist.extend(self.resetRotationCommands)

    def _getAxisVector(self, axis):
        millAxis = ""
        axisVect = FreeCAD.Vector(0, 0, 0)
        if axis == "X":
            millAxis = "A"
            axisVect = FreeCAD.Vector(1, 0, 0)
        elif axis == "Y":
            millAxis = "B"
            axisVect = FreeCAD.Vector(0, 1, 0)
        elif axis == "Z":
            millAxis = "C"
            axisVect = FreeCAD.Vector(0, 0, 1)
        else:
            return None
        return (millAxis, axisVect)

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

        if self.canDoRotation != "B(y)":
            # Rotation is around X-axis, cutter moves along same axis
            if abs(stockBB.YMin) > abs(stockBB.YMax):
                ylim = stockBB.YMin
            else:
                ylim = stockBB.YMax

        if self.canDoRotation != "A(x)":
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

    def faceRotationAnalysis(self, enabRot, norm, surf, revDir=False):
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
        # self.canDoRotation = Job.EnableRotation

        # Enforce limits on VerticalIndexOffset
        if obj.VerticalIndexOffset < -360.0:
            obj.VerticalIndexOffset = -360.0
        elif obj.VerticalIndexOffset > 360.0:
            obj.VerticalIndexOffset = 360.0

        if obj.FixedIndexReference != "None":
            if self.canDoRotation == "Off":
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
                    if millAxis in self.canDoRotation:
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
                self.canDoRotation, norm, surf, False  # obj.OppositeIndexAngle
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

                # if obj.InvertIndexRotation is True:
                #    rotAng = -1 * rotAng

                return (True, rotAng, axisVect, millAxis)
        else:
            PathLog.error("surf: {};  norm: {}".format(surf, norm))
            return (False, 0.0, FreeCAD.Vector(1, 0, 0), "A")

    def _applyFixedIndex(self, job, obj, rotAng, axisVect, millAxis):
        PathLog.debug("activeFixedIndex is True.")
        from Draft import rotate

        gcode = []

        # Reset model and stock to initial orientation, then apply fixed index
        self.resetModelToInitPlacement(obj, True)
        rotate(
            job.Model.Group,
            rotAng,
            center=FreeCAD.Vector(0, 0, 0),
            axis=axisVect,
            copy=False,
        )
        if job.Stock:
            rotate(
                [job.Stock],
                rotAng,
                center=FreeCAD.Vector(0, 0, 0),
                axis=axisVect,
                copy=False,
            )
            job.Stock.purgeTouched()
        for mdl in job.Model.Group:
            mdl.recompute()
            mdl.purgeTouched()

        gcode.append(Path.Command("N100 (Set fixed index or working plane)", {}))
        gcode.append(
            Path.Command("G0", {"Z": obj.ClearanceHeight.Value, "F": self.vertRapid})
        )
        print(
            "  -- rotAng: {};  millAxis: {};  axialFeed: {}".format(
                rotAng, millAxis, self.axialFeed
            )
        )
        gcode.append(Path.Command("G1", {millAxis: rotAng, "F": self.axialRapid}))

        self.resetRotationCommands = [
            Path.Command("G0", {"Z": obj.SafeHeight.Value, "F": self.vertRapid}),
            # Path.Command("G1", {millAxis: -1.0 * rotAng, "F": self.axialRapid}),
            Path.Command("G1", {millAxis: 0.0, "F": self.axialRapid}),
        ]
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
