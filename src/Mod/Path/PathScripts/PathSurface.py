# -*- coding: utf-8 -*-

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2016 sliptonic <shopinthewoods@gmail.com>               *
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
# *                                                                         *
# *   Additional modifications and contributions beginning 2019             *
# *   by Russell Johnson  <russ4262@gmail.com>                              *
# *                                                                         *
# ***************************************************************************

from __future__ import print_function

import FreeCAD
import MeshPart
import Path
import PathScripts.PathLog as PathLog
import PathScripts.PathUtils as PathUtils
import PathScripts.PathOp as PathOp
from DraftGeomUtils import isPlanar, isCoplanar
from PathScripts.PathGeom import isVertical

from PySide import QtCore
import time
import math
import Part
import Draft

__title__ = "Path Surface Operation"
__author__ = "sliptonic (Brad Collette)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Class and implementation of Mill Facing operation."
__contributors__ = "russ4262 (Russell Johnson), roivai[FreeCAD]"
__created__ = "2016"
__scriptVersion__ = "8a"
__lastModified__ = "2020-01-28 22:59 CST"

PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


# OCL must be installed
try:
    import ocl
except ImportError:
    FreeCAD.Console.PrintError(
        translate("Path_Surface", "This operation requires OpenCamLib to be installed.") + "\n")
    import sys
    sys.exit(translate("Path_Surface", "This operation requires OpenCamLib to be installed."))


class ObjectSurface(PathOp.ObjectOp):
    '''Proxy object for Surfacing operation.'''

    # These are static while document is open, if it contains a 3D Surface Op
    initFinalDepth = None
    initOpFinalDepth = None
    initOpStartDepth = None
    docRestored = False

    def baseObject(self):
        '''baseObject() ... returns super of receiver
        Used to call base implementation in overwritten functions.'''
        return super(self.__class__, self)

    def opFeatures(self, obj):
        '''opFeatures(obj) ... return all standard features and edges based geomtries'''
        return PathOp.FeatureTool | PathOp.FeatureDepths | PathOp.FeatureHeights | PathOp.FeatureStepDown | PathOp.FeatureCoolant | PathOp.FeatureBaseFaces

    def initOperation(self, obj):
        '''initPocketOp(obj) ... create facing specific properties'''
        obj.addProperty("App::PropertyEnumeration", "Algorithm", "Algorithm", QtCore.QT_TRANSLATE_NOOP("App::Property", "The library to use to generate the path"))
        obj.addProperty("App::PropertyEnumeration", "BoundBox", "Algorithm", QtCore.QT_TRANSLATE_NOOP("App::Property", "Should the operation be limited by the stock object or by the bounding box of the base object"))
        obj.addProperty("App::PropertyEnumeration", "DropCutterDir", "Algorithm", QtCore.QT_TRANSLATE_NOOP("App::Property", "The direction along which dropcutter lines are created"))
        obj.addProperty("App::PropertyVectorDistance", "DropCutterExtraOffset", "Algorithm", QtCore.QT_TRANSLATE_NOOP("App::Property", "Additional offset to the selected bounding box"))
        obj.addProperty("App::PropertyEnumeration", "LayerMode", "Algorithm", QtCore.QT_TRANSLATE_NOOP("App::Property", "The completion mode for the operation: single or multi-pass"))
        obj.addProperty("App::PropertyEnumeration", "ScanType", "Algorithm", QtCore.QT_TRANSLATE_NOOP("App::Property", "Planar: Flat, 3D surface scan.  Rotational: 4th-axis rotational scan."))

        obj.addProperty("App::PropertyBool", "OptimizeLinearPaths", "Optimization", QtCore.QT_TRANSLATE_NOOP("App::Property", "Enable optimization of linear paths (co-linear points). Removes unnecessary co-linear points from G-Code output."))
        obj.addProperty("App::PropertyBool", "OptimizeLinearTransitions", "Optimization", QtCore.QT_TRANSLATE_NOOP("App::Property", "Enable separate, more complex optimization of transitions between adjacent linear path segments."))
        obj.addProperty("App::PropertyBool", "OptimizeArcTransitions", "Optimization", QtCore.QT_TRANSLATE_NOOP("App::Property", "Enable separate, more complex optimization of transitions between co-radial arc path segments."))

        obj.addProperty("App::PropertyDistance", "BoundaryAdjustment", "Path", QtCore.QT_TRANSLATE_NOOP("App::Property", "Positive values push the cutter toward, or beyond, the boundary. Negative values retract the cutter away from the boundary."))
        obj.addProperty("App::PropertyBool", "RespectBoundary", "Path", QtCore.QT_TRANSLATE_NOOP("App::Property", "If true, the cutter will remain inside the boundaries of the model or selected face(s)."))

        obj.addProperty("App::PropertyFloat", "CutterTilt", "Rotational", QtCore.QT_TRANSLATE_NOOP("App::Property", "Stop index(angle) for rotational scan"))
        obj.addProperty("App::PropertyEnumeration", "RotationAxis", "Rotational", QtCore.QT_TRANSLATE_NOOP("App::Property", "The model will be rotated around this axis."))
        obj.addProperty("App::PropertyFloat", "StartIndex", "Rotational", QtCore.QT_TRANSLATE_NOOP("App::Property", "Start index(angle) for rotational scan"))
        obj.addProperty("App::PropertyFloat", "StopIndex", "Rotational", QtCore.QT_TRANSLATE_NOOP("App::Property", "Stop index(angle) for rotational scan"))

        obj.addProperty("App::PropertyBool", "CutInternalFeatures", "Surface", QtCore.QT_TRANSLATE_NOOP("App::Property", "Ignore internal feature areas within a larger selected face."))
        obj.addProperty("App::PropertyEnumeration", "CutMode", "Surface", QtCore.QT_TRANSLATE_NOOP("App::Property", "The direction that the toolpath should go around the part: Climb(ClockWise) or Conventional(CounterClockWise)"))
        obj.addProperty("App::PropertyEnumeration", "CutPattern", "Surface", QtCore.QT_TRANSLATE_NOOP("App::Property", "Clearing pattern to use"))
        obj.addProperty("App::PropertyFloat", "CutPatternAngle", "Surface", QtCore.QT_TRANSLATE_NOOP("App::Property", "Yaw angle for certain clearing patterns"))
        obj.addProperty("App::PropertyDistance", "DepthOffset", "Surface", QtCore.QT_TRANSLATE_NOOP("App::Property", "Z-axis offset from the surface of the object"))
        obj.addProperty("App::PropertyBool", "FinishPassOnly", "Surface", QtCore.QT_TRANSLATE_NOOP("App::Property", "Only perform the finish pass: profile and final depth areas."))
        obj.addProperty("App::PropertyEnumeration", "HandleMultipleFeatures", "Surface", QtCore.QT_TRANSLATE_NOOP("App::Property", "Choose how to process multiple Base Geometry features."))
        obj.addProperty("App::PropertyDistance", "SampleInterval", "Surface", QtCore.QT_TRANSLATE_NOOP("App::Property", "The Sample Interval. Small values cause long wait times"))
        obj.addProperty("App::PropertyPercent", "StepOver", "Surface", QtCore.QT_TRANSLATE_NOOP("App::Property", "Step over percentage of the drop cutter path"))
        obj.addProperty("App::PropertyInteger", "AvoidLastXFaces", "Surface", QtCore.QT_TRANSLATE_NOOP("App::Property", "Avoid cutting the last 'X' faces in the Base Geometry list of selected faces."))

        obj.addProperty("App::PropertyBool", "IgnoreWaste", "Waste", QtCore.QT_TRANSLATE_NOOP("App::Property", "Ignore areas that proceed below specified depth."))
        obj.addProperty("App::PropertyFloat", "IgnoreWasteDepth", "Waste", QtCore.QT_TRANSLATE_NOOP("App::Property", "Depth used to identify waste areas to ignore."))
        obj.addProperty("App::PropertyBool", "ReleaseFromWaste", "Waste", QtCore.QT_TRANSLATE_NOOP("App::Property", "Cut through waste to depth at model edge, releasing the model."))

        obj.addProperty("App::PropertyVectorDistance", "StartPoint", "Start Point", QtCore.QT_TRANSLATE_NOOP("PathOp", "The start point of this path"))
        obj.addProperty("App::PropertyBool", "UseStartPoint", "Start Point", QtCore.QT_TRANSLATE_NOOP("PathOp", "Make True, if specifying a Start Point"))

        # For debugging
        obj.addProperty('App::PropertyString', 'AreaParams', 'Debugging')
        obj.setEditorMode('AreaParams', 2)  # hide

        obj.Algorithm = ['OCL Dropcutter', 'OCL Waterline']
        obj.BoundBox = ['BaseBoundBox', 'Stock']
        obj.CutMode = ['Conventional', 'Climb']
        obj.CutPattern = ['Line', 'ZigZag', 'Circular']  # Additional goals ['Offset', 'Spiral', 'ZigZagOffset', 'Grid', 'Triangle']
        obj.DropCutterDir = ['X', 'Y']
        obj.HandleMultipleFeatures = ['Collectively', 'Individually']
        obj.LayerMode = ['Single-pass', 'Multi-pass']
        obj.RotationAxis = ['X', 'Y']
        obj.ScanType = ['Planar', 'Rotational']

        if not hasattr(obj, 'DoNotSetDefaultValues'):
            self.setEditorProperties(obj)
        self.addedAllProperties = True

    def setEditorProperties(self, obj):
        # Used to hide inputs in properties list
        if obj.Algorithm == 'OCL Dropcutter':
            # obj.setEditorMode('DropCutterExtraOffset', 0)
            if obj.ScanType == 'Planar':
                obj.setEditorMode('DropCutterDir', 2)
            elif obj.ScanType == 'Rotational':
                obj.setEditorMode('DropCutterDir', 0)
        else:
            obj.setEditorMode('DropCutterDir', 2)
            # obj.setEditorMode('DropCutterExtraOffset', 2)

        if obj.ScanType == 'Planar':
            obj.setEditorMode('RotationAxis', 2)  # 2=hidden
            obj.setEditorMode('StartIndex', 2)
            obj.setEditorMode('StopIndex', 2)
            obj.setEditorMode('CutterTilt', 2)
        elif obj.ScanType == 'Rotational':
            obj.setEditorMode('RotationAxis', 0)  # 0=show & editable
            obj.setEditorMode('StartIndex', 0)
            obj.setEditorMode('StopIndex', 0)
            obj.setEditorMode('CutterTilt', 0)

        # Disable incomplete feature
        obj.setEditorMode('FinishPassOnly', 2)

        # Disable IgnoreWaste feature
        obj.setEditorMode('IgnoreWaste', 2)
        obj.setEditorMode('IgnoreWasteDepth', 2)
        obj.setEditorMode('ReleaseFromWaste', 2)

    def onChanged(self, obj, prop):
        if hasattr(self, 'addedAllProperties'):
            if self.addedAllProperties is True:
                if prop in ['Algorithm', 'FinishPassOnly', 'LayerMode', 'ScanType', 'CutPattern']:
                    self.setEditorProperties(obj)

    def opOnDocumentRestored(self, obj):
        self.addedAllProperties = True
        self.setEditorProperties(obj)
        # Import FinalDepth from existing operation for use in recompute() operations
        self.initFinalDepth = obj.FinalDepth.Value
        self.initOpFinalDepth = obj.OpFinalDepth.Value
        self.docRestored = True
        PathLog.debug("Imported existing OpFinalDepth of " + str(self.initOpFinalDepth) + " for recompute() purposes.")
        PathLog.debug("Imported existing FinalDepth of " + str(self.initFinalDepth) + " for recompute() purposes.")

    def opExecute(self, obj):
        '''opExecute(obj) ... process surface operation'''
        PathLog.track()

        self.modelSTLs = list()
        self.safeSTLs = list()
        self.modelTypes = list()
        self.boundBoxes = list()
        faceShapes = list()
        voidShapes = list()
        deflection = None
        deleteTempsFlag = True  # Set to False for debugging

        # mark beginning of operation and identify parent Job
        startTime = time.time()

        # Identify parent Job
        JOB = PathUtils.findParentJob(obj)
        if JOB is None:
            PathLog.error(translate('PathSurface', "No JOB"))
            return

        # Begin GCode for operation with basic information
        # ... and move cutter to clearance height and startpoint
        output = ''
        if obj.Comment != '':
            output += '(' + str(obj.Comment) + ')\n'
        output += '(' + obj.Label + ')'
        output += '(Compensated Tool Path. Diameter: ' + str(obj.ToolController.Tool.Diameter) + ')'
        self.commandlist.append(Path.Command('N ({})'.format(output), {}))
        self.commandlist.append(Path.Command('G0', {'Z': obj.ClearanceHeight.Value, 'F': self.vertRapid}))
        if obj.UseStartPoint is True:
            self.commandlist.append(Path.Command('G0', {'X': obj.StartPoint.x, 'Y': obj.StartPoint.y, 'F': self.horizRapid}))

        # Instantiate additional class operation variables
        self.resetOpVariables()

        # Impose property limits
        self.opApplyPropertyLimits(obj)

        # Create temporary group for temporary objects
        self.tempGroupName = 'tmpGrp_' + str(startTime)
        if PathLog.getLevel(PathLog.thisModule()) == 4:
            deleteTempsFlag = False
            self.tempGroupName = 'debugTempGrp_' + str(startTime)
        FreeCAD.ActiveDocument.addObject('App::DocumentObjectGroup', self.tempGroupName)
        self.tempGroupName = FreeCAD.ActiveDocument.ActiveObject.Name
        # Add temp object to temp group folder with following code:
        # ... FreeCAD.ActiveDocument.getObject(self.tempGroupName).addObject(OBJ)

        # Disable(ignore) ReleaseFromWaste option(input)
        obj.ReleaseFromWaste = False

        # Setup cutter for OCL and cutout value for operation - based on tool controller properties
        self.cutter = self.setOclCutter(obj)
        self.cutOut = (self.cutter.getDiameter() * (float(obj.StepOver) / 100.0))
        self.radius = self.cutter.getDiameter() / 2

        # Get height offset values for later use
        self.SafeHeightOffset = JOB.SetupSheet.SafeHeightOffset.Value
        self.ClearHeightOffset = JOB.SetupSheet.ClearanceHeightOffset.Value

        # Import OpFinalDepth from pre-existing operation for recompute() scenarios
        if obj.OpFinalDepth.Value != self.initOpFinalDepth:
            if obj.OpFinalDepth.Value == obj.FinalDepth.Value:
                obj.FinalDepth.Value = self.initOpFinalDepth
                obj.OpFinalDepth.Value = self.initOpFinalDepth
            if self.initOpFinalDepth is not None:
                obj.OpFinalDepth.Value = self.initOpFinalDepth

        # Calculate default depthparams for operation
        self.depthParams = PathUtils.depth_params(obj.ClearanceHeight.Value, obj.SafeHeight.Value, obj.StartDepth.Value, obj.StepDown.Value, 0.0, obj.FinalDepth.Value)

        # try/except is for Path Jobs created before GeometryTolerance
        try:
            deflection = JOB.GeometryTolerance
        except AttributeError as ee:
            import PathScripts.PathPreferences as PathPreferences
            deflection = PathPreferences.defaultGeometryTolerance()

        # Setup STL, model type, and bound box containers for each model in Job
        for m in range(0, len(JOB.Model.Group)):
            M = JOB.Model.Group[m]
            self.modelSTLs.append(False)
            self.safeSTLs.append(False)
            # Set bound box
            if obj.BoundBox == 'BaseBoundBox':
                if M.TypeId.startswith('Mesh'):
                    self.modelTypes.append('M')  # Mesh
                    self.boundBoxes.append(M.Mesh.BoundBox)
                else:
                    self.modelTypes.append('S')  # Solid
                    self.boundBoxes.append(M.Shape.BoundBox)
            elif obj.BoundBox == 'Stock':
                self.boundBoxes.append(JOB.Stock.Shape.BoundBox)
            self.safeSTLs.append(self._makeMass(JOB, obj, M, deflection))

        # make stock.cut(model_ENVELOPE) united with model - for avoidance detection on transitions
        # self.fullSTL = self._makeMass(JOB, obj, deflection)
        prepSTLs = self._prepareSTLs(JOB, deflection)

        if obj.Algorithm == 'OCL Waterline':
            for M in JOB.Model.Group:
                final = self._waterlineOp(obj, M)
        elif obj.Algorithm == 'OCL Dropcutter':
            # Process selected faces, if available
            addFlag = False
            voidFlag = False
            faceAvoidAreaShapes = list()
            faceCutAreaShapes = list()

            if obj.Base:
                (FACES, VOIDS) = self._preProcessSelectedFaces(JOB, obj)

            if len(FACES) > 0:
                addFlag = True
            if len(VOIDS) > 0:
                voidFlag = True
            # Convert avoid faces to avoid areas
            if voidFlag is True:
                for (mdlIdx, fcshp, faceIdx) in VOIDS:
                    base = JOB.Model.Group[mdlIdx]
                    faceAvoidAreaShp = self._createFacialCutArea(obj, base, fcshp, faceIdx, avoid=True)
                    if faceAvoidAreaShp is not False:
                        faceAvoidAreaShapes.append(faceAvoidAreaShp)
            # Convert add faces to add areas.
            if addFlag is True:
                if obj.OptimizeLinearTransitions is True and len(FACES) > 1:
                    PathLog.warning(translate('PathSurface', "Multiple faces selected. \nWARNING: The `OptimizeLinearTransitions` algorithm might produce incorrect transitional paths between face regions. \nSeparate out faces to fix problem."))

                # Convert faces to cut areas
                for (mdlIdx, fcshp, faceIdx) in FACES:
                    base = JOB.Model.Group[mdlIdx]
                    faceCutAreaShp = self._createFacialCutArea(obj, base, fcshp, faceIdx)
                    if faceCutAreaShp is not False:
                        faceCutAreaShapes.append(faceCutAreaShp)
            # return (faceCutAreaShapes, faceAvoidAreaShapes)

            if addFlag is True:
                final = self._processSelectedFaces(obj, faceCutAreaShapes, faceAvoidAreaShapes)
            else:
                final = self._processEntireModel(obj, faceAvoidAreaShapes)

        # Delete temporary objects
        if deleteTempsFlag is True:
            for to in FreeCAD.ActiveDocument.getObject(self.tempGroupName).Group:
                FreeCAD.ActiveDocument.removeObject(to.Name)
            FreeCAD.ActiveDocument.removeObject(self.tempGroupName)
        else:
            FreeCAD.ActiveDocument.getObject(self.tempGroupName).purgeTouched()

        self.resetOpVariables()
        # self.deleteOpVariables()

        # Save gcode produced
        self.commandslist.extend(final)

        execTime = time.time() - startTime
        PathLog.info('Operation time: {} sec.'.format(execTime))

        return True

    def _processSelectedFaces(self, obj, faceShapes, voidShapes):
        final = list()
        # Process faces Collectively or Individually
        if obj.HandleMultipleFeatures == 'Collectively':
            if len(voidShapes) > 0:
                DEL = Part.makeCompound(voidShapes)
                ADD = Part.makeCompound(faceShapes)
                COMP = ADD.cut(DEL)
            else:
                COMP = Part.makeCompound(faceShapes)

            if obj.ScanType == 'Planar':
                final = self.opProcessBasePlanar(obj, base, COMP)
            elif obj.ScanType == 'Rotational':
                final = self.opProcessBaseRotational(obj, base, COMP)
        elif obj.HandleMultipleFeatures == 'Individually':
            for cas in faceShapes:
                # self.deleteOpVariables(all=False)
                self.resetOpVariables(all=False)
                if len(voidShapes) > 0:
                    DEL = Part.makeCompound(voidShapes)
                    ADD = Part.makeCompound([cas])
                    COMP = ADD.cut(DEL)
                else:
                    COMP = Part.makeCompound([cas])

                if obj.ScanType == 'Planar':
                    final.extend(self.opProcessBasePlanar(obj, base, COMP))
                elif obj.ScanType == 'Rotational':
                    final.extend(self.opProcessBaseRotational(obj, base, COMP))
                COMP = None
                final = None
        # Eif

        return final

    def _processEntireModel(self, obj, voidShapes):
        # Cycle through parts of model
        final = list()
        # for base in self.model:
        for mdl in range(0, len(JOB.Model.Group)):
            model = JOB.Model.Group[mdl]
            if obj.BoundBox == 'Stock':
                BS = JOB.Stock
                baseEnv = PathUtils.getEnvelope(BS.Shape, depthparams=self.depthParams)
            elif obj.BoundBox == 'BaseBoundBox':
                baseEnv = PathUtils.getEnvelope(model.Shape, depthparams=self.depthParams)

            # Make cross-section and convert to planar face
            midHeight = (baseEnv.BoundBox.ZMax - baseEnv.BoundBox.ZMin) / 2
            csFaceShape = self._makeCrossSectionToFaceshape(baseEnv, midHeight, zHghtTrgt=0.0)

            # Create offset shape
            faceOffsetShape = self._extractFaceOffset(obj, csFaceShape, isHole=False)

            if len(voidShapes) > 0:
                DEL = Part.makeCompound(voidShapes)
                cutShape = faceOffsetShape.cut(DEL)
            else:
                cutShape = faceOffsetShape

            # Process faces Collectively or Individually
            if obj.ScanType == 'Planar':
                final.extend(self.opProcessBasePlanar(obj, mdl, COMP))
            elif obj.ScanType == 'Rotational':
                final.extend(self.opProcessBaseRotational(obj, mdl, COMP))
        # Efor

        return final

    def _prepareSTLs(self, JOB, deflection):
        rtn = False
        for m in range(0, len(JOB.Model.Group)):
            M = JOB.Model.Group[m]

            if self.modelTypes[m] == 'M':
                mesh = M.Mesh
            else:
                # base.Shape.tessellate(0.05) # 0.5 original value
                # mesh = MeshPart.meshFromShape(base.Shape, Deflection=deflection)
                mesh = MeshPart.meshFromShape(Shape=M.Shape, LinearDeflection=deflection, AngularDeflection=0.25, Relative=False)

            if self.modelSTLs[m] is True:
                stl = ocl.STLSurf()
                if obj.Algorithm == 'OCL Dropcutter':
                    for f in mesh.Facets:
                        p = f.Points[0]
                        q = f.Points[1]
                        r = f.Points[2]
                        t = ocl.Triangle(ocl.Point(p[0], p[1], p[2]),
                                            ocl.Point(q[0], q[1], q[2]),
                                            ocl.Point(r[0], r[1], r[2]))
                        stl.addTriangle(t)
                elif obj.Algorithm == 'OCL Waterline':
                    for f in mesh.Facets:
                        p = f.Points[0]
                        q = f.Points[1]
                        r = f.Points[2]
                        t = ocl.Triangle(ocl.Point(p[0], p[1], p[2] + obj.DepthOffset.Value),
                                            ocl.Point(q[0], q[1], q[2] + obj.DepthOffset.Value),
                                            ocl.Point(r[0], r[1], r[2] + obj.DepthOffset.Value))
                        stl.addTriangle(t)
                self.modelSTLs[m] = stl
                rtn = True
        return rtn

    def _preProcessSelectedFaces(self, JOB, obj):
        FACES = list()
        VOIDS = list()
        minHeight = None
        maxHeight = None

        # The user has selected subobjects from the base.  Pre-Process each.
        PathLog.debug('obj.Base exists. Pre-processing for selected faces.')
        baseSubTuples = list()
        oneBase = [obj.Base[0][0], True]
        sub0 = getattr(obj.Base[0][0].Shape, obj.Base[0][1][0])
        minHeight = sub0.BoundBox.ZMax
        maxHeight = sub0.BoundBox.ZMin
        # Separate selected faces into (base, face) tuples
        for (bs, SBS) in obj.Base:
            for sb in SBS:
                # Flag model for STL creation
                mdlIdx = None
                for m in range(0, len(JOB.Model.Group)):
                    if bs is JOB.Model.Group[m]:
                        self.modelSTLs[m] = True
                        mdlIdx = m
                        break
                if oneBase[0] is not bs:
                    # Cancel op: Only one model base allowed in the operation
                    oneBase[1] = False
                    PathLog.error(translate('PathSurface', '3D Surface cancelled. Only one base model permitted in an operation.'))
                    return False
                baseSubTuples.append((mdlIdx, bs, sb))  # (base, sub)

        faceCnt = len(baseSubTuples)
        add = faceCnt - obj.AvoidLastXFaces
        for bst in range(0, faceCnt):
            (mdlIdx, base, sub) = baseSubTuples[bst]
            shape = getattr(base.Shape, sub)
            if isinstance(shape, Part.Face):
                faceIdx = int(sub[4:]) - 1
                if bst < add:
                    FACES.append((mdlIdx, shape, faceIdx))
                    PathLog.info(translate('PathSurface', 'Adding Face') + str(faceIdx + 1))
                    # Record min/max zHeights of added faces
                    if shape.BoundBox.ZMax > maxHeight:
                        maxHeight = shape.BoundBox.ZMax
                    if shape.BoundBox.ZMin < minHeight:
                        minHeight = shape.BoundBox.ZMin
                else:
                    VOIDS.append((mdlIdx, shape, faceIdx))
                    PathLog.info(translate('PathSurface', 'Adding Face') + str(faceIdx + 1))
        return (FACES, VOIDS)

    def opSetDefaultValues(self, obj, job):
        '''opSetDefaultValues(obj, job) ... initialize defaults'''
        obj.StepOver = 100
        obj.OptimizeLinearPaths = True
        obj.IgnoreWaste = False
        obj.ReleaseFromWaste = False
        obj.CutInternalFeatures = False
        obj.OptimizeLinearTransitions = False
        obj.OptimizeArcTransitions = False
        obj.FinishPassOnly = False
        obj.RespectBoundary = True
        obj.UseStartPoint = False
        obj.StartPoint.x = 0.0
        obj.StartPoint.y = 0.0
        obj.StartPoint.z = obj.ClearanceHeight.Value
        obj.LayerMode = 'Single-pass'
        obj.ScanType = 'Planar'
        obj.RotationAxis = 'X'
        obj.CutMode = 'Conventional'
        obj.CutPattern = 'Line'
        obj.HandleMultipleFeatures = 'Individually'
        obj.AreaParams = ''
        obj.CutPatternAngle = 0.0
        obj.CutterTilt = 0.0
        obj.StartIndex = 0.0
        obj.StopIndex = 360.0
        obj.SampleInterval.Value = 1.0
        obj.BoundaryAdjustment.Value = 0.0
        obj.AvoidLastXFaces = 0

        # need to overwrite the default depth calculations for facing
        job = PathUtils.findParentJob(obj)
        if job:
            if job.Stock:
                d = PathUtils.guessDepths(job.Stock.Shape, None)
                PathLog.debug("job.Stock exists")
            else:
                PathLog.debug("job.Stock NOT exist")
        else:
            PathLog.debug("job NOT exist")

        if self.docRestored is True:  # This op is NOT the first in the Operations list
            PathLog.debug("doc restored")
            obj.FinalDepth.Value = obj.OpFinalDepth.Value
        else:
            PathLog.debug("new operation")
            obj.OpFinalDepth.Value = d.final_depth
            obj.OpStartDepth.Value = d.start_depth
            if self.initOpFinalDepth is None and self.initFinalDepth is None:
                self.initFinalDepth = d.final_depth
                self.initOpFinalDepth = d.final_depth
            else:
                PathLog.debug("-initFinalDepth" + str(self.initFinalDepth))
                PathLog.debug("-initOpFinalDepth" + str(self.initOpFinalDepth))
        obj.IgnoreWasteDepth = obj.FinalDepth.Value + 0.001

    def opProcessBasePlanar(self, obj, mdlIdx, compoundFaces=None):
        initIdx = 0.0
        final = list()

        JOB = PathUtils.findParentJob(obj)
        base = JOB.Model.Group[mdlIdx]
        bb = self.boundBoxes[mdlIdx]

        # If cut pattern is all arcs, there are minimal straight lines to optimize
        preOLP = obj.OptimizeLinearPaths
        if obj.CutPattern == 'Circular':
            obj.OptimizeLinearPaths = False

        if obj.LayerMode == 'Single-pass':
            final = self._planarDropCutSingle(obj, bb, base, compoundFaces)
        elif obj.LayerMode == 'Multi-pass':
            final = self._planarDropCutMulti(obj, bb, base, compoundFaces)

        # If cut pattern is all arcs, restore initial OLP value
        if obj.CutPattern == 'Circular':
            obj.OptimizeLinearPaths = preOLP

        # Raise to clearance height between individual faces.
        if obj.HandleMultipleFeatures == 'Individually':
            final.insert(0, Path.Command('G0', {'Z': obj.ClearanceHeight.Value, 'F': self.vertRapid}))

        return final

    def opProcessBaseRotational(self, obj, mdlIdx, compoundFaces=None):
        initIdx = 0.0
        final = list()

        JOB = PathUtils.findParentJob(obj)
        base = JOB.Model.Group[mdlIdx]
        bb = self.boundBoxes[mdlIdx]
        stl = self.modelSTLs[mdlIdx]

        # Rotate model to initial index
        initIdx = obj.CutterTilt + obj.StartIndex
        if initIdx != 0.0:
            self.basePlacement = FreeCAD.ActiveDocument.getObject(base.Name).Placement
            if obj.RotationAxis == 'X':
                base.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), initIdx))
            else:
                base.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), initIdx))

        '''
        # Rotate model back to original index
        if obj.ScanType == 'Rotational':
            if initIdx != 0.0:
                initIdx = 0.0
                base.Placement = self.basePlacement
        '''

        # Prepare global holdpoint container
        if self.holdPoint is None:
            self.holdPoint = ocl.Point(float("inf"), float("inf"), float("inf"))
        if self.layerEndPnt is None:
            self.layerEndPnt = ocl.Point(float("inf"), float("inf"), float("inf"))

        # Avoid division by zero in rotational scan calculations
        if obj.FinalDepth.Value <= 0.0:
            zero = obj.SampleInterval.Value  # 0.00001
            self.FinalDepth = zero
            obj.FinalDepth.Value = 0.0
        else:
            self.FinalDepth = obj.FinalDepth.Value

        # Determine boundbox radius based upon xzy limits data
        if math.fabs(bb.ZMin) > math.fabs(bb.ZMax):
            vlim = bb.ZMin
        else:
            vlim = bb.ZMax
        if obj.RotationAxis == 'X':
            # Rotation is around X-axis, cutter moves along same axis
            if math.fabs(bb.YMin) > math.fabs(bb.YMax):
                hlim = bb.YMin
            else:
                hlim = bb.YMax
        else:
            # Rotation is around Y-axis, cutter moves along same axis
            if math.fabs(bb.XMin) > math.fabs(bb.XMax):
                hlim = bb.XMin
            else:
                hlim = bb.XMax

        # Compute max radius of stock, as it rotates, and rotational clearance & safe heights
        self.bbRadius = math.sqrt(hlim**2 + vlim**2)
        self.clearHeight = self.bbRadius + JOB.SetupSheet.ClearanceHeightOffset.Value
        self.safeHeight = self.bbRadius + JOB.SetupSheet.ClearanceHeightOffset.Value

        final = self._rotationalDropCutterOp(obj, stl, bb)

        return final

    def opApplyPropertyLimits(self, obj):
        '''opApplyPropertyLimits(obj) ... Apply necessary limits to user input property values before performing main operation.'''
        # Limit start index
        if obj.StartIndex < 0.0:
            obj.StartIndex = 0.0
        if obj.StartIndex > 360.0:
            obj.StartIndex = 360.0

        # Limit stop index
        if obj.StopIndex > 360.0:
            obj.StopIndex = 360.0
        if obj.StopIndex < 0.0:
            obj.StopIndex = 0.0

        # Limit cutter tilt
        if obj.CutterTilt < -90.0:
            obj.CutterTilt = -90.0
        if obj.CutterTilt > 90.0:
            obj.CutterTilt = 90.0

        # Limit sample interval
        if obj.SampleInterval.Value < 0.001:
            obj.SampleInterval.Value = 0.001
            PathLog.error(translate('PathSurface', 'Sample interval limits are 0.001 to 25.4 millimeters.'))
        if obj.SampleInterval.Value > 25.4:
            obj.SampleInterval.Value = 25.4
            PathLog.error(translate('PathSurface', 'Sample interval limits are 0.001 to 25.4 millimeters.'))

        # Limit cut pattern angle
        if obj.CutPatternAngle < 0.0:
            obj.CutPatternAngle = 0.0
            PathLog.error(translate('PathSurface', 'Cut pattern angle limits are 0 to 360 degrees.'))
        if obj.CutPatternAngle >= 360.0:
            obj.CutPatternAngle = 360.0
            PathLog.error(translate('PathSurface', 'Cut pattern angle limits are 0 to 360 degrees.'))

        # Limit StepOver to natural number percentage
        if obj.StepOver > 100:
            obj.StepOver = 100
        if obj.StepOver < 1:
            obj.StepOver = 1

        # Limit AvoidLastXFaces to zero and positive values
        if obj.AvoidLastXFaces < 0:
            obj.AvoidLastXFaces = 0
            PathLog.error(translate('PathSurface', 'AvoidLastXFaces: Only zero or positive values permitted.'))
        if obj.AvoidLastXFaces > 100:
            obj.AvoidLastXFaces = 100
            PathLog.error(translate('PathSurface', 'AvoidLastXFaces: Avoid last X faces count limited to 100.'))

    def _makeMass(self, JOB, obj, M, deflection):
        # get envelope of Model.
        # mdlShp = Part.makeCompound([M.Shape for M in JOB.Model.Group])
        mdlShp = M.Shape
        mdlsEnv = PathUtils.getEnvelope(partshape=mdlShp, depthparams=self.depthParams)  # Produces .Shape
        wstShp = JOB.Stock.Shape.cut(mdlsEnv)
        waste = FreeCAD.ActiveDocument.addObject("Part::Feature", "Waste")
        waste.Shape = wstShp
        waste.recompute()
        waste.purgeTouched()
        # fuseObjects = [M for M in JOB.Model.Group]
        # fuseObjects.append(waste)
        fuse = FreeCAD.ActiveDocument.addObject("Part::MultiFuse", "Fusion")
        # fuse.Shapes = fuseObjects
        fuse.Shapes = [M, waste]
        fuse.recompute()
        fuse.purgeTouched()

        # Extract mesh from fusion
        meshFuse = MeshPart.meshFromShape(Shape=fuse.Shape, LinearDeflection=deflection, AngularDeflection=0.25, Relative=False)
        fullSTL = ocl.STLSurf()
        for f in meshFuse.Facets:
            p = f.Points[0]
            q = f.Points[1]
            r = f.Points[2]
            t = ocl.Triangle(ocl.Point(p[0], p[1], p[2]),
                                ocl.Point(q[0], q[1], q[2]),
                                ocl.Point(r[0], r[1], r[2]))
            fullSTL.addTriangle(t)

        # Delete temporary objects
        FreeCAD.ActiveDocument.removeObject(fuse.Name)
        FreeCAD.ActiveDocument.removeObject(waste.Name)

        return fullSTL

    # Main planar scan functions
    def _planarDropCutSingle(self, obj, bb, base, compoundFaces=None):
        GCODE = list()
        GCODE.append(Path.Command('N (Beginning of Single-pass layer.)', {}))

        # Compute number and size of stepdowns, and final depth
        depthparams = [obj.FinalDepth.Value]
        lenDP = len(depthparams)

        # Scan the piece to depth
        pdc = self._planarGetPDC(self.stl, depthparams[lenDP - 1], obj.SampleInterval.Value)
        fullPDC = self._planarGetPDC(self.fullSTL, depthparams[lenDP - 1], obj.SampleInterval.Value)
        SCANS = self._planarGetLineScans(obj, pdc, base, compoundFaces)
        lenScans = len(SCANS)
        COM = FreeCAD.Vector(self.tmpCOM.x, self.tmpCOM.y, 0.0)
        if lenScans == 0:
            PathLog.error('No SCANS data.')
            return list()

        if obj.CutPattern == 'ZigZag':
            NEWSCANS = list()
            COLIN = list()  # List of collinear-with-previous-line flags
            InLine = list()
            prvFirst = FreeCAD.Vector(SCANS[0][0].x + 5, SCANS[0][0].y - 9, 3.0)
            odd = False  # odd/even line flag
            for ln in range(0, lenScans):
                LN = SCANS[ln]
                lenLN = len(LN)
                first = LN[0]
                last = LN[lenLN - 1]
                # Test if current LN is collinear with previous line (jumped over internal feature)
                endPnt = FreeCAD.Vector(last.x, last.y, 0.0)
                pointP = FreeCAD.Vector(first.x, first.y, 0.0)
                if self.isCollinear(prvFirst, endPnt, pointP):
                    COLIN.append('Y')
                    if odd is True:
                        SCANS[ln].insert(0, 'BRK')  # add BREAK marker to beginning of scan line data
                        InLine.append(SCANS[ln])
                    else:
                        if InLine[0][0] != 'BRK':
                            InLine[0].insert(0, 'BRK')
                        InLine.insert(0, SCANS[ln])
                else:
                    if len(InLine) > 0:  # add previous collinear set to NEWSCANS
                        NEWSCANS.extend(InLine)
                    InLine = [SCANS[ln]]  # reset InLine, adding current LN as first entry
                    if odd is True:  # toggle odd/even line flag
                        odd = False
                    else:
                        odd = True
                    COLIN.append('N')
                    prvFirst = pointP
            NEWSCANS.extend(InLine)  # add previous collinear set to N
            SCANS = NEWSCANS
        elif obj.CutPattern == 'Circular':
            COLIN = list()  # List of collinear-with-previous-line flags
            prvFirst = FreeCAD.Vector(SCANS[0][0].x, SCANS[0][0].y, 0.0)
            for ln in range(0, lenScans):
                LN = SCANS[ln]
                first = LN[0]
                # Test if current LN(arc) is co-radial with previous (avoided internal feature)
                pointP = FreeCAD.Vector(first.x, first.y, 0.0)
                if abs(pointP.sub(COM).Length - prvFirst.sub(COM).Length) < 0.000001:
                    COLIN.append('Y')
                else:
                    COLIN.append('N')
                prvFirst = pointP

        # Apply depth offset
        if obj.DepthOffset.Value != 0.0:
            self._planarApplyDepthOffset(SCANS, obj.DepthOffset.Value)

        # Pre-process each scan line in layer: Single-pass has only one layer
        LINES = list()
        for ln in range(0, lenScans):
            LN = SCANS[ln]
            numPts = len(LN)
            if LN[0] == 'BRK':
                first = LN[1]
            else:
                first = LN[0]
            last = LN[numPts - 1]
            LINES.append((LN, numPts, first, last))

        # Send cutter to x,y position of first point on first line
        (LN, numPts, first, last) = LINES[0]
        GCODE.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))

        # Cycle through each line in the scan
        lenLINES = len(LINES)
        lstPnt = None
        for ln in range(0, lenLINES):
            (LN, numPts, first, last) = LINES[ln]
            brkFlg = False
            cmds = []
            cmds.append(Path.Command('N (Begin line {}.)'.format(str(ln)), {}))
            if obj.CutPattern == 'Line':
                # Go to safe height between collective faces/regions
                cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
            elif obj.CutPattern == 'ZigZag':
                if LN[0] == 'BRK':
                    brk = LN.pop(0)
                    brkFlg = True
                if brkFlg is True:
                    cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                    cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
            elif obj.CutPattern == 'Circular':
                if ln == 0:
                    cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
                else:
                    if obj.OptimizeArcTransitions is False:
                        cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                        cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
                    else:
                        if COLIN[ln] == 'Y':
                            cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                            cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
                        else:
                            tolrnc = 0.000001
                            minSTH = self._getMinSafeTravelHeight(fullPDC, lstPnt, first)  # Check safe travel height against fullSTL
                            vectTrvl = first.z - lstPnt.z
                            if abs(vectTrvl) < tolrnc:  # transitions to same Z height
                                if minSTH > first.z:
                                    cmds.append(Path.Command('G0', {'Z': minSTH, 'F': self.vertRapid}))
                                cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
                            elif vectTrvl > tolrnc:  # transition steps up
                                cmds.append(Path.Command('G0', {'Z': first.z, 'F': self.vertRapid}))
                            else:
                                cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
                        '''
                        if abs(first.z - lstPnt.z) < tolrnc:  # transitions over flat surface at same Z height
                            other = True
                            if ln < (lenLINES - 2):
                                if numPts > 1:
                                    if abs(LN[1].z - first.z) > obj.StepDown.Value:
                                        cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                                        cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
                                        other = False
                            if other:
                                sth = first.z
                                if minSTH > first.z:
                                    sth = minSTH
                                cmds.append(Path.Command('N (Flat transition between segments.)'))
                                cmds.append(Path.Command('G0', {'Z': sth, 'F': self.vertRapid}))
                                cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
                        elif abs(first.x - lstPnt.x) < (self.cutOut + tolrnc) and abs(first.y - lstPnt.y) < tolrnc:  # loop transition points align
                            if first.z > lstPnt.z:
                                cmds.append(Path.Command('G0', {'Z': lstPnt.z, 'F': self.vertRapid}))
                            else:
                                cmds.append(Path.Command('G1', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
                        else:
                            cmds.append(Path.Command('N (Uneven transition between segments.)'))
                            cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                            cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
                            cmds.append(Path.Command('G1', {'Z': first.z + obj.StepDown.Value, 'F': self.vertFeed}))
                        '''

            # Convert line data to gcode
            cmds.append(Path.Command('N (Line {} commands.)'.format(str(ln)), {}))
            cmds.extend(self._planarSinglepassProcess(obj, LN))

            cmds.append(Path.Command('N (Line {} closing.)'.format(str(ln)), {}))
            if obj.CutPattern == 'Line':
                # Go to clearance height between collective faces/regions
                cmds.append(Path.Command('N (Go to safe height)', {}))
                cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
            elif obj.CutPattern == 'ZigZag':
                pass
            elif obj.CutPattern == 'Circular':
                pass

            cmds.append(Path.Command('N (End of line {}.)'.format(str(ln)), {}))

            GCODE.extend(cmds)  # save line commands
            lstPnt = last  # save last point in loop/line
        # Efor

        # Set previous depth
        GCODE.append(Path.Command('N (End of layer.)', {}))

        return GCODE

    def _planarDropCutMulti(self, obj, bb, base, compoundFaces=None):
        GCODE = list()
        GCODE.append(Path.Command('N (Beginning of Multi-pass layers.)', {}))

        # Compute number and size of stepdowns, and final depth
        dep_par = PathUtils.depth_params(obj.ClearanceHeight.Value, obj.SafeHeight.Value, obj.StartDepth.Value, obj.StepDown.Value, 0.0, obj.FinalDepth.Value)
        depthparams = [i for i in dep_par]
        lenDP = len(depthparams)
        prevDepth = bb.ZMax + 0.5  # depthparams[0]

        # Scan the piece to depth
        pdc = self._planarGetPDC(self.stl, depthparams[lenDP - 1], obj.SampleInterval.Value)
        SCANS = self._planarGetLineScans(obj, pdc, base, compoundFaces)
        lenScans = len(SCANS)
        lastScanIdx = lenScans - 1

        # Pre-process SCAN data, identifying collinear lines, suggesting gap or avoided feature.
        COLIN = list()  # List of collinear-with-previous-line flags
        if obj.CutPattern == 'Line':
            prvFirst = FreeCAD.Vector(SCANS[0][0].x + 5, SCANS[0][0].y - 9, 3.0)
            for ln in range(0, lenScans):
                LN = SCANS[ln]
                lenLN = len(LN)
                first = LN[0]
                last = LN[lenLN - 1]
                # Test if current LN is collinear with previous line (jumped over internal feature)
                endPnt = FreeCAD.Vector(last.x, last.y, 0.0)
                pointP = FreeCAD.Vector(first.x, first.y, 0.0)
                if self.isCollinear(prvFirst, endPnt, pointP):
                    COLIN.append('Y')
                else:
                    COLIN.append('N')
                    prvFirst = pointP
        elif obj.CutPattern == 'ZigZag':
            NEWSCANS = list()
            InLine = list()
            prvFirst = FreeCAD.Vector(SCANS[0][0].x + 5, SCANS[0][0].y - 9, 3.0)
            odd = False  # odd/even line flag
            for ln in range(0, lenScans):
                LN = SCANS[ln]
                lenLN = len(LN)
                first = LN[0]
                last = LN[lenLN - 1]
                # Test if current LN is collinear with previous line (jumped over internal feature)
                endPnt = FreeCAD.Vector(last.x, last.y, 0.0)
                pointP = FreeCAD.Vector(first.x, first.y, 0.0)
                if self.isCollinear(prvFirst, endPnt, pointP):
                    COLIN.append('Y')
                    if odd is True:
                        SCANS[ln].insert(0, 'BRK')  # add BREAK marker to beginning of scan line data
                        InLine.append(SCANS[ln])
                    else:
                        if InLine[0][0] != 'BRK':
                            InLine[0].insert(0, 'BRK')
                        InLine.insert(0, SCANS[ln])
                else:
                    if len(InLine) > 0:  # add previous collinear set to NEWSCANS
                        NEWSCANS.extend(InLine)
                    InLine = [SCANS[ln]]  # reset InLine, adding current LN as first entry
                    if odd is True:  # toggle odd/even line flag
                        odd = False
                    else:
                        odd = True
                    COLIN.append('N')
                    prvFirst = pointP
            NEWSCANS.extend(InLine)  # add previous collinear set to N
            SCANS = NEWSCANS
        elif obj.CutPattern == 'Circular':
            prvFirst = FreeCAD.Vector(SCANS[0][0].x + 5, SCANS[0][0].y - 9, 3.0)
            COM = FreeCAD.Vector(self.tmpCOM.x, self.tmpCOM.y, 0.0)
            for ln in range(0, lenScans):
                LN = SCANS[ln]
                lenLN = len(LN)
                first = LN[0]
                # Test if current LN is collinear with previous line (jumped over internal feature)
                pointP = FreeCAD.Vector(first.x, first.y, 0.0)
                if pointP.sub(COM).Length < 0.00001:
                    COLIN.append('Y')
                else:
                    COLIN.append('N')
                    prvFirst = pointP

        # Apply depth offset
        if obj.DepthOffset.Value != 0.0:
            self._planarApplyDepthOffset(SCANS, obj.DepthOffset.Value)

        # Process each layer in depthparams
        for lyr in range(0, lenDP):
            LINES = list()
            LYR = list()
            lyrMax = None
            prevFirst = None
            prevLast = None
            isCoLinear = False
            saveLayer = False
            lyrDep = depthparams[lyr]

            # Cycle through each line in the scan, pre-processing each
            cnt = 0
            for ln in range(0, lenScans):
                LN = SCANS[ln]
                brkFlg = False
                # Pre-process scan for layer depth and holds
                (PNTS, lMax) = self._planarMultipassPreProcess(obj, LN, prevDepth, lyrDep)
                lenPNTS = len(PNTS)

                if lenPNTS > 0:
                    # Temporarily remove break marker from line data
                    # The marker will be returned to the line data later
                    if PNTS[0] == 'BRK':
                        brk = PNTS.pop(0)
                        brkFlg = True
                        lenPNTS -= 1

                if lenPNTS > 0:
                    save = True
                    first = PNTS[0]
                    last = PNTS[lenPNTS - 1]
                    if cnt == 0:
                        lyrMax = lMax
                    else:
                        if lMax > lyrMax:
                            lyrMax = lMax
                    # Return break marker to beginning of line data
                    if brkFlg is True:
                        PNTS.insert(0, 'BRK')
                    cnt += 1
                    LINES.append((PNTS, first, last, lMax))
            # Efor

            # Cycle through each pre-processed line of scan data
            lenLINES = len(LINES)
            for ln in range(0, lenLINES):
                (PNTS, first, last, lMax) = LINES[ln]
                numPts = len(PNTS)
                save = True
                brkFlg = False
                cmds = [Path.Command('N (Line ' + str(ln) + ')', {})]

                if ln == 0:
                    prevFirst = first
                    prevLast = last

                # Pre-line conversion Gcode commands
                if obj.CutPattern == 'Line':
                    cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
                elif obj.CutPattern == 'ZigZag':
                    if PNTS[0] == 'BRK':
                        brkFlg = True
                    if ln == 0:
                        cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
                    else:
                        # if prevLast to first > stepover, raise to safeheight?
                        prevLastToFirst = first.sub(prevLast).Length  # get length of vector difference
                        if prevLastToFirst > self.cutOut:  # obj.StepDown.Value:
                            cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                            cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
                    if brkFlg is True:
                        cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                        cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
                        cmds.append(Path.Command('G0', {'Z': first.z + obj.StepDown.Value, 'F': self.vertRapid}))

                    if obj.HandleMultipleFeatures == 'Collectively':
                        pass
                    elif obj.HandleMultipleFeatures == 'Individually':
                        pass
                elif obj.CutPattern == 'Circular':
                    cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))

                # Generate gcode
                lineCmds = self._planarMultipassProcess(obj, PNTS, lyr, ln, lMax)
                if len(lineCmds) == 0:
                    save = False
                else:
                    cmds.extend(lineCmds)
                    saveLayer = True

                clrLine = prevDepth + 2.0
                if lMax > clrLine:
                    clrLine = lMax + 2.0

                # Post-line conversion Gcode commands
                if obj.CutPattern == 'Line':
                    if obj.OptimizeLinearTransitions is False:
                        clrLine = obj.SafeHeight.Value
                    # Go to height to clear highest point on line
                    cmds.append(Path.Command('G0', {'Z': clrLine, 'F': self.vertRapid}))
                    # Return to start point of line
                    if ln != lastScanIdx:
                        # if current line is NOT collinear with next, return to line start point
                        if COLIN[ln + 1] == 'N':
                            cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                    if obj.OptimizeLinearTransitions is True:
                        cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                    # Eif
                elif obj.CutPattern == 'ZigZag':
                    pass
                elif obj.CutPattern == 'Circular':
                    if obj.OptimizeLinearTransitions is False:
                        clrLine = obj.SafeHeight.Value
                    # Go to height to clear highest point on line
                    cmds.append(Path.Command('G0', {'Z': clrLine, 'F': self.vertRapid}))
                    # Return to start point of line
                    if ln != lastScanIdx:
                        # if current line is NOT collinear with next, return to line start point
                        if COLIN[ln + 1] == 'N':
                            cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                    if obj.OptimizeLinearTransitions is True:
                        cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                    # Eif

                # append layer commands to operation command list
                if save is True:
                    LYR.extend(cmds)
                # Rotate points
                prevFirst = first
                prevLast = last
            # Efor

            # Set previous depth
            prevDepth = lyrDep
            if saveLayer is True:
                LYR.insert(0, Path.Command('N (Beginning of layer ' + str(lyr) + ')', {}))
                LYR.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                LYR.append(Path.Command('N (End of layer ' + str(lyr) + ')', {}))
                GCODE.extend(LYR)
        # Efor

        return GCODE

    def _planarSinglepassProcess(self, obj, PNTS):
        output = []
        optimize = obj.OptimizeLinearPaths
        lenPNTS = len(PNTS)
        lastPNTS = len(PNTS) - 1
        lop = None
        onLine = False

        # Initialize first three points
        nxt = None
        pnt = PNTS[0]
        prev = FreeCAD.Vector(pnt.x - 4464.6, pnt.y + 25853553.2, pnt.z + 353425)

        #  Add temp end point
        PNTS.append(FreeCAD.Vector(pnt.x + 4464.6, pnt.y - 25853553.2, pnt.z - 353425))

        # Begin processing ocl points list into gcode
        for i in range(0, lenPNTS):
            # Calculate next point for consideration with current point
            nxt = PNTS[i + 1]

            # Process point
            if optimize is True:
                iPOL = self.isPointOnLine(prev, nxt, pnt)
                # iPOL = self.isCollinear(prev, nxt, pnt)
                if iPOL is True:
                    onLine = True
                else:
                    onLine = False
                    output.append(Path.Command('G1', {'X': pnt.x, 'Y': pnt.y, 'Z': pnt.z, 'F': self.horizFeed}))
            else:
                output.append(Path.Command('G1', {'X': pnt.x, 'Y': pnt.y, 'Z': pnt.z, 'F': self.horizFeed}))

            # Rotate point data
            if onLine is False:
                prev = pnt
            pnt = nxt
        # Efor
        
        temp = PNTS.pop()  # Remove temp end point

        return output

    def _planarMultipassPreProcess(self, obj, LN, prvDep, layDep):
        ALL = list()
        PTS = list()
        brkFlg = False
        optLinTrans = obj.OptimizeLinearTransitions
        safe = obj.SafeHeight.Value

        # Remove 'BRK' flag if present
        if LN[0] == 'BRK':
            brk = LN.pop(0)
            brkFlg = True

        if optLinTrans is True:
            for P in LN:
                ALL.append(FreeCAD.Vector(P.x, P.y, P.z))
                # Handle layer depth AND hold points
                if P.z <= layDep:
                    PTS.append(FreeCAD.Vector(P.x, P.y, layDep))
                elif P.z > prvDep:
                    PTS.append(FreeCAD.Vector(P.x, P.y, safe))
                else:
                    PTS.append(FreeCAD.Vector(P.x, P.y, P.z))
            # Efor
        else:
            for P in LN:
                ALL.append(FreeCAD.Vector(P.x, P.y, P.z))
                # Handle layer depth only
                if P.z <= layDep:
                    PTS.append(FreeCAD.Vector(P.x, P.y, layDep))
                else:
                    PTS.append(FreeCAD.Vector(P.x, P.y, P.z))
            # Efor
        
        if optLinTrans is True:
            # Remove leading and trailing Hold Points
            popList = list()
            for i in range(0, len(PTS)):  # identify leading string
                if PTS[i].z == safe:
                    popList.append(i)
                else:
                    break
            popList.sort(reverse=True)
            for p in popList:  # Remove hold points
                PTS.pop(p)
                ALL.pop(p)
            popList = list()
            for i in range(len(PTS) - 1, -1, -1):  # identify trailing string
                if PTS[i].z == safe:
                    popList.append(i)
                else:
                    break
            popList.sort(reverse=True)
            for p in popList:  # Remove hold points
                PTS.pop(p)
                ALL.pop(p)

        # Determine max Z height for remaining points on line
        lMax = -99999999999999.9654321
        if len(ALL) > 0:
            lMax = ALL[0].z
            for P in ALL:
                if P.z > lMax:
                    lMax = P.z

        # Restore 'BRK' flag if present
        if brkFlg is True:
            PTS.insert(0, 'BRK')
            LN.insert(0, 'BRK')

        return (PTS, lMax)

    def _planarMultipassProcess(self, obj, PNTS, lyr, lnCnt, lMax):
        output = list()
        optimize = obj.OptimizeLinearPaths
        safe = obj.SafeHeight.Value
        lenPNTS = len(PNTS)
        lastPNTS = lenPNTS - 1
        prcs = True
        onHold = False
        clrScnLn = lMax + 2.0
        strIdx = 0

        if PNTS[0] == 'BRK':
            strIdx = 1

        # Initialize first three points
        nxt = None
        pnt = PNTS[strIdx]
        prev = FreeCAD.Vector(pnt.x - 4464.6, pnt.y + 25853553.2, pnt.z + 353425)

        #  Add temp end point
        PNTS.append(FreeCAD.Vector(pnt.x + 4464.6, pnt.y - 25853553.2, pnt.z - 353425))

        # Add additional point at end
        PNTS.append(FreeCAD.Vector(-945.24, 573.826, 9994673))

        # Begin processing ocl points list into gcode
        for i in range(strIdx, lenPNTS):
            prcs = True
            nxt = PNTS[i + 1]

            if pnt.z == safe:
                prcs = False
                if onHold is False:
                    onHold = True
                    output.append( Path.Command('N (Start hold)', {}) )
                    output.append( Path.Command('G0', {'Z': clrScnLn, 'F': self.vertRapid}) )
            else:
                if onHold is True:
                    onHold = False
                    output.append( Path.Command('N (End hold)', {}) )
                    output.append( Path.Command('G0', {'X': pnt.x, 'Y': pnt.y, 'F': self.horizRapid}) )

            # Process point
            if prcs is True:
                if optimize is True:
                    if prev != 'HP' and nxt != 'HP':
                        iPOL = self.isPointOnLine(prev, nxt, pnt)
                        if iPOL is True:
                            onLine = True
                        else:
                            onLine = False
                            output.append(Path.Command('G1', {'X': pnt.x, 'Y': pnt.y, 'Z': pnt.z, 'F': self.horizFeed}))
                else:
                    output.append(Path.Command('G1', {'X': pnt.x, 'Y': pnt.y, 'Z': pnt.z, 'F': self.horizFeed}))

            # Rotate point data
            if onLine is False:
                prev = pnt
            pnt = nxt
        # Efor

        temp = PNTS.pop()  # Remove temp end point

        return output

    def _planarApplyDepthOffset(self, SCANS, DepthOffset):
        PathLog.info('Applying DepthOffset value.')
        lenScans = len(SCANS)
        for s in range(0, lenScans):
            LN = SCANS[s]
            numPts = len(LN)
            for pt in range(0, numPts):
                SCANS[s][pt].z += DepthOffset

    def _planarGetPDC(self, stl, finalDep, SampleInterval):
        pdc = ocl.PathDropCutter()   # create a pdc [PathDropCutter] object
        pdc.setSTL(stl)  # add stl model
        pdc.setCutter(self.cutter)  # add cutter
        pdc.setZ(finalDep)  # set minimumZ (final / target depth value)
        pdc.setSampling(SampleInterval)  # set sampling size
        return pdc

    def _planarGetLineScans(self, obj, pdc, base, compoundFaces):
        SCANS = list()
        # Get LINESET and perform OCL scan on each line within
        linesetObject = self._planarGetLineSet(obj, base, compoundFaces)
        PNTSET = self._convertLinesetToPointSet(obj, linesetObject)
        if obj.CutPattern in ['Line', 'ZigZag']:
            for p1p2Tup in PNTSET:
                SCANS.append(self._planarDropCutScan(pdc, p1p2Tup))
        elif obj.CutPattern == 'Circular':
            for ARC in PNTSET:
                SCANS.append(self._planarCircularDropCutScan(pdc, ARC))
        return SCANS

    def _planarGetLineSet(self, obj, base, subShp=None):
        axisRot = FreeCAD.Vector(0.0, 0.0, 1.0)
        addTopLine = False
        MaxLC = -1
        # JOB = PathUtils.findParentJob(obj)
        # base = JOB.Model.Group[mdlIdx]

        # set initial placement - used for each line
        pl = FreeCAD.Placement()
        pl.Rotation = FreeCAD.Rotation(axisRot, 0.0)
        pl.Base = FreeCAD.Vector(0, 0, 0)

        # Get envelope shape of base object or collective faces selected
        depPrms = PathUtils.depth_params(
            clearance_height=10,
            safe_height=8,
            start_depth=6,
            step_down=1,
            z_finish_step=0.0,
            final_depth=-2,
            user_depths=None)

        # Apply drop cutter extra offset and set the max and min XY area of the operation
        if subShp is None:
            # Get correct boundbox
            if obj.BoundBox == 'Stock':
                BS = PathUtils.findParentJob(obj).Stock
                bb = BS.Shape.BoundBox
            elif obj.BoundBox == 'BaseBoundBox':
                BS = base
                bb = base.Shape.BoundBox

            env = PathUtils.getEnvelope(partshape=BS.Shape, depthparams=depPrms)  # Produces .Shape

            dceoX = obj.DropCutterExtraOffset.x
            dceoY = obj.DropCutterExtraOffset.y
            xmin = bb.XMin - dceoX
            xmax = bb.XMax + dceoX
            ymin = bb.YMin - dceoY
            ymax = bb.YMax + dceoY
            zmin = bb.ZMin
            zmax = bb.ZMax
        else:
            xmin = subShp.BoundBox.XMin
            xmax = subShp.BoundBox.XMax
            ymin = subShp.BoundBox.YMin
            ymax = subShp.BoundBox.YMax
            zmin = subShp.BoundBox.ZMin
            zmax = subShp.BoundBox.ZMax
            if zmax != 0.0:
                subShp.translate(FreeCAD.Vector(0, 0, 0 - zmax))  # move to ZMax of job boundbox

        # convert envelope to solid object
        ENV = FreeCAD.ActiveDocument.addObject('Part::Feature', 'tmpCutAreaEnvelope')
        if subShp is None:
            ENV.Shape = env
        else:
            ENV.Shape = subShp
        ENV.recompute()
        ENV.purgeTouched()
        envName = ENV.Name
        FreeCAD.ActiveDocument.getObject(self.tempGroupName).addObject(ENV)
        COM = ENV.Shape.Face1.CenterOfMass
        self.tmpCOM = COM

        # get X, Y, Z spans; Compute center of rotation
        deltaX = abs(xmax-xmin)
        deltaY = abs(ymax-ymin)
        deltaZ = abs(zmax-zmin)
        deltaC = math.sqrt(deltaX**2 + deltaY**2)
        zHeight = 0.0
        lineLen = deltaC + (2 * self.cutter.getDiameter())  # Line length to span boundbox diag with 2x cutter diameter extra on each end
        cutPasses = math.ceil(lineLen / self.cutOut) + 1  # Number of lines(passes) required to cover lineLen

        # Generate the Draft line/circle sets to be intersected with the cut-face-area
        if obj.CutPattern in ['ZigZag', 'Line']:
            corX = xmin + (deltaX / 2)  # CenterOfRotation X
            corY = ymin + (deltaY / 2)  # CenterOfRotation Y
            centRot = FreeCAD.Vector(corX, corY, zHeight)
            cAng = math.atan(deltaX / deltaY)  # BoundaryBox angle

            startPoint = FreeCAD.Vector(xmin, ymin, zHeight)  # Center of face/selection/model
            centRot = startPoint  # center of rotation is (xmin,ymin)
            corX = xmin + (deltaX / 2)  # CenterOfRotation X
            corY = ymin + (deltaY / 2)  # CenterOfRotation Y
            centRot = FreeCAD.Vector(corX, corY, zHeight)
            cAng = math.atan(deltaX / deltaY)  # BoundaryBox angle
            zHeight = 0.0

            lineLen = deltaC + (2 * self.cutter.getDiameter())  # Line length to span boundbox diag with 2x cutter diameter extra on each end
            cutPasses = math.ceil(lineLen / self.cutOut) + 1  # Number of lines(passes) required to cover lineLen
            startPoint = FreeCAD.Vector(xmin, ymin, zHeight)  # Center of face/selection/model
            centRot = startPoint  # center of rotation is (xmin,ymin)

            # Determine end points and create top lines
            x1 = startPoint.x - lineLen
            x2 = startPoint.x + lineLen
            diag = None
            if obj.CutPatternAngle == 0 or obj.CutPatternAngle == 180:
                MaxLC = math.floor(deltaY / self.cutOut)
                diag = deltaY
            elif obj.CutPatternAngle == 90 or obj.CutPatternAngle == 270:
                MaxLC = math.floor(deltaX / self.cutOut)
                diag = deltaX
            else:
                perpDist = math.cos(cAng - math.radians(obj.CutPatternAngle)) * deltaC
                MaxLC = math.floor(perpDist / self.cutOut)
                diag = perpDist
            y1 = startPoint.y + diag
            p1 = FreeCAD.Vector(x1, y1, zHeight)
            p2 = FreeCAD.Vector(x2, y1, zHeight)
            topLineTuple = (p1, p2)
            ny1 = startPoint.y - diag
            n1 = FreeCAD.Vector(x1, ny1, zHeight)
            n2 = FreeCAD.Vector(x2, ny1, zHeight)
            negTopLineTuple = (n1, n2)

            # Create end points for set of lines to intersect with cross-section face
            pntTuples = list()
            # for lc in range(0, cutPasses):
            negStart = (-1 * cutPasses)
            for lc in range((-1 * (cutPasses - 1)), cutPasses + 1):
                x1 = startPoint.x - lineLen
                x2 = startPoint.x + lineLen
                y1 = startPoint.y + (lc * self.cutOut)
                # y2 = y1
                p1 = FreeCAD.Vector(x1, y1, zHeight)
                p2 = FreeCAD.Vector(x2, y1, zHeight)
                pntTuples.append( (p1, p2) )
            pntTuples.insert(MaxLC + 1, topLineTuple)
            pntTuples.insert((cutPasses - MaxLC), negTopLineTuple)

            # Convert end points to lines
            LineSet = []
            Names = list()
            for (p1, p2) in pntTuples:
                line = Draft.makeWire([p1, p2], placement=pl, closed=False, face=False, support=None)
                Draft.autogroup(line)
                lineName = FreeCAD.ActiveDocument.ActiveObject.Name
                Names.append(lineName)
                line.recompute()
                line.purgeTouched()
                LineSet.append(line)

        elif obj.CutPattern == 'Circular':
            LineSet = []
            Names = list()
            cntr = FreeCAD.Placement()
            cntr.Rotation = FreeCAD.Rotation(axisRot, 0.0)
            cntr.Base = COM  # Use center of Mass;  # FreeCAD.Vector(0, 0, 0)

            if obj.StepOver > 50:
                circle = Draft.makeCircle(radius=(self.cutOut / 10), placement=cntr, face=False, support=None)
                Draft.autogroup(circle)
                cirName = FreeCAD.ActiveDocument.ActiveObject.Name
                Names.append(cirName)
                circle.recompute()
                circle.purgeTouched()
                LineSet.append(circle)

            for lc in range(1, cutPasses + 1):
                rad = (lc * self.cutOut)
                circle = Draft.makeCircle(radius=rad, placement=cntr, face=False, support=None)
                Draft.autogroup(circle)
                cirName = FreeCAD.ActiveDocument.ActiveObject.Name
                Names.append(cirName)
                circle.recompute()
                circle.purgeTouched()
                LineSet.append(circle)
            # Efor
        # Eif

        # Add all new line objects to temporary group for deletion
        for nm in Names:
            FreeCAD.ActiveDocument.getObject(self.tempGroupName).addObject(FreeCAD.ActiveDocument.getObject(nm))

        # Create compound object to bind all lines in Lineset
        CMPD = FreeCAD.ActiveDocument.addObject('Part::Compound', 'Compound')
        CMPD.Links = LineSet
        CMPD.recompute()
        CMPD.purgeTouched()
        compoundName = CMPD.Name
        FreeCAD.ActiveDocument.getObject(self.tempGroupName).addObject(CMPD)

        # Rotate line set
        if obj.CutPattern == 'ZigZag':
            Draft.rotate(CMPD, -1 * obj.CutPatternAngle, center=centRot, axis=axisRot, copy=False)
            CMPD.purgeTouched()
        elif obj.CutPattern == 'Line':
            Draft.rotate(CMPD, -1 * obj.CutPatternAngle, center=centRot, axis=axisRot, copy=False)
            CMPD.purgeTouched()

        # Identify intersection of cross-section face and lineset
        CMN = FreeCAD.ActiveDocument.addObject('Part::MultiCommon', 'Common')
        cmnName = CMN.Name
        CMN.Shapes = [FreeCAD.ActiveDocument.getObject(envName), FreeCAD.ActiveDocument.getObject(compoundName)]
        CMN.recompute()
        CMN.purgeTouched()
        FreeCAD.ActiveDocument.getObject(self.tempGroupName).addObject(CMN)

        return FreeCAD.ActiveDocument.getObject(cmnName)

    def _convertLinesetToPointSet(self, obj, LSET):
        # Extract intersection line segments for return value as list()
        LINES = list()
        ec = len(LSET.Shape.Edges)
        if obj.CutPattern == 'ZigZag':
            pp1 = None
            dirFlg = 1
            for ei in range(0, ec):
                edg = LSET.Shape.Edges[ei]
                p1 = (edg.Vertexes[0].X, edg.Vertexes[0].Y)
                p2 = (edg.Vertexes[1].X, edg.Vertexes[1].Y)
                if ei > 0:
                    sp = FreeCAD.Vector(pp1[0], pp1[1], 0.0)
                    ep = FreeCAD.Vector(p2[0], p2[1], 0.0)
                    cp = FreeCAD.Vector(p1[0], p1[1], 0.0)
                    if self.isCollinear(sp, ep, cp) is False:
                        dirFlg = -1 * dirFlg
                if dirFlg == 1:
                    tup = (p1, p2)
                else:
                    tup = (p2, p1)
                LINES.append(tup)
                pp1 = p1
        elif obj.CutPattern == 'Line':
            for ei in range(0, ec):
                edg = LSET.Shape.Edges[ei]
                p1 = (edg.Vertexes[0].X, edg.Vertexes[0].Y)
                p2 = (edg.Vertexes[1].X, edg.Vertexes[1].Y)
                tup = (p1, p2)
                if obj.CutMode == 'Climb':
                    tup = (p2, p1)
                LINES.append(tup)
        elif obj.CutPattern == 'Circular':
            COM = LSET.Shape.Edges[0].Placement.Base
            SEGS = list()
            segEI = list()
            LOOPS = list()
            ARCS = list()
            arcEI = list()
            IDS = list()
            isSame = False
            sameRad = None
            for ei in range(0, ec):
                edg = LSET.Shape.Edges[ei]
                if edg.Closed is True:
                    Loop = self._loopToLineSegments(obj, edg.Placement.Base, edg)
                    LOOPS.append(Loop)
                    IDS.append('L')
                else:
                    Arc = self._arcToLineSegments(ei, obj, edg.Placement.Base, edg)
                    if isSame is False:
                        SEGS.append(Arc)
                        segEI.append(ei)
                        isSame = True
                        pnt = FreeCAD.Vector(edg.Vertexes[0].X, edg.Vertexes[0].Y, 0.0)
                        sameRad = pnt.sub(COM).Length
                    else:
                        # Check if arc is co-radial to current SEGS
                        pnt = FreeCAD.Vector(edg.Vertexes[0].X, edg.Vertexes[0].Y, 0.0)
                        if abs(sameRad - pnt.sub(COM).Length) > 0.00001:
                            isSame = False
                        
                        if isSame is True:
                            SEGS.append(Arc)
                            segEI.append(ei)
                        else:
                            # Move co-radial arc segments
                            ARCS.append(SEGS)
                            arcEI.append(segEI)
                            IDS.append('A')
                            # Start new list of arc segments
                            SEGS = [Arc]
                            segEI = [ei]
                            isSame = True
                            pnt = FreeCAD.Vector(edg.Vertexes[0].X, edg.Vertexes[0].Y, 0.0)
                            sameRad = pnt.sub(COM).Length
            # Process trailing SEGS data, if available
            if isSame is True:
                ARCS.append(SEGS)
                arcEI.append(segEI)
                IDS.append('A')

            # Identify adjacent arcs with y=0 start/end points that connect
            for SG in range(0, len(ARCS)):
                startOnAxis = list()
                endOnAxis = list()
                A = ARCS[SG]  # list of arc segments
                EI = arcEI[SG]  # list of corresponding LSET.Shape.Edges indexes

                # Identify startOnAxis and endOnAxis arcs
                for i in range(0, len(EI)):
                    ei = EI[i]
                    E = LSET.Shape.Edges[ei]
                    if abs(COM.y - E.Vertexes[0].Y) < 0.00001:
                        startOnAxis.append((i, E.Vertexes[0]))
                    elif abs(COM.y - E.Vertexes[1].Y) < 0.00001:
                        endOnAxis.append((i, E.Vertexes[1]))

                # Look for connections between startOnAxis and endOnAxis arcs. Consolidate data when connected
                delList = list()
                lenSOA = len(startOnAxis)
                lenEOA = len(endOnAxis)
                if lenSOA > 0 and lenEOA > 0:
                    delIdxs = list()
                    lstFindIdx = 0
                    for soa in range(0, lenSOA):
                        (iS, vS) = startOnAxis[soa]
                        for eoa in range(0, len(endOnAxis)):
                            (iE, vE) = endOnAxis[eoa]
                            dist = vE.X - vS.X
                            if abs(dist) < 0.00001:  # They connect on axis at same radius
                                # Transfer points to end of ending arc
                                for d in ARCS[SG][iS]:
                                    ARCS[SG][iE].append(d)
                                delList.append(iS)
                                break
                            elif dist > 0:
                                break  # stop searching

                # Remove empty arcs that were connected to another
                if len(delList) > 0:
                    delList.sort(reverse=True)
                    for d in delList:
                        ARCS[SG].pop(d)
                        arcEI[SG].pop(d)
            # Efor

            # Re-assemble loops and arcs in order
            for i in IDS:
                if i == 'L':
                    LINES.append(LOOPS.pop(0))
                else:
                    SEGS = ARCS.pop(0)
                    if obj.CutMode == 'Climb':
                        SEGS.reverse()  # Reverse order of arcs.
                        REVSEGS = list()
                        for S in SEGS:
                            REV = list()
                            S.reverse()  # Reverse order of point sets in each arc
                            for (p1, p2) in S:
                                REV.append((p2, p1))  # reverse order of vertexes in each point set
                            REVSEGS.append(REV)
                        LINES.extend(REVSEGS)
                    else:
                        LINES.extend(SEGS)
        # Eif 'Circular'
                
        return LINES

    def _planarDropCutScan(self, pdc, p1p2Tup):
        PNTS = list()
        ((x1, y1), (x2, y2)) = p1p2Tup
        path = ocl.Path()                   # create an empty path object
        p1 = ocl.Point(x1, y1, 0)   # start-point of line
        p2 = ocl.Point(x2, y2, 0)   # end-point of line
        lo = ocl.Line(p1, p2)     # line-object
        path.append(lo)        # add the line to the path
        pdc.setPath(path)
        pdc.run()  # run dropcutter algorithm on path
        CLP = pdc.getCLPoints()
        for p in CLP:
            PNTS.append(FreeCAD.Vector(p.x, p.y, p.z))
        return PNTS  # pdc.getCLPoints()

    def _planarCircularDropCutScan(self, pdc, ARC):
        PNTS = list()
        path = ocl.Path()                   # create an empty path object
        for (v1, v2) in ARC:
            p1 = ocl.Point(v1.x, v1.y, 0)   # start-point of line
            p2 = ocl.Point(v2.x, v2.y, 0)   # end-point of line
            lo = ocl.Line(p1, p2)     # line-object
            path.append(lo)        # add the line to the path
        pdc.setPath(path)
        pdc.run()  # run dropcutter algorithm on path
        CLP = pdc.getCLPoints()
        for p in CLP:
            PNTS.append(FreeCAD.Vector(p.x, p.y, p.z))
        return PNTS  # pdc.getCLPoints()

    # Methods for creating offset face using Path.Area()
    def _createFacialCutArea(self, obj, oneBase, fc, faceIdx, avoid=False):
        '''_createFacialCutArea(obj, oneBase, fc, faceIdx) ... 
        Recieves the base object, face object and face index for same face on base.
        Returns face object reflecting offset cut area to be processed with OCL.'''
        PathLog.debug('_createFacialCutArea()')
        # isHole = False
        isHole = avoid  # True for avoid areas, false for add faces
        depthparams = PathUtils.depth_params(obj.ClearanceHeight.Value, obj.SafeHeight.Value, obj.StartDepth.Value*2, obj.StepDown.Value, 0.0, obj.FinalDepth.Value)
        finDep = max(obj.FinalDepth.Value, fc.BoundBox.ZMin)

        # Get ZMax of boundary box for model: same used for LINESET creation.
        if obj.BoundBox == 'Stock':
            BS = PathUtils.findParentJob(obj).Stock
            bb = BS.Shape.BoundBox
        elif obj.BoundBox == 'BaseBoundBox':
            bb = oneBase.Shape.BoundBox
        zHghtTrgt = 0.0

        if isPlanar(fc) and isVertical(fc):
            PathLog.info('Face{} is planar and vertical.'.format(faceIdx + 1))
            LengthFwd = 2.0
        else:
            LengthFwd = (fc.BoundBox.ZMax - fc.BoundBox.ZMin + 1.0) * 2

        # Check for open wires on face.
        # If so, use envelope for entire face, ignoring internal features
        makeEnvFlag = False
        for w in range(0, len(fc.Wires)):
            # Refine wire
            rWire = Part.Wire(Part.__sortEdges__(fc.Wires[w].Edges))
            if rWire.isClosed() is False:
                makeEnvFlag = True
                PathLog.warning('Face{} requires use of envelope for extrusion. Internal features might be ignored.'.format(faceIdx))
                break

        # Loop through each wire in face, extracting offset shape
        if makeEnvFlag is False:
            outerFaceName = None
            for w in range(0, len(fc.Wires)):
                wire = fc.Wires[w]
                if w > 0:
                    isHole = True
                if w == 0:
                    outerFace = self._wireToOffsetFace(obj, isHole, fc, wire, LengthFwd, zHghtTrgt)  # complete object
                    outerFaceName = outerFace.Name
                    if obj.CutInternalFeatures is True:
                        break
                else:
                    innerFace = self._wireToOffsetFace(obj, isHole, fc, wire, LengthFwd, zHghtTrgt)
                    if w == 1:
                        cutShape = outerFace.Shape.cut(innerFace.Shape)  # obj.Shape
                    else:
                        cutShape = cutShape.cut(innerFace.Shape)  # obj.Shape
            # Efor

            if w == 0:
                return outerFace.Shape
            else:
                offsetFaceShape = cutShape
        else:
            # Create envelope from non-planar face
            env = PathUtils.getEnvelope(fc, depthparams=depthparams)
            FreeCAD.ActiveDocument.addObject('Part::Feature','tmpFaceEnvelope')
            E = FreeCAD.ActiveDocument.ActiveObject
            E.Shape = env
            E.recompute()
            E.purgeTouched()
            FreeCAD.ActiveDocument.getObject(self.tempGroupName).addObject(E)

            # Make cross-section and translate it
            sliceZ = obj.FinalDepth.Value + (abs(obj.StartDepth.Value - obj.FinalDepth.Value) / 2)  # slice at middle
            csFaceShape = self._makeCrossSectionToFaceshape(E.Shape, sliceZ, zHghtTrgt)

            # Use Path.Area() to extract offset loop of face.
            offsetFaceShape = self._extractFaceOffset(obj, csFaceShape, isHole)
        # Eif

        return offsetFaceShape

    def _wireToOffsetFace(self, obj, isHole, fc, wire, LengthFwd, bbZMax):
        '''_wireToOffsetFace(obj, isHole, fc, wire, LengthFwd, bbZMax) ... 
        Returns a cross-sectional face made from ether an extrusion or envelope
        of the wire received.'''
        PathLog.debug('_wireToOffsetFace()')
        depthparams = PathUtils.depth_params(obj.ClearanceHeight.Value, obj.SafeHeight.Value, obj.StartDepth.Value*2, obj.StepDown.Value, 0.0, obj.FinalDepth.Value)
        # Refine incoming wire
        nWire = Part.Wire(Part.__sortEdges__(wire.Edges))
        hght = ((nWire.BoundBox.ZMax - nWire.BoundBox.ZMin) * 2) + 2
        nWire.translate(FreeCAD.Vector(0, 0, 0 - nWire.BoundBox.ZMin - (hght / 2)))

        FreeCAD.ActiveDocument.addObject('Part::Feature','tmpWire').Shape = nWire
        NW = FreeCAD.ActiveDocument.ActiveObject
        NW.purgeTouched()
        FreeCAD.ActiveDocument.getObject(self.tempGroupName).addObject(NW)

        # if nWire.isClosed() and isPlanar(NW.Shape) and isCoPlnr is True:
        if isPlanar(NW.Shape) and isCoplanar([fc, fc]):
            # Extrude wire to twice source face height
            FreeCAD.ActiveDocument.addObject('Part::Extrusion','tmpFaceExtrude')
            EXT = FreeCAD.ActiveDocument.ActiveObject
            EXT.Base = NW
            EXT.DirMode = 'Custom'
            EXT.Dir = FreeCAD.Vector(0, 0, 1)
            EXT.LengthFwd = hght
            EXT.Solid = True
        else:
            # Create envelope from non-planar face
            env = PathUtils.getEnvelope(NW.Shape, depthparams=depthparams)
            FreeCAD.ActiveDocument.addObject('Part::Feature','tmpFaceEnvelope')
            EXT = FreeCAD.ActiveDocument.ActiveObject
            EXT.Shape = env
        EXT.recompute()
        EXT.purgeTouched()
        FreeCAD.ActiveDocument.getObject(self.tempGroupName).addObject(EXT)

        # Make cross-section and translate it
        sliceZ = EXT.Shape.BoundBox.ZMin + (EXT.Shape.BoundBox.ZLength / 2)  # slice at middle
        csFaceShape = self._makeCrossSectionToFaceshape(EXT.Shape, sliceZ, zHghtTrgt=bbZMax)

        offsetFace = FreeCAD.ActiveDocument.addObject('Part::Feature','offsetFace')
        #if obj.RespectBoundary is True or obj.BoundaryAdjustment.Value != 0:
        #    # Use Path.Area() to extract offset loop of face.
        #    offsetShape = self._extractFaceOffset(obj, csFaceShape, isHole)
        #    offsetFace.Shape = offsetShape
        #else:
        #    offsetFace.Shape = csFaceShape
        offsetShape = self._extractFaceOffset(obj, csFaceShape, isHole)
        offsetFace.Shape = offsetShape
        offsetFace.recompute()
        offsetFace.purgeTouched()
        FreeCAD.ActiveDocument.getObject(self.tempGroupName).addObject(offsetFace)
        
        return offsetFace

    def _extractFaceOffset(self, obj, baseobject, isHole):
        '''_extractFaceOffset(obj, baseobject, isHole) ... internal function.
            Original _buildPathArea() version copied from PathAreaOp.py module.  This version is modified.
            Adjustments made based on notes by @sliptonic - https://github.com/sliptonic/FreeCAD/wiki/PathArea-notes.'''
        PathLog.debug('_extractFaceOffset()')
        areaParams = {}
        offset = -1 * obj.BoundaryAdjustment.Value

        tolrnc = 0.000001
        if obj.RespectBoundary is True:
            offset += (self.radius + tolrnc)
        else:
            offset -= (self.radius + tolrnc)
        if isHole is False:
            offset = 0 - offset
        areaParams['Offset'] = offset
        areaParams['Fill'] = 1
        areaParams['Coplanar'] = 0
        areaParams['SectionCount'] = 1  # -1 = full(all per depthparams??) sections
        areaParams['Reorient'] = True
        areaParams['OpenMode'] = 0
        areaParams['MaxArcPoints'] = 400  # 400
        areaParams['Project'] = True

        area = Path.Area()  # Create instance of Area() class object
        area.setPlane(PathUtils.makeWorkplane(baseobject))  # Set working plane
        area.add(baseobject)  # obj.Shape to use for extracting offset
        area.setParams(**areaParams)  # set parameters

        # Save parameters for debugging
        obj.AreaParams = str(area.getParams())
        PathLog.debug("Area with params: {}".format(area.getParams()))

        offsetShape = area.getShape()

        return offsetShape

    # Main rotational scan functions
    def _rotationalDropCutterOp(self, obj, stl, bb):
        self.resetTolerance = 0.0000001  # degrees
        self.layerEndzMax = 0.0
        commands = []
        scanLines = []
        advances = []
        iSTG = []
        rSTG = []
        rings = []
        lCnt = 0
        rNum = 0
        # stepDeg = 1.1
        # layCircum = 1.1
        # begIdx = 0.0
        # endIdx = 0.0
        # arc = 0.0
        # sumAdv = 0.0
        bbRad = self.bbRadius

        def invertAdvances(advances):
            idxs = [1.1]
            for adv in advances:
                idxs.append(-1 * adv)
            idxs.pop(0)
            return idxs

        def linesToPointRings(scanLines):
            rngs = []
            numPnts = len(scanLines[0])  # Number of points per line along axis, at obj.SampleInterval.Value spacing
            for line in scanLines:  # extract circular set(ring) of points from scan lines
                if len(line) != numPnts:
                    PathLog.debug('Error: line lengths not equal')
                    return rngs

            for num in range(0, numPnts):
                rngs.append([1.1])  # Initiate new ring
                for line in scanLines:  # extract circular set(ring) of points from scan lines
                    rngs[num].append(line[num])
                rngs[num].pop(0)
            return rngs

        def indexAdvances(arc, stepDeg):
            indexes = [0.0]
            numSteps = int(math.floor(arc / stepDeg))
            for ns in range(0, numSteps):
                indexes.append(stepDeg)

            travel = sum(indexes)
            if arc == 360.0:
                indexes.insert(0, 0.0)
            else:
                indexes.append(arc - travel)

            return indexes

        # Compute number and size of stepdowns, and final depth
        if obj.LayerMode == 'Single-pass':
            depthparams = [self.FinalDepth]
        else:
            dep_par = PathUtils.depth_params(self.clearHeight, self.safeHeight, self.bbRadius, obj.StepDown.Value, 0.0, self.FinalDepth)
            depthparams = [i for i in dep_par]
        prevDepth = depthparams[0]
        lenDP = len(depthparams)

        # Set drop cutter extra offset
        cdeoX = obj.DropCutterExtraOffset.x
        cdeoY = obj.DropCutterExtraOffset.y

        # Set updated bound box values and redefine the new min/mas XY area of the operation based on greatest point radius of model
        bb.ZMin = -1 * bbRad
        bb.ZMax = bbRad
        if obj.RotationAxis == 'X':
            bb.YMin = -1 * bbRad
            bb.YMax = bbRad
            ymin = 0.0
            ymax = 0.0
            xmin = bb.XMin - cdeoX
            xmax = bb.XMax + cdeoX
        else:
            bb.XMin = -1 * bbRad
            bb.XMax = bbRad
            ymin = bb.YMin - cdeoY
            ymax = bb.YMax + cdeoY
            xmin = 0.0
            xmax = 0.0

        # Calculate arc
        begIdx = obj.StartIndex
        endIdx = obj.StopIndex
        if endIdx < begIdx:
            begIdx -= 360.0
        arc = endIdx - begIdx

        # Begin gcode operation with raising cutter to safe height
        commands.append(Path.Command('G0', {'Z': self.safeHeight, 'F': self.vertRapid}))

        # Complete rotational scans at layer and translate into gcode
        for layDep in depthparams:
            t_before = time.time()

            # Compute circumference and step angles for current layer
            layCircum = 2 * math.pi * layDep
            if lenDP == 1:
                layCircum = 2 * math.pi * bbRad

            # Set axial feed rates
            self.axialFeed = 360 / layCircum * self.horizFeed
            self.axialRapid = 360 / layCircum * self.horizRapid

            # Determine step angle.
            if obj.RotationAxis == obj.DropCutterDir:  # Same == indexed
                stepDeg = (self.cutOut / layCircum) * 360.0
            else:
                stepDeg = (obj.SampleInterval.Value / layCircum) * 360.0

            # Limit step angle and determine rotational index angles [indexes].
            if stepDeg > 120.0:
                stepDeg = 120.0
            advances = indexAdvances(arc, stepDeg)  # Reset for each step down layer

            # Perform rotational indexed scans to layer depth
            if obj.RotationAxis == obj.DropCutterDir:  # Same == indexed OR parallel
                sample = obj.SampleInterval.Value
            else:
                sample = self.cutOut
            scanLines = self._indexedDropCutScan(obj, stl, advances, xmin, ymin, xmax, ymax, layDep, sample)

            # Complete rotation if necessary
            if arc == 360.0:
                advances.append(360.0 - sum(advances))
                advances.pop(0)
                zero = scanLines.pop(0)
                scanLines.append(zero)

            # Translate OCL scans into gcode
            if obj.RotationAxis == obj.DropCutterDir:  # Same == indexed (cutter runs parallel to axis)
                # Invert advances if RotationAxis == Y
                if obj.RotationAxis == 'Y':
                    advances = invertAdvances(advances)

                # Translate scan to gcode
                # sumAdv = 0.0
                sumAdv = begIdx
                for sl in range(0, len(scanLines)):
                    sumAdv += advances[sl]
                    # Translate scan to gcode
                    iSTG = self._indexedScanToGcode(obj, sl, scanLines[sl], sumAdv, prevDepth, layDep, lenDP)
                    commands.extend(iSTG)

                    # Add rise to clear height before beginning next index in CutPattern: Line
                    # if obj.CutPattern == 'Line':
                    #    commands.append(Path.Command('G0', {'Z': self.clearHeight, 'F': self.vertRapid}))

                    # Raise cutter to safe height after each index cut
                    commands.append(Path.Command('G0', {'Z': self.clearHeight, 'F': self.vertRapid}))
                # Eol
            else:
                if obj.CutMode == 'Conventional':
                    advances = invertAdvances(advances)
                    advances.reverse()
                    scanLines.reverse()

                # Invert advances if RotationAxis == Y
                if obj.RotationAxis == 'Y':
                    advances = invertAdvances(advances)

                # Begin gcode operation with raising cutter to safe height
                commands.append(Path.Command('G0', {'Z': self.clearHeight, 'F': self.vertRapid}))

                # Convert rotational scans into gcode
                rings = linesToPointRings(scanLines)
                rNum = 0
                for rng in rings:
                    rSTG = self._rotationalScanToGcode(obj, rng, rNum, prevDepth, layDep, advances)
                    commands.extend(rSTG)
                    if arc != 360.0:
                        clrZ = self.layerEndzMax + self.SafeHeightOffset
                        commands.append(Path.Command('G0', {'Z': clrZ, 'F': self.vertRapid}))
                    rNum += 1
                # Eol

                # Add rise to clear height before beginning next index in CutPattern: Line
                # if obj.CutPattern == 'Line':
                #    commands.append(Path.Command('G0', {'Z': self.clearHeight, 'F': self.vertRapid}))

            prevDepth = layDep
            lCnt += 1  # increment layer count
            PathLog.info("--Layer " + str(lCnt) + ": " + str(len(advances)) + " OCL scans and gcode in " + str(time.time() - t_before) + " s")
            time.sleep(0.2)
        # Eol
        return commands

    def _indexedDropCutScan(self, obj, stl, advances, xmin, ymin, xmax, ymax, layDep, sample):
        cutterOfst = 0.0
        # radsRot = 0.0
        # reset = 0.0
        iCnt = 0
        Lines = []
        result = None

        pdc = ocl.PathDropCutter()   # create a pdc
        pdc.setCutter(self.cutter)
        pdc.setZ(layDep)  # set minimumZ (final / ta9rget depth value)
        pdc.setSampling(sample)

        # if self.useTiltCutter == True:
        if obj.CutterTilt != 0.0:
            cutterOfst = layDep * math.sin(math.radians(obj.CutterTilt))
            PathLog.info("CutterTilt: cutterOfst is " + str(cutterOfst))

        sumAdv = 0.0
        for adv in advances:
            sumAdv += adv
            if adv > 0.0:
                # Rotate STL object using OCL method
                radsRot = math.radians(adv)
                if obj.RotationAxis == 'X':
                    stl.rotate(radsRot, 0.0, 0.0)
                else:
                    stl.rotate(0.0, radsRot, 0.0)

            # Set STL after rotation is made
            pdc.setSTL(stl)

            # add Line objects to the path in this loop
            if obj.RotationAxis == 'X':
                p1 = ocl.Point(xmin, cutterOfst, 0.0)   # start-point of line
                p2 = ocl.Point(xmax, cutterOfst, 0.0)   # end-point of line
            else:
                p1 = ocl.Point(cutterOfst, ymin, 0.0)   # start-point of line
                p2 = ocl.Point(cutterOfst, ymax, 0.0)   # end-point of line

            # Create line object
            if obj.RotationAxis == obj.DropCutterDir:  # parallel cut
                if obj.CutPattern == 'ZigZag':
                    if (iCnt % 2 == 0.0):  # even
                        lo = ocl.Line(p1, p2)
                    else:  # odd
                        lo = ocl.Line(p2, p1)
                elif obj.CutPattern == 'Line':
                    if obj.CutMode == 'Conventional':
                        lo = ocl.Line(p1, p2)
                    else:
                        lo = ocl.Line(p2, p1)
            else:
                lo = ocl.Line(p1, p2)   # line-object

            path = ocl.Path()                   # create an empty path object
            path.append(lo)         # add the line to the path
            pdc.setPath(path)       # set path
            pdc.run()               # run drop-cutter on the path
            result = pdc.getCLPoints()
            Lines.append(result)  # request the list of points

            iCnt += 1
        # End loop
        # Rotate STL object back to original position using OCL method
        reset = -1 * math.radians(sumAdv - self.resetTolerance)
        if obj.RotationAxis == 'X':
            stl.rotate(reset, 0.0, 0.0)
        else:
            stl.rotate(0.0, reset, 0.0)
        self.resetTolerance = 0.0

        return Lines

    def _indexedScanToGcode(self, obj, li, CLP, idxAng, prvDep, layerDepth, numDeps):
        # generate the path commands
        output = []
        optimize = obj.OptimizeLinearPaths
        holdCount = 0
        holdStart = False
        holdStop = False
        zMax = prvDep
        lenCLP = len(CLP)
        lastCLP = lenCLP - 1
        prev = ocl.Point(float("inf"), float("inf"), float("inf"))
        nxt = ocl.Point(float("inf"), float("inf"), float("inf"))
        pnt = ocl.Point(float("inf"), float("inf"), float("inf"))

        # Create first point
        pnt.x = CLP[0].x
        pnt.y = CLP[0].y
        pnt.z = CLP[0].z + float(obj.DepthOffset.Value)

        # Rotate to correct index location
        if obj.RotationAxis == 'X':
            output.append(Path.Command('G0', {'A': idxAng, 'F': self.axialFeed}))
        else:
            output.append(Path.Command('G0', {'B': idxAng, 'F': self.axialFeed}))

        if li > 0:
            if pnt.z > self.layerEndPnt.z:
                clrZ = pnt.z + 2.0
                output.append(Path.Command('G1', {'Z': clrZ, 'F': self.vertRapid}))
        else:
            output.append(Path.Command('G0', {'Z': self.clearHeight, 'F': self.vertRapid}))

        output.append(Path.Command('G0', {'X': pnt.x, 'Y': pnt.y, 'F': self.horizRapid}))
        output.append(Path.Command('G1', {'Z': pnt.z, 'F': self.vertFeed}))

        for i in range(0, lenCLP):
            if i < lastCLP:
                nxt.x = CLP[i + 1].x
                nxt.y = CLP[i + 1].y
                nxt.z = CLP[i + 1].z + float(obj.DepthOffset.Value)
            else:
                optimize = False

            # Update zMax values
            if pnt.z > zMax:
                zMax = pnt.z

            if obj.LayerMode == 'Multi-pass':
                # if z travels above previous layer, start/continue hold high cycle
                if pnt.z > prvDep and optimize is True:
                    if self.onHold is False:
                        holdStart = True
                    self.onHold = True

                if self.onHold is True:
                    if holdStart is True:
                        # go to current coordinate
                        output.append(Path.Command('G1', {'X': pnt.x, 'Y': pnt.y, 'Z': pnt.z, 'F': self.horizFeed}))
                        # Save holdStart coordinate and prvDep values
                        self.holdPoint.x = pnt.x
                        self.holdPoint.y = pnt.y
                        self.holdPoint.z = pnt.z
                        holdCount += 1  # Increment hold count
                        holdStart = False  # cancel holdStart

                    # hold cutter high until Z value drops below prvDep
                    if pnt.z <= prvDep:
                        holdStop = True

                if holdStop is True:
                    # Send hold and current points to
                    zMax += 2.0
                    for cmd in self.holdStopCmds(obj, zMax, prvDep, pnt, "Hold Stop: in-line"):
                        output.append(cmd)
                    # reset necessary hold related settings
                    zMax = prvDep
                    holdStop = False
                    self.onHold = False
                    self.holdPoint = ocl.Point(float("inf"), float("inf"), float("inf"))

            if self.onHold is False:
                if not optimize or not self.isPointOnLine(FreeCAD.Vector(prev.x, prev.y, prev.z), FreeCAD.Vector(nxt.x, nxt.y, nxt.z), FreeCAD.Vector(pnt.x, pnt.y, pnt.z)):
                    output.append(Path.Command('G1', {'X': pnt.x, 'Y': pnt.y, 'Z': pnt.z, 'F': self.horizFeed}))
                # elif i == lastCLP:
                #     output.append(Path.Command('G1', {'X': pnt.x, 'Y': pnt.y, 'Z': pnt.z, 'F': self.horizFeed}))

            # Rotate point data
            prev.x = pnt.x
            prev.y = pnt.y
            prev.z = pnt.z
            pnt.x = nxt.x
            pnt.y = nxt.y
            pnt.z = nxt.z
        output.append(Path.Command('N (End index angle ' + str(round(idxAng, 4)) + ')', {}))

        # Save layer end point for use in transitioning to next layer
        self.layerEndPnt.x = pnt.x
        self.layerEndPnt.y = pnt.y
        self.layerEndPnt.z = pnt.z

        return output

    def _rotationalScanToGcode(self, obj, RNG, rN, prvDep, layDep, advances):
        '''_rotationalScanToGcode(obj, RNG, rN, prvDep, layDep, advances) ...
        Convert rotational scan data to gcode path commands.'''
        output = []
        nxtAng = 0
        zMax = 0.0
        # prev = ocl.Point(float("inf"), float("inf"), float("inf"))
        nxt = ocl.Point(float("inf"), float("inf"), float("inf"))
        pnt = ocl.Point(float("inf"), float("inf"), float("inf"))

        begIdx = obj.StartIndex
        endIdx = obj.StopIndex
        if endIdx < begIdx:
            begIdx -= 360.0

        # Rotate to correct index location
        axisOfRot = 'A'
        if obj.RotationAxis == 'Y':
            axisOfRot = 'B'

        # Create first point
        ang = 0.0 + obj.CutterTilt
        pnt.x = RNG[0].x
        pnt.y = RNG[0].y
        pnt.z = RNG[0].z + float(obj.DepthOffset.Value)

        # Adjust feed rate based on radius/circumference of cutter.
        # Original feed rate based on travel at circumference.
        if rN > 0:
            # if pnt.z > self.layerEndPnt.z:
            if pnt.z >= self.layerEndzMax:
                clrZ = pnt.z + 5.0
                output.append(Path.Command('G1', {'Z': clrZ, 'F': self.vertRapid}))
        else:
            output.append(Path.Command('G1', {'Z': self.clearHeight, 'F': self.vertRapid}))

        output.append(Path.Command('G0', {axisOfRot: ang, 'F': self.axialFeed}))
        output.append(Path.Command('G1', {'X': pnt.x, 'Y': pnt.y, 'F': self.axialFeed}))
        output.append(Path.Command('G1', {'Z': pnt.z, 'F': self.axialFeed}))

        lenRNG = len(RNG)
        lastIdx = lenRNG - 1
        for i in range(0, lenRNG):
            if i < lastIdx:
                nxtAng = ang + advances[i + 1]
                nxt.x = RNG[i + 1].x
                nxt.y = RNG[i + 1].y
                nxt.z = RNG[i + 1].z + float(obj.DepthOffset.Value)

            if pnt.z > zMax:
                zMax = pnt.z

            output.append(Path.Command('G1', {'X': pnt.x, 'Y': pnt.y, 'Z': pnt.z, axisOfRot: ang, 'F': self.axialFeed}))
            pnt.x = nxt.x
            pnt.y = nxt.y
            pnt.z = nxt.z
            ang = nxtAng

        # Save layer end point for use in transitioning to next layer
        self.layerEndPnt.x = RNG[0].x
        self.layerEndPnt.y = RNG[0].y
        self.layerEndPnt.z = RNG[0].z
        self.layerEndzMax = zMax

        # Move cutter to final point
        # output.append(Path.Command('G1', {'X': self.layerEndPnt.x, 'Y': self.layerEndPnt.y, 'Z': self.layerEndPnt.z, axisOfRot: endang, 'F': self.axialFeed}))

        return output

    # Main waterline functions
    def _waterlineOp(self, obj, base):
        '''_waterlineOp(obj, base) ... Main waterline function to perform waterline extraction from model.'''
        commands = []

        t_begin = time.time()
        JOB = PathUtils.findParentJob(obj)

        if base.TypeId.startswith('Mesh'):
            mesh = base.Mesh
        else:
            # try/except is for Path Jobs created before GeometryTolerance
            try:
                deflection = JOB.GeometryTolerance
            except AttributeError:
                import PathScripts.PathPreferences as PathPreferences
                deflection = PathPreferences.defaultGeometryTolerance()
            # base.Shape.tessellate(0.05) # 0.5 original value
            # mesh = MeshPart.meshFromShape(base.Shape, Deflection=deflection)
            mesh = MeshPart.meshFromShape(Shape=base.Shape, LinearDeflection=deflection, AngularDeflection=0.25, Relative=False)

        # Set bound box
        if obj.BoundBox == 'BaseBoundBox':
            bb = mesh.BoundBox
        elif obj.BoundBox == 'Stock':
            bb = JOB.Stock.Shape.BoundBox

        stl = ocl.STLSurf()
        for f in mesh.Facets:
            p = f.Points[0]
            q = f.Points[1]
            r = f.Points[2]
            t = ocl.Triangle(ocl.Point(p[0], p[1], p[2] + obj.DepthOffset.Value),
                                ocl.Point(q[0], q[1], q[2] + obj.DepthOffset.Value),
                                ocl.Point(r[0], r[1], r[2] + obj.DepthOffset.Value))
            stl.addTriangle(t)

        # Prepare global holdpoint and layerEndPnt containers
        if self.holdPoint is None:
            self.holdPoint = ocl.Point(float("inf"), float("inf"), float("inf"))
        if self.layerEndPnt is None:
            self.layerEndPnt = ocl.Point(float("inf"), float("inf"), float("inf"))

        # Set extra offset to diameter of cutter to allow cutter to move around perimeter of model
        # Need to make DropCutterExtraOffset available for waterline algorithm
        # cdeoX = obj.DropCutterExtraOffset.x
        # cdeoY = obj.DropCutterExtraOffset.y
        toolDiam = self.cutter.getDiameter()
        cdeoX = 0.6 * toolDiam
        cdeoY = 0.6 * toolDiam

        # the max and min XY area of the operation
        xmin = bb.XMin - cdeoX
        xmax = bb.XMax + cdeoX
        ymin = bb.YMin - cdeoY
        ymax = bb.YMax + cdeoY

        smplInt = obj.SampleInterval.Value
        minSampInt = 0.001  # value is mm
        if smplInt < minSampInt:
            smplInt = minSampInt

        # Determine bounding box length for the OCL scan
        bbLength = math.fabs(ymax - ymin)
        numScanLines = int(math.ceil(bbLength / smplInt) + 1)  # Number of lines

        # Compute number and size of stepdowns, and final depth
        if obj.LayerMode == 'Single-pass':
            depthparams = [obj.FinalDepth.Value]
        else:
            dep_par = PathUtils.depth_params(obj.ClearanceHeight.Value, obj.SafeHeight.Value, obj.StartDepth.Value, obj.StepDown.Value, 0.0, obj.FinalDepth.Value)
            depthparams = [dp for dp in dep_par]
        lenDP = len(depthparams)

        # Scan the piece to depth at smplInt
        oclScan = []
        oclScan = self._waterlineDropCutScan(stl, smplInt, xmin, xmax, ymin, depthparams[lenDP - 1], numScanLines)
        lenOS = len(oclScan)
        ptPrLn = int(lenOS / numScanLines)

        # Convert oclScan list of points to multi-dimensional list
        scanLines = []
        for L in range(0, numScanLines):
            scanLines.append([])
            for P in range(0, ptPrLn):
                pi = L * ptPrLn + P
                scanLines[L].append(oclScan[pi])
        lenSL = len(scanLines)
        pntsPerLine = len(scanLines[0])
        PathLog.info("--OCL scan: " + str(lenSL * pntsPerLine) + " points, with " + str(numScanLines) + " lines and " + str(pntsPerLine) + " pts/line")
        PathLog.info("--Setup, OCL scan, and scan conversion to multi-dimen. list took " + str(time.time() - t_begin) + " s")

        # Extract Wl layers per depthparams
        lyr = 0
        cmds = []
        layTime = time.time()
        self.topoMap = []
        for layDep in depthparams:
            cmds = self._getWaterline(obj, scanLines, layDep, lyr, lenSL, pntsPerLine)
            commands.extend(cmds)
            lyr += 1
        PathLog.info("--All layer scans combined took " + str(time.time() - layTime) + " s")
        return commands

    def _waterlineDropCutScan(self, stl, smplInt, xmin, xmax, ymin, fd, numScanLines):
        '''_waterlineDropCutScan(stl, smplInt, xmin, xmax, ymin, fd, numScanLines) ... 
        Perform OCL scan for waterline purpose.'''
        pdc = ocl.PathDropCutter()   # create a pdc
        pdc.setSTL(stl)
        pdc.setCutter(self.cutter)
        pdc.setZ(fd)  # set minimumZ (final / target depth value)
        pdc.setSampling(smplInt)

        # Create line object as path
        path = ocl.Path()                   # create an empty path object
        for nSL in range(0, numScanLines):
            yVal = ymin + (nSL * smplInt)
            p1 = ocl.Point(xmin, yVal, fd)   # start-point of line
            p2 = ocl.Point(xmax, yVal, fd)   # end-point of line
            path.append(ocl.Line(p1, p2))
            # path.append(l)        # add the line to the path
        pdc.setPath(path)
        pdc.run()  # run drop-cutter on the path

        # return the list the points
        return pdc.getCLPoints()

    def _getWaterline(self, obj, scanLines, layDep, lyr, lenSL, pntsPerLine):
        '''_getWaterline(obj, scanLines, layDep, lyr, lenSL, pntsPerLine) ... Get waterline.'''
        commands = []
        cmds = []
        loopList = []
        self.topoMap = []
        # Create topo map from scanLines (highs and lows)
        self.topoMap = self._createTopoMap(scanLines, layDep, lenSL, pntsPerLine)
        # Add buffer lines and columns to topo map
        self._bufferTopoMap(lenSL, pntsPerLine)
        # Identify layer waterline from OCL scan
        self._highlightWaterline(4, 9)
        # Extract waterline and convert to gcode
        loopList = self._extractWaterlines(obj, scanLines, lyr, layDep)
        time.sleep(0.1)
        # save commands
        for loop in loopList:
            cmds = self._loopToGcode(obj, layDep, loop)
            commands.extend(cmds)
        return commands

    def _createTopoMap(self, scanLines, layDep, lenSL, pntsPerLine):
        '''_createTopoMap(scanLines, layDep, lenSL, pntsPerLine) ... Create topo map version of OCL scan data.'''
        topoMap = []
        for L in range(0, lenSL):
            topoMap.append([])
            for P in range(0, pntsPerLine):
                if scanLines[L][P].z > layDep:
                    topoMap[L].append(2)
                else:
                    topoMap[L].append(0)
        return topoMap

    def _bufferTopoMap(self, lenSL, pntsPerLine):
        '''_bufferTopoMap(lenSL, pntsPerLine) ... Add buffer boarder of zeros to all sides to topoMap data.'''
        pre = [0, 0]
        post = [0, 0]
        for p in range(0, pntsPerLine):
            pre.append(0)
            post.append(0)
        for l in range(0, lenSL):
            self.topoMap[l].insert(0, 0)
            self.topoMap[l].append(0)
        self.topoMap.insert(0, pre)
        self.topoMap.append(post)
        return True

    def _highlightWaterline(self, extraMaterial, insCorn):
        '''_highlightWaterline(extraMaterial, insCorn) ... Highlight the waterline data, separating from extra material.'''
        TM = self.topoMap
        lastPnt = len(TM[1]) - 1
        lastLn = len(TM) - 1
        highFlag = 0

        # ("--Convert parallel data to ridges")
        for lin in range(1, lastLn):
            for pt in range(1, lastPnt):  # Ignore first and last points
                if TM[lin][pt] == 0:
                    if TM[lin][pt + 1] == 2:  # step up
                        TM[lin][pt] = 1
                    if TM[lin][pt - 1] == 2:  # step down
                        TM[lin][pt] = 1

        # ("--Convert perpendicular data to ridges and highlight ridges")
        for pt in range(1, lastPnt):  # Ignore first and last points
            for lin in range(1, lastLn):
                if TM[lin][pt] == 0:
                    highFlag = 0
                    if TM[lin + 1][pt] == 2:  # step up
                        TM[lin][pt] = 1
                    if TM[lin - 1][pt] == 2:  # step down
                        TM[lin][pt] = 1
                elif TM[lin][pt] == 2:
                    highFlag += 1
                    if highFlag == 3:
                        if TM[lin - 1][pt - 1] < 2 or TM[lin - 1][pt + 1] < 2:
                            highFlag = 2
                        else:
                            TM[lin - 1][pt] = extraMaterial
                            highFlag = 2

        # ("--Square corners")
        for pt in range(1, lastPnt):
            for lin in range(1, lastLn):
                if TM[lin][pt] == 1:                    # point == 1
                    cont = True
                    if TM[lin + 1][pt] == 0:            # forward == 0
                        if TM[lin + 1][pt - 1] == 1:    # forward left == 1
                            if TM[lin][pt - 1] == 2:    # left == 2
                                TM[lin + 1][pt] = 1     # square the corner
                                cont = False

                        if cont is True and TM[lin + 1][pt + 1] == 1:  # forward right == 1
                            if TM[lin][pt + 1] == 2:    # right == 2
                                TM[lin + 1][pt] = 1     # square the corner
                        cont = True

                    if TM[lin - 1][pt] == 0:          # back == 0
                        if TM[lin - 1][pt - 1] == 1:    # back left == 1
                            if TM[lin][pt - 1] == 2:    # left == 2
                                TM[lin - 1][pt] = 1     # square the corner
                                cont = False

                        if cont is True and TM[lin - 1][pt + 1] == 1:  # back right == 1
                            if TM[lin][pt + 1] == 2:    # right == 2
                                TM[lin - 1][pt] = 1     # square the corner

        # remove inside corners
        for pt in range(1, lastPnt):
            for lin in range(1, lastLn):
                if TM[lin][pt] == 1:                    # point == 1
                    if TM[lin][pt + 1] == 1:
                        if TM[lin - 1][pt + 1] == 1 or TM[lin + 1][pt + 1] == 1:
                            TM[lin][pt + 1] = insCorn
                    elif TM[lin][pt - 1] == 1:
                        if TM[lin - 1][pt - 1] == 1 or TM[lin + 1][pt - 1] == 1:
                            TM[lin][pt - 1] = insCorn

        return True

    def _extractWaterlines(self, obj, oclScan, lyr, layDep):
        '''_extractWaterlines(obj, oclScan, lyr, layDep) ... Extract water lines from OCL scan data.'''
        srch = True
        lastPnt = len(self.topoMap[0]) - 1
        lastLn = len(self.topoMap) - 1
        maxSrchs = 5
        srchCnt = 1
        loopList = []
        loop = []
        loopNum = 0

        if obj.CutMode == 'Conventional':
            lC = [1, 1, 1, 0, -1, -1, -1, 0, 1, 1, 1, 0, -1, -1, -1, 0, 1, 1, 1, 0, -1, -1, -1, 0]
            pC = [-1, 0, 1, 1, 1, 0, -1, -1, -1, 0, 1, 1, 1, 0, -1, -1, -1, 0, 1, 1, 1, 0, -1, -1]
        else:
            lC = [-1, -1, -1, 0, 1, 1, 1, 0, -1, -1, -1, 0, 1, 1, 1, 0, -1, -1, -1, 0, 1, 1, 1, 0]
            pC = [-1, 0, 1, 1, 1, 0, -1, -1, -1, 0, 1, 1, 1, 0, -1, -1, -1, 0, 1, 1, 1, 0, -1, -1]

        while srch is True:
            srch = False
            if srchCnt > maxSrchs:
                PathLog.info("Max search scans, " + str(maxSrchs) + " reached\nPossible incomplete waterline result!")
                break
            for L in range(1, lastLn):
                for P in range(1, lastPnt):
                    if self.topoMap[L][P] == 1:
                        # start loop follow
                        srch = True
                        loopNum += 1
                        loop = self._trackLoop(oclScan, lC, pC, L, P, loopNum)
                        self.topoMap[L][P] = 0  # Mute the starting point
                        loopList.append(loop)
            srchCnt += 1
        PathLog.debug("Search count for layer " + str(lyr) + " is " + str(srchCnt) + ", with " + str(loopNum) + " loops.")
        return loopList

    def _trackLoop(self, oclScan, lC, pC, L, P, loopNum):
        '''_trackLoop(oclScan, lC, pC, L, P, loopNum) ... Track the loop direction.'''
        loop = [oclScan[L - 1][P - 1]]  # Start loop point list
        cur = [L, P, 1]
        prv = [L, P - 1, 1]
        nxt = [L, P + 1, 1]
        follow = True
        ptc = 0
        ptLmt = 200000
        while follow is True:
            ptc += 1
            if ptc > ptLmt:
                PathLog.info("Loop number " + str(loopNum) + " at [" + str(nxt[0]) + ", " + str(nxt[1]) + "] pnt count exceeds, " + str(ptLmt) + ".  Stopped following loop.")
                break
            nxt = self._findNextWlPoint(lC, pC, cur[0], cur[1], prv[0], prv[1])  # get next point
            loop.append(oclScan[nxt[0] - 1][nxt[1] - 1])  # add it to loop point list
            self.topoMap[nxt[0]][nxt[1]] = nxt[2]  # Mute the point, if not Y stem
            if nxt[0] == L and nxt[1] == P:  # check if loop complete
                follow = False
            elif nxt[0] == cur[0] and nxt[1] == cur[1]:  # check if line cannot be detected
                follow = False
            prv = cur
            cur = nxt
        return loop

    def _findNextWlPoint(self, lC, pC, cl, cp, pl, pp):
        '''_findNextWlPoint(lC, pC, cl, cp, pl, pp) ...
        Find the next waterline point in the point cloud layer provided.'''
        dl = cl - pl
        dp = cp - pp
        num = 0
        i = 3
        s = 0
        mtch = 0
        found = False
        while mtch < 8:  # check all 8 points around current point
            if lC[i] == dl:
                if pC[i] == dp:
                    s = i - 3
                    found = True
                    # Check for y branch where current point is connection between branches
                    for y in range(1, mtch):
                        if lC[i + y] == dl:
                            if pC[i + y] == dp:
                                num = 1
                                break
                    break
            i += 1
            mtch += 1
        if found is False:
            # ("_findNext: No start point found.")
            return [cl, cp, num]

        for r in range(0, 8):
            l = cl + lC[s + r]
            p = cp + pC[s + r]
            if self.topoMap[l][p] == 1:
                return [l, p, num]

        # ("_findNext: No next pnt found")
        return [cl, cp, num]

    def _loopToGcode(self, obj, layDep, loop):
        '''_loopToGcode(obj, layDep, loop) ... Convert set of loop points to Gcode.'''
        # generate the path commands
        output = []
        optimize = obj.OptimizeLinearPaths

        prev = ocl.Point(float("inf"), float("inf"), float("inf"))
        nxt = ocl.Point(float("inf"), float("inf"), float("inf"))
        pnt = ocl.Point(float("inf"), float("inf"), float("inf"))

        # Create first point
        pnt.x = loop[0].x
        pnt.y = loop[0].y
        pnt.z = layDep

        # Position cutter to begin loop
        output.append(Path.Command('G0', {'Z': obj.ClearanceHeight.Value, 'F': self.vertRapid}))
        output.append(Path.Command('G0', {'X': pnt.x, 'Y': pnt.y, 'F': self.horizRapid}))
        output.append(Path.Command('G1', {'Z': pnt.z, 'F': self.vertFeed}))

        lenCLP = len(loop)
        lastIdx = lenCLP - 1
        # Cycle through each point on loop
        for i in range(0, lenCLP):
            if i < lastIdx:
                nxt.x = loop[i + 1].x
                nxt.y = loop[i + 1].y
                nxt.z = layDep
            else:
                optimize = False

            if not optimize or not self.isPointOnLine(FreeCAD.Vector(prev.x, prev.y, prev.z), FreeCAD.Vector(nxt.x, nxt.y, nxt.z), FreeCAD.Vector(pnt.x, pnt.y, pnt.z)):
                output.append(Path.Command('G1', {'X': pnt.x, 'Y': pnt.y, 'F': self.horizFeed}))

            # Rotate point data
            prev.x = pnt.x
            prev.y = pnt.y
            prev.z = pnt.z
            pnt.x = nxt.x
            pnt.y = nxt.y
            pnt.z = nxt.z

        # Save layer end point for use in transitioning to next layer
        self.layerEndPnt.x = pnt.x
        self.layerEndPnt.y = pnt.y
        self.layerEndPnt.z = pnt.z

        return output

    # Support functions for both dropcutter and waterline operations
    def isPointOnLine(self, strtPnt, endPnt, pointP):
        '''isPointOnLine(strtPnt, endPnt, pointP) ... Determine if a given point is on the line defined by start and end points.'''
        tolerance = 1e-6
        vectorAB = endPnt - strtPnt
        vectorAC = pointP - strtPnt
        crossproduct = vectorAB.cross(vectorAC)
        dotproduct = vectorAB.dot(vectorAC)

        if crossproduct.Length > tolerance:
            return False

        if dotproduct < 0:
            return False

        if dotproduct > vectorAB.Length * vectorAB.Length:
            return False

        return True

    def holdStopCmds(self, obj, zMax, pd, p2, txt):
        '''holdStopCmds(obj, zMax, pd, p2, txt) ... Gcode commands to be executed at beginning of hold.'''
        cmds = []
        msg = 'N (' + txt + ')'
        cmds.append(Path.Command(msg, {}))  # Raise cutter rapid to zMax in line of travel
        cmds.append(Path.Command('G0', {'Z': zMax, 'F': self.vertRapid}))  # Raise cutter rapid to zMax in line of travel
        cmds.append(Path.Command('G0', {'X': p2.x, 'Y': p2.y, 'F': self.horizRapid}))  # horizontal rapid to current XY coordinate
        if zMax != pd:
            cmds.append(Path.Command('G0', {'Z': pd, 'F': self.vertRapid}))  # drop cutter down rapidly to prevDepth depth
            cmds.append(Path.Command('G0', {'Z': p2.z, 'F': self.vertFeed}))  # drop cutter down to current Z depth, returning to normal cut path and speed
        return cmds

    def holdStopEndCmds(self, obj, p2, txt):
        '''holdStopEndCmds(obj, p2, txt) ... Gcode commands to be executed at end of hold stop.'''
        cmds = []
        msg = 'N (' + txt + ')'
        cmds.append(Path.Command(msg, {}))  # Raise cutter rapid to zMax in line of travel
        cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))  # Raise cutter rapid to zMax in line of travel
        # cmds.append(Path.Command('G0', {'X': p2.x, 'Y': p2.y, 'F': self.horizRapid}))  # horizontal rapid to current XY coordinate
        return cmds

    def subsectionCLP(self, CLP, xmin, ymin, xmax, ymax):
        '''subsectionCLP(CLP, xmin, ymin, xmax, ymax) ...
        This function returns a subsection of the CLP scan, limited to the min/max values supplied.'''
        section = list()
        lenCLP = len(CLP)
        for i in range(0, lenCLP):
            if CLP[i].x < xmax:
                if CLP[i].y < ymax:
                    if CLP[i].x > xmin:
                        if CLP[i].y > ymin:
                            section.append(CLP[i])
        return section

    def getMaxHeightBetweenPoints(self, finalDepth, p1, p2, cutter, CLP):
        ''' getMaxHeightBetweenPoints(finalDepth, p1, p2, cutter, CLP) ...
        This function connects two HOLD points with line.
        Each point within the subsection point list is tested to determinie if it is under cutter.
        Points determined to be under the cutter on line are tested for z height.
        The highest z point is the requirement for clearance between p1 and p2, and returned as zMax with 2 mm extra.
        '''
        dx = (p2.x - p1.x)
        if dx == 0.0:
            dx = 0.00001  # Need to employ a global tolerance here
        m = (p2.y - p1.y) / dx
        b = p1.y - (m * p1.x)

        avoidTool = round(cutter * 0.75, 1)  # 1/2 diam. of cutter is theoretically safe, but 3/4 diam is used for extra clearance
        zMax = finalDepth
        lenCLP = len(CLP)
        for i in range(0, lenCLP):
            mSqrd = m**2
            if mSqrd < 0.0000001:  # Need to employ a global tolerance here
                mSqrd = 0.0000001
            perpDist = math.sqrt((CLP[i].y - (m * CLP[i].x) - b)**2 / (1 + 1 / (mSqrd)))
            if perpDist < avoidTool:  # if point within cutter reach on line of travel, test z height and update as needed
                if CLP[i].z > zMax:
                    zMax = CLP[i].z
        return zMax + 2.0
    
    def resetOpVariables(self, all=True):
        '''resetOpVariables() ... Reset class variables used for instance of operation.'''
        self.holdPoint = None
        self.layerEndPnt = None
        self.onHold = False
        self.SafeHeightOffset = 2.0
        self.ClearHeightOffset = 4.0
        self.layerEndzMax = 0.0
        self.resetTolerance = 0.0
        self.holdPntCnt = 0
        self.bbRadius = 0.0
        self.axialFeed = 0.0
        self.axialRapid = 0.0
        self.FinalDepth = 0.0
        self.clearHeight = 0.0
        self.safeHeight = 0.0
        self.faceZMax = -999999999999.0
        if all is True:
            self.cutter = None
            self.stl = None
            self.fullSTL = None
            self.cutOut = 0.0
            self.radius = 0.0
            self.useTiltCutter = False
        return True

    def deleteOpVariables(self, all=True):
        '''deleteOpVariables() ... Reset class variables used for instance of operation.'''
        del self.holdPoint
        del self.layerEndPnt
        del self.onHold
        del self.SafeHeightOffset
        del self.ClearHeightOffset
        del self.layerEndzMax
        del self.resetTolerance
        del self.holdPntCnt
        del self.bbRadius
        del self.axialFeed
        del self.axialRapid
        del self.FinalDepth
        del self.clearHeight
        del self.safeHeight
        del self.faceZMax
        if all is True:
            del self.cutter
            del self.stl
            del self.fullSTL
            del self.cutOut
            del self.radius
            del self.useTiltCutter
        return True

    def setOclCutter(self, obj):
        ''' setOclCutter(obj) ... Translation function to convert FreeCAD tool definition to OCL formatted tool. '''
        # Set cutter details
        #  https://www.freecadweb.org/api/dd/dfe/classPath_1_1Tool.html#details
        diam_1 = float(obj.ToolController.Tool.Diameter)
        lenOfst = obj.ToolController.Tool.LengthOffset if hasattr(obj.ToolController.Tool, 'LengthOffset') else 0
        FR = obj.ToolController.Tool.FlatRadius if hasattr(obj.ToolController.Tool, 'FlatRadius') else 0
        CEH = obj.ToolController.Tool.CuttingEdgeHeight if hasattr(obj.ToolController.Tool, 'CuttingEdgeHeight') else 0
        CEA = obj.ToolController.Tool.CuttingEdgeAngle if hasattr(obj.ToolController.Tool, 'CuttingEdgeAngle') else 0

        PathLog.debug('ToolType: {}'.format(obj.ToolController.Tool.ToolType))
        if obj.ToolController.Tool.ToolType == 'EndMill':
            # Standard End Mill
            return ocl.CylCutter(diam_1, (CEH + lenOfst))

        elif obj.ToolController.Tool.ToolType == 'BallEndMill' and FR == 0.0:
            # Standard Ball End Mill
            # OCL -> BallCutter::BallCutter(diameter, length)
            self.useTiltCutter = True
            return ocl.BallCutter(diam_1, (diam_1 / 2 + lenOfst))

        elif obj.ToolController.Tool.ToolType == 'BallEndMill' and FR > 0.0:
            # Bull Nose or Corner Radius cutter
            # Reference: https://www.fine-tools.com/halbstabfraeser.html
            # OCL -> BallCutter::BallCutter(diameter, length)
            return ocl.BullCutter(diam_1, FR, (CEH + lenOfst))

        elif obj.ToolController.Tool.ToolType == 'Engraver' and FR > 0.0:
            # Bull Nose or Corner Radius cutter
            # Reference: https://www.fine-tools.com/halbstabfraeser.html
            # OCL -> ConeCutter::ConeCutter(diameter, angle, lengthOffset)
            return ocl.ConeCutter(diam_1, (CEA / 2), lenOfst)

        elif obj.ToolController.Tool.ToolType == 'ChamferMill':
            # Bull Nose or Corner Radius cutter
            # Reference: https://www.fine-tools.com/halbstabfraeser.html
            # OCL -> ConeCutter::ConeCutter(diameter, angle, lengthOffset)
            return ocl.ConeCutter(diam_1, (CEA / 2), lenOfst)
        else:
            # Default to standard end mill
            PathLog.warning("Defaulting cutter to standard end mill.")
            return ocl.CylCutter(diam_1, (CEH + lenOfst))

        # http://www.carbidecutter.net/products/carbide-burr-cone-shape-sm.html
        '''
            return "Drill";
            return "CenterDrill";
            return "CounterSink";
            return "CounterBore";
            return "FlyCutter";
            return "Reamer";
            return "Tap";
            return "EndMill";
            return "SlotCutter";
            return "BallEndMill";
            return "ChamferMill";
            return "CornerRound";
            return "Engraver";
            return "Undefined";
        '''
        PathLog.error('Unable to set OCL cutter.')
        return False

    def isPocket(self, b, f, w):
        e = w.Edges[0]
        for fi in range(0, len(b.Shape.Faces)):
            face = b.Shape.Faces[fi]
            for ei in range(0, len(face.Edges)):
                edge = face.Edges[ei]
                if e.isSame(edge) is True:
                    if f is face:
                        # Alternative: run loop to see if all edges are same
                        pass  # same source face, look for another
                    else:
                        if face.CenterOfMass.z < f.CenterOfMass.z:
                            return True
        return False

    def getAllIncludedFaces(self, base, env, faceZ):
        included = []
        eXMin = env.BoundBox.XMin
        eXMax = env.BoundBox.XMax
        eYMin = env.BoundBox.YMin
        eYMax = env.BoundBox.YMax
        # eZMin = env.BoundBox.ZMin
        eZMin = faceZ
        # eZMax = env.BoundBox.ZMax

        def isOverlap(fMn, fMx, eMn, eMx):
            if fMx > eMn:
                if fMx <= eMx:
                    return True
                elif fMx >= eMx and fMn <= eMx:
                    return True
            if fMn < eMx:
                if fMn >= eMn:
                    return True
                elif fMn <= eMn and fMx >= eMn:
                    return True
            return False

        for fi in range(0, len(base.Shape.Faces)):
            incl = False
            face = base.Shape.Faces[fi]
            fXMin = face.BoundBox.XMin
            fXMax = face.BoundBox.XMax
            fYMin = face.BoundBox.YMin
            fYMax = face.BoundBox.YMax
            # fZMin = face.BoundBox.ZMin
            fZMax = face.BoundBox.ZMax
            if fZMax > eZMin:
                if isOverlap(fXMin, fXMax, eXMin, eXMax) is True:
                    if isOverlap(fYMin, fYMax, eYMin, eYMax) is True:
                        incl = True
            if incl is True:
                included.append(face)
        return included

    def determineVectDirect(self, pnt, nxt, travVect):
        if nxt.x == pnt.x:
            travVect.x = 0
        elif nxt.x < pnt.x:
            travVect.x = -1
        else:
            travVect.x = 1

        if nxt.y == pnt.y:
            travVect.y = 0
        elif nxt.y < pnt.y:
            travVect.y = -1
        else:
            travVect.y = 1
        return travVect

    def determineLineOfTravel(self, travVect):
        if travVect.x == 0 and travVect.y != 0:
            lineOfTravel = "Y"
        elif travVect.y == 0 and travVect.x != 0:
            lineOfTravel = "X"
        else:
            lineOfTravel = "O"  # used for turns
        return lineOfTravel

    def isCollinear(self, strtPnt, endPnt, pointP):
        '''isCollinear(strtPnt, endPnt, pointP) ... Determine if a given point is on the line defined by start and end points.'''
        tolerance = 1e-6
        # y = mx + b
        # b = y - mx
        dY = endPnt.y - strtPnt.y
        dX = endPnt.x - strtPnt.x
        if dX == 0:
            # Vertical line
            if abs(endPnt.x - pointP.x) < tolerance:
                return True
            else:
                return False
        else:
            m = dY / dX
            b = strtPnt.y - (m * strtPnt.x)
            x = pointP.x
            y = pointP.y
            if abs(y - ((m * x) + b)) < tolerance:
                return True
            else:
                return False


        return True

    def _makeCrossSectionToFaceshape(self, shape, sliceZ, zHghtTrgt=None):
        '''_makeCrossSectionToFaceshape(shape, sliceZ, zHghtTrgt=None)... 
        Creates cross-section objectc from shape.  Translates cross-section to zHghtTrgt if available.
        Makes face shape from cross-section object. Returns face shape at zHghtTrgt.'''
        # Create cross-section of shape and translate
        wires = list()
        for i in shape.slice(FreeCAD.Vector(0, 0, 1), sliceZ):
            wires.append(i)
        comp = Part.Compound(wires)
        if zHghtTrgt is not None:
            comp.translate(FreeCAD.Vector(0, 0, zHghtTrgt - sliceZ))
        cs = FreeCAD.ActiveDocument.addObject('Part::Feature','tmpEnvCrossSection')
        cs.Shape = comp
        cs.recompute()
        cs.purgeTouched()
        FreeCAD.ActiveDocument.getObject(self.tempGroupName).addObject(cs)
        # Create face shape from cross-section
        csFaceShape = Part.Face(cs.Shape.Wires[0])
        return csFaceShape

    def _loopToLineSegments(self, obj, COM, edge):
        LOOPSEGS = list()
        Names = list()

        # set initial placement - used for each line
        pl = FreeCAD.Placement()
        pl.Rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 0.0)
        pl.Base = FreeCAD.Vector(0, 0, 0)

        RING = list()
        radPnt = FreeCAD.Vector(edge.Vertexes[0].X, edge.Vertexes[0].Y, 0.0)
        R = abs(radPnt.sub(COM).Length)
        segLen = obj.SampleInterval.Value
        C = 2 * math.pi * R  # R=radius, C4=1/4 circumfrence
        numSegs = math.ceil(C / segLen)
        segAng = (math.pi * 2) / numSegs

        # Create segmented arcs for each quadrant
        curAng = 0.0
        p1 = FreeCAD.Vector(COM.x + R, COM.y, 0)
        for s in range(1, math.floor(numSegs)):
            curAng += segAng
            X = R * math.cos(curAng)
            Y = R * math.sin(curAng)
            p2 = FreeCAD.Vector(COM.x + X, COM.y + Y, 0)
            RING.append((p1, p2))
            p1 = p2
        p2 = FreeCAD.Vector(COM.x + R, COM.y, 0)
        RING.append((p1, p2))

        # For debugging: Add visuales of line segments generated for OCL scan
        if PathLog.getLevel(PathLog.thisModule()) == 4:
            TG = FreeCAD.ActiveDocument.addObject('App::DocumentObjectGroup', 'loopSegs')
            tgName = FreeCAD.ActiveDocument.ActiveObject.Name
            TG.purgeTouched()
            FreeCAD.ActiveDocument.getObject(self.tempGroupName).addObject(FreeCAD.ActiveDocument.getObject(tgName))

            for (p1, p2) in RING:
                line = Draft.makeWire([p1, p2], placement=pl, closed=False, face=False, support=None)
                Draft.autogroup(line)
                lineName = FreeCAD.ActiveDocument.ActiveObject.Name
                Names.append(lineName)
                line.recompute()
                line.purgeTouched()

            # Add all new line objects to temporary group for deletion
            for nm in Names:
                TG.addObject(FreeCAD.ActiveDocument.getObject(nm))

        if obj.CutMode == 'Climb':
            RING.reverse()
            for (p1, p2) in RING:
                LOOPSEGS.append((p2, p1))
            return LOOPSEGS

        return RING

    def _arcToLineSegments(self, ei, obj, COM, edge):
        ARCSEGS = list()
        Names = list()

        # set initial placement - used for each line
        pl = FreeCAD.Placement()
        pl.Rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 0.0)
        pl.Base = FreeCAD.Vector(0, 0, 0)

        ARC = list()
        lstVrt = len(edge.Vertexes) - 1
        v1 = FreeCAD.Vector(edge.Vertexes[0].X, edge.Vertexes[0].Y, 0.0)
        v2 = FreeCAD.Vector(edge.Vertexes[1].X, edge.Vertexes[1].Y, 0.0)
        R = abs(v1.sub(COM).Length)
        segLen = obj.SampleInterval.Value
        C = 2 * math.pi * R
        fullNumSegs = math.ceil(C / segLen)
        fullSegAng = (math.pi * 2) / fullNumSegs

        d1 = v1.sub(COM)
        d2 = v2.sub(COM)
        dAxis = FreeCAD.Vector(R, 0, 0)
        arc = d1.getAngle(d2)

        numSegs = math.floor(edge.Length / segLen)
        curAng = self._mapPointToRadianCircle(d1)
        p1 = v1
        for s in range(1, numSegs):
            curAng += fullSegAng
            X = R * math.cos(curAng)
            Y = R * math.sin(curAng)
            p2 = FreeCAD.Vector(COM.x + X, COM.y + Y, 0)
            ARC.append((p1, p2))
            p1 = p2
        p2 = v2
        ARC.append((p1, p2))

        # For debugging: Add visuales of line segments generated for OCL scan
        if PathLog.getLevel(PathLog.thisModule()) == 4:
            TG = FreeCAD.ActiveDocument.addObject('App::DocumentObjectGroup', 'ArcSegsGrp_{}'.format(ei))
            tgName = FreeCAD.ActiveDocument.ActiveObject.Name
            TG.purgeTouched()
            FreeCAD.ActiveDocument.getObject(self.tempGroupName).addObject(FreeCAD.ActiveDocument.getObject(tgName))

            for (p1, p2) in ARC:
                line = Draft.makeWire([p1, p2], placement=pl, closed=False, face=False, support=None)
                Draft.autogroup(line)
                lineName = FreeCAD.ActiveDocument.ActiveObject.Name
                Names.append(lineName)
                line.recompute()
                line.purgeTouched()

            # Add all new line objects to temporary group for deletion
            for nm in Names:
                TG.addObject(FreeCAD.ActiveDocument.getObject(nm))

        return ARC

    def _mapPointToRadianCircle(self, pnt):
        # map point to radian angle 0-2pi
        if pnt.x == 0:
            if pnt.y > 0:
                return math.pi / 2
            else:
                return 3 * math.pi / 2
        elif pnt.y == 0:
            if pnt.x > 0:
                return 0.0
            else:
                return math.pi

        absAng = math.atan(abs(pnt.y) / abs(pnt.x))
        if pnt.x > 0:
            if pnt.y >= 0:
                return absAng
            else:
                return (2 * math.pi) - absAng  # (3 * math.pi / 2) + absAng
        else:
            if pnt.y > 0:
                return math.pi - absAng  # (math.pi / 2) + absAng
            else:
                return (math.pi) + absAng

    def _getMinSafeTravelHeight(self, pdc, p1, p2):
        p1p2Tup = ((p1.x, p1.y), (p2.x, p2.y))
        LINE = self._planarDropCutScan(pdc, p1p2Tup)
        zMax = LINE[0].z
        for p in LINE:
            if p.z > zMax:
                zMax = p.z
        return zMax


def SetupProperties():
    ''' SetupProperties() ... Return list of properties required for operation.'''
    setup = []
    setup.append('Algorithm')
    setup.append('DropCutterDir')
    setup.append('BoundBox')
    setup.append('StepOver')
    setup.append('DepthOffset')
    setup.append('LayerMode')
    setup.append('ScanType')
    setup.append('RotationAxis')
    setup.append('CutMode')
    setup.append('SampleInterval')
    setup.append('StartIndex')
    setup.append('StopIndex')
    setup.append('CutterTilt')
    setup.append('CutPattern')
    setup.append('CutPatternAngle')
    setup.append('HandleMultipleFeatures')
    setup.append('CutInternalFeatures')
    setup.append('BoundaryAdjustment')
    setup.append('RespectBoundary')
    setup.append('OptimizeLinearTransitions')
    setup.append('OptimizeArcTransitions')
    setup.append('FinishPassOnly')
    setup.append('AreaParams')
    setup.append('AvoidLastXFaces')
    setup.append('UseStartPoint')
    setup.append('StartPoint')
    # Targeted for possible removal
    setup.append('IgnoreWasteDepth')
    setup.append('IgnoreWaste')
    setup.append('ReleaseFromWaste')
    return setup


def Create(name, obj=None):
    '''Create(name) ... Creates and returns a Surface operation.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectSurface(obj, name)
    return obj
