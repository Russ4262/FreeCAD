# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2014 Yorik van Havre <yorik@uncreated.net>              *
# *   Copyright (c) 2016 sliptonic <shopinthewoods@gmail.com>               *
# *   Copyright (c) 2018 Kresimir Tusek <kresimir.tusek@gmail.com>          *
# *   Copyright (c) 2019-2021 Schildkroet                                   *
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
import Path.Log as PathLog
import PathScripts.PathUtils as PathUtils

from PySide import QtCore

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader

Part = LazyLoader("Part", globals(), "Part")
DraftGeomUtils = LazyLoader("DraftGeomUtils", globals(), "DraftGeomUtils")
PathGeom = LazyLoader("Path.Geom", globals(), "Path.Geom")
PathOpTools = LazyLoader("Path.Base.Util", globals(), "Path.Base.Util")
# time = LazyLoader('time', globals(), 'time')
json = LazyLoader("json", globals(), "json")
math = LazyLoader("math", globals(), "math")
area = LazyLoader("area", globals(), "area")

if FreeCAD.GuiUp:
    coin = LazyLoader("pivy.coin", globals(), "pivy.coin")
    FreeCADGui = LazyLoader("FreeCADGui", globals(), "FreeCADGui")


__title__ = "Path Strategy Adaptive"
__author__ = "Yorik van Havre; sliptonic (Brad Collette)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Path Adaptive strategy for path generation."


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class StrategyAdaptive:
    """class StrategyAdaptive
    Class and implementation of the current Adaptive operation, used as direct path generation."
    """

    sceneGraph = None
    scenePathNodes = []  # for scene cleanup aftewards
    topZ = 10

    def __init__(
        self,
        faces,
        toolController,
        depthParams,
        startDepth,
        finalDepth,
        operationType,
        cutSide,
        forceInsideOut,
        materialAllowance,
        stepOver,
        liftDistance,
        finishingProfile,
        helixAngle,
        helixConeAngle,
        useHelixArcs,
        helixDiameterLimit,
        keepToolDownRatio,
        tolerance,
        stopped,
        stopProcessing,
        stockType,
        stockShape,
        job,
        adaptiveOutputState,
        adaptiveInputState,
        viewObject,
    ):
        PathLog.debug("StrategyAdaptive.__init__()")
        PathLog.debug(
            "StrategyAdaptive.__init__() materialAllowance: {}".format(
                materialAllowance
            )
        )

        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        self.useHelixEntry = True  # Set False to disable helix entry
        self.adaptiveGeometry = []
        self.pathArray = []
        self.commandList = []

        # Apply limits to argument values
        if tolerance < 0.001:
            tolerance = 0.001

        if helixAngle < 1.0:
            helixAngle = 1.0
        if helixAngle > 89.0:
            helixAngle = 89.0

        if helixConeAngle < 0.0:
            helixConeAngle = 0.0

        self.faces = faces
        self.depthParams = depthParams
        self.operationType = operationType
        self.cutSide = cutSide
        self.forceInsideOut = forceInsideOut
        self.materialAllowance = materialAllowance
        self.stockType = stockType
        self.stockShape = stockShape
        self.job = job
        self.stepOver = stepOver
        self.liftDistance = liftDistance
        self.finishingProfile = finishingProfile
        self.helixAngle = helixAngle
        self.helixConeAngle = helixConeAngle
        self.useHelixArcs = useHelixArcs
        self.helixDiameterLimit = helixDiameterLimit
        self.keepToolDownRatio = keepToolDownRatio
        self.tolerance = tolerance
        self.stopped = stopped
        self.stopProcessing = stopProcessing
        self.adaptiveOutputState = adaptiveOutputState
        self.adaptiveInputState = adaptiveInputState
        self.viewObject = viewObject

        self.clearanceHeight = depthParams.clearance_height
        self.safeHeight = depthParams.safe_height
        self.startDepth = startDepth
        self.finishDepth = depthParams.z_finish_depth
        self.finalDepth = finalDepth
        self.stepDown = depthParams.step_down
        if self.stepDown < 0.1:
            self.stepDown = 0.1

        self.vertFeed = toolController.VertFeed.Value
        self.horizFeed = toolController.HorizFeed.Value
        self.toolDiameter = (
            toolController.Tool.Diameter.Value
            if hasattr(toolController.Tool.Diameter, "Value")
            else float(toolController.Tool.Diameter)
        )

        # self.stockShape = stock.Shape
        self.stockShape = stockShape
        self.generateGeometry = False
        self.generateCommands = True
        self.guiPreviewPaths = False

    # Private methods
    def _convertTo2d(self, pathArray):
        output = []
        for path in pathArray:
            pth2 = []
            for edge in path:
                for pt in edge:
                    pth2.append([pt[0], pt[1]])
            output.append(pth2)
        return output

    def _sceneDrawPath(self, path, color=(0, 0, 1)):
        coPoint = coin.SoCoordinate3()

        pts = []
        for pt in path:
            pts.append([pt[0], pt[1], self.topZ])

        coPoint.point.setValues(0, len(pts), pts)
        ma = coin.SoBaseColor()
        ma.rgb = color
        li = coin.SoLineSet()
        li.numVertices.setValue(len(pts))
        pathNode = coin.SoSeparator()
        pathNode.addChild(coPoint)
        pathNode.addChild(ma)
        pathNode.addChild(li)
        self.sceneGraph.addChild(pathNode)
        self.scenePathNodes.append(pathNode)  # for scene cleanup afterwards

    def _sceneClean(self):
        for n in self.scenePathNodes:
            self.sceneGraph.removeChild(n)

        del self.scenePathNodes[:]

    def _discretize(self, edge, flipDirection=False):
        pts = edge.discretize(Deflection=0.0001)
        if flipDirection:
            pts.reverse()

        return pts

    def _calcHelixConePoint(self, height, cur_z, radius, angle):
        x = ((height - cur_z) / height) * radius * math.cos(math.radians(angle) * cur_z)
        y = ((height - cur_z) / height) * radius * math.sin(math.radians(angle) * cur_z)
        z = cur_z

        return {"X": x, "Y": y, "Z": z}

    def _generateGCode(self, adaptiveResults):
        PathLog.debug("StrategyAdaptive._generateGCode()")
        self.commandList = []
        commandList = []
        motionCutting = area.AdaptiveMotionType.Cutting
        motionLinkClear = area.AdaptiveMotionType.LinkClear
        motionLinkNotClear = area.AdaptiveMotionType.LinkNotClear

        # pylint: disable=unused-argument
        if len(adaptiveResults) == 0 or len(adaptiveResults[0]["AdaptivePaths"]) == 0:
            # PathLog.info("No adaptiveResults to process.")
            return

        helixRadius = 0.0
        for region in adaptiveResults:
            p1 = region["HelixCenterPoint"]
            p2 = region["StartPoint"]
            r = math.sqrt(
                (p1[0] - p2[0]) * (p1[0] - p2[0]) + (p1[1] - p2[1]) * (p1[1] - p2[1])
            )
            if r > helixRadius:
                helixRadius = r

        passStartDepth = self.startDepth

        length = 2 * math.pi * helixRadius

        helixAngleRad = math.pi * self.helixAngle / 180.0
        depthPerOneCircle = length * math.tan(helixAngleRad)
        # print("Helix circle depth: {}".format(depthPerOneCircle))

        stepUp = self.liftDistance
        if stepUp < 0:
            stepUp = 0

        stepDown = self.stepDown
        finish_step = self.finishDepth
        if finish_step > stepDown:
            finish_step = stepDown

        depth_params = PathUtils.depth_params(
            clearance_height=self.clearanceHeight,
            safe_height=self.safeHeight,
            start_depth=self.startDepth,
            step_down=self.stepDown,
            z_finish_step=finish_step,
            final_depth=self.finalDepth,
            user_depths=None,
        )

        # ml: this is dangerous because it'll hide all unused variables hence forward
        #     however, I don't know what lx and ly signify so I'll leave them for now
        # russ4262: I think that the `l` in `lx, ly, and lz` stands for `last`.
        # pylint: disable=unused-variable
        # lx = adaptiveResults[0]["HelixCenterPoint"][0]
        # ly = adaptiveResults[0]["HelixCenterPoint"][1]
        lz = passStartDepth  # lz is likely `last Z depth`
        step = 0

        for passEndDepth in depth_params.data:
            step = step + 1

            for region in adaptiveResults:
                startAngle = math.atan2(
                    region["StartPoint"][1] - region["HelixCenterPoint"][1],
                    region["StartPoint"][0] - region["HelixCenterPoint"][0],
                )

                # lx = region["HelixCenterPoint"][0]
                # ly = region["HelixCenterPoint"][1]

                passDepth = passStartDepth - passEndDepth

                p1 = region["HelixCenterPoint"]
                p2 = region["StartPoint"]
                helixRadius = math.sqrt(
                    (p1[0] - p2[0]) * (p1[0] - p2[0])
                    + (p1[1] - p2[1]) * (p1[1] - p2[1])
                )
                PathLog.info(
                    f"P1: {p1[0]}, {p1[1]};   P2: {p2[0]}, {p2[1]};  helixRadius: {helixRadius}"
                )

                # Helix ramp
                PathLog.info(f"Using helix entry: {self.useHelixEntry}")
                PathLog.info(f"helixRadius: {helixRadius} mm")
                if self.useHelixEntry and helixRadius > 0.01:
                    PathLog.info("Using helix entry.")
                    r = helixRadius - 0.01

                    maxfi = passDepth / depthPerOneCircle * 2 * math.pi
                    fi = 0
                    offsetFi = -maxfi + startAngle - math.pi / 16

                    helixStart = [
                        region["HelixCenterPoint"][0] + r * math.cos(offsetFi),
                        region["HelixCenterPoint"][1] + r * math.sin(offsetFi),
                    ]

                    commandList.append(
                        Path.Command("(Helix to depth: %f)" % passEndDepth)
                    )

                    if not self.useHelixArcs:
                        # rapid move to start point
                        commandList.append(
                            Path.Command("G0", {"Z": self.clearanceHeight})
                        )
                        commandList.append(
                            Path.Command(
                                "G0",
                                {
                                    "X": helixStart[0],
                                    "Y": helixStart[1],
                                    "Z": self.clearanceHeight,
                                },
                            )
                        )

                        # rapid move to safe height
                        commandList.append(
                            Path.Command(
                                "G0",
                                {
                                    "X": helixStart[0],
                                    "Y": helixStart[1],
                                    "Z": self.safeHeight,
                                },
                            )
                        )

                        # move to start depth
                        commandList.append(
                            Path.Command(
                                "G1",
                                {
                                    "X": helixStart[0],
                                    "Y": helixStart[1],
                                    "Z": passStartDepth,
                                    "F": self.vertFeed,
                                },
                            )
                        )

                        if self.helixConeAngle == 0:
                            while fi < maxfi:
                                x = region["HelixCenterPoint"][0] + r * math.cos(
                                    fi + offsetFi
                                )
                                y = region["HelixCenterPoint"][1] + r * math.sin(
                                    fi + offsetFi
                                )
                                z = passStartDepth - fi / maxfi * (
                                    passStartDepth - passEndDepth
                                )
                                commandList.append(
                                    Path.Command(
                                        "G1",
                                        {"X": x, "Y": y, "Z": z, "F": self.vertFeed},
                                    )
                                )
                                # lx = x
                                # ly = y
                                fi = fi + math.pi / 16

                            # one more circle at target depth to make sure center is cleared
                            maxfi = maxfi + 2 * math.pi
                            while fi < maxfi:
                                x = region["HelixCenterPoint"][0] + r * math.cos(
                                    fi + offsetFi
                                )
                                y = region["HelixCenterPoint"][1] + r * math.sin(
                                    fi + offsetFi
                                )
                                z = passEndDepth
                                commandList.append(
                                    Path.Command(
                                        "G1",
                                        {"X": x, "Y": y, "Z": z, "F": self.horizFeed},
                                    )
                                )
                                # lx = x
                                # ly = y
                                fi = fi + math.pi / 16

                        else:
                            # Cone
                            _HelixAngle = 360.0 - (self.helixAngle * 4.0)

                            if self.helixConeAngle > 6:
                                self.helixConeAngle = 6

                            helixRadius *= 0.9

                            # Calculate everything
                            helix_height = passStartDepth - passEndDepth
                            r_extra = helix_height * math.tan(
                                math.radians(self.helixConeAngle)
                            )
                            HelixTopRadius = helixRadius + r_extra
                            helix_full_height = HelixTopRadius * (
                                math.cos(math.radians(self.helixConeAngle))
                                / math.sin(math.radians(self.helixConeAngle))
                            )

                            # Start height
                            z = passStartDepth
                            i = 0

                            # Default step down
                            z_step = 0.05

                            # Bigger angle, smaller step down
                            if _HelixAngle > 120:
                                z_step = 0.025
                            if _HelixAngle > 240:
                                z_step = 0.015

                            p = None
                            # Calculate conical helix
                            while z >= passEndDepth:
                                if z < passEndDepth:
                                    z = passEndDepth

                                p = self._calcHelixConePoint(
                                    helix_full_height, i, HelixTopRadius, _HelixAngle
                                )
                                commandList.append(
                                    Path.Command(
                                        "G1",
                                        {
                                            "X": p["X"] + region["HelixCenterPoint"][0],
                                            "Y": p["Y"] + region["HelixCenterPoint"][1],
                                            "Z": z,
                                            "F": self.vertFeed,
                                        },
                                    )
                                )
                                z = z - z_step
                                i = i + z_step

                            # Calculate some stuff for arcs at bottom
                            p["X"] = p["X"] + region["HelixCenterPoint"][0]
                            p["Y"] = p["Y"] + region["HelixCenterPoint"][1]
                            x_m = (
                                region["HelixCenterPoint"][0]
                                - p["X"]
                                + region["HelixCenterPoint"][0]
                            )
                            y_m = (
                                region["HelixCenterPoint"][1]
                                - p["Y"]
                                + region["HelixCenterPoint"][1]
                            )
                            i_off = (x_m - p["X"]) / 2
                            j_off = (y_m - p["Y"]) / 2

                            # One more circle at target depth to make sure center is cleared
                            commandList.append(
                                Path.Command(
                                    "G3",
                                    {
                                        "X": x_m,
                                        "Y": y_m,
                                        "Z": passEndDepth,
                                        "I": i_off,
                                        "J": j_off,
                                        "F": self.horizFeed,
                                    },
                                )
                            )
                            commandList.append(
                                Path.Command(
                                    "G3",
                                    {
                                        "X": p["X"],
                                        "Y": p["Y"],
                                        "Z": passEndDepth,
                                        "I": -i_off,
                                        "J": -j_off,
                                        "F": self.horizFeed,
                                    },
                                )
                            )

                    else:
                        # Use arcs for helix - no conical shape support
                        helixStart = [
                            region["HelixCenterPoint"][0] + r,
                            region["HelixCenterPoint"][1],
                        ]

                        # rapid move to start point
                        commandList.append(
                            Path.Command("G0", {"Z": self.clearanceHeight})
                        )
                        commandList.append(
                            Path.Command(
                                "G0",
                                {
                                    "X": helixStart[0],
                                    "Y": helixStart[1],
                                    "Z": self.clearanceHeight,
                                },
                            )
                        )

                        # rapid move to safe height
                        commandList.append(
                            Path.Command(
                                "G0",
                                {
                                    "X": helixStart[0],
                                    "Y": helixStart[1],
                                    "Z": self.safeHeight,
                                },
                            )
                        )

                        # move to start depth
                        commandList.append(
                            Path.Command(
                                "G1",
                                {
                                    "X": helixStart[0],
                                    "Y": helixStart[1],
                                    "Z": passStartDepth,
                                    "F": self.vertFeed,
                                },
                            )
                        )

                        x = region["HelixCenterPoint"][0] + r
                        y = region["HelixCenterPoint"][1]

                        curDep = passStartDepth
                        while curDep > (passEndDepth + depthPerOneCircle):
                            commandList.append(
                                Path.Command(
                                    "G2",
                                    {
                                        "X": x - (2 * r),
                                        "Y": y,
                                        "Z": curDep - (depthPerOneCircle / 2),
                                        "I": -r,
                                        "F": self.vertFeed,
                                    },
                                )
                            )
                            commandList.append(
                                Path.Command(
                                    "G2",
                                    {
                                        "X": x,
                                        "Y": y,
                                        "Z": curDep - depthPerOneCircle,
                                        "I": r,
                                        "F": self.vertFeed,
                                    },
                                )
                            )
                            curDep = curDep - depthPerOneCircle

                        lastStep = curDep - passEndDepth
                        if lastStep > (depthPerOneCircle / 2):
                            commandList.append(
                                Path.Command(
                                    "G2",
                                    {
                                        "X": x - (2 * r),
                                        "Y": y,
                                        "Z": curDep - (lastStep / 2),
                                        "I": -r,
                                        "F": self.vertFeed,
                                    },
                                )
                            )
                            commandList.append(
                                Path.Command(
                                    "G2",
                                    {
                                        "X": x,
                                        "Y": y,
                                        "Z": passEndDepth,
                                        "I": r,
                                        "F": self.vertFeed,
                                    },
                                )
                            )
                        else:
                            commandList.append(
                                Path.Command(
                                    "G2",
                                    {
                                        "X": x - (2 * r),
                                        "Y": y,
                                        "Z": passEndDepth,
                                        "I": -r,
                                        "F": self.vertFeed,
                                    },
                                )
                            )
                            commandList.append(
                                Path.Command(
                                    "G1",
                                    {
                                        "X": x,
                                        "Y": y,
                                        "Z": passEndDepth,
                                        "F": self.vertFeed,
                                    },
                                )
                            )

                        # one more circle at target depth to make sure center is cleared
                        commandList.append(
                            Path.Command(
                                "G2",
                                {
                                    "X": x - (2 * r),
                                    "Y": y,
                                    "Z": passEndDepth,
                                    "I": -r,
                                    "F": self.horizFeed,
                                },
                            )
                        )
                        commandList.append(
                            Path.Command(
                                "G2",
                                {
                                    "X": x,
                                    "Y": y,
                                    "Z": passEndDepth,
                                    "I": r,
                                    "F": self.horizFeed,
                                },
                            )
                        )
                        # lx = x
                        # ly = y

                else:  # no helix entry
                    # rapid move to clearance height
                    commandList.append(Path.Command("G0", {"Z": self.clearanceHeight}))
                    commandList.append(
                        Path.Command(
                            "G0",
                            {
                                "X": region["StartPoint"][0],
                                "Y": region["StartPoint"][1],
                                "Z": self.clearanceHeight,
                            },
                        )
                    )
                    # straight plunge to target depth
                    commandList.append(
                        Path.Command(
                            "G1",
                            {
                                "X": region["StartPoint"][0],
                                "Y": region["StartPoint"][1],
                                "Z": passEndDepth,
                                "F": self.vertFeed,
                            },
                        )
                    )

                lz = passEndDepth
                z = self.clearanceHeight
                commandList.append(
                    Path.Command("(Adaptive - depth: %f)" % passEndDepth)
                )

                # add adaptive paths
                for pth in region["AdaptivePaths"]:
                    motionType = pth[0]  # [0] contains motion type

                    for pt in pth[1]:  # [1] contains list of points
                        x = pt[0]
                        y = pt[1]

                        # dist = math.sqrt((x-lx)*(x-lx) + (y-ly)*(y-ly))

                        if motionType == motionCutting:
                            z = passEndDepth
                            if z != lz:
                                commandList.append(
                                    Path.Command("G1", {"Z": z, "F": self.vertFeed})
                                )  # plunge at feed rate

                            commandList.append(
                                Path.Command(
                                    "G1", {"X": x, "Y": y, "F": self.horizFeed}
                                )
                            )  # feed to point

                        elif motionType == motionLinkClear:
                            z = passEndDepth + stepUp
                            if z != lz:
                                commandList.append(
                                    Path.Command("G0", {"Z": z})
                                )  # rapid to previous pass depth

                            commandList.append(
                                Path.Command("G0", {"X": x, "Y": y})
                            )  # rapid to point

                        elif motionType == motionLinkNotClear:
                            z = self.clearanceHeight
                            if z != lz:
                                commandList.append(
                                    Path.Command("G0", {"Z": z})
                                )  # rapid to clearance height

                            commandList.append(
                                Path.Command("G0", {"X": x, "Y": y})
                            )  # rapid to point

                        # elif motionType == area.AdaptiveMotionType.LinkClearAtPrevPass:
                        #     if lx!=x or ly!=y:
                        #         commandList.append(Path.Command("G0", { "X": lx, "Y":ly, "Z":passStartDepth+stepUp}))
                        #     commandList.append(Path.Command("G0", { "X": x, "Y":y, "Z":passStartDepth+stepUp}))

                        # rotate values: current values become last for next loop
                        # lx = x
                        # ly = y
                        lz = z

                # return to clearance height in this Z pass
                z = self.clearanceHeight
                if z != lz:
                    commandList.append(Path.Command("G0", {"Z": z}))

                lz = z
            # Efor

            passStartDepth = passEndDepth

            # return to safe height in this Z pass
            z = self.clearanceHeight
            if z != lz:
                commandList.append(Path.Command("G0", {"Z": z}))

            lz = z
        # Efor

        z = self.clearanceHeight
        if z != lz:
            commandList.append(Path.Command("G0", {"Z": z}))

        lz = z

        # Save commands
        # PathLog.info(f"Adaptive cmd count: {len(commandList)}")
        self.commandList = commandList

    # Public methods
    def disableHelixEntry(self):
        self.useHelixEntry = False
        self.helixDiameterLimit = 0.01
        self.helixAngle = 89.0

    def execute(self):
        PathLog.debug("StrategyAdaptive.execute()")

        # PathLog.info("*** Adaptive toolpath processing started...")
        # startTime = time.time()
        if not FreeCAD.GuiUp:
            self.guiPreviewPaths = False

        for shp in self.faces:
            shp.translate(FreeCAD.Vector(0.0, 0.0, self.finalDepth - shp.BoundBox.ZMin))
            for w in shp.Wires:
                for e in w.Edges:
                    self.pathArray.append([self._discretize(e)])

        path2d = self._convertTo2d(self.pathArray)

        if self.guiPreviewPaths:
            self.sceneGraph = FreeCADGui.ActiveDocument.ActiveView.getSceneGraph()

        # hide old toolpaths during recalculation
        # self.obj.Path = Path.Path("(Calculating...)")  # self.obj.Path should change to self.Path

        if self.guiPreviewPaths:
            # store old visibility state
            # oldObjVisibility = self.viewObject.Visibility
            # oldJobVisibility = self.job.ViewObject.Visibility

            # self.viewObject.Visibility = False
            # self.job.ViewObject.Visibility = False

            FreeCADGui.updateGui()
        self.topZ = self.stockShape.BoundBox.ZMax
        self.stopped = False
        self.stopProcessing = False

        stockPaths = []
        if self.stockType == "CreateCylinder":
            stockPaths.append([self._discretize(self.stockShape.Edges[0])])
            PathLog.info("Adaptive stock type is cylinder")
        else:
            stockBB = self.stockShape.BoundBox
            v = []
            v.append(FreeCAD.Vector(stockBB.XMin, stockBB.YMin, 0))
            v.append(FreeCAD.Vector(stockBB.XMax, stockBB.YMin, 0))
            v.append(FreeCAD.Vector(stockBB.XMax, stockBB.YMax, 0))
            v.append(FreeCAD.Vector(stockBB.XMin, stockBB.YMax, 0))
            v.append(FreeCAD.Vector(stockBB.XMin, stockBB.YMin, 0))
            stockPaths.append([v])

        stockPath2d = self._convertTo2d(stockPaths)
        # Part.show(self.stockShape, "StockShape")

        opType = area.AdaptiveOperationType.ClearingInside
        if self.operationType == "Clearing":
            if self.cutSide == "Outside":
                opType = area.AdaptiveOperationType.ClearingOutside

            else:
                opType = area.AdaptiveOperationType.ClearingInside

        else:  # profiling
            if self.cutSide == "Outside":
                opType = area.AdaptiveOperationType.ProfilingOutside

            else:
                opType = area.AdaptiveOperationType.ProfilingInside

        # put here all properties that influence calculation of adaptive base paths,
        inputStateObject = {
            "tool": self.toolDiameter,
            "tolerance": self.tolerance,
            "geometry": path2d,
            "stockGeometry": stockPath2d,
            "stepover": self.stepOver,
            "effectiveHelixDiameter": self.helixDiameterLimit,
            "operationType": self.operationType,
            "side": self.cutSide,
            "forceInsideOut": self.forceInsideOut,
            "finishingProfile": self.finishingProfile,
            "keepToolDownRatio": self.keepToolDownRatio,
            "stockToLeave": self.materialAllowance,
        }

        inputStateChanged = False
        adaptiveResults = None

        if self.adaptiveOutputState is not None and self.adaptiveOutputState != "":
            adaptiveResults = self.adaptiveOutputState

        if json.dumps(self.adaptiveInputState) != json.dumps(inputStateObject):
            inputStateChanged = True
            adaptiveResults = None

        # progress callback fn, if return true it will stop processing
        def progressFn(tpaths):
            motionCutting = area.AdaptiveMotionType.Cutting
            if self.guiPreviewPaths:
                for (
                    path
                ) in (
                    tpaths
                ):  # path[0] contains the MotionType, #path[1] contains list of points
                    if path[0] == motionCutting:
                        self._sceneDrawPath(path[1], (0, 0, 1))

                    else:
                        self._sceneDrawPath(path[1], (1, 0, 1))

                FreeCADGui.updateGui()

            return self.stopProcessing

        if inputStateChanged or adaptiveResults is None:
            a2d = area.Adaptive2d()
            a2d.stepOverFactor = 0.01 * self.stepOver
            a2d.toolDiameter = self.toolDiameter
            a2d.helixRampDiameter = self.helixDiameterLimit
            a2d.keepToolDownDistRatio = self.keepToolDownRatio
            a2d.stockToLeave = self.materialAllowance
            a2d.tolerance = self.tolerance
            a2d.forceInsideOut = self.forceInsideOut
            a2d.finishingProfile = self.finishingProfile
            a2d.opType = opType

        try:
            # EXECUTE
            results = a2d.Execute(stockPath2d, path2d, progressFn)

            # need to convert results to python object to be JSON serializable
            adaptiveResults = []
            for result in results:
                PathLog.info(f"CP: {result.HelixCenterPoint};  SP: {result.StartPoint}")
                adaptiveResults.append(
                    {
                        "HelixCenterPoint": result.HelixCenterPoint,
                        "StartPoint": result.StartPoint,
                        "AdaptivePaths": result.AdaptivePaths,
                        "ReturnMotionType": result.ReturnMotionType,
                    }
                )

            # Generate G-Code
            if self.generateCommands:
                self._generateGCode(adaptiveResults)

            if not self.stopProcessing:
                # PathLog.info("*** Done. Elapsed time: %f sec" % (time.time()-startTime))
                self.adaptiveOutputState = adaptiveResults
                self.adaptiveInputState = inputStateObject

            else:
                # PathLog.info("*** Processing cancelled (after: %f sec)." % (time.time()-startTime))
                pass

        finally:
            if self.guiPreviewPaths:
                # self.viewObject.Visibility = oldObjVisibility
                # self.job.ViewObject.Visibility = oldJobVisibility
                self._sceneClean()

        return True

    # Functions for managing properties and their default values
    @classmethod
    def adaptivePropertyDefinitions(cls):
        """adaptivePropertyDefinitions() ... returns a list of tuples.
        Each tuple contains property declaration information in the
        form of (prototype, name, section, tooltip)."""
        return [
            (
                "App::PropertyEnumeration",
                "CutSide",
                "Adaptive",
                "Side of selected faces that tool should cut",
            ),
            (
                "App::PropertyEnumeration",
                "OperationType",
                "Adaptive",
                "Type of adaptive operation",
            ),
            (
                "App::PropertyFloat",
                "Tolerance",
                "Adaptive",
                "Influences accuracy and performance",
            ),
            (
                "App::PropertyDistance",
                "LiftDistance",
                "Adaptive",
                "Lift distance for rapid moves",
            ),
            (
                "App::PropertyDistance",
                "KeepToolDownRatio",
                "Adaptive",
                "Max length of keep tool down path compared to direct distance between points",
            ),
            (
                "App::PropertyBool",
                "ForceInsideOut",
                "Adaptive",
                "Force plunging into material inside and clearing towards the edges",
            ),
            (
                "App::PropertyBool",
                "FinishingProfile",
                "Adaptive",
                "To take a finishing profile path at the end",
            ),
            ("App::PropertyBool", "Stopped", "Adaptive", "Stop processing"),
            ("App::PropertyBool", "StopProcessing", "Adaptive", "Stop processing"),
            (
                "App::PropertyBool",
                "UseHelixArcs",
                "Adaptive",
                "Use Arcs (G2) for helix ramp",
            ),
            (
                "App::PropertyPythonObject",
                "AdaptiveInputState",
                "Adaptive",
                "Internal input state",
            ),
            (
                "App::PropertyPythonObject",
                "AdaptiveOutputState",
                "Adaptive",
                "Internal output state",
            ),
            (
                "App::PropertyAngle",
                "HelixAngle",
                "Adaptive",
                "Helix ramp entry angle (degrees)",
            ),
            (
                "App::PropertyAngle",
                "HelixConeAngle",
                "Adaptive",
                "Helix cone angle (degrees)",
            ),
            (
                "App::PropertyLength",
                "HelixDiameterLimit",
                "Adaptive",
                "Limit helix entry diameter, if limit larger than tool diameter or 0, tool diameter is used",
            ),
            (
                "App::PropertyBool",
                "DisableHelixEntry",
                "Adaptive",
                "Disable the helix entry, and use simple plunge.",
            ),
        ]

    @classmethod
    def adaptivePropertyDefaults(cls, obj, job):
        """adaptivePropertyDefaults(obj, job) ... returns a dictionary of default values
        for the strategy's properties."""
        return {
            "CutSide": "Inside",
            "OperationType": "Clearing",
            "Tolerance": 0.1,
            "LiftDistance": 0,
            "ForceInsideOut": False,
            "FinishingProfile": True,
            "Stopped": False,
            "StopProcessing": False,
            "HelixAngle": 5,
            "HelixConeAngle": 0,
            "HelixDiameterLimit": 0.0,
            "AdaptiveInputState": "",
            "AdaptiveOutputState": "",
            "KeepToolDownRatio": 3.0,
            "UseHelixArcs": False,
            "DisableHelixEntry": False,
        }

    @classmethod
    def propEnumerations(cls, dataType="data"):
        """adaptivePropertyEnumerations() ... returns a dictionary of enumeration lists
        for the operation's enumeration type properties."""
        # Enumeration lists for App::PropertyEnumeration properties
        enums = {
            "OperationType": [
                (translate("Path", "Clearing"), "Clearing"),
                (translate("Path", "Profile"), "Profile"),
            ],
            "CutSide": [
                (translate("Path", "Outside"), "Outside"),
                (translate("Path", "Inside"), "Inside"),
            ],
        }

        if dataType == "raw":
            return enums

        data = []
        idx = 0 if dataType == "translated" else 1

        Path.Log.debug(enums)

        for k, v in enumerate(enums):
            data.append((v, [tup[idx] for tup in enums[v]]))
        Path.Log.debug(data)

        return data

    @classmethod
    def adaptiveSetEditorModes(cls, obj, hide=False):
        """adaptiveSetEditorModes(obj) ... Set property editor modes."""
        # Always hide these properties
        obj.setEditorMode("Stopped", 2)
        obj.setEditorMode("StopProcessing", 2)
        obj.setEditorMode("AdaptiveInputState", 2)
        obj.setEditorMode("AdaptiveOutputState", 2)

        mode = 0
        if hide:
            mode = 2
        obj.setEditorMode("CutSide", mode)
        obj.setEditorMode("OperationType", mode)
        obj.setEditorMode("Tolerance", mode)
        obj.setEditorMode("LiftDistance", mode)
        obj.setEditorMode("KeepToolDownRatio", mode)
        obj.setEditorMode("ForceInsideOut", mode)
        obj.setEditorMode("FinishingProfile", mode)
        obj.setEditorMode("UseHelixArcs", mode)
        obj.setEditorMode("HelixAngle", mode)
        obj.setEditorMode("HelixConeAngle", mode)
        obj.setEditorMode("HelixDiameterLimit", mode)
        obj.setEditorMode("DisableHelixEntry", mode)


# Eclass
