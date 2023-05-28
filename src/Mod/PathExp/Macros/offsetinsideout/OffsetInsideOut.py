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
import Path.Op.PocketShape as PocketShape
import time

__title__ = "Offset Inside-out Dressup"
__author__ = "Russell Johnson (russ4262) <russ4262@gmail.com>"
__doc__ = "Creates a Offset Inside-out dressup on a referenced Pocket operation."
__usage__ = "Import this module.  Run the 'Create(base)' function, passing it the desired Pocket operation as the base parameter."
__url__ = ""
__Wiki__ = ""
__date__ = "2023.05.23"
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


class DressupOffsetInsideOut(object):
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
                "Width value for Offset Inside-out.",
            ),
        )
        obj.addProperty(
            "App::PropertyBool",
            "CutInsideOut",
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
        obj.CutInsideOut = True
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

        pb = OffsetInsideOut(
            obj.Base,
            obj.CutInsideOut,
        )
        obj.Path = pb.execute()

        timeStr = time.strftime("%H:%M:%S", time.gmtime(time.time() - startTime))
        Path.Log.info("Processing time: " + timeStr + "\n")


# Eclass


class OffsetInsideOut:
    """OffsetInsideOut() class...
    This class creates a Offset Inside-out gcode command set from a base Pocket operation.
    The class is instantiated with four arguments:
        baseOp ... base Pocket operation
        profileWidth ... length to extend clearing beyound existing profile pass in base Pocket operation
        stepOver ... stepover percentage for compound profile operation
        cutInsideOut ... OPTIONAL ... defaults to True, set to False to cut inside to out
    Execute the utility by calling `execute()` method. As part of the execution, the base
    Pocket operation will be set inactive and visibility toggled off.
    """

    def __init__(self, baseOp, cutInsideOut=True):
        self.baseOp = baseOp
        self.cutInsideOut = cutInsideOut
        self.toolDiameter = baseOp.ToolController.Tool.Diameter.Value
        self.toolRadius = self.toolDiameter / 2.0
        self.depthParams = self._getDepthParams()
        self.success = False
        self.offsetValues = []
        self.startingPoint = None  # FreeCAD.Vector(0.0, 0.0, 0.0)
        self.shape = None
        self.isFirst = True

    # Private methods
    def _getDepthParams(self):
        """_getDepthParams() ... Calculate matching set of depth parameters from base operation."""
        op = self.baseOp
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

    def _getStartingPoint(self, op):
        self.shape = op.removalshape
        zMax = self.shape.BoundBox.ZMax
        for f in self.shape.Faces:
            if Path.Geom.isRoughly(f.BoundBox.ZMin, zMax):
                if self.cutInsideOut:
                    self.startingPoint = f.CenterOfMass
                else:
                    # self.startingPoint = f.Wires[0].Vertexes[0].Point
                    offsetFace = PathUtils.getOffsetArea(
                        f, -1.0 * (self.toolRadius + op.ExtraOffset.Value)
                    )
                    self.startingPoint = offsetFace.Wires[0].Vertexes[0].Point
                break

    def _startPointCommand(self, op):
        if not op.UseStartPoint:
            return None

        Path.Log.info(f"Including start point: {op.StartPoint}")
        return Path.Command(
            "G0",
            {
                "X": op.StartPoint.x,
                "Y": op.StartPoint.y,
                "F": self.baseOp.ToolController.HorizRapid.Value,
            },
        )

    def _generatePocket(self):
        """_generatePocket() ... Primary fuction to create compound profile commands and gcode."""

        commands = []
        op = self.baseOp
        self._getStartingPoint(op)
        if self.startingPoint is None:
            Path.Log.error("Failed to determine starting point")
            return commands

        startCommand = self._startPointCommand(op)

        opStartingPoint = op.StartPoint
        opUseStartingPoint = op.UseStartPoint
        opActiveState = op.Active

        op.Active = True
        op.StartPoint = self.startingPoint
        op.UseStartPoint = True
        stepDown = self.baseOp.StepDown.Value * 0.9

        # Save current profile op settings for restoration
        startDep = op.StartDepth.Value
        startDepExp = getExpression(op, "StartDepth")
        finalDep = op.FinalDepth.Value
        finalDepExp = getExpression(op, "FinalDepth")

        # Path.Log.info(f"depthParams: {self.depthParams}")
        # Path.Log.info(f"offsetValues: {self.offsetValues}")
        op.setExpression("StartDepth", None)
        op.setExpression("FinalDepth", None)

        isNotFirst = False
        if op.KeepToolDown:
            last = []

            # Loop through depths and offsets to create Compound Pocket commands
            for depth in self.depthParams:
                op.StartDepth.Value = depth + stepDown
                op.FinalDepth.Value = depth
                last = []
                # print(f"     depth: {depth};  offset: {offset}")
                op.recompute()
                # print(f"     count: {len(op.Path.Commands)}")
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
            # Loop through depths and offsets to create Compound Pocket commands
            for depth in self.depthParams:
                op.StartDepth.Value = depth + stepDown
                op.FinalDepth.Value = depth
                # print(f"     depth: {depth};  offset: {offset}")
                # print(f"     count: {len(op.Path.Commands)}")
                op.recompute()
                cmds = op.Path.Commands.copy()
                if isNotFirst:
                    # c1 = cmds.pop(4)
                    # c1 = cmds.pop(3)
                    # c1 = cmds.pop(2)
                    # c1 = cmds.pop(1)
                    c1 = cmds.pop(0)
                isNotFirst = True
                commands.extend(cmds)

        # Restore current profile op settings
        if startDepExp:
            op.setExpression("StartDepth", startDepExp)
        else:
            op.StartDepth.Value = startDep

        if finalDepExp:
            op.setExpression("FinalDepth", finalDepExp)
        else:
            op.FinalDepth.Value = finalDep

        op.Active = opActiveState
        op.StartPoint = opStartingPoint
        op.UseStartPoint = opUseStartingPoint
        op.recompute()
        op.purgeTouched()

        if op.UseStartPoint and self.isFirst:
            commands.insert(2, startCommand)

        # Save commands generated
        self.success = True
        return commands

    # Public method
    def execute(self):
        """execute() ...
        This is the public method to be called to create a OffsetInsideOut object,
        using a modified Path Custom object in the active document."""
        Path.Log.debug("OffsetInsideOut.execute()")
        commands = []

        if (
            not self.baseOp
            or not self.baseOp.isDerivedFrom("Path::Feature")
            or self.baseOp.Name[:12] != "Pocket_Shape"
            or not self.baseOp.Path
        ):
            Path.Log.error("Invalid base operation.")
            return None

        if len(self.baseOp.Path.Commands) == 0:
            Path.Log.warning("No Path Commands for %s" % self.baseOp.Label)
            return []

        self.safeHeight = float(PathUtil.opProperty(self.baseOp, "SafeHeight"))
        self.clearanceHeight = float(
            PathUtil.opProperty(self.baseOp, "ClearanceHeight")
        )

        if not isinstance(self.baseOp.Proxy, PocketShape.ObjectPocket):
            msg = translate(
                "OffsetInsideOutUtility", "Operation is not a Pocket operation."
            )
            Path.Log.error(msg)
            return None

        # initialize variables
        commands.extend(self._generatePocket())
        """for sld in self.baseOp.removalshape.Solids:
            self.shape = sld
            commands.extend(self._generatePocket())
            self.isFirst = False"""

        if self.success:
            # Path.Log.info("Success !")
            return Path.Path(commands)

        Path.Log.error("No success. Aborting transaction")
        return None


# Eclass


def Create(base, name="DressupOffsetInsideOut"):
    """Create(base, name='DressupOffsetInsideOut') ... creates a dressup adding multiple profile passes at each depth."""

    if not base.isDerivedFrom("Path::Feature"):
        Path.Log.error(
            translate(
                "Path_DressupOffsetInsideOut",
                "The selected object is not a Path operation.",
            )
            + "\n"
        )
        return None

    obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    job = PathUtils.findParentJob(base)
    obj.Proxy = DressupOffsetInsideOut(obj, base, job)
    job.Proxy.addOperation(obj, base, True)
    return obj
