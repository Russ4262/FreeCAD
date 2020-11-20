add_subdirectory(App)
add_subdirectory(libarea)
add_subdirectory(PathSimulator)

if(BUILD_GUI)
    add_subdirectory(Gui)
endif(BUILD_GUI)

set(Path_Scripts
    Init.py
    PathCommands.py
    TestPathApp.py
)

if(BUILD_GUI)
    list (APPEND Path_Scripts InitGui.py)
endif(BUILD_GUI)

INSTALL(
    FILES
        ${Path_Scripts}
    DESTINATION
        Mod/Path
)

SET(PathScripts_SRCS
    PathCommands.py
    PathScripts/__init__.py
    PathScripts/PathArray.py
    PathScripts/PathComment.py
    PathScripts/PathCopy.py
    PathScripts/PathCustom.py
    PathScripts/PathCustomGui.py
    PathScripts/PathDressup.py
    PathScripts/PathDressupAxisMap.py
    PathScripts/PathDressupDogbone.py
    PathScripts/PathDressupDragknife.py
    PathScripts/PathDressupHoldingTags.py
    PathScripts/PathDressupLeadInOut.py
    PathScripts/PathDressupPathBoundary.py
    PathScripts/PathDressupPathBoundaryGui.py
    PathScripts/PathDressupRampEntry.py
    PathScripts/PathDressupTag.py
    PathScripts/PathDressupTagGui.py
    PathScripts/PathDressupTagPreferences.py
    PathScripts/PathDressupZCorrect.py
    PathScripts/PathFixture.py
    PathScripts/PathGeom.py
    PathScripts/PathGetPoint.py
    PathScripts/PathGui.py
    PathScripts/PathGuiInit.py
    PathScripts/PathHop.py
    PathScripts/PathIconViewProvider.py
    PathScripts/PathInspect.py
    PathScripts/PathJob.py
    PathScripts/PathJobCmd.py
    PathScripts/PathJobDlg.py
    PathScripts/PathJobGui.py
    PathScripts/PathLog.py
    PathScripts/PathOp.py
    PathScripts/PathOpGui.py
    PathScripts/PathOpTools.py
    PathScripts/PathPost.py
    PathScripts/PathPostProcessor.py
    PathScripts/PathPreferences.py
    PathScripts/PathPreferencesPathDressup.py
    PathScripts/PathPreferencesPathJob.py
    PathScripts/PathProbe.py
    PathScripts/PathProbeGui.py
    PathScripts/PathSanity.py
    PathScripts/PathSelection.py
    PathScripts/PathSetupSheet.py
    PathScripts/PathSetupSheetGui.py
    PathScripts/PathSetupSheetOpPrototype.py
    PathScripts/PathSetupSheetOpPrototypeGui.py
    PathScripts/PathSimpleCopy.py
    PathScripts/PathSimulatorGui.py
    PathScripts/PathStock.py
    PathScripts/PathStop.py
    PathScripts/PathToolBit.py
    PathScripts/PathToolBitCmd.py
    PathScripts/PathToolBitEdit.py
    PathScripts/PathToolBitGui.py
    PathScripts/PathToolBitLibraryCmd.py
    PathScripts/PathToolBitLibraryGui.py
    PathScripts/PathToolController.py
    PathScripts/PathToolControllerGui.py
    PathScripts/PathToolEdit.py
    PathScripts/PathToolLibraryEditor.py
    PathScripts/PathToolLibraryManager.py
    PathScripts/PathUtil.py
    PathScripts/PathUtils.py
    PathScripts/PathUtilsGui.py
    PathScripts/PostUtils.py
)

SET(PathScripts_Features_SRCS
    PathScripts/Features/__init__.py
    PathScripts/Features/BaseGeometryTaskPanel.py
    PathScripts/Features/BaseLocationTaskPanel.py
    PathScripts/Features/DepthsTaskPanel.py
    PathScripts/Features/HeightsTaskPanel.py
)

SET(PathScripts_Operations_SRCS
    PathScripts/Operations/__init__.py
    PathScripts/Operations/PathAdaptive.py
    PathScripts/Operations/PathAdaptiveGui.py
    PathScripts/Operations/PathAreaOp.py
    PathScripts/Operations/PathCircularHoleBase.py
    PathScripts/Operations/PathCircularHoleBaseGui.py
    PathScripts/Operations/PathDeburr.py
    PathScripts/Operations/PathDeburrGui.py
    PathScripts/Operations/PathDrilling.py
    PathScripts/Operations/PathDrillingGui.py
    PathScripts/Operations/PathEngrave.py
    PathScripts/Operations/PathEngraveBase.py
    PathScripts/Operations/PathEngraveGui.py
    PathScripts/Operations/PathHelix.py
    PathScripts/Operations/PathHelixGui.py
    PathScripts/Operations/PathMillFace.py
    PathScripts/Operations/PathMillFaceGui.py
    PathScripts/Operations/PathPocket.py
    PathScripts/Operations/PathPocketBase.py
    PathScripts/Operations/PathPocketBaseGui.py
    PathScripts/Operations/PathPocketGui.py
    PathScripts/Operations/PathPocketShape.py
    PathScripts/Operations/PathPocketShapeGui.py
    PathScripts/Operations/PathProfile.py
    PathScripts/Operations/PathProfileContour.py
    PathScripts/Operations/PathProfileContourGui.py
    PathScripts/Operations/PathProfileEdges.py
    PathScripts/Operations/PathProfileEdgesGui.py
    PathScripts/Operations/PathProfileFaces.py
    PathScripts/Operations/PathProfileFacesGui.py
    PathScripts/Operations/PathProfileGui.py
    PathScripts/Operations/PathSlot.py
    PathScripts/Operations/PathSlotGui.py
    PathScripts/Operations/PathSurface.py
    PathScripts/Operations/PathSurfaceGui.py
    PathScripts/Operations/PathSurfaceSupport.py
    PathScripts/Operations/PathWaterline.py
    PathScripts/Operations/PathWaterlineGui.py
    PathScripts/Operations/PathVcarve.py
    PathScripts/Operations/PathVcarveGui.py
)

SET(PathScripts_post_SRCS
    PathScripts/post/__init__.py
    PathScripts/post/centroid_post.py
    PathScripts/post/comparams_post.py
    PathScripts/post/dynapath_post.py
    PathScripts/post/example_pre.py
    PathScripts/post/gcode_pre.py
    PathScripts/post/grbl_post.py
    PathScripts/post/jtech_post.py
    PathScripts/post/linuxcnc_post.py
    PathScripts/post/mach3_mach4_post.py
    PathScripts/post/nccad_post.py
    PathScripts/post/opensbp_post.py
    PathScripts/post/opensbp_pre.py
    PathScripts/post/philips_post.py
    PathScripts/post/rml_post.py
    PathScripts/post/slic3r_pre.py
    PathScripts/post/smoothie_post.py
)

SET(Tools_Bit_SRCS
    Tools/Bit/t1.fctb
    Tools/Bit/t2.fctb
    Tools/Bit/t3.fctb
    Tools/Bit/t4.fctb
    Tools/Bit/t5.fctb
    Tools/Bit/t6.fctb
    Tools/Bit/t7.fctb
    Tools/Bit/t8.fctb
    Tools/Bit/t9.fctb
)

SET(Tools_Library_SRCS
    Tools/Library/endmills.fctl
)

SET(Tools_Shape_SRCS
    Tools/Shape/ballend.fcstd
    Tools/Shape/bullnose.fcstd
    Tools/Shape/drill.fcstd
    Tools/Shape/endmill.fcstd
    Tools/Shape/v-bit.fcstd
)

SET(PathTests_SRCS
    PathTests/__init__.py
    PathTests/PathTestUtils.py
    PathTests/TestPathCore.py
    PathTests/TestPathDeburr.py
    PathTests/TestPathDepthParams.py
    PathTests/TestPathDressupDogbone.py
    PathTests/TestPathDressupHoldingTags.py
    PathTests/TestPathGeom.py
    PathTests/TestPathHelix.py
    PathTests/TestPathLog.py
    PathTests/TestPathOpTools.py
    PathTests/TestPathPost.py
    PathTests/TestPathPreferences.py
    PathTests/TestPathSetupSheet.py
    PathTests/TestPathStock.py
    PathTests/TestPathTool.py
    PathTests/TestPathToolBit.py
    PathTests/TestPathToolController.py
    PathTests/TestPathTooltable.py
    PathTests/TestPathUtil.py
    PathTests/TestPathVoronoi.py
    PathTests/boxtest.fcstd
    PathTests/test_centroid_00.ngc
    PathTests/test_geomop.fcstd
    PathTests/test_holes00.fcstd
    PathTests/test_linuxcnc_00.ngc
)

SET(PathImages_Ops
    Images/Ops/chamfer.svg
)

SET(PathImages_Tools
    Images/Tools/drill.svg
    Images/Tools/endmill.svg
    Images/Tools/v-bit.svg
)

SET(Path_Images
    ${PathImages_Ops}
    ${PathImages_Tools}
)

SET(all_files
    ${PathScripts_SRCS}
    ${PathScripts_post_SRCS}
    ${PathScripts_Features_SRCS}
    ${PathScripts_Operations_SRCS}
    ${Tools_Bit_SRCS}
    ${Tools_Library_SRCS}
    ${Tools_Shape_SRCS}
    ${Path_Images}
)

ADD_CUSTOM_TARGET(PathScripts ALL
    SOURCES ${all_files}
)

SET(test_files
  ${Path_Scripts}
  ${PathTests_SRCS}
)

ADD_CUSTOM_TARGET(PathTests ALL
    SOURCES ${test_files}
)

fc_copy_sources(PathScripts "${CMAKE_BINARY_DIR}/Mod/Path" ${all_files})
fc_copy_sources(PathTests "${CMAKE_BINARY_DIR}/Mod/Path" ${test_files})

INSTALL(
    FILES
        ${PathScripts_SRCS}
    DESTINATION
        Mod/Path/PathScripts
)

INSTALL(
    FILES
        ${PathScripts_Features_SRCS}
    DESTINATION
        Mod/Path/PathScripts/Features
)

INSTALL(
    FILES
        ${PathScripts_Operations_SRCS}
    DESTINATION
        Mod/Path/PathScripts/Operations
)

INSTALL(
    FILES
        ${PathTests_SRCS}
    DESTINATION
        Mod/Path/PathTests
)

INSTALL(
    FILES
        ${PathScripts_post_SRCS}
    DESTINATION
        Mod/Path/PathScripts/post
)

INSTALL(
    FILES
        ${Tools_Bit_SRCS}
    DESTINATION
        Mod/Path/Tools/Bit
)

INSTALL(
    FILES
        ${Tools_Library_SRCS}
    DESTINATION
        Mod/Path/Tools/Library
)

INSTALL(
    FILES
      ${Tools_Shape_SRCS}
    DESTINATION
      Mod/Path/Tools/Shape
)

INSTALL(
    FILES
        ${PathImages_Ops}
    DESTINATION
        Mod/Path/Images/Ops
)

INSTALL(
    FILES
        ${PathImages_Tools}
    DESTINATION
        Mod/Path/Images/Tools
)

