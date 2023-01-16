# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2021 Russell Johnson (russ4262) <russ4262@gmail.com>    *
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
import Generators.PathGeometryGenerator as GeometryGenerator

# import strategies.PathStrategySlicing as PathStrategySlicing

# import PathScripts.strategies.PathStrategyRestTools as PathStrategyRestTools
import Path.Geom as PathGeom
import Part

from PySide import QtCore

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader

DraftGeomUtils = LazyLoader("DraftGeomUtils", globals(), "DraftGeomUtils")
PathStrategyAdaptive = LazyLoader(
    "Generators.PathStrategyAdaptive",
    globals(),
    "Generators.PathStrategyAdaptive",
)
TargetBuildUtils = LazyLoader(
    "strategies.PathTargetBuildUtils",
    globals(),
    "strategies.PathTargetBuildUtils",
)


__title__ = "Path Strategy Clearing"
__author__ = "russ4262 (Russell Johnson"
__url__ = "https://www.freecadweb.org"
__doc__ = "Path clearing strategy for 2D and 3D path generation."


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
translate = FreeCAD.Qt.translate


def isSafeTransition(baseFace, start, end, toolDiameter):
    """isSafeTransition(baseFace, start, end, toolDiameter)...
    Make simple circle with diameter of tool, at start point.
    Extrude it latterally along path.
    Extrude it vertically.
    Check for collision with model."""

    # Verify same Z height of points
    if not PathGeom.isRoughly(end.z, start.z):
        return False
    # Verify points not same point
    pathLen = end.sub(start).Length
    if PathGeom.isRoughly(pathLen, 0.0):
        return True

    def getPerp(start, end, dist):
        toEnd = end.sub(start)
        perp = FreeCAD.Vector(-1 * toEnd.y, toEnd.x, 0.0)
        if perp.x == 0 and perp.y == 0:
            return perp
        perp.normalize()
        perp.multiply(dist)
        return perp

    rad = toolDiameter / 2.0  #  + 0.00025  # reduce radius by 25 thousands millimeter

    # Make first cylinder
    ce1 = Part.Wire(Part.makeCircle(rad, start).Edges)
    cylinder1 = Part.Face(ce1)
    cylinder1.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - cylinder1.BoundBox.ZMin))

    # Make second cylinder
    ce2 = Part.Wire(Part.makeCircle(rad, end).Edges)
    cylinder2 = Part.Face(ce2)
    cylinder2.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - cylinder2.BoundBox.ZMin))

    # Make extruded rectangle to connect cylinders
    perp = getPerp(start, end, rad)
    v1 = start.add(perp)
    v2 = start.sub(perp)
    v3 = end.sub(perp)
    v4 = end.add(perp)
    e1 = Part.makeLine(v1, v2)
    e2 = Part.makeLine(v2, v3)
    e3 = Part.makeLine(v3, v4)
    e4 = Part.makeLine(v4, v1)
    edges = Part.__sortEdges__([e1, e2, e3, e4])
    rectFace = Part.Face(Part.Wire(edges))
    rectFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - rectFace.BoundBox.ZMin))

    # Fuse two cylinders and box together
    part1 = cylinder1.fuse(rectFace)
    pathTravel = part1.fuse(cylinder2).removeSplitter()
    contact = pathTravel.common(baseFace)
    # Part.show(baseFace, "baseFace")
    # Part.show(pathTravel, "pathTravel")
    # Part.show(contact, "contact")

    tol = 0.006 * pathLen / toolDiameter
    if PathGeom.isRoughly(contact.Area, pathTravel.Area, tol):
        return True

    # print("\npathTravel.Area: {}".format(pathTravel.Area))
    # print("contact.Area: {}".format(contact.Area))
    # print("path - contact areas: {}".format(pathTravel.Area - contact.Area))

    return False


class StrategyClearVolume_ORIG:
    """StrategyClearVolume()...
    Creates a path geometry shape from an assigned pattern for conversion to tool paths.
    Arguments:
                 callerClass: Reference to calling class - usually a `self` argument upon instantiation.
                 volumeShape: 3D volume shape to be cleared.
                 clearanceHeight: clearance height for paths
                 safeHeight: safe height for paths
                 patternCenterAt: Choice of centering options, including a `Custom` option
                 patternCenterCustom: Custom pattern center point when provided, otherwise, a feedback of calculated pattern center point.
                 cutPatternReversed: Set True to reverse the cut pattern - outside inward, or inside outward.
                 cutPatternAngle: Angle used to rotate certain cut patterns.
                 cutPattern: Choice of cut pattern: Adaptive, Circular, CircularZigZag, Grid, Line, LineOffset, Offset, Spiral, Triangle, ZigZag, ZigZagOffset.
                 cutDirection: Cut direction: Climb or Conventional
                 stepOver: Step over value.
                 materialAllowance: Material allowance, or extra offset.
                 minTravel: Boolean to enable minimum travel (disabled)
                 keepToolDown: Boolean to force keeping tool down.
                 toolController: Reference to active tool controller object.
                 startPoint: Vector start point, or None.
                 depthParams: list of depth parameters, or reference to depthParam object
                 jobTolerance: job tolerance value
    Usage:
        - Call the _generatePathGeometry() method to request the path geometry.
        - The path geometry has correctional linking applied.
    """

    def __init__(
        self,
        callerClass,
        baseObject,
        volumeShape,
        slices,
        depthOffset,
        patternCenterAt,
        patternCenterCustom,
        cutPatternReversed,
        cutPatternAngle,
        cutPattern,
        cutDirection,
        stepOver,
        materialAllowance,
        profileOutside,
        minTravel,
        keepToolDown,
        toolController,
        startPoint,
        depthParams,
        jobTolerance,
    ):
        """__init__(callerClass, baseObject, volumeShape, slices, depthOffset, patternCenterAt,
                    patternCenterCustom, cutPatternReversed, cutPatternAngle,
                    cutPattern, cutDirection, stepOver, materialAllowance, profileOutside,
                    minTravel, keepToolDown, toolController, startPoint, depthParams, jobTolerance)...
        StrategyClearing class constructor method.
        """
        PathLog.debug("StrategyClearing.__init__()")

        # Debugging attributes
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        self.showDebugShapes = False
        self.callerClass = callerClass

        self.safeBaseShape = None
        self.cutPattern = "None"
        self.rawGeoList = None
        self.centerOfMass = None
        self.centerOfPattern = None
        self.halfDiag = None
        self.halfPasses = None
        self.workingPlane = Part.makeCircle(2.0)  # make circle for workplane
        self.rawPathGeometry = None
        self.linkedPathGeom = None
        self.endVectors = []
        self.pathGeometry = []
        self.commandList = []
        self.useStaticCenter = True
        self.isCenterSet = False
        self.offsetDirection = -1.0  # 1.0=outside;  -1.0=inside
        self.endVector = None
        self.pathParams = ""
        self.areaParams = ""
        self.simObj = None
        self.transitionClearance = 2.0  # millimeters
        self.baseShape = None
        self.layerDepth = 0.0
        self.startCommands = []
        self.useOCL = False

        # Save argument values to class instance
        self.baseObject = baseObject
        self.volumeShape = volumeShape
        self.depthOffset = depthOffset
        self.patternCenterAt = patternCenterAt
        self.patternCenterCustom = patternCenterCustom
        self.cutPattern = cutPattern
        self.cutPatternReversed = cutPatternReversed
        self.cutPatternAngle = cutPatternAngle
        self.cutDirection = cutDirection
        self.stepOver = stepOver
        self.materialAllowance = materialAllowance
        self.profileOutside = profileOutside
        self.minTravel = minTravel
        self.keepToolDown = keepToolDown
        self.toolController = toolController
        self.jobTolerance = jobTolerance
        self.startPoint = startPoint
        self.depthParams = depthParams
        self.slices = slices

        self.clearanceHeight = depthParams.clearance_height
        self.safeHeight = depthParams.safe_height
        self.prevDepth = depthParams.safe_height
        self.startDepth = depthParams.start_depth
        self.finalDepth = depthParams.final_depth
        self.stepDown = depthParams.step_down
        self.finishDepth = depthParams.z_finish_depth

        self.vertFeed = toolController.VertFeed.Value
        self.vertRapid = toolController.VertRapid.Value
        self.horizFeed = toolController.HorizFeed.Value
        self.horizRapid = toolController.HorizRapid.Value
        self.toolDiameter = (
            toolController.Tool.Diameter.Value
            if hasattr(toolController.Tool.Diameter, "Value")
            else float(toolController.Tool.Diameter)
        )
        self.toolRadius = self.toolDiameter / 2.0
        self.cutOut = self.toolDiameter * (self.stepOver / 100.0)
        # Setting toolDownThreshold below effective cut out (stepover * tool diameter) will keep tool down between transitions
        self.toolDownThreshold = self.toolDiameter * 1.5

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
        self.stockObj = None
        self.viewObject = None

    def _debugMsg(self, msg, isError=False):
        """_debugMsg(msg)
        If `self.isDebug` flag is True, the provided message is printed in the Report View.
        If not, then the message is assigned a debug status.
        """
        if isError:
            FreeCAD.Console.PrintError("StrategyClearVolume: " + msg + "\n")
            return

        if self.isDebug:
            # PathLog.info(msg)
            FreeCAD.Console.PrintMessage("StrategyClearVolume: " + msg + "\n")
        else:
            PathLog.debug(msg)

    def _addDebugObject(self, objShape, objName="shape"):
        """_addDebugObject(objShape, objName='shape')
        If `self.isDebug` and `self.showDebugShapes` flags are True, the provided
        debug shape will be added to the active document with the provided name.
        """
        if self.isDebug and self.showDebugShapes:
            O = FreeCAD.ActiveDocument.addObject("Part::Feature", "debug_" + objName)
            O.Shape = objShape
            O.purgeTouched()

    def _getPathGeometry(self, face):
        """_getPathGeometry(face)... Simple switch controller for obtaining the path geometry."""

        if not self.baseShape:
            self._debugMsg("_getPathGeometry() No baseShape")
            return []

        pGG = GeometryGenerator.PathGeometryGenerator(
            self,
            face,
            self.patternCenterAt,
            self.patternCenterCustom,
            self.cutPatternReversed,
            self.cutPatternAngle,
            self.cutPattern,
            self.cutDirection,
            self.stepOver,
            self.materialAllowance,
            self.profileOutside,
            self.minTravel,
            self.keepToolDown,
            self.toolController,
            self.jobTolerance,
        )
        pGG.baseShape = self.baseShape
        pGG.targetFaceHeight = self.layerDepth

        if self.cutPattern == "Adaptive":
            pGG.setAdaptiveAttributes(
                self.operationType,
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
                self.stockObj,
            )

        pGG.useStaticCenter = self.useStaticCenter
        pGG.isDebug = self.isDebug  # Pass isDebug flag

        if pGG.execute():
            self.centerOfPattern = pGG.centerOfPattern  # Retreive center of cut pattern
            return pGG.pathGeometry

        return []

    def _hopPath(self, upHeight, trgtX, trgtY, downHeight):
        paths = []
        prevDepth = self.prevDepth + 0.5  # 1/2 mm buffer
        paths.append(
            Path.Command("G0", {"Z": upHeight, "F": self.vertRapid})
        )  # Rapid retraction
        paths.append(
            Path.Command("G0", {"X": trgtX, "Y": trgtY, "F": self.horizRapid})
        )  # Rapid lateral move
        if (
            self.useStaticCenter
            and upHeight > prevDepth
            and upHeight <= self.safeHeight
        ):
            paths.append(Path.Command("G0", {"Z": prevDepth, "F": self.vertRapid}))
        paths.append(
            Path.Command("G1", {"Z": downHeight, "F": self.vertFeed})
        )  # Plunge at vertical feed rate
        return paths

    def _buildStartPath(self):
        """_buildStartPath() ... Convert Offset pattern wires to paths."""
        self._debugMsg("_buildStartPath()")

        if len(self.startCommands) > 0:
            return

        useStart = False
        if self.startPoint:
            useStart = True

        paths = [Path.Command("G0", {"Z": self.clearanceHeight, "F": self.vertRapid})]
        if useStart:
            paths.append(
                Path.Command(
                    "G0",
                    {
                        "X": self.startPoint.x,
                        "Y": self.startPoint.y,
                        "F": self.horizRapid,
                    },
                )
            )

        self.startCommands = paths

    # Pattern-specific gcode production methods
    def _buildPaths(self, height, wireList):
        """_buildPaths(height, wireList) ... Method to convert wires into paths."""
        self._debugMsg("_buildPaths()")

        if self.cutPattern == "Offset":
            return self._buildOffsetPaths(height, wireList)

        if self.cutPattern == "Profile":
            return self._buildOffsetPaths(height, wireList)

        if self.cutPattern == "MultiProfile":
            return self._buildOffsetPaths(height, wireList)

        if self.cutPattern == "Spiral":
            return self._buildSpiralPaths(height, wireList)

        if self.cutPattern in ["Line", "LineOffset"]:
            return self._buildLinePaths(height, wireList)

        if self.cutPattern in ["ZigZag", "ZigZagOffset", "CircularZigZag"]:
            return self._buildZigZagPaths(height, wireList)

        paths = []
        end_vector = None  # FreeCAD.Vector(0.0, 0.0, self.clearanceHeight)
        useStart = False
        if self.startPoint:
            useStart = True

        pathParams = {}  # pylint: disable=assignment-from-no-return
        pathParams["feedrate"] = self.horizFeed
        pathParams["feedrate_v"] = self.vertFeed
        pathParams["verbose"] = True
        pathParams["return_end"] = False  # True to return end vector
        pathParams["resume_height"] = self.safeHeight
        pathParams["retraction"] = self.clearanceHeight
        pathParams[
            "preamble"
        ] = False  # Eemitting preambles between moves breaks some dressups and prevents path optimization on some controllers

        # More work is needed on this feature before implementation
        # if self.keepToolDown:
        #    pathParams['threshold'] = self.toolDiameter * 1.001

        for w in wireList:
            wire = w.copy()
            wire.translate(FreeCAD.Vector(0, 0, height))

            pathParams["shapes"] = [wire]

            vrtxs = wire.Vertexes
            if useStart:
                pathParams["start"] = FreeCAD.Vector(
                    self.startPoint.x, self.startPoint.y, self.safeHeight
                )
                useStart = False
            else:
                pathParams["start"] = FreeCAD.Vector(vrtxs[0].X, vrtxs[0].Y, vrtxs[0].Z)

            # (pp, end_vector) = Path.fromShapes(**pathParams)
            pp = Path.fromShapes(**pathParams)
            paths.extend(pp.Commands)

        self.pathParams = str(
            {key: value for key, value in pathParams.items() if key != "shapes"}
        )
        self.endVectors.append(end_vector)

        # self._debugMsg("Path with params: {} at height: {}".format(self.pathParams, height))

        return paths

    def _buildGridAndTrianglePaths(self, getsim=False):
        """_buildGridAndTrianglePaths(getsim=False) ... Generate paths for Grid and Triangle patterns."""
        PathLog.track()
        areaParams = {}
        pathParams = {}
        heights = [i for i in self.depthParams]
        self._debugMsg("depths: {}".format(heights))

        if self.cutPattern == "Triangle":
            self.pocketMode = 7
        if self.cutDirection == "Climb":
            self.orientation = 1

        areaParams["Fill"] = 0
        areaParams["Coplanar"] = 0
        areaParams["PocketMode"] = 1
        areaParams["SectionCount"] = -1
        areaParams["Angle"] = self.cutPatternAngle
        areaParams["FromCenter"] = not self.cutPatternReversed
        areaParams["PocketStepover"] = (self.toolRadius * 2) * (
            float(self.stepOver) / 100
        )
        # areaParams["PocketExtraOffset"] = self.materialAllowance
        areaParams["ToolRadius"] = self.toolRadius
        # Path.Area() pattern list is ['None', 'ZigZag', 'Offset', 'Spiral', 'ZigZagOffset', 'Line', 'Grid', 'Triangle']
        areaParams[
            "PocketMode"
        ] = (
            self.pocketMode
        )  # should be a 6 or 7 to indicate the index for 'Grid' or 'Triangle'

        pathArea = Path.Area()
        pathArea.setPlane(PathUtils.makeWorkplane(Part.makeCircle(5.0)))
        pathArea.add(self.volumeShape)
        pathArea.setParams(**areaParams)

        # Save pathArea parameters
        self.areaParams = str(pathArea.getParams())
        self._debugMsg("Area with params: {}".format(pathArea.getParams()))

        # Extract layer sections from pathArea object
        sections = pathArea.makeSections(mode=0, project=False, heights=heights)
        self._debugMsg("sections = %s" % sections)
        shapelist = [sec.getShape() for sec in sections]
        self._debugMsg("shapelist = %s" % shapelist)

        # Set path parameters
        pathParams["orientation"] = self.orientation
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
            pathParams["sort_mode"] = 3
            pathParams["threshold"] = self.toolRadius * 2
        pathParams["shapes"] = shapelist
        pathParams["feedrate"] = self.horizFeed
        pathParams["feedrate_v"] = self.vertFeed
        pathParams["verbose"] = True
        pathParams["resume_height"] = self.safeHeight
        pathParams["retraction"] = self.clearanceHeight
        pathParams["return_end"] = True
        # Note that emitting preambles between moves breaks some dressups and prevents path optimization on some controllers
        pathParams["preamble"] = False

        if self.keepToolDown:
            pathParams["threshold"] = self.toolDiameter

        if self.endVector is not None:
            pathParams["start"] = self.endVector
        elif self.startPoint:
            pathParams["start"] = self.startPoint

        self.pathParams = str(
            {key: value for key, value in pathParams.items() if key != "shapes"}
        )
        self._debugMsg("Path with params: {}".format(self.pathParams))

        # Build paths from path parameters
        (pp, end_vector) = Path.fromShapes(**pathParams)
        self._debugMsg("pp: {}, end vector: {}".format(pp, end_vector))
        self.endVector = end_vector  # pylint: disable=attribute-defined-outside-init

        simobj = None
        """
        if getsim:
            areaParams["Thicken"] = True
            areaParams["ToolRadius"] = self.toolRadius - self.toolRadius * 0.005
            pathArea.setParams(**areaParams)
            sec = pathArea.makeSections(mode=0, project=False, heights=heights)[
                -1
            ].getShape()
            simobj = sec.extrude(FreeCAD.Vector(0, 0, self.volumeShape.BoundBox.ZMax))
        """
        self.commandList = pp.Commands
        self.simObj = simobj

    def _buildOffsetPaths(self, height, wireList):
        """_buildOffsetPaths(height, wireList) ... Convert Offset pattern wires to paths."""
        self._debugMsg("_buildOffsetPaths()")

        if self.keepToolDown:
            return self._buildKeepOffsetDownPaths(height, wireList)

        paths = []
        self._buildStartPath()

        if self.cutDirection == "Climb":
            for w in wireList:
                wire = w.copy()
                wire.translate(FreeCAD.Vector(0, 0, height))

                e0 = wire.Edges[len(wire.Edges) - 1]
                paths.append(
                    Path.Command(
                        "G0",
                        {
                            "X": e0.Vertexes[1].X,
                            "Y": e0.Vertexes[1].Y,
                            "F": self.horizRapid,
                        },
                    )
                )
                paths.append(
                    Path.Command("G0", {"Z": self.prevDepth + 0.1, "F": self.vertRapid})
                )
                paths.append(Path.Command("G1", {"Z": height, "F": self.vertFeed}))

                for i in range(len(wire.Edges) - 1, -1, -1):
                    e = wire.Edges[i]
                    paths.extend(
                        PathGeom.cmdsForEdge(e, flip=True, hSpeed=self.horizFeed)
                    )

                paths.append(
                    Path.Command("G0", {"Z": self.safeHeight, "F": self.vertRapid})
                )

        else:
            for w in wireList:
                wire = w.copy()
                wire.translate(FreeCAD.Vector(0, 0, height))

                e0 = wire.Edges[0]
                paths.append(
                    Path.Command(
                        "G0",
                        {
                            "X": e0.Vertexes[0].X,
                            "Y": e0.Vertexes[0].Y,
                            "F": self.horizRapid,
                        },
                    )
                )
                paths.append(
                    Path.Command("G0", {"Z": self.prevDepth + 0.1, "F": self.vertRapid})
                )
                paths.append(Path.Command("G1", {"Z": height, "F": self.vertFeed}))

                for e in wire.Edges:
                    paths.extend(PathGeom.cmdsForEdge(e, hSpeed=self.horizFeed))

                paths.append(
                    Path.Command("G0", {"Z": self.safeHeight, "F": self.vertRapid})
                )

        return paths

    def _buildProfilePaths(self, height, wireList):
        """_buildProfilePaths(height, wireList) ... Convert Offset pattern wires to paths."""
        self._debugMsg("_buildProfilePaths()")

        if self.keepToolDown:
            # return self._buildKeepOffsetDownPaths(height, wireList)
            self._debugMsg("_buildProfilePaths()", isError=True)

        paths = []
        self._buildStartPath()

        if self.cutDirection == "Climb":
            for w in wireList:
                wire = w.copy()
                wire.translate(FreeCAD.Vector(0, 0, height))

                e0 = wire.Edges[len(wire.Edges) - 1]
                paths.append(
                    Path.Command(
                        "G0",
                        {
                            "X": e0.Vertexes[1].X,
                            "Y": e0.Vertexes[1].Y,
                            "F": self.horizRapid,
                        },
                    )
                )
                paths.append(
                    Path.Command("G0", {"Z": self.prevDepth + 0.1, "F": self.vertRapid})
                )
                paths.append(Path.Command("G1", {"Z": height, "F": self.vertFeed}))

                for i in range(len(wire.Edges) - 1, -1, -1):
                    e = wire.Edges[i]
                    paths.extend(
                        PathGeom.cmdsForEdge(e, flip=True, hSpeed=self.horizFeed)
                    )

                paths.append(
                    Path.Command("G0", {"Z": self.safeHeight, "F": self.vertRapid})
                )

        else:
            for w in wireList:
                wire = w.copy()
                wire.translate(FreeCAD.Vector(0, 0, height))

                e0 = wire.Edges[0]
                paths.append(
                    Path.Command(
                        "G0",
                        {
                            "X": e0.Vertexes[0].X,
                            "Y": e0.Vertexes[0].Y,
                            "F": self.horizRapid,
                        },
                    )
                )
                paths.append(
                    Path.Command("G0", {"Z": self.prevDepth + 0.1, "F": self.vertRapid})
                )
                paths.append(Path.Command("G1", {"Z": height, "F": self.vertFeed}))

                for e in wire.Edges:
                    paths.extend(PathGeom.cmdsForEdge(e, hSpeed=self.horizFeed))

                paths.append(
                    Path.Command("G0", {"Z": self.safeHeight, "F": self.vertRapid})
                )

        return paths

    def _buildKeepOffsetDownPaths(self, height, wireList):
        """_buildKeepOffsetDownPaths(height, wireList) ... Convert Offset pattern wires to paths."""
        self._debugMsg("_buildKeepOffsetDownPaths()")

        paths = []
        self._buildStartPath()

        lastPnt = None
        if self.cutDirection == "Climb":
            for w in wireList:
                wire = w.copy()
                wire.translate(FreeCAD.Vector(0, 0, height))
                e0 = wire.Edges[len(wire.Edges) - 1]
                pnt0 = e0.Vertexes[1].Point

                if lastPnt:
                    isKeepDownSafe = isSafeTransition(
                        self.safeBaseShape, lastPnt, pnt0, self.toolDiameter
                    )
                    # self._debugMsg("isKeepDownSafe: {}".format(isKeepDownSafe))
                    if isKeepDownSafe:
                        if pnt0.sub(lastPnt).Length > self.toolDownThreshold:
                            paths.extend(
                                self._hopPath(
                                    self.safeHeight,
                                    e0.Vertexes[1].X,
                                    e0.Vertexes[1].Y,
                                    height,
                                )
                            )
                        else:
                            paths.append(
                                Path.Command(
                                    "G1",
                                    {
                                        "X": e0.Vertexes[1].X,
                                        "Y": e0.Vertexes[1].Y,
                                        "F": self.horizFeed,
                                    },
                                )
                            )
                    else:
                        paths.extend(
                            self._hopPath(
                                self.safeHeight,
                                e0.Vertexes[1].X,
                                e0.Vertexes[1].Y,
                                height,
                            )
                        )
                else:
                    paths.append(
                        Path.Command(
                            "G0",
                            {
                                "X": e0.Vertexes[1].X,
                                "Y": e0.Vertexes[1].Y,
                                "F": self.horizRapid,
                            },
                        )
                    )
                    paths.append(
                        Path.Command(
                            "G0", {"Z": self.prevDepth + 0.1, "F": self.vertRapid}
                        )
                    )
                    paths.append(Path.Command("G1", {"Z": height, "F": self.vertFeed}))

                for i in range(len(wire.Edges) - 1, -1, -1):
                    e = wire.Edges[i]
                    paths.extend(
                        PathGeom.cmdsForEdge(e, flip=True, hSpeed=self.horizFeed)
                    )

                # Save last point
                lastPnt = wire.Edges[0].Vertexes[0].Point

        else:
            for w in wireList:
                wire = w.copy()
                wire.translate(FreeCAD.Vector(0, 0, height))
                eCnt = len(wire.Edges)
                e0 = wire.Edges[0]
                pnt0 = e0.Vertexes[0].Point

                if lastPnt:
                    isKeepDownSafe = isSafeTransition(
                        self.safeBaseShape, lastPnt, pnt0, self.toolDiameter
                    )
                    # self._debugMsg("isKeepDownSafe: {}".format(isKeepDownSafe))
                    if isKeepDownSafe:
                        if pnt0.sub(lastPnt).Length > self.toolDownThreshold:
                            paths.extend(
                                self._hopPath(
                                    self.safeHeight,
                                    e0.Vertexes[0].X,
                                    e0.Vertexes[0].Y,
                                    height,
                                )
                            )
                        else:
                            paths.append(
                                Path.Command(
                                    "G1",
                                    {
                                        "X": e0.Vertexes[0].X,
                                        "Y": e0.Vertexes[0].Y,
                                        "F": self.horizRapid,
                                    },
                                )
                            )
                    else:
                        paths.extend(
                            self._hopPath(
                                self.safeHeight,
                                e0.Vertexes[0].X,
                                e0.Vertexes[0].Y,
                                height,
                            )
                        )

                else:
                    paths.append(
                        Path.Command(
                            "G0",
                            {
                                "X": e0.Vertexes[0].X,
                                "Y": e0.Vertexes[0].Y,
                                "F": self.horizRapid,
                            },
                        )
                    )
                    paths.append(
                        Path.Command(
                            "G0", {"Z": self.prevDepth + 0.1, "F": self.vertRapid}
                        )
                    )
                    paths.append(Path.Command("G1", {"Z": height, "F": self.vertFeed}))

                for i in range(0, eCnt):
                    paths.extend(
                        PathGeom.cmdsForEdge(wire.Edges[i], hSpeed=self.horizFeed)
                    )

                # Save last point
                lastEdgeVertexes = wire.Edges[eCnt - 1].Vertexes
                lastPnt = lastEdgeVertexes[len(lastEdgeVertexes) - 1].Point
        # Eif

        return paths

    def _buildLinePaths(self, height, wireList):
        """_buildLinePaths(height, wireList) ... Convert Line-based wires to paths."""
        self._debugMsg("_buildLinePaths()")

        paths = []
        self._buildStartPath()

        for w in wireList:
            wire = w.copy()
            wire.translate(FreeCAD.Vector(0, 0, height))

            e0 = wire.Edges[0]
            paths.append(
                Path.Command(
                    "G0",
                    {
                        "X": e0.Vertexes[0].X,
                        "Y": e0.Vertexes[0].Y,
                        "F": self.horizRapid,
                    },
                )
            )
            paths.append(
                Path.Command("G0", {"Z": self.prevDepth + 0.1, "F": self.vertRapid})
            )
            paths.append(Path.Command("G1", {"Z": height, "F": self.vertFeed}))

            for e in wire.Edges:
                paths.extend(PathGeom.cmdsForEdge(e, hSpeed=self.horizFeed))

            paths.append(
                Path.Command("G0", {"Z": self.safeHeight, "F": self.vertRapid})
            )

        self._debugMsg("_buildLinePaths() path count: {}".format(len(paths)))
        return paths

    def _buildZigZagPaths(self, height, wireList):
        """_buildZigZagPaths(height, wireList) ... Convert ZigZab-based wires to paths.
        With KeepToolDown, the assumption is that material above clearing area where transitions cross part are cleared to that depth."""
        self._debugMsg("_buildZigZagPaths()")

        if not self.keepToolDown:
            return self._buildLinePaths(height, wireList)

        # Proceed with KeepToolDown proceedure
        paths = []
        self._buildStartPath()

        lastPnt = None
        for w in wireList:
            wire = w.copy()
            wire.translate(FreeCAD.Vector(0, 0, height))
            eCnt = len(wire.Edges)
            e0 = wire.Edges[0]
            pnt0 = e0.Vertexes[0].Point

            if lastPnt:
                isKeepDownSafe = isSafeTransition(
                    self.safeBaseShape, lastPnt, pnt0, self.toolDiameter
                )
                # self._debugMsg("isKeepDownSafe: {}".format(isKeepDownSafe))
                if isKeepDownSafe:
                    paths.append(
                        Path.Command(
                            "G1",
                            {
                                "X": e0.Vertexes[0].X,
                                "Y": e0.Vertexes[0].Y,
                                "F": self.horizFeed,
                            },
                        )
                    )
                else:
                    paths.extend(
                        self._hopPath(
                            self.safeHeight, e0.Vertexes[0].X, e0.Vertexes[0].Y, height
                        )
                    )
            else:
                paths.append(
                    Path.Command(
                        "G0",
                        {
                            "X": e0.Vertexes[0].X,
                            "Y": e0.Vertexes[0].Y,
                            "F": self.horizRapid,
                        },
                    )
                )
                paths.append(
                    Path.Command("G0", {"Z": self.prevDepth + 0.1, "F": self.vertRapid})
                )
                paths.append(Path.Command("G1", {"Z": height, "F": self.vertFeed}))

            for i in range(0, eCnt):
                paths.extend(PathGeom.cmdsForEdge(wire.Edges[i], hSpeed=self.horizFeed))

            # Save last point
            lastEdgeVertexes = wire.Edges[eCnt - 1].Vertexes
            lastPnt = lastEdgeVertexes[len(lastEdgeVertexes) - 1].Point
        # Efor

        self._debugMsg("_buildZigZagPaths() path count: {}".format(len(paths)))

        return paths

    def _buildSpiralPaths(self, height, wireList):
        """_buildSpiralPaths(height, wireList) ... Convert Spiral wires to paths."""
        self._debugMsg("_buildSpiralPaths()")

        paths = []
        self._buildStartPath()

        wIdx = 0
        for w in wireList:
            wire = w.copy()
            wire.translate(FreeCAD.Vector(0, 0, height))

            e0 = wire.Edges[0]
            paths.append(
                Path.Command(
                    "G0",
                    {
                        "X": e0.Vertexes[0].X,
                        "Y": e0.Vertexes[0].Y,
                        "F": self.horizRapid,
                    },
                )
            )
            paths.append(
                Path.Command("G0", {"Z": self.prevDepth + 0.1, "F": self.vertRapid})
            )
            paths.append(Path.Command("G1", {"Z": height, "F": self.vertFeed}))

            for e in wire.Edges:
                paths.append(
                    Path.Command(
                        "G1",
                        {
                            "X": e.Vertexes[1].X,
                            "Y": e.Vertexes[1].Y,
                            "F": self.horizFeed,
                        },
                    )
                )

            paths.append(
                Path.Command("G0", {"Z": self.safeHeight, "F": self.vertRapid})
            )
            wIdx += 1

        return paths

    def _getAdaptivePaths(self):
        """_getAdaptivePaths()... Proxy method for generating Adaptive paths"""
        commandList = []
        # Execute the Adaptive code to generate path data

        # Slice each solid at requested depth and apply Adaptive pattern to each layer
        success = False
        depIdx = 0
        startDep = self.startDepth
        for dep in self.depthParams:
            finalDep = dep
            # Slice the solid at depth
            face = TargetBuildUtils.getCrossSectionOfSolid(self.volumeShape, dep)
            if face:
                faces = face.Faces

                # Execute the Adaptive code to generate path data
                strategy = PathStrategyAdaptive.StrategyAdaptive(
                    faces,
                    self.toolController,
                    self.depthParams,
                    startDep,
                    finalDep,
                    self.operationType,
                    self.cutSide,
                    self.forceInsideOut,
                    self.materialAllowance,
                    self.stepOver,
                    self.liftDistance,
                    self.finishingProfile,
                    self.helixAngle,
                    self.helixConeAngle,
                    self.useHelixArcs,
                    self.helixDiameterLimit,
                    self.keepToolDownRatio,
                    self.tolerance,
                    self.stopped,
                    self.stopProcessing,
                    self.stockObj,
                    self.job,
                    self.adaptiveOutputState,
                    self.adaptiveInputState,
                    self.viewObject,
                )
                strategy.isDebug = self.isDebug  # Transfer debug status
                if self.disableHelixEntry:
                    strategy.disableHelixEntry()
                strategy.generateGeometry = False  # Set True to make geometry list available in `adaptiveGeometry` attribute
                strategy.generateCommands = (
                    True  # Set False to disable path command generation
                )

                try:
                    # Generate the path commands
                    rtn = strategy.execute()
                except Exception as e:  # pylint: disable=broad-except
                    FreeCAD.Console.PrintError(str(e) + "\n")
                    PathLog.error(
                        "Something unexpected happened. Check project and tool config. 3\n"
                    )
                else:
                    # Save path commands to operation command list
                    commandList.extend(strategy.commandList)
                    success = True

            else:
                self._debugMsg("No cross-sectional faces at {} mm.".format(dep))
                if success:
                    break
            depIdx += 1
            startDep = dep
        # Efor
        self.commandList = commandList

    # OCL build path methods
    def _buildPathsOCL(self, height, wireList):
        """_buildPaths(height, wireList) ... Method to convert wires into paths."""
        self._debugMsg("_buildPaths()")

        if self.cutPattern == "Offset":
            return self._buildOffsetPaths(height, wireList)

        if self.cutPattern == "Spiral":
            return self._buildSpiralPaths(height, wireList)

        if self.cutPattern in ["Line", "LineOffset"]:
            return self._buildLinePaths(height, wireList)

        if self.cutPattern in ["ZigZag", "ZigZagOffset", "CircularZigZag"]:
            return self._buildZigZagPaths(height, wireList)

        paths = []
        end_vector = None  # FreeCAD.Vector(0.0, 0.0, self.clearanceHeight)
        useStart = False
        if self.startPoint:
            useStart = True

        pathParams = {}  # pylint: disable=assignment-from-no-return
        pathParams["feedrate"] = self.horizFeed
        pathParams["feedrate_v"] = self.vertFeed
        pathParams["verbose"] = True
        pathParams["return_end"] = False  # True to return end vector
        pathParams["resume_height"] = self.safeHeight
        pathParams["retraction"] = self.clearanceHeight
        pathParams[
            "preamble"
        ] = False  # Eemitting preambles between moves breaks some dressups and prevents path optimization on some controllers

        # More work is needed on this feature before implementation
        # if self.keepToolDown:
        #    pathParams['threshold'] = self.toolDiameter * 1.001

        for w in wireList:
            wire = w.copy()
            wire.translate(FreeCAD.Vector(0, 0, height))

            pathParams["shapes"] = [wire]

            vrtxs = wire.Vertexes
            if useStart:
                pathParams["start"] = FreeCAD.Vector(
                    self.startPoint.x, self.startPoint.y, self.safeHeight
                )
                useStart = False
            else:
                pathParams["start"] = FreeCAD.Vector(vrtxs[0].X, vrtxs[0].Y, vrtxs[0].Z)

            # (pp, end_vector) = Path.fromShapes(**pathParams)
            pp = Path.fromShapes(**pathParams)
            paths.extend(pp.Commands)

        self.pathParams = str(
            {key: value for key, value in pathParams.items() if key != "shapes"}
        )
        self.endVectors.append(end_vector)

        # self._debugMsg("Path with params: {} at height: {}".format(self.pathParams, height))

        return paths

    def _oclScanEdges(self, ocl, pathGeom):
        pointLists = []

        def lineToPoints(ocl, edge):
            p0 = edge.Vertexes[0].Point
            p1 = edge.Vertexes[1].Point
            start = (p0.x, p0.y)
            end = (p1.x, p1.y)
            return ocl.linearDropCut(start, end)

        def arcToPoints(ocl, edge):
            cMode = DraftGeomUtils.isClockwise(edge)
            if len(edge.Vertexes) == 1:
                # complete circle
                p0 = edge.Vertexes[0].Point
                c = edge.Curve.Center
                radVect = c.sub(p0)
                p1 = c.add(radVect)
                start = (p0.x, p0.y)
                end = (p1.x, p1.y)
                cent = (c.x, c.y)
                pntList = ocl.circularDropCut((start, end, cent), cMode)
                pntList.extend(ocl.circularDropCut((end, start, cent), cMode))
                first = pntList[0]
                pntList.append(FreeCAD.Vector(first.x, first.y, first.z))
                return pntList
            else:
                p0 = edge.Vertexes[0].Point
                p1 = edge.Vertexes[1].Point
                c = edge.Curve.Center
                start = (p0.x, p0.y)
                end = (p1.x, p1.y)
                cent = (c.x, c.y)
                return ocl.circularDropCut((start, end, cent), cMode)

        # Convert path geometry to drop cut points
        for wire in pathGeom:
            for edge in wire.Edges:
                if edge.Curve.TypeId.endswith("GeomCircle"):
                    pointLists.append(arcToPoints(ocl, edge))
                else:
                    pointLists.append(lineToPoints(ocl, edge))
            pointLists.append("Break")  # Use empty list as break marker

        return pointLists

    def _limitPointsToDepth(self, pointLists, prevDepth, curDepth):
        points = []
        lastItms = None

        # Convert points to gcode
        for itm in pointLists:
            if isinstance(itm, str):  # process break
                if lastItms:
                    points.append(itm)
            else:  # process points
                itms = []
                cutting = False
                for pnt in itm:
                    z = pnt.z
                    if z < prevDepth:
                        cutting = True
                        if z < curDepth:
                            itms.append(FreeCAD.Vector(pnt.x, pnt.y, curDepth))
                        else:
                            itms.append(FreeCAD.Vector(pnt.x, pnt.y, z))
                    else:
                        if cutting:
                            if itms:
                                points.append(itms)
                                points.append("Skip")
                                itms = []
                            cutting = False

                if itms:
                    points.append(itms)
                lastItms = itms

        return points

    def _refinePointsList(self, pointLists, tolerance=1e-4):
        points = []

        if self.cutPattern in [
            "Circular",
            "CircularZigZag",
            "Spiral",
            "Adaptive",
            "Offset",
        ]:
            return pointLists

        # Convert points to gcode
        for itm in pointLists:
            if isinstance(itm, str):  # process break
                points.append(itm)
            else:  # process points
                pnts = []
                tracking = False
                itmCnt = len(itm)

                if itmCnt < 3:
                    points.append(itm)
                    continue

                prev = itm.pop(0)
                pnts.append(prev)  # save first point in list
                itmCnt -= 1
                cur = itm[0]

                for i in range(1, itmCnt):
                    nxt = itm[i]
                    # Check linear deflection
                    deflection = cur.distanceToLineSegment(prev, nxt).Length
                    if deflection > tolerance:
                        pnts.append(cur)  # save current point
                        prev = cur  # move cur to prev
                        tracking = False
                    else:
                        tracking = True

                    cur = nxt
                # Efor

                if tracking:
                    pnts.append(cur)

                points.append(pnts)

        return points

    def _convertCurvedOclPointLists(self, pointLists):
        """Cut patterns with this method are expected to be non-linear,
        so this method does not run a collinear check between points."""
        paths = []
        # self._buildStartPath()
        prev = None
        edgeGroups = []

        def addPath(prev, cur, paths):
            paths.append(
                Path.Command(
                    "G1",
                    {
                        "X": cur.x,
                        "Y": cur.y,
                        "Z": cur.z,
                        "F": PathGeom.speedBetweenPoints(
                            prev, cur, self.horizFeed, self.vertFeed
                        ),
                    },
                )
            )

        def addEdge(prev, cur, edges):
            edges.append(Part.makeLine(prev, cur))

        # Convert points to gcode
        for itm in pointLists:
            edges = []
            if isinstance(itm, str):  # process break
                paths.append(
                    # Retract to clearance height
                    Path.Command(
                        "G0",
                        {"Z": self.clearanceHeight, "F": self.vertRapid},
                    ),
                )
            else:  # process points
                lenItm = len(itm)
                if lenItm == 0:
                    continue

                # Convert first point to gcode
                prev = itm[0]
                # Rapid to (x, y) of next point, then feed to depth
                paths.extend(
                    [
                        Path.Command(
                            "G0",
                            {"X": prev.x, "Y": prev.y, "F": self.horizRapid},
                        ),
                        Path.Command(
                            "G1",
                            # {"X": prev.x, "Y": prev.y, "Z": prev.z, "F": self.vertFeed},
                            {"Z": prev.z, "F": self.vertFeed},
                        ),
                    ]
                )

                # Convert second point to gcode
                if lenItm > 1:
                    cur = itm[1]
                    addPath(prev, cur, paths)
                    addEdge(prev, cur, edges)

                    if lenItm > 2:
                        for nxt in itm:
                            # cycle points
                            prev = cur
                            cur = nxt
                            addPath(prev, cur, paths)
                            addEdge(prev, cur, edges)
            # Eif
            edgeGroups.append(edges)
        # Efor

        wires = [Part.Wire(g) for g in edgeGroups if g]

        return paths, wires

    def _convertOclPointLists(self, pointLists):
        paths = []
        # self._buildStartPath()
        prev = None
        edgeGroups = []

        def addPath(prev, cur, paths):
            paths.append(
                Path.Command(
                    "G1",
                    {
                        "X": cur.x,
                        "Y": cur.y,
                        "Z": cur.z,
                        "F": PathGeom.speedBetweenPoints(
                            prev, cur, self.horizFeed, self.vertFeed
                        ),
                    },
                )
            )

        def addEdge(prev, cur, edges):
            edges.append(Part.makeLine(prev, cur))

        # Convert points to gcode
        for itm in pointLists:
            edges = []
            if isinstance(itm, str):  # process break
                paths.append(
                    # Retract to clearance height
                    Path.Command(
                        "G0",
                        {"Z": self.clearanceHeight, "F": self.vertRapid},
                    ),
                )
            else:  # process points
                lenItm = len(itm)
                if lenItm == 0:
                    continue

                # Convert first point to gcode
                prev = itm[0]
                # Rapid to (x, y) of first point, then feed to depth
                paths.extend(
                    [
                        Path.Command(
                            "G0",
                            {"X": prev.x, "Y": prev.y, "F": self.horizRapid},
                        ),
                        Path.Command(
                            "G1",
                            # {"X": prev.x, "Y": prev.y, "Z": prev.z, "F": self.vertFeed},
                            {"Z": prev.z, "F": self.vertFeed},
                        ),
                    ]
                )

                # Convert second point to gcode
                if lenItm > 1:
                    cur = itm[1]

                    if lenItm > 2:
                        for nxt in itm[2:]:
                            addPath(prev, cur, paths)
                            addEdge(prev, cur, edges)
                            # cycle points
                            prev = cur
                            cur = nxt

                    addPath(prev, cur, paths)
                    addEdge(prev, cur, edges)
                else:
                    pass
            # Eif
            edgeGroups.append(edges)
        # Efor

        wires = [Part.Wire(g) for g in edgeGroups if g]

        return paths, wires

    # Public methods
    def setAdaptiveAttributes(
        self,
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
        stopped,
        stopProcessing,
        tolerance,
        stockObj,
        job,
        adaptiveOutputState,
        adaptiveInputState,
        viewObject,
    ):
        """setAdaptiveAttributes(startDepth,
                                 stepDown,
                                 finishDepth,
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
                                 stopped,
                                 stopProcessing,
                                 tolerance,
                                 stockObj,
                                 job,
                                 adaptiveOutputState,
                                 adaptiveInputState,
                                 viewObj):
        Call to set adaptive-dependent attributes."""
        # self.startDepth = startDepth
        # self.finalDepth = finalDepth
        # self.stepDown = stepDown
        # self.finishDepth = finishDepth
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
        self.stopped = stopped
        self.stopProcessing = stopProcessing
        self.tolerance = tolerance
        self.stockObj = stockObj
        self.job = job
        self.adaptiveOutputState = adaptiveOutputState
        self.adaptiveInputState = adaptiveInputState
        self.viewObject = viewObject

    def execute(self):
        """execute()...
        The public method for the StrategyClearing class.
        Returns a tuple containing a list of path commands and a list of shapes(wires and edges) as the path geometry.
        """
        # self._debugMsg("StrategyClearing.execute()")
        # PathLog.info("StrategyClearing.execute()")

        # Uncomment as needed for localized class debugging
        # self.isDebug = True
        # self.showDebugShapes = True

        commandList = []
        self.commandList = []  # Reset list
        self.pathGeometry = []  # Reset list
        self.startCommands = []  # Reset list
        self.isCenterSet = False
        # depthParams = [i for i in self.depthParams]
        self.prevDepth = self.safeHeight

        # Exit if pattern not available
        if self.cutPattern == "None":
            return False

        """
        if len(depthParams) == 0:
            self._debugMsg("No depth parameters", True)
            return []
        # PathLog.info("depthParams: {}".format(depthParams))

        # Verify input shape has volume (is an envelope)
        if hasattr(self.volumeShape, "Volume") and PathGeom.isRoughly(
            self.volumeShape.Volume, 0.0
        ):
            self._debugMsg("StrategyClearing: No volume in working shape.")
            return False
        """

        # Use Path.Area() for Grid and Triangle cut patterns
        if self.cutPattern in ["Grid", "Triangle"]:
            self._buildGridAndTrianglePaths()
            return True

        # Use refactored Adaptive op for Adaptive cut pattern
        if self.cutPattern == "Adaptive":
            self._getAdaptivePaths()
            return True

        # slices = PathStrategySlicing.sliceSolid(self.volumeShape, depthParams)
        lastFace = None
        lastPathGeom = None
        # print("PathStrategyClearing.execute() len(slices): {}".format(len(slices)))
        for slc in self.slices:
            # Part.show(slc, "slice")
            depth = slc.BoundBox.ZMin
            self._debugMsg(f"Slice depth of {depth}.", isError=True)

            # copy slice face and translate to Z=0.0
            useFace = slc.copy()
            useFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - useFace.BoundBox.ZMin))
            self.safeBaseShape = useFace

            if lastFace:
                # Compare current slice face with last face
                faceDif = lastFace.cut(useFace)
                wireDif = abs(lastFace.Wires[0].Length - useFace.Wires[0].Length)
                if PathGeom.isRoughly(faceDif.Area, 0.0, 0.0025) and PathGeom.isRoughly(
                    wireDif, 0.0
                ):
                    # print("PathStrategyClearing.execute() slices identical")
                    pathGeom = lastPathGeom
                else:
                    pathGeom = self._getPathGeometry(useFace)
                    lastPathGeom = pathGeom
            else:
                pathGeom = self._getPathGeometry(useFace)
                lastPathGeom = pathGeom

            if pathGeom:
                pathCmds = self._buildPaths(depth, pathGeom)
                if pathCmds:
                    if not self.keepToolDown:
                        pathCmds.append(
                            Path.Command(
                                "G0",
                                {
                                    "Z": self.clearanceHeight,
                                    "F": self.vertRapid,
                                },
                            )
                        )
                    # Save gcode
                    commandList.append(Path.Command("(Begin slice)", {}))
                    commandList.extend(pathCmds)
                    commandList.append(
                        Path.Command(
                            "G0",
                            {
                                "Z": self.safeHeight,
                                "F": self.vertRapid,
                            },
                        )
                    )

                # Save path geometry at depth
                pathGeomComp = Part.makeCompound(pathGeom)
                pathGeomComp.translate(FreeCAD.Vector(0.0, 0.0, depth))
                self.pathGeometry.append(pathGeomComp)
                # Part.show(pathGeomComp, "pathGeomComp")

                # rotate useFace
                lastFace = useFace
            else:
                self._debugMsg(
                    f"No path geometry to process at depth of {depth}.", isError=True
                )
                # break

            self.prevDepth = depth
        # Efor

        if len(commandList) > 0:
            self.commandList = self.startCommands + commandList
        else:
            # self._debugMsg("No commands in commandList", isError=True)
            self._debugMsg("No commands in commandList")

        PathLog.debug("commandList count: {}".format(len(self.commandList)))
        PathLog.debug("Path with params: {}".format(self.pathParams))

        endVectCnt = len(self.endVectors)
        if endVectCnt > 0:
            self.endVector = self.endVectors[endVectCnt - 1]

        # Part.show(Part.makeCompound(self.pathGeometry), "strategy.pathGeometry")

        return True

    def executeOCL(self, model_object, obj):
        """executeOCL()...
        The public method for the StrategyClearing class for use with OpenCAM Library.
        Returns a tuple containing a list of path commands and a list of shapes(wires and edges) as the path geometry.
        """
        # self._debugMsg("StrategyClearing.execute()")
        PathLog.info("StrategyClearing.execute()")
        import PathScripts.strategies.PathStrategyOCL as PathStrategyOCL

        # Uncomment as needed for localized class debugging
        self.isDebug = True
        # self.showDebugShapes = True

        # self.commandList = []  # Reset list
        self.pathGeometry = []  # Reset list
        self.isCenterSet = False
        commandList = []
        depthParams = [i for i in self.depthParams]
        startDepth = self.depthParams.start_depth
        finalDepth = self.depthParams.final_depth
        self.prevDepth = self.safeHeight
        pathGeometry = []

        # Create OCL cutter from tool controller attributes
        oclTool = PathStrategyOCL.OCL_Tool(obj.ToolController)
        oclCutter = oclTool.getOclTool()

        # Exit if pattern not available
        if self.cutPattern == "None":
            return False

        if len(depthParams) == 0:
            self._debugMsg("No depth parameters", True)
            return False

        if not self.volumeShape:
            return False

        self._buildStartPath()

        """
        if self.keepToolDown:
            if not self.safeBaseShape:
                PathLog.warning(
                    translate(
                        "PathStrategyClearing", "No safe base shape for Keep Tool Down."
                    )
                )
                self.keepToolDown = False
        """

        if self.cutPattern in [
            "Circular",
            "CircularZigZag",
            "Spiral",
            "Adaptive",
            "Offset",
        ]:
            conversionMethod = self._convertCurvedOclPointLists
        else:
            conversionMethod = self._convertOclPointLists

        openCAMLib = PathStrategyOCL.OpenCAMLib(
            oclCutter,
            model_object.Shape,
            finalDepth,
            self.depthOffset,
            obj.SampleInterval.Value,
            obj.LinearDeflection.Value,
        )

        if self.materialAllowance != 0.0:
            targetArea = PathUtils.getOffsetArea(
                self.volumeShape, -1.0 * self.materialAllowance
            )
            # offsetFace = PathUtils.getOffsetArea(self.volumeShape, self.materialAllowance)
            # targetArea = offsetFace.cut(self.baseObject.Shape)
        else:
            targetArea = self.volumeShape

        if obj.CutMode == "Single-pass":
            pathGeom = self._getPathGeometry(targetArea)
            if pathGeom:
                # self.pathGeometry.extend(pathGeom)
                pointLists = self._oclScanEdges(openCAMLib, pathGeom)
                refinedPointLists = self._refinePointsList(
                    pointLists, self.jobTolerance / 2.0
                )
                pathCmds, edgeGroups = conversionMethod(refinedPointLists)

                self.pathGeometry.extend(edgeGroups)

                commandList.extend(pathCmds)
            else:
                self._debugMsg("No path geometry to process.", isError=True)

        elif obj.CutMode == "Multi-pass":
            prevDepth = startDepth
            pathGeom = self._getPathGeometry(targetArea)
            if pathGeom:
                # self.pathGeometry.extend(pathGeom)
                rawPointLists = self._oclScanEdges(openCAMLib, pathGeom)

                for passDepth in depthParams:
                    # self._addDebugObject(wf, 'workingFace_' + str(round(passDepth, 2)))
                    pointLists = self._limitPointsToDepth(
                        rawPointLists, prevDepth, passDepth
                    )
                    refinedPointLists = self._refinePointsList(
                        pointLists, self.jobTolerance / 2.0
                    )
                    pathCmds, edgeGroups = conversionMethod(refinedPointLists)
                    self.pathGeometry.extend(edgeGroups)
                    commandList.extend(pathCmds)
                    prevDepth = passDepth
            else:
                self._debugMsg("No path geometry to process.", isError=True)

        openCAMLib = None
        oclTool = None
        oclCutter = None
        del openCAMLib
        del oclTool
        del oclCutter

        self._debugMsg("commandList count: {}".format(len(commandList)))
        self._debugMsg("Path with params: {}".format(self.pathParams))

        endVectCnt = len(self.endVectors)
        if endVectCnt > 0:
            self.endVector = self.endVectors[endVectCnt - 1]

        if len(commandList) > 0:
            self.commandList = []
            self.commandList.extend(self.startCommands)
            self.commandList.extend(commandList)
        else:
            self._debugMsg("No commands in commandList")

        return True


# Eclass
