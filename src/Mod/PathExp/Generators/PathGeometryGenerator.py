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
PathOpTools = LazyLoader(
    # "PathScripts.PathOpTools", globals(), "PathScripts.PathOpTools"
    "Path.Op.Util",
    globals(),
    "Path.Op.Util",
)
time = LazyLoader("time", globals(), "time")
json = LazyLoader("json", globals(), "json")
math = LazyLoader("math", globals(), "math")
area = LazyLoader("area", globals(), "area")

if FreeCAD.GuiUp:
    coin = LazyLoader("pivy.coin", globals(), "pivy.coin")
    FreeCADGui = LazyLoader("FreeCADGui", globals(), "FreeCADGui")


__title__ = "Path Strategies"
__author__ = "Yorik van Havre; sliptonic (Brad Collette)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Path strategies available for path generation."
__contributors__ = ""


PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
translate = FreeCAD.Qt.translate


class PathGeometryGenerator:
    """PathGeometryGenerator() class...
    Generates a path geometry shape from an assigned pattern for conversion to tool paths.
    Arguments:
        callerClass:        reference to caller class
        targetFace:         face shape to serve as base for path geometry generation
        patternCenterAt:    choice of centering options
        patternCenterCustom: custom (x, y, 0.0) center point
        cutPatternReversed: boolean to reverse cut pattern from inside-out to outside-in
        cutPatternAngle:    rotation angle applied to rotatable patterns
        cutPattern:         cut pattern choice
        cutDirection:       conventional or climb
        stepOver:           step over percentage
        materialAllowance:  positive material to allow(leave), negative additional material to remove
        minTravel:          boolean to enable minimum travel (feature not enabled at this time)
        keepToolDown:       boolean to enable keeping tool down (feature not enabled at this time)
        toolController:     instance of tool controller to be used
        jobTolerance:       job tolerance value
    Available Patterns:
        - Adaptive, Circular, CircularZigZag, Grid, Line, LineOffset, Offset, Spiral, Triangle, ZigZag, ZigZagOffset
    Usage:
        - Instantiate this class.
        - Call the `setAdaptiveAttributes()` method with required attributes if you intend to use Adaptive cut pattern.
        - Call the `execute()` method to generate the path geometry. The path geometry has correctional linking applied.
        - The path geometry in now available in the `pathGeometry` attribute.
    Notes:
        - Grid and Triangle patterns are not rotatable at this time.
    """

    # Register valid patterns here by name
    # Create a corresponding processing method below. Precede the name with an underscore(_)
    patterns = (
        "Adaptive",
        "Circular",
        "CircularZigZag",
        "Grid",
        "Line",
        "LineOffset",
        "Offset",
        "Profile",
        "MultiProfile",
        "Spiral",
        "Triangle",
        "ZigZag",
        "ZigZagOffset",
    )
    rotatablePatterns = ("Line", "ZigZag", "LineOffset", "ZigZagOffset")
    curvedPatterns = ("Circular", "CircularZigZag", "Spiral")

    def __init__(
        self,
        callerClass,
        targetFace,
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
        jobTolerance,
    ):
        """__init__(callerClass,
            callerClass,
            targetFace,
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
            jobTolerance,)...
        PathGeometryGenerator class constructor method.
        """
        PathLog.debug("PathGeometryGenerator.__init__()")

        # Debugging attributes
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False
        self.showDebugShapes = False

        self.cutPattern = "None"
        self.face = None
        self.rawGeoList = None
        self.centerOfMass = None
        self.centerOfPattern = None
        self.halfDiag = None
        self.halfPasses = None
        self.workingPlane = Part.makeCircle(2.0)  # make circle for workplane
        self.rawPathGeometry = None
        self.linkedPathGeom = None
        self.pathGeometry = []
        self.commandList = []
        self.useStaticCenter = True  # Set True to use static center for all faces created by offsets and step downs.  Set False for dynamic centers based on PatternCenterAt
        self.isCenterSet = False
        self.endVector = None
        self.pathParams = ""
        self.areaParams = ""
        self.pfsRtn = None
        self.baseShape = None
        self.targetFaceHeight = 0.0

        # Save argument values to class instance
        self.callerClass = callerClass
        self.targetFace = targetFace
        self.patternCenterAt = patternCenterAt
        self.patternCenterCustom = patternCenterCustom
        self.cutPatternReversed = cutPatternReversed
        self.cutPatternAngle = cutPatternAngle
        self.cutDirection = cutDirection
        self.stepOver = stepOver
        self.materialAllowance = materialAllowance
        if cutPattern in ["Profile", "MultiProfile"]:
            self.offsetDirection = (
                1.0 if profileOutside else -1.0
            )  # 1.0=outside;  -1.0=inside
        else:
            self.offsetDirection = -1.0
        self.minTravel = minTravel
        self.keepToolDown = keepToolDown
        self.toolController = toolController
        self.jobTolerance = jobTolerance
        self.profileOutside = profileOutside

        self.toolDiameter = (
            toolController.Tool.Diameter.Value
            if hasattr(toolController.Tool.Diameter, "Value")
            else float(toolController.Tool.Diameter)
        )
        self.toolRadius = self.toolDiameter / 2.0
        self.cutOut = self.toolDiameter * (
            self.stepOver / 100.0
        )  # * self.offsetDirection

        if cutPattern in self.patterns:
            self.cutPattern = cutPattern
        else:
            PathLog.debug("The `{}` cut pattern is not available.".format(cutPattern))

        # Grid and Triangle pattern requirements - paths produced by Path.fromShapes()
        self.pocketMode = 6  # Grid=6, Triangle=7
        self.orientation = 0  # ['Conventional', 'Climb']

        ### Adaptive-specific attributes ###
        self.adaptiveMaterialAllowance = 0.0001
        self.pathArray = []
        self.operationType = None
        self.cutSide = None
        self.disableHelixEntry = None
        self.forceInsideOut = None
        self.liftDistance = None
        self.finishingProfile = False
        self.helixAngle = None
        self.helixConeAngle = None
        self.useHelixArcs = None
        self.helixDiameterLimit = None
        self.keepToolDownRatio = None
        self.tolerance = None
        self.stockType = ""
        self.stockShape = None

    def _debugMsg(self, msg, isError=False):
        """_debugMsg(msg)
        If `self.isDebug` flag is True, the provided message is printed in the Report View.
        If not, then the message is assigned a debug status.
        """
        if isError:
            PathLog.error("PathGeometryGenerator: " + msg + "\n")
            return

        if self.isDebug:
            # PathLog.info(msg)
            FreeCAD.Console.PrintMessage("PathGeometryGenerator: " + msg + "\n")
        else:
            PathLog.debug(msg)

    def _addDebugShape(self, shape, name="debug"):
        if self.isDebug and self.showDebugShapes:
            do = FreeCAD.ActiveDocument.addObject("Part::Feature", "debug_" + name)
            do.Shape = shape
            do.purgeTouched()

    # Raw cut pattern geometry generation methods
    def _Line(self):
        """_Line()... Returns raw set of Line wires at Z=0.0."""
        self._debugMsg("_Line()")

        geomList = []
        centRot = FreeCAD.Vector(
            0.0, 0.0, 0.0
        )  # Bottom left corner of face/selection/model
        segLength = self.halfDiag
        if self.patternCenterAt in ["XminYmin", "Custom"]:
            segLength = 2.0 * self.halfDiag
        self._debugMsg(f"_Line segLength: {segLength}")

        # Create end points for set of lines to intersect with cross-section face
        pntTuples = []
        start = -1 * (self.halfPasses - 1)
        end = self.halfPasses + 1
        self._debugMsg(f"_Line pnt tuple loop start, end: {start}, {end}")
        for lc in range(start, end):
            x1 = centRot.x - segLength
            x2 = centRot.x + segLength
            y1 = centRot.y + (lc * self.cutOut)
            # y2 = y1
            p1 = FreeCAD.Vector(x1, y1, 0.0)
            p2 = FreeCAD.Vector(x2, y1, 0.0)
            pntTuples.append((p1, p2))

        self._debugMsg(f"_Line pnt tuple count: {len(pntTuples)}")

        # Convert end points to lines

        if (self.cutDirection == "Climb" and not self.cutPatternReversed) or (
            self.cutDirection != "Climb" and self.cutPatternReversed
        ):
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
        """_LineOffset()... Returns raw set of Line wires at Z=0.0, with the Offset portion added later in the `_generatePathGeometry()` method."""
        self._debugMsg("_LineOffset()")
        return self._Line()

    def _Circular(self):
        """_Circular()... Returns raw set of Circular wires at Z=0.0."""
        geomList = []
        radialPasses = self._getRadialPasses()
        minRad = self.toolDiameter * 0.45

        if (self.cutDirection == "Conventional" and not self.cutPatternReversed) or (
            self.cutDirection != "Conventional" and self.cutPatternReversed
        ):
            direction = FreeCAD.Vector(0.0, 0.0, 1.0)
        else:
            direction = FreeCAD.Vector(0.0, 0.0, -1.0)

        # Make small center circle to start pattern
        if self.stepOver > 50:
            circle = Part.makeCircle(minRad, self.centerOfPattern, direction)
            geomList.append(circle)

        for lc in range(1, radialPasses + 1):
            rad = lc * self.cutOut
            if rad >= minRad:
                wire = Part.Wire(
                    [Part.makeCircle(rad, self.centerOfPattern, direction)]
                )
                geomList.append(wire)

        if not self.cutPatternReversed:
            geomList.reverse()

        return geomList

    def _CircularZigZag(self):
        """_CircularZigZag()... Returns raw set of Circular ZigZag wires at Z=0.0."""
        geomList = []
        radialPasses = self._getRadialPasses()
        minRad = self.toolDiameter * 0.45
        dirForward = FreeCAD.Vector(0, 0, 1)
        dirReverse = FreeCAD.Vector(0, 0, -1)

        if (self.cutDirection == "Climb" and self.cutPatternReversed) or (
            self.cutDirection != "Climb" and not self.cutPatternReversed
        ):
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
            activeDir = (
                dirForward if direction > 0 else dirReverse
            )  # update active direction after toggle

        for lc in range(1, radialPasses + 1):
            rad = lc * self.cutOut
            if rad >= minRad:
                wire = Part.Wire(
                    [Part.makeCircle(rad, self.centerOfPattern, activeDir)]
                )
                geomList.append(wire)
                direction *= -1  # toggle direction
                activeDir = (
                    dirForward if direction > 0 else dirReverse
                )  # update active direction after toggle
        # Efor

        if not self.cutPatternReversed:
            geomList.reverse()

        return geomList

    def _ZigZag(self):
        """_ZigZag()... Returns raw set of ZigZag wires at Z=0.0."""
        geomList = []
        centRot = FreeCAD.Vector(
            0.0, 0.0, 0.0
        )  # Bottom left corner of face/selection/model
        segLength = self.halfDiag
        if self.patternCenterAt == "XminYmin":
            segLength = 2.0 * self.halfDiag

        # Create end points for set of lines to intersect with cross-section face
        pntTuples = []
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
        if (self.cutDirection == "Climb" and not self.cutPatternReversed) or (
            self.cutDirection != "Climb" and self.cutPatternReversed
        ):
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
        """_ZigZagOffset()... Returns raw set of ZigZag wires at Z=0.0, with the Offset portion added later in the `_generatePathGeometry()` method."""
        return self._ZigZag()

    def _Offset(self):
        """_Offset()...
        Returns raw set of Offset wires at Z=0.0.
        Direction of cut is taken into account.
        Additional offset loop ordering is handled in the linking method.
        """
        PathLog.debug("_Offset()")

        wires = []
        shape = self.face
        offset = 0.0
        direction = 0
        doLast = 0
        loop = 1

        def _get_direction(w):
            if PathOpTools._isWireClockwise(w):
                return 1
            return -1

        def _reverse_wire(w):
            rev_list = []
            for e in w.Edges:
                rev_list.append(PathUtils.reverseEdge(e))
            rev_list.reverse()
            return Part.Wire(Part.__sortEdges__(rev_list))

        if self.stepOver > 49.0:
            doLast += 1

        while True:
            offsetArea = PathUtils.getOffsetArea(shape, offset, plane=self.workingPlane)
            if not offsetArea:
                # Attempt clearing of residual area
                if doLast:
                    doLast += 1
                    offset += self.cutOut / 2.0
                    offsetArea = PathUtils.getOffsetArea(
                        shape, offset, plane=self.workingPlane
                    )
                    if not offsetArea:
                        # Area fully consumed
                        break
                else:
                    # Area fully consumed
                    break

            # set initial cut direction
            if direction == 0:
                first_face_wire = offsetArea.Faces[0].Wires[0]
                direction = _get_direction(first_face_wire)
                if direction == 1:
                    direction = -1

            # process each wire within face
            for f in offsetArea.Faces:
                for w in f.Wires:
                    use_direction = direction
                    if self.cutPatternReversed:
                        use_direction = -1 * direction
                    wire_direction = _get_direction(w)
                    # Process wire
                    if wire_direction == use_direction:  # direction is correct
                        wire = w
                    else:  # incorrect direction, so reverse wire
                        wire = _reverse_wire(w)
                    wires.append(wire)

            offset -= self.cutOut
            loop += 1
            if doLast > 1:
                break
        # Ewhile

        return wires

    def _Profile(self):
        """_Profile... based on _Offset()...
        Returns raw set of Offset wires at Z=0.0.
        Direction of cut is taken into account.
        Additional offset loop ordering is handled in the linking method.
        """
        PathLog.debug("_Profile()")

        wires = []
        shape = self.face
        offset = 0.0
        direction = 0
        doLast = 0
        loop = 1

        def _get_direction(w):
            if PathOpTools._isWireClockwise(w):
                return 1
            return -1

        def _reverse_wire(w):
            rev_list = []
            for e in w.Edges:
                rev_list.append(PathUtils.reverseEdge(e))
            rev_list.reverse()
            return Part.Wire(Part.__sortEdges__(rev_list))

        if self.stepOver > 49.0:
            doLast += 1

        while True:
            offsetArea = PathUtils.getOffsetArea(shape, offset, plane=self.workingPlane)
            if not offsetArea:
                # Attempt clearing of residual area
                if doLast:
                    doLast += 1
                    offset += self.cutOut / 2.0
                    offsetArea = PathUtils.getOffsetArea(
                        shape, offset, plane=self.workingPlane
                    )
                    if not offsetArea:
                        # Area fully consumed
                        break
                else:
                    # Area fully consumed
                    break

            # set initial cut direction
            if direction == 0:
                first_face_wire = offsetArea.Faces[0].Wires[0]
                direction = _get_direction(first_face_wire)
                if direction == 1:
                    direction = -1

            # process each wire within face
            for f in offsetArea.Faces:
                for w in f.Wires:
                    use_direction = direction
                    if self.cutPatternReversed:
                        use_direction = -1 * direction
                    wire_direction = _get_direction(w)
                    # Process wire
                    if wire_direction == use_direction:  # direction is correct
                        wire = w
                    else:  # incorrect direction, so reverse wire
                        wire = _reverse_wire(w)
                    wires.append(wire)

            offset -= self.cutOut
            loop += 1
            if doLast > 1:
                break
            if loop > 1:
                # PathLog.info("Breaking offsetting process after first loop.")
                break  # breaking after one cycle
        # Ewhile

        return wires

    def _MultiProfile(self):
        """_MultiProfile... based on _Offset()...
        Returns raw set of Offset wires at Z=0.0.
        Direction of cut is taken into account.
        Additional offset loop ordering is handled in the linking method.
        """
        PathLog.debug("_MultiProfile()")

        wires = []
        shape = self.face
        direction = 0
        doLast = 0
        loop = 1
        loopStop = 2 if self.profileOutside else 2
        # wCnt = 0

        if self.profileOutside:
            offset = 1.0 * (
                self.toolRadius - (self.jobTolerance / 10.0)
            )  # self.offsetDirection * (self.toolRadius - (self.jobTolerance / 10.0))
        else:
            offset = -1.0 * (
                self.toolRadius - (self.jobTolerance / 10.0)
            )  # self.offsetDirection * (self.toolRadius - (self.jobTolerance / 10.0))

        # Part.show(shape, "MPFace")

        def _get_direction(w):
            if PathOpTools._isWireClockwise(w):
                return 1
            return -1

        def _reverse_wire(w):
            rev_list = []
            for e in w.Edges:
                rev_list.append(PathUtils.reverseEdge(e))
            rev_list.reverse()
            return Part.Wire(Part.__sortEdges__(rev_list))

        if self.stepOver > 49.0:
            doLast += 1

        while True:
            PathLog.info(f"MultiProfile offset start: {offset}")
            offsetArea = PathUtils.getOffsetArea(shape, offset, plane=self.workingPlane)
            if not offsetArea:
                # Attempt clearing of residual area
                if doLast:
                    doLast += 1
                    offset += self.cutOut / 2.0
                    offsetArea = PathUtils.getOffsetArea(
                        shape, offset, plane=self.workingPlane
                    )
                    if not offsetArea:
                        # Area fully consumed
                        break
                else:
                    # Area fully consumed
                    break

            # set initial cut direction
            if direction == 0:
                first_face_wire = offsetArea.Faces[0].Wires[0]
                direction = _get_direction(first_face_wire)
                if direction == 1:
                    direction = -1

            # process each wire within face
            for f in offsetArea.Faces:
                for w in f.Wires:
                    use_direction = direction
                    if self.cutPatternReversed:
                        use_direction = -1 * direction
                    wire_direction = _get_direction(w)
                    # Process wire
                    if wire_direction == use_direction:  # direction is correct
                        wire = w.copy()
                    else:  # incorrect direction, so reverse wire
                        wire = _reverse_wire(w)
                    # Part.show(wire, f"MP_Wire{wCnt}_")
                    # wCnt += 1
                    wires.append(wire)

            if self.profileOutside:
                offset += self.cutOut  # for growth of face
            else:
                offset += self.cutOut
            loop += 1
            if doLast > 1:
                PathLog.info("multiProfile break for doLast")
                break
            if loop > loopStop:
                PathLog.info(f"Breaking offsetting process after loop {loopStop}.")
                break
        # Ewhile

        # PathLog.info(f"wire count: {len(wires)}")
        return wires

    def _Spiral(self):
        """_Spiral()... Returns raw set of Spiral wires at Z=0.0."""
        geomList = []
        allEdges = []
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
            PathLog.debug("_Spiral() regular pattern")
            if self.cutDirection == "Climb":
                getPoint = self._makeRegSpiralPnt
            else:
                getPoint = self._makeOppSpiralPnt

            while draw:
                radAng = sumRadians + stepAng
                p1 = lastPoint
                p2 = getPoint(
                    move, cutOut, radAng
                )  # cutOut is 'b' in the equation r = b * radAng
                sumRadians += stepAng  # Increment sumRadians
                loopRadians += stepAng  # Increment loopRadians
                if loopRadians > twoPi:
                    loopCnt += 1
                    loopRadians -= twoPi
                    stepAng = segLen / (
                        (loopCnt + 1) * self.cutOut
                    )  # adjust stepAng with each loop/cycle
                # Create line and show in Object tree
                lineSeg = Part.makeLine(p1, p2)
                allEdges.append(lineSeg)
                # increment loop items
                segCnt += 1
                lastPoint = p2
                if sumRadians > stopRadians:
                    draw = False
            # Ewhile
        else:
            PathLog.debug("_Spiral() REVERSED pattern")
            if self.cutDirection == "Conventional":
                getPoint = self._makeOppSpiralPnt
            else:
                getPoint = self._makeRegSpiralPnt

            while draw:
                radAng = sumRadians + stepAng
                p1 = lastPoint
                p2 = getPoint(
                    move, cutOut, radAng
                )  # cutOut is 'b' in the equation r = b * radAng
                sumRadians += stepAng  # Increment sumRadians
                loopRadians += stepAng  # Increment loopRadians
                if loopRadians > twoPi:
                    loopCnt += 1
                    loopRadians -= twoPi
                    stepAng = segLen / (
                        (loopCnt + 1) * self.cutOut
                    )  # adjust stepAng with each loop/cycle
                segCnt += 1
                lastPoint = p2
                if sumRadians > stopRadians:
                    draw = False
                # Create line and show in Object tree
                lineSeg = Part.makeLine(p2, p1)
                allEdges.append(lineSeg)
            # Ewhile
            allEdges.reverse()
        # Eif

        spiral = Part.Wire(allEdges)
        geomList.append(spiral)

        return geomList

    def _Grid(self):
        """_Grid()...
        Returns raw set of Grid wires at Z=0.0 using `Path.fromShapes()` to generate gcode.
        Then a short converter algorithm is applied to the gcode to extract wires."""
        self.pocketMode = 6
        return self._extractGridAndTriangleWires()

    def _Triangle(self):
        """_Triangle()...
        Returns raw set of Triangle wires at Z=0.0 using `Path.fromShapes()` to generate gcode.
        Then a short converter algorithm is applied to the gcode to extract wires."""
        self.pocketMode = 7
        return self._extractGridAndTriangleWires()

    def _Adaptive(self):
        """_Adaptive()...
        Returns raw set of Adaptive wires at Z=0.0 using a condensed version of code from the Adaptive operation.
        Currently, no helix entry wires are included, only the clearing portion of wires.
        """
        PathLog.debug("_Adaptive() *** Adaptive path geometry generation started...")
        startTime = time.time()

        self.targetFace.translate(
            FreeCAD.Vector(0.0, 0.0, 0.0 - self.targetFace.BoundBox.ZMin)
        )
        for w in self.targetFace.Wires:
            for e in w.Edges:
                self.pathArray.append([self._discretize(e)])

        path2d = self._convertTo2d(self.pathArray)

        stockPaths = []
        if self.stockType == "CreateCylinder":
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
        a2d.stockToLeave = self.adaptiveMaterialAllowance  # self.materialAllowance
        a2d.tolerance = self.tolerance
        a2d.forceInsideOut = self.forceInsideOut
        a2d.finishingProfile = self.finishingProfile
        a2d.opType = opType

        def progressFn(tpaths):
            """progressFn(tpaths)... progress callback fn, if return true it will stop processing"""
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
                adaptiveResults.append(
                    {
                        "HelixCenterPoint": result.HelixCenterPoint,
                        "StartPoint": result.StartPoint,
                        "AdaptivePaths": result.AdaptivePaths,
                        "ReturnMotionType": result.ReturnMotionType,
                    }
                )

            # Generate geometry
            # PathLog.debug("Extracting wires from Adaptive data...")
            wires = []
            motionCutting = area.AdaptiveMotionType.Cutting
            for region in adaptiveResults:
                for pth in region["AdaptivePaths"]:
                    motion = pth[0]  # [0] contains motion type
                    if motion == motionCutting:
                        edges = []
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
            # self.adaptiveGeometry = wires
            PathLog.debug("*** Done. Elapsed time: %f sec" % (time.time() - startTime))
            # return self.adaptiveGeometry
            return wires

    # Path linking methods
    def _Link_Line(self):
        """_Link_Line()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
        self._debugMsg("_Link_Line()")

        allGroups = []
        allWires = []

        def isOriented(direction, p0, p1):
            oriented = p1.sub(p0).normalize()
            if PathGeom.isRoughly(direction.sub(oriented).Length, 0.0):
                return True
            return False

        i = 0
        edges = self.rawPathGeometry.Edges
        limit = len(edges)

        if limit == 0:
            PathLog.debug("no edges to link")
            return allWires

        e = edges[0]
        p0 = e.Vertexes[0].Point
        p1 = e.Vertexes[1].Point
        vect = p1.sub(p0)
        targetAng = math.atan2(vect.y, vect.x)
        group = [(edges[0], vect.Length)]
        direction = p1.sub(p0).normalize()

        for i in range(1, limit):
            # get next edge
            ne = edges[i]
            np0 = ne.Vertexes[0].Point  # Next point 0
            np1 = ne.Vertexes[1].Point  # Next point 1
            diff = np1.sub(p0)
            nxtAng = math.atan2(diff.y, diff.x)

            # Check if prev and next are colinear
            angDiff = abs(nxtAng - targetAng)
            if 0.000001 > angDiff:
                if isOriented(direction, np0, np1):
                    group.append((ne, np1.sub(p0).Length))
                else:
                    # PathLog.info("flipping line")
                    line = Part.makeLine(np1, np0)  # flip line segment
                    group.append((line, np1.sub(p0).Length))
            else:
                # Save current group
                allGroups.append(group)
                # Rotate edge and point value
                e = ne
                p0 = np0
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
        """_Link_Line()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
        return self._Link_Line()

    def _Link_Circular(self):
        """_Link_Circular()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
        # PathLog.debug("_Link_Circular()")

        def combineAdjacentArcs(grp):
            """combineAdjacentArcs(arcList)...
            Combine two adjacent arcs in list into single.
            The two arcs in the original list are replaced by the new single. The modified list is returned.
            """
            # PathLog.debug("combineAdjacentArcs()")

            i = 1
            limit = len(grp)
            arcs = []
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
                    # PathLog.debug("combining arcs")
                    # Create one continuous arc
                    cent = arc.Curve.Center
                    vect0 = aP1.sub(cent)
                    vect1 = naP0.sub(cent)
                    radius = arc.Curve.Radius
                    direct = FreeCAD.Vector(0.0, 0.0, 1.0)
                    angle0 = math.degrees(math.atan2(vect1.y, vect1.x))
                    angle1 = math.degrees(math.atan2(vect0.y, vect0.x))
                    if reversed:
                        newArc = Part.makeCircle(
                            radius,
                            cent,
                            direct.multiply(-1.0),
                            360.0 - angle0,
                            360 - angle1,
                        )  # makeCircle(radius,[pnt,dir,angle1,angle2])
                    else:
                        newArc = Part.makeCircle(
                            radius, cent, direct, angle0, angle1
                        )  # makeCircle(radius,[pnt,dir,angle1,angle2])
                    ang = aP0.sub(cent).normalize()
                    line = Part.makeLine(cent, aP0.add(ang))
                    touch = DraftGeomUtils.findIntersection(newArc, line)
                    if not touch:
                        if reversed:
                            newArc = Part.makeCircle(
                                radius,
                                cent,
                                direct.multiply(-1.0),
                                360.0 - angle1,
                                360 - angle0,
                            )  # makeCircle(radius,[pnt,dir,angle1,angle2])
                        else:
                            newArc = Part.makeCircle(
                                radius, cent, direct, angle1, angle0
                            )  # makeCircle(radius,[pnt,dir,angle1,angle2])
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

        allGroups = []
        allEdges = []
        if self.cutPatternReversed:  # inside to out
            edges = sorted(
                self.rawPathGeometry.Edges,
                key=lambda e: e.Curve.Center.sub(self.centerOfPattern).Length,
            )
        else:
            edges = sorted(
                self.rawPathGeometry.Edges,
                key=lambda e: e.Curve.Center.sub(self.centerOfPattern).Length,
                reverse=True,
            )
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
                allEdges.append(Part.Wire(g[0]))
            else:
                wires = [Part.Wire(arc) for arc in combineAdjacentArcs(g)]
                allEdges.extend(wires)

        return allEdges

    def _Link_CircularZigZag(self):
        """_Link_CircularZigZag()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
        return self._Link_Circular()

    def _Link_ZigZag(self):
        """_Link_ZigZag()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
        return self._Link_Line()

    def _Link_ZigZagOffset(self):
        """_Link_ZigZagOffset()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
        return self._Link_Line()

    def _Link_Offset(self):
        """_Link_Offset()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
        if self.cutPatternReversed:
            return sorted(
                self.rawPathGeometry.Wires, key=lambda wire: Part.Face(wire).Area
            )
        else:
            return sorted(
                self.rawPathGeometry.Wires,
                key=lambda wire: Part.Face(wire).Area,
                reverse=True,
            )

    def _Link_Profile(self):
        """_Link_Profile()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
        if self.cutPatternReversed:
            return sorted(
                self.rawPathGeometry.Wires, key=lambda wire: Part.Face(wire).Area
            )
        else:
            return sorted(
                self.rawPathGeometry.Wires,
                key=lambda wire: Part.Face(wire).Area,
                reverse=True,
            )

    def _Link_MultiProfile(self):
        """_Link_MultiProfile()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
        if self.cutPatternReversed:
            return sorted(
                self.rawPathGeometry.Wires, key=lambda wire: Part.Face(wire).Area
            )
        else:
            return sorted(
                self.rawPathGeometry.Wires,
                key=lambda wire: Part.Face(wire).Area,
                reverse=True,
            )

    def _Link_Spiral(self):
        """_Link_Spiral()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""

        def sortWires0(wire):
            return wire.Edges[0].Vertexes[0].Point.sub(self.centerOfPattern).Length

        def sortWires1(wire):
            eIdx = len(wire.Edges) - 1
            return wire.Edges[eIdx].Vertexes[1].Point.sub(self.centerOfPattern).Length

        if self.cutPatternReversed:
            # Center outward
            return sorted(self.rawPathGeometry.Wires, key=sortWires0)
        else:
            # Outside inward
            return sorted(self.rawPathGeometry.Wires, key=sortWires1, reverse=True)

    def _Link_Grid(self):
        """_Link_Grid()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
        # No linking required.
        return self.rawPathGeometry.Wires

    def _Link_Triangle(self):
        """_Link_Grid()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
        # No linking required.
        return self.rawPathGeometry.Wires

    def _Link_Adaptive(self):
        """_Link_Adaptive()... Apply necessary linking to resulting wire set after common between target face and raw wire set."""
        # No linking required.
        return self.rawPathGeometry.Wires

    # Support methods
    def _prepareAttributes(self):
        """_prepareAttributes()... Prepare instance attribute values for path generation."""
        if self.isCenterSet:
            if self.useStaticCenter:
                return

        # Compute weighted center of mass of all faces combined
        if self.patternCenterAt == "CenterOfMass":
            comF = self.face.CenterOfMass
            self.centerOfMass = FreeCAD.Vector(comF.x, comF.y, 0.0)
        self.centerOfPattern = self._getPatternCenter()

        # calculate line length
        deltaC = self.targetFace.BoundBox.DiagonalLength
        lineLen = deltaC + (
            2.0 * self.toolDiameter
        )  # Line length to span boundbox diag with 2x cutter diameter extra on each end
        if self.patternCenterAt == "Custom":
            distToCent = self.face.BoundBox.Center.sub(self.centerOfPattern).Length
            lineLen += distToCent
        self.halfDiag = math.ceil(lineLen / 2.0)

        # Calculate number of passes
        cutPasses = (
            math.ceil(lineLen / self.cutOut) + 1
        )  # Number of lines(passes) required to cover boundbox diagonal
        if self.patternCenterAt == "Custom":
            self.halfPasses = math.ceil(cutPasses)
        else:
            self.halfPasses = math.ceil(cutPasses / 2.0)

        self.isCenterSet = True

    def _getPatternCenter(self):
        """_getPatternCenter()... Determine center of cut pattern and save in instance attribute."""
        centerAt = self.patternCenterAt

        if centerAt == "CenterOfMass":
            cntrPnt = FreeCAD.Vector(self.centerOfMass.x, self.centerOfMass.y, 0.0)
        elif centerAt == "CenterOfBoundBox":
            cent = self.face.BoundBox.Center
            cntrPnt = FreeCAD.Vector(cent.x, cent.y, 0.0)
        elif centerAt == "XminYmin":
            cntrPnt = FreeCAD.Vector(
                self.face.BoundBox.XMin, self.face.BoundBox.YMin, 0.0
            )
        elif centerAt == "Custom":
            cntrPnt = FreeCAD.Vector(
                self.patternCenterCustom.x, self.patternCenterCustom.y, 0.0
            )

        self.centerOfPattern = cntrPnt

        return cntrPnt

    def _getRadialPasses(self):
        """_getRadialPasses()... Return number of radial passes required for circular and spiral patterns."""
        # recalculate number of passes, if need be
        radialPasses = self.halfPasses
        if self.patternCenterAt != "CenterOfBoundBox":
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
            diag = dMax + (
                2.0 * self.toolDiameter
            )  # Line length to span boundbox diag with 2x cutter diameter extra on each end
            radialPasses = (
                math.ceil(diag / self.cutOut) + 1
            )  # Number of lines(passes) required to cover boundbox diagonal

        return radialPasses

    def _makeRegSpiralPnt(self, move, b, radAng):
        """_makeRegSpiralPnt(move, b, radAng)... Return next point on regular spiral pattern."""
        x = b * radAng * math.cos(radAng)
        y = b * radAng * math.sin(radAng)
        return FreeCAD.Vector(x, y, 0.0).add(move)

    def _makeOppSpiralPnt(self, move, b, radAng):
        """_makeOppSpiralPnt(move, b, radAng)... Return next point on opposite(reversed) spiral pattern."""
        x = b * radAng * math.cos(radAng)
        y = b * radAng * math.sin(radAng)
        return FreeCAD.Vector(-1 * x, y, 0.0).add(move)

    def _getProfileWires(self):
        """_getProfileWires()... Return set of profile wires for target face."""
        wireList = []
        shape = self.face
        offset = 0.0
        direction = 1  # 'Conventional on outer loop of Pocket clearing
        if self.cutDirection == "Climb":
            direction = -1

        def _get_direction(w):
            if PathOpTools._isWireClockwise(w):
                return 1
            return -1

        def _reverse_wire(w):
            rev_list = []
            for e in w.Edges:
                rev_list.append(PathUtils.reverseEdge(e))
            # rev_list.reverse()
            return Part.Wire(Part.__sortEdges__(rev_list))

        offsetArea = PathUtils.getOffsetArea(shape, offset, plane=self.workingPlane)
        if not offsetArea:
            PathLog.debug("_getProfileWires() no offsetArea")
            # Area fully consumed
            return wireList

        # process each wire within face
        for f in offsetArea.Faces:
            wCnt = 0
            for w in f.Wires:
                use_direction = direction
                wire_direction = _get_direction(w)
                if wCnt > 0:
                    use_direction = -1 * direction
                # Process wire
                if wire_direction == use_direction:  # direction is correct
                    wire = w
                else:  # incorrect direction, so reverse wire
                    wire = _reverse_wire(w)
                wireList.append(wire)
                wCnt += 1

        return wireList

    def _applyPathLinking(self):
        """_applyPathLinking()... Control method for applying linking to target wire set."""
        PathLog.debug(f"_applyPathLinking({self.cutPattern})")

        # patterns = ('Adaptive', 'Circular', 'CircularZigZag', 'Grid', 'Line', 'LineOffset', 'Offset', 'Spiral', 'Triangle', 'ZigZag', 'ZigZagOffset')
        linkMethodName = "_Link_" + self.cutPattern
        linkMethod = getattr(self, linkMethodName)
        linked = linkMethod()
        return linked

    def _extractGridAndTriangleWires(self):
        """_buildGridAndTrianglePaths() ... Returns a set of wires representng Grid or Triangle cut paths."""
        PathLog.track()
        # areaParams = {}
        pathParams = {}

        if self.cutDirection == "Climb":
            self.orientation = 1

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
        pathParams["shapes"] = [self.targetFace]
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
        PathLog.debug("Path with params: {}".format(self.pathParams))

        # Build paths from path parameters
        (pp, end_vector) = Path.fromShapes(**pathParams)
        PathLog.debug("pp: {}, end vector: {}".format(pp, end_vector))
        self.endVector = end_vector  # pylint: disable=attribute-defined-outside-init

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

    def _generatePathGeometry(self):
        """_generatePathGeometry()... Control function that generates path geometry wire sets."""
        self._debugMsg("_generatePathGeometry()")

        patternMethod = getattr(self, "_" + self.cutPattern)
        self.rawGeoList = patternMethod()
        self._debugMsg(f"len(self.rawGeoList): {len(self.rawGeoList)}")

        # Create compound object to bind all geometry
        geomShape = Part.makeCompound(self.rawGeoList)
        # Part.show(geomShape, "GeomShape")

        self._addDebugShape(geomShape, "rawPathGeomShape")  # Debugging

        # Position and rotate the Line and ZigZag geometry
        if self.cutPattern in self.rotatablePatterns:
            if self.cutPatternAngle != 0.0:
                geomShape.Placement.Rotation = FreeCAD.Rotation(
                    FreeCAD.Vector(0, 0, 1), self.cutPatternAngle
                )
            cop = self.centerOfPattern
            geomShape.Placement.Base = FreeCAD.Vector(
                cop.x, cop.y, 0.0 - geomShape.BoundBox.ZMin
            )

        self._addDebugShape(geomShape, "tmpGeometrySet")  # Debugging

        # Return current geometry for Offset or Profile patterns
        if self.cutPattern == "Offset":
            self.rawPathGeometry = geomShape
            self.linkedPathGeom = self._applyPathLinking()
            return self.linkedPathGeom

        # Add profile 'Offset' path after base pattern
        appendOffsetWires = False
        if self.cutPattern != "Offset" and self.cutPattern[-6:] == "Offset":
            appendOffsetWires = True

        # Identify intersection of cross-section face and lineset
        if self.cutPattern == "MultiProfile" and self.profileOutside:
            self.rawPathGeometry = Part.makeCompound(geomShape.Wires)
        elif self.cutPattern in ["Profile", "MultiProfile"]:
            self.rawPathGeometry = Part.makeCompound(geomShape.Wires)
        else:
            rawWireSet = Part.makeCompound(geomShape.Wires)
            self.rawPathGeometry = self.face.common(rawWireSet)

        self._addDebugShape(self.rawPathGeometry, "rawPathGeometry")  # Debugging

        linkedPathGeom = self._applyPathLinking()
        # PathLog.info(f"len(linkedPathGeom): {len(linkedPathGeom)}")
        # Part.show(Part.makeCompound(linkedPathGeom), "linkedPathGeom")

        if appendOffsetWires:
            linkedPathGeom.extend(self._getProfileWires())

        self.linkedPathGeom = linkedPathGeom
        return linkedPathGeom

    # Private adaptive support methods
    def _convertTo2d(self, pathArray):
        """_convertTo2d() ... Converts array of edge lists into list of point list pairs. Used for Adaptive cut pattern."""
        output = []
        for path in pathArray:
            pth2 = []
            for edge in path:
                for pt in edge:
                    pth2.append([pt[0], pt[1]])
            output.append(pth2)
        return output

    def _discretize(self, edge, flipDirection=False):
        """_discretize(edge, flipDirection=False) ... Discretizes an edge into a set of points. Used for Adaptive cut pattern."""
        pts = edge.discretize(Deflection=0.0001)
        if flipDirection:
            pts.reverse()

        return pts

    def _generateGCode(self, adaptiveResults):
        """_generateGCode(adaptiveResults) ...
        Converts raw Adaptive algorithm data into gcode.
        Not currently active.  Will be modified to extract helix data as wires.
        Will be used for Adaptive cut pattern."""
        self.commandList = []
        commandList = []
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

                # Helix ramp
                if self.useHelixEntry and helixRadius > 0.01:
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
        tolerance,
        stockType,
        stockShape,
    ):
        """setAdaptiveAttributes(operationType,
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
        Call to set adaptive-dependent attributes prior to calling `execute()` method.
        Arguments:
            operationType:      clearing or profile
            cutSide:            inside or outside
            disableHelixEntry:  boolean to disable helix entry (feature hard coded True, with no helix geometry available at this time)
            forceInsideOut:     boolean to force cutting direction inside-out
            liftDistance:       distance to lift cutter between same-layer linking moves
            finishingProfile:   boolean to include finishing profile path
            helixAngle:         helix angle
            helixConeAngle:     helix cone angle
            useHelixArcs:       boolean to use G2/G3 arcs for helix in place of G1 line segments
            helixDiameterLimit: max diameter for helix entry
            keepToolDownRatio:  threshold value for keeping tool down
            tolerance:          tolerance versus accuracy value within set range
            stockObj:           reference to job stock object
        """
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
        self.stockType = stockType
        self.stockShape = stockShape

        # if disableHelixEntry:
        #    self.helixDiameterLimit = 0.01
        #    self.helixAngle = 89.0
        pass

    def execute(self):
        """execute()...
        Call this method to execute the path generation code in PathGeometryGenerator class.
        Returns True on success.  Access class instance `pathGeometry` attribute for path geometry.
        """
        self._debugMsg("StrategyClearing.execute()")

        self.commandList = []  # Reset list
        # self.pathGeometry = []  # Reset list
        pathGeometry = []  # Reset list
        self.isCenterSet = False
        # success = False

        # Exit if pattern not available
        if self.cutPattern == "None":
            self._debugMsg("self.cutPattern == 'None'", True)
            return False

        if hasattr(self.targetFace, "Area") and PathGeom.isRoughly(
            self.targetFace.Area, 0.0
        ):
            self._debugMsg("PathGeometryGenerator: No area in working shape.", True)
            return False

        if not self.baseShape:
            self._debugMsg("PathGeometryGenerator: No baseShape.", True)
            return False

        self.targetFace.translate(
            FreeCAD.Vector(0.0, 0.0, 0.0 - self.targetFace.BoundBox.ZMin)
        )

        # Set initial face offset value based on cut pattern
        if self.cutPattern in ["Adaptive", "MultiProfile"]:
            ofstVal = 0.0
            offsetWF = self.targetFace.copy()
        else:
            #  Apply simple radius shrinking offset for clearing pattern generation.
            ofstVal = self.offsetDirection * (
                self.toolRadius
                - (self.jobTolerance / 10.0)  #  + self.materialAllowance
            )
            PathLog.info(f"PathGeometryGenerator ofstVal: {ofstVal}")
            offsetWF = PathUtils.getOffsetArea(self.targetFace, ofstVal)

        # Part.show(offsetWF, "OffsetWF")

        if offsetWF is False:
            self._debugMsg("getOffsetArea() failed")
            Part.show(self.targetFace, "PGG_TargetFace")
        elif len(offsetWF.Faces) == 0:
            self._debugMsg("No offset faces to process for path geometry.")
        else:
            for fc in offsetWF.Faces:
                # fc.translate(FreeCAD.Vector(0.0, 0.0, self.targetFaceHeight))

                # useFaces = fc.cut(self.baseShape)
                useFaces = fc
                if useFaces.Faces:
                    for f in useFaces.Faces:
                        f.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - f.BoundBox.ZMin))
                        self.face = f
                        self._prepareAttributes()
                        pathGeom = self._generatePathGeometry()
                        pathGeometry.extend(w.copy() for w in pathGeom)
                        # success = True
                else:
                    self._debugMsg("No offset faces after cut with base shape.")

        # self._debugMsg("Path with params: {}".format(self.pathParams))

        # PathLog.info(f"returning len(pathGeometry): {len(pathGeometry)}")
        self.pathGeometry = pathGeometry
        return pathGeometry


# Eclass
