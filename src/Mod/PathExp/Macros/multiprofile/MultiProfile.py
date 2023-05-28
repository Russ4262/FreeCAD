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

from PySide.QtCore import QT_TRANSLATE_NOOP
import FreeCAD
import Path
import Path.Base.Util as PathUtil
import PathScripts.PathUtils as PathUtils
import Path.Op.Profile as PathProfile
import time

__title__ = "Multi-profile Dressup"
__author__ = "Russell Johnson (russ4262) <russ4262@gmail.com>"
__doc__ = "Creates a Multi-profile dressup on a referenced Profile operation."
__usage__ = "Import this module.  Run the 'Create(base)' function, passing it the desired Profile operation as the base parameter."
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


def getExpression(op, prop):
    """getExpression(op, prop)
    Returns op expression from ExpressionEngine for prop if it exists.
    """
    if hasattr(op, "ExpressionEngine"):
        i = -1
        for (p, exp) in op.ExpressionEngine:
            i += 1
            if p == prop:
                break
        if i >= 0:
            return op.ExpressionEngine[i][1]
    return ""


class DressupMultiProfile(object):
    def __init__(self, obj, base, job):
        self.obj = obj
        self.job = job

        self.safeHeight = None
        self.clearanceHeight = None

        obj.addProperty(
            "App::PropertyBool",
            "Active",
            "Base",
            QT_TRANSLATE_NOOP(
                "App::Property", "Make False, to prevent dressup from generating code"
            ),
        )
        obj.addProperty(
            "App::PropertyLink",
            "Base",
            "Dressup",
            QT_TRANSLATE_NOOP("App::Property", "The base path to modify"),
        )
        obj.addProperty(
            "App::PropertyDistance",
            "ProfileWidth",
            "Dressup",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Width value for multi-profile.",
            ),
        )
        obj.addProperty(
            "App::PropertyBool",
            "CutOutsideIn",
            "Dressup",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Determines if cut starts at outside and moves inward.",
            ),
        )
        obj.addProperty(
            "App::PropertyBool",
            "KeepToolDown",
            "Dressup",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Determines tool remains at depth for lateral move to adjacent profile cut.",
            ),
        )
        obj.addProperty(
            "App::PropertyFloat",
            "StepOver",
            "Dressup",
            QT_TRANSLATE_NOOP(
                "App::Property",
                "Set the stepover percentage, based on the base tool's diameter.",
            ),
        )

        # Set default values
        obj.Active = True
        obj.Base = base
        obj.ProfileWidth = base.ToolController.Tool.Diameter
        obj.CutOutsideIn = True
        obj.KeepToolDown = False
        obj.StepOver = 100.0

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

    def onDocumentRestored(self, obj):
        self.obj = obj

    def onDelete(self, obj, args):
        if obj.Base:
            job = PathUtils.findParentJob(obj)
            if job:
                job.Proxy.addOperation(obj.Base, obj)
            if obj.Base.ViewObject:
                obj.Base.ViewObject.Visibility = True
                obj.Base.Active = True
            obj.Base = None
        return True

    def execute(self, obj):
        startTime = time.time()

        pb = MultiProfile(
            obj.Base,
            obj.ProfileWidth.Value,
            obj.StepOver,
            obj.CutOutsideIn,
            obj.KeepToolDown,
        )
        obj.Path = pb.execute()

        timeStr = time.strftime("%H:%M:%S", time.gmtime(time.time() - startTime))
        Path.Log.info("Processing time: " + timeStr + "\n")


# Eclass


class MultiProfile:
    """MultiProfile() class...
    This class creates a multi-profile gcode command set from a base Profile operation.
    The class is instantiated with four arguments:
        profileOp ... base Profile operation
        profileWidth ... length to extend clearing beyound existing profile pass in base Profile operation
        stepOver ... stepover percentage for compound profile operation
        cutOutsideIn ... OPTIONAL ... defaults to True, set to False to cut inside to out
    Execute the utility by calling `execute()` method. As part of the execution, the base
    Profile operation will be set inactive and visibility toggled off.
    """

    def __init__(
        self, profileOp, profileWidth, stepOver, cutOutsideIn=True, keepToolDown=False
    ):
        self.profileWidth = profileWidth
        self.profileOp = profileOp
        self.stepOver = stepOver
        self.cutOutsideIn = cutOutsideIn
        self.keepToolDown = keepToolDown
        self.toolDiameter = profileOp.ToolController.Tool.Diameter.Value
        self.toolRadius = self.toolDiameter / 2.0
        self.cutOut = self.toolDiameter * (self.stepOver / 100.0)
        self.depthParams = self._getDepthParams()
        self.materialAllowance = self.profileOp.OffsetExtra.Value
        self.compoundProfile = None
        self.success = False
        self.offsetValues = []

    # Private methods
    def _getDepthParams(self):
        """_getDepthParams() ... Calculate matching set of depth parameters from base operation."""
        op = self.profileOp
        finish_step = op.FinishDepth.Value if hasattr(op, "FinishDepth") else 0.0
        cdp = PathUtils.depth_params(
            clearance_height=op.ClearanceHeight.Value,
            safe_height=op.SafeHeight.Value,
            start_depth=op.StartDepth.Value,
            step_down=op.StepDown.Value,
            z_finish_step=finish_step,
            final_depth=op.FinalDepth.Value,
            user_depths=None,
        )
        return [v for v in cdp]

    def _calculateOffsetValues(self):
        """_calculateOffsetValues() ... Calculate list of offset values for path generation."""
        self.offsetValues = []
        # closest pass to stock, regarless of removal direction
        profilePass = self.materialAllowance

        profilePassRemoval = self.materialAllowance + self.toolDiameter
        removalLimit = profilePassRemoval + self.profileWidth
        lastPass = removalLimit - self.toolDiameter

        if self.cutOutsideIn:
            self.offsetValues.append(lastPass)

            while lastPass > profilePass:
                cutPass = lastPass - self.cutOut
                if cutPass > profilePass:
                    self.offsetValues.append(cutPass)
                    lastPass -= self.cutOut
                else:
                    break
            self.offsetValues.append(profilePass)
        else:
            self.offsetValues.append(profilePass)  # first pass
            offset = self.materialAllowance
            cutDist = offset + self.toolDiameter

            while cutDist < removalLimit:
                nextDist = cutDist + self.cutOut
                if nextDist < removalLimit:
                    self.offsetValues.append(offset + self.cutOut)
                    cutDist += self.cutOut
                    offset += self.cutOut
                else:
                    break
            self.offsetValues.append(lastPass)

        # Path.Log.info(f"self.offsetValues: {self.offsetValues}")

    def _generateCompoundProfile(self):
        """_generateCompoundProfile() ... Primary fuction to create compound profile commands and gcode."""

        commands = []
        op = self.profileOp

        opActiveState = op.Active
        op.Active = True
        stepDown = self.profileOp.StepDown.Value * 0.9

        # Save current profile op settings for restoration
        startDep = op.StartDepth.Value
        startDepExp = getExpression(op, "StartDepth")
        finalDep = op.FinalDepth.Value
        finalDepExp = getExpression(op, "FinalDepth")
        offsetExtra = op.OffsetExtra.Value

        # Path.Log.info(f"depthParams: {self.depthParams}")
        # Path.Log.info(f"offsetValues: {self.offsetValues}")
        op.setExpression("StartDepth", None)
        op.setExpression("FinalDepth", None)

        if self.keepToolDown:
            isNotFirst = False
            last = []

            # Loop through depths and offsets to create Compound Profile commands
            for depth in self.depthParams:
                op.StartDepth.Value = depth + stepDown
                op.FinalDepth.Value = depth
                for offset in self.offsetValues:
                    last = []
                    op.OffsetExtra.Value = offset
                    # print(f"     depth: {depth};  offset: {offset}")
                    op.recompute()
                    # print(f"     count: {len(op.Path.Commands)}")
                    # commands.extend(op.Path.Commands.copy())
                    cmds = op.Path.Commands.copy()
                    last.append(cmds.pop())
                    last.append(cmds.pop())
                    if isNotFirst:
                        c1 = cmds.pop(4)
                        c1 = cmds.pop(3)
                        c1 = cmds.pop(2)
                        c1 = cmds.pop(1)
                        c1 = cmds.pop(0)
                    isNotFirst = True
                    commands.extend(cmds)
            commands.extend(last)
        else:
            # Loop through depths and offsets to create Compound Profile commands
            for depth in self.depthParams:
                op.StartDepth.Value = depth + stepDown
                op.FinalDepth.Value = depth
                for offset in self.offsetValues:
                    op.OffsetExtra.Value = offset
                    # print(f"     depth: {depth};  offset: {offset}")
                    op.recompute()
                    # print(f"     count: {len(op.Path.Commands)}")
                    commands.extend(op.Path.Commands.copy())

        # Restore current profile op settings
        if startDepExp:
            op.setExpression("StartDepth", startDepExp)
        else:
            op.StartDepth.Value = startDep

        if finalDepExp:
            op.setExpression("FinalDepth", finalDepExp)
        else:
            op.FinalDepth.Value = finalDep

        op.OffsetExtra.Value = offsetExtra

        op.Active = opActiveState
        op.recompute()
        op.purgeTouched()

        # Save commands generated
        self.success = True
        return commands

    # Public method
    def execute(self):
        """execute() ...
        This is the public method to be called to create a MultiProfile object,
        using a modified Path Custom object in the active document."""
        Path.Log.debug("MultiProfile.execute()")

        if (
            not self.profileOp
            or not self.profileOp.isDerivedFrom("Path::Feature")
            or self.profileOp.Name[:7] != "Profile"
            or not self.profileOp.Path
        ):
            return None

        if len(self.profileOp.Path.Commands) == 0:
            Path.Log.warning("No Path Commands for %s" % self.profileOp.Label)
            return []

        self.safeHeight = float(PathUtil.opProperty(self.profileOp, "SafeHeight"))
        self.clearanceHeight = float(
            PathUtil.opProperty(self.profileOp, "ClearanceHeight")
        )

        if not isinstance(self.profileOp.Proxy, PathProfile.ObjectProfile):
            msg = translate(
                "CompoundProfileUtility", "Operation is not a Profile operation."
            )
            Path.Log.error(msg)
            return None

        # initialize variables
        self._calculateOffsetValues()
        commands = self._generateCompoundProfile()

        if self.success:
            # Path.Log.info("Success !")
            return Path.Path(commands)

        Path.Log.error("No success. Aborting transaction")
        return None


# Eclass


def Create(base, name="DressupMultiProfile"):
    """Create(base, name='DressupMultiProfile') ... creates a dressup adding multiple profile passes at each depth."""

    if not base.isDerivedFrom("Path::Feature"):
        Path.Log.error(
            translate(
                "Path_DressupMultiProfile",
                "The selected object is not a Path operation.",
            )
            + "\n"
        )
        return None

    obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    job = PathUtils.findParentJob(base)
    obj.Proxy = DressupMultiProfile(obj, base, job)
    job.Proxy.addOperation(obj, base, True)
    return obj
