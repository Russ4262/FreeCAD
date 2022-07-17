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
import PathScripts.strategies.PathTargetOpenEdge as PathTargetOpenEdge
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


class Target2DEnvelope:
    """class Working2DAreas
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
        boundaryShape="Face Region",
        stockShape=None,
        finalDepth=None,
    ):
        """__init__(baseObjectList, extensions=None, otherFaces=list())
        The baseObjectList is expected to be a pointer to obj.Base.
        """
        PathLog.debug("Working2DAreas.__init__()")

        self.baseObjectList = baseObjectList
        self.extensions = extensions
        self.processCircles = processCircles
        self.processHoles = processHoles
        self.processPerimeter = processPerimeter
        self.handleMultipleFeatures = handleMultipleFeatures
        self.boundaryShape = boundaryShape
        self.stockShape = stockShape
        self.finalDepth = finalDepth
        self.zMin = finalDepth
        self.overheadFaces = None
        self.workingAreas = list()
        self.extensionFaces = list()
        self.allOuters = list()
        self.workingHoles = list()
        self.avoidFeatures = list()
        self.horiz = list()
        self.vert = list()
        self.allVert = list()
        self.oblique = list()
        self.holes = list()
        self.edges = list()
        self.baseObj = None
        self.baseSubsTups = None
        self.processInternals = False
        self.subs = dict()
        self.stockProcessed = False
        self.avoidOverhead = False
        self.baseFacesDict = dict()
        self.baseOutersDict = dict()
        self.overheadRegionsDict = (
            dict()
        )  # Save overhead regions by base.Name for external class access
        self.basePerimeterDict = dict()  # Save base perimeter by base.Name
        self.disableOverheadCheck = False

        # Open edge usage
        self.rawOpenEdgeBaseTups = list()
        self.openWireTups = list()
        self.openEdges = list()

        if processHoles or processCircles:
            self.processInternals = True

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
                "PathTarget2DEnvelope.Target2DEnvelope: " + msg + "\n"
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
        self._debugMsg("_processBaseSubsList()")

        self.disableOverheadCheck = False

        # Get faces selected by user
        for base, subs in self.baseSubsTups:
            self.baseObj = base
            self.subs[base.Name] = subs

            for sub in subs:
                # Sort features in Base Geometry selection
                subShp = base.Shape.getElement(sub)
                if sub.startswith("Face"):
                    self.baseFacesDict[base.Name].append(subShp)
                    if sub not in self.avoidFeatures:
                        if not self._clasifyFace(base, sub):
                            msg = translate(
                                "PathPocket", "Pocket does not support shape %s.%s"
                            ) % (base.Label, sub)
                            PathLog.error("getWorkingAreas(): " + msg)
                    else:
                        msg = translate("PathPocket", "Avoiding %s.%s") % (
                            base.Label,
                            sub,
                        )
                        self._debugMsg("getWorkingAreas(): " + msg)
                elif sub.startswith("Edge"):
                    self.edges.append(subShp)

            if len(subs) == 0:
                self._debugMsg("{}: No subs".format(base.Name))
                # if self.boundaryShape == 'Face Region':
                #    self.boundaryShape = 'Perimeter'
                if self.boundaryShape == "Boundbox":
                    self.allOuters.append(
                        PathTargetBuildUtils.makeBoundBoxFace(base.Shape.BoundBox)
                    )
                else:
                    bcs = self._getBaseCrossSection(base)
                    if bcs:
                        self.horiz.extend(bcs.Faces)
                self.avoidOverhead = False

            self._identifyLoopedEdges()
            self._processVertFaces()
            self._processHorizFaces()
            self._processHoles()
            self._applyBoundaryShape()

            # Reset lists
            self.horiz = list()
            self.vert = list()
            self.edges = list()
            # self.baseObj = None  # Commented out due to possible need later in successive class methods

            # Disable overhead check for horizontal face only bases
            if isRoughly(base.Shape.BoundBox.ZLength, 0.0):
                self.disableOverheadCheck = True

        # Efor

    def _clasifyFace(self, baseObject, sub):
        """_clasifyFace(baseObject, sub)...
        Given a base object, a sub-feature name,
        this function returns True if the sub-feature is a horizontally or vertically
        oriented face. The face need not be flat to be considered vertically oriented,
        such as a bspline that is vertically extruded. All other faces converted to a
        horizontal cross-section.
        """
        self._debugMsg("_clasifyFace({})".format(sub))

        face = baseObject.Shape.getElement(sub)
        if type(face.Surface) == Part.Cylinder or type(face.Surface) == Part.Cone:
            if not isVertical(face.Surface.normal(0, 0)):
                csFace = PathTargetBuildUtils.flattenFace(face)
                if csFace:
                    # Move cross-section face to ZMax of face
                    csFace.translate(FreeCAD.Vector(0.0, 0.0, face.BoundBox.ZMax))
                    self.horiz.append(csFace)
                else:
                    return False
        if isHorizontal(face):
            self.horiz.append(face)
        elif isVertical(face):
            self.vert.append(face)
        else:
            csFace = PathTargetBuildUtils.flattenFace(face)
            if csFace:
                # Move cross-section face to ZMax of face
                csFace.translate(FreeCAD.Vector(0.0, 0.0, face.BoundBox.ZMax))
                self.horiz.append(csFace)
            else:
                return False

        return True

    def _identifyLoopedEdges(self):
        """_identifyLoopedEdges()... Attempt to identify a closed wire
        from a set of edges.  If closed, return a horizontal cross-section
        of the closed wire."""
        self._debugMsg("_identifyLoopedEdges()")

        if not self.edges:
            return

        self.openWireTups = list()
        horizFaces = list()
        sourceCompound = Part.makeCompound(self.edges)
        wires = DraftGeomUtils.findWires(self.edges)
        if wires:
            for w in wires:
                if w.isClosed():
                    flatWire = PathTargetBuildUtils.flattenWireSingleLoop(w)
                    face = Part.Face(flatWire)
                    if face.Area > 0.0:
                        self._debugMsg("Working2DAreas: Found edge loop")
                        horizFaces.append(face)
                    else:
                        self._debugMsg("Working2DAreas: No face from selected edges.")
                else:
                    self.openWireTups.append(
                        (self.baseObj, w)
                    )  # Later processing of open edges in Profile module
        else:
            msg = translate("PathGeom", "No wire from selected edges.")
            PathLog.error("Working2DAreas: " + msg)

        if horizFaces:
            self._categorizeFaces(horizFaces, sourceCompound)

        # process open wire data
        self._identifyProjectedWireLoop()

    def _identifyProjectedWireLoop(self):
        """_identifyProjectedWireLoop()... Attempt to identify a closed wire
        from a multi-height open wires.  The wires are flattened, then a check for closed wires is completed.
        If found, working faces are created from the closed wires."""
        if not self.openWireTups:
            return

        loopFaces = list()
        flatEdges = list()
        rawOpenEdgeBaseTups = list()
        openWires = [tup[1] for tup in self.openWireTups]
        sourceCompound = Part.makeCompound(openWires)

        # flatten each wire and extract edges
        for w in [PathTargetBuildUtils.flattenWireSingleLoop(w) for w in openWires]:
            flatEdges.extend(w.Edges)

        # Check for closed wires
        wires = DraftGeomUtils.findWires(flatEdges)
        if wires:
            for w in wires:
                if w.isClosed():
                    face = Part.Face(w)
                    if face.Area > 0.0:
                        self._debugMsg("Working2DAreas: Found edge loop")
                        loopFaces.append(face)
                    else:
                        self._debugMsg("Working2DAreas: No face from flattened edges.")
                else:
                    self._debugMsg(
                        "Working2DAreas: Flattened wire is not a closed wire."
                    )
                    rawOpenEdgeBaseTups.append(
                        (self.baseObj, w)
                    )  # Later processing of open edges in Profile module
        else:
            self._debugMsg("Working2DAreas: No wires from flattened edges.")

        if rawOpenEdgeBaseTups:
            self.rawOpenEdgeBaseTups.extend(rawOpenEdgeBaseTups)

        # Identify relationship of loopFaces - some may be holes within larger loop face
        if loopFaces:
            self._categorizeFaces(loopFaces, sourceCompound)

    def _categorizeFaces(self, faceList, sourceCompound):
        """_categorizeFaces(faceList, sourceCompound)...
        Reconstruct proper faces from faces provided in faceList.  Identify if any faces are holes in other faces,
        and apply those holes to those faces.  Reconstructed faces are properly assigned to class variable lists."""
        faces = list()
        holes = list()
        trueFaces = list()
        faceList.sort(key=lambda face: face.Area)  # small to big order

        def findHole(outer, faceList):
            for i in range(0, len(faceList)):
                inner = faceList[i]
                cmn = outer.common(inner)
                if cmn.Area > 0.0:
                    # inner is hole in outer
                    return i
            return -1

        while len(faceList) > 0:
            outer = faceList.pop()
            faces.append(outer)
            idx = 0
            cutFace = False
            while idx >= 0:
                idx = findHole(outer, faceList)
                if idx >= 0:
                    inner = faceList.pop(idx)
                    holes.append(inner)
                    cut = outer.cut(inner)
                    cutFace = True
                    outer = cut
            if cutFace:
                trueFaces.append(outer)

        if trueFaces:
            self.horiz.extend(trueFaces)
            for tf in trueFaces:
                tf.translate(
                    FreeCAD.Vector(
                        0.0, 0.0, sourceCompound.BoundBox.ZMax - tf.BoundBox.ZMin
                    )
                )
                self.baseFacesDict[self.baseObj.Name].append(tf)
        elif faces:
            self.horiz.extend(faces)
            for f in faces:
                f.translate(
                    FreeCAD.Vector(
                        0.0, 0.0, sourceCompound.BoundBox.ZMax - f.BoundBox.ZMin
                    )
                )
                self.baseFacesDict[self.baseObj.Name].append(f)

    def _processVertFaces(self):
        """_processVertFaces()... Attempt to identify a horizontal cross-section
        from a set of vertical faces provided in base subs list."""
        if not self.vert:
            return

        self.allVert.extend(self.vert)

        vert = Part.makeCompound(self.vert)
        horizFaces = PathTargetBuildUtils.getHorizFaceFromVertFaceLoop(self.vert)
        if horizFaces:
            # Translate horizontal faces to bottom of vertical loop
            for f in horizFaces:
                f.translate(
                    FreeCAD.Vector(0.0, 0.0, vert.BoundBox.ZMin - f.BoundBox.ZMin)
                )
            self.horiz.extend(horizFaces)
            return

        self._debugMsg(
            "Working2DAreas: Attempting to convert non-looped vertical faces to open edges."
        )
        lowZMax = min(
            [f.BoundBox.ZMax for f in self.vert]
        )  # determine lowest ZMax in face list
        # Flatten all vertical faces to cross-sectional wires at Z=0.0 height
        flatEdges = list()
        for f in self.vert:
            wire = PathTargetBuildUtils.flattenVerticalFace(f)
            if wire:
                flatEdges.extend(wire.Edges)
            else:
                self._debugMsg(
                    "flattenVerticalFace() failed to return edge(s) for a vertical face."
                )

        # Identify continuous wires from all flat edges of flattend faces above
        wires = DraftGeomUtils.findWires(flatEdges)
        if wires:
            for w in wires:
                w.translate(FreeCAD.Vector(0.0, 0.0, lowZMax - w.BoundBox.ZMin))
                self.rawOpenEdgeBaseTups.append(
                    (self.baseObj, w)
                )  # Later processing of open edges in Profile module

    def _processHorizFaces(self):
        """_processHorizFaces()... Process horizontal faces provided in base subs list."""
        self._debugMsg(
            "_processHorizFaces({})".format(
                len(self.horiz) if len(self.horiz) > 0 else 0
            )
        )

        if not self.horiz:
            return

        for f in self.horiz:
            self.baseOutersDict[self.baseObj.Name].append(Part.Face(f.Wires[0]))

        # Translate horizontal faces to final depth
        for f in self.horiz:
            f.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - f.BoundBox.ZMin))

        if self.processPerimeter:
            for f in self.horiz:
                self.allOuters.append(Part.Face(f.Wires[0]))

        if self.processInternals:
            # Identify all holes
            for f in self.horiz:
                for wire in f.Wires[1:]:
                    self.holes.append(wire)

    def _processHoles(self):
        """_processHoles()... Process holes in horizontal faces provided in base subs list."""
        if not self.holes:
            return

        for wire in self.holes:
            self._saveHole(wire)

    def _saveHole(self, wire):
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
            self.workingHoles.append(face)

    def _applyBoundaryShape(self):
        """_applyBoundaryShape()... Apply user request for boundary shape of selected region(s)."""
        self._debugMsg("_applyBoundaryShape({})".format(self.boundaryShape))

        if self.boundaryShape == "Boundbox":
            comp = Part.makeCompound(self.allOuters)
            self.allOuters = [
                PathTargetBuildUtils.makeBoundBoxFace(
                    comp.BoundBox, offset=0.0, zHeight=0.0
                )
            ]
        elif self.boundaryShape == "Face Region":
            # Default setting, processing faces normally
            pass
        elif self.boundaryShape == "Perimeter":  # Referred to as Outline sometimes
            # Two methods for getting outline: TechDraw.findShapeOutline and self._get_getCrossSectionFace
            # perimeterFace = Part.Face(TechDraw.findShapeOutline(self.baseObj.Shape, 1, FreeCAD.Vector(0, 0, 1)))
            # perimeterFace.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - perimeterFace.BoundBox.ZMin))
            # self.allOuters.append(perimeterFace)

            perimeterFace2 = PathTargetBuildUtils.getCrossSectionFace(
                self.baseObj.Shape
            )
            self.allOuters.append(perimeterFace2)
        elif self.boundaryShape == "Stock" and not self.stockProcessed:
            csFace = PathTargetBuildUtils.getCrossSectionFace(self.stockShape)
            self.allOuters = [csFace]
            self.stockProcessed = True

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

                wire = ext.getWire()
                if wire:
                    for f in ext.getExtensionFaces(wire):
                        self.allOuters.append(f)
                        self.extensionFaces.append(f)

    def _identifyWorkAreas(self):
        """_identifyWorkAreas()...
        This method attempts to combine(fuse, merge) all the identified areas
        when possible. This method is what produces the final pocket areas
        that are requested from this class.
        """
        self._debugMsg("_identifyWorkAreas()")

        if len(self.allOuters) == 0 or not self.processPerimeter:
            self._debugMsg("no raw faces for _identifyWorkAreas()")
            return

        # Place all faces into same working plane
        for h in self.allOuters:
            h.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - h.BoundBox.ZMin))

        # Second face-combining method attempted
        chf = PathTargetBuildUtils.combineHorizontalFaces(self.allOuters)
        if chf:
            self._debugMsg("combineHorizontalFaces count: {}".format(len(chf)))
            i = 0
            for f in chf:
                i += 1
                self._addDebugObject(f, "combineHorizontalFaces_{}".format(i))

                if self.processPerimeter and self.processHoles and self.processCircles:
                    self.workingAreas.append(f)
                else:
                    self.workingAreas.append(Part.Face(f.Wires[0]))

                if self.processInternals:
                    # save any holes
                    for wire in f.Wires[1:]:
                        self._saveHole(wire)

    def _applyAvoidOverhead(self, base):
        """_applyAvoidOverhead(base)...
        Create overhead regions and apply collision therewith to working shapes.
        """
        self._debugMsg("_applyAvoidOverhead({})".format(base.Name))

        if (
            not self.avoidOverhead
            or (not self.workingAreas and not self.workingHoles)
            or self.disableOverheadCheck
        ):
            return

        faceList = self.baseFacesDict[base.Name]
        faceComp = Part.makeCompound(faceList)
        self.zMin = faceComp.BoundBox.ZMax

        if isRoughly(self.zMin, base.Shape.BoundBox.ZMax):
            # cancel overhead collision if faceList is at top of model
            self._debugMsg("Canceling overhead collision check.")
            return

        height = self.finalDepth
        # if not isRoughly(self.zMin - self.finalDepth, 0.0):
        if self.finalDepth < self.zMin:
            height = self.zMin
            # msg = translate('PathGeom', 'Please verify Final Depth.')
            # PathLog.warning(msg)
            msg2 = translate(
                "PathGeom",
                "High point of selection: {} mm.".format(round(self.zMin, 6)),
            )
            PathLog.debug(msg2)

        overhead = self.getOverheadRegions(base, height)
        if not overhead:
            self._debugMsg("_applyAvoidOverhead() No overhead regions")
            return

        self._addDebugObject(faceComp, objName="pre_overheadRegions_facesCompound")
        self._addDebugObject(
            Part.makeCompound(self.workingAreas),
            objName="pre_overheadRegions_workingAreas",
        )
        self._addDebugObject(
            overhead, objName="{}_overheadRegions_{}".format(base.Name, height)
        )

        # PathLog.info('_applyAvoidOverhead() forced return in place before applying overhead regions for collision avoidance')
        # return

        # Cut overhead shape from working shapes
        if self.workingAreas:
            self._debugMsg("pre-overhead area count: {}".format(len(self.workingAreas)))
            safeAreas = [ws.cut(overhead) for ws in self.workingAreas]
            self.workingAreas = safeAreas

        if self.processInternals and self.workingHoles:
            self._debugMsg(
                "pre-overhead holes count: {}".format(len(self.workingHoles))
            )
            safeHoles = [ws.cut(overhead) for ws in self.workingHoles]
            self.workingHoles = safeHoles

    def _getBaseCrossSection(self, base):
        if base.Name in self.basePerimeterDict.keys():
            return self.basePerimeterDict[base.Name]

        bcs = PathTargetBuildUtils.getBaseCrossSection(
            base.Shape, self.processInternals
        )
        self.basePerimeterDict[base.Name] = bcs
        return bcs

    # Public method
    def getWorkingAreas(self, avoidOverhead=False):
        """getWorkingAreas()...
        This is the main class control function for identifying pocket areas,
        including extensions to selected faces using input from the Base Geometry
        and Extensions features.
        """
        PathLog.track(self.handleMultipleFeatures)

        # Force debug in this class
        # self.isDebug = True
        # self.showDebugShapes = True

        self.avoidOverhead = avoidOverhead

        if not self.baseObjectList:
            return list()

        def processBaseSubs():
            self._processBaseSubsList()
            if self.allOuters:
                if self.processInternals and self.workingHoles:
                    pa = Part.Compound(self.allOuters)
                    ah = Part.Compound(self.workingHoles)
                    self.allOuters = [f for f in pa.cut(ah).Faces]
            self._processExtensions()
            self._identifyWorkAreas()
            self.allOuters = list()

        self._debugMsg(
            "HandleMultipleFeatures = {}".format(self.handleMultipleFeatures)
        )

        # Procede with processing based upon handleMultipleFeatures setting
        if self.handleMultipleFeatures == "Collectively":
            for tup in self.baseObjectList:
                self.baseFacesDict[tup[0].Name] = list()
                self.baseOutersDict[tup[0].Name] = list()
                self.baseSubsTups = [tup]
                processBaseSubs()
                self._applyAvoidOverhead(tup[0])
        else:
            for base, subsList in self.baseObjectList:
                self.baseFacesDict[base.Name] = list()
                self.baseOutersDict[base.Name] = list()
                for sub in subsList:
                    self.baseSubsTups = [(base, [sub])]
                    processBaseSubs()
                self._applyAvoidOverhead(base)

        if self.workingAreas:
            if self.isDebug:
                self._debugMsg(
                    "returning {} self.workingAreas".format(len(self.workingAreas))
                )
                self._addDebugObject(Part.Compound(self.workingAreas), "workingAreas")
                pass
            return self.workingAreas

        if self.processInternals and self.workingHoles:
            return self.getHoleAreas()

        if (
            self.handleMultipleFeatures == "Individually"
            and self.allVert
            and not self.workingAreas
        ):
            PathLog.info(
                translate(
                    "PathTarget2DEnvelope",
                    "Verify `HandleMultipleFeatures` property.",
                )
            )

        self._debugMsg("No working areas to return.")
        return None

    def getWorkingSolids(self, avoidOverhead=False):
        """getWorkingSolids()...
        This is a ghost method in place unitl a parent class is created for working areas.
        """
        return list()

    def getExtensionFaces(self):
        """getExtensionFaces()... Returns list of extension faces identified"""
        return self.extensionFaces

    def getHoleAreas(self):
        """getHoleAreas()... Returns list of holes (any internal openning in face) identified"""
        if self.processInternals and self.workingHoles:
            if self.isDebug:
                self._debugMsg("returning self.workingHoles")
                self._addDebugObject(Part.Compound(self.workingHoles), "workingHoles")
                pass
            fusedHoles = PathTargetBuildUtils.fuseShapes(self.workingHoles)
            if fusedHoles:
                self.workingHoles = fusedHoles.Faces
                self._debugMsg(
                    "self.workingHoles count: {}".format(len(self.workingHoles))
                )
                return self.workingHoles

        return None

    def getOpenEdges(
        self, toolRadius, offsetRadius, useToolComp, jobTolerance, jobLabel="Job"
    ):
        """setOpenEdgeAttributes(toolRadius, offsetRadius, jobTolerance, jobLabel='Job')...
        Call this method with arguments after calling `getWorkingAreas()` method.
        This method processes any identified open edges, returning a list
        of offset wires ready for path processing.
        """
        self._debugMsg("getOpenEdges()")

        for (base, wire) in self.rawOpenEdgeBaseTups:
            oe = PathTargetOpenEdge.OpenEdge(
                base.Shape,
                wire,
                self.finalDepth,
                toolRadius,
                offsetRadius,
                useToolComp,
                jobTolerance,
                jobLabel,
            )
            oe.isDebug = self.isDebug  # Transfer debug status
            oe.showDebugShapes = (
                self.showDebugShapes
            )  # Transfer show debug shapes status
            openEdges = oe.getOpenEdges()
            if openEdges:
                self.openEdges.extend(openEdges)

        return self.openEdges

    def getOverheadRegions(self, base, height):
        self._debugMsg("getOverheadRegions({}, height={}mm)".format(base.Name, height))
        # This version uses all above height collision avoidance

        if base.Name in self.overheadRegionsDict.keys():
            return self.overheadRegionsDict[base.Name]

        # orah = getOverheadRegionsAboveHeight(base.Shape, height, self.isDebug and self.showDebugShapes)
        orah = PathTargetBuildUtils.getOverheadRegionsAboveHeight(base.Shape, height)
        if orah:
            self._addDebugObject(orah, "overheadRegion_{}".format(base.Name))
        else:
            self._debugMsg("No overhead regions identified.")
        self.overheadRegionsDict[base.Name] = orah
        return orah

    def getOverheadRegions_3D(self, base, height):
        self._debugMsg(
            "getOverheadRegions_3D({}, height={}mm)".format(base.Name, height)
        )
        # This version uses 3D overhead collision

        if base.Name in self.overheadRegionsDict.keys():
            return self.overheadRegionsDict[base.Name]
        else:
            self.baseFacesDict[base.Name] = list()

        faceList = self.baseFacesDict[base.Name]
        if len(faceList) > 0:
            orah = PathTargetBuildUtils.getOverheadRegionsAboveHeight(
                base.Shape, height
            )
            # orah = getOverheadRegions3D(base.Shape, faceList)
            self.overheadRegionsDict[base.Name] = orah
            return orah
        else:
            PathLog.error("No faces for {}".format(base.Name))
        return None


# Eclass
