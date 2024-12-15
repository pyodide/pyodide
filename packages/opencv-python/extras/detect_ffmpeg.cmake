# --- FFMPEG ---

set(HAVE_FFMPEG TRUE)
set(FFMPEG_FOUND TRUE)

set(FFMPEG_ROOT_PATH "$ENV{FFMPEG_ROOT}")
set(FFMPEG_INCLUDE_DIRS "${FFMPEG_ROOT_PATH}/include")
set(FFMPEG_LIBRARIES
  "${FFMPEG_ROOT_PATH}/lib/libavcodec.a"
  "${FFMPEG_ROOT_PATH}/lib/libavformat.a"
  "${FFMPEG_ROOT_PATH}/lib/libavutil.a"
  "${FFMPEG_ROOT_PATH}/lib/libswscale.a"
  "${FFMPEG_ROOT_PATH}/lib/libswresample.a"
)

ocv_add_external_target(ffmpeg "${FFMPEG_INCLUDE_DIRS}" "${FFMPEG_LIBRARIES}" "HAVE_FFMPEG")

set(__builtin_defines "")
set(__builtin_include_dirs "")
set(__builtin_libs "")
set(__plugin_defines "")
set(__plugin_include_dirs "")
set(__plugin_libs "")
if(HAVE_OPENCL)
set(__opencl_dirs "")
if(OPENCL_INCLUDE_DIRS)
    set(__opencl_dirs "${OPENCL_INCLUDE_DIRS}")
elseif(OPENCL_INCLUDE_DIR)
    set(__opencl_dirs "${OPENCL_INCLUDE_DIR}")
else()
    set(__opencl_dirs "${OpenCV_SOURCE_DIR}/3rdparty/include/opencl/1.2")
endif()
# extra dependencies for building code (OpenCL dir is required for extensions like cl_d3d11.h)
# building HAVE_OPENCL is already defined through cvconfig.h
list(APPEND __builtin_include_dirs "${__opencl_dirs}")

# extra dependencies for
list(APPEND __plugin_defines "HAVE_OPENCL")
list(APPEND __plugin_include_dirs "${__opencl_dirs}")
endif()

# TODO: libva, d3d11

if(__builtin_include_dirs OR __builtin_include_defines OR __builtin_include_libs)
ocv_add_external_target(ffmpeg.builtin_deps "${__builtin_include_dirs}" "${__builtin_include_libs}" "${__builtin_defines}")
endif()
if(VIDEOIO_ENABLE_PLUGINS AND __plugin_include_dirs OR __plugin_include_defines OR __plugin_include_libs)
ocv_add_external_target(ffmpeg.plugin_deps "${__plugin_include_dirs}" "${__plugin_include_libs}" "${__plugin_defines}")
endif()
