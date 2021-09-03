# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2017 sliptonic <shopinthewoods@gmail.com>               *
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
import Path
import PathScripts.PathLog as PathLog
import PathScripts.PathOp as PathOp
import PathScripts.PathUtils as PathUtils
import PathScripts.Strategies.PathStrategyClearing as StrategyClearing
import PathScripts.PathSelectionProcessing as SelectionProcessing
import PathScripts.PathUtils as PathUtils
import Part

from PySide import QtCore


__title__ = "Path Pocket Shape Operation"
__author__ = "sliptonic (Brad Collette)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Class and implementation of shape based Pocket operation."


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())


# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class ObjectPocket(PathOp.ObjectOp):
    '''Proxy object for Pocket operation.'''

    def opFeatures(self, obj):
        '''opFeatures(obj) ... returns the base features supported by all Path.Area based operations.'''
        return PathOp.FeatureTool | PathOp.FeatureDepths | PathOp.FeatureStepDown \
            | PathOp.FeatureStartPoint | PathOp.FeatureCoolant | PathOp.FeatureBaseEdges \
            | PathOp.FeatureBaseFaces | PathOp.FeatureFinishDepth | PathOp.FeatureExtensions

    def initOperation(self, obj):
        '''initOperation(obj) ... implement to extend class `__init__()` contructor,
        like create additional properties.'''
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False

    def opPropertyDefinitions(self):
        '''opProperties() ... returns a tuples.
        Each tuple contains property declaration information in the
        form of (prototype, name, section, tooltip).'''
        props = [
            ("App::PropertyEnumeration", "CutDirection", "PathOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "The direction that the toolpath should go around the part: Climb or Conventional.")),
            ("App::PropertyDistance", "MaterialAllowance", "PathOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Extra offset to apply to the operation. Direction is operation dependent.")),
            ("App::PropertyEnumeration", "StartAt", "PathOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Start pocketing at center or boundary")),
            ("App::PropertyDistance", "StepOver", "PathOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Percent of cutter diameter to step over on each pass")),
            ("App::PropertyFloat", "CutPatternAngle", "PathOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Angle of the zigzag pattern")),
            ("App::PropertyEnumeration", "CutPattern", "PathOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Clearing pattern to use")),
            ("App::PropertyBool", "MinTravel", "PathOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Use 3D Sorting of Path")),
            ("App::PropertyBool", "KeepToolDown", "PathOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Attempts to avoid unnecessary retractions.")),
            ("App::PropertyBool", "CutPatternReversed", "PathOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Reverse the cut order of the stepover paths. For circular cut patterns, begin at the outside and work toward the center.")),
            ("App::PropertyVectorDistance", "PatternCenterCustom", "PathOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Set the start point for the cut pattern.")),
            ("App::PropertyEnumeration", "PatternCenterAt", "PathOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Choose location of the center point for starting the cut pattern.")),
            ("App::PropertyBool", "Cut3DPocket", "Operation", QtCore.QT_TRANSLATE_NOOP("App::Property", "Enable to cut a 3D pocket instead of the standard 2D pocket")),
            ("App::PropertyBool", "UseComp", "PathOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Make True, if using Cutter Radius Compensation")),
            ("App::PropertyEnumeration", "BoundaryShape", "SelectionOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Shape to use for calculating Boundary")),
            ('App::PropertyEnumeration', 'HandleMultipleFeatures', "SelectionOptions", QtCore.QT_TRANSLATE_NOOP('PathPocket', 'Choose how to process multiple Base Geometry features.')),
            ("App::PropertyBool", "ProcessPerimeter", "SelectionOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Profile the outline")),
            ("App::PropertyBool", "ProcessHoles", "SelectionOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Profile holes as well as the outline")),
            ("App::PropertyBool", "ProcessCircles", "SelectionOptions", QtCore.QT_TRANSLATE_NOOP("App::Property", "Profile round holes")),
            ("App::PropertyString", "AreaParams", "Debug", QtCore.QT_TRANSLATE_NOOP("App::Property", "Debug property that stores parameters passed to Path.Area() for this operation.")),
            ("App::PropertyString", "PathParams", "Debug", QtCore.QT_TRANSLATE_NOOP("App::Property", "Debug property that stores parameters passed to Path.fromShapes() for this operation.")),
            ("App::PropertyBool", "ShowDebugShapes", "Debug", QtCore.QT_TRANSLATE_NOOP("App::Property", "Show the temporary path construction objects when module is in DEBUG mode."))
        ]
        props.extend(StrategyClearing.StrategyAdaptive.adaptivePropertyDefinitions())
        return props

    def opPropertyEnumerations(self):
        '''opPropertyEnumerations() ... returns a dictionary of enumeration lists
        for the operation's enumeration type properties.'''
        # Enumeration lists for App::PropertyEnumeration properties
        enums = {
            'CutDirection': ['Climb', 'Conventional'],
            'StartAt': ['Center', 'Edge'],
            'CutPattern': ['Adaptive', 'Circular', 'CircularZigZag', 'Grid', 'Line', 'LineOffset', 'Offset', 'Spiral', 'Triangle', 'ZigZag', 'ZigZagOffset'],
            'BoundaryShape': ['Boundbox', 'Face Region', 'Perimeter', 'Stock'],
            'HandleMultipleFeatures': ['Collectively', 'Individually'],
            'PatternCenterAt': ['CenterOfMass', 'CenterOfBoundBox', 'XminYmin', 'Custom']
        }
        for k, v in StrategyClearing.StrategyAdaptive.adaptivePropertyEnumerations().items():
            enums[k] = v
        return enums

    def opPropertyDefaults(self, obj, job):
        '''opPropertyDefaults(obj, job) ... returns a dictionary of default values
        for the operation's properties.'''
        defaults = {
            'CutDirection': 'Conventional',
            'MaterialAllowance': 0.0,
            'StartAt': 'Center',
            'StepOver': 50.0,
            'CutPatternAngle': 0.0,
            'CutPattern': 'ZigZag',
            'UseComp': True,
            'MinTravel': False,
            'KeepToolDown': False,
            'Cut3DPocket': False,
            'CutPatternReversed': False,
            'PatternCenterCustom': FreeCAD.Vector(0.0, 0.0, 0.0),
            'PatternCenterAt': 'CenterOfBoundBox',
            'BoundaryShape': 'Face Region',
            'HandleMultipleFeatures': 'Collectively',
            'ProcessPerimeter': True,
            'ProcessHoles': True,
            'ProcessCircles': True,
            'AreaParams': '',
            'PathParams': '',
            'ShowDebugShapes': False
        }
        for k, v in StrategyClearing.StrategyAdaptive.adaptivePropertyDefaults(obj, job).items():
            defaults[k] = v
        return defaults

    def opSetDefaultValues(self, obj, job):
        '''opSetDefaultValues(obj) ... base implementation, do not overwrite.
        The base implementation sets the depths and heights based on the
        opShapeForDepths() return value.'''
        PathLog.debug("opSetDefaultValues(%s, %s)" % (obj.Label, job.Label))

        shape = None
        try:
            shape = self.opShapeForDepths(obj, job)
        except Exception as ee: # pylint: disable=broad-except
            PathLog.error(ee)

        # Set initial start and final depths
        if shape is None:
            PathLog.debug("shape is None")
            startDepth = 1.0
            finalDepth = 0.0
        else:
            bb = job.Stock.Shape.BoundBox
            startDepth = bb.ZMax
            finalDepth = bb.ZMin

        obj.OpStartDepth.Value = startDepth
        obj.OpFinalDepth.Value = finalDepth

    def opSetEditorModes(self, obj):
        '''opSetEditorModes(obj, porp) ... Process operation-specific changes to properties visibility.'''

        # Always hidden
        if PathLog.getLevel(PathLog.thisModule()) != 4:
            obj.setEditorMode('ShowDebugShapes', 2)
        # obj.setEditorMode('JoinType', 2)
        # obj.setEditorMode('MiterLimit', 2)
        hide = False if hasattr(obj, "CutPattern") and obj.CutPattern == 'Adaptive' else True
        StrategyClearing.StrategyAdaptive.adaptiveSetEditorModes(obj, hide)

    def opShapeForDepths(self, obj, job):
        '''opShapeForDepths(obj) ... returns the shape used to make an initial calculation for the depths being used.
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

    def opUpdateDepths(self, obj):
        # PathLog.info("opUpdateDepths()")
        if obj.Cut3DPocket:
            zMins = list()
            if not hasattr(obj, 'Base') or not obj.Base:
                zMins = [min([base.Shape.BoundBox.ZMin for base in self.job.Model.Group])]
            else:
                for base, subsList in obj.Base:
                    zMins.append(min([base.Shape.getElement(s).BoundBox.ZMin for s in subsList]))
            obj.OpFinalDepth.Value = min(zMins)
            # PathLog.debug("Cut 3D pocket update final depth: {} mm\n".format(obj.OpFinalDepth.Value))

    def opOnDocumentRestored(self, obj):
        '''opOnDocumentRestored(obj) ... implement if an op needs special handling.'''
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False

    def opExecute_ORIG(self, obj, getsim=False): # pylint: disable=arguments-differ
        '''opExecute(obj, getsim=False) ... implementation of Path.Area ops.
        determines the parameters for _buildPathArea().
        '''
        PathLog.track()
        self.commandlist = list()
        sims = None
        # Initiate depthparams and calculate operation heights for operation
        finish_step = obj.FinishDepth.Value if hasattr(obj, "FinishDepth") else 0.0
        self.depthparams = PathUtils.depth_params(
                                clearance_height=obj.ClearanceHeight.Value,
                                safe_height=obj.SafeHeight.Value,
                                start_depth=obj.StartDepth.Value,
                                step_down=obj.StepDown.Value,
                                z_finish_step=finish_step,
                                final_depth=obj.FinalDepth.Value,
                                user_depths=None)

        if obj.CutPattern == 'Adaptive':
            if obj.Cut3DPocket:
                self.opExecuteAdaptive3D(obj)
            else:
                self.opExecuteAdaptive(obj)
        else:
            sims = self.opExecuteArea(obj, getsim)

        # PathLog.debug("obj.Name: {}".format(obj.Name))
        if self.removalshapes:
            obj.WorkingShape = Part.makeCompound([trio[0] for trio in self.removalshapes])

        return sims

    def opExecute(self, obj, getsim=False): # pylint: disable=arguments-differ
        '''opExecute(obj, getsim=False) ... implementation of Path.Area ops.
        determines the parameters for _buildPathArea().
        '''
        PathLog.track()
        self.commandlist = list()
        sims = None
        # Initiate depthparams and calculate operation heights for operation
        finish_step = obj.FinishDepth.Value if hasattr(obj, "FinishDepth") else 0.0
        self.depthparams = PathUtils.depth_params(
                                clearance_height=obj.ClearanceHeight.Value,
                                safe_height=obj.SafeHeight.Value,
                                start_depth=obj.StartDepth.Value,
                                step_down=obj.StepDown.Value,
                                z_finish_step=finish_step,
                                final_depth=obj.FinalDepth.Value,
                                user_depths=None)

        sims = self.opExecuteArea(obj, getsim)

        # PathLog.debug("obj.Name: {}".format(obj.Name))
        if self.removalshapes:
            obj.WorkingShape = Part.makeCompound([trio[0] for trio in self.removalshapes])

        return sims

    def opExecuteArea(self, obj, getsim=False): # pylint: disable=arguments-differ
        '''opExecute(obj, getsim=False) ... Apply non-adaptive cut patterns to 2D extruded envelopes.'''
        PathLog.debug("opExecuteArea()")

        # Instantiate class variables for operation reference
        self.endVector = None # pylint: disable=attribute-defined-outside-init
        # opFeatures = self.opFeatures(obj)
        startPoint = None
        opRetractTool = not obj.KeepToolDown
        PathLog.debug("retracting tool: %d" % (opRetractTool))

        # Set start point
        if obj.UseStartPoint:
            startPoint = obj.StartPoint

        shapes = self.shapeIdentification(obj) # pylint: disable=assignment-from-no-return

        # Sort operations
        if len(shapes) > 1:
            jobs = list()
            for s in shapes:
                shp = s[0]
                jobs.append({
                    'x': shp.BoundBox.XMax,
                    'y': shp.BoundBox.YMax,
                    'shape': s
                })

            jobs = PathUtils.sort_jobs(jobs, ['x', 'y'])

            shapes = [j['shape'] for j in jobs]

        sims = []
        for shape, isHole, details in shapes:
            """
            strategy = StrategyClearing.StrategyPocket(shape, startPoint, getsim,
                                self.depthparams, self.horizFeed, self.vertFeed,
                                self.endVector, self.radius, self.opFeatures(obj),
                                obj.SafeHeight.Value, obj.ClearanceHeight.Value,
                                obj.MaterialAllowance.Value, obj.CutDirection,
                                False, opRetractTool, False,
                                obj.CutPattern, obj.CutPatternAngle, obj.StepOver.Value,
                                obj.StartAt, obj.MinTravel)
            try:
                # Generate the path commands
                strategy.execute()

                self.endVector = strategy.endVector
                # Save gcode commands to object command list
                self.commandlist.extend(strategy.commandList)
                if getsim:
                    sims.append(strategy.simObj)
                obj.AreaParams = strategy.areaParams  # save area parameters
                obj.PathParams = strategy.pathParams  # save path parameters
            except Exception as e: # pylint: disable=broad-except
                FreeCAD.Console.PrintError(e + "\n")
                FreeCAD.Console.PrintError("Something unexpected happened. Check project and tool config. 1\n")
            """

            strategy = StrategyClearing.StrategyClearVolume(shape,
                        obj.ClearanceHeight.Value,
                        obj.SafeHeight.Value,
                        obj.PatternCenterAt,
                        obj.PatternCenterCustom,
                        obj.CutPatternReversed,
                        obj.CutPatternAngle,
                        obj.CutPattern,
                        obj.CutDirection,
                        obj.StepOver.Value,
                        obj.MaterialAllowance.Value,
                        obj.MinTravel,
                        obj.KeepToolDown,
                        obj.ToolController,
                        startPoint,
                        self.depthparams,
                        self.job.GeometryTolerance.Value)
            if obj.CutPattern == "Adaptive":
                # set adaptive-dependent attributes
                strategy.setAdaptiveAttributes(obj.OperationType,
                        obj.CutSide,
                        obj.DisableHelixEntry,
                        obj.ForceInsideOut,
                        obj.LiftDistance.Value,
                        obj.FinishingProfile,
                        obj.HelixAngle.Value,
                        obj.HelixConeAngle.Value,
                        obj.UseHelixArcs,
                        obj.HelixDiameterLimit.Value,
                        obj.KeepToolDownRatio.Value,
                        obj.Tolerance,
                        self.stock)
            strategy.isDebug = self.isDebug  # Transfer debug status
            try:
                # Generate the path commands
                rtn = strategy.execute()
            except Exception as e: # pylint: disable=broad-except
                FreeCAD.Console.PrintError(str(e) + "\n")
                FreeCAD.Console.PrintError("Something unexpected happened. Check project and tool config. 1\n")

            else:
                # Transfer some values from strategy class back to operation
                if obj.PatternCenterAt != 'Custom' and strategy.centerOfPattern is not None:
                    obj.PatternCenterCustom = strategy.centerOfPattern
                self.endVector = strategy.endVector
                obj.AreaParams = strategy.areaParams  # save area parameters
                obj.PathParams = strategy.pathParams  # save path parameters
                # Save path commands to operation command list
                self.commandlist.extend(strategy.commandList)
                if getsim:
                    sims.append(strategy.simObj)

            if self.endVector is not None and len(self.commandlist) > 1:
                self.endVector[2] = obj.ClearanceHeight.Value
                self.commandlist.append(Path.Command('G0', {'Z': obj.ClearanceHeight.Value, 'F': self.vertRapid}))

        return sims

    def opExecuteAdaptive(self, obj): # pylint: disable=arguments-differ
        '''opExecuteAdaptive(obj) ... Apply adaptive cut pattern to 2D extruded envelopes.'''
        PathLog.debug("opExecuteAdaptive()")

        shapes = self.shapeIdentification(obj, isPreview=False, facesOnly=True)
        if not shapes:
            PathLog.debug("No working shapes.")
            return

        faces = [tup[0] for tup in shapes]
        for f in faces:
            f.translate(FreeCAD.Vector(0.0, 0.0, obj.FinalDepth.Value - f.BoundBox.ZMin))
        
        viewObject = None
        if hasattr(obj, "ViewObject"):
            viewObject = obj.ViewObject

        # Execute the Adaptive code to generate path data
        strategy = StrategyClearing.StrategyAdaptive(faces,
                    obj.ToolController,
                    obj.ClearanceHeight.Value,
                    obj.SafeHeight.Value,
                    obj.StartDepth.Value,
                    obj.FinishDepth.Value,
                    obj.FinalDepth.Value,
                    obj.OperationType,
                    obj.CutSide,
                    obj.ForceInsideOut,
                    obj.MaterialAllowance.Value,
                    obj.StepDown.Value,
                    obj.StepOver.Value,
                    obj.LiftDistance.Value,
                    obj.FinishingProfile,
                    obj.HelixAngle.Value,
                    obj.HelixConeAngle.Value,
                    obj.UseHelixArcs,
                    obj.HelixDiameterLimit.Value,
                    obj.KeepToolDownRatio.Value,
                    obj.Tolerance,
                    obj.Stopped,
                    obj.StopProcessing,
                    self.stock,
                    self.job,
                    obj.AdaptiveOutputState,
                    obj.AdaptiveInputState,
                    viewObject)
        strategy.isDebug = self.isDebug  # Transfer debug status
        if obj.DisableHelixEntry:
            strategy.disableHelixEntry()
        strategy.generateGeometry = False  # Set True to make geometry list available in `adaptiveGeometry` attribute
        strategy.generateCommands = True  # Set False to disable path command generation

        try:
            # Generate the path commands
            rtn = strategy.execute()
        except Exception as e: # pylint: disable=broad-except
            FreeCAD.Console.PrintError(str(e) + "\n")
            FreeCAD.Console.PrintError("Something unexpected happened. Check project and tool config. 2\n")
        else:
            # Save path commands to operation command list
            self.commandlist.extend(strategy.commandList)

    def opExecuteAdaptive3D(self, obj): # pylint: disable=arguments-differ
        '''opExecuteAdaptive3D(obj) ... Apply adaptive cut pattern to 3D shapes using slicing method.'''
        PathLog.debug("opExecuteAdaptive3D()")

        shapes = self.shapeIdentification(obj)

        # Save original depth values
        startDep = obj.StartDepth.Value
        stepDown = obj.StepDown.Value
        finDep = obj.FinalDepth.Value

        # Override step down value temporarily
        obj.StepDown.Value = obj.ClearanceHeight.Value + 1.0 - obj.FinalDepth.Value

        viewObject = None
        if hasattr(obj, "ViewObject"):
            viewObject = obj.ViewObject

        # Slice each solid at requested depth and apply Adaptive pattern to each layer
        success = False
        solids = [tup[0] for tup in shapes]
        for s in solids:
            # PathLog.debug("Adaptive solid...")
            for dep in self.depthparams:
                # Set temporary depths depth for this layer in the depth parameters
                obj.StartDepth.Value = dep + (stepDown * 1.25)  # This 1.25 factor will likely need adjustment or exposure to the user.
                obj.FinalDepth.Value = dep

                # Slice the solid at depth
                face = SelectionProcessing.getCrossSectionOfSolid(s, dep)
                if face:
                    faces = face.Faces

                    # Execute the Adaptive code to generate path data
                    strategy = StrategyClearing.StrategyAdaptive(faces,
                                obj.ToolController,
                                obj.ClearanceHeight.Value,
                                obj.SafeHeight.Value,
                                obj.StartDepth.Value,
                                obj.FinishDepth.Value,
                                obj.FinalDepth.Value,
                                obj.OperationType,
                                obj.CutSide,
                                obj.ForceInsideOut,
                                obj.MaterialAllowance.Value,
                                obj.StepDown.Value,
                                obj.StepOver.Value,
                                obj.LiftDistance.Value,
                                obj.FinishingProfile,
                                obj.HelixAngle.Value,
                                obj.HelixConeAngle.Value,
                                obj.UseHelixArcs,
                                obj.HelixDiameterLimit.Value,
                                obj.KeepToolDownRatio.Value,
                                obj.Tolerance,
                                obj.Stopped,
                                obj.StopProcessing,
                                self.stock,
                                self.job,
                                obj.AdaptiveOutputState,
                                obj.AdaptiveInputState,
                                viewObject)
                    strategy.isDebug = self.isDebug  # Transfer debug status
                    if obj.DisableHelixEntry:
                        strategy.disableHelixEntry()
                    strategy.generateGeometry = False  # Set True to make geometry list available in `adaptiveGeometry` attribute
                    strategy.generateCommands = True  # Set False to disable path command generation

                    try:
                        # Generate the path commands
                        rtn = strategy.execute()
                    except Exception as e: # pylint: disable=broad-except
                        FreeCAD.Console.PrintError(str(e) + "\n")
                        FreeCAD.Console.PrintError("Something unexpected happened. Check project and tool config. 3\n")
                    else:
                        # Save path commands to operation command list
                        self.commandlist.extend(strategy.commandList)
                        success = True

                else:
                    PathLog.debug("No cross-sectional faces at {} mm.".format(dep))
                    if success:
                        break
            # Efor
        # Efor

        # Restore depth values
        obj.StartDepth.Value = startDep
        obj.StepDown.Value = stepDown
        obj.FinalDepth.Value = finDep

    def shapeIdentification(self, obj, isPreview=False, facesOnly=False):
        '''shapeIdentification(obj) ... return shapes representing the solids to be removed.'''
        PathLog.track()
        self.removalshapes = []
        workingAreas = None
        extensions = None

        self._setMisingClassVariables(obj)
        self.isDebug = True if PathLog.getLevel(PathLog.thisModule()) == 4 else False

        if obj.Base:
            baseObjList = obj.Base
            extensions = PathOp.PathFeatureExtensions.getExtensions(obj)
        else:
            baseObjList = [(base, list()) for base in self.model]

        # Process user inputs via Base Geometry and Extensions into pocket areas
        if obj.Cut3DPocket:
            PathLog.debug("shapeIdentification() for 3D pocket")
            if isPreview:
                self.opUpdateDepths(obj)

            pac = SelectionProcessing.Working3DFaces(
                baseObjList,
                extensions,
                processPerimeter=obj.ProcessPerimeter,
                processHoles=obj.ProcessHoles,
                processCircles=obj.ProcessCircles,
                handleMultipleFeatures=obj.HandleMultipleFeatures,
                startDepth=obj.StartDepth.Value + obj.StepDown.Value,
                finalDepth=obj.FinalDepth.Value)
        else:
            PathLog.debug("shapeIdentification()")
            pac = SelectionProcessing.Working2DAreas(
                baseObjList,
                extensions,
                processPerimeter=obj.ProcessPerimeter,
                processHoles=obj.ProcessHoles,
                processCircles=obj.ProcessCircles,
                handleMultipleFeatures=obj.HandleMultipleFeatures,
                boundaryShape=obj.BoundaryShape,
                stockShape=self.job.Stock.Shape,
                finalDepth=obj.FinalDepth.Value)
        pac.isDebug = self.isDebug  #  You can force True here to set debug mode for SelectionProcessing class
        pac.showDebugShapes = obj.ShowDebugShapes  #  You can force True here to show debug shapes for SelectionProcessing class
        workingAreas = pac.getWorkingAreas(avoidOverhead=True)
        workingSolids = pac.getWorkingSolids(avoidOverhead=True)
        self.exts = pac.getExtensionFaces()

        if workingAreas:
            if facesOnly:
                self.removalshapes.extend([(wa, False, 'pocketShape') for wa in workingAreas])
            else:
                # Translate pocket area faces to final depth plus envelope padding
                # The padding is a buffer for later internal rounding issues - *path data are unaffected*
                envPad = (self.radius * 0.1)
                envDepth = obj.FinalDepth.Value - envPad
                for f in workingAreas:
                    f.translate(FreeCAD.Vector(0.0, 0.0, envDepth - f.BoundBox.ZMin))
                extent = FreeCAD.Vector(0, 0, (obj.StartDepth.Value - obj.FinalDepth.Value) + 2 * envPad)

                # extrude all pocket area faces up to StartDepth plus padding and those are the removal shapes with padding
                self.removalshapes.extend([(face.removeSplitter().extrude(extent), False, 'pocketShape') for face in workingAreas])

        if workingSolids:
            # add working solids as prepared envelopes for 3D Pocket
            self.removalshapes.extend([(env, False, 'pocket3D') for env in workingSolids])
            # for env in workingSolids:
            #    PathLog.info("workingSolid ZMin: {}".format(env.BoundBox.ZMin))
            # [Part.show(env) for env in workingSolids]

        return self.removalshapes
# Eclass


def SetupProperties():
    setup = list()
    setup.extend([tup[1] for tup in ObjectPocket.opPropertyDefinitions(None)])
    setup.extend([tup[1] for tup in StrategyClearing.StrategyAdaptive.adaptivePropertyDefinitions()])
    return setup


def Create(name, obj=None):
    '''Create(name) ... Creates and returns a Pocket operation.'''
    if obj is None:
        obj = FreeCAD.ActiveDocument.addObject('Path::FeaturePython', name)

    obj.Proxy = ObjectPocket(obj, name)

    return obj