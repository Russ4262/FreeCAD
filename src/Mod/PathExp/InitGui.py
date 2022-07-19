# ***************************************************************************
# *   Copyright (c) 2022 Russell Johnson (russ4262) <russ4262@gmail.com>    *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful,            *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Lesser General Public License for more details.                   *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with FreeCAD; if not, write to the Free Software        *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************


class PathExpCommandGroup:
    def __init__(self, cmdlist, menu, tooltip=None):
        self.cmdlist = cmdlist
        self.menu = menu
        if tooltip is None:
            self.tooltip = menu
        else:
            self.tooltip = tooltip

    def GetCommands(self):
        return tuple(self.cmdlist)

    def GetResources(self):
        return {"MenuText": self.menu, "ToolTip": self.tooltip}

    def IsActive(self):
        if FreeCAD.ActiveDocument is not None:
            for o in FreeCAD.ActiveDocument.Objects:
                if o.Name.startswith("Body"):
                    FreeCAD.Console.PrintWarning(
                        "Path Experimental command group is active.\n"
                    )
                    return True
        return False


class PathExpWorkbench(Workbench):
    "Path Experimental workbench"

    def __init__(self):
        # self.__class__.Icon = (
        #    FreeCAD.getResourceDir() + "Mod/Path/Resources/icons/PathWorkbench.svg"
        # )
        self.__class__.Icon = (
            FreeCAD.getUserAppDataDir() + "Mod/PathExp/GuiSupport/PathExpWorkbench.svg"
        )
        self.__class__.MenuText = "Path Exp"
        self.__class__.ToolTip = (
            "An experimental workbench to enhance the Path workbench"
        )

    def Initialize(self):
        global PathExpCommandGroup
        import PathExpCommands

        translate = FreeCAD.Qt.translate
        FreeCADGui.addLanguagePath(":/translations")
        FreeCADGui.addIconPath(":/icons")

        # FreeCADGui.addCommand("PathExp_Toggle", PathExpCommands._Toggle())
        # FreeCADGui.addCommand("PathExp_Profile", PathExpCommands._ProfileOperation())
        # FreeCADGui.addCommand("PathExp_Sample", PathExpCommands._SampleOperation())
        # FreeCADGui.addCommand("PathExp_Slot", PathExpCommands._SlotOperation())
        pwbc = PathExpCommands._LoadPathWorkbench()
        pwbc.Icon = (
            FreeCAD.getUserAppDataDir() + "Mod/PathExp/GuiSupport/PathExpWorkbench.svg"
        )
        FreeCADGui.addCommand("_LoadPathWorkbench", pwbc)
        FreeCADGui.addCommand("_TargetShape", PathExpCommands._TargetShape())
        FreeCADGui.addCommand("_StartOperation", PathExpCommands._StartOperation())

        # import MyModuleA, MyModuleB  # import here all the needed files that create your FreeCAD commands

        # A list of command names created in the line above
        self.list = [
            # "PathExp_Toggle",
            # "PathExp_Profile",
            # "PathExp_Sample",
            # "PathExp_Slot",
            "_LoadPathWorkbench",
            "_TargetShape",
            "_StartOperation",
        ]
        # creates a new toolbar with your commands
        self.appendToolbar("My Commands", self.list)
        self.appendMenu("Path Exp", self.list)  # creates a new menu
        # self.appendMenu(["An existing Menu","My submenu"],self.list) # appends a submenu to an existing menu

    def GetClassName(self):
        return "Gui::PythonWorkbench"

    def Activated(self):
        # update the translation engine
        FreeCADGui.updateLocale()
        # Msg("Path workbench activated\n")

    def Deactivated(self):
        # Msg("Path workbench deactivated\n")
        pass

    def ContextMenu(self, recipient):
        self.appendContextMenu(
            "My commands", self.list
        )  # add commands to the context menu


Gui.addWorkbench(PathExpWorkbench())

# FreeCAD.addImportType("GCode (*.nc *.gc *.ncc *.ngc *.cnc *.tap *.gcode)", "PathGui")


FreeCAD.Console.PrintMessage("Loading GUI portion of Path Experimental workbench...\n")
