import FreeCAD
import Part
import DraftGeomUtils
import Path.Geom as PathGeom
import generators.Utilities as GenUtils

IS_MACRO = False  # False  # Set to True to use as macro
SET_SELECTION = False
SELECTIONS = [
    (
        "Body",
        [
            "Face16",
            "Face18",
            "Face17",
            "Face14",
            "Face15",
            "Face7",
            "Face3",
            "Face9",
        ],
    )
]
SELECTIONS2 = [
    (
        "Body",
        [
            "Face8",
            "Face39",
        ],
    )
]
SELECTIONS3 = [
    (
        "Body",
        [
            "Face4",
            "Face8",
            "Face6",
            "Face26",
        ],
    )
]


# Support functions
def _separateFaceWires(faces):
    outerWires = []
    innerWires = []
    for face in faces:
        # Process outer wire
        outerWires.append(face.Wires[0].copy())
        # process inner wires
        for w in face.Wires[1:]:
            innerWires.append(w.copy())
    return outerWires, innerWires


def _xyz_to_text(x, y, z):
    return "x{}_y{}_z{}".format(x, y, z)


def _pointToText(p, precision=6):
    factor = 10 ** precision
    v0x = int(round(p.x, precision) * factor)
    v0y = int(round(p.y, precision) * factor)
    v0z = int(round(p.z, precision) * factor)
    return _xyz_to_text(v0x, v0y, v0z)


def _getXYMinVertex(edge):
    v0 = edge.Vertexes[0].Point

    if len(edge.Vertexes) == 1:
        return v0, None

    v1 = edge.Vertexes[1].Point

    if v0.x < v1.x:
        # v0 is min
        return v0, v1
    elif v0.x > v1.x:
        return v1, v0
    else:
        if v0.y <= v1.y:
            # v0 is min
            return v0, v1
        else:
            return v1, v0


def _flattenWires(wires):
    flattened = []
    for w in wires:
        if w.isClosed():
            wBB = w.BoundBox
            if PathGeom.isRoughly(wBB.ZLength, 0.0):
                flat = Part.Wire([e.copy() for e in w.Edges])
                flat.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - flat.BoundBox.ZMin))
                flattened.append(flat)
            else:
                face = PathGeom.makeBoundBoxFace(wBB, 2.0, wBB.ZMin - 2.0)
                flat = face.makeParallelProjection(w, FreeCAD.Vector(0.0, 0.0, 1.0))
                flat.translate(FreeCAD.Vector(0.0, 0.0, 0.0 - flat.BoundBox.ZMin))
                flattened.append(Part.Wire(flat.Edges))
    return flattened


def _makeAdjacentWire_Tups(outerWires):
    # print("_makeAdjacentWire_Tups()")
    allEdgesTups = []
    edgeCount = 0
    # print(f"processing {len(outerWires)} outer wires")
    for wi in range(len(outerWires)):
        w = outerWires[wi]
        # print(f"  {len(w.Edges)} edges")
        edgeCount += len(w.Edges)
        for ei in range(len(w.Edges)):
            e = w.Edges[ei]
            try:
                midpntVert = e.valueAt(e.getParameterByLength(e.Length / 2.0))
                midpntVertTxt = _pointToText(midpntVert, 4)
                minVert, maxVert = _getXYMinVertex(e)
                minVertTxt = _pointToText(minVert, 4)
                if maxVert:
                    maxVertTxt = _pointToText(maxVert, 4)
                else:
                    maxVertTxt = ""
                    # print("___________ No max vertex ___________")
                allEdgesTups.append(
                    (minVertTxt + midpntVertTxt, minVertTxt, maxVertTxt, e)
                )
            except:
                # Part.show(e.copy(), "error_edge")
                print("_makeAdjacentWire_Tups() edge to string error")

    allEdgesTups.sort(key=lambda tup: tup[0])

    # print(f"Raw edge count: {edgeCount}")

    return allEdgesTups


def _removeDuplicateEdges(allEdgesTups):
    # print("_removeDuplicateEdges()")
    # Remove shared edges
    uniqueEdgesTups = [allEdgesTups[0]]
    for t in allEdgesTups[1:]:
        if uniqueEdgesTups:
            if uniqueEdgesTups[-1][0] != t[0]:
                # unique edge
                uniqueEdgesTups.append(t)
            else:
                # remove last edge because it is same as current
                # print("popping last edge")
                uniqueEdgesTups.pop()
                # Part.show(last[3], "LastEdge")
        else:
            uniqueEdgesTups.append(t)

    # print(f"uniqueEdgesTups count: {len(uniqueEdgesTups)}")

    return [(b, c, d) for (a, b, c, d) in uniqueEdgesTups]


def _mergeAdjacentWires(outerWires):
    # print("_mergeAdjacentWires()")
    allEdgesTups = _makeAdjacentWire_Tups(outerWires)
    uniqueEdgesTups = _removeDuplicateEdges(allEdgesTups)
    # Convert unique edges to wires
    wires = DraftGeomUtils.findWires([e for (__, __, e) in uniqueEdgesTups])
    return wires


def _consolidateAreas(closedWires, saveHoles=True):
    wireCnt = len(closedWires)
    # print(f"_consolidateAreas(closedWires={wireCnt})")

    if wireCnt == 1:
        return [Part.Face(closedWires[0])], []

    # Create face data tups
    faceTups = []
    for i in range(wireCnt):
        w = closedWires[i]
        f = Part.Face(w)
        faceTups.append((i, f, f.Area))

    # Sort large to small by face area
    faceTups.sort(key=lambda tup: tup[2], reverse=True)

    result = []
    cnt = len(faceTups)
    while cnt > 0:
        small = faceTups.pop()
        cnt -= 1
        if cnt:
            for fti in range(len(faceTups)):
                big = faceTups[fti]
                cut = big[1].cut(small[1])
                if PathGeom.isRoughly(cut.Area, big[2]):
                    # small not inside big
                    result.append(small)
                else:
                    # replace big face with cut version
                    # print("found internal loop wire")
                    if saveHoles:
                        faceTups[fti] = (big[0], cut, cut.Area)
                    break
        else:
            result.append(small)
    # Ewhile
    faces = [t[1] for t in result]
    outerFaces = [Part.Face(f.Wires[0]) for f in faces]
    innerFaces = []
    for f in faces:
        for w in f.Wires[1:]:
            innerFaces.append(Part.Face(w))

    return outerFaces, innerFaces


def _fuseFlatWireAreas(flatWires):
    openEdges = []
    closedWires = []

    # separate edges from open wires
    for w in flatWires:
        if w.isClosed():
            closedWires.append(w)
        else:
            openEdges.extend(w.Edges)
    # Attempt to make closed wires from all open edges
    if len(openEdges) > 1:
        closedWires.extend(
            [
                w
                for w in [Part.Wire(edgs) for edgs in Part.sortEdges(openEdges)]
                if w.isClosed()
            ]
        )

    # Process closed wires
    # merge adjacent regions using fuse() method to connect closed wires at common edges
    if len(closedWires) > 1:
        face = Part.Face(closedWires.pop())
        for w in closedWires:
            f = face.fuse(Part.Face(w)).removeSplitter()
            face = f
        return face.Wires
    else:
        return closedWires


def _makeWireText(w):
    f = Part.Face(w)
    centOfMass = _pointToText(f.CenterOfMass)
    wireLength = "_" + str(int(w.Length * 10000))
    area = "_" + str(int(f.Area * 100))
    return centOfMass + wireLength + area


def _removeSelectedInternals(outerWires, InnerWires):
    """_removeSelectedInternals(outerWires, InnerWires)
    Check if any inners are identical to selected outers, and remove both if true."""
    outers = []
    inners = []
    data = []

    # Create wire detail tuples for outer and inner wires
    for i in range(len(outerWires)):
        w = outerWires[i]
        data.append((_makeWireText(w), w, 0))
    for i in range(len(InnerWires)):
        w = InnerWires[i]
        data.append((_makeWireText(w), w, 1))
    data.sort(key=lambda tup: tup[0])

    # Identify unique wire detail tuples
    unique = [data[0]]
    for d in data[1:]:
        if len(unique) == 0:
            # re-seed unique if empty list
            unique.append(d)
        else:
            if d[0] == unique[-1][0]:
                # remove selected duplicate inner and outer wires
                unique.pop()
            else:
                # Add unique outer and inner tuples
                unique.append(d)

    # Separate wires from tuples into outer and inner
    for txt, w, typ in unique:
        if typ == 0:
            outers.append(w)
        else:
            inners.append(w)

    return outers, inners


def _executeAsMacro():
    # Get hole settings from user
    guiInput = GenUtils.Gui_Input.GuiInput()
    guiInput.setWindowTitle("Combine Region Details")
    seh = guiInput.addCheckBox("Save Existing Holes")
    seh.setChecked(True)
    shfm = guiInput.addCheckBox("Save Holes From Merge")
    shfm.setChecked(True)
    values = guiInput.execute()
    if values is None:
        return None, None

    (saveExisting, saveMerged) = values
    # return tuple (region, selectedFace)
    # return GenUtils.combineSelectedFaces(saveExisting, saveMerged)
    selectedFaces, __ = GenUtils.getFacesFromSelection()
    if len(selectedFaces) == 0:
        return None

    # combine faces into horizontal regions
    region = combineRegions(selectedFaces, saveExisting, saveMerged)

    # fuse faces together for projection of path geometry
    fusedFace = selectedFaces[0]
    if len(selectedFaces) > 1:
        fusedFace = selectedFaces[0]
        for f in selectedFaces[1:]:
            fused = fusedFace.fuse(f)
            fusedFace = fused

    return region, fusedFace


# Primary function
def identifyRegions(faceShapes, saveExistingHoles=True, saveMergedHoles=True):
    """identifyRegions(faceShapes, saveExistingHoles=True, saveMergedHoles=True)
    Returns (outer, inner) tuple containing outer faces and inner faces.  A manual cut is
    required to create the complete set of combined faces, or use module method, `combineRegions()`.
    Arguments:
        faceShapes:  List of face shapes to merge
        saveExistingHoles:  Set True to preserve existing holes in selected face shapes
        saveMergedHoles:  Set True to save holes created by merger of selected face shapes
    """
    # print("identifyRegions()")
    innerFaces = None
    internalFaces = []

    outerWiresRaw, innerWiresRaw = _separateFaceWires(faceShapes)
    if len(outerWiresRaw) == 0:
        print("No outerWires")
        return [], []

    ########################################################################################

    # Flattend all outer wires in case some are 3D
    flatOuterWiresRaw = _flattenWires(outerWiresRaw)

    if innerWiresRaw:
        # Flatten inner wires and remove duplicates of outer selections
        # print(f"Found inner {len(innerWiresRaw)} wires")
        flatInnerWiresRaw = _flattenWires(innerWiresRaw)
        flatOuterWires, rawInnerWires = _removeSelectedInternals(
            flatOuterWiresRaw, flatInnerWiresRaw
        )
        if saveExistingHoles and rawInnerWires:
            internalFaces.extend([Part.Face(w) for w in rawInnerWires])
    else:
        flatOuterWires = flatOuterWiresRaw

    ########################################################################################

    fusedFlatOuterWires = _fuseFlatWireAreas(flatOuterWires)
    if len(fusedFlatOuterWires) == 0:
        print("No fused flat outer wires")
        Part.show(Part.makeCompound(flatOuterWires), "FlatOuterWires")
        return [], []

    ########################################################################################

    # Remove duplicate edges
    mergedFlatOuterWires_1 = _mergeAdjacentWires(fusedFlatOuterWires)

    ########################################################################################

    flattenedWires, inFaces1 = _consolidateAreas(
        mergedFlatOuterWires_1, saveHoles=saveMergedHoles
    )
    if inFaces1:
        # print(f"Found inner loop wire(s)")
        internalFaces.extend(inFaces1)

    ########################################################################################

    mergedWires_C = _fuseFlatWireAreas(flattenedWires)

    ########################################################################################

    # Remove duplicate edges from fused regions
    merged = _mergeAdjacentWires(mergedWires_C)

    ########################################################################################

    outFaces, inFaces = _consolidateAreas(merged, saveHoles=saveMergedHoles)
    outerFaces = Part.makeCompound(outFaces)
    # print(f"Found {len(inFaces)} inner loop wire(s)")
    internalFaces.extend(inFaces)

    if saveExistingHoles and internalFaces:
        innerFaces = Part.makeCompound(internalFaces)
        # Part.show(innerFaces, "innerFaces")

    return outerFaces, innerFaces


def combineRegions(faces, saveExistingHoles=True, saveMergedHoles=True):
    if not faces:
        return None

    outerFaces, innerFaces = identifyRegions(faces, saveExistingHoles, saveMergedHoles)

    # perform manual cut to make complete set of combined face regions
    if outerFaces:
        if innerFaces:
            if len(innerFaces.Faces) == 1:
                cut = outerFaces.cut(innerFaces)
            else:
                cut = outerFaces.cut(innerFaces.Faces[0])
                for f in innerFaces.Faces[1:]:
                    new = cut.cut(f)
                    cut = new
        else:
            cut = outerFaces
        return cut

    return None


print("Imported Macro_CombineRegions")


if IS_MACRO and FreeCAD.GuiUp:
    region, selectedFaces = _executeAsMacro()
    if region is not None:
        r = Part.show(region, "Face")
        r.Label = "Combined Region"
    else:
        print("No combine region returned.")
    FreeCAD.ActiveDocument.recompute()
