# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2022 Russell Johnson (russ4262) <russ4262@gmail.com>    *
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

import PathScripts.PathLog as PathLog
from pivy import coin


__title__ = "Path UI helper and utility functions"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "A collection of helper and utility functions for the Path GUI."


if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())


class PreviewShape(object):
    """class PreviewShape(shape, color=(0.25, 0.5, 0.75), transparency=0.6)...
    This class creates a Coin3D object that is ready to be added to the current
    scenegraph."""

    def __init__(self, shape, color=(0.25, 0.5, 0.75), transparency=0.6):
        self.shape = shape
        self.color = color

        sep = coin.SoSeparator()
        pos = coin.SoTranslation()
        mat = coin.SoMaterial()
        crd = coin.SoCoordinate3()
        fce = coin.SoFaceSet()
        hnt = coin.SoShapeHints()

        allPolys = list()
        numVert = list()
        cnt = 0
        # Need to add type check for incoming shape: Solid, Shell, Face, Wire, Edge, etc...
        for f in shape.Faces:
            cnt += 1
            pCnt = 0
            for w in f.Wires:
                # poly = [p for p in w.discretize(Deflection=0.01)][:-1]
                poly = [p for p in w.discretize(Deflection=0.01)]
                pCnt += len(poly)
                allPolys.extend(poly)
            numVert.append(pCnt)
        points = [(p.x, p.y, p.z) for p in allPolys]

        crd.point.setValues(points)
        fce.numVertices.setValues(tuple(numVert))

        mat.diffuseColor = color
        mat.transparency = transparency
        hnt.faceType = coin.SoShapeHints.UNKNOWN_FACE_TYPE
        hnt.vertexOrdering = coin.SoShapeHints.CLOCKWISE

        sep.addChild(pos)
        sep.addChild(mat)
        sep.addChild(hnt)
        sep.addChild(crd)
        sep.addChild(fce)

        switch = coin.SoSwitch()
        switch.addChild(sep)
        switch.whichChild = coin.SO_SWITCH_NONE

        self.material = mat

        self.switch = switch
        self.root = switch
        self.switch.whichChild = coin.SO_SWITCH_ALL


# Eclass
