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
from DraftGeomUtils import isPlanar
from PathScripts.PathGeom import isHorizontal

from PySide import QtCore
import time
import math
import Part
import Draft

__title__ = "Path Surface Operation"
__author__ = "sliptonic (Brad Collette)"
__url__ = "http://www.freecadweb.org"
__doc__ = "Class and implementation of Mill Facing operation."
__contributors__ = "roivai[FreeCAD], russ4262 (Russell Johnson)"
__created__ = "2016"
__scriptVersion__ = "4i Usable"
__lastModified__ = "2020-01-12 12:12 CST"

PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
#PathLog.trackModule(PathLog.thisModule())


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
        # return PathOp.FeatureTool | PathOp.FeatureDepths | PathOp.FeatureHeights | PathOp.FeatureStepDown | PathOp.FeatureCoolant
        return PathOp.FeatureTool | PathOp.FeatureDepths | PathOp.FeatureHeights | PathOp.FeatureStepDown | PathOp.FeatureCoolant | PathOp.FeatureBaseFaces

    def initOperation(self, obj):
        '''initPocketOp(obj) ... create facing specific properties'''
        obj.addProperty('App::PropertyEnumeration', 'Algorithm', 'Algorithm', QtCore.QT_TRANSLATE_NOOP('App::Property', 'The library to use to generate the path'))
        obj.addProperty('App::PropertyEnumeration', 'DropCutterDir', 'Algorithm', QtCore.QT_TRANSLATE_NOOP('App::Property', 'The direction along which dropcutter lines are created'))
        obj.addProperty('App::PropertyEnumeration', 'BoundBox', 'Algorithm', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Should the operation be limited by the stock object or by the bounding box of the base object'))
        obj.addProperty('App::PropertyVectorDistance', 'DropCutterExtraOffset', 'Algorithm', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Additional offset to the selected bounding box'))
        obj.addProperty('App::PropertyEnumeration', 'ScanType', 'Algorithm', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Planar: Flat, 3D surface scan.  Rotational: 4th-axis rotational scan.'))
        obj.addProperty('App::PropertyEnumeration', 'LayerMode', 'Algorithm', QtCore.QT_TRANSLATE_NOOP('App::Property', 'The completion mode for the operation: single or multi-pass'))
        obj.addProperty('App::PropertyEnumeration', 'CutMode', 'Path', QtCore.QT_TRANSLATE_NOOP('App::Property', 'The direction that the toolpath should go around the part: Climb(ClockWise) or Conventional(CounterClockWise)'))
        obj.addProperty('App::PropertyEnumeration', 'CutPattern', 'Path', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Clearing pattern to use'))
        obj.addProperty('App::PropertyFloat', 'CutPatternAngle', 'Path', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Yaw angle for certain clearing patterns'))
        obj.addProperty('App::PropertyBool', 'IgnoreInternalFeatures', 'Path', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Ignore internal feature areas within a larger selected face.'))
        obj.addProperty('App::PropertyDistance', 'PathLineAdjustment', 'Path', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Adjust the length of the path scan-line ends, trimming or extending.'))
        obj.addProperty('App::PropertyEnumeration', 'RotationAxis', 'Rotational', QtCore.QT_TRANSLATE_NOOP('App::Property', 'The model will be rotated around this axis.'))
        obj.addProperty('App::PropertyFloat', 'StartIndex', 'Rotational', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Start index(angle) for rotational scan'))
        obj.addProperty('App::PropertyFloat', 'StopIndex', 'Rotational', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Stop index(angle) for rotational scan'))
        obj.addProperty('App::PropertyFloat', 'CutterTilt', 'Rotational', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Stop index(angle) for rotational scan'))
        obj.addProperty('App::PropertyDistance', 'DepthOffset', 'Surface', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Z-axis offset from the surface of the object'))
        obj.addProperty('App::PropertyEnumeration', 'HandleMultipleFeatures', 'Path', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Choose how to process multiple Base Geometry features.'))
        obj.addProperty('App::PropertyBool', 'OptimizeLinearPaths', 'Surface', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Enable optimization of linear paths (co-linear points). Removes unnecessary co-linear points from G-Code output.'))
        obj.addProperty('App::PropertyDistance', 'SampleInterval', 'Surface', QtCore.QT_TRANSLATE_NOOP('App::Property', 'The Sample Interval. Small values cause long wait times'))
        obj.addProperty('App::PropertyBool', 'FinishPassOnly', 'Surface', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Only perform the finish pass: profile and final depth areas.'))
        obj.addProperty('App::PropertyPercent', 'StepOver', 'Surface', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Step over percentage of the drop cutter path'))
        obj.addProperty('App::PropertyBool', 'OptimizeLinearTransitions', 'Surface', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Enable separate, more complex optimization of paths'))
        obj.addProperty('App::PropertyBool', 'IgnoreWaste', 'Waste', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Ignore areas that proceed below specified depth.'))
        obj.addProperty('App::PropertyFloat', 'IgnoreWasteDepth', 'Waste', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Depth used to identify waste areas to ignore.'))
        obj.addProperty('App::PropertyBool', 'ReleaseFromWaste', 'Waste', QtCore.QT_TRANSLATE_NOOP('App::Property', 'Cut through waste to depth at model edge, releasing the model.'))

        obj.CutMode = ['Conventional', 'Climb']
        obj.BoundBox = ['BaseBoundBox', 'Stock']
        obj.DropCutterDir = ['X', 'Y']
        obj.Algorithm = ['OCL Dropcutter', 'OCL Waterline']
        obj.LayerMode = ['Single-pass', 'Multi-pass']
        obj.ScanType = ['Planar', 'Rotational']
        obj.RotationAxis = ['X', 'Y']
        obj.CutPattern = ['Line', 'ZigZag']  # Additional goals ['Offset', 'Spiral', 'ZigZagOffset', 'Grid', 'Triangle']
        obj.HandleMultipleFeatures = ['Collectively', 'Individually']

        if not hasattr(obj, 'DoNotSetDefaultValues'):
            self.setEditorProperties(obj)

    def setEditorProperties(self, obj):
        # Used to hide inputs in properties list
        if obj.Algorithm == 'OCL Dropcutter':
            obj.setEditorMode('DropCutterDir', 0)
            # obj.setEditorMode('DropCutterExtraOffset', 0)
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

        # Disable IgnoreWaste feature
        obj.setEditorMode('IgnoreWaste', 2)
        obj.setEditorMode('IgnoreWasteDepth', 2)
        obj.setEditorMode('ReleaseFromWaste', 2)

    def onChanged(self, obj, prop):
        if prop == "Algorithm":
            self.setEditorProperties(obj)

    def opOnDocumentRestored(self, obj):
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

        # Instantiate additional class operation variables
        self.resetOpVariables()
        self.deleteTempsFlag = True

        # Disable(ignore) ReleaseFromWaste option(input)
        obj.ReleaseFromWaste = False

        # mark beginning of operation
        self.startTime = time.time()

        # Set cutter for OCL based on tool controller properties
        self.setOclCutter(obj)

        # self.reportThis('Script version: ' + __scriptVersion__ + '  Lm: ' + __lastModified__)

        # Impose property limits
        self.opApplyPropertyLimits(obj)

        output = ''
        if obj.Comment != '':
            output += '(' + str(obj.Comment) + ')\n'

        output += '(' + obj.Label + ')'
        output += '(Compensated Tool Path. Diameter: ' + str(obj.ToolController.Tool.Diameter) + ')'

        parentJob = PathUtils.findParentJob(obj)
        if parentJob is None:
            self.reportThis("No parentJob")
            return
        self.SafeHeightOffset = parentJob.SetupSheet.SafeHeightOffset.Value
        self.ClearHeightOffset = parentJob.SetupSheet.ClearanceHeightOffset.Value

        # Import OpFinalDepth from pre-existing operation for recompute() scenarios
        if obj.OpFinalDepth.Value != self.initOpFinalDepth:
            if obj.OpFinalDepth.Value == obj.FinalDepth.Value:
                obj.FinalDepth.Value = self.initOpFinalDepth
                obj.OpFinalDepth.Value = self.initOpFinalDepth
            if self.initOpFinalDepth is not None:
                obj.OpFinalDepth.Value = self.initOpFinalDepth

        if obj.Base:  # The user has selected subobjects from the base.  Pre-Process each.
            FACES = list()
            oneBase = [obj.Base[0][0], True]
            sub0 = getattr(obj.Base[0][0].Shape, obj.Base[0][1][0])
            maxHeight = sub0.BoundBox.ZMin
            for (base, subsList) in obj.Base:
                for sub in subsList:
                    shape = getattr(base.Shape, sub)
                    if isinstance(shape, Part.Face):
                        if oneBase[0] is not base:
                            # Cancel op: Only one model base allowed in the operation
                            oneBase[1] = False
                            for txt in self.opReport:
                                print(txt)
                            # self.deleteOpVariables(all=False)
                            # self.resetOpVariables()
                            PathLog.error(translate('PathSurface', '3D Surface cancelled. Only one base model permitted in the operation.'))
                            return False
                        FACES.append(shape)
                        if shape.BoundBox.ZMax > maxHeight:
                            maxHeight = shape.BoundBox.ZMax

        if obj.Base:  # The user has selected subobjects from the base.  Process each.
            if len(FACES) > 0:
                if obj.OptimizeLinearTransitions is True and len(FACES) > 1:
                    PathLog.warning(translate('PathSurface', "Multiple faces selected. \nWARNING: The `OptimizeLinearTransitions` algorithm might produce incorrect transitional paths between face regions. \nSeparate out faces to fix problem."))
                depthparams = PathUtils.depth_params(obj.ClearanceHeight.Value, obj.SafeHeight.Value, obj.StartDepth.Value*2, obj.StepDown.Value, 0.0, obj.FinalDepth.Value)
                # Process faces Collectively or Individually
                if obj.HandleMultipleFeatures == 'Collectively':
                    allEnvs = list()
                    for fc in FACES:
                        faceEnv = PathUtils.getEnvelope(fc, depthparams=depthparams)
                        if obj.IgnoreInternalFeatures is True:
                            # Identify all internal holes in each face
                            if len(fc.Wires) > 1:
                                for wire in fc.Wires[1:]:
                                    wireFaceShape = Part.Face(Part.Wire(Part.__sortEdges__(wire.Edges)))
                                    # Check for vertical planar face and ignore it 
                                    if isPlanar(wireFaceShape):
                                        if isHorizontal(wireFaceShape.Surface.Axis) is False:
                                            wireFaceEnv = PathUtils.getEnvelope(wireFaceShape, depthparams=depthparams)
                                            faceEnv = faceEnv.cut(wireFaceEnv)
                                    else:
                                        wireFaceEnv = PathUtils.getEnvelope(wireFaceShape, depthparams=depthparams)
                                        faceEnv = faceEnv.cut(wireFaceEnv)
                        allEnvs.append(faceEnv)
                    ENVS = Part.makeCompound(allEnvs)
                    final = self.opProcessBase(obj, base, ENVS)
                    self.commandlist.extend(final)
                elif obj.HandleMultipleFeatures == 'Individually':
                    for fc in FACES:
                        self.deleteOpVariables(all=False)
                        self.resetOpVariables(all=False)
                        self.faceZMax = fc.BoundBox.ZMax
                        if obj.IgnoreInternalFeatures is True:
                            allEnvs = list()
                            faceEnv = PathUtils.getEnvelope(fc, depthparams=depthparams)
                            # Identify all internal holes in each face
                            if len(fc.Wires) > 1:
                                for wire in fc.Wires[1:]:
                                    wireFaceShape = Part.Face(Part.Wire(Part.__sortEdges__(wire.Edges)))
                                    # Check for vertical planar face and ignore it 
                                    if isPlanar(wireFaceShape):
                                        if isHorizontal(wireFaceShape.Surface.Axis) is False:
                                            wireFaceEnv = PathUtils.getEnvelope(wireFaceShape, depthparams=depthparams)
                                            faceEnv = faceEnv.cut(wireFaceEnv)
                                            allEnvs.append(faceEnv)
                                    else:
                                        wireFaceEnv = PathUtils.getEnvelope(wireFaceShape, depthparams=depthparams)
                                        faceEnv = faceEnv.cut(wireFaceEnv)
                                        allEnvs.append(faceEnv)
                            else:
                                allEnvs.append(faceEnv)
                            ENVS = Part.makeCompound(allEnvs)
                            final = self.opProcessBase(obj, base, ENVS)
                            allEnvs = None
                        else:
                            faceEnv = PathUtils.getEnvelope(fc, depthparams=depthparams)
                            ENVS = Part.makeCompound([faceEnv])
                            final = self.opProcessBase(obj, base, faceEnv)
                        self.commandlist.extend(final)
                        ENVS = None
                    final = None
            else:
                PathLog.error(translate('PathSurface', 'No selected faces to surface.'))
        else:
            # Cycle through parts of model
            for base in self.model:
                self.reportThis("BASE object: " + str(base.Name))

                final = self.opProcessBase(obj, base)

                # Send final list of commands to operation object
                self.commandlist.extend(final)
            # Efor

        self.endTime = time.time()
        self.reportThis("OPERATION time: " + str(self.endTime - self.startTime) + " sec.")

        # Delete temporary objects
        for n in self.deleteList:
            FreeCAD.ActiveDocument.removeObject(n)

        for txt in self.opReport:
            print(txt)
        self.resetOpVariables()
        self.deleteOpVariables()

    def opSetDefaultValues(self, obj, job):
        '''opSetDefaultValues(obj, job) ... initialize defaults'''
        obj.StepOver = 100
        obj.OptimizeLinearPaths = True
        obj.IgnoreWaste = False
        obj.ReleaseFromWaste = False
        obj.IgnoreInternalFeatures = True
        obj.OptimizeLinearTransitions = False
        obj.FinishPassOnly = False
        obj.LayerMode = 'Single-pass'
        obj.ScanType = 'Planar'
        obj.RotationAxis = 'X'
        obj.CutMode = 'Conventional'
        obj.CutPattern = 'Line'
        obj.HandleMultipleFeatures = 'Collectively'
        obj.CutPatternAngle = 0.0
        obj.CutterTilt = 0.0
        obj.StartIndex = 0.0
        obj.StopIndex = 360.0
        obj.SampleInterval.Value = 1.0
        obj.PathLineAdjustment.Value = 0.0  # -1 * obj.ToolController.Tool.Diameter * 0.5

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

    def getCrossSectionOfEnvelope(shape, ZHeight):
        wires=list()

        for i in shape.slice(Base.Vector(0,0,1),30):
            wires.append(i)

        comp=Part.Compound(wires)
        slice=FreeCAD.ActiveDocument.addObject("Part::Feature","CrossSection")
        slice.Shape=comp
        slice.purgeTouched()

    def opProcessBase(self, obj, base, compoundFaces=None):
        initIdx = 0.0
        parentJob = PathUtils.findParentJob(obj)

        # Rotate model to initial index
        if obj.ScanType == 'Rotational':
            initIdx = obj.CutterTilt + obj.StartIndex
            if initIdx != 0.0:
                self.basePlacement = FreeCAD.ActiveDocument.getObject(base.Name).Placement
                if obj.RotationAxis == 'X':
                    # FreeCAD.ActiveDocument.getObject(base.Name).Placement = FreeCAD.Placement(FreeCAD.Vector(0,0,0),FreeCAD.Rotation(FreeCAD.Vector(1,0,0), initIdx))
                    base.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), initIdx))
                else:
                    # FreeCAD.ActiveDocument.getObject(base.Name).Placement = FreeCAD.Placement(FreeCAD.Vector(0,0,0),FreeCAD.Rotation(FreeCAD.Vector(0,1,0), initIdx))
                    base.Placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, 0), FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), initIdx))

        if base.TypeId.startswith('Mesh'):
            mesh = base.Mesh
        else:
            # try/except is for Path Jobs created before GeometryTolerance
            try:
                deflection = parentJob.GeometryTolerance
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
            bb = parentJob.Stock.Shape.BoundBox

        # Compute number and size of stepdowns, and final depth
        depthparams = PathUtils.depth_params(obj.ClearanceHeight.Value, obj.SafeHeight.Value, obj.StartDepth.Value, obj.StepDown.Value, 0.0, obj.FinalDepth.Value)

        # Create envelope for stock boundary
        if obj.BoundBox == 'BaseBoundBox':
            bbperim = Part.makeBox(bb.XLength, bb.YLength, 1, FreeCAD.Vector(bb.XMin, bb.YMin, bb.ZMin), FreeCAD.Vector(0, 0, 1))
            env = PathUtils.getEnvelope(partshape=bbperim, depthparams=depthparams)
        elif obj.BoundBox == 'Stock':
            stock = PathUtils.findParentJob(obj).Stock.Shape
            env = stock

        # Objective is to remove material from surface in StepDown layers rather than one pass to FinalDepth
        final = list()
        if obj.Algorithm == 'OCL Waterline':
            self.reportThis("--CutMode: " + str(obj.CutMode))
            if self.stl is None:
                self.stl = ocl.STLSurf()
                for f in mesh.Facets:
                    p = f.Points[0]
                    q = f.Points[1]
                    r = f.Points[2]
                    t = ocl.Triangle(ocl.Point(p[0], p[1], p[2] + obj.DepthOffset.Value),
                                    ocl.Point(q[0], q[1], q[2] + obj.DepthOffset.Value),
                                    ocl.Point(r[0], r[1], r[2] + obj.DepthOffset.Value))
                    self.stl.addTriangle(t)
            final = self._waterlineOp(obj, self.stl, bb)
        elif obj.Algorithm == 'OCL Dropcutter':
            # Rotate model back to original index
            if obj.ScanType == 'Rotational':
                if initIdx != 0.0:
                    initIdx = 0.0
                    base.Placement = self.basePlacement

            # Create stl object via OCL
            if self.stl is None:
                self.stl = ocl.STLSurf()
                for f in mesh.Facets:
                    p = f.Points[0]
                    q = f.Points[1]
                    r = f.Points[2]
                    t = ocl.Triangle(ocl.Point(p[0], p[1], p[2]),
                                    ocl.Point(q[0], q[1], q[2]),
                                    ocl.Point(r[0], r[1], r[2]))
                    self.stl.addTriangle(t)

            # Prepare global holdpoint container
            if self.holdPoint is None:
                self.holdPoint = ocl.Point(float("inf"), float("inf"), float("inf"))
            if self.layerEndPnt is None:
                self.layerEndPnt = ocl.Point(float("inf"), float("inf"), float("inf"))

            if obj.ScanType == 'Planar':
                if obj.LayerMode == 'Single-pass':
                    final = self._planarDropCutSingle(obj, self.stl, bb, base, compoundFaces)
                elif obj.LayerMode == 'Multi-pass':
                    final = self._planarDropCutMulti(obj, self.stl, bb, base, compoundFaces)
            elif obj.ScanType == 'Rotational':
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
                self.clearHeight = self.bbRadius + parentJob.SetupSheet.ClearanceHeightOffset.Value
                self.safeHeight = self.bbRadius + parentJob.SetupSheet.ClearanceHeightOffset.Value

                final = self._rotationalDropCutterOp(obj, self.stl, bb)
        # End IF
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
        if obj.SampleInterval.Value > 25.4:
            obj.SampleInterval.Value = 25.4

        # Limit cut pattern angle
        if obj.CutPattern == 'Zigzag':
            if obj.CutPatternAngle < 0.0:
                obj.CutPatternAngle = 0.0
            if obj.CutPatternAngle > 180.0:
                obj.CutPatternAngle = 180.0

        # Limit StepOver to natural number percentage
        if obj.Algorithm == 'OCL Dropcutter':
            if obj.StepOver > 100:
                obj.StepOver = 100
            if obj.StepOver < 1:
                obj.StepOver = 1
            self.cutOut = (self.cutter.getDiameter() * (float(obj.StepOver) / 100.0))

    # Main planar scan functions
    def _planarDropCutSingle(self, obj, stl, bb, base, compoundFaces=None):
        GCODE = [Path.Command('G0', {'Z': obj.ClearanceHeight.Value, 'F': self.vertRapid})]

        # Compute number and size of stepdowns, and final depth
        depthparams = [obj.FinalDepth.Value]
        lenDP = len(depthparams)
        prevDepth = depthparams[0]

        # Scan the piece to depth
        pdc = self._planarGetPDC(stl, depthparams[lenDP - 1], obj.SampleInterval.Value)
        SCANS = self._planarGetLineScans(obj, pdc, base, compoundFaces)
        lenScans = len(SCANS)

        # Determine min and max Z heights for each line in SCANS
        MAXS = []
        for LN in SCANS:
            lMax = LN[0].z
            for pt in LN:
                if pt.z > lMax:
                    lMax = pt.z
            MAXS.append(lMax)

        # Apply depth offset
        if obj.DepthOffset.Value != 0.0:
            self._planarApplyDepthOffset(SCANS, obj.DepthOffset.Value)

        # Process each layer in depthparams
        for lyr in range(0, lenDP):
            cmdFlag = False
            GCODE.append(Path.Command('N (Beginning of layer ' + str(lyr) + ')', {}))
            # Cycle through each line in the scan
            for ln in range(0, lenScans):
                LN = SCANS[ln]
                numPts = len(LN)
                lyrDep = depthparams[lyr]
                lastPnt = LN[numPts - 1]
                #if ln > 0:
                #    # Which endpoint of current line is closer, if needed reverse current line list
                #    self._planarCheckNextLine(SCANS, ln)
                lMax = MAXS[ln]

                if obj.CutPattern == 'Line':
                    # Convert line data to gcode
                    cmds = self._planarSinglepassProcess(obj, lyr, prevDepth, lyrDep, LN, ln, lMax)
                    if len(cmds) > 0:
                        cmds.insert(0, Path.Command('G0', {'X': LN[0].x, 'Y': LN[0].y, 'F': self.horizRapid}) )
                        # cmds.insert(0, Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}) )
                        if obj.HandleMultipleFeatures == 'Collectively':
                            # Go to clearance height between collective faces/regions
                            cmds.append(Path.Command('N (Go to safe height)', {}))
                            cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                            # Determine transitional clear(safe) travel height between two points
                            # transHght = self._planarDetermMinlTransHeight(pdc, LN[numPts - 1], SCANS[ln + 1][0]) + 2.0
                            # cmds.append(Path.Command('N (Transition clearance height)', {}))
                            # cmds.append(Path.Command('G0', {'Z': transHght, 'F': self.vertRapid}))
                elif obj.CutPattern == 'ZigZag':
                    # Convert line data to gcode
                    cmds = self._planarSinglepassProcess(obj, lyr, prevDepth, lyrDep, LN, ln, lMax)
                    if len(cmds) > 0:
                        if ln == 0:
                            cmds.insert(0, Path.Command('G0', {'X': LN[0].x, 'Y': LN[0].y, 'F': self.horizRapid}) )
                        if obj.HandleMultipleFeatures == 'Collectively':
                            # Go to clearance height between collective faces/regions
                            # cmds.append(Path.Command('N (Go to safe height)', {}))
                            # cmds.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
                            pass

                # append layer commands to operation command list
                if len(cmds) > 0:
                    cmdFlag = True
                    GCODE.append(Path.Command('N (Line ' + str(ln) + ')', {}))
                    GCODE.extend(cmds)
                # Eif
            # Efor
            # Set previous depth
            prevDepth = depthparams[lyr]
            if cmdFlag is True:
                GCODE.append(Path.Command('N (End of layer ' + str(lyr) + ')', {}))
            else:
                GCODE.pop()  # Remove beginning layer gcode comment
        # Efor
        return GCODE

    def _planarDropCutMulti(self, obj, stl, bb, base, compoundFaces=None):
        GCODE = [Path.Command('G0', {'Z': obj.ClearanceHeight.Value, 'F': self.vertRapid})]

        # Compute number and size of stepdowns, and final depth
        dep_par = PathUtils.depth_params(obj.ClearanceHeight.Value, obj.SafeHeight.Value, obj.StartDepth.Value, obj.SampleInterval.Value, 0.0, obj.FinalDepth.Value)
        depthparams = [i for i in dep_par]
        lenDP = len(depthparams)
        lastLyr = depthparams[lenDP - 1]
        # prevDepth = depthparams[0]
        prevDepth = bb.ZMax + 0.5

        # Scan the piece to depth
        pdc = self._planarGetPDC(stl, depthparams[lenDP - 1], obj.SampleInterval.Value)
        SCANS = self._planarGetLineScans(obj, pdc, base, compoundFaces)
        lenScans = len(SCANS)
        lastScanIdx = lenScans - 1

        # Apply depth offset
        if obj.DepthOffset.Value != 0.0:
            self._planarApplyDepthOffset(SCANS, obj.DepthOffset.Value)

        #if obj.FinishPassOnly is True:
        #    pass

        # Process each layer in depthparams
        for lyr in range(0, lenDP):
            cmdFlag = False
            lyrMax = None
            LINES = list()
            prevFirst = None
            prevLast = None
            lyrDep = depthparams[lyr]
            GCODE.append(Path.Command('N (Beginning of layer ' + str(lyr) + ')', {}))

            # Cycle through each line in the scan, pre-processing each
            cnt = 0
            for ln in range(0, lenScans):
                LN = SCANS[ln]
                # Pre-process scan for layer depth and holds
                (PNTS, lMax) = self._planarMultipassPreProcess(obj, LN, prevDepth, lyrDep, lastLayer)
                lenPNTS = len(PNTS)

                if lenPNTS > 0:
                    first = PNTS[0]
                    last = PNTS[lenPNTS - 1]
                    if cnt == 0:
                        lyrMax = lMax
                    else:
                        if lMax > lyrMax:
                            lyrMax = lMax
                    cnt += 1
                    LINES.append((PNTS, first, last, lMax))
            # Efor

            if obj.FinishPassOnly is True:
                if lyr == lastLyr:
                    #PNTS = self._planarConvertLayerToProfile()
                    pass

            # Cycle through each pre-processed lines
            lenLINES = len(LINES)
            for ln in range(0, lenLINES):
                (PNTS, first, last, lMax) = LINES[ln]
                numPts = len(PNTS)
                cmds = [Path.Command('N (Line ' + str(ln) + ')', {})]
                if ln == 0:
                    prevFirst = first
                    prevLast = last
                if obj.CutPattern == 'Line':
                    cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))
                elif obj.CutPattern == 'ZigZag':
                    if ln == 0:
                        cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}))

                # PathLog.info(f'Multi-pass layer: {lyr} @ {lyrDep};  Line count: {ln}')
                #if ln > 0:
                #    # Which endpoint of current line is closer, if needed reverse current line list
                #    self._planarCheckNextLine(SCANS, ln)

                # Generate gcode
                cmds.extend(self._planarMultipassProcess(obj, PNTS, lyr, ln, lMax))

                clrLine = prevDepth + 2.0
                if lMax > clrLine:
                    clrLine = lMax + 2.0

                if obj.CutPattern == 'Line':
                    if obj.OptimizeLinearTransitions is False:
                        clrLine = obj.SafeHeight.Value
                    #cmds.append(Path.Command('N (Go to layer max cleared height)', {}))
                    cmds.append(Path.Command('G0', {'Z': clrLine, 'F': self.vertRapid}))
                    # Return to start point of line
                    cmds.append(Path.Command('G0', {'X': first.x, 'Y': first.y, 'F': self.horizRapid}) )
                    if obj.OptimizeLinearTransitions is True:
                        nxtIdx = ln + 1
                        if nxtIdx < lenLINES:
                            (nPNTS, nfirst, nlast, nlMax) = LINES[nxtIdx]
                            mTH = self._planarDetermMinlTransHeight(pdc, first, nfirst) + 2.0
                            if mTH > clrLine:
                                cmds.append(Path.Command('G0', {'Z': mTH, 'F': self.vertRapid}))
                    # Eif
                elif obj.CutPattern == 'ZigZag':
                    pass

                # append layer commands to operation command list
                GCODE.extend(cmds)
                # Rotate points
                prevFirst = first
                prevLast = last
            # Efor

            # Set previous depth
            prevDepth = depthparams[lyr]
            # GCODE.append(Path.Command('N (Go to safe height)', {}))
            GCODE.append(Path.Command('G0', {'Z': obj.SafeHeight.Value, 'F': self.vertRapid}))
            GCODE.append(Path.Command('N (End of layer ' + str(lyr) + ')', {}))
        # Efor
        return GCODE

    def _planarSinglepassProcess(self, obj, lyr, prvDep, layDep, CLP, lnCnt, lMax):
        output = []
        optimize = obj.OptimizeLinearPaths
        lenCLP = len(CLP)
        lastCLP = len(CLP) - 1
        prcs = True
        HOLDPNTS = []
        onHold = False

        # if obj.HandleMultipleFeatures == 'Individually':
        #    self.faceZMax = fc.BoundBox.ZMax

        # Create containers for x,y,z points
        prev = ocl.Point(float("inf"), float("inf"), float("inf"))
        nxt = ocl.Point(float("inf"), float("inf"), float("inf"))
        pnt = ocl.Point(float("inf"), float("inf"), float("inf"))
        # frstPnt = ocl.Point(float("inf"), float("inf"), float("inf"))

        # Set values for first gcode point in layer
        pnt.x = CLP[0].x
        pnt.y = CLP[0].y
        pnt.z = CLP[0].z
        
        # Save beginning point
        #frstPnt.x = pnt.x
        #frstPnt.y = pnt.y
        #frstPnt.z = pnt.z
        frstPnt = pnt

        # Set initial previous point data
        prev.x = pnt.x - 4.6
        prev.y = pnt.y + 25.2
        prev.z = pnt.z

        # Begin processing ocl points list into gcode
        for i in range(0, lenCLP):
            # Calculate next point for consideration with current point
            if i < lastCLP:
                nxt.x = CLP[i + 1].x
                nxt.y = CLP[i + 1].y
                nxt.z = CLP[i + 1].z
            else:
                optimize = False

            # Process point
            if optimize is True:
                iPOL = self.isPointOnLine(FreeCAD.Vector(prev.x, prev.y, prev.z), FreeCAD.Vector(nxt.x, nxt.y, nxt.z), FreeCAD.Vector(pnt.x, pnt.y, pnt.z))
                if iPOL is False:
                    output.append(Path.Command('G1', {'X': pnt.x, 'Y': pnt.y, 'Z': pnt.z, 'F': self.horizFeed}))
            else:
                output.append(Path.Command('G1', {'X': pnt.x, 'Y': pnt.y, 'Z': pnt.z, 'F': self.horizFeed}))

            # Rotate point data
            prev.x = pnt.x
            prev.y = pnt.y
            prev.z = pnt.z
            pnt.x = nxt.x
            pnt.y = nxt.y
            pnt.z = nxt.z
        # Efor

        return output

    def _planarMultipassPreProcess(self, obj, LN, prvDep, layDep):
        ALL = list()
        PTS = list()
        optLinTrans = obj.OptimizeLinearTransitions
        safe = obj.SafeHeight.Value

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

        return (PTS, lMax)

    def _planarMultipassProcess(self, obj, PNTS, lyr, lnCnt, lMax):
        output = list()
        optimize = obj.OptimizeLinearPaths
        safe = obj.SafeHeight.Value
        lenPNTS = len(PNTS)
        lastPNTS = lenPNTS - 1
        prcs = True
        HOLDPNTS = []
        onHold = False
        delLstCmd = False
        clrScnLn = lMax + 2.0

        # if obj.HandleMultipleFeatures == 'Individually':
        #    self.faceZMax = fc.BoundBox.ZMax

        # Set values for first gcode point in layer
        pnt = PNTS[0]
        frstPnt = pnt
        prev = FreeCAD.Vector(-483543.6, 2548536.2, 999999999.4321)
        nxt = FreeCAD.Vector(0, 0, 0)

        # Add additional point at end
        lstPnt = PNTS[lastPNTS]
        if lstPnt == 'HP':
            delLstCmd = True
        PNTS.append(FreeCAD.Vector(-945.24, 573.826, 9994673))

        # Begin processing ocl points list into gcode
        for i in range(0, lenPNTS):
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
                        iPOL = self.isPointOnLine(FreeCAD.Vector(prev.x, prev.y, prev.z), FreeCAD.Vector(nxt.x, nxt.y, nxt.z), FreeCAD.Vector(pnt.x, pnt.y, pnt.z))
                        if iPOL is False:
                            output.append(Path.Command('G1', {'X': pnt.x, 'Y': pnt.y, 'Z': pnt.z, 'F': self.horizFeed}))
                else:
                    output.append(Path.Command('G1', {'X': pnt.x, 'Y': pnt.y, 'Z': pnt.z, 'F': self.horizFeed}))

            # Rotate point data
            prev = pnt
            pnt = nxt
        # Efor

        if delLstCmd is True:
            trash = output.pop()

        return output

    def _planarGetLineSet(self, obj, base, subShp=None):
        LINES = list()

        if obj.BoundBox == 'Stock':
            BS = PathUtils.findParentJob(obj).Stock
            bb = BS.Shape.BoundBox
        elif obj.BoundBox == 'BaseBoundBox':
            BS = base
            bb = base.Shape.BoundBox

        # Apply drop cutter extra offset and set the max and min XY area of the operation
        cdeoX = obj.DropCutterExtraOffset.x
        cdeoY = obj.DropCutterExtraOffset.y
        xmin = bb.XMin - cdeoX
        xmax = bb.XMax + cdeoX
        ymin = bb.YMin - cdeoY
        ymax = bb.YMax + cdeoY
        zmin = bb.ZMin
        zmax = bb.ZMax

        deltaX = abs(xmax-xmin)
        deltaY = abs(ymax-ymin)
        deltaZ = abs(zmax-zmin)
        tmpGrpNm = 'tmpGrp3n8z'

        # Create temporary group to contain temporary objects created in this method
        FreeCAD.ActiveDocument.addObject('App::DocumentObjectGroup', tmpGrpNm)
        tmpGrpNm = FreeCAD.ActiveDocument.ActiveObject.Name
        TG = FreeCAD.ActiveDocument.getObject(tmpGrpNm)

        lineLen = math.ceil(math.sqrt(deltaX**2 + deltaY**2))
        corX = xmin + (deltaX / 2)  # CenterOfRotation X
        corY = ymin + (deltaY / 2)  # CenterOfRotation Y
        centRot = FreeCAD.Vector(corX, corY, zmax)
        startPoint = FreeCAD.Vector(corX - (lineLen / 2), corY - (lineLen / 2), zmax)

        # Get envelope shape of base object or collective faces selected
        if(deltaZ < 0.01):
            stpDwn = 0.01
        else:
            stpDwn = deltaZ / 2
        hght = 2 * deltaZ + zmin
        depPrms = PathUtils.depth_params(
            clearance_height=hght + 2,
            safe_height=hght + 1,
            start_depth=hght,
            step_down=stpDwn,
            z_finish_step=0.0,
            final_depth=zmin,
            user_depths=None)

        if subShp is None:
            # env = PathUtils.getEnvelope(partshape=BS.Shape, subshape=subShp, depthparams=depPrms)  # Produces .Shape
            env = PathUtils.getEnvelope(partshape=BS.Shape, depthparams=depPrms)  # Produces .Shape

        # convert envelope to solid object
        FreeCAD.ActiveDocument.addObject('Part::Feature', 'Env')
        envName = FreeCAD.ActiveDocument.ActiveObject.Name
        TG.addObject(FreeCAD.ActiveDocument.getObject(envName))
        if subShp is None:
            FreeCAD.ActiveDocument.ActiveObject.Shape = env
        else:
            FreeCAD.ActiveDocument.ActiveObject.Shape = subShp
        FreeCAD.ActiveDocument.getObject(envName).recompute()
        FreeCAD.ActiveDocument.ActiveObject.purgeTouched()

        # Create set of lines to intersect with cross-section face
        LineSet = []
        axisRot = FreeCAD.Vector(0.0, 0.0, 1.0)
        # set initial placement - used for each line
        pl = FreeCAD.Placement()
        pl.Rotation.Q = (0.0, 0.0, 0.0, 1.0)
        pl.Base = FreeCAD.Vector(startPoint.x, startPoint.y, zmax)
        # Calculate how many lines need to be created, and create them
        lineCnt = math.ceil(lineLen / self.cutOut) + 1
        for lc in range(0, lineCnt):
            x1 = startPoint.x + (lc * self.cutOut)
            x2 = x1
            y1 = startPoint.y
            y2 = y1 + lineLen
            line = Draft.makeWire([FreeCAD.Vector(x1, y1, zmax), FreeCAD.Vector(x2, y2, zmax)], placement=pl, closed=False, face=False, support=None)
            Draft.autogroup(line)
            lineName = FreeCAD.ActiveDocument.ActiveObject.Name
            TG.addObject(FreeCAD.ActiveDocument.getObject(lineName))
            line.recompute()
            line.purgeTouched()
            LineSet.append(line)

        # Create compound object from lineset
        FreeCAD.ActiveDocument.addObject('Part::Compound', 'Compound')
        compoundName = FreeCAD.ActiveDocument.ActiveObject.Name
        TG.addObject(FreeCAD.ActiveDocument.getObject(compoundName))
        FreeCAD.ActiveDocument.ActiveObject.Links = LineSet
        FreeCAD.ActiveDocument.getObject(compoundName).recompute()
        FreeCAD.ActiveDocument.ActiveObject.purgeTouched()

        # Rotate line set
        if obj.CutPattern == 'ZigZag':
            Draft.rotate(FreeCAD.ActiveDocument.ActiveObject, -90.0 + obj.CutPatternAngle, center=centRot, axis=axisRot, copy=False)
            FreeCAD.ActiveDocument.getObject(compoundName).purgeTouched()
        elif obj.CutPattern == 'Line':
            if obj.DropCutterDir == 'X':
                Draft.rotate(FreeCAD.ActiveDocument.ActiveObject, -90.0 + obj.CutPatternAngle, center=centRot, axis=axisRot, copy=False)
                FreeCAD.ActiveDocument.getObject(compoundName).purgeTouched()

        # Identify intersection of cross-section face and lineset
        FreeCAD.ActiveDocument.addObject('Part::MultiCommon', 'Common')
        cmnName = FreeCAD.ActiveDocument.ActiveObject.Name
        TG.addObject(FreeCAD.ActiveDocument.getObject(cmnName))
        FreeCAD.ActiveDocument.ActiveObject.Shapes = [FreeCAD.ActiveDocument.getObject(envName), FreeCAD.ActiveDocument.getObject(compoundName)]
        FreeCAD.ActiveDocument.ActiveObject.recompute()
        FreeCAD.ActiveDocument.ActiveObject.purgeTouched()

        # Extract intersection line segments for return value as list()
        LSET = FreeCAD.ActiveDocument.getObject(cmnName)
        ec = len(LSET.Shape.Edges)
        for ei in range(0, ec):
            edg = LSET.Shape.Edges[ei]
            p1 = (edg.Vertexes[0].X, edg.Vertexes[0].Y)
            p2 = (edg.Vertexes[1].X, edg.Vertexes[1].Y)
            if obj.CutPattern == 'ZigZag':
                if obj.CutMode == 'Conventional':
                    if ei % 2 == 0.0:
                        tup = (p1, p2)
                    else:
                        tup = (p2, p1)
                elif obj.CutMode == 'Climb':
                    if ei % 2 == 0.0:
                        tup = (p2, p1)
                    else:
                        tup = (p1, p2)
            elif obj.CutPattern == 'Line':
                if obj.CutMode == 'Conventional':
                    tup = (p1, p2)
                else:
                    tup = (p2, p1)
            LINES.append(tup)
        
        # Apply PathLineAdjustment value, trimming or extending the scan-line ends
        SPC_LINES = list()
        if obj.PathLineAdjustment.Value != 0:
            for ((a,b), (c,d)) in LINES:
                angle = math.atan((b - d)/(a - c))
                dist = math.sqrt((a - c)**2 + (b - d)**2)
                unitX = math.cos(angle)
                unitY = math.sin(angle)
                adjX = (obj.PathLineAdjustment.Value / 2) * unitX
                adjY = (obj.PathLineAdjustment.Value / 2) * unitY
                if obj.PathLineAdjustment.Value < 0:
                    if dist >= (-1 * obj.PathLineAdjustment.Value):
                        A = (a - adjX, b - adjY)
                        B = (c + adjX, d + adjY)
                        SPC_LINES.append((A, B))
                elif obj.PathLineAdjustment.Value > 0:
                    A = (a + adjX, b + adjY)
                    B = (c - adjX, d - adjY)
                    SPC_LINES.append((A, B))
            LINES = SPC_LINES

        # Delete temporary objects for lineset creation
        for to in TG.Group:
            FreeCAD.ActiveDocument.removeObject(to.Name)
        FreeCAD.ActiveDocument.removeObject(tmpGrpNm)

        return LINES

    def _planarApplyDepthOffset(self, SCANS, DepthOffset):
        PathLog.info('Applying DepthOffset value.')
        lenScans = len(SCANS)
        for s in range(0, lenScans):
            LN = SCANS[s]
            numPts = len(LN)
            for pt in range(0, numPts):
                SCANS[s][pt].z += DepthOffset

    def _planarDetermMinlTransHeight(self, pdc, p1, p2):
        # Determine transitional clear(safe) travel height
        # p1 = last point in current line
        # p2 = first point in next line
        transLineScan = self._planarDropCutScan(pdc, ((p1.x, p1.y), (p2.x, p2.y)))
        tMax = transLineScan[0].z
        for pt in transLineScan:
            if pt.z > tMax:
                tMax = pt.z
        return tMax

    def _planarCheckNextLine(self, SCANS, ln):
        # determine if last point in last line is closer...
        # ...to first or last point in current line, if last...
        # ...reverse order of current line list to reduce travel
        LN = SCANS[ln]
        numPts = len(LN)
        lstLN = SCANS[ln - 1]
        lstIdxLstLN = len(SCANS[ln - 1]) - 1
        P = SCANS[ln - 1][lstIdxLstLN]
        F = LN[0]
        L = LN[numPts - 1]
        dPF = math.sqrt( ((F.x - P.x)**2) + ((F.y - P.y)**2) )
        dPL = math.sqrt( ((L.x - P.x)**2) + ((L.y - P.y)**2) )
        if dPL < dPF:
            SCANS[ln].reverse()

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
        LINESET = self._planarGetLineSet(obj, base, compoundFaces)
        for p1p2Tup in LINESET:
            SCANS.append(self._planarDropCutScan(pdc, p1p2Tup))
        return SCANS

    def _planarGetLineSet(self, obj, base, subShp=None):
        LINES = list()

        if obj.BoundBox == 'Stock':
            BS = PathUtils.findParentJob(obj).Stock
            bb = BS.Shape.BoundBox
        elif obj.BoundBox == 'BaseBoundBox':
            BS = base
            bb = base.Shape.BoundBox

        # Apply drop cutter extra offset and set the max and min XY area of the operation
        cdeoX = obj.DropCutterExtraOffset.x
        cdeoY = obj.DropCutterExtraOffset.y
        xmin = bb.XMin - cdeoX
        xmax = bb.XMax + cdeoX
        ymin = bb.YMin - cdeoY
        ymax = bb.YMax + cdeoY
        zmin = bb.ZMin
        zmax = bb.ZMax

        deltaX = abs(xmax-xmin)
        deltaY = abs(ymax-ymin)
        deltaZ = abs(zmax-zmin)
        tmpGrpNm = 'tmpGrp3n8z'

        # Create temporary group to contain temporary objects created in this method
        FreeCAD.ActiveDocument.addObject('App::DocumentObjectGroup', tmpGrpNm)
        tmpGrpNm = FreeCAD.ActiveDocument.ActiveObject.Name
        TG = FreeCAD.ActiveDocument.getObject(tmpGrpNm)

        lineLen = math.ceil(math.sqrt(deltaX**2 + deltaY**2))
        corX = xmin + (deltaX / 2)  # CenterOfRotation X
        corY = ymin + (deltaY / 2)  # CenterOfRotation Y
        centRot = FreeCAD.Vector(corX, corY, zmax)
        startPoint = FreeCAD.Vector(corX - (lineLen / 2), corY - (lineLen / 2), zmax)

        # Get envelope shape of base object or collective faces selected
        if(deltaZ < 0.01):
            stpDwn = 0.01
        else:
            stpDwn = deltaZ / 2
        hght = 2 * deltaZ + zmin
        depPrms = PathUtils.depth_params(
            clearance_height=hght + 2,
            safe_height=hght + 1,
            start_depth=hght,
            step_down=stpDwn,
            z_finish_step=0.0,
            final_depth=zmin,
            user_depths=None)

        if subShp is None:
            # env = PathUtils.getEnvelope(partshape=BS.Shape, subshape=subShp, depthparams=depPrms)  # Produces .Shape
            env = PathUtils.getEnvelope(partshape=BS.Shape, depthparams=depPrms)  # Produces .Shape

        # convert envelope to solid object
        FreeCAD.ActiveDocument.addObject('Part::Feature', 'Env')
        envName = FreeCAD.ActiveDocument.ActiveObject.Name
        TG.addObject(FreeCAD.ActiveDocument.getObject(envName))
        if subShp is None:
            FreeCAD.ActiveDocument.ActiveObject.Shape = env
        else:
            FreeCAD.ActiveDocument.ActiveObject.Shape = subShp
        FreeCAD.ActiveDocument.getObject(envName).recompute()
        FreeCAD.ActiveDocument.ActiveObject.purgeTouched()

        # Create set of lines to intersect with cross-section face
        LineSet = []
        axisRot = FreeCAD.Vector(0.0, 0.0, 1.0)
        # set initial placement - used for each line
        pl = FreeCAD.Placement()
        pl.Rotation.Q = (0.0, 0.0, 0.0, 1.0)
        pl.Base = FreeCAD.Vector(startPoint.x, startPoint.y, zmax)
        # Calculate how many lines need to be created, and create them
        lineCnt = math.ceil(lineLen / self.cutOut) + 1
        for lc in range(0, lineCnt):
            x1 = startPoint.x + (lc * self.cutOut)
            x2 = x1
            y1 = startPoint.y
            y2 = y1 + lineLen
            line = Draft.makeWire([FreeCAD.Vector(x1, y1, zmax), FreeCAD.Vector(x2, y2, zmax)], placement=pl, closed=False, face=False, support=None)
            Draft.autogroup(line)
            lineName = FreeCAD.ActiveDocument.ActiveObject.Name
            TG.addObject(FreeCAD.ActiveDocument.getObject(lineName))
            line.recompute()
            line.purgeTouched()
            LineSet.append(line)

        # Create compound object from lineset
        FreeCAD.ActiveDocument.addObject('Part::Compound', 'Compound')
        compoundName = FreeCAD.ActiveDocument.ActiveObject.Name
        TG.addObject(FreeCAD.ActiveDocument.getObject(compoundName))
        FreeCAD.ActiveDocument.ActiveObject.Links = LineSet
        FreeCAD.ActiveDocument.getObject(compoundName).recompute()
        FreeCAD.ActiveDocument.ActiveObject.purgeTouched()

        # Rotate line set
        if obj.CutPattern == 'ZigZag':
            Draft.rotate(FreeCAD.ActiveDocument.ActiveObject, -90.0 + obj.CutPatternAngle, center=centRot, axis=axisRot, copy=False)
            FreeCAD.ActiveDocument.getObject(compoundName).purgeTouched()
        elif obj.CutPattern == 'Line':
            if obj.DropCutterDir == 'X':
                Draft.rotate(FreeCAD.ActiveDocument.ActiveObject, -90.0 + obj.CutPatternAngle, center=centRot, axis=axisRot, copy=False)
                FreeCAD.ActiveDocument.getObject(compoundName).purgeTouched()

        # Identify intersection of cross-section face and lineset
        FreeCAD.ActiveDocument.addObject('Part::MultiCommon', 'Common')
        cmnName = FreeCAD.ActiveDocument.ActiveObject.Name
        TG.addObject(FreeCAD.ActiveDocument.getObject(cmnName))
        FreeCAD.ActiveDocument.ActiveObject.Shapes = [FreeCAD.ActiveDocument.getObject(envName), FreeCAD.ActiveDocument.getObject(compoundName)]
        FreeCAD.ActiveDocument.ActiveObject.recompute()
        FreeCAD.ActiveDocument.ActiveObject.purgeTouched()

        # Extract intersection line segments for return value as list()
        LSET = FreeCAD.ActiveDocument.getObject(cmnName)
        ec = len(LSET.Shape.Edges)
        for ei in range(0, ec):
            edg = LSET.Shape.Edges[ei]
            p1 = (edg.Vertexes[0].X, edg.Vertexes[0].Y)
            p2 = (edg.Vertexes[1].X, edg.Vertexes[1].Y)
            if obj.CutPattern == 'ZigZag':
                if obj.CutMode == 'Conventional':
                    if ei % 2 == 0.0:
                        tup = (p1, p2)
                    else:
                        tup = (p2, p1)
                elif obj.CutMode == 'Climb':
                    if ei % 2 == 0.0:
                        tup = (p2, p1)
                    else:
                        tup = (p1, p2)
            elif obj.CutPattern == 'Line':
                if obj.CutMode == 'Conventional':
                    tup = (p1, p2)
                else:
                    tup = (p2, p1)
            LINES.append(tup)
        
        # Apply PathLineAdjustment value, trimming or extending the scan-line ends
        SPC_LINES = list()
        if obj.PathLineAdjustment.Value != 0:
            for ((a,b), (c,d)) in LINES:
                angle = math.atan((b - d)/(a - c))
                dist = math.sqrt((a - c)**2 + (b - d)**2)
                unitX = math.cos(angle)
                unitY = math.sin(angle)
                adjX = (obj.PathLineAdjustment.Value / 2) * unitX
                adjY = (obj.PathLineAdjustment.Value / 2) * unitY
                if obj.PathLineAdjustment.Value < 0:
                    if dist >= (-1 * obj.PathLineAdjustment.Value):
                        A = (a - adjX, b - adjY)
                        B = (c + adjX, d + adjY)
                        SPC_LINES.append((A, B))
                elif obj.PathLineAdjustment.Value > 0:
                    A = (a + adjX, b + adjY)
                    B = (c - adjX, d - adjY)
                    SPC_LINES.append((A, B))
            LINES = SPC_LINES

        # Delete temporary objects for lineset creation
        if self.deleteTempsFlag is True:
            for to in TG.Group:
                FreeCAD.ActiveDocument.removeObject(to.Name)
            FreeCAD.ActiveDocument.removeObject(tmpGrpNm)

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

    # Methods sourced from PathAreaOp and PathProfileBase modules
    # These methods used for creating boundary shape for faces
    # The boundary shape should be created prior to makeCompound()...
    # ... and prior to creation of lineset for union with envelope.
    def _buildPathArea(self, obj, baseobject, isHole, start, getsim):
        '''_buildPathArea(obj, baseobject, isHole, start, getsim) ... internal function.
            Original version copied from PathAreaOp.py module.  This version is modified.'''
        PathLog.track()
        area = Path.Area()
        area.setPlane(PathUtils.makeWorkplane(baseobject))
        area.add(baseobject)

        areaParams = self.areaOpAreaParams(obj, isHole) # pylint: disable=assignment-from-no-return

        heights = [i for i in self.depthparams]
        PathLog.debug('depths: {}'.format(heights))
        area.setParams(**areaParams)
        obj.AreaParams = str(area.getParams())

        PathLog.debug("Area with params: {}".format(area.getParams()))

        sections = area.makeSections(mode=0, project=self.areaOpUseProjection(obj), heights=heights)
        PathLog.debug("sections = %s" % sections)
        shapelist = [sec.getShape() for sec in sections]
        PathLog.debug("shapelist = %s" % shapelist)

        pathParams = self.areaOpPathParams(obj, isHole) # pylint: disable=assignment-from-no-return
        pathParams['shapes'] = shapelist
        pathParams['feedrate'] = self.horizFeed
        pathParams['feedrate_v'] = self.vertFeed
        pathParams['verbose'] = True
        pathParams['resume_height'] = obj.SafeHeight.Value
        pathParams['retraction'] = obj.ClearanceHeight.Value
        pathParams['return_end'] = True
        # Note that emitting preambles between moves breaks some dressups and prevents path optimization on some controllers
        pathParams['preamble'] = False

        if not self.areaOpRetractTool(obj):
            pathParams['threshold'] = 2.001 * self.radius

        if self.endVector is not None:
            pathParams['start'] = self.endVector
        elif PathOp.FeatureStartPoint & self.opFeatures(obj) and obj.UseStartPoint:
            pathParams['start'] = obj.StartPoint

        obj.PathParams = str({key: value for key, value in pathParams.items() if key != 'shapes'})
        PathLog.debug("Path with params: {}".format(obj.PathParams))

        (pp, end_vector) = Path.fromShapes(**pathParams)
        PathLog.debug('pp: {}, end vector: {}'.format(pp, end_vector))
        self.endVector = end_vector # pylint: disable=attribute-defined-outside-init

        simobj = None
        if getsim:
            areaParams['Thicken'] = True
            areaParams['ToolRadius'] = self.radius - self.radius * .005
            area.setParams(**areaParams)
            sec = area.makeSections(mode=0, project=False, heights=heights)[-1].getShape()
            simobj = sec.extrude(FreeCAD.Vector(0, 0, baseobject.BoundBox.ZMax))

        return pp, simobj

    def areaOpAreaParams(self, obj, isHole):
        '''areaOpAreaParams(obj, isHole) ... returns dictionary with area parameters.
        Do not overwrite.'''
        params = {}
        params['Fill'] = 0
        params['Coplanar'] = 0
        params['SectionCount'] = -1

        offset = 0.0
        if obj.UseComp:
            offset = self.radius + obj.OffsetExtra.Value
        if obj.Side == 'Inside':
            offset = 0 - offset
        if isHole:
            offset = 0 - offset
        params['Offset'] = offset

        jointype = ['Round', 'Square', 'Miter']
        params['JoinType'] = jointype.index(obj.JoinType)

        if obj.JoinType == 'Miter':
            params['MiterLimit'] = obj.MiterLimit

        return params

    def areaOpPathParams(self, obj, isHole):
        '''areaOpPathParams(obj, isHole) ... returns dictionary with path parameters.
        Do not overwrite.'''
        params = {}

        # Reverse the direction for holes
        if isHole:
            direction = "CW" if obj.Direction == "CCW" else "CCW"
        else:
            direction = obj.Direction

        if direction == 'CCW':
            params['orientation'] = 0
        else:
            params['orientation'] = 1
        if not obj.UseComp:
            if direction == 'CCW':
                params['orientation'] = 1
            else:
                params['orientation'] = 0

        return params

    def areaOpUseProjection(self, obj):
        '''areaOpUseProjection(obj) ... returns True'''
        return True

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
            self.reportThis("--layDep " + str(layDep))

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
            self.reportThis("--Layer " + str(lCnt) + ": " + str(len(advances)) + " OCL scans and gcode in " + str(time.time() - t_before) + " s")
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
            cutterOfst = layDep * math.sin(obj.CutterTilt * math.pi / 180.0)
            self.reportThis("CutterTilt: cutterOfst is " + str(cutterOfst))

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
        # self.reportThis("points after optimization: " + str(len(output)))
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
        # self.reportThis("points after optimization: " + str(len(output)))

        # Save layer end point for use in transitioning to next layer
        self.layerEndPnt.x = RNG[0].x
        self.layerEndPnt.y = RNG[0].y
        self.layerEndPnt.z = RNG[0].z
        self.layerEndIdx = ang
        self.layerEndzMax = zMax

        # Move cutter to final point
        # output.append(Path.Command('G1', {'X': self.layerEndPnt.x, 'Y': self.layerEndPnt.y, 'Z': self.layerEndPnt.z, axisOfRot: endang, 'F': self.axialFeed}))

        return output

    # Main waterline functions
    def _waterlineOp(self, obj, stl, bb):
        '''_waterlineOp(obj, stl, bb) ... Main waterline function to perform waterline extraction from model.'''
        t_begin = time.time()  # self.keepTime = time.time()
        commands = []

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
        self.reportThis("--OCL scan: " + str(lenSL * pntsPerLine) + " points, with " + str(numScanLines) + " lines and " + str(pntsPerLine) + " pts/line")
        self.reportThis("--Setup, OCL scan, and scan conversion to multi-dimen. list took " + str(time.time() - t_begin) + " s")

        # Extract Wl layers per depthparams
        lyr = 0
        cmds = []
        layTime = time.time()
        self.topoMap = []
        for layDep in depthparams:
            cmds = self._getWaterline(obj, scanLines, layDep, lyr, lenSL, pntsPerLine)
            commands.extend(cmds)
            lyr += 1
        self.reportThis("--All layer scans combined took " + str(time.time() - layTime) + " s")
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

        # self.reportThis("--Convert parallel data to ridges")
        for lin in range(1, lastLn):
            for pt in range(1, lastPnt):  # Ignore first and last points
                if TM[lin][pt] == 0:
                    if TM[lin][pt + 1] == 2:  # step up
                        TM[lin][pt] = 1
                    if TM[lin][pt - 1] == 2:  # step down
                        TM[lin][pt] = 1

        # self.reportThis("--Convert perpendicular data to ridges and highlight ridges")
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

        # Square corners
        # self.reportThis("--Square corners")
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
        # self.reportThis("--Remove inside corners")
        for pt in range(1, lastPnt):
            for lin in range(1, lastLn):
                if TM[lin][pt] == 1:                    # point == 1
                    if TM[lin][pt + 1] == 1:
                        if TM[lin - 1][pt + 1] == 1 or TM[lin + 1][pt + 1] == 1:
                            TM[lin][pt + 1] = insCorn
                    elif TM[lin][pt - 1] == 1:
                        if TM[lin - 1][pt - 1] == 1 or TM[lin + 1][pt - 1] == 1:
                            TM[lin][pt - 1] = insCorn

        # PathLog.debug("\n-------------")
        # for li in TM:
        #    PathLog.debug("Line: " + str(li))
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
                self.reportThis("Max search scans, " + str(maxSrchs) + " reached\nPossible incomplete waterline result!")
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
        # self.reportThis("Search count for layer " + str(lyr) + " is " + str(srchCnt) + ", with " + str(loopNum) + " loops.")
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
                self.reportThis("Loop number " + str(loopNum) + " at [" + str(nxt[0]) + ", " + str(nxt[1]) + "] pnt count exceeds, " + str(ptLmt) + ".  Stopped following loop.")
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
            # self.reportThis("_findNext: No start point found.")
            return [cl, cp, num]

        for r in range(0, 8):
            l = cl + lC[s + r]
            p = cp + pC[s + r]
            if self.topoMap[l][p] == 1:
                return [l, p, num]

        # self.reportThis("_findNext: No next pnt found")
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
        # self.reportThis("points after optimization: " + str(len(output)))

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
            dx = 0.00001
        m = (p2.y - p1.y) / dx
        b = p1.y - (m * p1.x)

        avoidTool = round(cutter * 0.75, 1)  # 1/2 diam. of cutter is theoretically safe, but 3/4 diam is used for extra clearance
        zMax = finalDepth
        lenCLP = len(CLP)
        for i in range(0, lenCLP):
            mSqrd = m**2
            if mSqrd < 0.0000001:
                mSqrd = 0.0000001
            perpDist = math.sqrt((CLP[i].y - (m * CLP[i].x) - b)**2 / (1 + 1 / (mSqrd)))
            if perpDist < avoidTool:  # if point within cutter reach on line of travel, test z height and update as needed
                if CLP[i].z > zMax:
                    zMax = CLP[i].z
        return zMax + 2.0

    def reportThis(self, txt):
        self.opReport.append(txt)
    
    def resetOpVariables(self, all=True):
        '''resetOpVariables() ... Reset class variables used for instance of operation.'''
        self.holdPoint = None
        self.layerEndPnt = None
        self.onHold = False
        self.useTiltCutter = False
        self.holdStartPnts = []
        self.holdStopPnts = []
        self.holdStopTypes = []
        self.holdZMaxVals = []
        self.holdPrevLayerVals = []
        self.SafeHeightOffset = 2.0
        self.ClearHeightOffset = 4.0
        self.layerEndIdx = 0.0
        self.layerEndzMax = 0.0
        self.resetTolerance = 0.0
        self.holdPntCnt = 0
        self.lineCNT = 0
        self.keepTime = 0.0
        self.lineScanTime = 0.0
        self.bbRadius = 0.0
        self.targetDepth = 0.0
        self.stepDeg = 0.0
        self.stepRads = 0.0
        self.axialFeed = 0.0
        self.axialRapid = 0.0
        self.FinalDepth = 0.0
        self.clearHeight = 0.0
        self.safeHeight = 0.0
        self.faceZMax = -9999999999.0
        if all is True:
            self.opReport = list()
            self.cutter = None
            self.stl = None
            self.startTime = 0.0
            self.endTime = 0.0
            self.cutOut = 0.0
            self.deleteList = []
        return True

    def deleteOpVariables(self, all=True):
        '''deleteOpVariables() ... Reset class variables used for instance of operation.'''
        del self.holdPoint
        del self.layerEndPnt
        del self.onHold
        del self.useTiltCutter
        del self.holdStartPnts
        del self.holdStopPnts
        del self.holdStopTypes
        del self.holdZMaxVals
        del self.holdPrevLayerVals
        del self.SafeHeightOffset
        del self.ClearHeightOffset
        del self.layerEndIdx
        del self.layerEndzMax
        del self.resetTolerance
        del self.holdPntCnt
        del self.lineCNT
        del self.keepTime
        del self.lineScanTime
        del self.bbRadius
        del self.targetDepth
        del self.stepDeg
        del self.stepRads
        del self.axialFeed
        del self.axialRapid
        del self.FinalDepth
        del self.clearHeight
        del self.safeHeight
        del self.faceZMax
        if all is True:
            del self.opReport
            del self.cutter
            del self.stl
            del self.startTime
            del self.endTime
            del self.cutOut
            del self.deleteList
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

        if obj.ToolController.Tool.ToolType == 'EndMill':
            # Standard End Mill
            self.cutter = ocl.CylCutter(diam_1, (CEH + lenOfst))

        elif obj.ToolController.Tool.ToolType == 'BallEndMill' and FR == 0.0:
            # Standard Ball End Mill
            # OCL -> BallCutter::BallCutter(diameter, length)
            self.cutter = ocl.BallCutter(diam_1, (diam_1 / 2 + lenOfst))
            self.useTiltCutter = True

        elif obj.ToolController.Tool.ToolType == 'BallEndMill' and FR > 0.0:
            # Bull Nose or Corner Radius cutter
            # Reference: https://www.fine-tools.com/halbstabfraeser.html
            # OCL -> BallCutter::BallCutter(diameter, length)
            self.cutter = ocl.BullCutter(diam_1, FR, (CEH + lenOfst))

        elif obj.ToolController.Tool.ToolType == 'Engraver' and FR > 0.0:
            # Bull Nose or Corner Radius cutter
            # Reference: https://www.fine-tools.com/halbstabfraeser.html
            # OCL -> ConeCutter::ConeCutter(diameter, angle, lengthOffset)
            self.cutter = ocl.ConeCutter(diam_1, (CEA / 2), lenOfst)

        elif obj.ToolController.Tool.ToolType == 'ChamferMill':
            # Bull Nose or Corner Radius cutter
            # Reference: https://www.fine-tools.com/halbstabfraeser.html
            # OCL -> ConeCutter::ConeCutter(diameter, angle, lengthOffset)
            self.cutter = ocl.ConeCutter(diam_1, (CEA / 2), lenOfst)
        else:
            # Default to standard end mill
            self.cutter = ocl.CylCutter(diam_1, (CEH + lenOfst))
            PathLog.info("Defaulting cutter to standard end mill.")

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
        return True

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

    def makePnt(self, pnt):
        p = ocl.Point(float("inf"), float("inf"), float("inf"))
        p.x = pnt.x
        p.y = pnt.y
        p.z = pnt.z
        return p



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
    setup.append('IgnoreWasteDepth')
    setup.append('IgnoreWaste')
    setup.append('ReleaseFromWaste')
    setup.append('HandleMultipleFeatures')
    setup.append('IgnoreInternalFeatures')
    setup.append('PathLineAdjustment')
    setup.append('OptimizeLinearTransitions')
    setup.append('FinishPassOnly')
    return setup


def Create(name, obj=None):
    '''Create(name) ... Creates and returns a Surface operation.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", name)
    obj.Proxy = ObjectSurface(obj, name)
    return obj
