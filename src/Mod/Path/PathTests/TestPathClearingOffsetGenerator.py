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

import Path
import FreeCAD
import Generators.clearing_offset_generator as generator
import PathScripts.PathLog as PathLog
import PathTests.PathTestUtils as PathTestUtils
import Part


import PathScripts.PathJob as PathJob
import PathScripts.PathCustom as PathCustom

if FreeCAD.GuiUp:
    import PathScripts.PathCustomGui as PathCustomGui
    import PathScripts.PathJobGui as PathJobGui


PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())
PathLog.trackModule(PathLog.thisModule())


def _addViewProvider(op):
    if FreeCAD.GuiUp:
        PathOpGui = PathCustomGui.PathOpGui
        cmdRes = PathCustomGui.Command.res
        op.ViewObject.Proxy = PathOpGui.ViewProvider(op.ViewObject, cmdRes)
        op.ViewObject.Proxy.deleteOnReject = False
        op.ViewObject.Visibility = False


class TestPathClearingOffsetGenerator(PathTestUtils.PathTestBase):
    @classmethod
    def setUpClass(cls):
        """setUpClass()...
        This method is called upon instantiation of this test class.  Add code and objects here
        that are needed for the duration of the test() methods in this class.  In other words,
        set up the 'global' test environment here; use the `setUp()` method to set up a 'local'
        test environment.
        This method does not have access to the class `self` reference, but it
        is able to call static methods within this same class.
        """

        # Open existing FreeCAD document with test geometry
        # doc = FreeCAD.open(
        #     FreeCAD.getHomePath() + "Mod/Path/PathTests/test_adaptive.fcstd"
        # )

        cls.makeFaces()
        doc = FreeCAD.ActiveDocument
        # box = doc.addObject("Part::Box", "Box")
        # box.Shape = Part.makeBox(30, 20, 10)

        doc.Shape001.Placement.Base = FreeCAD.Vector(60, 60, 0)
        cut = doc.Shape.Shape.cut(doc.Shape001.Shape)
        Part.show(cut)

        # Create Job object, adding geometry objects from file opened above
        job = PathJob.Create("Job", [doc.Shape, doc.Shape001, doc.Shape002], None)
        job.GeometryTolerance.Value = 0.001
        if FreeCAD.GuiUp:
            job.ViewObject.Proxy = PathJobGui.ViewProvider(job.ViewObject)
            job.ViewObject.Proxy.showOriginAxis(True)
            job.ViewObject.Proxy.deleteOnReject = False
            # box.ViewObject.Visibility = False
            doc.Shape.ViewObject.Visibility = False
            doc.Shape001.ViewObject.Visibility = False

        # Instantiate an Adaptive operation for querying available properties
        prototype = PathCustom.Create("Custom")
        prototype.Label = "Prototype"
        _addViewProvider(prototype)

        doc.recompute()

    @classmethod
    def tearDownClass(cls):
        """tearDownClass()...
        This method is called prior to destruction of this test class.  Add code and objects here
        that cleanup the test environment after the test() methods in this class have been executed.
        This method does not have access to the class `self` reference.  This method
        is able to call static methods within this same class.
        """
        # FreeCAD.Console.PrintMessage("TestPathAdaptive.tearDownClass()\n")

        # Close geometry document without saving
        # FreeCAD.closeDocument(FreeCAD.ActiveDocument.Name)
        pass

    @classmethod
    def makeFaces(cls):
        p1 = FreeCAD.Vector(0, 0, 0)
        p2 = FreeCAD.Vector(0, 100, 0)
        p3 = FreeCAD.Vector(100, 100, 0)
        p4 = FreeCAD.Vector(100, 0, 0)

        seg1 = Part.makeLine(p1, p2)
        seg2 = Part.makeLine(p2, p3)
        seg3 = Part.makeLine(p3, p4)
        seg4 = Part.makeLine(p4, p1)

        wire = Part.Wire([seg1, seg2, seg3, seg4])
        face = Part.Face(wire)
        Part.show(face)

        circle = Part.makeCircle(15.0)
        circleFace = Part.Face(Part.Wire([circle]))
        Part.show(circleFace)

    # Setup and tear down methods called before and after each unit test
    def setUp(self):
        """setUp()...
        This method is called prior to each `test()` method.  Add code and objects here
        that are needed for multiple `test()` methods.
        """
        self.doc = FreeCAD.ActiveDocument
        self.con = FreeCAD.Console
        self.tc = self.doc.Job.Tools.Group[0]

    def tearDown(self):
        """tearDown()...
        This method is called after each test() method. Add cleanup instructions here.
        Such cleanup instructions will likely undo those in the setUp() method.
        """
        pass

    def resetArgs(self):
        return {
            "face": self.doc.Shape002.Shape.copy(),
            "toolController": self.tc,
            "retractHeight": 10.0,
            "finalDepth": 0.0,
            "stepOver": 40.0,
            "patternCenterAt": "CenterOfBoundBox",
            "patternCenterCustom": FreeCAD.Vector(0.0, 0.0, 0.0),
            "cutPatternAngle": 0.0,
            "cutPatternReversed": False,
            "cutDirection": "Conventional",
            "minTravel": False,
            "keepToolDown": False,
            "jobTolerance": 0.001,
        }

    def test00(self):
        """Test Line Clearing Generator Return"""

        args = {
            "face": self.doc.Shape002.Shape.copy(),
            "toolController": self.tc,
            "retractHeight": 10.0,
            "finalDepth": 0.0,
            "stepOver": 40.0,
            "patternCenterAt": "CenterOfBoundBox",
            "patternCenterCustom": FreeCAD.Vector(0.0, 0.0, 0.0),
            "cutPatternAngle": 0.0,
            "cutPatternReversed": False,
            "cutDirection": "Conventional",
            "minTravel": False,
            "keepToolDown": False,
            "jobTolerance": 0.001,
        }

        result = generator.generate(**args)

        self.assertTrue(type(result) is list)
        self.assertTrue(type(result[0]) is Path.Command)

        # for c in result:
        #    print("cmd: {}".format(c))

        # Instantiate an Adaptive operation for querying available properties
        op = PathCustom.Create("Custom")
        op.Label = "Custom_test00"
        op.Gcode = [r.toGCode() + "\n" for r in result]
        _addViewProvider(op)

    def test01(self):
        """Test Line Clearing Generator argument types and value limits"""

        args = self.resetArgs()

        # require step over > 0.01
        args["stepOver"] = 0.0
        self.assertRaises(ValueError, generator.generate, **args)

        # require step over <= 100.0
        args["stepOver"] = 100.1
        self.assertRaises(ValueError, generator.generate, **args)

        # require retractHeight is float
        args = self.resetArgs()
        args["retractHeight"] = 10
        self.assertRaises(ValueError, generator.generate, **args)

        # require finalDepth is float
        args = self.resetArgs()
        args["finalDepth"] = 1
        self.assertRaises(ValueError, generator.generate, **args)

    def test02(self):
        """Test Offset Clearing Generator verify keepToolDown feature"""

        """args = self.resetArgs()
        args["keepToolDown"] = True

        result = generator.generate(**args)

        self.assertTrue(type(result) is list)
        self.assertTrue(type(result[0]) is Path.Command)

        # for c in result:
        #    print("cmd: {}".format(c))

        # Instantiate an Adaptive operation for querying available properties
        op = PathCustom.Create("Custom")
        op.Label = "Custom_test02"
        op.Gcode = [r.toGCode() + "\n" for r in result]
        _addViewProvider(op)"""
        return
