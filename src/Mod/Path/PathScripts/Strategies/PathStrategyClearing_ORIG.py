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
import PathScripts.PathLog as PathLog
import PathScripts.PathUtils as PathUtils

from PySide import QtCore

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader
Part = LazyLoader('Part', globals(), 'Part')
DraftGeomUtils = LazyLoader('DraftGeomUtils', globals(), 'DraftGeomUtils')
PathGeom = LazyLoader('PathScripts.PathGeom', globals(), 'PathScripts.PathGeom')
PathOpTools = LazyLoader('PathScripts.PathOpTools', globals(), 'PathScripts.PathOpTools')
time = LazyLoader('time', globals(), 'time')
json = LazyLoader('json', globals(), 'json')
math = LazyLoader('math', globals(), 'math')
area = LazyLoader('area', globals(), 'area')

if FreeCAD.GuiUp:
    coin = LazyLoader('pivy.coin', globals(), 'pivy.coin')
    FreeCADGui = LazyLoader('FreeCADGui', globals(), 'FreeCADGui')


__title__ = "Path Strategies"
__author__ = "Yorik van Havre; sliptonic (Brad Collette)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Path strategies available for path generation."
__contributors__ = ""


PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)

# Depreciated clearing strategy class
class StrategyPocket:
    '''class StrategyPocket'''

    def __init__(self,
            shape,
            startPoint,
            getsim,
            depthparams,
            horizFeed,
            vertFeed,
            endVector,
            radius,
            opFeatures,
            safeHeight,
            clearanceHeight,
            stockAllowance,
            direction,
            opUseProjection,
            opRetractTool,
            pocketInvertExtraOffset,
            cutPattern,
            cutPatternAngle,
            stepOver,
            startAt,
            useMinTravel):
        PathLog.debug("StrategyPocket.__init__()")

        self.opUseProjection = opUseProjection
        self.opRetractTool = opRetractTool
        self.shape = shape
        self.startPoint = startPoint
        self.getsim = getsim
        self.resume_height = safeHeight  # obj.SafeHeight.Value
        self.retraction = clearanceHeight  # obj.ClearanceHeight.Value
        self.depthparams = depthparams
        self.horizFeed = horizFeed
        self.vertFeed = vertFeed
        self.endVector = endVector
        self.radius = radius
        self.opFeatures = opFeatures
        self.stockAllowance = stockAllowance
        self.direction = direction
        self.pocketInvertExtraOffset = pocketInvertExtraOffset
        self.cutPattern = cutPattern
        self.cutPatternAngle = cutPatternAngle
        self.stepOver = stepOver
        self.startAt = startAt
        self.useMinTravel = useMinTravel

        self.simObj = None
        self.pathParams = ""
        self.areaParams = ""
        self.commandList = list()

    # Private methods
    def _getAreaParams(self):
        '''_getAreaParams() ... returns dictionary with area parameters.'''
        params = {}
        params['Fill'] = 0
        params['Coplanar'] = 0
        params['PocketMode'] = 1
        params['SectionCount'] = -1
        params['Angle'] = self.cutPatternAngle
        params['FromCenter'] = (self.startAt == "Center")
        params['PocketStepover'] = (self.radius * 2) * (float(self.stepOver)/100)
        extraOffset = self.stockAllowance
        if self.pocketInvertExtraOffset:
            extraOffset = 0 - extraOffset
        params['PocketExtraOffset'] = extraOffset
        params['ToolRadius'] = self.radius

        Pattern = ['ZigZag', 'Offset', 'Spiral', 'ZigZagOffset', 'Line', 'Grid', 'Triangle']
        params['PocketMode'] = Pattern.index(self.cutPattern) + 1

        return params

    def _getPathParams(self):
        '''_getPathParams() ... returns dictionary with path parameters.'''
        params = {}

        orientation = ['Conventional', 'Climb']
        params['orientation'] = orientation.index(self.direction)

        # if MinTravel is turned on, set path sorting to 3DSort
        # 3DSort shouldn't be used without a valid start point. Can cause
        # tool crash without it.
        #
        # ml: experimental feature, turning off for now (see https://forum.freecadweb.org/viewtopic.php?f=15&t=24422&start=30#p192458)
        # realthunder: I've fixed it with a new sorting algorithm, which I
        # tested fine, but of course need more test. Please let know if there is
        # any problem
        #
        if self.useMinTravel and self.startPoint:
            params['sort_mode'] = 3
            params['threshold'] = self.radius * 2

        return params

    # Public methods
    def execute(self):
        '''execute() ... public function to generate gcode for path area shape.'''
        PathLog.debug("execute()")
        PathLog.track()

        area = Path.Area()
        area.setPlane(PathUtils.makeWorkplane(self.shape))
        area.add(self.shape)

        areaParams = self._getAreaParams() # pylint: disable=assignment-from-no-return

        heights = [i for i in self.depthparams]
        PathLog.debug('depths: {}'.format(heights))
        area.setParams(**areaParams)
        self.areaParams = str(area.getParams())

        PathLog.debug("Area with params: {}".format(area.getParams()))

        sections = area.makeSections(mode=0, project=self.opUseProjection, heights=heights)
        PathLog.debug("sections = %s" % sections)
        shapelist = [sec.getShape() for sec in sections]
        PathLog.debug("shapelist = %s" % shapelist)

        pathParams = self._getPathParams() # pylint: disable=assignment-from-no-return
        pathParams['shapes'] = shapelist
        pathParams['feedrate'] = self.horizFeed
        pathParams['feedrate_v'] = self.vertFeed
        pathParams['verbose'] = True
        pathParams['resume_height'] = self.resume_height
        pathParams['retraction'] = self.retraction
        pathParams['return_end'] = True
        # Note that emitting preambles between moves breaks some dressups and prevents path optimization on some controllers
        pathParams['preamble'] = False

        if not self.opRetractTool:
            pathParams['threshold'] = 2.001 * self.radius

        if self.endVector is not None:
            pathParams['start'] = self.endVector
        elif self.startPoint is not None:
            pathParams['start'] = self.startPoint

        self.pathParams = str({key: value for key, value in pathParams.items() if key != 'shapes'})
        PathLog.debug("Path with params: {}".format(self.pathParams))

        (pp, end_vector) = Path.fromShapes(**pathParams)
        PathLog.debug('pp: {}, end vector: {}'.format(pp, end_vector))
        self.endVector = end_vector # pylint: disable=attribute-defined-outside-init

        if self.getsim:
            areaParams['Thicken'] = True
            areaParams['ToolRadius'] = self.radius - self.radius * .005
            area.setParams(**areaParams)
            sec = area.makeSections(mode=0, project=False, heights=heights)[-1].getShape()
            self.simObj = sec.extrude(FreeCAD.Vector(0, 0, self.shape.BoundBox.ZMax))

        self.commandList = pp.Commands
        return True

    def getSimObj(self):
        return self.simObj
# Eclass


class StrategyAdaptive:
    """class StrategyAdaptive
    Class and implementation of the Adaptive path generation."
    """

    sceneGraph = None
    scenePathNodes = []  # for scene cleanup aftewards
    topZ = 10

    def __init__(self,
                 faces,
                 toolController,
                 clearanceHeight,
                 safeHeight,
                 startDepth,
                 finishDepth,
                 finalDepth,
                 operationType,
                 cutSide,
                 forceInsideOut,
                 materialAllowance,
                 stepDown,
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
                 stock,
                 job,
                 adaptiveOutputState,
                 adaptiveInputState,
                 viewObject):
        PathLog.debug("StrategyAdaptive.__init__()")

        self.useHelixEntry = True  # Set False to disable helix entry
        self.adaptiveGeometry = list()
        self.generateCommands = True
        self.generateGeometry = False

        # Apply limits to argument values
        if tolerance < 0.001:
            tolerance = 0.001

        if helixAngle < 1.0:
            helixAngle = 1.0
        if helixAngle > 89.0:
            helixAngle = 89.0

        if stepDown < 0.1:
            stepDown = 0.1

        if helixConeAngle < 0.0:
            helixConeAngle = 0.0

        self.faces = faces
        self.clearanceHeight = clearanceHeight
        self.safeHeight = safeHeight
        self.startDepth = startDepth
        self.finishDepth = finishDepth
        self.finalDepth = finalDepth
        self.operationType = operationType
        self.cutSide = cutSide
        self.forceInsideOut = forceInsideOut
        self.materialAllowance = materialAllowance
        self.stock = stock
        self.job = job
        self.stepDown = stepDown
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

        self.vertFeed = toolController.VertFeed.Value
        self.horizFeed = toolController.HorizFeed.Value
        self.toolDiameter = toolController.Tool.Diameter.Value
        # self.toolRadius = self.toolDiam / 2.0

        self.stockShape = stock.Shape
        self.pathArray = list()
        self.commandList = list()

        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False

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
        x = ((height - cur_z) / height) * radius * math.cos(math.radians(angle)*cur_z)
        y = ((height - cur_z) / height) * radius * math.sin(math.radians(angle)*cur_z)
        z = cur_z

        return {'X': x, 'Y': y, 'Z': z}

    def _generateGCode(self, adaptiveResults):
        self.commandList = list()
        commandList = list()
        motionCutting = area.AdaptiveMotionType.Cutting
        motionLinkClear = area.AdaptiveMotionType.LinkClear
        motionLinkNotClear = area.AdaptiveMotionType.LinkNotClear

        # pylint: disable=unused-argument
        if len(adaptiveResults) == 0 or len(adaptiveResults[0]["AdaptivePaths"]) == 0:
            return

        helixRadius = 0
        for region in adaptiveResults:
            p1 = region["HelixCenterPoint"]
            p2 = region["StartPoint"]
            r = math.sqrt((p1[0]-p2[0]) * (p1[0]-p2[0]) + (p1[1] - p2[1]) * (p1[1] - p2[1]))
            if r > helixRadius:
                helixRadius = r

        passStartDepth = self.startDepth

        length = 2*math.pi * helixRadius

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
                user_depths=None)

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
                startAngle = math.atan2(region["StartPoint"][1] - region["HelixCenterPoint"][1], region["StartPoint"][0] - region["HelixCenterPoint"][0])

                # lx = region["HelixCenterPoint"][0]
                # ly = region["HelixCenterPoint"][1]

                passDepth = (passStartDepth - passEndDepth)

                p1 = region["HelixCenterPoint"]
                p2 = region["StartPoint"]
                helixRadius = math.sqrt((p1[0]-p2[0]) * (p1[0]-p2[0]) + (p1[1]-p2[1]) * (p1[1]-p2[1]))

                # Helix ramp
                if self.useHelixEntry and helixRadius > 0.01:
                    r = helixRadius - 0.01

                    maxfi = passDepth / depthPerOneCircle * 2 * math.pi
                    fi = 0
                    offsetFi = -maxfi + startAngle-math.pi/16

                    helixStart = [region["HelixCenterPoint"][0] + r * math.cos(offsetFi), region["HelixCenterPoint"][1] + r * math.sin(offsetFi)]

                    commandList.append(Path.Command("(Helix to depth: %f)" % passEndDepth))

                    if not self.useHelixArcs:
                        # rapid move to start point
                        commandList.append(Path.Command("G0", {"Z": self.clearanceHeight}))
                        commandList.append(Path.Command("G0", {"X": helixStart[0], "Y": helixStart[1], "Z": self.clearanceHeight}))

                        # rapid move to safe height
                        commandList.append(Path.Command("G0", {"X": helixStart[0], "Y": helixStart[1], "Z": self.safeHeight}))

                        # move to start depth
                        commandList.append(Path.Command("G1", {"X": helixStart[0], "Y": helixStart[1], "Z": passStartDepth, "F": self.vertFeed}))

                        if self.helixConeAngle == 0:
                            while fi < maxfi:
                                x = region["HelixCenterPoint"][0] + r * math.cos(fi+offsetFi)
                                y = region["HelixCenterPoint"][1] + r * math.sin(fi+offsetFi)
                                z = passStartDepth - fi / maxfi * (passStartDepth - passEndDepth)
                                commandList.append(Path.Command("G1", {"X": x, "Y": y, "Z": z, "F": self.vertFeed}))
                                # lx = x
                                # ly = y
                                fi = fi + math.pi / 16

                            # one more circle at target depth to make sure center is cleared
                            maxfi = maxfi + 2*math.pi
                            while fi < maxfi:
                                x = region["HelixCenterPoint"][0] + r * math.cos(fi+offsetFi)
                                y = region["HelixCenterPoint"][1] + r * math.sin(fi+offsetFi)
                                z = passEndDepth
                                commandList.append(Path.Command("G1", {"X": x, "Y": y, "Z": z, "F": self.horizFeed}))
                                # lx = x
                                # ly = y
                                fi = fi + math.pi/16

                        else:
                            # Cone
                            _HelixAngle = 360.0 - (self.helixAngle * 4.0)

                            if self.helixConeAngle > 6:
                                self.helixConeAngle = 6

                            helixRadius *= 0.9

                            # Calculate everything
                            helix_height = passStartDepth - passEndDepth
                            r_extra = helix_height * math.tan(math.radians(self.helixConeAngle))
                            HelixTopRadius = helixRadius + r_extra
                            helix_full_height = HelixTopRadius * (math.cos(math.radians(self.helixConeAngle)) / math.sin(math.radians(self.helixConeAngle)))

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
                            while(z >= passEndDepth):
                                if z < passEndDepth:
                                    z = passEndDepth

                                p = self._calcHelixConePoint(helix_full_height, i, HelixTopRadius, _HelixAngle)
                                commandList.append(Path.Command("G1", {"X": p['X'] + region["HelixCenterPoint"][0], "Y": p['Y'] + region["HelixCenterPoint"][1], "Z": z, "F": self.vertFeed}))
                                z = z - z_step
                                i = i + z_step

                            # Calculate some stuff for arcs at bottom
                            p['X'] = p['X'] + region["HelixCenterPoint"][0]
                            p['Y'] = p['Y'] + region["HelixCenterPoint"][1]
                            x_m = region["HelixCenterPoint"][0] - p['X'] + region["HelixCenterPoint"][0]
                            y_m = region["HelixCenterPoint"][1] - p['Y'] + region["HelixCenterPoint"][1]
                            i_off = (x_m - p['X']) / 2
                            j_off = (y_m - p['Y']) / 2

                            # One more circle at target depth to make sure center is cleared
                            commandList.append(Path.Command("G3", {"X": x_m, "Y": y_m, "Z": passEndDepth, "I": i_off, "J": j_off, "F": self.horizFeed}))
                            commandList.append(Path.Command("G3", {"X": p['X'], "Y": p['Y'], "Z": passEndDepth, "I": -i_off, "J": -j_off, "F": self.horizFeed}))

                    else:
                        # Use arcs for helix - no conical shape support
                        helixStart = [region["HelixCenterPoint"][0] + r, region["HelixCenterPoint"][1]]

                        # rapid move to start point
                        commandList.append(Path.Command("G0", {"Z": self.clearanceHeight}))
                        commandList.append(Path.Command("G0", {"X": helixStart[0], "Y": helixStart[1], "Z": self.clearanceHeight}))

                        # rapid move to safe height
                        commandList.append(Path.Command("G0", {"X": helixStart[0], "Y": helixStart[1], "Z": self.safeHeight}))

                        # move to start depth
                        commandList.append(Path.Command("G1", {"X": helixStart[0], "Y": helixStart[1], "Z": passStartDepth, "F": self.vertFeed}))

                        x = region["HelixCenterPoint"][0] + r
                        y = region["HelixCenterPoint"][1]

                        curDep = passStartDepth
                        while curDep > (passEndDepth + depthPerOneCircle):
                            commandList.append(Path.Command("G2", {"X": x - (2*r), "Y": y, "Z": curDep - (depthPerOneCircle/2), "I": -r, "F": self.vertFeed}))
                            commandList.append(Path.Command("G2", {"X": x, "Y": y, "Z": curDep - depthPerOneCircle, "I": r, "F": self.vertFeed}))
                            curDep = curDep - depthPerOneCircle

                        lastStep = curDep - passEndDepth
                        if lastStep > (depthPerOneCircle/2):
                            commandList.append(Path.Command("G2", {"X": x - (2*r), "Y": y, "Z": curDep - (lastStep/2), "I": -r, "F": self.vertFeed}))
                            commandList.append(Path.Command("G2", {"X": x, "Y": y, "Z": passEndDepth, "I": r, "F": self.vertFeed}))
                        else:
                            commandList.append(Path.Command("G2", {"X": x - (2*r), "Y": y, "Z": passEndDepth, "I": -r, "F": self.vertFeed}))
                            commandList.append(Path.Command("G1", {"X": x, "Y": y, "Z": passEndDepth, "F": self.vertFeed}))

                        # one more circle at target depth to make sure center is cleared
                        commandList.append(Path.Command("G2", {"X": x - (2*r), "Y": y, "Z": passEndDepth, "I": -r, "F": self.horizFeed}))
                        commandList.append(Path.Command("G2", {"X": x, "Y": y, "Z": passEndDepth, "I": r, "F": self.horizFeed}))
                        # lx = x
                        # ly = y

                else:  # no helix entry
                    # rapid move to clearance height
                    commandList.append(Path.Command("G0", {"Z": self.clearanceHeight}))
                    commandList.append(Path.Command("G0", {"X": region["StartPoint"][0], "Y": region["StartPoint"][1], "Z": self.clearanceHeight}))
                    # straight plunge to target depth
                    commandList.append(Path.Command("G1", {"X": region["StartPoint"][0], "Y": region["StartPoint"][1], "Z": passEndDepth, "F": self.vertFeed}))

                lz = passEndDepth
                z = self.clearanceHeight
                commandList.append(Path.Command("(Adaptive - depth: %f)" % passEndDepth))

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
                                commandList.append(Path.Command("G1", {"Z": z, "F": self.vertFeed}))  # plunge at feed rate

                            commandList.append(Path.Command("G1", {"X": x, "Y": y, "F": self.horizFeed}))  # feed to point

                        elif motionType == motionLinkClear:
                            z = passEndDepth + stepUp
                            if z != lz:
                                commandList.append(Path.Command("G0", {"Z": z}))  # rapid to previous pass depth

                            commandList.append(Path.Command("G0", {"X": x, "Y": y}))  # rapid to point

                        elif motionType == motionLinkNotClear:
                            z = self.clearanceHeight
                            if z != lz:
                                commandList.append(Path.Command("G0", {"Z": z}))  # rapid to clearance height

                            commandList.append(Path.Command("G0", {"X": x, "Y": y}))  # rapid to point

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

            passStartDepth = passEndDepth

            # return to safe height in this Z pass
            z = self.clearanceHeight
            if z != lz:
                commandList.append(Path.Command("G0", {"Z": z}))

            lz = z

        z = self.clearanceHeight
        if z != lz:
            commandList.append(Path.Command("G0", {"Z": z}))

        lz = z

        # Save commands
        self.commandList = commandList

    def _generateGeometry(self, adaptiveResults):
        wires = list()
        motionCutting = area.AdaptiveMotionType.Cutting
        for region in adaptiveResults:
            for pth in region["AdaptivePaths"]:
                motion = pth[0]  # [0] contains motion type
                if motion == motionCutting:
                    edges = list()
                    sp = pth[1][0]
                    start = FreeCAD.Vector(sp[0], sp[1], 0.0)
                    for pt in pth[1][1:]:  # [1] contains list of points
                        end = FreeCAD.Vector(pt[0], pt[1], 0.0)
                        if not PathGeom.isRoughly(start.sub(end).Length, 0.0):
                            edges.append(Part.makeLine(start, end))
                            start = end
                    wires.append(Part.Wire(Part.__sortEdges__(edges)))
        self.adaptiveGeometry = wires

    # Public methods
    def disableHelixEntry(self):
        self.useHelixEntry = False
        self.helixDiameterLimit = 0.01
        self.helixAngle = 89.0

    def execute(self):
        PathLog.debug("StrategyAdaptive.execute()")

        for shp in self.faces:
            shp.translate(FreeCAD.Vector(0.0, 0.0, self.finalDepth - shp.BoundBox.ZMin))
            for w in shp.Wires:
                for e in w.Edges:
                    self.pathArray.append([self._discretize(e)])

        if FreeCAD.GuiUp:
            self.sceneGraph = FreeCADGui.ActiveDocument.ActiveView.getSceneGraph()

        PathLog.info("*** Adaptive toolpath processing started...")
        start = time.time()

        # hide old toolpaths during recalculation
        # self.obj.Path = Path.Path("(Calculating...)")  # self.obj.Path should change to self.Path

        if FreeCAD.GuiUp:
            #store old visibility state
            oldObjVisibility = self.viewObject.Visibility
            oldJobVisibility = self.job.ViewObject.Visibility

            self.viewObject.Visibility = False
            self.job.ViewObject.Visibility = False

            FreeCADGui.updateGui()

        try:
            self.topZ = self.stockShape.BoundBox.ZMax
            self.stopped = False
            self.stopProcessing = False

            path2d = self._convertTo2d(self.pathArray)

            stockPaths = []
            if hasattr(self.stock, "StockType") and self.stock.StockType == "CreateCylinder":
                stockPaths.append([self._discretize(self.stockShape.Edges[0])])

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
                "stockToLeave": self.materialAllowance
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
                if FreeCAD.GuiUp:
                    for path in tpaths: #path[0] contains the MotionType, #path[1] contains list of points
                        if path[0] == motionCutting:
                            self._sceneDrawPath(path[1],(0,0,1))

                        else:
                            self._sceneDrawPath(path[1],(1,0,1))

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

                # EXECUTE
                results = a2d.Execute(stockPath2d, path2d, progressFn)

                # need to convert results to python object to be JSON serializable
                adaptiveResults = []
                for result in results:
                    adaptiveResults.append({
                        "HelixCenterPoint": result.HelixCenterPoint,
                        "StartPoint": result.StartPoint,
                        "AdaptivePaths": result.AdaptivePaths,
                        "ReturnMotionType": result.ReturnMotionType})

            # GENERATE
            if self.generateCommands:
                self._generateGCode(adaptiveResults)

            # Generate geometry
            if self.generateGeometry:
                self._generateGeometry(adaptiveResults)

            if not self.stopProcessing:
                PathLog.info("*** Done. Elapsed time: %f sec\n\n" % (time.time()-start))
                self.adaptiveOutputState = adaptiveResults
                self.adaptiveInputState = inputStateObject

            else:
                PathLog.info("*** Processing cancelled (after: %f sec).\n\n" % (time.time()-start))

        finally:
            if FreeCAD.GuiUp:
                self.viewObject.Visibility = oldObjVisibility
                self.job.ViewObject.Visibility = oldJobVisibility
                self._sceneClean()
        
        return True

    # Functions for managing properties and their default values
    @classmethod
    def adaptivePropertyDefinitions(cls):
        '''adaptivePropertyDefinitions() ... returns a list of tuples.
        Each tuple contains property declaration information in the
        form of (prototype, name, section, tooltip).'''
        return [
            ("App::PropertyEnumeration", "CutSide", "Adaptive", "Side of selected faces that tool should cut"),
            ("App::PropertyEnumeration", "OperationType", "Adaptive", "Type of adaptive operation"),
            ("App::PropertyFloat", "Tolerance", "Adaptive", "Influences accuracy and performance"),
            ("App::PropertyDistance", "LiftDistance", "Adaptive", "Lift distance for rapid moves"),
            ("App::PropertyDistance", "KeepToolDownRatio", "Adaptive", "Max length of keep tool down path compared to direct distance between points"),
            ("App::PropertyBool", "ForceInsideOut", "Adaptive", "Force plunging into material inside and clearing towards the edges"),
            ("App::PropertyBool", "FinishingProfile", "Adaptive", "To take a finishing profile path at the end"),
            ("App::PropertyBool", "Stopped", "Adaptive", "Stop processing"),
            ("App::PropertyBool", "StopProcessing", "Adaptive", "Stop processing"),
            ("App::PropertyBool", "UseHelixArcs", "Adaptive", "Use Arcs (G2) for helix ramp"),
            ("App::PropertyPythonObject", "AdaptiveInputState", "Adaptive", "Internal input state"),
            ("App::PropertyPythonObject", "AdaptiveOutputState", "Adaptive", "Internal output state"),
            ("App::PropertyAngle", "HelixAngle", "Adaptive", "Helix ramp entry angle (degrees)"),
            ("App::PropertyAngle", "HelixConeAngle", "Adaptive", "Helix cone angle (degrees)"),
            ("App::PropertyLength", "HelixDiameterLimit", "Adaptive", "Limit helix entry diameter, if limit larger than tool diameter or 0, tool diameter is used"),
            ("App::PropertyBool", "DisableHelixEntry", "Adaptive", "Disable the helix entry, and use simple plunge.")
        ]

    @classmethod
    def adaptivePropertyDefaults(cls, obj, job):
        '''adaptivePropertyDefaults(obj, job) ... returns a dictionary of default values
        for the strategy's properties.'''
        return {
            'CutSide': "Inside",
            'OperationType': "Clearing",
            'Tolerance': 0.1,
            'LiftDistance': 0,
            'ForceInsideOut': False,
            'FinishingProfile': True,
            'Stopped': False,
            'StopProcessing': False,
            'HelixAngle': 5,
            'HelixConeAngle': 0,
            'HelixDiameterLimit': 0.0,
            'AdaptiveInputState': "",
            'AdaptiveOutputState': "",
            'KeepToolDownRatio': 3.0,
            'UseHelixArcs': False,
            'DisableHelixEntry': False
        }

    @classmethod
    def adaptivePropertyEnumerations(cls):
        '''adaptivePropertyEnumerations() ... returns a dictionary of enumeration lists
        for the operation's enumeration type properties.'''
        # Enumeration lists for App::PropertyEnumeration properties
        return {
            'OperationType': ['Clearing', 'Profile'],
            'CutSide': ['Outside', 'Inside'],
        }

    @classmethod
    def adaptiveSetEditorModes(cls, obj, hide=False):
        '''adaptiveSetEditorModes(obj) ... Set property editor modes.'''
        # Always hide these properties
        obj.setEditorMode('Stopped', 2)
        obj.setEditorMode('StopProcessing', 2)
        obj.setEditorMode('AdaptiveInputState', 2)
        obj.setEditorMode('AdaptiveOutputState', 2)

        mode = 0
        if hide:
            mode = 2
        obj.setEditorMode('CutSide', mode)
        obj.setEditorMode('OperationType', mode)
        obj.setEditorMode('Tolerance', mode)
        obj.setEditorMode('LiftDistance', mode)
        obj.setEditorMode('KeepToolDownRatio', mode)
        obj.setEditorMode('ForceInsideOut', mode)
        obj.setEditorMode('FinishingProfile', mode)
        obj.setEditorMode('UseHelixArcs', mode)
        obj.setEditorMode('HelixAngle', mode)
        obj.setEditorMode('HelixConeAngle', mode)
        obj.setEditorMode('HelixDiameterLimit', mode)
# Eclass


class StrategyClearing_ORIG:
    '''StrategyClearing(obj, workingShape, depthParams)...
    Creates a path geometry shape from an assigned pattern for conversion to tool paths.
    Arguments:    
        - obj: the operation object
        - shape: the horizontal planar shape
        - pattern: the name of the geometric pattern to apply
    Available Patterns:
        - Line, LineOffset, ZigZag, ZigZagOffset, Circular, CircularZigZag, Offset, Spiral, Profile
    Usage:
        - Call the _generatePathGeometry() method to request the path geometry.
        - The path geometry has correctional linking applied.

        strategy = StrategyClearing(shape,
                                obj.ClearanceHeight.Value,
                                obj.SafeHeight.Value,
                                obj.PatternCenterAt,
                                obj.PatternCenterCustom,
                                obj.CutPatternReversed,
                                obj.CutPatternAngle,
                                obj.CutPattern,
                                obj.CutMode,
                                float(obj.StepOver.Value),
                                obj.ExtraOffset.Value,
                                obj.MinTravel,
                                obj.KeepToolDown,
                                obj.ToolController,
                                startPoint,
                                self.depthparams,
                                self.job.GeometryTolerance.Value)
        strategy.execute()  # (pathCmds, pathGeom, sim)
        pathCmds = strategy.commandList
        sim = strategy.simObj
        if obj.PatternCenterAt != 'Custom' and strategy.centerOfPattern is not None:
            obj.PatternCenterCustom = strategy.centerOfPattern
        obj.AreaParams = strategy.areaParams
        obj.PathParams = strategy.pathParams
    '''

    # Register valid patterns here by name
    # Create a corresponding processing method below. Precede the name with an underscore(_)
    patterns = ('Adaptive', 'Circular', 'CircularZigZag', 'Grid', 'Line', 'LineOffset', 'Offset', 'Spiral', 'Triangle', 'ZigZag', 'ZigZagOffset')
    rotatablePatterns = ('Line', 'ZigZag', 'LineOffset', 'ZigZagOffset')
    curvedPatterns = ('Circular', 'CircularZigZag', 'Spiral')

    def __init__(self,
                 workingShape,
                 clearanceHeight,
                 safeHeight,
                 patternCenterAt,
                 patternCenterCustom,
                 cutPatternReversed,
                 cutPatternAngle,
                 cutPattern,
                 cutDirection,
                 stepOver,
                 materialAllowance,
                 minTravel,
                 keepToolDown,
                 toolController,
                 startPoint,
                 depthParams,
                 jobTolerance):
        '''__init__(workingShape, clearanceHeight, safeHeight, patternCenterAt,
                    patternCenterCustom, cutPatternReversed, cutPatternAngle, stepOver,
                    cutPattern, cutDirection, materialAllowance,
                    toolController, startPoint, depthParams, jobTolerance)...
        StrategyClearing class constructor method.
        '''
        PathLog.debug("StrategyClearing.__init__()")

        # Debugging attributes
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        self.showDebugShapes = False

        self.cutPattern = 'None'
        self.face = None
        self.rawGeoList = None
        self.centerOfMass = None
        self.centerOfPattern = None
        self.halfDiag = None
        self.halfPasses = None
        self.workingPlane = Part.makeCircle(2.0)  # make circle for workplane
        self.rawPathGeometry = None
        self.linkedPathGeom = None
        self.endVectors = list()
        self.pathGeometry = list()
        self.commandList = list()
        self.useStaticCenter = True
        self.isCenterSet = False
        self.offsetDirection = -1.0  # 1.0=outside;  -1.0=inside
        self.endVector = None
        self.pathParams = ""
        self.areaParams = ""
        self.simObj = None

        # Save argument values to class instance
        self.workingShape = workingShape
        self.depthParams = depthParams
        self.clearanceHeight = clearanceHeight
        self.safeHeight = safeHeight
        self.patternCenterAt = patternCenterAt
        self.patternCenterCustom = patternCenterCustom
        self.cutPatternReversed = cutPatternReversed
        self.cutPatternAngle = cutPatternAngle
        self.cutDirection = cutDirection
        self.stepOver = stepOver
        self.materialAllowance = materialAllowance
        self.minTravel = minTravel
        self.keepToolDown = keepToolDown
        self.toolController = toolController
        self.jobTolerance = jobTolerance
        self.startPoint = startPoint
        # self.sampleInterval = sampleInterval

        self.vertFeed = toolController.VertFeed.Value
        self.horizFeed = toolController.HorizFeed.Value
        self.toolDiameter = float(toolController.Tool.Diameter)
        self.toolRadius = self.toolDiameter / 2.0
        self.cutOut = self.toolDiameter * (self.stepOver / 100.0)

        # validate requested pattern and proceed accordingly
        if cutPattern in self.patterns:  # and hasattr(self, '_' + cutPattern):
            self.cutPattern = cutPattern

        # Grid and Triangle pattern requirements - paths produced by Path.Area() and Path.fromShapes()
        self.pocketMode = 6
        self.orientation = 0  # ['Conventional', 'Climb']

    def _addDebugShape(self, shape, name="debug"):
        if self.isDebug and self.showDebugShapes:
            do = FreeCAD.ActiveDocument.addObject('Part::Feature', 'debug_' + name)
            do.Shape = shape
            do.purgeTouched()

    # Raw cut pattern geometry generation methods
    def _Line(self):
        geomList = list()
        centRot = FreeCAD.Vector(0.0, 0.0, 0.0)  # Bottom left corner of face/selection/model
        segLength = self.halfDiag
        if self.patternCenterAt in ['XminYmin', 'Custom']:
            segLength = 2.0 * self.halfDiag

        # Create end points for set of lines to intersect with cross-section face
        pntTuples = list()
        for lc in range((-1 * (self.halfPasses - 1)), self.halfPasses + 1):
            x1 = centRot.x - segLength
            x2 = centRot.x + segLength
            y1 = centRot.y + (lc * self.cutOut)
            # y2 = y1
            p1 = FreeCAD.Vector(x1, y1, 0.0)
            p2 = FreeCAD.Vector(x2, y1, 0.0)
            pntTuples.append((p1, p2))

        # Convert end points to lines
        
        if (self.cutDirection == 'Climb' and not self.cutPatternReversed) or (self.cutDirection != 'Climb' and self.cutPatternReversed):
            for (p2, p1) in pntTuples:
                wire = Part.Wire([Part.makeLine(p1, p2)])
                geomList.append(wire)
        else:
            for (p1, p2) in pntTuples:
                wire = Part.Wire([Part.makeLine(p1, p2)])
                geomList.append(wire)

        if self.cutPatternReversed:
            geomList.reverse()

        return geomList

    def _LineOffset(self):
        return self._Line()

    def _Circular(self):
        geomList = list()
        radialPasses = self._getRadialPasses()
        minRad = self.toolDiameter * 0.45
        '''
        siX3 = 3 * self.sampleInterval
        minRadSI = (siX3 / 2.0) / math.pi

        if minRad < minRadSI:
            minRad = minRadSI
        '''

        if (self.cutDirection == 'Climb' and not self.cutPatternReversed) or (self.cutDirection != 'Climb' and self.cutPatternReversed):
            direction = FreeCAD.Vector(0.0, 0.0, 1.0)
        else:
            direction = FreeCAD.Vector(0.0, 0.0, -1.0)

        # Make small center circle to start pattern
        if self.stepOver > 50:
            circle = Part.makeCircle(minRad, self.centerOfPattern, direction)
            geomList.append(circle)

        for lc in range(1, radialPasses + 1):
            rad = (lc * self.cutOut)
            if rad >= minRad:
                wire = Part.Wire([Part.makeCircle(rad, self.centerOfPattern, direction)])
                geomList.append(wire)

        # if (self.cutDirection == 'Climb' and not self.cutPatternReversed) or (self.cutDirection != 'Climb' and self.cutPatternReversed):

        if self.cutPatternReversed:
            geomList.reverse()

        return geomList

    def _CircularZigZag(self):
        geomList = list()
        radialPasses = self._getRadialPasses()
        minRad = self.toolDiameter * 0.45
        dirForward = FreeCAD.Vector(0, 0, 1)
        dirReverse = FreeCAD.Vector(0, 0, -1)

        if (self.cutDirection == 'Climb' and not self.cutPatternReversed) or (self.cutDirection != 'Climb' and self.cutPatternReversed):
            activeDir = dirForward
            direction = 1
        else:
            activeDir = dirReverse
            direction = -1

        # Make small center circle to start pattern
        if self.stepOver > 50:
            circle = Part.makeCircle(minRad, self.centerOfPattern, activeDir)
            geomList.append(circle)
            direction *= -1  # toggle direction
            activeDir = dirForward if direction > 0 else dirReverse  # update active direction after toggle

        for lc in range(1, radialPasses + 1):
            rad = (lc * self.cutOut)
            if rad >= minRad:
                wire = Part.Wire([Part.makeCircle(rad, self.centerOfPattern, activeDir)])
                geomList.append(wire)
                direction *= -1  # toggle direction
                activeDir = dirForward if direction > 0 else dirReverse  # update active direction after toggle
        # Efor

        if self.cutPatternReversed:
            geomList.reverse()

        return geomList

    def _ZigZag(self):
        geomList = list()
        centRot = FreeCAD.Vector(0.0, 0.0, 0.0)  # Bottom left corner of face/selection/model
        segLength = self.halfDiag
        if self.patternCenterAt == 'XminYmin':
            segLength = 2.0 * self.halfDiag

        # Create end points for set of lines to intersect with cross-section face
        pntTuples = list()
        direction = 1
        for lc in range((-1 * (self.halfPasses - 1)), self.halfPasses + 1):
            x1 = centRot.x - segLength
            x2 = centRot.x + segLength
            y1 = centRot.y + (lc * self.cutOut)
            # y2 = y1
            if direction == 1:
                p1 = FreeCAD.Vector(x1, y1, 0.0)
                p2 = FreeCAD.Vector(x2, y1, 0.0)
            else:
                p1 = FreeCAD.Vector(x2, y1, 0.0)
                p2 = FreeCAD.Vector(x1, y1, 0.0)
            pntTuples.append((p1, p2))
            # swap direction
            direction *= -1

        # Convert end points to lines
        if (self.cutDirection == 'Climb' and not self.cutPatternReversed) or (self.cutDirection != 'Climb' and self.cutPatternReversed):
            for (p2, p1) in pntTuples:
                wire = Part.Wire([Part.makeLine(p1, p2)])
                geomList.append(wire)
        else:
            for (p1, p2) in pntTuples:
                wire = Part.Wire([Part.makeLine(p1, p2)])
                geomList.append(wire)

        if self.cutPatternReversed:
            geomList.reverse()

        return geomList

    def _ZigZagOffset(self):
        return self._ZigZag()

    def _Offset(self):
        return self._getAllOffsetWires()

    def _Spiral(self):
        geomList = list()
        SEGS = list()
        draw = True
        loopRadians = 0.0  # Used to keep track of complete loops/cycles
        sumRadians = 0.0
        loopCnt = 0
        segCnt = 0
        twoPi = 2.0 * math.pi
        maxDist = math.ceil(self.cutOut * self._getRadialPasses())  # self.halfDiag
        move = self.centerOfPattern  # Use to translate the center of the spiral
        lastPoint = self.centerOfPattern

        # Set tool properties and calculate cutout
        cutOut = self.cutOut / twoPi
        segLen = self.cutOut / 2.0  # self.sampleInterval
        stepAng = segLen / ((loopCnt + 1) * self.cutOut)
        stopRadians = maxDist / cutOut

        if self.cutPatternReversed:
            PathLog.debug("_Spiral() REVERSED pattern")
            if self.cutDirection == 'Conventional':
                getPoint = self._makeOppSpiralPnt
            else:
                getPoint = self._makeRegSpiralPnt

            while draw:
                radAng = sumRadians + stepAng
                p1 = lastPoint
                p2 = getPoint(move, cutOut, radAng)  # cutOut is 'b' in the equation r = b * radAng
                sumRadians += stepAng  # Increment sumRadians
                loopRadians += stepAng  # Increment loopRadians
                if loopRadians > twoPi:
                    loopCnt += 1
                    loopRadians -= twoPi
                    stepAng = segLen / ((loopCnt + 1) * self.cutOut)  # adjust stepAng with each loop/cycle
                segCnt += 1
                lastPoint = p2
                if sumRadians > stopRadians:
                    draw = False
                # Create line and show in Object tree
                lineSeg = Part.makeLine(p2, p1)
                SEGS.append(lineSeg)
            # Ewhile
            SEGS.reverse()
        else:
            PathLog.debug("_Spiral() regular pattern")
            if self.cutDirection == 'Conventional':
                getPoint = self._makeOppSpiralPnt
            else:
                getPoint = self._makeRegSpiralPnt

            while draw:
                radAng = sumRadians + stepAng
                p1 = lastPoint
                p2 = getPoint(move, cutOut, radAng)  # cutOut is 'b' in the equation r = b * radAng
                sumRadians += stepAng  # Increment sumRadians
                loopRadians += stepAng  # Increment loopRadians
                if loopRadians > twoPi:
                    loopCnt += 1
                    loopRadians -= twoPi
                    stepAng = segLen / ((loopCnt + 1) * self.cutOut)  # adjust stepAng with each loop/cycle
                # Create line and show in Object tree
                lineSeg = Part.makeLine(p1, p2)
                SEGS.append(lineSeg)
                # increment loop items
                segCnt += 1
                lastPoint = p2
                if sumRadians > stopRadians:
                    draw = False
            # Ewhile
        # Eif

        spiral = Part.Wire([ls.Edges[0] for ls in SEGS])
        geomList.append(spiral)

        return geomList

    # Path linking methods
    def _Link_Line(self):
        '''_Link_Line()'''
        allGroups = list()
        allWires = list()

        i = 0
        edges = self.rawPathGeometry.Edges
        limit = len(edges)

        if limit == 0:
            return allWires

        e = edges[0]
        p0 = e.Vertexes[0].Point
        p1 = e.Vertexes[1].Point
        vect = p1.sub(p0)
        targetAng = math.atan2(vect.y, vect.x)
        group = [(edges[0], vect)]

        for i in range(1, limit):
            # get next edge
            ne = edges[i]
            np1 = ne.Vertexes[1].Point
            diff = np1.sub(p0)
            nxtAng = math.atan2(diff.y, diff.x)

            # Check if prev and next are colinear
            angDiff = abs(nxtAng - targetAng)
            if angDiff < 0.0000001:
                group.append((ne, np1.sub(p0).Length))
            else:
                # Save current group
                allGroups.append(group)
                # Rotate edge and point value
                e = ne
                p0 = ne.Vertexes[0].Point
                # Create new group
                group = [(ne, np1.sub(p0).Length)]

        allGroups.append(group)

        if self.cutPattern.startswith("ZigZag") and self.keepToolDown and False:
            # The KeepToolDown feature likely needs an independent path-building method to properly keep tool down on zigs and zags
            g = allGroups.pop(0)
            if len(g) == 1:
                wires = [Part.Wire([g[0][0]])]
            else:
                g.sort(key=lambda grp: grp[1])
                wires = [Part.Wire([edg]) for edg, __ in g]
            allWires.extend(wires)
            # get last vertex
            lastWire = allWires[len(allWires) - 1]
            lastEndPoint = lastWire.Vertexes[1].Point

            for g in allGroups:
                if len(g) == 1:
                    wires = [Part.Wire([g[0][0]])]
                    lastWire = wires[0]
                else:
                    g.sort(key=lambda grp: grp[1])
                    wires = [Part.Wire([edg]) for edg, __ in g]
                    lastWire = wires[len(wires) - 1]
                startPoint = wires[0].Vertexes[0].Point
                transitionWire = Part.Wire(Part.makeLine(lastEndPoint, startPoint))
                wires.insert(0, transitionWire)
                lastEndPoint = lastWire.Vertexes[1].Point
                allWires.extend(wires)

        else:
            for g in allGroups:
                if len(g) == 1:
                    wires = [Part.Wire([g[0][0]])]
                else:
                    g.sort(key=lambda grp: grp[1])
                    wires = [Part.Wire([edg]) for edg, __ in g]
                allWires.extend(wires)


        return allWires

    def _Link_LineOffset(self):
        return self._Link_Line()

    def _Link_Circular(self):
        '''_Link_Circular()'''
        # PathLog.debug("_Link_Circular()")

        def combineAdjacentArcs(grp):
            '''combineAdjacentArcs(arcList)...
            Combine two adjacent arcs in list into single.
            The two arcs in the original list are replaced by the new single. The modified list is returned.
            '''
            # PathLog.debug("combineAdjacentArcs()")

            i = 1
            limit = len(grp)
            arcs = list()
            saveLast = False

            arc = grp[0]
            aP0 = arc.Vertexes[0].Point
            aP1 = arc.Vertexes[1].Point

            while i < limit:
                nArc = grp[i]
                naP0 = nArc.Vertexes[0].Point
                naP1 = nArc.Vertexes[1].Point
                if abs(arc.Curve.AngleXU) == 0.0:
                    reversed = False
                else:
                    reversed = True
                # Check if arcs are connected
                if naP1.sub(aP0).Length < 0.00001:
                    PathLog.info("combining arcs")
                    # Create one continuous arc
                    cent = arc.Curve.Center
                    vect0 = aP1.sub(cent)
                    vect1 = naP0.sub(cent)
                    radius = arc.Curve.Radius
                    direct = FreeCAD.Vector(0.0, 0.0, 1.0)
                    angle0 = math.degrees(math.atan2(vect1.y, vect1.x))
                    angle1 = math.degrees(math.atan2(vect0.y, vect0.x))
                    if reversed:
                        newArc = Part.makeCircle(radius, cent, direct.multiply(-1.0), 360.0-angle0, 360-angle1)  # makeCircle(radius,[pnt,dir,angle1,angle2])
                    else:
                        newArc = Part.makeCircle(radius, cent, direct, angle0, angle1)  # makeCircle(radius,[pnt,dir,angle1,angle2])
                    ang = aP0.sub(cent).normalize()
                    line = Part.makeLine(cent, aP0.add(ang))
                    touch = DraftGeomUtils.findIntersection(newArc, line)
                    if not touch:
                        if reversed:
                            newArc = Part.makeCircle(radius, cent, direct.multiply(-1.0), 360.0-angle1, 360-angle0)  # makeCircle(radius,[pnt,dir,angle1,angle2])
                        else:
                            newArc = Part.makeCircle(radius, cent, direct, angle1, angle0)  # makeCircle(radius,[pnt,dir,angle1,angle2])
                    arcs.append(newArc)
                    i += 1
                    if i < limit:
                        arc = grp[i]
                        aP0 = arc.Vertexes[0].Point
                        aP1 = arc.Vertexes[1].Point
                        saveLast = True
                    else:
                        saveLast = False
                        break
                else:
                    arcs.append(arc)
                    arc = nArc
                    aP0 = arc.Vertexes[0].Point
                    aP1 = arc.Vertexes[1].Point
                    saveLast = True
                i += 1

            if saveLast:
                arcs.append(arc)

            return arcs

        allGroups = list()
        allEdges = list()
        edges = self.rawPathGeometry.Edges
        limit = len(edges)

        if limit == 0:
            return allEdges

        e = edges[0]
        rad = e.Curve.Radius
        group = [e]

        if limit > 1:
            for i in range(1, limit):
                # get next edge
                ne = edges[i]
                nRad = ne.Curve.Radius

                # Check if prev and next are colinear
                if abs(nRad - rad) < 0.000001:
                    group.append(ne)
                else:
                    allGroups.append(group)
                    e = ne
                    rad = nRad
                    group = [ne]

        allGroups.append(group)

        # Process last remaining group of edges
        for g in allGroups:
            if len(g) < 2:
                allEdges.append(g)
            else:
                allEdges.append(combineAdjacentArcs(g))

        return allEdges

    def _Link_CircularZigZag(self):
        return self._Link_Circular()

    def _Link_ZigZag(self):
        return self._Link_Line()

    def _Link_ZigZagOffset(self):
        return self._Link_Line()

    def _Link_Offset(self):
        # return self.rawPathGeometry
        if self.cutPatternReversed:
            return sorted(self.rawPathGeometry.Wires, key=lambda wire: Part.Face(wire).Area)
        else:
            return sorted(self.rawPathGeometry.Wires, key=lambda wire: Part.Face(wire).Area, reverse=True)

    def _Link_Spiral(self):
        def sortWires(wire):
            return wire.Vertexes[0].Point.sub(self.patternCenterCustom).Length
        if self.cutPatternReversed:
            return sorted(self.rawPathGeometry.Wires, key=sortWires, reverse=True)
        else:
            return sorted(self.rawPathGeometry.Wires, key=sortWires)

    # Support methods
    def _prepareConstants(self):
        if self.isCenterSet:
            if self.useStaticCenter:
                return

        # Compute weighted center of mass of all faces combined
        if self.patternCenterAt == 'CenterOfMass':
            comF = self.face.CenterOfMass
            self.centerOfMass = FreeCAD.Vector(comF.x, comF.y, 0.0)
        self.centerOfPattern = self._getPatternCenter()

        # calculate line length
        deltaC = self.workingShape.BoundBox.DiagonalLength
        lineLen = deltaC + (2.0 * self.toolDiameter)  # Line length to span boundbox diag with 2x cutter diameter extra on each end
        if self.patternCenterAt == 'Custom':
            distToCent = self.face.BoundBox.Center.sub(self.centerOfPattern).Length
            lineLen += distToCent
        self.halfDiag = math.ceil(lineLen / 2.0)

        # Calculate number of passes
        cutPasses = math.ceil(lineLen / self.cutOut) + 1  # Number of lines(passes) required to cover boundbox diagonal
        if self.patternCenterAt == 'Custom':
            self.halfPasses = math.ceil(cutPasses)
        else:
            self.halfPasses = math.ceil(cutPasses / 2.0)

        self.isCenterSet = True

    def _getPatternCenter(self):
        centerAt = self.patternCenterAt

        if centerAt == 'CenterOfMass':
            cntrPnt = FreeCAD.Vector(self.centerOfMass.x, self.centerOfMass.y, 0.0)
        elif centerAt == 'CenterOfBoundBox':
            cent = self.face.BoundBox.Center
            cntrPnt = FreeCAD.Vector(cent.x, cent.y, 0.0)
        elif centerAt == 'XminYmin':
            cntrPnt = FreeCAD.Vector(self.face.BoundBox.XMin, self.face.BoundBox.YMin, 0.0)
        elif centerAt == 'Custom':
            cntrPnt = FreeCAD.Vector(self.patternCenterCustom.x, self.patternCenterCustom.y, 0.0)

        self.centerOfPattern = cntrPnt

        return cntrPnt

    def _getRadialPasses(self):
        # recalculate number of passes, if need be
        radialPasses = self.halfPasses
        if self.patternCenterAt != 'CenterOfBoundBox':
            # make 4 corners of boundbox in XY plane, find which is greatest distance to new circular center
            EBB = self.face.BoundBox
            CORNERS = [
                FreeCAD.Vector(EBB.XMin, EBB.YMin, 0.0),
                FreeCAD.Vector(EBB.XMin, EBB.YMax, 0.0),
                FreeCAD.Vector(EBB.XMax, EBB.YMax, 0.0),
                FreeCAD.Vector(EBB.XMax, EBB.YMin, 0.0),
            ]
            dMax = 0.0
            for c in range(0, 4):
                dist = CORNERS[c].sub(self.centerOfPattern).Length
                if dist > dMax:
                    dMax = dist
            diag = dMax + (2.0 * self.toolDiameter)  # Line length to span boundbox diag with 2x cutter diameter extra on each end
            radialPasses = math.ceil(diag / self.cutOut) + 1  # Number of lines(passes) required to cover boundbox diagonal

        return radialPasses

    def _makeRegSpiralPnt(self, move, b, radAng):
        x = b * radAng * math.cos(radAng)
        y = b * radAng * math.sin(radAng)
        return FreeCAD.Vector(x, y, 0.0).add(move)

    def _makeOppSpiralPnt(self, move, b, radAng):
        x = b * radAng * math.cos(radAng)
        y = b * radAng * math.sin(radAng)
        return FreeCAD.Vector(-1 * x, y, 0.0).add(move)

    def _getAllOffsetWires(self):
        PathLog.debug('_getAllOffsetWires()')
        wires = list()
        shape = self.face
        offset = 0.0  # Start right at the edge of cut area
        direction = 0
        loop_cnt = 0

        def _get_direction(w):
            if PathOpTools._isWireClockwise(w):
                return 1
            return -1

        def _reverse_wire(w):
            rev_list = list()
            for e in w.Edges:
                rev_list.append(PathUtils.reverseEdge(e))
            rev_list.reverse()
            return Part.Wire(rev_list)

        while True:
            offsetArea = PathUtils.getOffsetArea(shape, offset, plane=self.workingPlane)
            if not offsetArea:
                # Area fully consumed
                break

            # set initial cut direction
            if direction == 0:
                first_face_wire = offsetArea.Faces[0].Wires[0]
                direction = _get_direction(first_face_wire)
                if self.cutDirection == 'Climb':
                    if direction == 1:
                        direction = -1
                else:
                    if direction == -1:
                        direction = 1

            # Correct cut direction for `Conventional` cuts
            if self.cutDirection == 'Conventional':
                if loop_cnt == 1:
                    direction = direction * -1

            # process each wire within face
            for f in offsetArea.Faces:
                wire_cnt = 0
                for w in f.Wires:
                    use_direction = direction
                    if wire_cnt > 0:
                        # swap direction for internal features
                        use_direction = direction * -1
                    wire_direction = _get_direction(w)
                    # Process wire
                    if wire_direction == use_direction:
                        # direction is correct
                        wires.append(w)
                    else:
                        # incorrect direction, so reverse wire
                        rw = _reverse_wire(w)
                        wires.append(rw)

            offset -= self.cutOut
            loop_cnt += 1
        return wires

    def _getProfileWires(self):
        wireList = list()
        shape = self.face
        offset = 0.0
        direction = 0

        def _get_direction(w):
            if PathOpTools._isWireClockwise(w):
                return 1
            return -1

        def _reverse_wire(w):
            rev_list = list()
            for e in w.Edges:
                rev_list.append(PathUtils.reverseEdge(e))
            rev_list.reverse()
            return Part.Wire(rev_list)

        offsetArea = PathUtils.getOffsetArea(shape, offset, plane=self.workingPlane)
        if not offsetArea:
            PathLog.debug('_getProfileWires() no offsetArea')
            # Area fully consumed
            return wireList

        # set initial cut direction
        if direction == 0:
            first_face_wire = offsetArea.Faces[0].Wires[0]
            direction = _get_direction(first_face_wire)
            if self.cutDirection == 'Conventional':
                if direction == 1:
                    direction = -1
            else:
                if direction == -1:
                    direction = 1

        # process each wire within face
        for f in offsetArea.Faces:
            wire_cnt = 0
            for w in f.Wires:
                use_direction = direction
                if wire_cnt > 0:
                    # swap direction for internal features
                    use_direction = direction * -1
                wire_direction = _get_direction(w)
                # Process wire
                if wire_direction == use_direction:
                    # direction is correct
                    wireList.append(w)
                else:
                    # incorrect direction, so reverse wire
                    rw = _reverse_wire(w)
                    wireList.append(rw)

        # __ = Part.show(Part.makeCompound(wireList))

        return wireList

    def _applyPathLinking(self):
        PathLog.track("_applyPathLinking({})".format(self.cutPattern))
        # patterns = ('Adaptive', 'Circular', 'CircularZigZag', 'Grid', 'Line', 'LineOffset', 'Offset', 'Spiral', 'Triangle', 'ZigZag', 'ZigZagOffset')
        linkMethod = getattr(self, "_Link_" + self.cutPattern)
        self.linkedPathGeom = linkMethod()

    def _generatePathGeometry(self):
        '''_generatePathGeometry()... This function generates path geometry shapes.'''
        PathLog.debug("_generatePathGeometry()")

        patternMethod = getattr(self, "_" + self.cutPattern)
        self.rawGeoList = patternMethod()

        # Create compound object to bind all geometry
        geomShape = Part.makeCompound(self.rawGeoList)

        self._addDebugShape(geomShape, 'rawPathGeomShape')  # Debugging

        # Position and rotate the Line and ZigZag geometry
        if self.cutPattern in self.rotatablePatterns:
            if self.cutPatternAngle != 0.0:
                geomShape.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), self.cutPatternAngle)
            bbC = self.centerOfPattern
            geomShape.Placement.Base = FreeCAD.Vector(bbC.x, bbC.y, 0.0 - geomShape.BoundBox.ZMin)

        self._addDebugShape(geomShape, 'tmpGeometrySet')  # Debugging

        # Return current geometry for Offset or Profile patterns
        if self.cutPattern == 'Offset' or self.cutPattern == 'Profile':
            self.rawPathGeometry = geomShape
            self._applyPathLinking()
            return self.linkedPathGeom

        # Add profile 'Offset' path after base pattern
        appendOffsetWires = False
        if self.cutPattern != 'Offset' and self.cutPattern[-6:] == 'Offset':
            appendOffsetWires = True
        
        # Identify intersection of cross-section face and lineset
        self.rawPathGeometry = self.face.common(Part.makeCompound(geomShape.Wires))

        self._addDebugShape(self.rawPathGeometry, 'rawPathGeometry')  # Debugging

        self._applyPathLinking()
        if appendOffsetWires:
            for wire in self._getProfileWires():
                lst = [wire]
                self.linkedPathGeom.append(lst)

        return self.linkedPathGeom

    # Path generation methods
    def _buildPaths(self, height, edgeLists):
        '''_buildPaths(height, edgeLists) ... internal function.'''
        PathLog.track()
        PathLog.debug("_buildPaths()")

        paths = []
        end_vector = None  # FreeCAD.Vector(0.0, 0.0, self.clearanceHeight)
        useStart = False
        if self.startPoint:
            useStart = True

        pathParams = {} # pylint: disable=assignment-from-no-return
        pathParams['feedrate'] = self.horizFeed
        pathParams['feedrate_v'] = self.vertFeed
        pathParams['verbose'] = True
        pathParams['return_end'] = True

        if self.keepToolDown and False:
            pathParams['threshold'] = self.toolDiameter * 1.001
            pathParams['resume_height'] = 0.0
            pathParams['retraction'] = height
        else:
            pathParams['resume_height'] = self.safeHeight
            pathParams['retraction'] = self.clearanceHeight

        # Note that emitting preambles between moves breaks some dressups and prevents path optimization on some controllers
        pathParams['preamble'] = False

        for grp in edgeLists:
            if isinstance(grp, Part.Wire):
                grp.translate(FreeCAD.Vector(0, 0, height))

                pathParams['shapes'] = [grp]

                vrtxs = grp.Vertexes
                if useStart:
                    pathParams['start'] = FreeCAD.Vector(self.startPoint.x, self.startPoint.y, self.safeHeight)
                    useStart = False
                else:
                    if end_vector:
                        pathParams['start'] = end_vector
                    else:
                        pathParams['start'] = FreeCAD.Vector(vrtxs[0].X, vrtxs[0].Y, vrtxs[0].Z)

                (pp, end_vector) = Path.fromShapes(**pathParams)
                paths.extend(pp.Commands)
            else:
                for e in grp:
                    e.translate(FreeCAD.Vector(0, 0, height))

                    pathParams['shapes'] = [e]

                    vrtxs = e.Vertexes
                    if useStart:
                        pathParams['start'] = FreeCAD.Vector(self.startPoint.x, self.startPoint.y, self.safeHeight)
                        useStart = False
                    else:
                        if end_vector:
                            pathParams['start'] = end_vector
                        else:
                            pathParams['start'] = FreeCAD.Vector(vrtxs[0].X, vrtxs[0].Y, vrtxs[0].Z)

                    (pp, end_vector) = Path.fromShapes(**pathParams)
                    paths.extend(pp.Commands)

        self.pathParams = str({key: value for key, value in pathParams.items() if key != 'shapes'})
        self.endVectors.append(end_vector)

        # PathLog.debug("Path with params: {} at height: {}".format(self.pathParams, height))

        return paths

    def _buildGridAndTrianglePaths(self, getsim=False):
        '''_buildGridAndTrianglePaths(getsim=False) ... internal function.'''
        PathLog.track()
        areaParams = {}
        pathParams = {}
        heights = [i for i in self.depthParams]
        PathLog.debug('depths: {}'.format(heights))

        if self.cutPattern == "Triangle":
            self.pocketMode = 7
        if self.cutDirection == "Climb":
            self.orientation = 1

        areaParams['Fill'] = 0
        areaParams['Coplanar'] = 0
        areaParams['PocketMode'] = 1
        areaParams['SectionCount'] = -1
        areaParams['Angle'] = self.cutPatternAngle
        areaParams['FromCenter'] = not self.cutPatternReversed
        areaParams['PocketStepover'] = (self.toolRadius * 2) * (float(self.stepOver)/100)
        areaParams['PocketExtraOffset'] = self.materialAllowance
        areaParams['ToolRadius'] = self.toolRadius
        # Path.Area() pattern list is ['None', 'ZigZag', 'Offset', 'Spiral', 'ZigZagOffset', 'Line', 'Grid', 'Triangle']
        areaParams['PocketMode'] = self.pocketMode  # should be a 6 or 7 to indicate the index for 'Grid' or 'Triangle'

        area = Path.Area()
        area.setPlane(PathUtils.makeWorkplane(Part.makeCircle(5.0)))
        area.add(self.workingShape)
        area.setParams(**areaParams)

        # Save area parameters
        self.areaParams = str(area.getParams())
        PathLog.debug("Area with params: {}".format(area.getParams()))

        # Extract layer sections from area object
        sections = area.makeSections(mode=0, project=False, heights=heights)
        PathLog.debug("sections = %s" % sections)
        shapelist = [sec.getShape() for sec in sections]
        PathLog.debug("shapelist = %s" % shapelist)

        # Set path parameters
        pathParams['orientation'] = self.orientation
        # if MinTravel is turned on, set path sorting to 3DSort
        # 3DSort shouldn't be used without a valid start point. Can cause
        # tool crash without it.
        #
        # ml: experimental feature, turning off for now (see https://forum.freecadweb.org/viewtopic.php?f=15&t=24422&start=30#p192458)
        # realthunder: I've fixed it with a new sorting algorithm, which I
        # tested fine, but of course need more test. Please let know if there is
        # any problem
        #
        if self.minTravel and self.startPoint:
            pathParams['sort_mode'] = 3
            pathParams['threshold'] = self.toolRadius * 2
        pathParams['shapes'] = shapelist
        pathParams['feedrate'] = self.horizFeed
        pathParams['feedrate_v'] = self.vertFeed
        pathParams['verbose'] = True
        pathParams['resume_height'] = self.safeHeight
        pathParams['retraction'] = self.clearanceHeight
        pathParams['return_end'] = True
        # Note that emitting preambles between moves breaks some dressups and prevents path optimization on some controllers
        pathParams['preamble'] = False

        if self.keepToolDown:
            pathParams['threshold'] = self.toolDiameter

        if self.endVector is not None:
            pathParams['start'] = self.endVector
        elif self.startPoint:
            pathParams['start'] = self.startPoint

        self.pathParams = str({key: value for key, value in pathParams.items() if key != 'shapes'})
        PathLog.debug("Path with params: {}".format(self.pathParams))

        # Build paths from path parameters
        (pp, end_vector) = Path.fromShapes(**pathParams)
        PathLog.debug('pp: {}, end vector: {}'.format(pp, end_vector))
        self.endVector = end_vector # pylint: disable=attribute-defined-outside-init

        simobj = None
        if getsim:
            areaParams['Thicken'] = True
            areaParams['ToolRadius'] = self.toolRadius - self.toolRadius * .005
            area.setParams(**areaParams)
            sec = area.makeSections(mode=0, project=False, heights=heights)[-1].getShape()
            simobj = sec.extrude(FreeCAD.Vector(0, 0, self.workingShape.BoundBox.ZMax))

        self.commandList = pp.Commands
        self.simObj = simobj

    # Public methods
    def execute(self, includePaths=True):
        '''execute(includePaths=True)...
        The public method for the StrategyClearing class.
        Returns a tuple containing a list of path commands and a list of shapes(wires and edges) as the path geometry.
        Set includePaths argument to False if only path geometry is desired.
        '''
        PathLog.debug("StrategyClearing.execute()")

        self.commandList = list()  # Reset list
        self.pathGeometry = list()  # Reset list
        self.isCenterSet = False
        depthParams = [i for i in self.depthParams]

        # Exit if pattern not available
        if self.cutPattern == 'None':
            return False

        if hasattr(self.workingShape, "Volume") and PathGeom.isRoughly(self.workingShape.Volume, 0.0):
            PathLog.debug("StrategyClearing: No volume in working shape.")
            return False

        if  self.cutPattern in ["Grid", "Triangle"]:
            self._buildGridAndTrianglePaths()
            return True

        # Make box to serve as cut tool, and move into position above shape
        sBB = self.workingShape.BoundBox

        success = False
        for passDepth in depthParams:
            # PathLog.debug("current passDepth: {}".format(passDepth))
            cutFace = PathGeom.makeBoundBoxFace(sBB, offset=5.0, zHeight=passDepth)
            workingFaces = self.workingShape.common(cutFace)
            if workingFaces and len(workingFaces.Faces) > 0:
                for wf in workingFaces.Faces:
                    wf.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - wf.BoundBox.ZMin))
                    #  Apply simple radius shrinking offset for clearing pattern generation.
                    ofstVal = self.offsetDirection * (self.toolRadius - (self.jobTolerance / 5.0) + self.materialAllowance)
                    offsetWF = PathUtils.getOffsetArea(wf, ofstVal)
                    if offsetWF and len(offsetWF.Faces) > 0:
                        for f in offsetWF.Faces:
                            self.face = f
                            self._prepareConstants()
                            pathGeom = self._generatePathGeometry()
                            self.pathGeometry.extend(pathGeom)
                            if includePaths:
                                pathCmds = self._buildPaths(passDepth, pathGeom)
                                self.commandList.extend(pathCmds)
                            success = True
                    else:
                        # PathLog.debug("No offset working faces at {} mm.".format(passDepth))
                        pass
            else:
                PathLog.debug("No working faces at {} mm. Canceling lower layers.".format(passDepth))
                if success:
                    break

        PathLog.debug("Path with params: {}".format(self.pathParams))

        endVectCnt = len(self.endVectors)
        if endVectCnt > 0:
            self.endVector = self.endVectors[endVectCnt - 1]

        return True
# Eclass


class StrategyClearVolume:
    '''StrategyClearing(obj, volumeShape, depthParams)...
    Creates a path geometry shape from an assigned pattern for conversion to tool paths.
    Arguments:    
        - obj: the operation object
        - shape: the horizontal planar shape
        - pattern: the name of the geometric pattern to apply
    Usage:
        - Call the _generatePathGeometry() method to request the path geometry.
        - The path geometry has correctional linking applied.

        strategy = StrategyClearing(shape,
                                obj.ClearanceHeight.Value,
                                obj.SafeHeight.Value,
                                obj.PatternCenterAt,
                                obj.PatternCenterCustom,
                                obj.CutPatternReversed,
                                obj.CutPatternAngle,
                                obj.CutPattern,
                                obj.CutMode,
                                float(obj.StepOver.Value),
                                obj.ExtraOffset.Value,
                                obj.MinTravel,
                                obj.KeepToolDown,
                                obj.ToolController,
                                startPoint,
                                self.depthparams,
                                self.job.GeometryTolerance.Value)
        strategy.execute()  # (pathCmds, pathGeom, sim)
        pathCmds = strategy.commandList
        sim = strategy.simObj
        if obj.PatternCenterAt != 'Custom' and strategy.centerOfPattern is not None:
            obj.PatternCenterCustom = strategy.centerOfPattern
        obj.AreaParams = strategy.areaParams
        obj.PathParams = strategy.pathParams
    '''

    def __init__(self,
                 volumeShape,
                 clearanceHeight,
                 safeHeight,
                 patternCenterAt,
                 patternCenterCustom,
                 cutPatternReversed,
                 cutPatternAngle,
                 cutPattern,
                 cutDirection,
                 stepOver,
                 materialAllowance,
                 minTravel,
                 keepToolDown,
                 toolController,
                 startPoint,
                 depthParams,
                 jobTolerance):
        '''__init__(volumeShape, clearanceHeight, safeHeight, patternCenterAt,
                    patternCenterCustom, cutPatternReversed, cutPatternAngle, stepOver,
                    cutPattern, cutDirection, materialAllowance,
                    toolController, startPoint, depthParams, jobTolerance)...
        StrategyClearing class constructor method.
        '''
        PathLog.debug("StrategyClearing.__init__()")

        # Debugging attributes
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        self.showDebugShapes = False

        self.cutPattern = 'None'
        self.face = None
        self.rawGeoList = None
        self.centerOfMass = None
        self.centerOfPattern = None
        self.halfDiag = None
        self.halfPasses = None
        self.workingPlane = Part.makeCircle(2.0)  # make circle for workplane
        self.rawPathGeometry = None
        self.linkedPathGeom = None
        self.endVectors = list()
        self.pathGeometry = list()
        self.commandList = list()
        self.useStaticCenter = True
        self.isCenterSet = False
        self.offsetDirection = -1.0  # 1.0=outside;  -1.0=inside
        self.endVector = None
        self.pathParams = ""
        self.areaParams = ""
        self.simObj = None

        # Save argument values to class instance
        self.volumeShape = volumeShape
        self.depthParams = depthParams
        self.clearanceHeight = clearanceHeight
        self.safeHeight = safeHeight
        self.patternCenterAt = patternCenterAt
        self.patternCenterCustom = patternCenterCustom
        self.cutPattern = cutPattern
        self.cutPatternReversed = cutPatternReversed
        self.cutPatternAngle = cutPatternAngle
        self.cutDirection = cutDirection
        self.stepOver = stepOver
        self.materialAllowance = materialAllowance
        self.minTravel = minTravel
        self.keepToolDown = keepToolDown
        self.toolController = toolController
        self.jobTolerance = jobTolerance
        self.startPoint = startPoint

        self.vertFeed = toolController.VertFeed.Value
        self.horizFeed = toolController.HorizFeed.Value
        self.toolDiameter = float(toolController.Tool.Diameter)
        self.toolRadius = self.toolDiameter / 2.0
        self.cutOut = self.toolDiameter * (self.stepOver / 100.0)

        # Grid and Triangle pattern requirements - paths produced by Path.Area() and Path.fromShapes()
        self.pocketMode = 6
        self.orientation = 0  # ['Conventional', 'Climb']

        # Adaptive-dependent attributes to be set by call to `setAdaptiveAttributes()` with required arguments
        self.operationType = None
        self.cutSide = None
        self.disableHelixEntry = None
        self.forceInsideOut = None
        self.liftDistance = None
        self.finishingProfile = None
        self.helixAngle = None
        self.helixConeAngle = None
        self.useHelixArcs = None
        self.helixDiameterLimit = None
        self.keepToolDownRatio = None
        self.tolerance = None
        self.stockShape = None

    def _getPathGeometry(self, face):
        pGG = PathGeometryGenerator(face,
                self.patternCenterAt,
                self.patternCenterCustom,
                self.cutPatternReversed,
                self.cutPatternAngle,
                self.cutPattern,
                self.cutDirection,
                self.stepOver,
                self.materialAllowance,
                self.minTravel,
                self.keepToolDown,
                self.toolController,
                self.jobTolerance)

        if self.cutPattern == 'Adaptive':
            pGG.setAdaptiveAttributes(self.operationType,
                self.cutSide,
                self.disableHelixEntry,
                self.forceInsideOut,
                self.liftDistance,
                self.finishingProfile,
                self.helixAngle,
                self.helixConeAngle,
                self.useHelixArcs,
                self.helixDiameterLimit,
                self.keepToolDownRatio,
                self.tolerance,
                self.stockShape)

        pGG.execute()
        return pGG.pathGeometry

    def _buildPaths(self, height, edgeLists):
        '''_buildPaths(height, edgeLists) ... internal function.'''
        PathLog.track()
        PathLog.debug("_buildPaths()")

        paths = []
        end_vector = None  # FreeCAD.Vector(0.0, 0.0, self.clearanceHeight)
        useStart = False
        if self.startPoint:
            useStart = True

        pathParams = {} # pylint: disable=assignment-from-no-return
        pathParams['feedrate'] = self.horizFeed
        pathParams['feedrate_v'] = self.vertFeed
        pathParams['verbose'] = True
        pathParams['return_end'] = True

        if self.keepToolDown and False:
            pathParams['threshold'] = self.toolDiameter * 1.001
            pathParams['resume_height'] = 0.0
            pathParams['retraction'] = height
        else:
            pathParams['resume_height'] = self.safeHeight
            pathParams['retraction'] = self.clearanceHeight

        # Note that emitting preambles between moves breaks some dressups and prevents path optimization on some controllers
        pathParams['preamble'] = False

        for grp in edgeLists:
            if isinstance(grp, Part.Wire):
                grp.translate(FreeCAD.Vector(0, 0, height))

                pathParams['shapes'] = [grp]

                vrtxs = grp.Vertexes
                if useStart:
                    pathParams['start'] = FreeCAD.Vector(self.startPoint.x, self.startPoint.y, self.safeHeight)
                    useStart = False
                else:
                    if end_vector:
                        pathParams['start'] = end_vector
                    else:
                        pathParams['start'] = FreeCAD.Vector(vrtxs[0].X, vrtxs[0].Y, vrtxs[0].Z)

                (pp, end_vector) = Path.fromShapes(**pathParams)
                paths.extend(pp.Commands)
            else:
                for e in grp:
                    e.translate(FreeCAD.Vector(0, 0, height))

                    pathParams['shapes'] = [e]

                    vrtxs = e.Vertexes
                    if useStart:
                        pathParams['start'] = FreeCAD.Vector(self.startPoint.x, self.startPoint.y, self.safeHeight)
                        useStart = False
                    else:
                        if end_vector:
                            pathParams['start'] = end_vector
                        else:
                            pathParams['start'] = FreeCAD.Vector(vrtxs[0].X, vrtxs[0].Y, vrtxs[0].Z)

                    (pp, end_vector) = Path.fromShapes(**pathParams)
                    paths.extend(pp.Commands)

        self.pathParams = str({key: value for key, value in pathParams.items() if key != 'shapes'})
        self.endVectors.append(end_vector)

        # PathLog.debug("Path with params: {} at height: {}".format(self.pathParams, height))

        return paths

    def _buildGridAndTrianglePaths(self, getsim=False):
        '''_buildGridAndTrianglePaths(getsim=False) ... internal function.'''
        PathLog.track()
        areaParams = {}
        pathParams = {}
        heights = [i for i in self.depthParams]
        PathLog.debug('depths: {}'.format(heights))

        if self.cutPattern == "Triangle":
            self.pocketMode = 7
        if self.cutDirection == "Climb":
            self.orientation = 1

        areaParams['Fill'] = 0
        areaParams['Coplanar'] = 0
        areaParams['PocketMode'] = 1
        areaParams['SectionCount'] = -1
        areaParams['Angle'] = self.cutPatternAngle
        areaParams['FromCenter'] = not self.cutPatternReversed
        areaParams['PocketStepover'] = (self.toolRadius * 2) * (float(self.stepOver)/100)
        areaParams['PocketExtraOffset'] = self.materialAllowance
        areaParams['ToolRadius'] = self.toolRadius
        # Path.Area() pattern list is ['None', 'ZigZag', 'Offset', 'Spiral', 'ZigZagOffset', 'Line', 'Grid', 'Triangle']
        areaParams['PocketMode'] = self.pocketMode  # should be a 6 or 7 to indicate the index for 'Grid' or 'Triangle'

        area = Path.Area()
        area.setPlane(PathUtils.makeWorkplane(Part.makeCircle(5.0)))
        area.add(self.volumeShape)
        area.setParams(**areaParams)

        # Save area parameters
        self.areaParams = str(area.getParams())
        PathLog.debug("Area with params: {}".format(area.getParams()))

        # Extract layer sections from area object
        sections = area.makeSections(mode=0, project=False, heights=heights)
        PathLog.debug("sections = %s" % sections)
        shapelist = [sec.getShape() for sec in sections]
        PathLog.debug("shapelist = %s" % shapelist)

        # Set path parameters
        pathParams['orientation'] = self.orientation
        # if MinTravel is turned on, set path sorting to 3DSort
        # 3DSort shouldn't be used without a valid start point. Can cause
        # tool crash without it.
        #
        # ml: experimental feature, turning off for now (see https://forum.freecadweb.org/viewtopic.php?f=15&t=24422&start=30#p192458)
        # realthunder: I've fixed it with a new sorting algorithm, which I
        # tested fine, but of course need more test. Please let know if there is
        # any problem
        #
        if self.minTravel and self.startPoint:
            pathParams['sort_mode'] = 3
            pathParams['threshold'] = self.toolRadius * 2
        pathParams['shapes'] = shapelist
        pathParams['feedrate'] = self.horizFeed
        pathParams['feedrate_v'] = self.vertFeed
        pathParams['verbose'] = True
        pathParams['resume_height'] = self.safeHeight
        pathParams['retraction'] = self.clearanceHeight
        pathParams['return_end'] = True
        # Note that emitting preambles between moves breaks some dressups and prevents path optimization on some controllers
        pathParams['preamble'] = False

        if self.keepToolDown:
            pathParams['threshold'] = self.toolDiameter

        if self.endVector is not None:
            pathParams['start'] = self.endVector
        elif self.startPoint:
            pathParams['start'] = self.startPoint

        self.pathParams = str({key: value for key, value in pathParams.items() if key != 'shapes'})
        PathLog.debug("Path with params: {}".format(self.pathParams))

        # Build paths from path parameters
        (pp, end_vector) = Path.fromShapes(**pathParams)
        PathLog.debug('pp: {}, end vector: {}'.format(pp, end_vector))
        self.endVector = end_vector # pylint: disable=attribute-defined-outside-init

        simobj = None
        if getsim:
            areaParams['Thicken'] = True
            areaParams['ToolRadius'] = self.toolRadius - self.toolRadius * .005
            area.setParams(**areaParams)
            sec = area.makeSections(mode=0, project=False, heights=heights)[-1].getShape()
            simobj = sec.extrude(FreeCAD.Vector(0, 0, self.volumeShape.BoundBox.ZMax))

        self.commandList = pp.Commands
        self.simObj = simobj

    # Public methods
    def setAdaptiveAttributes(self,
                              operationType,
                              cutSide,
                              disableHelixEntry,
                              forceInsideOut,
                              liftDistance,
                              finishingProfile,
                              helixAngle,
                              helixConeAngle,
                              useHelixArcs,
                              helixDiameterLimit,
                              keepToolDownRatio,
                              tolerance,
                              stockShape):
        '''setAdaptiveAttributes(operationType,
                                 cutSide,
                                 disableHelixEntry,
                                 forceInsideOut,
                                 liftDistance,
                                 finishingProfile,
                                 helixAngle,
                                 helixConeAngle,
                                 useHelixArcs,
                                 helixDiameterLimit,
                                 keepToolDownRatio,
                                 tolerance,
                                 stockShape):
        Call to set adaptive-dependent attributes.'''
        self.operationType = operationType
        self.cutSide = cutSide
        self.disableHelixEntry = disableHelixEntry
        self.forceInsideOut = forceInsideOut
        self.liftDistance = liftDistance
        self.finishingProfile = finishingProfile
        self.helixAngle = helixAngle
        self.helixConeAngle = helixConeAngle
        self.useHelixArcs = useHelixArcs
        self.helixDiameterLimit = helixDiameterLimit
        self.keepToolDownRatio = keepToolDownRatio
        self.tolerance = tolerance
        self.stockShape = stockShape

    def execute(self):
        '''execute()...
        The public method for the StrategyClearing class.
        Returns a tuple containing a list of path commands and a list of shapes(wires and edges) as the path geometry.
        '''
        PathLog.debug("StrategyClearing.execute()")

        self.commandList = list()  # Reset list
        self.pathGeometry = list()  # Reset list
        self.isCenterSet = False
        depthParams = [i for i in self.depthParams]

        # Exit if pattern not available
        if self.cutPattern == 'None':
            return False

        if hasattr(self.volumeShape, "Volume") and PathGeom.isRoughly(self.volumeShape.Volume, 0.0):
            PathLog.debug("StrategyClearing: No volume in working shape.")
            return False

        if  self.cutPattern in ["Grid", "Triangle"]:
            self._buildGridAndTrianglePaths()
            return True

        # Make box to serve as cut tool, and move into position above shape
        sBB = self.volumeShape.BoundBox

        success = False
        for passDepth in depthParams:
            # PathLog.debug("current passDepth: {}".format(passDepth))
            cutFace = PathGeom.makeBoundBoxFace(sBB, offset=5.0, zHeight=passDepth)
            workingFaces = self.volumeShape.common(cutFace)
            if workingFaces and len(workingFaces.Faces) > 0:
                for wf in workingFaces.Faces:
                    wf.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - wf.BoundBox.ZMin))
                    #  Apply simple radius shrinking offset for clearing pattern generation.
                    ofstVal = self.offsetDirection * (self.toolRadius - (self.jobTolerance / 5.0) + self.materialAllowance)
                    offsetWF = PathUtils.getOffsetArea(wf, ofstVal)
                    if offsetWF and len(offsetWF.Faces) > 0:
                        for f in offsetWF.Faces:
                            self.face = f
                            pathGeom = self._getPathGeometry(f)
                            self.pathGeometry.extend(pathGeom)
                            pathCmds = self._buildPaths(passDepth, pathGeom)
                            self.commandList.extend(pathCmds)
                            success = True
                    else:
                        # PathLog.debug("No offset working faces at {} mm.".format(passDepth))
                        pass
            else:
                PathLog.debug("No working faces at {} mm. Canceling lower layers.".format(passDepth))
                if success:
                    break

        PathLog.debug("Path with params: {}".format(self.pathParams))

        endVectCnt = len(self.endVectors)
        if endVectCnt > 0:
            self.endVector = self.endVectors[endVectCnt - 1]

        return True

    # Functions for managing properties and their default values
    @classmethod
    def adaptivePropertyDefinitions(cls):
        '''adaptivePropertyDefinitions() ... returns a list of tuples.
        Each tuple contains property declaration information in the
        form of (prototype, name, section, tooltip).'''
        return [
            ("App::PropertyEnumeration", "CutSide", "Adaptive", "Side of selected faces that tool should cut"),
            ("App::PropertyEnumeration", "OperationType", "Adaptive", "Type of adaptive operation"),
            ("App::PropertyFloat", "Tolerance", "Adaptive", "Influences accuracy and performance"),
            ("App::PropertyDistance", "LiftDistance", "Adaptive", "Lift distance for rapid moves"),
            ("App::PropertyDistance", "KeepToolDownRatio", "Adaptive", "Max length of keep tool down path compared to direct distance between points"),
            ("App::PropertyBool", "ForceInsideOut", "Adaptive", "Force plunging into material inside and clearing towards the edges"),
            ("App::PropertyBool", "FinishingProfile", "Adaptive", "To take a finishing profile path at the end"),
            ("App::PropertyBool", "Stopped", "Adaptive", "Stop processing"),
            ("App::PropertyBool", "StopProcessing", "Adaptive", "Stop processing"),
            ("App::PropertyBool", "UseHelixArcs", "Adaptive", "Use Arcs (G2) for helix ramp"),
            ("App::PropertyPythonObject", "AdaptiveInputState", "Adaptive", "Internal input state"),
            ("App::PropertyPythonObject", "AdaptiveOutputState", "Adaptive", "Internal output state"),
            ("App::PropertyAngle", "HelixAngle", "Adaptive", "Helix ramp entry angle (degrees)"),
            ("App::PropertyAngle", "HelixConeAngle", "Adaptive", "Helix cone angle (degrees)"),
            ("App::PropertyLength", "HelixDiameterLimit", "Adaptive", "Limit helix entry diameter, if limit larger than tool diameter or 0, tool diameter is used"),
            ("App::PropertyBool", "DisableHelixEntry", "Adaptive", "Disable the helix entry, and use simple plunge.")
        ]

    @classmethod
    def adaptivePropertyDefaults(cls, obj, job):
        '''adaptivePropertyDefaults(obj, job) ... returns a dictionary of default values
        for the strategy's properties.'''
        return {
            'CutSide': "Inside",
            'OperationType': "Clearing",
            'Tolerance': 0.1,
            'LiftDistance': 0,
            'ForceInsideOut': False,
            'FinishingProfile': True,
            'Stopped': False,
            'StopProcessing': False,
            'HelixAngle': 5,
            'HelixConeAngle': 0,
            'HelixDiameterLimit': 0.0,
            'AdaptiveInputState': "",
            'AdaptiveOutputState': "",
            'KeepToolDownRatio': 3.0,
            'UseHelixArcs': False,
            'DisableHelixEntry': False
        }

    @classmethod
    def adaptivePropertyEnumerations(cls):
        '''adaptivePropertyEnumerations() ... returns a dictionary of enumeration lists
        for the operation's enumeration type properties.'''
        # Enumeration lists for App::PropertyEnumeration properties
        return {
            'OperationType': ['Clearing', 'Profile'],
            'CutSide': ['Outside', 'Inside'],
        }

    @classmethod
    def adaptiveSetEditorModes(cls, obj, hide=False):
        '''adaptiveSetEditorModes(obj) ... Set property editor modes.'''
        # Always hide these properties
        obj.setEditorMode('Stopped', 2)
        obj.setEditorMode('StopProcessing', 2)
        obj.setEditorMode('AdaptiveInputState', 2)
        obj.setEditorMode('AdaptiveOutputState', 2)

        mode = 0
        if hide:
            mode = 2
        obj.setEditorMode('CutSide', mode)
        obj.setEditorMode('OperationType', mode)
        obj.setEditorMode('Tolerance', mode)
        obj.setEditorMode('LiftDistance', mode)
        obj.setEditorMode('KeepToolDownRatio', mode)
        obj.setEditorMode('ForceInsideOut', mode)
        obj.setEditorMode('FinishingProfile', mode)
        obj.setEditorMode('UseHelixArcs', mode)
        obj.setEditorMode('HelixAngle', mode)
        obj.setEditorMode('HelixConeAngle', mode)
        obj.setEditorMode('HelixDiameterLimit', mode)
# Eclass


class PathGeometryGenerator:
    '''PathGeometryGenerator(obj, workingFace, depthParams)...
    Creates a path geometry shape from an assigned pattern for conversion to tool paths.
    Arguments:    
        - obj: the operation object
        - shape: the horizontal planar shape
        - pattern: the name of the geometric pattern to apply
    Available Patterns:
        - Line, LineOffset, ZigZag, ZigZagOffset, Circular, CircularZigZag, Offset, Spiral, Profile
    Usage:
        - Call the _generatePathGeometry() method to request the path geometry.
        - The path geometry has correctional linking applied.

        strategy = StrategyClearing(shape,
                                obj.ClearanceHeight.Value,
                                obj.SafeHeight.Value,
                                obj.PatternCenterAt,
                                obj.PatternCenterCustom,
                                obj.CutPatternReversed,
                                obj.CutPatternAngle,
                                obj.CutPattern,
                                obj.CutMode,
                                float(obj.StepOver.Value),
                                obj.ExtraOffset.Value,
                                obj.MinTravel,
                                obj.KeepToolDown,
                                obj.ToolController,
                                startPoint,
                                self.depthparams,
                                self.job.GeometryTolerance.Value)
        strategy.execute()  # (pathCmds, pathGeom, sim)
        pathCmds = strategy.commandList
        sim = strategy.simObj
        if obj.PatternCenterAt != 'Custom' and strategy.centerOfPattern is not None:
            obj.PatternCenterCustom = strategy.centerOfPattern
        obj.AreaParams = strategy.areaParams
        obj.PathParams = strategy.pathParams
    '''

    # Register valid patterns here by name
    # Create a corresponding processing method below. Precede the name with an underscore(_)
    patterns = ('Adaptive', 'Circular', 'CircularZigZag', 'Grid', 'Line', 'LineOffset', 'Offset', 'Spiral', 'Triangle', 'ZigZag', 'ZigZagOffset')
    rotatablePatterns = ('Line', 'ZigZag', 'LineOffset', 'ZigZagOffset')
    curvedPatterns = ('Circular', 'CircularZigZag', 'Spiral')

    def __init__(self,
                 workingFace,
                 patternCenterAt,
                 patternCenterCustom,
                 cutPatternReversed,
                 cutPatternAngle,
                 cutPattern,
                 cutDirection,
                 stepOver,
                 materialAllowance,
                 minTravel,
                 keepToolDown,
                 toolController,
                 jobTolerance):
        '''__init__(workingFace, patternCenterAt, patternCenterCustom, cutPatternReversed, cutPatternAngle, stepOver,
                    cutPattern, cutDirection, materialAllowance, minTravel, jobTolerance)...
        PathGeometryGenerator class constructor method.
        '''
        PathLog.debug("PathGeometryGenerator.__init__()")

        # Debugging attributes
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        self.showDebugShapes = False

        self.cutPattern = 'None'
        self.face = None
        self.rawGeoList = None
        self.centerOfMass = None
        self.centerOfPattern = None
        self.halfDiag = None
        self.halfPasses = None
        self.workingPlane = Part.makeCircle(2.0)  # make circle for workplane
        self.rawPathGeometry = None
        self.linkedPathGeom = None
        self.pathGeometry = list()
        self.commandList = list()
        self.useStaticCenter = True
        self.isCenterSet = False
        self.offsetDirection = -1.0  # 1.0=outside;  -1.0=inside
        self.endVector = None
        self.pathParams = ""
        self.areaParams = ""
        self.pfsRtn = None

        # Save argument values to class instance
        self.workingFace = workingFace
        self.patternCenterAt = patternCenterAt
        self.patternCenterCustom = patternCenterCustom
        self.cutPatternReversed = cutPatternReversed
        self.cutPatternAngle = cutPatternAngle
        self.cutDirection = cutDirection
        self.stepOver = stepOver
        self.materialAllowance = materialAllowance
        self.minTravel = minTravel
        self.keepToolDown = keepToolDown
        self.toolController = toolController
        self.jobTolerance = jobTolerance

        self.toolDiameter = float(toolController.Tool.Diameter)
        self.toolRadius = self.toolDiameter / 2.0
        self.cutOut = self.toolDiameter * (self.stepOver / 100.0)

        if cutPattern in self.patterns:
            self.cutPattern = cutPattern
        else:
            PathLog.info("The `{}` cut pattern is not available.".format(cutPattern))

        # Grid and Triangle pattern requirements - paths produced by Path.fromShapes()
        self.pocketMode = 6  # Grid=6, Triangle=7
        self.orientation = 0  # ['Conventional', 'Climb']

        ### Adaptive-specific attributes ###
        self.adaptiveGeometry = list()
        self.pathArray = list()
        self.operationType = None
        self.cutSide = None
        self.disableHelixEntry = None
        self.forceInsideOut = None
        self.liftDistance = None
        self.finishingProfile = None
        self.helixAngle = None
        self.helixConeAngle = None
        self.useHelixArcs = None
        self.helixDiameterLimit = None
        self.keepToolDownRatio = None
        self.tolerance = None
        self.stockObj = None

    def _addDebugShape(self, shape, name="debug"):
        if self.isDebug and self.showDebugShapes:
            do = FreeCAD.ActiveDocument.addObject('Part::Feature', 'debug_' + name)
            do.Shape = shape
            do.purgeTouched()

    # Raw cut pattern geometry generation methods
    def _Line(self):
        geomList = list()
        centRot = FreeCAD.Vector(0.0, 0.0, 0.0)  # Bottom left corner of face/selection/model
        segLength = self.halfDiag
        if self.patternCenterAt in ['XminYmin', 'Custom']:
            segLength = 2.0 * self.halfDiag

        # Create end points for set of lines to intersect with cross-section face
        pntTuples = list()
        for lc in range((-1 * (self.halfPasses - 1)), self.halfPasses + 1):
            x1 = centRot.x - segLength
            x2 = centRot.x + segLength
            y1 = centRot.y + (lc * self.cutOut)
            # y2 = y1
            p1 = FreeCAD.Vector(x1, y1, 0.0)
            p2 = FreeCAD.Vector(x2, y1, 0.0)
            pntTuples.append((p1, p2))

        # Convert end points to lines
        
        if (self.cutDirection == 'Climb' and not self.cutPatternReversed) or (self.cutDirection != 'Climb' and self.cutPatternReversed):
            for (p2, p1) in pntTuples:
                wire = Part.Wire([Part.makeLine(p1, p2)])
                geomList.append(wire)
        else:
            for (p1, p2) in pntTuples:
                wire = Part.Wire([Part.makeLine(p1, p2)])
                geomList.append(wire)

        if self.cutPatternReversed:
            geomList.reverse()

        return geomList

    def _LineOffset(self):
        return self._Line()

    def _Circular(self):
        geomList = list()
        radialPasses = self._getRadialPasses()
        minRad = self.toolDiameter * 0.45
        '''
        siX3 = 3 * self.sampleInterval
        minRadSI = (siX3 / 2.0) / math.pi

        if minRad < minRadSI:
            minRad = minRadSI
        '''

        if (self.cutDirection == 'Climb' and not self.cutPatternReversed) or (self.cutDirection != 'Climb' and self.cutPatternReversed):
            direction = FreeCAD.Vector(0.0, 0.0, 1.0)
        else:
            direction = FreeCAD.Vector(0.0, 0.0, -1.0)

        # Make small center circle to start pattern
        if self.stepOver > 50:
            circle = Part.makeCircle(minRad, self.centerOfPattern, direction)
            geomList.append(circle)

        for lc in range(1, radialPasses + 1):
            rad = (lc * self.cutOut)
            if rad >= minRad:
                wire = Part.Wire([Part.makeCircle(rad, self.centerOfPattern, direction)])
                geomList.append(wire)

        # if (self.cutDirection == 'Climb' and not self.cutPatternReversed) or (self.cutDirection != 'Climb' and self.cutPatternReversed):

        if self.cutPatternReversed:
            geomList.reverse()

        return geomList

    def _CircularZigZag(self):
        geomList = list()
        radialPasses = self._getRadialPasses()
        minRad = self.toolDiameter * 0.45
        dirForward = FreeCAD.Vector(0, 0, 1)
        dirReverse = FreeCAD.Vector(0, 0, -1)

        if (self.cutDirection == 'Climb' and not self.cutPatternReversed) or (self.cutDirection != 'Climb' and self.cutPatternReversed):
            activeDir = dirForward
            direction = 1
        else:
            activeDir = dirReverse
            direction = -1

        # Make small center circle to start pattern
        if self.stepOver > 50:
            circle = Part.makeCircle(minRad, self.centerOfPattern, activeDir)
            geomList.append(circle)
            direction *= -1  # toggle direction
            activeDir = dirForward if direction > 0 else dirReverse  # update active direction after toggle

        for lc in range(1, radialPasses + 1):
            rad = (lc * self.cutOut)
            if rad >= minRad:
                wire = Part.Wire([Part.makeCircle(rad, self.centerOfPattern, activeDir)])
                geomList.append(wire)
                direction *= -1  # toggle direction
                activeDir = dirForward if direction > 0 else dirReverse  # update active direction after toggle
        # Efor

        if self.cutPatternReversed:
            geomList.reverse()

        return geomList

    def _ZigZag(self):
        geomList = list()
        centRot = FreeCAD.Vector(0.0, 0.0, 0.0)  # Bottom left corner of face/selection/model
        segLength = self.halfDiag
        if self.patternCenterAt == 'XminYmin':
            segLength = 2.0 * self.halfDiag

        # Create end points for set of lines to intersect with cross-section face
        pntTuples = list()
        direction = 1
        for lc in range((-1 * (self.halfPasses - 1)), self.halfPasses + 1):
            x1 = centRot.x - segLength
            x2 = centRot.x + segLength
            y1 = centRot.y + (lc * self.cutOut)
            # y2 = y1
            if direction == 1:
                p1 = FreeCAD.Vector(x1, y1, 0.0)
                p2 = FreeCAD.Vector(x2, y1, 0.0)
            else:
                p1 = FreeCAD.Vector(x2, y1, 0.0)
                p2 = FreeCAD.Vector(x1, y1, 0.0)
            pntTuples.append((p1, p2))
            # swap direction
            direction *= -1

        # Convert end points to lines
        if (self.cutDirection == 'Climb' and not self.cutPatternReversed) or (self.cutDirection != 'Climb' and self.cutPatternReversed):
            for (p2, p1) in pntTuples:
                wire = Part.Wire([Part.makeLine(p1, p2)])
                geomList.append(wire)
        else:
            for (p1, p2) in pntTuples:
                wire = Part.Wire([Part.makeLine(p1, p2)])
                geomList.append(wire)

        if self.cutPatternReversed:
            geomList.reverse()

        return geomList

    def _ZigZagOffset(self):
        return self._ZigZag()

    def _Offset(self):
        return self._getAllOffsetWires()

    def _Spiral(self):
        geomList = list()
        SEGS = list()
        draw = True
        loopRadians = 0.0  # Used to keep track of complete loops/cycles
        sumRadians = 0.0
        loopCnt = 0
        segCnt = 0
        twoPi = 2.0 * math.pi
        maxDist = math.ceil(self.cutOut * self._getRadialPasses())  # self.halfDiag
        move = self.centerOfPattern  # Use to translate the center of the spiral
        lastPoint = self.centerOfPattern

        # Set tool properties and calculate cutout
        cutOut = self.cutOut / twoPi
        segLen = self.cutOut / 2.0  # self.sampleInterval
        stepAng = segLen / ((loopCnt + 1) * self.cutOut)
        stopRadians = maxDist / cutOut

        if self.cutPatternReversed:
            PathLog.debug("_Spiral() REVERSED pattern")
            if self.cutDirection == 'Conventional':
                getPoint = self._makeOppSpiralPnt
            else:
                getPoint = self._makeRegSpiralPnt

            while draw:
                radAng = sumRadians + stepAng
                p1 = lastPoint
                p2 = getPoint(move, cutOut, radAng)  # cutOut is 'b' in the equation r = b * radAng
                sumRadians += stepAng  # Increment sumRadians
                loopRadians += stepAng  # Increment loopRadians
                if loopRadians > twoPi:
                    loopCnt += 1
                    loopRadians -= twoPi
                    stepAng = segLen / ((loopCnt + 1) * self.cutOut)  # adjust stepAng with each loop/cycle
                segCnt += 1
                lastPoint = p2
                if sumRadians > stopRadians:
                    draw = False
                # Create line and show in Object tree
                lineSeg = Part.makeLine(p2, p1)
                SEGS.append(lineSeg)
            # Ewhile
            SEGS.reverse()
        else:
            PathLog.debug("_Spiral() regular pattern")
            if self.cutDirection == 'Conventional':
                getPoint = self._makeOppSpiralPnt
            else:
                getPoint = self._makeRegSpiralPnt

            while draw:
                radAng = sumRadians + stepAng
                p1 = lastPoint
                p2 = getPoint(move, cutOut, radAng)  # cutOut is 'b' in the equation r = b * radAng
                sumRadians += stepAng  # Increment sumRadians
                loopRadians += stepAng  # Increment loopRadians
                if loopRadians > twoPi:
                    loopCnt += 1
                    loopRadians -= twoPi
                    stepAng = segLen / ((loopCnt + 1) * self.cutOut)  # adjust stepAng with each loop/cycle
                # Create line and show in Object tree
                lineSeg = Part.makeLine(p1, p2)
                SEGS.append(lineSeg)
                # increment loop items
                segCnt += 1
                lastPoint = p2
                if sumRadians > stopRadians:
                    draw = False
            # Ewhile
        # Eif

        spiral = Part.Wire([ls.Edges[0] for ls in SEGS])
        geomList.append(spiral)

        return geomList

    def _Grid(self):
        self.pocketMode = 6
        return self._extractGridAndTriangleWires()

    def _Triangle(self):
        self.pocketMode = 7
        return self._extractGridAndTriangleWires()

    def _Adaptive(self):
        PathLog.info("*** Adaptive path geometry generation started...")
        start = time.time()

        self.workingFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - self.workingFace.BoundBox.ZMin))
        for w in self.workingFace.Wires:
            for e in w.Edges:
                self.pathArray.append([self._discretize(e)])

        path2d = self._convertTo2d(self.pathArray)

        stockPaths = []
        if hasattr(self.stockObj, "StockType") and self.stockObj.StockType == "CreateCylinder":
            stockPaths.append([self._discretize(self.stockObj.Shape.Edges[0])])

        else:
            stockBB = self.stockObj.Shape.BoundBox
            v = []
            v.append(FreeCAD.Vector(stockBB.XMin, stockBB.YMin, 0))
            v.append(FreeCAD.Vector(stockBB.XMax, stockBB.YMin, 0))
            v.append(FreeCAD.Vector(stockBB.XMax, stockBB.YMax, 0))
            v.append(FreeCAD.Vector(stockBB.XMin, stockBB.YMax, 0))
            v.append(FreeCAD.Vector(stockBB.XMin, stockBB.YMin, 0))
            stockPaths.append([v])

        stockPath2d = self._convertTo2d(stockPaths)

        opType = area.AdaptiveOperationType.ClearingInside
        if self.operationType == "Clearing":
            if self.cutSide == "Outside":
                opType = area.AdaptiveOperationType.ClearingOutside
            else:
                opType = area.AdaptiveOperationType.ClearingInside
        else:  # profile
            if self.cutSide == "Outside":
                opType = area.AdaptiveOperationType.ProfilingOutside
            else:
                opType = area.AdaptiveOperationType.ProfilingInside

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

        def progressFn(tpaths):
            '''progressFn(tpaths)... progress callback fn, if return true it will stop processing'''
            return False

        # EXECUTE
        try:
            results = a2d.Execute(stockPath2d, path2d, progressFn)
        except Exception as ee:
            FreeCAD.Console.PrintError(str(ee) + "\n")
            return list()
        else:
            # need to convert results to python object to be JSON serializable
            adaptiveResults = []
            for result in results:
                adaptiveResults.append({
                    "HelixCenterPoint": result.HelixCenterPoint,
                    "StartPoint": result.StartPoint,
                    "AdaptivePaths": result.AdaptivePaths,
                    "ReturnMotionType": result.ReturnMotionType})

            # Generate geometry
            # PathLog.info("Extracting wires from Adaptive data...")
            wires = list()
            motionCutting = area.AdaptiveMotionType.Cutting
            for region in adaptiveResults:
                for pth in region["AdaptivePaths"]:
                    motion = pth[0]  # [0] contains motion type
                    if motion == motionCutting:
                        edges = list()
                        sp = pth[1][0]
                        x = sp[0]
                        y = sp[1]
                        p1 = FreeCAD.Vector(x, y, 0.0)
                        for pt in pth[1][1:]:  # [1] contains list of points
                            xx = pt[0]
                            yy = pt[1]
                            p2 = FreeCAD.Vector(xx, yy, 0.0)
                            if not PathGeom.isRoughly(p1.sub(p2).Length, 0.0):
                                edges.append(Part.makeLine(p1, p2))
                                p1 = p2
                        wires.append(Part.Wire(Part.__sortEdges__(edges)))
            self.adaptiveGeometry = wires
            PathLog.info("*** Done. Elapsed time: %f sec" % (time.time()-start))
            return self.adaptiveGeometry

        return list()

    # Path linking methods
    def _Link_Line(self):
        '''_Link_Line()'''
        allGroups = list()
        allWires = list()

        i = 0
        edges = self.rawPathGeometry.Edges
        limit = len(edges)

        if limit == 0:
            return allWires

        e = edges[0]
        p0 = e.Vertexes[0].Point
        p1 = e.Vertexes[1].Point
        vect = p1.sub(p0)
        targetAng = math.atan2(vect.y, vect.x)
        group = [(edges[0], vect)]

        for i in range(1, limit):
            # get next edge
            ne = edges[i]
            np1 = ne.Vertexes[1].Point
            diff = np1.sub(p0)
            nxtAng = math.atan2(diff.y, diff.x)

            # Check if prev and next are colinear
            angDiff = abs(nxtAng - targetAng)
            if angDiff < 0.0000001:
                group.append((ne, np1.sub(p0).Length))
            else:
                # Save current group
                allGroups.append(group)
                # Rotate edge and point value
                e = ne
                p0 = ne.Vertexes[0].Point
                # Create new group
                group = [(ne, np1.sub(p0).Length)]

        allGroups.append(group)

        if self.cutPattern.startswith("ZigZag") and self.keepToolDown and False:
            # The KeepToolDown feature likely needs an independent path-building method to properly keep tool down on zigs and zags
            g = allGroups.pop(0)
            if len(g) == 1:
                wires = [Part.Wire([g[0][0]])]
            else:
                g.sort(key=lambda grp: grp[1])
                wires = [Part.Wire([edg]) for edg, __ in g]
            allWires.extend(wires)
            # get last vertex
            lastWire = allWires[len(allWires) - 1]
            lastEndPoint = lastWire.Vertexes[1].Point

            for g in allGroups:
                if len(g) == 1:
                    wires = [Part.Wire([g[0][0]])]
                    lastWire = wires[0]
                else:
                    g.sort(key=lambda grp: grp[1])
                    wires = [Part.Wire([edg]) for edg, __ in g]
                    lastWire = wires[len(wires) - 1]
                startPoint = wires[0].Vertexes[0].Point
                transitionWire = Part.Wire(Part.makeLine(lastEndPoint, startPoint))
                wires.insert(0, transitionWire)
                lastEndPoint = lastWire.Vertexes[1].Point
                allWires.extend(wires)

        else:
            for g in allGroups:
                if len(g) == 1:
                    wires = [Part.Wire([g[0][0]])]
                else:
                    g.sort(key=lambda grp: grp[1])
                    wires = [Part.Wire([edg]) for edg, __ in g]
                allWires.extend(wires)


        return allWires

    def _Link_LineOffset(self):
        return self._Link_Line()

    def _Link_Circular(self):
        '''_Link_Circular()'''
        # PathLog.debug("_Link_Circular()")

        def combineAdjacentArcs(grp):
            '''combineAdjacentArcs(arcList)...
            Combine two adjacent arcs in list into single.
            The two arcs in the original list are replaced by the new single. The modified list is returned.
            '''
            # PathLog.debug("combineAdjacentArcs()")

            i = 1
            limit = len(grp)
            arcs = list()
            saveLast = False

            arc = grp[0]
            aP0 = arc.Vertexes[0].Point
            aP1 = arc.Vertexes[1].Point

            while i < limit:
                nArc = grp[i]
                naP0 = nArc.Vertexes[0].Point
                naP1 = nArc.Vertexes[1].Point
                if abs(arc.Curve.AngleXU) == 0.0:
                    reversed = False
                else:
                    reversed = True
                # Check if arcs are connected
                if naP1.sub(aP0).Length < 0.00001:
                    PathLog.info("combining arcs")
                    # Create one continuous arc
                    cent = arc.Curve.Center
                    vect0 = aP1.sub(cent)
                    vect1 = naP0.sub(cent)
                    radius = arc.Curve.Radius
                    direct = FreeCAD.Vector(0.0, 0.0, 1.0)
                    angle0 = math.degrees(math.atan2(vect1.y, vect1.x))
                    angle1 = math.degrees(math.atan2(vect0.y, vect0.x))
                    if reversed:
                        newArc = Part.makeCircle(radius, cent, direct.multiply(-1.0), 360.0-angle0, 360-angle1)  # makeCircle(radius,[pnt,dir,angle1,angle2])
                    else:
                        newArc = Part.makeCircle(radius, cent, direct, angle0, angle1)  # makeCircle(radius,[pnt,dir,angle1,angle2])
                    ang = aP0.sub(cent).normalize()
                    line = Part.makeLine(cent, aP0.add(ang))
                    touch = DraftGeomUtils.findIntersection(newArc, line)
                    if not touch:
                        if reversed:
                            newArc = Part.makeCircle(radius, cent, direct.multiply(-1.0), 360.0-angle1, 360-angle0)  # makeCircle(radius,[pnt,dir,angle1,angle2])
                        else:
                            newArc = Part.makeCircle(radius, cent, direct, angle1, angle0)  # makeCircle(radius,[pnt,dir,angle1,angle2])
                    arcs.append(newArc)
                    i += 1
                    if i < limit:
                        arc = grp[i]
                        aP0 = arc.Vertexes[0].Point
                        aP1 = arc.Vertexes[1].Point
                        saveLast = True
                    else:
                        saveLast = False
                        break
                else:
                    arcs.append(arc)
                    arc = nArc
                    aP0 = arc.Vertexes[0].Point
                    aP1 = arc.Vertexes[1].Point
                    saveLast = True
                i += 1

            if saveLast:
                arcs.append(arc)

            return arcs

        allGroups = list()
        allEdges = list()
        edges = self.rawPathGeometry.Edges
        limit = len(edges)

        if limit == 0:
            return allEdges

        e = edges[0]
        rad = e.Curve.Radius
        group = [e]

        if limit > 1:
            for i in range(1, limit):
                # get next edge
                ne = edges[i]
                nRad = ne.Curve.Radius

                # Check if prev and next are colinear
                if abs(nRad - rad) < 0.000001:
                    group.append(ne)
                else:
                    allGroups.append(group)
                    e = ne
                    rad = nRad
                    group = [ne]

        allGroups.append(group)

        # Process last remaining group of edges
        for g in allGroups:
            if len(g) < 2:
                allEdges.append(g)
            else:
                allEdges.append(combineAdjacentArcs(g))

        return allEdges

    def _Link_CircularZigZag(self):
        return self._Link_Circular()

    def _Link_ZigZag(self):
        return self._Link_Line()

    def _Link_ZigZagOffset(self):
        return self._Link_Line()

    def _Link_Offset(self):
        # return self.rawPathGeometry
        if self.cutPatternReversed:
            return sorted(self.rawPathGeometry.Wires, key=lambda wire: Part.Face(wire).Area)
        else:
            return sorted(self.rawPathGeometry.Wires, key=lambda wire: Part.Face(wire).Area, reverse=True)

    def _Link_Spiral(self):
        def sortWires(wire):
            return wire.Vertexes[0].Point.sub(self.patternCenterCustom).Length
        if self.cutPatternReversed:
            return sorted(self.rawPathGeometry.Wires, key=sortWires, reverse=True)
        else:
            return sorted(self.rawPathGeometry.Wires, key=sortWires)

    def _Link_Grid(self):
        return self.rawPathGeometry.Wires

    def _Link_Triangle(self):
        return self.rawPathGeometry.Wires

    def _Link_Adaptive(self):
        return self.rawPathGeometry.Wires

    # Support methods
    def _prepareConstants(self):
        if self.isCenterSet:
            if self.useStaticCenter:
                return

        # Compute weighted center of mass of all faces combined
        if self.patternCenterAt == 'CenterOfMass':
            comF = self.face.CenterOfMass
            self.centerOfMass = FreeCAD.Vector(comF.x, comF.y, 0.0)
        self.centerOfPattern = self._getPatternCenter()

        # calculate line length
        deltaC = self.workingFace.BoundBox.DiagonalLength
        lineLen = deltaC + (2.0 * self.toolDiameter)  # Line length to span boundbox diag with 2x cutter diameter extra on each end
        if self.patternCenterAt == 'Custom':
            distToCent = self.face.BoundBox.Center.sub(self.centerOfPattern).Length
            lineLen += distToCent
        self.halfDiag = math.ceil(lineLen / 2.0)

        # Calculate number of passes
        cutPasses = math.ceil(lineLen / self.cutOut) + 1  # Number of lines(passes) required to cover boundbox diagonal
        if self.patternCenterAt == 'Custom':
            self.halfPasses = math.ceil(cutPasses)
        else:
            self.halfPasses = math.ceil(cutPasses / 2.0)

        self.isCenterSet = True

    def _getPatternCenter(self):
        centerAt = self.patternCenterAt

        if centerAt == 'CenterOfMass':
            cntrPnt = FreeCAD.Vector(self.centerOfMass.x, self.centerOfMass.y, 0.0)
        elif centerAt == 'CenterOfBoundBox':
            cent = self.face.BoundBox.Center
            cntrPnt = FreeCAD.Vector(cent.x, cent.y, 0.0)
        elif centerAt == 'XminYmin':
            cntrPnt = FreeCAD.Vector(self.face.BoundBox.XMin, self.face.BoundBox.YMin, 0.0)
        elif centerAt == 'Custom':
            cntrPnt = FreeCAD.Vector(self.patternCenterCustom.x, self.patternCenterCustom.y, 0.0)

        self.centerOfPattern = cntrPnt

        return cntrPnt

    def _getRadialPasses(self):
        # recalculate number of passes, if need be
        radialPasses = self.halfPasses
        if self.patternCenterAt != 'CenterOfBoundBox':
            # make 4 corners of boundbox in XY plane, find which is greatest distance to new circular center
            EBB = self.face.BoundBox
            CORNERS = [
                FreeCAD.Vector(EBB.XMin, EBB.YMin, 0.0),
                FreeCAD.Vector(EBB.XMin, EBB.YMax, 0.0),
                FreeCAD.Vector(EBB.XMax, EBB.YMax, 0.0),
                FreeCAD.Vector(EBB.XMax, EBB.YMin, 0.0),
            ]
            dMax = 0.0
            for c in range(0, 4):
                dist = CORNERS[c].sub(self.centerOfPattern).Length
                if dist > dMax:
                    dMax = dist
            diag = dMax + (2.0 * self.toolDiameter)  # Line length to span boundbox diag with 2x cutter diameter extra on each end
            radialPasses = math.ceil(diag / self.cutOut) + 1  # Number of lines(passes) required to cover boundbox diagonal

        return radialPasses

    def _makeRegSpiralPnt(self, move, b, radAng):
        x = b * radAng * math.cos(radAng)
        y = b * radAng * math.sin(radAng)
        return FreeCAD.Vector(x, y, 0.0).add(move)

    def _makeOppSpiralPnt(self, move, b, radAng):
        x = b * radAng * math.cos(radAng)
        y = b * radAng * math.sin(radAng)
        return FreeCAD.Vector(-1 * x, y, 0.0).add(move)

    def _getAllOffsetWires(self):
        PathLog.debug('_getAllOffsetWires()')
        wires = list()
        shape = self.face
        offset = 0.0  # Start right at the edge of cut area
        direction = 0
        loop_cnt = 0

        def _get_direction(w):
            if PathOpTools._isWireClockwise(w):
                return 1
            return -1

        def _reverse_wire(w):
            rev_list = list()
            for e in w.Edges:
                rev_list.append(PathUtils.reverseEdge(e))
            rev_list.reverse()
            return Part.Wire(rev_list)

        while True:
            offsetArea = PathUtils.getOffsetArea(shape, offset, plane=self.workingPlane)
            if not offsetArea:
                # Area fully consumed
                break

            # set initial cut direction
            if direction == 0:
                first_face_wire = offsetArea.Faces[0].Wires[0]
                direction = _get_direction(first_face_wire)
                if self.cutDirection == 'Climb':
                    if direction == 1:
                        direction = -1
                else:
                    if direction == -1:
                        direction = 1

            # Correct cut direction for `Conventional` cuts
            if self.cutDirection == 'Conventional':
                if loop_cnt == 1:
                    direction = direction * -1

            # process each wire within face
            for f in offsetArea.Faces:
                wire_cnt = 0
                for w in f.Wires:
                    use_direction = direction
                    if wire_cnt > 0:
                        # swap direction for internal features
                        use_direction = direction * -1
                    wire_direction = _get_direction(w)
                    # Process wire
                    if wire_direction == use_direction:
                        # direction is correct
                        wires.append(w)
                    else:
                        # incorrect direction, so reverse wire
                        rw = _reverse_wire(w)
                        wires.append(rw)

            offset -= self.cutOut
            loop_cnt += 1
        return wires

    def _getProfileWires(self):
        wireList = list()
        shape = self.face
        offset = 0.0
        direction = 0

        def _get_direction(w):
            if PathOpTools._isWireClockwise(w):
                return 1
            return -1

        def _reverse_wire(w):
            rev_list = list()
            for e in w.Edges:
                rev_list.append(PathUtils.reverseEdge(e))
            rev_list.reverse()
            return Part.Wire(rev_list)

        offsetArea = PathUtils.getOffsetArea(shape, offset, plane=self.workingPlane)
        if not offsetArea:
            PathLog.debug('_getProfileWires() no offsetArea')
            # Area fully consumed
            return wireList

        # set initial cut direction
        if direction == 0:
            first_face_wire = offsetArea.Faces[0].Wires[0]
            direction = _get_direction(first_face_wire)
            if self.cutDirection == 'Conventional':
                if direction == 1:
                    direction = -1
            else:
                if direction == -1:
                    direction = 1

        # process each wire within face
        for f in offsetArea.Faces:
            wire_cnt = 0
            for w in f.Wires:
                use_direction = direction
                if wire_cnt > 0:
                    # swap direction for internal features
                    use_direction = direction * -1
                wire_direction = _get_direction(w)
                # Process wire
                if wire_direction == use_direction:
                    # direction is correct
                    wireList.append(w)
                else:
                    # incorrect direction, so reverse wire
                    rw = _reverse_wire(w)
                    wireList.append(rw)

        # __ = Part.show(Part.makeCompound(wireList))

        return wireList

    def _applyPathLinking(self):
        PathLog.track("_applyPathLinking({})".format(self.cutPattern))
        # patterns = ('Adaptive', 'Circular', 'CircularZigZag', 'Grid', 'Line', 'LineOffset', 'Offset', 'Spiral', 'Triangle', 'ZigZag', 'ZigZagOffset')
        linkMethod = getattr(self, "_Link_" + self.cutPattern)
        self.linkedPathGeom = linkMethod()

    def _generatePathGeometry(self):
        '''_generatePathGeometry()... This function generates path geometry shapes.'''
        PathLog.debug("_generatePathGeometry()")

        patternMethod = getattr(self, "_" + self.cutPattern)
        self.rawGeoList = patternMethod()

        # Create compound object to bind all geometry
        geomShape = Part.makeCompound(self.rawGeoList)

        self._addDebugShape(geomShape, 'rawPathGeomShape')  # Debugging

        # Position and rotate the Line and ZigZag geometry
        if self.cutPattern in self.rotatablePatterns:
            if self.cutPatternAngle != 0.0:
                geomShape.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), self.cutPatternAngle)
            bbC = self.centerOfPattern
            geomShape.Placement.Base = FreeCAD.Vector(bbC.x, bbC.y, 0.0 - geomShape.BoundBox.ZMin)

        self._addDebugShape(geomShape, 'tmpGeometrySet')  # Debugging

        # Return current geometry for Offset or Profile patterns
        if self.cutPattern == 'Offset':
            self.rawPathGeometry = geomShape
            self._applyPathLinking()
            return self.linkedPathGeom

        # Add profile 'Offset' path after base pattern
        appendOffsetWires = False
        if self.cutPattern != 'Offset' and self.cutPattern[-6:] == 'Offset':
            appendOffsetWires = True
        
        # Identify intersection of cross-section face and lineset
        self.rawPathGeometry = self.face.common(Part.makeCompound(geomShape.Wires))

        self._addDebugShape(self.rawPathGeometry, 'rawPathGeometry')  # Debugging

        self._applyPathLinking()
        if appendOffsetWires:
            for wire in self._getProfileWires():
                lst = [wire]
                self.linkedPathGeom.append(lst)

        return self.linkedPathGeom

    def _extractGridAndTriangleWires(self):
        '''_buildGridAndTrianglePaths() ... internal function.'''
        PathLog.track()
        # areaParams = {}
        pathParams = {}
        heights = [0.0]

        if self.cutDirection == "Climb":
            self.orientation = 1

        '''
        areaParams['Fill'] = 0
        areaParams['Coplanar'] = 0
        areaParams['PocketMode'] = 1
        areaParams['SectionCount'] = -1
        areaParams['Angle'] = self.cutPatternAngle
        areaParams['FromCenter'] = not self.cutPatternReversed
        areaParams['PocketStepover'] = (self.toolRadius * 2) * (float(self.stepOver)/100)
        areaParams['PocketExtraOffset'] = self.materialAllowance
        areaParams['ToolRadius'] = self.toolRadius
        # Path.Area() pattern list is ['None', 'ZigZag', 'Offset', 'Spiral', 'ZigZagOffset', 'Line', 'Grid', 'Triangle']
        areaParams['PocketMode'] = self.pocketMode  # should be a 6 or 7 to indicate the index for 'Grid' or 'Triangle'

        area = Path.Area()
        area.setPlane(PathUtils.makeWorkplane(Part.makeCircle(5.0)))
        area.add(self.workingFace)
        area.setParams(**areaParams)

        # Save area parameters
        self.areaParams = str(area.getParams())
        PathLog.debug("Area with params: {}".format(area.getParams()))

        # Extract layer sections from area object
        sections = area.makeSections(mode=0, project=False, heights=heights)
        PathLog.debug("sections = %s" % sections)
        shapelist = [sec.getShape() for sec in sections]
        PathLog.debug("shapelist = %s" % shapelist)
        '''

        # Set path parameters
        pathParams['orientation'] = self.orientation
        # if MinTravel is turned on, set path sorting to 3DSort
        # 3DSort shouldn't be used without a valid start point. Can cause
        # tool crash without it.
        #
        # ml: experimental feature, turning off for now (see https://forum.freecadweb.org/viewtopic.php?f=15&t=24422&start=30#p192458)
        # realthunder: I've fixed it with a new sorting algorithm, which I
        # tested fine, but of course need more test. Please let know if there is
        # any problem
        #
        if self.minTravel and self.startPoint:
            pathParams['sort_mode'] = 3
            pathParams['threshold'] = self.toolRadius * 2
        pathParams['shapes'] = [self.workingFace]
        pathParams['feedrate'] = self.horizFeed
        pathParams['feedrate_v'] = self.vertFeed
        pathParams['verbose'] = True
        pathParams['resume_height'] = self.safeHeight
        pathParams['retraction'] = self.clearanceHeight
        pathParams['return_end'] = True
        # Note that emitting preambles between moves breaks some dressups and prevents path optimization on some controllers
        pathParams['preamble'] = False

        if self.keepToolDown:
            pathParams['threshold'] = self.toolDiameter

        if self.endVector is not None:
            pathParams['start'] = self.endVector
        elif self.startPoint:
            pathParams['start'] = self.startPoint

        self.pathParams = str({key: value for key, value in pathParams.items() if key != 'shapes'})
        PathLog.debug("Path with params: {}".format(self.pathParams))

        # Build paths from path parameters
        (pp, end_vector) = Path.fromShapes(**pathParams)
        PathLog.debug('pp: {}, end vector: {}'.format(pp, end_vector))
        self.endVector = end_vector # pylint: disable=attribute-defined-outside-init

        self.commandList = pp.Commands

        # Use modified version of PathGeom.wiresForPath() to extract wires from paths
        wires = []
        startPoint = FreeCAD.Vector(0.0, 0.0, 0.0)
        if self.startPoint:
            startPoint = self.startPoint
        if hasattr(pp, "Commands"):
            edges = []
            for cmd in pp.Commands:
                if cmd.Name in PathGeom.CmdMove:
                    edg = PathGeom.edgeForCmd(cmd, startPoint)
                    if PathGeom.isRoughly(edg.Vertexes[0].Z, edg.Vertexes[1].Z):
                        edges.append(edg)
                    startPoint = PathGeom.commandEndPoint(cmd, startPoint)

                elif cmd.Name in PathGeom.CmdMoveRapid:
                    if len(edges) > 0:
                        wires.append(Part.Wire(edges))
                        edges = []
                    startPoint = PathGeom.commandEndPoint(cmd, startPoint)
            if edges:
                wires.append(Part.Wire(edges))
        return wires

    # Private adaptive support methods
    def _convertTo2d(self, pathArray):
        output = []
        for path in pathArray:
            pth2 = []
            for edge in path:
                for pt in edge:
                    pth2.append([pt[0], pt[1]])
            output.append(pth2)
        return output

    def _discretize(self, edge, flipDirection=False):
        pts = edge.discretize(Deflection=0.0001)
        if flipDirection:
            pts.reverse()

        return pts

    # Public methods
    def setAdaptiveAttributes(self,
                              operationType,
                              cutSide,
                              disableHelixEntry,
                              forceInsideOut,
                              liftDistance,
                              finishingProfile,
                              helixAngle,
                              helixConeAngle,
                              useHelixArcs,
                              helixDiameterLimit,
                              keepToolDownRatio,
                              tolerance,
                              stockObj):
        '''setAdaptiveAttributes(operationType,
                                 cutSide,
                                 disableHelixEntry,
                                 forceInsideOut,
                                 liftDistance,
                                 finishingProfile,
                                 helixAngle,
                                 helixConeAngle,
                                 useHelixArcs,
                                 helixDiameterLimit,
                                 keepToolDownRatio,
                                 tolerance,
                                 stockObj):
        Call to set adaptive-dependent attributes.'''
        # Apply limits to argument values
        if tolerance < 0.001:
            tolerance = 0.001

        if helixAngle < 1.0:
            helixAngle = 1.0
        if helixAngle > 89.0:
            helixAngle = 89.0

        if helixConeAngle < 0.0:
            helixConeAngle = 0.0

        self.operationType = operationType
        self.cutSide = cutSide
        self.disableHelixEntry = disableHelixEntry
        self.forceInsideOut = forceInsideOut
        self.liftDistance = liftDistance
        self.finishingProfile = finishingProfile
        self.helixAngle = helixAngle
        self.helixConeAngle = helixConeAngle
        self.useHelixArcs = useHelixArcs
        self.helixDiameterLimit = helixDiameterLimit
        self.keepToolDownRatio = keepToolDownRatio
        self.tolerance = tolerance
        self.stockObj = stockObj

        if disableHelixEntry:
            self.helixDiameterLimit = 0.01
            self.helixAngle = 89.0

    def execute(self):
        '''execute()...
        Call this method to execute the path generation code in PathGeometryGenerator class.
        Returns True on success.  Access class instance `pathGeometry` attribute for path geometry.
        '''
        PathLog.debug("StrategyClearing.execute()")

        self.commandList = list()  # Reset list
        self.pathGeometry = list()  # Reset list
        self.isCenterSet = False

        # Exit if pattern not available
        if self.cutPattern == 'None':
            return False

        if hasattr(self.workingFace, "Area") and PathGeom.isRoughly(self.workingFace.Area, 0.0):
            PathLog.debug("StrategyClearing: No area in working shape.")
            return False

        self.workingFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - self.workingFace.BoundBox.ZMin))

        #  Apply simple radius shrinking offset for clearing pattern generation.
        ofstVal = self.offsetDirection * (self.toolRadius - (self.jobTolerance / 5.0) + self.materialAllowance)
        offsetWF = PathUtils.getOffsetArea(self.workingFace, ofstVal)
        if offsetWF and len(offsetWF.Faces) > 0:
            for f in offsetWF.Faces:
                self.face = f
                self._prepareConstants()
                pathGeom = self._generatePathGeometry()
                self.pathGeometry.extend(pathGeom)

        PathLog.debug("Path with params: {}".format(self.pathParams))

        return True
# Eclass


class AdaptiveGeometryGenerator:
    """class AdaptiveGeometryGenerator
    Class and implementation of the Adaptive path generation."
    """

    def __init__(self,
                 workingFace,
                 toolDiameter,
                 operationType,
                 cutSide,
                 disableHelixEntry,
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
                 stockObj):
        PathLog.debug("AdaptiveGeometryGenerator.__init__()")

        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        self.adaptiveGeometry = list()
        self.pathArray = list()
        self.commandList = list()

        # Apply limits to argument values
        if tolerance < 0.001:
            tolerance = 0.001

        if helixAngle < 1.0:
            helixAngle = 1.0
        if helixAngle > 89.0:
            helixAngle = 89.0

        if helixConeAngle < 0.0:
            helixConeAngle = 0.0

        self.workingFace = workingFace
        self.toolDiameter = toolDiameter
        self.operationType = operationType
        self.cutSide = cutSide
        self.disableHelixEntry = disableHelixEntry
        self.forceInsideOut = forceInsideOut
        self.materialAllowance = materialAllowance
        self.stepOver = stepOver
        self.liftDistance = liftDistance
        self.finishingProfile = finishingProfile
        self.helixAngle = helixAngle
        self.helixConeAngle = helixConeAngle
        self.useHelixArcs = useHelixArcs
        self.helixDiameterLimit = helixDiameterLimit
        self.keepToolDownRatio = keepToolDownRatio
        self.tolerance = tolerance
        self.stockObj = stockObj

        if disableHelixEntry:
            self.helixDiameterLimit = 0.01
            self.helixAngle = 89.0

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

    def _discretize(self, edge, flipDirection=False):
        pts = edge.discretize(Deflection=0.0001)
        if flipDirection:
            pts.reverse()

        return pts

    # Public methods
    def execute(self):
        PathLog.debug("StrategyAdaptive.execute()")

        PathLog.info("*** Adaptive toolpath processing started...")
        start = time.time()

        self.workingFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - self.workingFace.BoundBox.ZMin))
        for w in self.workingFace.Wires:
            for e in w.Edges:
                self.pathArray.append([self._discretize(e)])

        path2d = self._convertTo2d(self.pathArray)

        stockPaths = []
        if hasattr(self.stockObj, "StockType") and self.stockObj.StockType == "CreateCylinder":
            stockPaths.append([self._discretize(self.stockObj.Shape.Edges[0])])

        else:
            stockBB = self.stockObj.Shape.BoundBox
            v = []
            v.append(FreeCAD.Vector(stockBB.XMin, stockBB.YMin, 0))
            v.append(FreeCAD.Vector(stockBB.XMax, stockBB.YMin, 0))
            v.append(FreeCAD.Vector(stockBB.XMax, stockBB.YMax, 0))
            v.append(FreeCAD.Vector(stockBB.XMin, stockBB.YMax, 0))
            v.append(FreeCAD.Vector(stockBB.XMin, stockBB.YMin, 0))
            stockPaths.append([v])

        stockPath2d = self._convertTo2d(stockPaths)

        opType = area.AdaptiveOperationType.ClearingInside
        if self.operationType == "Clearing":
            if self.cutSide == "Outside":
                opType = area.AdaptiveOperationType.ClearingOutside
            else:
                opType = area.AdaptiveOperationType.ClearingInside
        else:  # profile
            if self.cutSide == "Outside":
                opType = area.AdaptiveOperationType.ProfilingOutside
            else:
                opType = area.AdaptiveOperationType.ProfilingInside

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

        def progressFn(tpaths):
            '''progressFn(tpaths)... progress callback fn, if return true it will stop processing'''
            return False

        # EXECUTE
        try:
            results = a2d.Execute(stockPath2d, path2d, progressFn)
        except Exception as ee:
            FreeCAD.Console.PrintError(str(ee) + "\n")
        else:
            # need to convert results to python object to be JSON serializable
            adaptiveResults = []
            for result in results:
                adaptiveResults.append({
                    "HelixCenterPoint": result.HelixCenterPoint,
                    "StartPoint": result.StartPoint,
                    "AdaptivePaths": result.AdaptivePaths,
                    "ReturnMotionType": result.ReturnMotionType})

            # Generate geometry
            # PathLog.info("Extracting wires from Adaptive data...")
            wires = list()
            motionCutting = area.AdaptiveMotionType.Cutting
            for region in adaptiveResults:
                for pth in region["AdaptivePaths"]:
                    motion = pth[0]  # [0] contains motion type
                    if motion == motionCutting:
                        edges = list()
                        sp = pth[1][0]
                        x = sp[0]
                        y = sp[1]
                        p1 = FreeCAD.Vector(x, y, 0.0)
                        for pt in pth[1][1:]:  # [1] contains list of points
                            xx = pt[0]
                            yy = pt[1]
                            p2 = FreeCAD.Vector(xx, yy, 0.0)
                            if not PathGeom.isRoughly(p1.sub(p2).Length, 0.0):
                                edges.append(Part.makeLine(p1, p2))
                                p1 = p2
                        wires.append(Part.Wire(Part.__sortEdges__(edges)))
            self.adaptiveGeometry = wires
            PathLog.info("*** Done. Elapsed time: %f sec" % (time.time()-start))
            return True

        return False
# Eclass

