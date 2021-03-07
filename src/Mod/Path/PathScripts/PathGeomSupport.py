# -*- coding: utf-8 -*-
# ***************************************************************************
# *   Copyright (c) 2020 Russell Johnson (russ4262) <russ4262@gmail.com>    *
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

from PySide import QtCore
import PathScripts.PathLog as PathLog

# lazily loaded modules
from lazy_loader.lazy_loader import LazyLoader

Part = LazyLoader("Part", globals(), "Part")

__title__ = "PathGeomSupport - additional geometry utilities for Path"
__author__ = "russ4262 (Russell Johnson)"
__url__ = "https://www.freecadweb.org"
__doc__ = "Support functions for managing edges."

Tolerance = 0.000001

PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
# PathLog.trackModule(PathLog.thisModule())

# Qt translation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)


class find_loops:
    """find_loops()...
    Expects list of edges containing one or more complete horizontal loops.
    Non-horizontal edges will be filtered out."""

    def __init__(self, edges):
        self.edges = edges
        self.loops = list()
        self.closed_loops = list()
        self.open_wires = list()
        self.extra_edges = list()
        self.loop = None
        self.loop_last_idx = None
        self.last = None  # track last edge index
        self.first = None  # track first edge index
        self.loop_edges_indexes = None
        self.z_last = None  # track last edge index
        self.horiz_edges = None
        self.other_edges = None

        self._prepare_edge_data(edges)

    # Internal methods
    def _prepare_edge_data(self, edges):
        # pull all edges and format for sorting
        horiz_edges = list()
        other_edges = list()
        for i, e in enumerate(edges):
            v0x = round(e.Vertexes[0].X, 4)
            v0y = round(e.Vertexes[0].Y, 4)
            v0z = round(e.Vertexes[0].Z, 4)
            v1x = round(e.Vertexes[1].X, 4)
            v1y = round(e.Vertexes[1].Y, 4)
            v1z = round(e.Vertexes[1].Z, 4)
            z = v1z - v0z
            if z == 0.0:
                p0 = "x{}_y{}_z{}".format(v0x, v0y, v0z)
                p1 = "x{}_y{}_z{}".format(v1x, v1y, v1z)
                horiz_edges.append((p0, p1, i))
            else:
                p0 = "z{}_x{}_y{}".format(v0z, v0x, v0y)
                p1 = "z{}_x{}_y{}".format(v1z, v1x, v1y)
                other_edges.append((p0, p1, i))

        # sort and store edges
        horiz_edges.sort(key=lambda tup: tup[0])
        other_edges.sort(key=lambda tup: tup[0])
        self.horiz_edges = horiz_edges
        self.other_edges = other_edges
        # PathLog.debug('len(horiz_edges): {}'.format(len(horiz_edges)))

    def _identify_loops(self, edge_list, cycle=1):
        self._initialize_loop(edge_list)
        search = True
        unused_list = list()
        while_cnt = 0
        connected = 0
        clean = False

        while search:
            while_cnt += 1
            cnt = len(edge_list)
            connected = 1
            for i in range(0, cnt):
                # pop off tuple
                edg_tup = edge_list.pop(0)
                # check if it connects to first or last edge in active loop
                if self._check_connection(edg_tup):
                    # PathLog.debug('... connected')
                    connected = 2
                    clean = False
                else:
                    # place independent edge in unused_list for recycling
                    unused_list.append(edg_tup)

            unused_cnt = len(unused_list)
            if connected == 1:
                if clean:
                    connected = 0
                    # PathLog.debug('unused_cnt == cnt: {}'.format(unused_cnt))
                    # no edges connected to active loop = ready to save

                    if cycle == 1:
                        # Check if list of edges forms closed loop and save accordingly
                        if self.loop_last_idx > 1 and self._edges_connected(
                            self.loop[0], self.loop[self.loop_last_idx]
                        ):
                            # extract list of edges from self.loop data and save
                            self.closed_loops.append(
                                [self.edges[lei] for lei in self.loop_edges_indexes]
                            )
                        else:
                            self.other_edges.extend(self.loop)
                    elif cycle == 2:
                        # Check if list of edges forms closed loop and save accordingly
                        if self.loop_last_idx > 0 and self._edges_connected(
                            self.loop[0], self.loop[self.loop_last_idx]
                        ):
                            # extract list of edges from self.loop data and save
                            # PathLog.debug('saving open wire self.loop_edges_indexes: {}'.format(self.loop_edges_indexes))
                            self.open_wires.append(
                                [self.edges[lei] for lei in self.loop_edges_indexes]
                            )
                        else:
                            self.extra_edges.extend(self.loop)

                    if unused_cnt == 0:
                        search = False
                        break

                    edge_list.extend(unused_list)
                    self._initialize_loop(edge_list)
                    unused_list = list()
                    clean = False
                else:
                    clean = True
                    edge_list.extend(unused_list)
                    unused_list = list()
            else:
                edge_list.extend(unused_list)
                unused_list = list()

            if while_cnt > 100:
                PathLog.error("while_cnt > 100")
                break

    def _initialize_loop(self, edge_list):
        self.loop = [edge_list.pop(0)]
        self.last = self.loop[0][2]  # track last edge index
        self.first = self.loop[0][2]  # track first edge index
        self.loop_last_idx = 0
        self.loop_edges_indexes = [self.last]

    def _check_connection(self, edg_tup):
        # check if edge attaches to last
        if self._edges_connected(self.loop[self.loop_last_idx], edg_tup):
            # check if edge connects to last edge in active loop
            self.loop.append(edg_tup)
            self.last = edg_tup[2]
            self.loop_last_idx += 1
            self.loop_edges_indexes.append(self.last)
            return True
        if self._edges_connected(self.loop[0], edg_tup):
            # check if edge connects to first edge in active loop
            self.loop.insert(0, edg_tup)
            self.first = edg_tup[2]
            self.loop_last_idx += 1
            self.loop_edges_indexes.insert(0, self.first)
            return True
        return False

    def _edges_connected(self, tup1, tup2):
        if tup1[0] == tup2[0] or tup1[1] == tup2[0]:
            return True
        if tup1[0] == tup2[1] or tup1[1] == tup2[1]:
            return True
        return False

    # Public methods
    def get_closed_loops(self):
        # extract closed loops first
        # PathLog.debug('len(self.horiz_edges): {}'.format(len(self.horiz_edges)))
        if self.horiz_edges:
            self._identify_loops(self.horiz_edges, 1)
            loops = [Part.Wire(Part.__sortEdges__(cl)) for cl in self.closed_loops]
            return loops

        return list()

    def get_all_wires(self):
        loops = self.get_closed_loops()

        # extract open wires
        if self.other_edges:
            # PathLog.debug('len(self.other_edges): {}'.format(len(self.other_edges)))
            self.other_edges.sort(key=lambda tup: tup[0])
            self._identify_loops(self.other_edges, 2)
            other = [Part.Wire(Part.__sortEdges__(ow)) for ow in self.open_wires]
            loops.extend(other)

        return loops


# Eclass
