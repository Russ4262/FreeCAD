# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2017 sliptonic <shopinthewoods@gmail.com>               *
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
import PathScripts.PathOp as PathOp
import PathScripts.PathUtils as PathUtils
import math
from PySide import QtCore

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader
Draft = LazyLoader('Draft', globals(), 'Draft')
Part = LazyLoader('Part', globals(), 'Part')
PathOpTools = LazyLoader('PathScripts.PathOpTools', globals(), 'PathScripts.PathOpTools')
DraftGeomUtils = LazyLoader('DraftGeomUtils', globals(), 'DraftGeomUtils')
PathGeom = LazyLoader('PathScripts.PathGeom', globals(), 'PathScripts.PathGeom')

if FreeCAD.GuiUp:
    import FreeCADGui

__title__ = "Base class for PathArea based operations."
__author__ = "sliptonic (Brad Collette)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Base class and properties for Path.Area based operations."
__contributors__ = "russ4262 (Russell Johnson)"


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class ObjectOp(PathOp.ObjectOp):
    '''Base class for all Path.Area based operations.
    Provides standard features including debugging properties AreaParams,
    PathParams and removalshape, all hidden.
    The main reason for existence is to implement the standard interface
    to Path.Area so subclasses only have to provide the shapes for the
    operations.'''

    def opFeatures(self, obj):
        '''opFeatures(obj) ... returns the base features supported by all Path.Area based operations.
        The standard feature list is OR'ed with the return value of areaOpFeatures().
        Do not overwrite, implement areaOpFeatures(obj) instead.'''
        return PathOp.FeatureTool | PathOp.FeatureDepths | PathOp.FeatureStepDown \
            | PathOp.FeatureHeights | PathOp.FeatureStartPoint \
            | self.areaOpFeatures(obj) | PathOp.FeatureCoolant

    def areaOpFeatures(self, obj):
        '''areaOpFeatures(obj) ... overwrite to add operation specific features.
        Can safely be overwritten by subclasses.'''
        # pylint: disable=unused-argument
        return 0

    def initOperation(self, obj):
        '''initOperation(obj) ... sets up standard Path.Area properties and calls initAreaOp().
        Do not overwrite, overwrite initAreaOp(obj) instead.'''
        PathLog.track()

        # Debugging
        obj.addProperty("App::PropertyString", "AreaParams", "Path")
        obj.setEditorMode('AreaParams', 2)  # hide
        obj.addProperty("App::PropertyString", "PathParams", "Path")
        obj.setEditorMode('PathParams', 2)  # hide
        obj.addProperty("Part::PropertyPartShape", "removalshape", "Path")
        obj.setEditorMode('removalshape', 2)  # hide

        self.initAreaOp(obj)

    def initAreaOp(self, obj):
        '''initAreaOp(obj) ... overwrite if the receiver class needs initialisation.
        Can safely be overwritten by subclasses.'''
        pass # pylint: disable=unnecessary-pass

    def areaOpShapeForDepths(self, obj, job):
        '''areaOpShapeForDepths(obj) ... returns the shape used to make an initial calculation for the depths being used.
        The default implementation returns the job's Base.Shape'''
        if job:
            if job.Stock:
                PathLog.debug("job=%s base=%s shape=%s" % (job, job.Stock, job.Stock.Shape))
                return job.Stock.Shape
            else:
                PathLog.warning(translate("PathAreaOp", "job %s has no Base.") % job.Label)
        else:
            PathLog.warning(translate("PathAreaOp", "no job for op %s found.") % obj.Label)
        return None

    def areaOpOnChanged(self, obj, prop):
        '''areaOpOnChanged(obj, porp) ... overwrite to process operation specific changes to properties.
        Can safely be overwritten by subclasses.'''
        pass # pylint: disable=unnecessary-pass

    def opOnChanged(self, obj, prop):
        '''opOnChanged(obj, prop) ... base implementation of the notification framework - do not overwrite.
        The base implementation takes a stab at determining Heights and Depths if the operations's Base
        changes.
        Do not overwrite, overwrite areaOpOnChanged(obj, prop) instead.'''
        # PathLog.track(obj.Label, prop)
        if prop in ['AreaParams', 'PathParams', 'removalshape']:
            obj.setEditorMode(prop, 2)

        if prop == 'Base' and len(obj.Base) == 1:
            (base, sub) = obj.Base[0]
            bb = base.Shape.BoundBox  # parent boundbox
            subobj = base.Shape.getElement(sub[0])
            fbb = subobj.BoundBox  # feature boundbox

            if hasattr(obj, 'Side'):
                if bb.XLength == fbb.XLength and bb.YLength == fbb.YLength:
                    obj.Side = "Outside"
                else:
                    obj.Side = "Inside"

        self.areaOpOnChanged(obj, prop)

    def opOnDocumentRestored(self, obj):
        for prop in ['AreaParams', 'PathParams', 'removalshape']:
            if hasattr(obj, prop):
                obj.setEditorMode(prop, 2)

        self.areaOpOnDocumentRestored(obj)

    def areaOpOnDocumentRestored(self, obj):
        '''areaOpOnDocumentRestored(obj) ... overwrite to fully restore receiver'''
        pass # pylint: disable=unnecessary-pass

    def opSetDefaultValues(self, obj, job):
        '''opSetDefaultValues(obj) ... base implementation, do not overwrite.
        The base implementation sets the depths and heights based on the
        areaOpShapeForDepths() return value.
        Do not overwrite, overwrite areaOpSetDefaultValues(obj, job) instead.'''
        PathLog.debug("opSetDefaultValues(%s, %s)" % (obj.Label, job.Label))

        if PathOp.FeatureDepths & self.opFeatures(obj):
            try:
                shape = self.areaOpShapeForDepths(obj, job)
            except Exception as ee: # pylint: disable=broad-except
                PathLog.error(ee)
                shape = None

            # Set initial start and final depths
            if shape is None:
                PathLog.debug("shape is None")
                startDepth = 1.0
                finalDepth = 0.0
            else:
                bb = job.Stock.Shape.BoundBox
                startDepth = bb.ZMax
                finalDepth = bb.ZMin

            # obj.StartDepth.Value = startDepth
            # obj.FinalDepth.Value = finalDepth
            obj.OpStartDepth.Value = startDepth
            obj.OpFinalDepth.Value = finalDepth

            PathLog.debug("Default OpDepths are Start: {}, and Final: {}".format(obj.OpStartDepth.Value, obj.OpFinalDepth.Value))
            PathLog.debug("Default Depths are Start: {}, and Final: {}".format(startDepth, finalDepth))

        self.areaOpSetDefaultValues(obj, job)

    def areaOpSetDefaultValues(self, obj, job):
        '''areaOpSetDefaultValues(obj, job) ... overwrite to set initial values of operation specific properties.
        Can safely be overwritten by subclasses.'''
        pass # pylint: disable=unnecessary-pass

    def _buildPathArea(self, obj, baseobject, isHole, start, getsim):
        '''_buildPathArea(obj, baseobject, isHole, start, getsim) ... internal function.'''
        # pylint: disable=unused-argument
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

    def _buildPathOpenWires(self, obj, compoundWires, isHole, start, getsim):
        '''_buildPathOpenWires(obj, compoundWires, isHole, start, getsim) ... internal function.'''
        # pylint: disable=unused-argument
        PathLog.track()

        paths = []
        end_vector = FreeCAD.Vector(0.0, 0.0, obj.ClearanceHeight.Value)
        heights = [i for i in self.depthparams]
        PathLog.debug('depths: {}'.format(heights))
        for i in range(0, len(heights)):
            # for baseShape in compoundWires:
            for hWire in compoundWires.Wires:
                # hWire = Part.Wire(Part.__sortEdges__(baseShape.Edges))
                hWire.translate(FreeCAD.Vector(0, 0, heights[i] - hWire.BoundBox.ZMin))

                pathParams = {} # pylint: disable=assignment-from-no-return
                pathParams['shapes'] = [hWire]
                pathParams['feedrate'] = self.horizFeed
                pathParams['feedrate_v'] = self.vertFeed
                pathParams['verbose'] = True
                pathParams['resume_height'] = obj.SafeHeight.Value
                pathParams['retraction'] = obj.ClearanceHeight.Value
                pathParams['return_end'] = True
                # Note that emitting preambles between moves breaks some dressups and prevents path optimization on some controllers
                pathParams['preamble'] = False

                if self.endVector is None:
                    V = hWire.Wires[0].Vertexes
                    lv = len(V) - 1
                    pathParams['start'] = FreeCAD.Vector(V[0].X, V[0].Y, V[0].Z)
                    if obj.CutMode == 'Climb':
                        pathParams['start'] = FreeCAD.Vector(V[lv].X, V[lv].Y, V[lv].Z)
                else:
                    pathParams['start'] = self.endVector

                obj.PathParams = str({key: value for key, value in pathParams.items() if key != 'shapes'})
                PathLog.debug("Path with params: {}".format(obj.PathParams))

                (pp, end_vector) = Path.fromShapes(**pathParams)
                paths.extend(pp.Commands)
                PathLog.debug('pp: {}, end vector: {}'.format(pp, end_vector))

        self.endVector = end_vector
        simobj = None

        return paths, simobj

    def opExecute(self, obj, getsim=False): # pylint: disable=arguments-differ
        '''opExecute(obj, getsim=False) ... implementation of Path.Area ops.
        determines the parameters for _buildPathArea().
        Do not overwrite, implement
            areaOpAreaParams(obj, isHole) ... op specific area param dictionary
            areaOpPathParams(obj, isHole) ... op specific path param dictionary
            areaOpShapes(obj)             ... the shape for path area to process
            areaOpUseProjection(obj)      ... return true if operation can use projection
        instead.'''
        PathLog.track()

        # Instantiate class variables for operation reference
        self.endVector = None # pylint: disable=attribute-defined-outside-init
        self.leadIn = 2.0  # pylint: disable=attribute-defined-outside-init
        startPoint = None

        # Initiate depthparams and calculate operation heights for operation
        self.depthparams = self._customDepthParams(obj, obj.StartDepth.Value, obj.FinalDepth.Value)

        # Set startPoint point
        if PathOp.FeatureStartPoint & self.opFeatures(obj) and obj.UseStartPoint:
            startPoint = obj.StartPoint

        # Get working shapes/envelopes to be converted into paths
        aOS = self.areaOpShapes(obj) # pylint: disable=assignment-from-no-return

        # Adjust tuples length received from other PathWB tools/operations
        shapes = []
        for shp in aOS:
            if len(shp) == 2:
                shapes.append((shp[0], shp[1], 'otherOp'))  # (shape/envelope, is hole boolean, sub/descriptor)
            else:
                shapes.append(shp)

        if len(shapes) > 1:
            # Sort shapes to be processed
            jobs = list()
            for s in shapes:
                if s[2] == 'OpenEdge':
                    shp = Part.makeCompound(s[0])
                else:
                    shp = s[0]
                jobs.append({
                    'x': shp.BoundBox.XMax,
                    'y': shp.BoundBox.YMax,
                    'shape': s
                })

            jobs = PathUtils.sort_jobs(jobs, ['x', 'y'])
            shapes = [j['shape'] for j in jobs]

        sims = []
        for shape, isHole, detail in shapes:
            pathCmds = list()

            if detail in ['pathPocketShape', 'pathMillFace', '3DPocket']:
                # obj, workingShape, depthParams, toolRadius, horizFeed, vertFeed, jobTolerance
                strategy = StrategyClearing(shape,
                                        obj.ClearanceHeight.Value,
                                        obj.SafeHeight.Value,
                                        obj.PatternCenterAt,
                                        obj.PatternCenterCustom,
                                        obj.CutPatternReversed,
                                        obj.CutPatternAngle,
                                        obj.CutPattern,
                                        obj.CutMode,
                                        float(obj.StepOver),
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

            elif detail == 'OpenEdge':
                if PathOp.FeatureStartPoint & self.opFeatures(obj) and obj.UseStartPoint:
                    osp = obj.StartPoint
                    self.commandlist.append(Path.Command('G0', {'X': osp.x, 'Y': osp.y, 'F': self.horizRapid}))
                try:
                    (pp, sim) = self._buildPathOpenWires(obj, shape, isHole, startPoint, getsim)
                    pathCmds = pp
                except Exception as e: # pylint: disable=broad-except
                    FreeCAD.Console.PrintError(e + "\n")
                    FreeCAD.Console.PrintError("Something unexpected happened. Check project and tool config.\n")

            else:
                try:
                    (pp, sim) = self._buildPathArea(obj, shape, isHole, startPoint, getsim)
                    pathCmds = pp.Commands
                except Exception as e: # pylint: disable=broad-except
                    FreeCAD.Console.PrintError(e + "\n")
                    FreeCAD.Console.PrintError("Something unexpected happened. Check project and tool config.\n")

            if pathCmds:
                # Save gcode commands to object command list
                self.commandlist.extend(pathCmds)
                sims.append(sim)

            if self.areaOpRetractTool(obj) and self.endVector is not None and len(self.commandlist) > 1:
                self.endVector[2] = obj.ClearanceHeight.Value
                self.commandlist.append(Path.Command('G0', {'Z': obj.ClearanceHeight.Value, 'F': self.vertRapid}))

        PathLog.debug("obj.Name: " + str(obj.Name) + "\n\n")
        return sims

    def areaOpRetractTool(self, obj):
        '''areaOpRetractTool(obj) ... return False to keep the tool at current level between shapes. Default is True.'''
        # pylint: disable=unused-argument
        return True

    def areaOpAreaParams(self, obj, isHole):
        '''areaOpAreaParams(obj, isHole) ... return operation specific area parameters in a dictionary.
        Note that the resulting parameters are stored in the property AreaParams.
        Must be overwritten by subclasses.'''
        # pylint: disable=unused-argument
        pass # pylint: disable=unnecessary-pass

    def areaOpPathParams(self, obj, isHole):
        '''areaOpPathParams(obj, isHole) ... return operation specific path parameters in a dictionary.
        Note that the resulting parameters are stored in the property PathParams.
        Must be overwritten by subclasses.'''
        # pylint: disable=unused-argument
        pass # pylint: disable=unnecessary-pass

    def areaOpShapes(self, obj):
        '''areaOpShapes(obj) ... return all shapes to be processed by Path.Area for this op.
        Must be overwritten by subclasses.'''
        # pylint: disable=unused-argument
        pass # pylint: disable=unnecessary-pass

    def areaOpUseProjection(self, obj):
        '''areaOpUseProcjection(obj) ... return True if the operation can use procjection, defaults to False.
        Can safely be overwritten by subclasses.'''
        # pylint: disable=unused-argument
        return False

    # Support methods
    def _customDepthParams(self, obj, strDep, finDep):
        finish_step = obj.FinishDepth.Value if hasattr(obj, "FinishDepth") else 0.0
        cdp = PathUtils.depth_params(
            clearance_height=obj.ClearanceHeight.Value,
            safe_height=obj.SafeHeight.Value,
            start_depth=strDep,
            step_down=obj.StepDown.Value,
            z_finish_step=finish_step,
            final_depth=finDep,
            user_depths=None)
        return cdp
# Eclass


class StrategyClearing:
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
                                float(obj.StepOver),
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
    patterns = ('Line', 'LineOffset', 'ZigZag', 'ZigZagOffset', 'Circular', 'CircularZigZag', 'Offset', 'Spiral', 'Grid', 'Triangle')
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

        # Debugging attributes
        self.isDebug = False
        self.debugObjectsGroup = None

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
        def combineAdjacentArcs(grp):
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

        e = edges[0]
        rad = e.Curve.Radius
        group = [e]

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
            if len(g) == 1:
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

    def _Link_Profile(self):
        return self.rawPathGeometry

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
        # patterns = ('Line', 'LineOffset', 'ZigZag', 'ZigZagOffset', 'Circular', 'CircularZigZag', 'Offset', 'Spiral', 'Profile')
        linkMethod = getattr(self, "_Link_" + self.cutPattern)
        self.linkedPathGeom = linkMethod()

    def _generatePathGeometry(self):
        '''_generatePathGeometry()...
        Call this function to obtain the path geometry shape, generated by this class.'''
        patternMethod = getattr(self, "_" + self.cutPattern)
        self.rawGeoList = patternMethod()

        # Create compound object to bind all geometry
        geomShape = Part.makeCompound(self.rawGeoList)
        
        # Debugging
        if self.isDebug:
            comp = Part.show(geomShape)
            FreeCAD.ActiveDocument.ActiveObject.Label = 'rawPathGeomShape'

        # Position and rotate the Line and ZigZag geometry
        if self.cutPattern in self.rotatablePatterns:
            if self.cutPatternAngle != 0.0:
                geomShape.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), self.cutPatternAngle)
            bbC = self.centerOfPattern
            geomShape.Placement.Base = FreeCAD.Vector(bbC.x, bbC.y, 0.0 - geomShape.BoundBox.ZMin)

        if self.debugObjectsGroup:
            F = FreeCAD.ActiveDocument.addObject('Part::Feature', 'tmpGeometrySet')
            F.Shape = geomShape
            F.purgeTouched()
            self.debugObjectsGroup.addObject(F)

        # Return current geometry for Offset or Profile patterns
        if self.cutPattern == 'Offset' or self.cutPattern == 'Profile':
            self.rawPathGeometry = geomShape
            self._applyPathLinking()
            return self.linkedPathGeom

        # Add profile 'Offset' path after base pattern
        addOffsetWires = False
        if self.cutPattern != 'Offset' and self.cutPattern[-6:] == 'Offset':
            addOffsetWires = True
        
        # Identify intersection of cross-section face and lineset
        self.rawPathGeometry = self.face.common(Part.makeCompound(geomShape.Wires))

        if self.debugObjectsGroup:
            F = FreeCAD.ActiveDocument.addObject('Part::Feature', 'tmpPathGeometry')
            F.Shape = self.rawPathGeometry
            F.purgeTouched()
            self.debugObjectsGroup.addObject(F)

        # Debugging
        if self.isDebug:
            __ = Part.show(self.rawPathGeometry)
            FreeCAD.ActiveDocument.ActiveObject.Label = 'rawPathGeometry'

        self._applyPathLinking()
        if addOffsetWires:
            for wire in self._getProfileWires():
                lst = [wire]
                self.linkedPathGeom.append(lst)

        return self.linkedPathGeom

    # Path generation methods
    def _buildPaths(self, height, edgeLists):
        '''_buildPaths(edgeLists) ... internal function.'''
        PathLog.track()
        # PathLog.info("_buildPaths()")

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
        PathLog.debug("Path with params: {}".format(self.pathParams))

        self.endVectors.append(end_vector)

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
    def setDebugObjectsGroup(self, isDebug=False, tmpGrpObject=None):
        '''setDebugObjectsGroup(tmpGrpObject)...
        Pass the temporary object group to show temporary construction objects'''
        self.isDebug = isDebug
        self.debugObjectsGroup = tmpGrpObject

    def execute(self, includePaths=True):
        '''execute(includePaths=True)...
        The public method for the StrategyClearing class.
        Returns a tuple containing a list of path commands and a list of shapes(wires and edges) as the path geometry.
        Set includePaths argument to False if only path geometry is desired.
        '''
        PathLog.debug("execute()")
        # patterns = ('Circular', 'CircularZigZag', 'Line', 'LineOffset', 'Offset', 'Spiral', 'ZigZag', 'ZigZagOffset', 'Profile')
        self.commandList = list()  # Reset list
        self.pathGeometry = list()  # Reset list
        self.isCenterSet = False
        depthParams = [i for i in self.depthParams]

        # Exit if pattern not available
        if self.cutPattern == 'None':
            return None

        if  self.cutPattern in ["Grid", "Triangle"]:
            self._buildGridAndTrianglePaths()
            return

        # Make box to serve as cut tool, and move into position above shape
        sBB = self.workingShape.BoundBox

        for dp in depthParams:
            cutFace = PathGeom.makeBoundBoxFace(sBB, offset=5.0, zHeight=dp)
            workingFaces = self.workingShape.common(cutFace)
            if workingFaces and workingFaces.Faces:
                for wf in workingFaces.Faces:
                    wf.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - wf.BoundBox.ZMin))
                    #  Apply simple radius shrinking offset for clearing pattern generation.
                    #  Adjust this offset with material allowance values
                    ofstVal = self.offsetDirection * (self.toolRadius - (self.jobTolerance / 5.0) + self.materialAllowance)
                    offsetWF = PathUtils.getOffsetArea(wf, ofstVal)
                    if offsetWF:
                        for f in offsetWF.Faces:
                            self.face = f
                            self._prepareConstants()
                            pathGeom = self._generatePathGeometry()
                            self.pathGeometry.extend(pathGeom)
                            if includePaths:
                                pathCmds = self._buildPaths(dp, pathGeom)
                                self.commandList.extend(pathCmds)
                    else:
                        PathLog.debug("No offset working faces at {} mm.".format(dp))
            else:
                PathLog.debug("No working faces at {} mm.".format(dp))

        endVectCnt = len(self.endVectors)
        if endVectCnt > 0:
            self.endVector = self.endVectors[endVectCnt - 1]
# Eclass


def SetupProperties():
    setup = []
    return setup
