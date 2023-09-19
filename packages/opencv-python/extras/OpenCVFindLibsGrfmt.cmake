# ----------------------------------------------------------------------------
#  Detect 3rd-party image IO libraries
# ----------------------------------------------------------------------------

# We want to use emscripten-ported version of ZLIB, LIBJPEG, LIBPNG.
# However, OpenCV tries to find them in system paths.
# Let's deceive OpenCV and pretend we have them.

set(HAVE_JPEG YES)
set(HAVE_PNG YES)
set(ZLIB_FOUND YES)

# --- libtiff (optional, should be searched after zlib and libjpeg) ---
if(WITH_TIFF)
  if(BUILD_TIFF)
    ocv_clear_vars(TIFF_FOUND)
  else()
    ocv_clear_internal_cache_vars(TIFF_LIBRARY TIFF_INCLUDE_DIR)
    include(FindTIFF)
    if(TIFF_FOUND)
      ocv_parse_header("${TIFF_INCLUDE_DIR}/tiff.h" TIFF_VERSION_LINES TIFF_VERSION_CLASSIC TIFF_VERSION_BIG TIFF_VERSION TIFF_BIGTIFF_VERSION)
    endif()
  endif()

  if(NOT TIFF_FOUND)
    ocv_clear_vars(TIFF_LIBRARY TIFF_LIBRARIES TIFF_INCLUDE_DIR)

    set(TIFF_LIBRARY libtiff CACHE INTERNAL "")
    set(TIFF_LIBRARIES ${TIFF_LIBRARY})
    add_subdirectory("${OpenCV_SOURCE_DIR}/3rdparty/libtiff")
    set(TIFF_INCLUDE_DIR "${${TIFF_LIBRARY}_SOURCE_DIR}" "${${TIFF_LIBRARY}_BINARY_DIR}" CACHE INTERNAL "")
    ocv_parse_header("${${TIFF_LIBRARY}_SOURCE_DIR}/tiff.h" TIFF_VERSION_LINES TIFF_VERSION_CLASSIC TIFF_VERSION_BIG TIFF_VERSION TIFF_BIGTIFF_VERSION)
  endif()

  if(TIFF_VERSION_CLASSIC AND NOT TIFF_VERSION)
    set(TIFF_VERSION ${TIFF_VERSION_CLASSIC})
  endif()

  if(TIFF_BIGTIFF_VERSION AND NOT TIFF_VERSION_BIG)
    set(TIFF_VERSION_BIG ${TIFF_BIGTIFF_VERSION})
  endif()

  if(NOT TIFF_VERSION_STRING AND TIFF_INCLUDE_DIR)
    list(GET TIFF_INCLUDE_DIR 0 _TIFF_INCLUDE_DIR)
    if(EXISTS "${_TIFF_INCLUDE_DIR}/tiffvers.h")
      file(STRINGS "${_TIFF_INCLUDE_DIR}/tiffvers.h" tiff_version_str REGEX "^#define[\t ]+TIFFLIB_VERSION_STR[\t ]+\"LIBTIFF, Version .*")
      string(REGEX REPLACE "^#define[\t ]+TIFFLIB_VERSION_STR[\t ]+\"LIBTIFF, Version +([^ \\n]*).*" "\\1" TIFF_VERSION_STRING "${tiff_version_str}")
      unset(tiff_version_str)
    endif()
    unset(_TIFF_INCLUDE_DIR)
  endif()

  set(HAVE_TIFF YES)
endif()

# --- libwebp (optional) ---

if(WITH_WEBP)
  if(BUILD_WEBP)
    ocv_clear_vars(WEBP_FOUND WEBP_LIBRARY WEBP_LIBRARIES WEBP_INCLUDE_DIR)
  else()
    ocv_clear_internal_cache_vars(WEBP_LIBRARY WEBP_INCLUDE_DIR)
    include(cmake/OpenCVFindWebP.cmake)
    if(WEBP_FOUND)
      set(HAVE_WEBP 1)
    endif()
  endif()
endif()

# --- Add libwebp to 3rdparty/libwebp and compile it if not available ---
if(WITH_WEBP AND NOT WEBP_FOUND
    AND (NOT ANDROID OR HAVE_CPUFEATURES)
)
  ocv_clear_vars(WEBP_LIBRARY WEBP_INCLUDE_DIR)
  set(WEBP_LIBRARY libwebp CACHE INTERNAL "")
  set(WEBP_LIBRARIES ${WEBP_LIBRARY})

  add_subdirectory("${OpenCV_SOURCE_DIR}/3rdparty/libwebp")
  set(WEBP_INCLUDE_DIR "${${WEBP_LIBRARY}_SOURCE_DIR}/src" CACHE INTERNAL "")
  set(HAVE_WEBP 1)
endif()

if(NOT WEBP_VERSION AND WEBP_INCLUDE_DIR)
  ocv_clear_vars(ENC_MAJ_VERSION ENC_MIN_VERSION ENC_REV_VERSION)
  if(EXISTS "${WEBP_INCLUDE_DIR}/enc/vp8enci.h")
    ocv_parse_header("${WEBP_INCLUDE_DIR}/enc/vp8enci.h" WEBP_VERSION_LINES ENC_MAJ_VERSION ENC_MIN_VERSION ENC_REV_VERSION)
    set(WEBP_VERSION "${ENC_MAJ_VERSION}.${ENC_MIN_VERSION}.${ENC_REV_VERSION}")
  elseif(EXISTS "${WEBP_INCLUDE_DIR}/webp/encode.h")
    file(STRINGS "${WEBP_INCLUDE_DIR}/webp/encode.h" WEBP_ENCODER_ABI_VERSION REGEX "#define[ \t]+WEBP_ENCODER_ABI_VERSION[ \t]+([x0-9a-f]+)" )
    if(WEBP_ENCODER_ABI_VERSION MATCHES "#define[ \t]+WEBP_ENCODER_ABI_VERSION[ \t]+([x0-9a-f]+)")
        set(WEBP_ENCODER_ABI_VERSION "${CMAKE_MATCH_1}")
        set(WEBP_VERSION "encoder: ${WEBP_ENCODER_ABI_VERSION}")
    else()
      unset(WEBP_ENCODER_ABI_VERSION)
    endif()
  endif()
endif()

# --- libopenjp2 (optional, check before libjasper) ---
if(WITH_OPENJPEG)
  if(BUILD_OPENJPEG)
    ocv_clear_vars(OpenJPEG_FOUND)
  else()
    find_package(OpenJPEG QUIET)
  endif()

  if(NOT OpenJPEG_FOUND OR OPENJPEG_MAJOR_VERSION LESS 2)
    ocv_clear_vars(OPENJPEG_MAJOR_VERSION OPENJPEG_MINOR_VERSION OPENJPEG_BUILD_VERSION OPENJPEG_LIBRARIES OPENJPEG_INCLUDE_DIRS)
    message(STATUS "Could NOT find OpenJPEG (minimal suitable version: 2.0, "
            "recommended version >= 2.3.1). OpenJPEG will be built from sources")
    add_subdirectory("${OpenCV_SOURCE_DIR}/3rdparty/openjpeg")
    if(OCV_CAN_BUILD_OPENJPEG)
      set(HAVE_OPENJPEG YES)
      message(STATUS "OpenJPEG libraries will be built from sources: ${OPENJPEG_LIBRARIES} "
              "(version \"${OPENJPEG_VERSION}\")")
    else()
      set(HAVE_OPENJPEG NO)
      message(STATUS "OpenJPEG libraries can't be built from sources. System requirements are not fulfilled.")
    endif()
  else()
    set(HAVE_OPENJPEG YES)
    message(STATUS "Found system OpenJPEG: ${OPENJPEG_LIBRARIES} "
            "(found version \"${OPENJPEG_VERSION}\")")
  endif()
endif()

# --- libjasper (optional, should be searched after libjpeg) ---
if(WITH_JASPER AND NOT HAVE_OPENJPEG)
  if(BUILD_JASPER)
    ocv_clear_vars(JASPER_FOUND)
  else()
    include(FindJasper)
  endif()

  if(NOT JASPER_FOUND)
    ocv_clear_vars(JASPER_LIBRARY JASPER_LIBRARIES JASPER_INCLUDE_DIR)

    set(JASPER_LIBRARY libjasper CACHE INTERNAL "")
    set(JASPER_LIBRARIES ${JASPER_LIBRARY})
    add_subdirectory("${OpenCV_SOURCE_DIR}/3rdparty/libjasper")
    set(JASPER_INCLUDE_DIR "${${JASPER_LIBRARY}_SOURCE_DIR}" CACHE INTERNAL "")
  endif()

  set(HAVE_JASPER YES)

  if(NOT JASPER_VERSION_STRING)
    ocv_parse_header2(JASPER "${JASPER_INCLUDE_DIR}/jasper/jas_config.h" JAS_VERSION "")
  endif()
endif()

# --- OpenEXR (optional) ---
if(WITH_OPENEXR)
  ocv_clear_vars(HAVE_OPENEXR)
  if(NOT BUILD_OPENEXR)
    ocv_clear_internal_cache_vars(OPENEXR_INCLUDE_PATHS OPENEXR_LIBRARIES OPENEXR_ILMIMF_LIBRARY OPENEXR_VERSION)
    include("${OpenCV_SOURCE_DIR}/cmake/OpenCVFindOpenEXR.cmake")
  endif()

  if(OPENEXR_FOUND)
    set(HAVE_OPENEXR YES)
  else()
    ocv_clear_vars(OPENEXR_INCLUDE_PATHS OPENEXR_LIBRARIES OPENEXR_ILMIMF_LIBRARY OPENEXR_VERSION)

    set(OPENEXR_LIBRARIES IlmImf)
    add_subdirectory("${OpenCV_SOURCE_DIR}/3rdparty/openexr")
    if(OPENEXR_VERSION)  # check via TARGET doesn't work
      set(BUILD_OPENEXR ON)
      set(HAVE_OPENEXR YES)
      set(BUILD_OPENEXR ON)
    endif()
  endif()
endif()

# --- GDAL (optional) ---
if(WITH_GDAL)
    find_package(GDAL QUIET)

    if(NOT GDAL_FOUND)
        set(HAVE_GDAL NO)
        ocv_clear_vars(GDAL_VERSION GDAL_LIBRARIES)
    else()
        set(HAVE_GDAL YES)
        ocv_include_directories(${GDAL_INCLUDE_DIR})
    endif()
endif()

if(WITH_GDCM)
  find_package(GDCM QUIET)
  if(NOT GDCM_FOUND)
    set(HAVE_GDCM NO)
    ocv_clear_vars(GDCM_VERSION GDCM_LIBRARIES)
  else()
    set(HAVE_GDCM YES)
    # include(${GDCM_USE_FILE})
    set(GDCM_LIBRARIES gdcmMSFF) # GDCM does not set this variable for some reason
  endif()
endif()

if(WITH_IMGCODEC_HDR)
  set(HAVE_IMGCODEC_HDR ON)
elseif(DEFINED WITH_IMGCODEC_HDR)
  set(HAVE_IMGCODEC_HDR OFF)
endif()
if(WITH_IMGCODEC_SUNRASTER)
  set(HAVE_IMGCODEC_SUNRASTER ON)
elseif(DEFINED WITH_IMGCODEC_SUNRASTER)
  set(HAVE_IMGCODEC_SUNRASTER OFF)
endif()
if(WITH_IMGCODEC_PXM)
  set(HAVE_IMGCODEC_PXM ON)
elseif(DEFINED WITH_IMGCODEC_PXM)
  set(HAVE_IMGCODEC_PXM OFF)
endif()
if(WITH_IMGCODEC_PFM)
  set(HAVE_IMGCODEC_PFM ON)
elseif(DEFINED WITH_IMGCODEC_PFM)
  set(HAVE_IMGCODEC_PFM OFF)
endif()
