import FreeCAD
import Part
import math
import PathScripts.PathGeom as PathGeom
import Generator_Utilities as GenUtils

IS_MACRO = False  # Set to True to use as macro
CENTER_OF_ROTATION = FreeCAD.Vector(0.0, 0.0, 0.0)
IS_DEBUG = False


# Support functions
def _invertRotationsVector(rotVect):
    changed = 0

    def invert(d):
        if d > 0.0:
            return d - 180.0, True
            changed += 1
        elif d < 0.0:
            return d + 180.0, True
            changed += 1
        else:
            return 0.0, False

    x, xd = invert(rotVect.x)
    y, yd = invert(rotVect.y)
    # Check if normalAt for Z=1 needs inverted
    if not xd and not yd:
        x = 180.0
    return FreeCAD.Vector(x, y, 0.0)


def _normalizeDegrees(degree):
    if degree > 180.0:
        return degree - 360.0
    elif degree < -180.0:
        return degree + 360.0
    else:
        return degree


def getRotationsForObject(obj):
    if obj.Face == "None" and obj.Edge == "None":
        FreeCAD.Console.PrintWarning("Feature name is None.\n")
        return (
            FreeCAD.Vector(0.0, 0.0, 0.0),
            False,
        )

    # for m in obj.Proxy.job.Model.Group:
    #    m.Placement.Rotation.setYawPitchRoll(0.0, 0.0, 0.0)
    # obj.Proxy.job.Stock.Placement.Rotation.setYawPitchRoll(0.0, 0.0, 0.0)

    if obj.Edge != "None":
        rotVect, isPlanar = getRotationToLineByName(obj.Model, obj.Edge)
        if obj.InvertDirection:
            rotVect = _invertRotationsVector(rotVect)
    else:
        rotVect, isPlanar = getRotationToFaceByName(obj.Model, obj.Face)
    # print(f"getRotations() final rotations: {rotations}")
    return rotVect, isPlanar


def getRotationsByName(modelName, featureName, invert):
    if featureName == "None":
        FreeCAD.Console.PrintWarning("Feature name is None.\n")
        return [], False
    if featureName.startswith("Edge"):
        rotVect, isPlanar = getRotationToLineByName(modelName, featureName)
        if invert:
            rotVect = _invertRotationsVector(rotVect)
    else:
        rotVect, isPlanar = getRotationToFaceByName(modelName, featureName)
    # print(f"rotations to apply full: {rotations}")
    return rotVect, isPlanar


def rotateShapeWithList(shape, rotations):
    rotVects = {
        "X": FreeCAD.Vector(1.0, 0.0, 0.0),
        "Y": FreeCAD.Vector(0.0, 1.0, 0.0),
        "Z": FreeCAD.Vector(0.0, 0.0, 1.0),
    }
    rotated = shape.copy()
    for axis, angle in rotations:
        rotated.rotate(CENTER_OF_ROTATION, rotVects[axis], angle)
    return rotated


def rotateShapeWithVector(shape, rotVect):
    rotated = shape.copy()
    if not PathGeom.isRoughly(rotVect.x, 0.0):
        rotated.rotate(CENTER_OF_ROTATION, FreeCAD.Vector(1.0, 0.0, 0.0), rotVect.x)
    if not PathGeom.isRoughly(rotVect.y, 0.0):
        rotated.rotate(CENTER_OF_ROTATION, FreeCAD.Vector(0.0, 1.0, 0.0), rotVect.y)
    if not PathGeom.isRoughly(rotVect.z, 0.0):
        rotated.rotate(CENTER_OF_ROTATION, FreeCAD.Vector(0.0, 0.0, 1.0), rotVect.z)
    return rotated


def getRotationToLineByName(modelName, edgeName):
    """getRotationToLineByName(modelName, faceName)
    Return necessary degree rotations to align given line with Z=1, in vector form x, y, and z.
    Note: The rotation values may need to be inverted in order to orient model correctly."""
    # rotations = []
    rotVect = FreeCAD.Vector(0.0, 0.0, 0.0)
    cycles = 4
    malAligned = True

    model = FreeCAD.ActiveDocument.getObject(modelName)
    edge = model.Shape.getElement(edgeName)  # 1, 6, 4
    if edge.Curve.TypeId not in ["Part::GeomLine", "Part::GeomLineSegment"]:
        FreeCAD.Console.PrintWarning("Edge must be line.\n")
        return FreeCAD.Vector(0.0, 0.0, 0.0), False

    e = edge.copy()
    com = e.valueAt(e.FirstParameter)
    trans = com.add(FreeCAD.Vector(0.0, 0.0, 0.0)).multiply(-1.0)
    e.translate(trans)

    while malAligned:
        cycles -= 1
        norm = e.valueAt(e.LastParameter).sub(e.valueAt(e.FirstParameter)).normalize()
        # print(f"--NORM: {norm}")
        x0 = PathGeom.isRoughly(norm.x, 0.0)
        y0 = PathGeom.isRoughly(norm.y, 0.0)
        z1 = PathGeom.isRoughly(norm.z, 1.0)
        z_1 = PathGeom.isRoughly(norm.z, -1.0)
        if not (z1 or z_1):
            if not x0:
                ang = math.degrees(math.atan2(norm.x, norm.z))
                if ang < 0.0:
                    ang = 0.0 - ang
                elif ang > 0.0:
                    ang = 180.0 - ang
                e.rotate(CENTER_OF_ROTATION, FreeCAD.Vector(0.0, 1.0, 0.0), ang)
                # rotations.append(("Y", _normalizeDegrees(ang)))
                rotVect.y = _normalizeDegrees(ang)
                # print(f"  ang: {ang}")
                continue
            elif not y0:
                ang = math.degrees(math.atan2(norm.z, norm.y))
                ang = 90.0 - ang
                e.rotate(CENTER_OF_ROTATION, FreeCAD.Vector(1.0, 0.0, 0.0), ang)
                # rotations.append(("X", _normalizeDegrees(ang)))
                rotVect.x = _normalizeDegrees(ang)
                # print(f"  ang: {ang}")
                continue
        elif x0 and y0 and z_1:
            e.rotate(CENTER_OF_ROTATION, FreeCAD.Vector(1.0, 0.0, 0.0), 180.0)
            continue

        malAligned = False
        if cycles < 1:
            print("Break for cycles")
            break

    # norm = e.valueAt(e.LastParameter).sub(e.valueAt(e.FirstParameter)).normalize()
    # print(f"  {edgeName} norm: {norm}\n  rotations: {rotations}")
    # Part.show(e, edgeName)

    return (rotVect, True)


def getRotationToFaceByName(modelName, faceName):
    """getRotationToFaceByName(modelName, faceName)
    Return necessary degree rotations to align given face with Z=1, in vector form x, y, and z."""
    # rotations = []
    rotVect = FreeCAD.Vector(0.0, 0.0, 0.0)
    cycles = 0
    malAligned = True

    model = FreeCAD.ActiveDocument.getObject(modelName)
    face = model.Shape.getElement(faceName)
    f = face.copy()
    com = face.CenterOfMass
    trans = com.add(FreeCAD.Vector(0.0, 0.0, 0.0)).multiply(-1.0)
    f.translate(trans)

    while malAligned:
        cycles += 1
        norm = f.normalAt(0, 0)
        if IS_DEBUG:
            print(f"{faceName}: cycle {cycles},   norm {norm}")
        # print(f"--NORM: {norm}")
        x0 = PathGeom.isRoughly(norm.x, 0.0)
        y0 = PathGeom.isRoughly(norm.y, 0.0)
        z1 = PathGeom.isRoughly(norm.z, 1.0)
        z_1 = PathGeom.isRoughly(norm.z, -1.0)
        if not (z1 or z_1):
            if not x0:
                ang = math.degrees(math.atan2(norm.x, norm.z))
                if ang < 0.0:
                    ang = 0.0 - ang
                elif ang > 0.0:
                    ang = 180.0 - ang
                # ang = -1.0 * ang
                f.rotate(CENTER_OF_ROTATION, FreeCAD.Vector(0.0, 1.0, 0.0), ang)
                # rotations.append(("Y", _normalizeDegrees(ang)))
                rotVect.y = _normalizeDegrees(ang)
                # print(f"  ang: {ang}")
                continue
            elif not y0:
                ang = math.degrees(math.atan2(norm.z, norm.y))
                ang = 90.0 - ang
                f.rotate(CENTER_OF_ROTATION, FreeCAD.Vector(1.0, 0.0, 0.0), ang)
                # rotations.append(("X", _normalizeDegrees(ang)))
                rotVect.x = _normalizeDegrees(ang)
                # print(f"  ang: {ang}")
                continue
        elif x0 and y0 and z_1:
            f.rotate(CENTER_OF_ROTATION, FreeCAD.Vector(1.0, 0.0, 0.0), 180.0)
            continue

        malAligned = False
        if cycles > 4:
            break

    # norm = f.normalAt(0, 0)
    # print(f"  {faceName} norm: {norm}\n  rotations: {rotations}")
    # print(f"  center of mass: {com}")
    # Part.show(f, faceName)

    isFlat = PathGeom.isRoughly(f.BoundBox.ZLength, 0.0)

    # Verify rotation data
    shp = model.Shape.copy()
    # rotated = rotateShapeWithList(shp, rotations)
    rotated = rotateShapeWithVector(shp, rotVect)
    rf = rotated.getElement(faceName)
    extPos = rf.extrude(FreeCAD.Vector(0.0, 0.0, 5.0))
    extNeg = rf.extrude(FreeCAD.Vector(0.0, 0.0, -5.0))
    if rotated.common(extPos).Area < rotated.common(extNeg).Area:
        return rotVect, isFlat

    # print(f"Auto-inverting '{faceName}'")
    return _invertRotationsVector(rotVect), isFlat


def getRotationToFaceByShape(modelShape, face):
    modelHash = modelShape.hashCode()
    modelName = ""
    for o in FreeCAD.ActiveDocument.Objects:
        if hasattr(o, "Shape") and hasattr(o.Shape, "hashCode"):
            if o.Shape.hashCode() == modelHash:
                modelName = o.Name
                break
    if not modelName:
        FreeCAD.Console.PrintError("No model name found.\n")
        return None

    faceHash = face.hashCode()
    faceName = ""
    for i in range(len(modelShape.Faces)):
        f = modelShape.Faces[i]
        if f.hashCode() == faceHash:
            rf = f
            faceName = f"Face{i+1}"
            break
    if not faceName:
        FreeCAD.Console.PrintError("No face name found.\n")
        return None

    return getRotationToFaceByName(modelName, faceName)


# Auxillary functions


def _executeAsMacro():
    base = []
    group = FreeCAD.ActiveDocument.addObject("App::DocumentObjectGroup", "Group")
    selection = FreeCADGui.Selection.getSelectionEx()
    # process user selection
    for sel in selection:
        # print(f"Object.Name: {sel.Object.Name}")
        base.append((sel.Object.Name, [n for n in sel.SubElementNames]))

    for baseName, featList in base:
        baseShape = FreeCAD.ActiveDocument.getObject(baseName).Shape
        for feat in featList:
            rotVect, isPlanar = getRotationsByName(baseName, feat, False)
            rotated = rotateShapeWithVector(baseShape, rotVect)
            if IS_DEBUG:
                print(f"{feat} rotation vector is {rotVect}")
            f = Part.show(rotated.getElement(feat), feat)
            group.addObject(f)


def test01():
    rotationVectors = [
        FreeCAD.Vector(0.0, 90, 0),
        FreeCAD.Vector(45, -45, 0),
        FreeCAD.Vector(-100, 20, 0),
        FreeCAD.Vector(0, 0, 0),
    ]
    for v in rotationVectors:
        inverted = _invertRotationsVector(v)
        print(f"{v}\n{inverted}\n")


# Primary function

# print("Imported Macro_AlignToFeature")


if IS_MACRO and FreeCAD.GuiUp:
    import FreeCADGui

    _executeAsMacro()
    # CENTER_OF_ROTATION = FreeCAD.Vector(100, 50, 0)
    # _executeAsMacro()
    # test01()
    FreeCAD.ActiveDocument.recompute()
