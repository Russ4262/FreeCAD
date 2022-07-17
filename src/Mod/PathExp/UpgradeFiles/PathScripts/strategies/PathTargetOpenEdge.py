# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2021 Russell Johnson (russ4262) <russ4262@gmail.com>    *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
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
import Part
import PathScripts.PathGeom as PathGeom
import PathScripts.PathLog as PathLog
import PathScripts.strategies.PathTargetBuildUtils as PathTargetBuildUtils
import math
from PySide import QtCore

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader

DraftGeomUtils = LazyLoader("DraftGeomUtils", globals(), "DraftGeomUtils")
PathUtils = LazyLoader("PathScripts.PathUtils", globals(), "PathScripts.PathUtils")
TechDraw = LazyLoader("TechDraw", globals(), "TechDraw")


__title__ = "Path Selection Processing"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "http://www.freecadweb.org"
__doc__ = (
    "Collection of classes and functions used to process and refine user selections."
)
__contributors__ = ""


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())

isRoughly = PathGeom.isRoughly
Tolerance = PathGeom.Tolerance
isVertical = PathGeom.isVertical
isHorizontal = PathGeom.isHorizontal

# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class OpenEdge:
    def __init__(
        self,
        baseShape,
        wire,
        finalDepth,
        toolRadius,
        offsetRadius,
        useToolComp,
        jobTolerance,
        jobLabel="Job",
    ):
        self.baseShape = baseShape
        self.wire = wire
        self.finalDepth = finalDepth
        self.toolRadius = abs(toolRadius)
        self.offsetRadius = offsetRadius
        self.useToolComp = useToolComp
        self.jobTolerance = jobTolerance
        self.jobLabel = jobLabel
        self.geomFinalDepth = finalDepth
        self.wireBoundBoxFaceAtZero = None
        self.useOtherSide = False
        self.pathStops = None
        self.otherPathStops = None
        self.sortedFlatWire = None
        self.errorshape = None
        self.inaccessibleMsg = translate(
            "PathProfile",
            "The selected edge(s) are inaccessible. If multiple, re-ordering selection might work.",
        )

        if finalDepth < baseShape.BoundBox.ZMin:
            self.geomFinalDepth = baseShape.BoundBox.ZMin

        if finalDepth > wire.BoundBox.ZMin:
            self.geomFinalDepth = wire.BoundBox.ZMin

        if toolRadius < 0.0:
            self.useOtherSide = True

        # Debugging attributes
        self.isDebug = False
        self.showDebugShapes = False

    # Method to add temporary debug object
    def _debugMsg(self, msg, isError=False):
        """_debugMsg(msg)
        If `self.isDebug` flag is True, the provided message is printed in the Report View.
        If not, then the message is assigned a debug status.
        """
        if isError:
            PathLog.error(msg)
            return

        if self.isDebug:
            # PathLog.info(msg)
            FreeCAD.Console.PrintMessage("PathTargetOpenEdge.OpenEdge: " + msg + "\n")
        else:
            PathLog.debug(msg)

    def _addDebugObject(self, objName, objShape):
        if self.isDebug and self.showDebugShapes:
            O = FreeCAD.ActiveDocument.addObject("Part::Feature", "tmp_" + objName)
            O.Shape = objShape
            O.purgeTouched()

    # Private methods
    def _getCutAreaCrossSection(self, origWire, flatWire):
        self._debugMsg("_getCutAreaCrossSection()")
        # FCAD = FreeCAD.ActiveDocument
        tolerance = self.jobTolerance
        toolDiam = 2 * self.toolRadius  # self.toolRadius defined in PathOp
        minBfr = toolDiam * 1.25
        bbBfr = (self.offsetRadius * 2) * 1.25
        if bbBfr < minBfr:
            bbBfr = minBfr
        # fwBB = flatWire.BoundBox
        wBB = origWire.BoundBox
        minArea = (self.offsetRadius - tolerance) ** 2 * math.pi
        self.wireBoundBoxFaceAtZero = self._makeExtendedBoundBox(wBB, bbBfr, 0.0)

        useWire = origWire.Wires[0]
        numOrigEdges = len(useWire.Edges)
        sdv = wBB.ZMax
        fdv = self.geomFinalDepth
        extLenFwd = sdv - fdv
        if extLenFwd <= 0.0:
            msg = translate(
                "PathProfile", "For open edges, verify Final Depth for this operation."
            )
            FreeCAD.Console.PrintError(msg + "\n")
            # return False
            extLenFwd = 0.1

        # Identify first/last edges and first/last vertex on wire
        numEdges = len(self.sortedFlatWire.Edges)
        begE = self.sortedFlatWire.Edges[0]  # beginning edge
        endE = self.sortedFlatWire.Edges[numEdges - 1]  # ending edge
        blen = begE.Length
        elen = endE.Length
        Vb = begE.Vertexes[0]  # first vertex of wire
        Ve = endE.Vertexes[1]  # last vertex of wire
        pb = FreeCAD.Vector(Vb.X, Vb.Y, fdv)
        pe = FreeCAD.Vector(Ve.X, Ve.Y, fdv)

        # Obtain beginning point perpendicular points
        if blen > 0.1:
            bcp = begE.valueAt(
                begE.getParameterByLength(0.1)
            )  # point returned 0.1 mm along edge
        else:
            bcp = FreeCAD.Vector(begE.Vertexes[1].X, begE.Vertexes[1].Y, fdv)
        if elen > 0.1:
            ecp = endE.valueAt(
                endE.getParameterByLength(elen - 0.1)
            )  # point returned 0.1 mm along edge
        else:
            ecp = FreeCAD.Vector(endE.Vertexes[1].X, endE.Vertexes[1].Y, fdv)

        # Create intersection tags for determining which side of wire to cut
        (begInt, begExt, iTAG, eTAG) = self._makeIntersectionTags(
            useWire, numOrigEdges, fdv
        )
        if not begInt or not begExt:
            return False
        self.iTAG = iTAG
        self.eTAG = eTAG

        # COLLISTION
        # collision = getOverheadRegionsAboveHeight(self.baseShape, fdv)  # was `fdv`

        # Identify working layer of baseShape for wire(s)
        if isRoughly(wBB.ZLength, 0.0):
            wireLayer = PathTargetBuildUtils.getCrossSectionOfSolid(
                self.baseShape, wBB.ZMin
            )
        else:
            thickCS = PathTargetBuildUtils.getThickCrossSection(
                self.baseShape, wBB.ZMin, wBB.ZMax, isDebug=False
            )
            projCS = PathTargetBuildUtils.getBaseCrossSection(thickCS)
            wireLayer = PathTargetBuildUtils.fuseShapes(projCS.Faces)
        wireLayer.translate(FreeCAD.Vector(0, 0, 0.0 - wireLayer.BoundBox.ZMin))
        self._addDebugObject("wireLayer", wireLayer)

        # Isolate working layer to expanded boundbox around wire
        rawComFC = self.wireBoundBoxFaceAtZero.cut(wireLayer)
        rawComFC.translate(FreeCAD.Vector(0, 0, 0.0 - rawComFC.BoundBox.ZMin))
        self._addDebugObject("rawComFC", rawComFC)

        # Invert the working face for Other Side as needed
        if (
            self.useOtherSide
        ):  # alternate Inside/Outside application in `_extractPathWire()` in progress...
            comFC = self.wireBoundBoxFaceAtZero.cut(rawComFC)
        else:
            comFC = rawComFC
        self._addDebugObject("comFC", comFC)

        # Determine with which set of intersection tags the model intersects
        tagCOM = self._checkTagIntersection(iTAG, eTAG, "QRY", comFC, begInt, begExt)

        # Make two beginning style(oriented) 'L' shape stops
        begStop = self._makeStop("BEG", bcp, pb, "BegStop")
        altBegStop = self._makeStop("END", bcp, pb, "BegStop")

        # Identify to which style 'L' stop the beginning intersection tag is closest,
        # and create partner end 'L' stop geometry, and save for application later
        lenBS_extETag = begStop.CenterOfMass.sub(tagCOM).Length
        lenABS_extETag = altBegStop.CenterOfMass.sub(tagCOM).Length
        if lenBS_extETag < lenABS_extETag:
            endStop = self._makeStop("END", ecp, pe, "EndStop")
            self.pathStops = Part.makeCompound([begStop, endStop])
            # save other Path Stops
            altEndStop = self._makeStop("BEG", ecp, pe, "EndStop")
            self.otherPathStops = Part.makeCompound([altBegStop, altEndStop])
        else:
            altEndStop = self._makeStop("BEG", ecp, pe, "EndStop")
            self.pathStops = Part.makeCompound([altBegStop, altEndStop])
            # save other Path Stops
            endStop = self._makeStop("END", ecp, pe, "EndStop")
            self.otherPathStops = Part.makeCompound([begStop, endStop])
        self.pathStops.translate(
            FreeCAD.Vector(0, 0, 0.0 - self.pathStops.BoundBox.ZMin)
        )
        self.otherPathStops.translate(
            FreeCAD.Vector(0, 0, 0.0 - self.otherPathStops.BoundBox.ZMin)
        )

        # Identify closed wire in cross-section that corresponds to user-selected edge(s)
        workShp = comFC
        fcShp = workShp
        wire = origWire
        WS = workShp.Wires
        lenWS = len(WS)
        if lenWS < 3:
            wi = 0
        else:
            wi = None
            for wvt in wire.Vertexes:
                for w in range(0, lenWS):
                    twr = WS[w]
                    for v in range(0, len(twr.Vertexes)):
                        V = twr.Vertexes[v]
                        if abs(V.X - wvt.X) < tolerance:
                            if abs(V.Y - wvt.Y) < tolerance:
                                # Same vertex found.  This wire to be used for offset
                                wi = w
                                break
            # Efor

            if wi is None:
                PathLog.error(
                    "The cut area cross-section wire does not coincide with selected edge. Wires[] index is None."
                )
                return False
            else:
                self._debugMsg("Cross-section Wires[] index is {}.".format(wi))

            nWire = Part.Wire(Part.__sortEdges__(workShp.Wires[wi].Edges))
            fcShp = Part.Face(nWire)
            fcShp.translate(FreeCAD.Vector(0, 0, fdv - workShp.BoundBox.ZMin))
        # Eif

        # verify that wire chosen is not inside the physical model
        # Recent changes above with identifying working layer might render this section obsolete - testing necessary
        if wi > 0:  # and isInterior is False:
            self._debugMsg(
                "Multiple wires in cut area. First choice is not 0. Testing."
            )
            testArea = fcShp.cut(self.baseShape)

            isReady = self._checkTagIntersection(iTAG, eTAG, self.cutSide, testArea)
            self._debugMsg("isReady {}.".format(isReady))

            if isReady is False:
                self._debugMsg("Using wire index {}.".format(wi - 1))
                pWire = Part.Wire(Part.__sortEdges__(workShp.Wires[wi - 1].Edges))
                pfcShp = Part.Face(pWire)
                pfcShp.translate(FreeCAD.Vector(0, 0, fdv - workShp.BoundBox.ZMin))
                workShp = pfcShp.cut(fcShp)

            if testArea.Area < minArea:
                self._debugMsg(
                    "offset area is less than minArea of {}.".format(minArea)
                )
                self._debugMsg("Using wire index {}.".format(wi - 1))
                pWire = Part.Wire(Part.__sortEdges__(workShp.Wires[wi - 1].Edges))
                pfcShp = Part.Face(pWire)
                pfcShp.translate(FreeCAD.Vector(0, 0, fdv - workShp.BoundBox.ZMin))
                workShp = pfcShp.cut(fcShp)
        # Eif

        # Add path stops at ends of wire
        cutShp = workShp.cut(self.pathStops)
        self._addDebugObject("CutShape", cutShp)

        return cutShp

    def _checkTagIntersection(
        self, iTAG, eTAG, cutSide, tstObj, begInt=None, begExt=None
    ):
        self._debugMsg("_checkTagIntersection()")
        # Identify intersection of Common area and Interior Tags
        intCmn = tstObj.common(iTAG)

        # Identify intersection of Common area and Exterior Tags
        extCmn = tstObj.common(eTAG)

        # Calculate common intersection (solid model side, or the non-cut side) area with tags, to determine physical cut side
        cmnIntArea = intCmn.Area
        cmnExtArea = extCmn.Area
        if cutSide == "QRY":
            # return (cmnIntArea, cmnExtArea)
            if cmnExtArea > cmnIntArea:
                self._debugMsg("Cutting on Ext side.")
                self.cutSide = "E"
                self.cutSideTags = eTAG
                tagCOM = begExt.CenterOfMass
            else:
                self._debugMsg("Cutting on Int side.")
                self.cutSide = "I"
                self.cutSideTags = iTAG
                tagCOM = begInt.CenterOfMass
            return tagCOM

        if cmnExtArea > cmnIntArea:
            self._debugMsg("Cutting on Ext side.")
            if cutSide == "E":
                return True
        else:
            self._debugMsg("Cutting on Int side.")
            if cutSide == "I":
                return True
        return False

    def _extractPathWire(self, flatWire, cutShp):
        self._debugMsg("_extractPathWire()")

        subLoops = list()
        rtnWIRES = list()
        osWrIdxs = list()
        subDistFactor = (
            1.0  # Raise to include sub wires at greater distance from original
        )
        wire = flatWire
        lstVrtIdx = len(wire.Vertexes) - 1
        lstVrt = wire.Vertexes[lstVrtIdx]
        frstVrt = wire.Vertexes[0]
        cent0 = FreeCAD.Vector(frstVrt.X, frstVrt.Y, 0.0)
        cent1 = FreeCAD.Vector(lstVrt.X, lstVrt.Y, 0.0)

        # Calculate offset shape, containing cut region
        ofstShp = self._getOffsetArea(cutShp, False)
        if not ofstShp:
            self._addDebugObject("error_cutShape", cutShp)
            return list()

        self._addDebugObject("OffsetShape", ofstShp)
        """
        # Alternative method to better switch sides for Inside/Outside profile
        if self.useOtherSide and False:
            # save original offset value
            origOffsetValue = self.offsetRadius
            self.offsetRadius *= 2.0
            # offset current offset twice original value in opposite direction
            newOfstShp = self._getOffsetArea(ofstShp, True)
            if not newOfstShp:
                PathLog.error("failed reverse offset for other side")
                return list()
            # Restore original offsetRadius value
            self.offsetRadius = origOffsetValue
            self._addDebugObject('newOfstShp', newOfstShp)
            # make common of wire BB face and new offset
            newOfstTrimmed = self.wireBoundBoxFaceAtZero.common(newOfstShp)
            # cut out other Path Stops
            newEndsIn = newOfstTrimmed.cut(self.pathStops)
            # re-assign as new offset shape
            self._addDebugObject('newEndsIn', newEndsIn)
        """

        numOSWires = len(ofstShp.Wires)
        for w in range(0, numOSWires):
            osWrIdxs.append(w)

        # Identify two vertexes for dividing offset loop
        NEAR0 = self._findNearestVertex(ofstShp, cent0)
        min0i = 0
        min0 = NEAR0[0][4]
        for n in range(0, len(NEAR0)):
            N = NEAR0[n]
            if N[4] < min0:
                min0 = N[4]
                min0i = n
        (w0, vi0, pnt0, _, _) = NEAR0[0]  # min0i
        # self._addDebugObject("Near0", Part.makeLine(cent0, pnt0))

        NEAR1 = self._findNearestVertex(ofstShp, cent1)
        min1i = 0
        min1 = NEAR1[0][4]
        for n in range(0, len(NEAR1)):
            N = NEAR1[n]
            if N[4] < min1:
                min1 = N[4]
                min1i = n
        (w1, vi1, pnt1, _, _) = NEAR1[0]  # min1i
        # self._addDebugObject("Near1", Part.makeLine(cent1, pnt1))

        if w0 != w1:
            PathLog.warning(
                "Offset wire endpoint indexes are not equal - w0, w1: {}, {}".format(
                    w0, w1
                )
            )

        if self.isDebug and False:  # remove False to add these comments when debugging
            self._debugMsg("min0i is {}.".format(min0i))
            self._debugMsg("min1i is {}.".format(min1i))
            self._debugMsg("NEAR0[{}] is {}.".format(w0, NEAR0[w0]))
            self._debugMsg("NEAR1[{}] is {}.".format(w1, NEAR1[w1]))
            self._debugMsg("NEAR0 is {}.".format(NEAR0))
            self._debugMsg("NEAR1 is {}.".format(NEAR1))

        mainWire = ofstShp.Wires[w0]
        self._addDebugObject("mainWire", mainWire)

        # Check for additional closed loops in offset wire by checking distance to iTAG or eTAG elements
        if numOSWires > 1:
            self._debugMsg("Number of offset wires > 1")
            # check all wires for proximity(children) to intersection tags
            tagsComList = list()
            for T in self.cutSideTags.Faces:
                tcom = T.CenterOfMass
                tv = FreeCAD.Vector(tcom.x, tcom.y, 0.0)
                tagsComList.append(tv)
            subDist = self.offsetRadius * subDistFactor
            for w in osWrIdxs:
                if w != w0:
                    cutSub = False
                    VTXS = ofstShp.Wires[w].Vertexes
                    for V in VTXS:
                        v = FreeCAD.Vector(V.X, V.Y, 0.0)
                        for t in tagsComList:
                            if t.sub(v).Length < subDist:
                                cutSub = True
                                break
                        if cutSub is True:
                            break
                    if cutSub is True:
                        sub = Part.Wire(Part.__sortEdges__(ofstShp.Wires[w].Edges))
                        subLoops.append(sub)
                # Eif

        # Break offset loop into two wires - one of which is the desired profile path wire.
        (part0, part1) = PathTargetBuildUtils.splitClosedWireAtTwoVertexes(
            mainWire, mainWire.Vertexes[vi0], mainWire.Vertexes[vi1], self.jobTolerance
        )

        # Determine which part is nearest original edge(s) by using distance between wire midpoints
        # Calculate midpoints of wires
        mpA = self._findWireMidpoint(self.sortedFlatWire.Wires[0])
        mp0 = self._findWireMidpoint(part0.Wires[0])
        mp1 = self._findWireMidpoint(part1.Wires[0])

        if mpA.sub(mp0).Length < mpA.sub(mp1).Length:
            rtnWIRES.append(part0)
        else:
            rtnWIRES.append(part1)
        rtnWIRES.extend(subLoops)

        for w in rtnWIRES:
            w.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - w.BoundBox.ZMin))

        return rtnWIRES

    def _getOffsetArea(self, fcShape, isHole):
        """Get an offset area for a shape. Wrapper around
        PathUtils.getOffsetArea."""
        self._debugMsg("_getOffsetArea()")

        offset = self.offsetRadius

        if isHole is False:
            offset = 0 - offset

        ofstShp = PathUtils.getOffsetArea(
            fcShape, offset, plane=Part.makeCircle(5.0), tolerance=self.jobTolerance
        )

        # CHECK for ZERO area of offset shape
        try:
            if not hasattr(ofstShp, "Area") or not ofstShp.Area:
                PathLog.error("No area to offset shape returned. 1")
                self.errorshape = fcShape
                return None
        except Exception as ee:
            PathLog.error("No area to offset shape returned. 2 {}".format(ee))
            self.errorshape = fcShape
            return None

        return ofstShp

    def _findNearestVertex(self, shape, point):
        self._debugMsg("_findNearestVertex()")
        points = list()
        testPnt = FreeCAD.Vector(point.x, point.y, 0.0)

        def sortDist(tup):
            return tup[4]

        for w in range(0, len(shape.Wires)):
            WR = shape.Wires[w]
            V = WR.Vertexes[0]
            P = FreeCAD.Vector(V.X, V.Y, 0.0)
            dist = P.sub(testPnt).Length
            vi = 0
            pnt = P
            vrt = V
            for v in range(0, len(WR.Vertexes)):
                V = WR.Vertexes[v]
                P = FreeCAD.Vector(V.X, V.Y, 0.0)
                d = P.sub(testPnt).Length
                if d < dist:
                    dist = d
                    vi = v
                    pnt = P
                    vrt = V
            points.append((w, vi, pnt, vrt, dist))
        points.sort(key=sortDist)
        return points

    def _makeCrossSection(self, shape, sliceZ, zHghtTrgt=False):
        """_makeCrossSection(shape, sliceZ, zHghtTrgt=None)...
        Creates cross-section objectc from shape.  Translates cross-section to zHghtTrgt if available.
        Makes face shape from cross-section object. Returns face shape at zHghtTrgt."""
        self._debugMsg("_makeCrossSection()")
        # Create cross-section of shape and translate
        wires = list()
        slcs = shape.slice(FreeCAD.Vector(0, 0, 1), sliceZ)
        if len(slcs) > 0:
            for i in slcs:
                wires.append(i)
            comp = Part.Compound(wires)
            if zHghtTrgt is not False:
                comp.translate(FreeCAD.Vector(0, 0, zHghtTrgt - comp.BoundBox.ZMin))
            return comp

        return False

    def _makeExtendedBoundBox(self, wBB, bbBfr, zDep):
        self._debugMsg("_makeExtendedBoundBox()")
        p1 = FreeCAD.Vector(wBB.XMin - bbBfr, wBB.YMin - bbBfr, zDep)
        p2 = FreeCAD.Vector(wBB.XMax + bbBfr, wBB.YMin - bbBfr, zDep)
        p3 = FreeCAD.Vector(wBB.XMax + bbBfr, wBB.YMax + bbBfr, zDep)
        p4 = FreeCAD.Vector(wBB.XMin - bbBfr, wBB.YMax + bbBfr, zDep)

        L1 = Part.makeLine(p1, p2)
        L2 = Part.makeLine(p2, p3)
        L3 = Part.makeLine(p3, p4)
        L4 = Part.makeLine(p4, p1)

        return Part.Face(Part.Wire([L1, L2, L3, L4]))

    def _makeIntersectionTags(self, useWire, numOrigEdges, fdv):
        self._debugMsg("_makeIntersectionTags()")
        # Create circular probe tags around perimiter of wire
        extTags = list()
        intTags = list()
        tagRad = self.toolRadius / 2
        tagCnt = 0
        begInt = False
        begExt = False
        for e in range(0, numOrigEdges):
            E = useWire.Edges[e]
            LE = E.Length
            if LE > (self.toolRadius * 2):
                nt = math.ceil(
                    LE / (tagRad * math.pi)
                )  # (tagRad * 2 * math.pi) is circumference
            else:
                nt = 4  # desired + 1
            mid = LE / nt
            spc = self.toolRadius / 10
            for i in range(0, int(nt)):
                if i == 0:
                    if e == 0:
                        if LE > 0.2:
                            aspc = 0.1
                        else:
                            aspc = LE * 0.75
                        cp1 = E.valueAt(E.getParameterByLength(0))
                        cp2 = E.valueAt(E.getParameterByLength(aspc))
                        (intTObj, extTObj) = self._makeOffsetCircleTag(
                            cp1, cp2, tagRad, fdv, "BeginEdge[{}]_".format(e)
                        )
                        if intTObj and extTObj:
                            begInt = intTObj
                            begExt = extTObj
                else:
                    d = i * mid
                    negTestLen = d - spc
                    if negTestLen < 0:
                        negTestLen = d - (LE * 0.25)
                    posTestLen = d + spc
                    if posTestLen > LE:
                        posTestLen = d + (LE * 0.25)
                    cp1 = E.valueAt(E.getParameterByLength(negTestLen))
                    cp2 = E.valueAt(E.getParameterByLength(posTestLen))
                    (intTObj, extTObj) = self._makeOffsetCircleTag(
                        cp1, cp2, tagRad, fdv, "Edge[{}]_".format(e)
                    )
                    if intTObj and extTObj:
                        tagCnt += nt
                        intTags.append(intTObj)
                        extTags.append(extTObj)
        # tagArea = math.pi * tagRad**2 * tagCnt
        iTAG = Part.makeCompound(intTags)
        eTAG = Part.makeCompound(extTags)

        return (begInt, begExt, iTAG, eTAG)

    def _makeOffsetCircleTag(self, p1, p2, cutterRad, depth, lbl, reverse=False):
        # self._debugMsg('_makeOffsetCircleTag()')
        pb = FreeCAD.Vector(p1.x, p1.y, 0.0)
        pe = FreeCAD.Vector(p2.x, p2.y, 0.0)

        toMid = pe.sub(pb).multiply(0.5)
        lenToMid = toMid.Length
        if lenToMid == 0.0:
            # Probably a vertical line segment
            return (False, False)

        cutFactor = (
            cutterRad / 2.1
        ) / lenToMid  # = 2 is tangent to wire; > 2 allows tag to overlap wire; < 2 pulls tag away from wire
        perpE = FreeCAD.Vector(-1 * toMid.y, toMid.x, 0.0).multiply(
            -1 * cutFactor
        )  # exterior tag
        extPnt = pb.add(toMid.add(perpE))

        # make exterior tag
        eCntr = extPnt.add(FreeCAD.Vector(0, 0, depth))
        ecw = Part.Wire(Part.makeCircle((cutterRad / 2), eCntr).Edges[0])
        extTag = Part.Face(ecw)

        # make interior tag
        perpI = FreeCAD.Vector(-1 * toMid.y, toMid.x, 0.0).multiply(
            cutFactor
        )  # interior tag
        intPnt = pb.add(toMid.add(perpI))
        iCntr = intPnt.add(FreeCAD.Vector(0, 0, depth))
        icw = Part.Wire(Part.makeCircle((cutterRad / 2), iCntr).Edges[0])
        intTag = Part.Face(icw)

        return (intTag, extTag)

    def _makeStop(self, sType, pA, pB, lbl):
        # self._debugMsg('_makeStop()')
        ofstRad = self.offsetRadius
        extra = self.toolRadius / 5.0
        lng = 0.05
        med = lng / 2.0
        shrt = lng / 5.0

        E = FreeCAD.Vector(pB.x, pB.y, 0)  # endpoint
        C = FreeCAD.Vector(pA.x, pA.y, 0)  # checkpoint

        if self.useToolComp is True or (
            self.useToolComp is False and self.offsetExtra != 0
        ):
            # 'L' stop shape and edge map
            # --1--
            # |   |
            # 2   6
            # |   |
            # |   ----5----|
            # |            4
            # -----3-------|
            # positive dist in _makePerp2DVector() is CCW rotation
            p1 = E
            if sType == "BEG":
                p2 = self._makePerp2DVector(C, E, -1 * shrt)  # E1
                p3 = self._makePerp2DVector(p1, p2, ofstRad + lng + extra)  # E2
                p4 = self._makePerp2DVector(p2, p3, shrt + ofstRad + extra)  # E3
                p5 = self._makePerp2DVector(p3, p4, lng + extra)  # E4
                p6 = self._makePerp2DVector(p4, p5, ofstRad + extra)  # E5
            elif sType == "END":
                p2 = self._makePerp2DVector(C, E, shrt)  # E1
                p3 = self._makePerp2DVector(p1, p2, -1 * (ofstRad + lng + extra))  # E2
                p4 = self._makePerp2DVector(p2, p3, -1 * (shrt + ofstRad + extra))  # E3
                p5 = self._makePerp2DVector(p3, p4, -1 * (lng + extra))  # E4
                p6 = self._makePerp2DVector(p4, p5, -1 * (ofstRad + extra))  # E5
            p7 = E  # E6
            L1 = Part.makeLine(p1, p2)
            L2 = Part.makeLine(p2, p3)
            L3 = Part.makeLine(p3, p4)
            L4 = Part.makeLine(p4, p5)
            L5 = Part.makeLine(p5, p6)
            L6 = Part.makeLine(p6, p7)
            wire = Part.Wire([L1, L2, L3, L4, L5, L6])
        else:
            # 'L' stop shape and edge map
            # :
            # |----2-------|
            # 3            1
            # |-----4------|
            # positive dist in _makePerp2DVector() is CCW rotation
            p1 = E
            if sType == "BEG":
                p2 = self._makePerp2DVector(
                    C, E, -1 * (shrt + abs(self.offsetExtra))
                )  # left, shrt
                p3 = self._makePerp2DVector(p1, p2, shrt + abs(self.offsetExtra))
                p4 = self._makePerp2DVector(
                    p2, p3, (med + abs(self.offsetExtra))
                )  #      FIRST POINT
                p5 = self._makePerp2DVector(
                    p3, p4, shrt + abs(self.offsetExtra)
                )  # E1                SECOND
            elif sType == "END":
                p2 = self._makePerp2DVector(
                    C, E, (shrt + abs(self.offsetExtra))
                )  # left, shrt
                p3 = self._makePerp2DVector(p1, p2, -1 * (shrt + abs(self.offsetExtra)))
                p4 = self._makePerp2DVector(
                    p2, p3, -1 * (med + abs(self.offsetExtra))
                )  #      FIRST POINT
                p5 = self._makePerp2DVector(
                    p3, p4, -1 * (shrt + abs(self.offsetExtra))
                )  # E1                SECOND
            p6 = p1  # E4
            L1 = Part.makeLine(p1, p2)
            L2 = Part.makeLine(p2, p3)
            L3 = Part.makeLine(p3, p4)
            L4 = Part.makeLine(p4, p5)
            L5 = Part.makeLine(p5, p6)
            wire = Part.Wire([L1, L2, L3, L4, L5])
        # Eif
        face = Part.Face(wire)
        self._addDebugObject(lbl, face)

        return face

    def _makePerp2DVector(self, v1, v2, dist):
        p1 = FreeCAD.Vector(v1.x, v1.y, 0.0)
        p2 = FreeCAD.Vector(v2.x, v2.y, 0.0)
        toEnd = p2.sub(p1)
        factor = dist / toEnd.Length
        perp = FreeCAD.Vector(-1 * toEnd.y, toEnd.x, 0.0).multiply(factor)
        return p1.add(toEnd.add(perp))

    def _findWireMidpoint(self, wire):
        midPnt = None
        dist = 0.0
        wL = wire.Length
        midW = wL / 2

        for e in range(0, len(wire.Edges)):
            E = wire.Edges[e]
            elen = E.Length
            d_ = dist + elen
            if dist < midW and midW <= d_:
                dtm = midW - dist
                midPnt = E.valueAt(E.getParameterByLength(dtm))
                break
            else:
                dist += elen
        return midPnt

    def _altOffsetMethod(self):
        import PathScripts.PathOpTools as PathOpTools

        try:
            altOffsetWire = PathOpTools.offsetWire(
                wire=self.wire,
                base=self.baseShape,
                offset=self.offsetRadius,
                forward=True,
            )
            self._addDebugObject("altOffsetWire", altOffsetWire)
        except:
            self._debugMsg("Failed to offset wire using PathOpTools.offsetWire().")
            return

    # Public method
    def getOpenEdges(self):
        openEdges = list()
        wire = self.wire

        # Uncommnet to debug OpenEdge class only
        # self.isDebug = True  ##############################################################################

        if self.jobTolerance == 0.0:
            msg = self.jobLabel + "GeometryTolerance = 0.0. "
            msg += translate(
                "PathTargetOpenEdge",
                "Please set to an acceptable value greater than zero.",
            )
            PathLog.error(msg)
            return openEdges

        zDiff = math.fabs(wire.BoundBox.ZMin - self.geomFinalDepth)
        if zDiff < self.jobTolerance:
            msg = translate(
                "PathProfile",
                "Check edge selection and Final Depth requirements for profiling open edge(s).",
            )
            PathLog.debug(msg)

        flatWire = PathTargetBuildUtils.flattenWireSingleLoop(wire, self.geomFinalDepth)
        if not flatWire:
            PathLog.error(self.inaccessibleMsg + " 2")
            return openEdges
        self._addDebugObject("FlatWire", flatWire)

        # Start process for extracting openEdge offset wire
        self.sortedFlatWire = Part.Wire(
            Part.__sortEdges__(flatWire.Wires[0].Edges)
        )  # complex selections need edges sorted
        cutShp = self._getCutAreaCrossSection(wire, flatWire)

        if cutShp:
            cutWireObjs = self._extractPathWire(flatWire, cutShp)

            if cutWireObjs:
                for cW in cutWireObjs:
                    openEdges.append(cW)
            else:
                PathLog.error(self.inaccessibleMsg + " 3")

        # self._altOffsetMethod()  # fails on bspline wires and other situations

        return openEdges


# Eclass
