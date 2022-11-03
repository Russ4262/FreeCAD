import FreeCAD
import Part
import Path.Geom as PathGeom
import PathScripts.PathUtils as PathUtils

IS_MACRO = False
LINEARDEFLECTION = FreeCAD.Units.Quantity("0.0001 mm")
moveCnt = 0


def _toolShapeCenter(toolShape):
    tBB = toolShape.BoundBox
    return FreeCAD.Vector(
        round(tBB.Center.x, 7), round(tBB.Center.y, 7), round(tBB.ZMin, 7)
    )


def _bspline(__, sampleInterval, cnt, edgeLen):
    # print(".. _bspline")
    return (sampleInterval * cnt) / edgeLen


def _arc(e, sampleInterval, cnt, edgeLen):
    # print(".. _arc")
    rate = (sampleInterval * cnt) / edgeLen
    return e.FirstParameter + rate * (e.LastParameter - e.FirstParameter)


def _ellipse(e, sampleInterval, cnt, edgeLen):
    # print(".. _ellipse")
    rate = (sampleInterval * cnt) / edgeLen
    return e.FirstParameter + rate * (e.LastParameter - e.FirstParameter)


def _line(e, sampleInterval, cnt, __):
    # print(".. _line")
    return e.FirstParameter + (sampleInterval * cnt)


def _getValueAtArgument(typeId):
    if typeId == "Part::GeomBSplineCurve":
        return _bspline
    elif typeId == "Part::GeomCircle":
        return _arc
    elif typeId == "Part::GeomLine":
        return _line
    elif typeId == "Part::GeomEllipse":
        return _ellipse

    print(f"_followEdge() e.Curve.TypeId, {typeId}, is not available.")
    return None


def _dropShapeToFace(toolShape, face, location, destination, startDepth, dropTolerance):
    drops = 0
    deltaX = destination.x - location.x
    deltaY = destination.y - location.y
    deltaZ = startDepth - location.z
    trans = FreeCAD.Vector(deltaX, deltaY, deltaZ)
    toolShape.translate(trans)
    dist = toolShape.distToShape(face)[0]
    while dist > dropTolerance:
        drops += 1
        trans = FreeCAD.Vector(0.0, 0.0, dist * -0.8)
        toolShape.translate(trans)
        dist = toolShape.distToShape(face)[0]
        if drops > 12:
            print(f"_dropShapeToFace() Breaking at dist = {dist} mm")
            break
    return toolShape, _toolShapeCenter(toolShape), drops


def _followEdge(
    e, toolShape, face, startDepth, sampleInterval, dropTolerance, lastEdge
):
    global moveCnt

    points = []
    tool = toolShape
    eLen = e.Length
    edgeLen = e.Length
    dropCnt = 0
    moveCnt += 1
    loopCnt = 0

    typeId = e.Curve.TypeId
    valueFunction = _getValueAtArgument(typeId)

    location = _toolShapeCenter(tool)
    # follow edge
    while eLen > sampleInterval:
        moveCnt += 1
        # move to next point along edge
        valueAtParam = valueFunction(e, sampleInterval, loopCnt, edgeLen)
        nxt = e.valueAt(valueAtParam)
        tool, center, drpCnt = _dropShapeToFace(
            tool, face, location, nxt, startDepth, dropTolerance
        )
        dropCnt += drpCnt
        if center.z < nxt.z:
            # print("Vertically adjusting tool")
            center.z = nxt.z
        points.append(center)
        location = center
        eLen -= sampleInterval
        loopCnt += 1

    if loopCnt == 0 or lastEdge:
        # experimental section for edges of length less than sampleInterval
        nxt = e.valueAt(e.LastParameter)
        tool, center, drpCnt = _dropShapeToFace(
            tool, face, location, nxt, startDepth, dropTolerance
        )
        dropCnt += drpCnt
        if center.z < nxt.z:
            # print("Vertically adjusting tool")
            center.z = nxt.z
        points.append(FreeCAD.Vector(center.x, center.y, center.z))

    return points, dropCnt


def _dropCutEdges(
    edges, toolShape, faceShape, startDepth, sampleInterval, dropTolerance
):
    wirePoints = []
    dropCnt = 0
    distance = 0.0
    for e in edges[:-1]:
        if distance + e.Length > sampleInterval:
            distance = 0.0
            points, drpCnt = _followEdge(
                e,
                toolShape,
                faceShape,
                startDepth,
                sampleInterval,
                dropTolerance,
                False,
            )
            wirePoints.extend(points)
            dropCnt += drpCnt
        else:
            distance += e.Length

    # Process last edge
    e = edges[-1]
    points, drpCnt = _followEdge(
        e, toolShape, faceShape, startDepth, sampleInterval, dropTolerance, True
    )
    wirePoints.extend(points)
    dropCnt += drpCnt

    return wirePoints, dropCnt


def getToolShape(toolController):
    """getToolShape(toolController) Return tool shape with shank removed."""
    full = toolController.Tool.Shape.copy()
    vertEdges = [
        e
        for e in full.Edges
        if len(e.Vertexes) == 2
        and PathGeom.isRoughly(e.Vertexes[0].X, e.Vertexes[1].X)
        and PathGeom.isRoughly(e.Vertexes[0].Y, e.Vertexes[1].Y)
    ]
    vertEdges.sort(key=lambda e: e.BoundBox.ZMax)
    topVertEdge = vertEdges.pop()
    top = full.BoundBox.ZMax + 2.0
    face = PathGeom.makeBoundBoxFace(full.BoundBox, 5.0, top)
    dist = -1.0 * (top - topVertEdge.BoundBox.ZMin)
    faceExt = face.extrude(FreeCAD.Vector(0.0, 0.0, dist))
    # Part.show(full, "Full")
    # Part.show(faceExt, "FaceExt")
    return full.cut(faceExt)


# Public functions
def dropCutWires(
    pathWires,
    faceShape,
    toolShape,
    sampleInterval,
    dropTolerance,
    optimizeLines=False,
):
    print(f"dropCutWires() dropTolerance: {dropTolerance}")
    pointsLists = []
    dropCnt = 0
    startDepth = faceShape.BoundBox.ZMax + 1.0
    wCnt = 0

    for w in pathWires:
        wCnt += 1
        # Must create new toolShape object for each wire, otherwise FreeCAD crash will occur
        toolShp = toolShape.copy()
        if w.Length > sampleInterval:
            # Cut regular, longer wires longer than sample interval
            (wirePoints, drpCnt) = _dropCutEdges(
                w.Edges, toolShp, faceShape, startDepth, sampleInterval, dropTolerance
            )
        else:
            # Make sure wires less than sample interval are cut
            (wirePoints, drpCnt) = _dropCutEdges(
                w.Edges,
                toolShp,
                faceShape,
                startDepth,
                w.Length * 0.90,
                dropTolerance,
            )
        dropCnt += drpCnt
        # Optimize points list
        if len(wirePoints) > 0:
            if optimizeLines:
                pointsLists.append(
                    PathUtils.simplify3dLine(wirePoints, LINEARDEFLECTION.Value)
                )
            else:
                pointsLists.append(wirePoints)
        else:
            print(f"no drop cut wire points from wire {wCnt}")

    # Part.show(toolShape, "ToolShape")
    print(f"Dropcut count: {dropCnt}")

    return pointsLists


def getProjectedGeometry(face, pathGeomList):
    """getProjectedGeometry(face, pathGeomList) Return list of wires resulting from projection onto face"""
    # Project 2D wires onto 3D face(s)
    faceCopy = face.copy()
    # print(f"   paths: {paths}")
    compPathGeom = Part.makeCompound(pathGeomList)
    # Part.show(compPathGeom, "PathGeom")  #  path projected to original face
    faceCopy.translate(
        FreeCAD.Vector(
            0.0, 0.0, (compPathGeom.BoundBox.ZMin - 10.0) - faceCopy.BoundBox.ZMin
        )
    )
    transDiff = face.BoundBox.ZMin - faceCopy.BoundBox.ZMin
    projWires = []
    for w in pathGeomList:
        p = faceCopy.makeParallelProjection(w, FreeCAD.Vector(0.0, 0.0, -1.0))
        p.translate(FreeCAD.Vector(0.0, 0.0, transDiff))
        wire = Part.Wire(Part.__sortEdges__(p.Edges))  # sort edges properly
        projWires.append(wire)

    return projWires


def pointsToLines(pointsLists, depthOffset=0.0):
    wires = []
    if depthOffset == 0.0:
        for pnts in pointsLists:
            if len(pnts) > 1:
                lines = []
                p0 = pnts[0]
                for p in pnts[1:]:
                    if p0.sub(p).Length > 0.000001:
                        lines.append(Part.makeLine(p0, p))
                        p0 = p
                if len(lines) > 0:
                    wires.append(Part.Wire(lines))
    else:
        trans = FreeCAD.Vector(0.0, 0.0, depthOffset)
        for pnts in pointsLists:
            if len(pnts) > 1:
                lines = []
                p0 = pnts[0]
                for p in pnts[1:]:
                    if p0.sub(p).Length > 0.000001:
                        line = Part.makeLine(p0, p)
                        line.translate(trans)
                        lines.append(line)
                        p0 = p
                if len(lines) > 0:
                    wires.append(Part.Wire(lines))

    return wires


def dropCutWire(
    wire,
    fusedFace,
    toolShape,
    depthOffset,
    sampleInterval,
    dropTolerance,
    optimizeLines=False,
):
    projWires = getProjectedGeometry(fusedFace, [wire])
    # Apply drop cut to 3D projected wires to get point set
    pointsLists = dropCutWires(
        projWires,
        fusedFace,
        toolShape,
        sampleInterval,
        dropTolerance,
        optimizeLines,
    )

    # return pointsToLines(pointsLists, depthOffset)
    lineSegs = pointsToLines(pointsLists, depthOffset)
    return Part.Wire(lineSegs)


# Macro functions
def _getUserInput(Gui_Input):
    # Get cut pattern settings from user
    guiInput = Gui_Input.GuiInput()
    guiInput.setWindowTitle("Dropcut Wire Settings")
    do = guiInput.addDoubleSpinBox("Depth Offset", 0.0)
    do.setMinimum(-99999999)
    do.setMaximum(99999999)
    si = guiInput.addDoubleSpinBox("Sample Interval (0.1 to 10)", 1.0)
    si.setMinimum(0.1)
    si.setMaximum(10.0)
    dt = guiInput.addDoubleSpinBox("Dropcut Tolerance (0.001 to 10)", 0.1)
    dt.setMinimum(0.001)
    dt.setMaximum(10.0)
    guiInput.addCheckBox("Optimize paths")
    return guiInput.execute()


def executeAsMacro():
    import Macros.Generator_Utilities as GenUtils

    job, tc = GenUtils.getJobAndToolController()
    if job is None:
        print("No Job returned.")
        return

    selectedFaces, selectedWires = GenUtils.getFacesFromSelection()
    if len(selectedFaces) == 0:
        return None

    values = _getUserInput(GenUtils.Gui_Input)
    if values is None:
        return
    (depthOffset, sampleInterval, dropTolerance, optimizeLines) = values

    # combine faces into horizontal regions
    region, fusedFace = GenUtils.combineFacesToRegion(
        selectedFaces, saveOldHoles=True, saveNewHoles=True
    )

    toolShape = GenUtils.getToolShape(tc)

    for w in selectedWires:
        dcWire = dropCutWire(
            w,
            fusedFace,
            toolShape,
            depthOffset,
            sampleInterval,
            dropTolerance,
            optimizeLines,
        )
        Part.show(dcWire, "Wire")


print("Imported Generator_DropCut")

if IS_MACRO:
    executeAsMacro()
