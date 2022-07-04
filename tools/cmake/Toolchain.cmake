###############################################################################################
# This file is a 'toolchain description file' for CMake.                                      #
# The content of this file is mostly adpated from Emscripten CMake toolcahin file,            #
# with some modifications to make it work with Pyodide build system.                          #
###############################################################################################

set(CMAKE_CROSSCOMPILING TRUE)

# Note: this is False in original Emscripten toolchain,
#       however we often want to build shared libs
#       (See also: https://github.com/emscripten-core/emscripten/pull/16281)
set_property(GLOBAL PROPERTY TARGET_SUPPORTS_SHARED_LIBS True)

# Advertise Emscripten as a 32-bit platform (as opposed to
# CMAKE_SYSTEM_PROCESSOR=x86_64 for 64-bit platform), since some projects (e.g.
# OpenCV) use this to detect bitness.
# Allow users to ovewrite this on the command line with -DEMSCRIPTEN_SYSTEM_PROCESSOR=arm.
if ("${EMSCRIPTEN_SYSTEM_PROCESSOR}" STREQUAL "")
  set(EMSCRIPTEN_SYSTEM_PROCESSOR x86)
endif()
set(CMAKE_SYSTEM_PROCESSOR ${EMSCRIPTEN_SYSTEM_PROCESSOR})

# Tell CMake how it should instruct the compiler to generate multiple versions
# of an outputted .so library: e.g. "libfoo.so, libfoo.so.1, libfoo.so.1.4" etc.
# This feature is activated if a shared library project has the property
# SOVERSION defined.
set(CMAKE_SHARED_LIBRARY_SONAME_C_FLAG "-Wl,-soname,")

# In CMake, CMAKE_HOST_WIN32 is set when we are cross-compiling from Win32 to
# Emscripten:
# http://www.cmake.org/cmake/help/v2.8.12/cmake.html#variable:CMAKE_HOST_WIN32
# The variable WIN32 is set only when the target arch that will run the code
# will be WIN32, so unset WIN32 when cross-compiling.
set(WIN32)

# The same logic as above applies for APPLE and CMAKE_HOST_APPLE, so unset
# APPLE.
set(APPLE)

# And for UNIX and CMAKE_HOST_UNIX. However, Emscripten is often able to mimic
# being a Linux/Unix system, in which case a lot of existing CMakeLists.txt
# files can be configured for Emscripten while assuming UNIX build, so this is
# left enabled.
set(UNIX 1)

# Locate where the Emscripten compiler resides in relative to this toolchain file.
if ("${EMSCRIPTEN_ROOT_PATH}" STREQUAL "")
  get_filename_component(GUESS_EMSCRIPTEN_ROOT_PATH "${CMAKE_CURRENT_LIST_DIR}/../../emsdk/emsdk/upstream/emscripten" ABSOLUTE)
  if (EXISTS "${GUESS_EMSCRIPTEN_ROOT_PATH}/emranlib")
    set(EMSCRIPTEN_ROOT_PATH "${GUESS_EMSCRIPTEN_ROOT_PATH}")
  endif()
endif()

# If not found by above search, locate using the EMSCRIPTEN environment variable.
if ("${EMSCRIPTEN_ROOT_PATH}" STREQUAL "")
  set(EMSCRIPTEN_ROOT_PATH "$ENV{EMSCRIPTEN}")
endif()

# Abort if not found.
if ("${EMSCRIPTEN_ROOT_PATH}" STREQUAL "")
  message(FATAL_ERROR "Could not locate the Emscripten compiler toolchain directory! Either set the EMSCRIPTEN environment variable, or pass -DEMSCRIPTEN_ROOT_PATH=xxx to CMake to explicitly specify the location of the compiler!")
endif()

# Normalize, convert Windows backslashes to forward slashes or CMake will crash.
get_filename_component(EMSCRIPTEN_ROOT_PATH "${EMSCRIPTEN_ROOT_PATH}" ABSOLUTE)

list(APPEND CMAKE_MODULE_PATH "${EMSCRIPTEN_ROOT_PATH}/cmake/Modules")

execute_process(COMMAND "${EMSCRIPTEN_ROOT_PATH}/em-config${EMCC_SUFFIX}" "CACHE"
  RESULT_VARIABLE _emcache_result
  OUTPUT_VARIABLE _emcache_output
  OUTPUT_STRIP_TRAILING_WHITESPACE)
if (NOT _emcache_result EQUAL 0)
  message(FATAL_ERROR "Failed to find emscripten cache directory with command \"'${EMSCRIPTEN_ROOT_PATH}/em-config${EMCC_SUFFIX}' CACHE\"! Process returned with error code ${_emcache_result}.")
endif()
file(TO_CMAKE_PATH "${_emcache_output}" _emcache_output)
set(EMSCRIPTEN_SYSROOT "${_emcache_output}/sysroot")

list(APPEND CMAKE_FIND_ROOT_PATH "${EMSCRIPTEN_SYSROOT}")
list(APPEND CMAKE_SYSTEM_PREFIX_PATH /)

if ($ENV{CFLAGS} MATCHES "MEMORY64")
  set(CMAKE_LIBRARY_ARCHITECTURE "wasm64-emscripten")
else()
  set(CMAKE_LIBRARY_ARCHITECTURE "wasm32-emscripten")
endif()

if(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
  set(CMAKE_INSTALL_PREFIX "${EMSCRIPTEN_SYSROOT}" CACHE PATH
    "Install path prefix, prepended onto install directories." FORCE)
endif()

# To find programs to execute during CMake run time with find_program(), e.g.
# 'git' or so, we allow looking into system paths.
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)

# Since Emscripten is a cross-compiler, we should never look at the
# system-provided directories like /usr/include and so on. Therefore only
# CMAKE_FIND_ROOT_PATH should be used as a find directory. See
# http://www.cmake.org/cmake/help/v3.0/variable/CMAKE_FIND_ROOT_PATH_MODE_INCLUDE.html
if (NOT CMAKE_FIND_ROOT_PATH_MODE_LIBRARY)
  set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
endif()
if (NOT CMAKE_FIND_ROOT_PATH_MODE_INCLUDE)
  set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
endif()
if (NOT CMAKE_FIND_ROOT_PATH_MODE_PACKAGE)
  set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
endif()

set(_em_pkgconfig_libdir "${EMSCRIPTEN_SYSROOT}/local/lib/pkgconfig" "${EMSCRIPTEN_SYSROOT}/lib/pkgconfig")
if("${CMAKE_VERSION}" VERSION_LESS "3.20")
  file(TO_NATIVE_PATH "${_em_pkgconfig_libdir}" _em_pkgconfig_libdir)
  if(CMAKE_HOST_UNIX)
    string(REPLACE ";" ":" _em_pkgconfig_libdir "${_em_pkgconfig_libdir}")
    string(REPLACE "\\ " " " _em_pkgconfig_libdir "${_em_pkgconfig_libdir}")
  endif()
else()
  cmake_path(CONVERT "${_em_pkgconfig_libdir}" TO_NATIVE_PATH_LIST _em_pkgconfig_libdir)
endif()
set(ENV{PKG_CONFIG_LIBDIR} "${_em_pkgconfig_libdir}")
unset(_em_pkgconfig_libdir)

set(CMAKE_C_USE_RESPONSE_FILE_FOR_LIBRARIES 1)
set(CMAKE_CXX_USE_RESPONSE_FILE_FOR_LIBRARIES 1)
set(CMAKE_C_USE_RESPONSE_FILE_FOR_OBJECTS 1)
set(CMAKE_CXX_USE_RESPONSE_FILE_FOR_OBJECTS 1)
set(CMAKE_C_USE_RESPONSE_FILE_FOR_INCLUDES 1)
set(CMAKE_CXX_USE_RESPONSE_FILE_FOR_INCLUDES 1)

set(CMAKE_C_RESPONSE_FILE_LINK_FLAG "@")
set(CMAKE_CXX_RESPONSE_FILE_LINK_FLAG "@")

# Set a global EMSCRIPTEN variable that can be used in client CMakeLists.txt to
# detect when building using Emscripten.
set(EMSCRIPTEN 1 CACHE BOOL "If true, we are targeting Emscripten output.")

# Hardwire support for cmake-2.8/Modules/CMakeBackwardsCompatibilityC.cmake
# without having CMake to try complex things to autodetect these:
set(CMAKE_SKIP_COMPATIBILITY_TESTS 1)
set(CMAKE_SIZEOF_CHAR 1)
set(CMAKE_SIZEOF_UNSIGNED_SHORT 2)
set(CMAKE_SIZEOF_SHORT 2)
set(CMAKE_SIZEOF_INT 4)
set(CMAKE_SIZEOF_UNSIGNED_LONG 4)
set(CMAKE_SIZEOF_UNSIGNED_INT 4)
set(CMAKE_SIZEOF_LONG 4)
set(CMAKE_SIZEOF_VOID_P 4)
set(CMAKE_SIZEOF_FLOAT 4)
set(CMAKE_SIZEOF_DOUBLE 8)
set(CMAKE_C_SIZEOF_DATA_PTR 4)
set(CMAKE_CXX_SIZEOF_DATA_PTR 4)
set(CMAKE_HAVE_LIMITS_H 1)
set(CMAKE_HAVE_UNISTD_H 1)
set(CMAKE_HAVE_PTHREAD_H 1)
set(CMAKE_HAVE_SYS_PRCTL_H 1)
set(CMAKE_WORDS_BIGENDIAN 0)
set(CMAKE_DL_LIBS)

if (NOT DEFINED CMAKE_CROSSCOMPILING_EMULATOR)
  find_program(NODE_JS_EXECUTABLE NAMES nodejs node)
  if(NODE_JS_EXECUTABLE)
    set(CMAKE_CROSSCOMPILING_EMULATOR "${NODE_JS_EXECUTABLE}" CACHE FILEPATH "Path to the emulator for the target system.")
  endif()
endif()

# TODO: CMake appends <sysroot>/usr/include to implicit includes; switching to use usr/include will make this redundant.
if ("${CMAKE_C_IMPLICIT_INCLUDE_DIRECTORIES}" STREQUAL "")
  set(CMAKE_C_IMPLICIT_INCLUDE_DIRECTORIES "${EMSCRIPTEN_SYSROOT}/include")
endif()
if ("${CMAKE_CXX_IMPLICIT_INCLUDE_DIRECTORIES}" STREQUAL "")
  set(CMAKE_CXX_IMPLICIT_INCLUDE_DIRECTORIES "${EMSCRIPTEN_SYSROOT}/include")
endif()
unset(_em_sysroot_include)
