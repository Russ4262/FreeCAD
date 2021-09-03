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
import PathScripts.PathJob as PathJob
import PathScripts.PathPocketShape as PathPocketShape
import PathScripts.PathGeom as PathGeom
from PathTests.PathTestUtils import PathTestBase
if FreeCAD.GuiUp:
    import PathScripts.PathPocketShapeGui as PathPocketShapeGui
    import PathScripts.PathJobGui as PathJobGui


class TestPathPocketShape(PathTestBase):
    '''Unit tests for the PocketShape operation.'''

    @classmethod
    def setUpClass(cls):
        '''setUpClass()...
        This method is called upon instantiation of this test class.  Add code and objects here
        that are needed for the duration of the test() methods in this class.  In other words,
        set up the 'global' test environment here; use the `setUp()` method to set up a 'local'
        test environment. 
        This method does not have access to the class `self` reference, but it
        is able to call static methods within this same class.
        '''

        # Create a new document and create test geometry
        # doc_title = "TestPocketShape"
        # doc = FreeCAD.newDocument(doc_title)
        # cls._createTestGeometry(doc)

        # Open existing document with test geometry
        doc = FreeCAD.open(FreeCAD.getHomePath() + 'Mod/Path/PathTests/test_pocketshape.fcstd')

        # Create Job object, adding geometry objects from file opened above
        job = PathJob.Create('Job', [doc.Fuse0r, doc.Box2, doc.Body, doc.Body001], None)
        job.GeometryTolerance.Value = 0.001
        if FreeCAD.GuiUp:
            job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)

        # Instantiate an Adaptive operation for quering available properties
        prototype = PathPocketShape.Create("PocketShape")
        prototype.Base = [(doc.Fuse0r, ["Face2"])]
        prototype.Label = "Prototype"
        _addViewProvider(prototype)

        doc.recompute()

    @classmethod
    def tearDownClass(cls):
        '''tearDownClass()...
        This method is called prior to destruction of this test class.  Add code and objects here
        that cleanup the test environment after the test() methods in this class have been executed.
        This method does not have access to the class `self` reference.  This method
        is able to call static methods within this same class.
        '''
        # FreeCAD.Console.PrintMessage("TestPathPocketShape.tearDownClass()\n")

        # Comment out to leave test file open and objects and paths intact after all tests finish
        # FreeCAD.closeDocument(FreeCAD.ActiveDocument.Name)
        pass

    @staticmethod
    def _createTestGeometry(doc):
        '''_createTestGeometry(doc)...
        This contains the instructions to create test geometry for the unit tests in this class.
        A simple example creation is provided.
        '''

        # Create a square donut
        box0 = doc.addObject('Part::Box', 'Box0')  # Box
        box0.Length = 50.0
        box0.Width = 50.0
        box0.Height = 10.0
        box1 = doc.addObject('Part::Box', 'Box1')  # Box001
        box1.Length = 10.0  # X
        box1.Width = 10.0  # Y
        box1.Height = 20.0  # Z
        box1.Placement = FreeCAD.Placement(FreeCAD.Vector(10.0, 10.0, -5.0), FreeCAD.Rotation(FreeCAD.Vector(0,0,1), 0))
        cut0 = doc.addObject('Part::Cut', 'Cut0')
        cut0.Base = box0
        cut0.Tool = box1
        doc.recompute()

    # Setup and tear down methods called before and after each unit test
    def setUp(self):
        '''setUp()...
        This method is called prior to each `test()` method.  Add code and objects here
        that are needed for multiple `test()` methods.
        '''
        self.doc = FreeCAD.ActiveDocument
        self.con = FreeCAD.Console

    def tearDown(self):
        '''tearDown()...
        This method is called after each test() method. Add cleanup instructions here.
        Such cleanup instructions will likely undo those in the setUp() method.
        '''
        pass

    # Unit tests
    def test00(self):
        '''test00() Verify default property values.'''

        # Instantiate a PocketShape operation and set Base Geometry
        op = FreeCAD.ActiveDocument.getObject('PocketShape')

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
            'BoundaryShape': 'Face Region',
            'HandleMultipleFeatures': 'Collectively',
            'ProcessPerimeter': True,
            'ProcessHoles': True,
            'ProcessCircles': True,
            # 'AreaParams': '',  # Changes when operation is executed
            # 'PathParams': '',  # Changes when operation is executed
            'ShowDebugShapes': False
        }
        for k, v in defaults.items():
            prop = getattr(op, k)
            if hasattr(prop, "Value"):
                self.assertEqual(prop.Value, v, "default {}: {} is not op {}: {}".format(k, v, k, prop.Value))
            else:
                self.assertEqual(prop, v, "default {}: {} is not op {}: {}".format(k, v, k, prop))

    def test01(self):
        '''test01() Verify `ProcessPerimeter` function without internal holes or circles.'''

        # Instantiate a PocketShape operation and set Base Geometry
        op = PathPocketShape.Create('PocketShape')
        op.Base = [(self.doc.Fuse0r, ["Face16"])]  # (base, subs_list)
        op.Label = "test01+"
        op.Comment = "test01() Verify `ProcessPerimeter` function without internal holes or circles."

        # Set additional operation properties
        # setDepthsAndHeights(op)
        op.CutPattern = "ZigZag"
        op.CutPatternAngle = 0.0
        op.ProcessHoles = False
        op.ProcessCircles = False
        op.setExpression('StepDown', None)
        op.StepDown.Value = 20.0  # Have to set expression to None before numerical value assignment

        _addViewProvider(op)
        self.doc.recompute()

        moves = getGcodeMoves(op.Path.Commands, includeRapids=False)
        operationMoves = ";  ".join(moves)
        # self.con.PrintMessage("test00_moves: " + operationMoves + "\n")

        self.assertTrue(expected_moves_test01 == operationMoves,
                        "expected_moves_test01: {}\noperationMoves: {}".format(expected_moves_test01.replace(";  ", ";  \\\n"), operationMoves.replace(";  ", ";  \\\n")))

    def test02(self):
        '''test02() PocketShape check basic functionality with Body001:Face18 and CutPattern=Offset; StepOver=50'''

        # Instantiate a PocketShape operation and set Base Geometry
        op = PathPocketShape.Create('PocketShape')
        op.Base = [(self.doc.Body001, ["Face18"])]  # (base, subs_list)
        op.Label = "test02+"
        op.Comment = "PocketShape check basic functionality with Body001:Face18 and CutPattern=Offset; StepOver=50"

        # Set additional operation properties
        # setDepthsAndHeights(op)
        op.CutPattern = "ZigZag"
        op.CutPatternAngle = 0.0
        op.setExpression('StepOver', None)
        op.StepOver.Value = 50
        op.setExpression('StepDown', None)
        op.StepDown.Value = 20.0  # Have to set expression to None before numerical value assignment

        _addViewProvider(op)
        self.doc.recompute()
        
        moves = getGcodeMoves(op.Path.Commands, includeRapids=False)
        operationMoves = ";  ".join(moves)
        # self.con.PrintMessage("test00_moves: " + operationMoves + "\n")

        self.assertTrue(expected_moves_test02 == operationMoves,
                        "expected_moves_test02: {}\noperationMoves: {}".format(expected_moves_test02.replace(";  ", ";  \\\n"), operationMoves.replace(";  ", ";  \\\n")))

    def test03(self):
        '''test03() PocketShape verify overhang is ignored with Body001:Face16 and CutPattern=Offset; StepOver=50'''

        # Instantiate a PocketShape operation and set Base Geometry
        op = PathPocketShape.Create('PocketShape')
        op.Base = [(self.doc.Body001, ["Face16"])]  # (base, subs_list)
        op.Label = "test03+"
        op.Comment = "PocketShape verify overhang is ignored with Body001:Face16 and CutPattern=Offset; StepOver=50"

        # Set additional operation properties
        # setDepthsAndHeights(op)
        op.CutPattern = "ZigZag"
        op.CutPatternAngle = 0.0
        op.StepOver = 50
        op.setExpression('StepDown', None)
        op.StepDown.Value = 20.0  # Have to set expression to None before numerical value assignment

        _addViewProvider(op)
        self.doc.recompute()
        
        moves = getGcodeMoves(op.Path.Commands, includeRapids=False)
        operationMoves = ";  ".join(moves)
        # self.con.PrintMessage("test01_moves: " + operationMoves + "\n")

        self.assertTrue(expected_moves_test03 == operationMoves,
                        "expected_moves_test03: {}\noperationMoves: {}".format(expected_moves_test03.replace(";  ", ";  \\\n"), operationMoves.replace(";  ", ";  \\\n")))

    def test04(self):
        '''test04() PocketShape verify Extra Offset with Body001:Face18 and CutPattern=Offset; StepOver=50; MaterialAllowance=-2.5'''

        # Instantiate a PocketShape operation and set Base Geometry
        op = PathPocketShape.Create('PocketShape')
        op.Base = [(self.doc.Body001, ["Face18"])]  # (base, subs_list)
        op.Label = "test04+"
        op.Comment = "PocketShape verify Extra Offset with Body001:Face18 and CutPattern=Offset; StepOver=50; MaterialAllowance=-2.5"
        # self.doc.recompute()

        # Set additional operation properties
        # setDepthsAndHeights(op, finDep=15)
        # op.FinalDepth.Value = 15.0
        op.CutPattern = "ZigZag"
        op.CutPatternAngle = 0.0
        op.setExpression('StepOver', None)
        op.StepOver.Value = 50.0
        op.MaterialAllowance.Value = -2.5
        op.setExpression('StepDown', None)
        op.StepDown.Value = 20.0  # Have to set expression to None before numerical value assignment

        _addViewProvider(op)
        self.doc.recompute()

        moves = getGcodeMoves(op.Path.Commands, includeRapids=False)
        operationMoves = ";  ".join(moves)
        # self.con.PrintMessage("test02_moves: " + ";  \\\n".join(moves) + "\n")

        self.assertTrue(expected_moves_test04 == operationMoves,
                        "expected_moves_test04: {}\noperationMoves: {}".format(expected_moves_test04.replace(";  ", ";  \\\n"), operationMoves.replace(";  ", ";  \\\n")))

    def test05(self):
        '''test05() PocketShape verify Process Perimeter only with Fuse0r:Face16 and CutPattern=Offset; StepOver=50'''

        # Instantiate a PocketShape operation and set Base Geometry
        op = PathPocketShape.Create('PocketShape')
        op.Base = [(self.doc.Fuse0r, ["Face16"])]  # (base, subs_list)
        op.Label = "test05+"
        op.Comment = "PocketShape verify Process Perimeter only with Fuse0r:Face16 and CutPattern=Offset; StepOver=50"

        # Set additional operation properties
        # setDepthsAndHeights(op, finDep=5.0)
        # op.FinalDepth.Value = 5.0
        op.CutPattern = "ZigZag"
        op.CutPatternAngle = 0.0
        op.StepOver.Value = 50
        op.ProcessPerimeter = True
        op.ProcessHoles = False
        op.ProcessCircles = False

        _addViewProvider(op)
        self.doc.recompute()
        
        moves = getGcodeMoves(op.Path.Commands, includeRapids=False)
        operationMoves = ";  ".join(moves)
        # self.con.PrintMessage("test03_moves: " + ";  \\\n".join(moves) + "\n")

        self.assertTrue(expected_moves_test05 == operationMoves,
                        "expected_moves_test05: {}\noperationMoves: {}".format(expected_moves_test05.replace(";  ", ";  \\\n"), operationMoves.replace(";  ", ";  \\\n")))

    # Support methods
    def _verifyPointData(self, testName, points, verify_points):
        '''_verifyPointData(testName, points, verify_points)...
        General method to compare point data of path with verified points.'''

        len_pts = len(points)
        len_vrfy_pts = len(verify_points)

        # Verify point count
        if len_vrfy_pts > len_pts:
            self.con.PrintMessage("verify_points: {}\n".format(verify_points))
            self.con.PrintMessage("...... points: {}\n".format(points))
        self.assertFalse(len_vrfy_pts > len_pts)

        # Verify each point, excluding arcs
        for vp in verify_points:
            if vp not in points:
                self.con.PrintMessage("verify_points: {}\n".format(verify_points))
                self.con.PrintMessage("...... points: {}\n".format(points))
                self.assertEqual(vp, "(-10.0, -10.0, -10.0)")
# Eclass


def setDepthsAndHeights(op, strDep=20.0, finDep=0.0):
    '''setDepthsAndHeights(op, strDep=20.0, finDep=0.0)... Sets default depths and heights for `op` passed to it'''

    # Set start and final depth in order to eliminate effects of stock (and its default values)
    op.setExpression('StartDepth', None)
    op.StartDepth.Value = strDep
    op.setExpression('FinalDepth', None)
    op.FinalDepth.Value = finDep

    # Set step down so as to only produce one layer path
    op.setExpression('StepDown', None)
    op.StepDown.Value = 20.0

    # Set Heights
    # default values used

def getGcodeMoves(cmdList, includeRapids=True, includeLines=True, includeArcs=True):
    '''getGcodeMoves(cmdList, includeRapids=True, includeLines=True, includeArcs=True)...
    Accepts command dict and returns point string coordinate.
    '''
    gcode_list = list()
    last = FreeCAD.Vector(0.0, 0.0, 0.0)
    for c in cmdList:
        p = c.Parameters
        name = c.Name
        if includeRapids and name in ["G0", "G00"]:
            gcode = name
            x = last.x
            y = last.y
            z = last.z
            if p.get("X"):
                x = round(p["X"], 2)
                gcode += " X" + str(x) 
            if p.get("Y"):
                y = round(p["Y"], 2)
                gcode += " Y" + str(y) 
            if p.get("Z"):
                z = round(p["Z"], 2)
                gcode += " Z" + str(z) 
            last.x = x
            last.y = y
            last.z = z
            gcode_list.append(gcode)
        elif includeLines and name in ["G1", "G01"]:
            gcode = name
            x = last.x
            y = last.y
            z = last.z
            if p.get("X"):
                x = round(p["X"], 2)
                gcode += " X" + str(x) 
            if p.get("Y"):
                y = round(p["Y"], 2)
                gcode += " Y" + str(y) 
            if p.get("Z"):
                z = round(p["Z"], 2)
                gcode += " Z" + str(z) 
            last.x = x
            last.y = y
            last.z = z
            gcode_list.append(gcode)
        elif includeArcs and name in ["G2", "G3", "G02", "G03"]:
            gcode = name
            x = last.x
            y = last.y
            z = last.z
            i = 0.0
            j = 0.0
            k = 0.0
            if p.get("I"):
                i = round(p["I"], 2)
            gcode += " I" + str(i)
            if p.get("J"):
                j = round(p["J"], 2)
            gcode += " J" + str(j)
            if p.get("K"):
                k = round(p["K"], 2)
            gcode += " K" + str(k)

            if p.get("X"):
                x = round(p["X"], 2)
            gcode += " X" + str(x) 
            if p.get("Y"):
                y = round(p["Y"], 2)
            gcode += " Y" + str(y) 
            if p.get("Z"):
                z = round(p["Z"], 2)
            gcode += " Z" + str(z) 

            gcode_list.append(gcode)
            last.x = x
            last.y = y
            last.z = z
    return gcode_list


def _addViewProvider(op):
    if FreeCAD.GuiUp:
        PathOpGui = PathPocketShapeGui.PathOpGui
        cmdRes = PathPocketShapeGui.Command.res
        op.ViewObject.Proxy = PathOpGui.ViewProvider(op.ViewObject, cmdRes)
        op.ViewObject.Document.setEdit(op.ViewObject, 5)


# Expected moves for unit tests
expected_moves_test01 = " G1 X20.0 Y20.0 Z5.0;  \
G1 X30.0 Y20.0 Z5.0;  \
G1 X30.0 Y22.5 Z5.0;  \
G1 X20.0 Y22.5 Z5.0;  \
G1 X20.0 Y25.0 Z5.0;  \
G1 X30.0 Y25.0 Z5.0;  \
G1 X30.0 Y27.5 Z5.0;  \
G1 X20.0 Y27.5 Z5.0;  \
G1 X20.0 Y30.0 Z5.0;  \
G1 X30.0 Y30.0 Z5.0"

expected_moves_test02 = "G1 X20.0 Y-20.0 Z15.0;  \
G1 X20.0 Y-20.0 Z15.0"

expected_moves_test03 = "G1 X32.5 Y-22.5 Z5.0;  \
G1 X32.5 Y-22.76 Z5.0;  \
G3 I2.4 J-12.0 K0.0 X27.5 Y-25.01 Z5.0;  \
G1 X27.5 Y-25.0 Z5.0;  \
G1 X27.5 Y-22.5 Z5.0;  \
G1 X32.5 Y-22.5 Z5.0;  \
G1 X25.02 Y-27.5 Z5.0;  \
G3 I9.66 J-7.36 K0.0 X22.76 Y-32.5 Z5.0;  \
G1 X22.5 Y-32.5 Z5.0;  \
G1 X22.5 Y-27.5 Z5.0;  \
G1 X25.0 Y-27.5 Z5.0;  \
G1 X25.02 Y-27.5 Z5.0"

expected_moves_test04 = "G1 X25.0 Y-25.0 Z15.0;  \
G1 X15.0 Y-25.0 Z15.0;  \
G1 X15.0 Y-22.5 Z15.0;  \
G1 X25.0 Y-22.5 Z15.0;  \
G1 X25.0 Y-20.0 Z15.0;  \
G1 X15.0 Y-20.0 Z15.0;  \
G1 X15.0 Y-17.5 Z15.0;  \
G1 X25.0 Y-17.5 Z15.0;  \
G1 X25.0 Y-15.0 Z15.0;  \
G1 X15.0 Y-15.0 Z15.0"

expected_moves_test05 = "G1 X20.0 Y20.0 Z11.0;  \
G1 X30.0 Y20.0 Z11.0;  \
G1 X30.0 Y22.5 Z11.0;  \
G1 X20.0 Y22.5 Z11.0;  \
G1 X20.0 Y25.0 Z11.0;  \
G1 X30.0 Y25.0 Z11.0;  \
G1 X30.0 Y27.5 Z11.0;  \
G1 X20.0 Y27.5 Z11.0;  \
G1 X20.0 Y30.0 Z11.0;  \
G1 X30.0 Y30.0 Z11.0;  \
G1 X20.0 Y20.0 Z6.0;  \
G1 X30.0 Y20.0 Z6.0;  \
G1 X30.0 Y22.5 Z6.0;  \
G1 X20.0 Y22.5 Z6.0;  \
G1 X20.0 Y25.0 Z6.0;  \
G1 X30.0 Y25.0 Z6.0;  \
G1 X30.0 Y27.5 Z6.0;  \
G1 X20.0 Y27.5 Z6.0;  \
G1 X20.0 Y30.0 Z6.0;  \
G1 X30.0 Y30.0 Z6.0;  \
G1 X20.0 Y20.0 Z5.0;  \
G1 X30.0 Y20.0 Z5.0;  \
G1 X30.0 Y22.5 Z5.0;  \
G1 X20.0 Y22.5 Z5.0;  \
G1 X20.0 Y25.0 Z5.0;  \
G1 X30.0 Y25.0 Z5.0;  \
G1 X30.0 Y27.5 Z5.0;  \
G1 X20.0 Y27.5 Z5.0;  \
G1 X20.0 Y30.0 Z5.0;  \
G1 X30.0 Y30.0 Z5.0"