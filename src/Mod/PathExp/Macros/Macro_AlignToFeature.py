import FreeCAD
import Part
import math
import PathScripts.PathGeom as PathGeom

# import Generator_Utilities as GenUtils

IS_MACRO = False  # Set to True to use as macro
IS_DEBUG = False
CENTER_OF_ROTATION = FreeCAD.Vector(0.0, 0.0, 0.0)
AVAILABLE_AXES = {"X": True, "Y": True, "Z": False}
AXES_OF_ROTATION = {
    "X": FreeCAD.Vector(1.0, 0.0, 0.0),
    "Y": FreeCAD.Vector(0.0, 1.0, 0.0),
    "Z": FreeCAD.Vector(0.0, 0.0, 1.0),
}


# Support functions
def _getFirstAxisAvailable():
    for a in AVAILABLE_AXES.keys():
        if AVAILABLE_AXES[a]:
            return a


def _invertRotationsVector(rotVect):
    def invert(d):
        if d > 0.0:
            return d - 180.0, True
        elif d < 0.0:
            return d + 180.0, True
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


def getRotationsForObject_orig(obj):
    print("getRotationsForObject()")
    if obj.Face == "None" and obj.Edge == "None":
        FreeCAD.Console.PrintWarning("Feature name is None.\n")
        return (
            FreeCAD.Vector(0.0, 0.0, 0.0),
            False,
        )

    if obj.Edge != "None":
        rotations, isPlanar = getRotationToLineByName(
            obj.Model, obj.Edge, obj.InvertDirection
        )
    else:
        rotations, isPlanar = getRotationToFace(
            FreeCAD.ActiveDocument.getObject(obj.Model.Name), obj.Face
        )
    # print(f"getRotations() final rotations: {rotations}")
    return rotations, isPlanar


def getRotationsForObject(obj):
    print("getRotationsForObject()")
    if obj.Face == "None" and obj.Edge == "None":
        FreeCAD.Console.PrintWarning("Feature name is None.\n")
        return ([], False)

    if obj.Edge != "None":
        rotations, isPlanar = getRotationToLineByName(
            obj.Model, obj.Edge, obj.InvertDirection
        )
    else:
        rotations, isPlanar = getRotationToFace(
            FreeCAD.ActiveDocument.getObject(obj.Model), obj.Face
        )
    # print(f"getRotations() final rotations: {rotations}")
    return rotations, isPlanar


def getRotationsByName(modelName, featureName, invert):
    print("getRotationsByName()")
    if featureName == "None":
        FreeCAD.Console.PrintWarning("Feature name is None.\n")
        return [], False
    if featureName.startswith("Edge"):
        rotations, isPlanar = getRotationToLineByName(modelName, featureName, invert)
    else:
        rotations, isPlanar = getRotationToFace(
            FreeCAD.ActiveDocument.getObject(modelName), featureName
        )
    # print(f"rotations to apply full: {rotations}")
    return rotations, isPlanar


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


def getRotationToLineByName(modelName, edgeName, isInverted=False):
    """getRotationToLineByName(modelName, faceName)
    Return necessary degree rotations to align given line with Z=1, in vector form x, y, and z.
    Note: The rotation values may need to be inverted in order to orient model correctly."""
    rotations = []
    # rotVect = FreeCAD.Vector(0.0, 0.0, 0.0)
    cycles = 4
    malAligned = True

    model = FreeCAD.ActiveDocument.getObject(modelName)
    edge = model.Shape.getElement(edgeName)  # 1, 6, 4
    if edge.Curve.TypeId not in ["Part::GeomLine", "Part::GeomLineSegment"]:
        FreeCAD.Console.PrintWarning("Edge must be line.\n")
        return FreeCAD.Vector(0.0, 0.0, 0.0), False

    e = edge.copy()
    if isInverted:
        com = e.valueAt(e.LastParameter)
    else:
        com = e.valueAt(e.FirstParameter)
    trans = com.add(FreeCAD.Vector(0.0, 0.0, 0.0)).multiply(-1.0)
    e.translate(trans)

    while malAligned:
        cycles -= 1
        if isInverted:
            norm = (
                e.valueAt(e.FirstParameter).sub(e.valueAt(e.LastParameter)).normalize()
            )
        else:
            norm = (
                e.valueAt(e.LastParameter).sub(e.valueAt(e.FirstParameter)).normalize()
            )
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
                rotations.append(("Y", _normalizeDegrees(ang)))
                # rotVect.y = _normalizeDegrees(ang)
                # print(f"  ang: {ang}")
                continue
            elif not y0:
                ang = math.degrees(math.atan2(norm.z, norm.y))
                ang = 90.0 - ang
                e.rotate(CENTER_OF_ROTATION, FreeCAD.Vector(1.0, 0.0, 0.0), ang)
                rotations.append(("X", _normalizeDegrees(ang)))
                # rotVect.x = _normalizeDegrees(ang)
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

    return (rotations, True)


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


def _getTwoSolutions(face, norm):
    yRotAng1 = -90.0
    xRotAng1 = math.degrees(math.atan2(norm.y, norm.x))
    sltn1 = FreeCAD.Vector(xRotAng1, yRotAng1, 0.0)
    yRotAng2 = math.degrees(math.atan2(norm.x, norm.y))
    xRotAng2 = -90.0
    sltn2 = FreeCAD.Vector(xRotAng2, yRotAng2, 0.0)
    return (sltn1, sltn2)


def _calculateRotationsToFace(face):
    """_calculateRotationsToFace(face)
    Return necessary degree rotations to align given face with Z=1, in vector form x, y, and z."""
    print("Macro_AlignToFeature._calculateRotationsToFace()")

    rotations = []  # Preferred because rotation order is important
    cycles = 0
    malAligned = True
    com = face.CenterOfMass

    faa = _getFirstAxisAvailable()
    if faa not in ["X", "Y"]:
        print("--ERROR: X and Y not available for rotation where norm.z = 0.0")
        return rotations

    f = face.copy()
    trans = com.add(FreeCAD.Vector(0.0, 0.0, 0.0)).multiply(-1.0)
    f.translate(trans)

    while malAligned:
        cycles += 1
        u, v = f.ParameterRange[:2]
        norm = f.normalAt(u, v)
        if IS_DEBUG:
            print(f"cycle {cycles},   norm {norm}")
        # print(f"--NORM: {norm}")
        x0 = PathGeom.isRoughly(norm.x, 0.0)
        x1 = PathGeom.isRoughly(norm.x, 1.0)
        x_1 = PathGeom.isRoughly(norm.x, -1.0)
        y0 = PathGeom.isRoughly(norm.y, 0.0)
        y1 = PathGeom.isRoughly(norm.y, 1.0)
        y_1 = PathGeom.isRoughly(norm.y, -1.0)
        z0 = PathGeom.isRoughly(norm.z, 0.0)
        z1 = PathGeom.isRoughly(norm.z, 1.0)
        z_1 = PathGeom.isRoughly(norm.z, -1.0)
        if z0:
            # Vertical face
            if x1 or x_1:
                # Facing along X axis
                if AVAILABLE_AXES["Y"]:
                    rotAng = -90.0
                    if x_1:
                        rotAng = 90.0
                    f.rotate(CENTER_OF_ROTATION, AXES_OF_ROTATION["Y"], rotAng)
                    print("Rotating for Z=0 around Y axis.")
                    rotations.append(("Y", rotAng))
                    return rotations
            elif y1 or y_1:
                # Facing along Y axis
                if AVAILABLE_AXES["X"]:
                    rotAng = 90.0
                    if y_1:
                        rotAng = -90.0
                    f.rotate(CENTER_OF_ROTATION, AXES_OF_ROTATION["X"], rotAng)
                    print("Rotating for Z=0 around X axis.")
                    rotations.append(("X", rotAng))
                    return rotations
            else:
                aSol, bSol = _getTwoSolutions(face, norm)
                f.rotate(CENTER_OF_ROTATION, FreeCAD.Vector(0.0, 1.0, 0.0), aSol.y)
                f.rotate(CENTER_OF_ROTATION, FreeCAD.Vector(1.0, 0.0, 0.0), aSol.x)
                print(f"Dual rotation for Z=0. Using solution A. {aSol}")
                rotations.append(("Y", aSol.y))
                rotations.append(("X", aSol.x))
                return rotations
        elif z_1 and x0 and y0:
            if AVAILABLE_AXES["Y"]:
                rotAng = 180.0
                f.rotate(CENTER_OF_ROTATION, AXES_OF_ROTATION["Y"], rotAng)
                print("Flipping object for Z=-1.0 around Y axis.")
                rotations.append(("Y", rotAng))
                return rotations
            elif AVAILABLE_AXES["X"]:
                rotAng = 180.0
                f.rotate(CENTER_OF_ROTATION, AXES_OF_ROTATION["X"], rotAng)
                print("Flipping object for Z=-1.0 around X axis.")
                rotations.append(("X", rotAng))
                return rotations
            else:
                print("Unable to flip Z=-1.0 object around Y or X axes.")
                return rotations
        elif z1:
            if IS_DEBUG:
                print("Breaking rotation scan loop for Z=1")
            break
        else:
            if not x0:
                ang = math.degrees(math.atan2(norm.x, norm.z))
                if ang < 0.0:
                    ang = 0.0 - ang
                elif ang > 0.0:
                    ang = 180.0 - ang
                f.rotate(CENTER_OF_ROTATION, FreeCAD.Vector(0.0, 1.0, 0.0), ang)
                rotAng = _normalizeDegrees(ang)
                rotations.append(("Y", rotAng))
                # print(f"  ang: {ang}")
                continue
            elif not y0:
                ang = math.degrees(math.atan2(norm.z, norm.y))
                ang = 90.0 - ang
                f.rotate(CENTER_OF_ROTATION, FreeCAD.Vector(1.0, 0.0, 0.0), ang)
                rotAng = _normalizeDegrees(ang)
                rotations.append(("X", rotAng))
                # print(f"  ang: {ang}")
                continue

        malAligned = False
        if cycles > 5:
            break

    # norm = f.normalAt(0, 0)
    # print(f"  {faceName} norm: {norm}\n  rotations: {rotations}")
    # print(f"  center of mass: {com}")
    # Part.show(f, faceName)

    return rotations


def _rotationsToOrderAndValues(rotations):
    axisOrder = ""
    degreeValues = FreeCAD.Vector(0.0, 0.0, 0.0)
    for axis, degree in rotations:
        attr = axis.lower()
        axisOrder += attr
        setattr(degreeValues, attr, degree)
    return axisOrder, degreeValues


# Regular functions
def getRotationToFace(base, faceName):
    """getRotationToFace(base, face, label)
    Return necessary degree rotations to align given face with Z=1, in vector form x, y, and z."""
    print("Macro_AlignToFeature.getRotationToFace()")
    global GROUP

    face = base.Shape.getElement(faceName)

    # Need to pass the following commented global normal vector to the _calculateRotationsToFace() method
    # u, v = face.ParameterRange[:2]
    # norm = face.normalAt(u, v)
    # globPlace = base.getGlobalPlacement()
    # globRotation = globPlace.Rotation
    # normalVector = globRotation.multVec(norm)
    # print(f"global normalVector: {normalVector}")

    rotations = _calculateRotationsToFace(face)  # Needs normalVector calculated above
    rotBase2 = rotateShapeWithList(base.Shape, rotations)
    isFlat = PathGeom.isRoughly(rotBase2.getElement(faceName).BoundBox.ZLength, 0.0)
    # rb2 = Part.show(rotBase2, f"RotBase2_{faceName}")
    # GROUP.addObject(rb2)
    return rotations, isFlat


def _executeAsMacro8():
    global GROUP
    baseObj = []

    print("\n")

    selection = FreeCADGui.Selection.getSelectionEx()
    # process user selection
    for sel in selection:
        # print(f"Object.Name: {sel.Object.Name}")
        baseObj.append((sel.Object, [n for n in sel.SubElementNames]))

    for base, featList in baseObj:
        for feat in featList:
            print(f"Working... {feat}")
            getRotationToFace(base, feat)


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

    GROUP = FreeCAD.ActiveDocument.addObject("App::DocumentObjectGroup", "Group")
    _executeAsMacro8()
    # CENTER_OF_ROTATION = FreeCAD.Vector(100, 50, 0)
    # _executeAsMacro()
    # test01()
    FreeCAD.ActiveDocument.recompute()
