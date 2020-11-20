# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2018 sliptonic <shopinthewoods@gmail.com>               *
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
# pylint: disable=unused-import

import PathScripts.PathLog as PathLog

LOGLEVEL = False

if LOGLEVEL:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())

Processed = False

def Startup():
    global Processed # pylint: disable=global-statement
    if not Processed:
        PathLog.debug('Initializing PathGui')
        from PathScripts.Operations import PathAdaptiveGui
        from PathScripts import PathArray
        from PathScripts import PathComment
        # from PathScripts import PathCustom
        from PathScripts import PathCustomGui
        from PathScripts.Operations import PathDeburrGui
        from PathScripts import PathDressupAxisMap
        from PathScripts import PathDressupDogbone
        from PathScripts import PathDressupDragknife
        from PathScripts import PathDressupRampEntry
        from PathScripts import PathDressupPathBoundaryGui
        from PathScripts import PathDressupTagGui
        from PathScripts import PathDressupLeadInOut
        from PathScripts import PathDressupZCorrect
        from PathScripts.Operations import PathDrillingGui
        from PathScripts.Operations import PathEngraveGui
        from PathScripts import PathFixture
        from PathScripts.Operations import PathHelixGui
        from PathScripts import PathHop
        from PathScripts import PathInspect
        from PathScripts.Operations import PathMillFaceGui
        from PathScripts.Operations import PathPocketGui
        from PathScripts.Operations import PathPocketShapeGui
        from PathScripts import PathPost
        from PathScripts import PathProbeGui
        # Next three were merged into PathProfileGui
        # from PathScripts import PathProfileContourGui
        # from PathScripts import PathProfileEdgesGui
        # from PathScripts import PathProfileFacesGui
        from PathScripts.Operations import PathProfileGui
        from PathScripts import PathSanity
        from PathScripts import PathSetupSheetGui
        from PathScripts import PathSimpleCopy
        from PathScripts import PathSimulatorGui
        from PathScripts.Operations import PathSlotGui
        from PathScripts import PathStop
        # from PathScripts import PathSurfaceGui  # Added in initGui.py due to OCL dependency
        from PathScripts import PathToolController
        from PathScripts import PathToolControllerGui
        from PathScripts import PathToolLibraryManager
        from PathScripts import PathToolLibraryEditor
        from PathScripts import PathUtilsGui
        # from PathScripts import PathWaterlineGui  # Added in initGui.py due to OCL dependency
        from PathScripts.Dressups import PathDressupAxisMap
        from PathScripts.Dressups import PathDressupDogbone
        from PathScripts.Dressups import PathDressupDragknife
        from PathScripts.Dressups import PathDressupLeadInOut
        from PathScripts.Dressups import PathDressupPathBoundaryGui
        from PathScripts.Dressups import PathDressupRampEntry
        from PathScripts.Dressups import PathDressupTagGui
        from PathScripts.Dressups import PathDressupZCorrect
        from PathScripts.Operations import PathAdaptiveGui
        from PathScripts.Operations import PathDeburrGui
        from PathScripts.Operations import PathDrillingGui
        from PathScripts.Operations import PathEngraveGui
        from PathScripts.Operations import PathHelixGui
        from PathScripts.Operations import PathMillFaceGui
        from PathScripts.Operations import PathPocketGui
        from PathScripts.Operations import PathPocketShapeGui
        from PathScripts.Operations import PathProfileGui
        from PathScripts.Operations import PathSlotGui
        from PathScripts.Operations import PathVcarveGui
        Processed = True
    else:
        PathLog.debug('Skipping PathGui initialisation')
