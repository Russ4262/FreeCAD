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


class Target3DShape:
    """class Target3DShape
    This class processes user inputs through both the Base Geometry and Extensions features,
    combining connected or overlapping regions when necessary, and returns a list
    of working areas represented by faces."""

    def __init__(
        self,
        baseObjectList,
        extensions=None,
        processPerimeter=False,
        processHoles=False,
        processCircles=False,
        handleMultipleFeatures="Collectively",
        startDepth=None,
        finalDepth=None,
    ):
        """__init__(baseObjectList, extensions=None, processPerimeter=False, processHoles=False, processCircles=False, handleMultipleFeatures="Collectively", startDepth=None, finalDepth=None)
        The baseObjectList is expected to be a pointer to obj.Base.
        """
        self.baseObjectList = baseObjectList
        self.extensions = extensions
        self.processCircles = processCircles
        self.processHoles = processHoles
        self.processPerimeter = processPerimeter
        self.handleMultipleFeatures = handleMultipleFeatures
        self.startDepth = startDepth
        self.finalDepth = finalDepth
        self.rawAreas = list()
        self.rawSolids = list()
        self.rawHoles = list()
        self.extensionFaces = list()
        self.workingSolids = list()
        self.workingAreas = list()
        self.workingHoles = list()
        self.targetSolidTups = list()
        self.targetAreaTups = list()
        self.targetHoleTups = list()
        self.fullBaseDict = dict()
        self.subs = dict()
        self.vert = list()
        self.nonVerticalFaces = list()
        self.edges = list()
        self.avoidFeatures = list()
        self.baseObj = None
        self.baseSubsTups = None
        self.processInternals = False
        self.stockProcessed = False
        self.baseFacesDict = dict()
        self.overheadRegionsDict = (
            dict()
        )  # Save overhead regions by base.Name for external class access
        self.avoidOverhead = False

        if processHoles or processCircles:
            self.processInternals = True

        # Sort bases and related faces
        for base, subsList in baseObjectList:
            self.baseFacesDict[base.Name] = [
                base.Shape.getElement(sub) for sub in subsList if sub.startswith("Face")
            ]

        # Identify extension faces to avoid
        if self.extensions:
            for e in self.extensions:
                if e.avoid:
                    self.avoidFeatures.append(e.feature)

        # Debugging attributes
        self.isDebug = False
        self.showDebugShapes = False

    # Private methods
    def _debugMsg(self, msg):
        """_debugMsg(msg)
        If `self.isDebug` flag is True, the provided message is printed in the Report View.
        If not, then the message is assigned a debug status.
        """
        if self.isDebug:
            # PathLog.info(msg)
            FreeCAD.Console.PrintMessage(
                "PathTarget3DShape.Target3DShape: " + msg + "\n"
            )
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

    def _processBaseSubsList(self):
        """_processBaseSubsList()...
        This method processes the base objects list (obj.Base). It assesses selected
        faces and edges to determine if they are acceptable.
        A vertical face loop is converted to a horizontal working area.
        A set of closed edges are converted to a horizontal working area.
        Non-horizontally planar faces are regected.
        """

        # Get faces selected by user
        for base, subs in self.baseSubsTups:
            self.baseObj = base
            self.subs[base.Name] = subs
            for sub in subs:
                # Sort features in Base Geometry selection
                if sub.startswith("Face"):
                    if sub not in self.avoidFeatures:
                        if not self._clasifyFace(base, sub):
                            msg = "%s.%s is vertical. Ignoring." % (base.Label, sub)
                            self._debugMsg("Working3DFaces: " + msg)
                elif sub.startswith("Edge"):
                    self.edges.append(base.Shape.getElement(sub))
                else:
                    msgNoSupport = translate(
                        "PathPocket", "Pocket does not support shape %s.%s"
                    ) % (base.Label, sub)
                    PathLog.info(msgNoSupport)

            subCnt = len(subs)
            if subCnt == 0:
                self._debugMsg("_processBaseSubsList() {}: No subs".format(base.Name))
                self._processEntireBase()
            else:
                self._debugMsg(
                    "_processBaseSubsList() {}: {} subs".format(base.Name, subCnt)
                )
                self._processEdges()
                self._processFaces()

            # Reset lists
            self.nonVerticalFaces = list()
            self.edges = list()
        # Efor

    def _clasifyFace(self, baseObject, sub):
        """_clasifyFace(baseObject, sub)...
        Given a base object, a sub-feature name,
        this function returns True if the sub-feature is a horizontally or vertically
        oriented face. The face need not be flat to be considered vertically oriented,
        such as a bspline that is vertically extruded. All other faces are placed
        in a `neither` list.
        """
        vertical = True

        face = baseObject.Shape.getElement(sub)

        if type(face.Surface) == Part.Sphere:
            vertical = False
        elif type(face.Surface) == Part.Cylinder or type(face.Surface) == Part.Cone:
            vertical = isVertical(face.Surface.normal(0, 0))
        else:
            vertical = isVertical(face)

        if vertical:
            self.vert.append(face)
            self._debugMsg("_clasifyFace({}) vertical".format(sub))
            return False

        self.nonVerticalFaces.append(face)
        self._debugMsg("_clasifyFace({}) non-vertical".format(sub))
        return True

    def _processEntireBase(self):
        """_processEntireBase()... Process entire base shape into working 3D solid."""
        self._debugMsg("_processEntireBase()")

        name = self.baseObj.Name
        if name not in self.fullBaseDict.keys():
            solidBase = self._processSolid(self.baseObj.Shape)
            self.fullBaseDict[name] = solidBase
            self.rawSolids.append(solidBase)
            self.avoidOverhead = False  # Cancel overhead collision detection

    def _processSolid(self, solidShape):
        """_processSolid(solidShape)... Process solid shape into working solid base.
        This process eliminates overhangs and voids in solid below top surfaces.
        """
        self._debugMsg("_processSolid()")

        bsBB = solidShape.BoundBox
        extent = math.floor(bsBB.ZLength + 2.0)
        extrudedFaces = PathTargetBuildUtils.extrudeNonVerticalFaces(
            solidShape.Faces, -1 * extent
        )
        fused = PathTargetBuildUtils.fuseShapes(extrudedFaces)
        box = Part.makeBox(bsBB.XLength + 10.0, bsBB.YLength + 10.0, extent + 5.0)
        box.translate(
            FreeCAD.Vector(bsBB.XMin - 5.0, bsBB.YMin - 5.0, -1.0 * (extent + 5.0))
        )
        surfaceBase = fused.cut(box)

        baseEnv = PathTargetBuildUtils.getBaseCrossSection(
            solidShape, includeInternals=False
        )
        baseEnv.translate(FreeCAD.Vector(0.0, 0.0, bsBB.ZMin - baseEnv.BoundBox.ZMin))
        baseEnvExt = baseEnv.extrude(FreeCAD.Vector(0.0, 0.0, bsBB.ZLength))
        solidBase = baseEnvExt.cut(surfaceBase).removeSplitter()
        return solidBase

    def _processEdges(self):
        """_processEdges()... Process selected edges.
        Attempt to identify closed areas from selected edges.
        Project closed areas onto base shape and add common 3D solid to working solids list."""
        self._debugMsg("_processEdges()")

        if not self.edges:
            return

        # Attempt to identify closed areas from selected edges
        closedAreas = self._identifyClosedAreas()
        if not closedAreas:
            return

        # Translate closed areas to bottom of base shape and extrude closed areas upward
        boBB = self.baseObj.Shape.BoundBox
        caComp = Part.makeCompound(closedAreas)
        caComp.translate(FreeCAD.Vector(0.0, 0.0, boBB.ZMin))
        extent = math.floor((boBB.ZLength) * 10.0)
        fusion = PathTargetBuildUtils.extrudeFacesToSolid(caComp.Faces, extent)

        # Get common solid with extrusion and base shape
        targetSolid = self.baseObj.Shape.common(fusion)

        # Process solid into usable 3D envelope shape for working solid
        solidBase = self._processSolid(targetSolid)

        self.rawSolids.append(solidBase)
        self.avoidOverhead = False  # Cancel overhead collision detection

    def _identifyClosedAreas(self):
        """_identifyClosedAreas()... Attempt to identify a closed wire
        from a set of edges.  If closed, return a horizontal cross-section
        of the closed wire."""
        self._debugMsg("_identifyClosedAreas()")

        closedAreas = list()
        # edges = Part.makeCompound(self.edges)
        wires = DraftGeomUtils.findWires(self.edges)
        if wires:
            for w in wires:
                if w.isClosed():
                    face = Part.Face(PathTargetBuildUtils.flattenWireSingleLoop(w))
                    if face.Area > 0.0:
                        closedAreas.append(face)
                        # self.baseFacesDict[self.baseObj.Name].append(face)
                    else:
                        msg = translate("PathGeom", "No face from selected edges.")
                        PathLog.error("Working3DAreas: " + msg)
                else:
                    msg = translate("PathGeom", "Not a closed wire.")
                    self._debugMsg("Working3DAreas: " + msg)
                    # self.rawOpenEdgeBaseTups.append((self.baseObj, w))  # Later processing of open edges in Profile module
                    pass
        else:
            msg = translate("PathGeom", "No wire from selected edges.")
            PathLog.error("Working2DAreas: " + msg)

        return closedAreas

    def _processFaces(self):
        """_processFaces()... Process selected faces into working 3D solid."""
        self._debugMsg("_processFaces()")

        if not self.nonVerticalFaces:
            return

        self._processExtensions()

        self._addDebugObject(
            Part.makeCompound(self.nonVerticalFaces), "nonVerticalFaces"
        )

        # Extrude well beyond start depth, and fuse to solid
        extent = math.floor((self.baseObj.Shape.BoundBox.ZLength) * 10.0)
        fusion = PathTargetBuildUtils.extrudeFacesToSolid(self.nonVerticalFaces, extent)
        if not fusion:
            return

        self._addDebugObject(fusion, "fusion")

        # Get cross-sectional faces
        # csFaces = self._getCrossSections(fusion)  # for later feature/capability expansion
        # self._addDebugObject(Part.makeCompound(csFaces), "csFaces")

        # Trim extrusion to start height
        trimmed = self._trimExtrusion(fusion, self.startDepth)
        self._addDebugObject(trimmed, "fusion_trimmed")

        self._debugMsg("_processFaces() trimmed.Volume = {}".format(trimmed.Volume))
        self.rawSolids.append(trimmed)

    def _processExtensions(self):
        """_processExtensions()...
        This method processes any available extension faces from the Extensions feature.
        """
        if not self.extensions:
            return

        # Apply regular Extensions
        for ext in self.extensions:
            # verify extension is not an avoided face
            # verify extension pertains to active base object (model)
            # verify extension feature is in active subs list
            if (
                not ext.avoid
                and ext.obj.Name == self.baseObj.Name
                and ext.feature in self.subs[self.baseObj.Name]
            ):
                self._debugMsg("Adding extension for {}".format(ext.feature))
                wire = ext.getWire()
                if wire:
                    self.avoidOverhead = False  # disable overhead check, temporarily
                    self._debugMsg("Overhead check disabled due to extensions.")
                    for f in ext.getExtensionFaces(wire):
                        self.nonVerticalFaces.append(f)

    def _getCrossSections(self, fusion):
        csFaces = list()
        boBB = self.baseObj.Shape.BoundBox
        height = math.floor((boBB.ZLength) * 5.0 + boBB.ZMin)
        trimmed = self._trimExtrusion(fusion, height)
        for f in trimmed.Faces:
            if isRoughly(f.BoundBox.ZMin, height):
                csFaces.append(f)
        return csFaces

    def _trimExtrusion(self, extShape, height):
        extrusion = Part.makeSolid(extShape.Shells[0])
        extBB = extrusion.BoundBox
        box = Part.makeBox(
            extBB.XLength + 2.0, extBB.YLength + 2.0, math.floor(extBB.ZLength + 2.0)
        )
        move = FreeCAD.Vector(extBB.XMin - 1.0, extBB.YMin - 1.0, height)
        box.translate(move)
        self._addDebugObject(box, "trim_box")
        return extrusion.cut(box)

    def _saveHole(self, base, wire):
        """_saveHole(wire)... Analyze hole and save accordingly."""
        self._debugMsg("_saveHole()")

        cont = False
        drillable = PathUtils.isDrillable(self.baseObj, wire)

        if self.processCircles:
            if drillable:
                cont = True
        if self.processHoles:
            if not drillable:
                cont = True

        if cont:
            try:
                face = Part.Face(wire)
            except Exception as ee:
                PathLog.error("{}".format(ee))
                return
            face.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - face.BoundBox.ZMin))
            self.workingHoles.append((base, face))

    def _identifyWorkAreas(self, base):
        """_identifyWorkAreas(base)...
        This method attempts to combine(fuse, merge) all the identified areas
        when possible. This method is what produces the final pocket areas
        that are requested from this class.
        """
        self._debugMsg("_identifyWorkAreas()")
        workingAreas = list()

        if len(self.rawAreas) == 0 or not self.processPerimeter:
            self._debugMsg("no raw faces for _identifyWorkAreas()")
            return

        # Place all faces into same working plane
        for h in self.rawAreas:
            h.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - h.BoundBox.ZMin))

        # Second face-combining method attempted
        chf = PathTargetBuildUtils.combineHorizontalFaces(self.rawAreas)
        if chf:
            self._debugMsg("combineHorizontalFaces count: {}".format(len(chf)))
            i = 0
            for f in chf:
                i += 1
                self._addDebugObject(f, "combineHorizontalFaces_{}".format(i))

                if self.processPerimeter and self.processHoles and self.processCircles:
                    workingAreas.append(f)
                else:
                    workingAreas.append(Part.Face(f.Wires[0]))

                if self.processInternals:
                    # save any holes
                    for wire in f.Wires[1:]:
                        self._saveHole(base, wire)

        for a in workingAreas:
            self.workingAreas.append((base, a))

    def _applyAvoidOverhead(self, base):
        """_applyAvoidOverhead(base)...
        Create overhead regions and apply collision therewith to working shapes.
        """
        self._debugMsg("_applyAvoidOverhead({})".format(base.Name))

        if not self.avoidOverhead or (
            not self.rawSolids and not self.rawHoles and not self.rawAreas
        ):
            self._debugMsg("Canceling _applyAvoidOverhead()")
            return

        # Save overhead regions by base.Name for external class access
        faceList = self.baseFacesDict[base.Name]
        overheadRegions = PathTargetBuildUtils.getOverheadRegions3D(
            base.Shape, faceList
        )
        self.overheadRegionsDict[base.Name] = overheadRegions
        try:
            if (
                not overheadRegions
                or not hasattr(overheadRegions, "Volume")
                or overheadRegions.Volume == 0.0
            ):
                self._debugMsg("No overhead regions to avoid")
                return
        except:
            self._debugMsg("No overhead regions to avoid")
            return

        self._addDebugObject(
            overheadRegions, objName="{}_overheadRegions".format(base.Name)
        )

        # Cut overhead shape from working shapes
        if self.rawSolids:
            self._debugMsg("pre-overhead solids count: {}".format(len(self.rawSolids)))
            safeSolids = [ws.cut(overheadRegions) for ws in self.rawSolids]
            self.rawSolids = safeSolids
            self._debugMsg("post-overhead solids count: {}".format(len(self.rawSolids)))

        if self.processInternals and self.rawHoles:
            self._debugMsg("pre-overhead holes count: {}".format(len(self.rawHoles)))
            safeHoles = [ws.cut(overheadRegions) for ws in self.rawHoles]
            self.rawHoles = safeHoles

    def _finishProcessing(self):
        # Move bottom of solids to final depth is the idea.  This will likely require more complexity to correctly implement.
        if self.workingSolids:
            for s in self.workingSolids:
                s.translate(FreeCAD.Vector(0.0, 0.0, self.finalDepth - s.BoundBox.ZMin))

    def _saveData(self, base):
        for sol in self.rawSolids:
            self.targetSolidTups.append((base, sol))
        for hol in self.rawHoles:
            self.targetHoleTups.append((base, hol))
        self.rawSolids = list()
        self.rawHoles = list()

    # Public method
    def applyMaterialAllowance(self, materialAllowance):
        # Use material allowance as depth offset is plan for code here.
        return

    def buildTargetShapes(self, avoidOverhead=False):
        """buildTargetShapes(avoidOverhead=False)...
        This is the main class control function for identifying pocket areas,
        including extensions to selected faces using input from the Base Geometry
        and Extensions features.
        """
        self._debugMsg("buildTargetShapes()")
        PathLog.track(self.handleMultipleFeatures)

        # Force debug in this class
        self.isDebug = True
        # self.showDebugShapes = True

        self.avoidOverhead = avoidOverhead
        if not self.baseObjectList:
            return list()

        print("Target3DShape.buildTargetShapes()\nstart, final dpeths: {}, {}".format(self.startDepth, self.finalDepth))
        
        # Procede with processing based upon handleMultipleFeatures setting
        if self.handleMultipleFeatures == "Collectively":
            for tup in self.baseObjectList:
                self.avoidOverhead = avoidOverhead
                self.rawAreas = list()
                self.rawSolids = list()
                self.rawHoles = list()
                self.baseSubsTups = [tup]
                self._processBaseSubsList()
                self._saveData(tup[0])
        else:
            for base, subsList in self.baseObjectList:
                for sub in subsList:
                    self.avoidOverhead = avoidOverhead
                    self.rawAreas = list()
                    self.rawSolids = list()
                    self.rawHoles = list()
                    self.baseSubsTups = [(base, [sub])]
                    self._processBaseSubsList()
                    self._saveData(base)

        # self._finishProcessing()

    def getExtensionFaces(self):
        """getExtensionFaces()... Returns list of extension faces identified"""
        return self.extensionFaces

    def getHoleSolids(self):
        """getHoleSolids()... Returns list of holes (any internal openning in face) identified"""
        return self.workingHoles


# Eclass
