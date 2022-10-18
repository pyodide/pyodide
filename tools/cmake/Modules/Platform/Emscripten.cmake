###############################################################################################
# This file is a 'toolchain description file' for CMake.                                      #
# Differences from the original Emscripten toolchain file are:                                #
# - set TARGET_SUPPORTS_SHARED_LIBS to TRUE                                                   #
# - set CMAKE_INSTALL_PREFIX to WASM_LIBRARY_DIR                                              #
# - disable the usage of response file for object and libraries                               #
# - allow to overwrite CMAKE_PROJECT_INCLUDE, CMAKE_PROJECT_INCLUDE_BEFORE with env variable  #
# - append SIDE_MODULE_CFLAGS and SIDE_MODULE_LDFLAGS automatically                           #
###############################################################################################

# First, we inherit most of settings from the original Emscripten toolchain file.
# Then, we will update some settings.

execute_process(COMMAND "em-config" "EMSCRIPTEN_ROOT"
  RESULT_VARIABLE _emconfig_result
  OUTPUT_VARIABLE _emconfig_output
  OUTPUT_STRIP_TRAILING_WHITESPACE)
if (NOT _emconfig_result EQUAL 0)
  message(FATAL_ERROR "Failed to find emscripten root directory with command \"em-config EMSCRIPTEN_ROOT\"! Process returned with error code ${_emcache_result}.")
endif()

file(TO_CMAKE_PATH "${_emconfig_output}" _emcache_output)
set(EMSCRIPTEN_CMAKE_TOOLCHAIN_FILE "${_emconfig_output}/cmake/Modules/Platform/Emscripten.cmake" CACHE FILEPATH "Path to Emscripten CMake toolchain file.")
include("${EMSCRIPTEN_CMAKE_TOOLCHAIN_FILE}")

# Note: this is False in original Emscripten toolchain,
#       however we always want to allow build shared libs
#       (See also: https://github.com/emscripten-core/emscripten/pull/16281)
set_property(GLOBAL PROPERTY TARGET_SUPPORTS_SHARED_LIBS TRUE)

# CMakeSystemSpecificInformation.cmake tries to include a Toolchain file from ${CMAKE_MODULE_PATH}/Platform/{CMAKE_SYSTEM_NAME}.cmake.
# So in order to prevent CMake from loading the original Emscripten toolchain file, we need to prepend our own toolchain file.
list(PREPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/..")

# We build libraries into WASM_LIBRARY_DIR, so lets tell CMake
# to find libraries from there.
if (NOT "$ENV{WASM_LIBRARY_DIR}" STREQUAL "")
  list(PREPEND CMAKE_FIND_ROOT_PATH "$ENV{WASM_LIBRARY_DIR}")
  if (CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
    set(CMAKE_INSTALL_PREFIX "$ENV{WASM_LIBRARY_DIR}" CACHE PATH
      "Install path prefix, prepended onto install directories." FORCE)
  endif()
endif()

# Note: Emscripten installs libraries into subdirectories such as:
# - Non PIC: <SYSROOT>/lib/<arch>/<lib>
# - PIC: <SYSROOT>/lib/<arch>/pic/<lib>
# - LTO: <SYSROOT>/lib/<arch>/lto/<lib>
# - PIC+LTO: <SYSROOT>/lib/<arch>/pic/lto/<lib>
# We always wants to use a library built with "-fPIC", but
# CMake's find_library() will search Non-PIC dir only by default.
# This is a hack which overrides find_library() to tell CMake to look at PIC dirs first.
if ($ENV{CFLAGS} MATCHES "MEMORY64")
  set(CMAKE_LIBRARY_ARCHITECTURE "wasm64-emscripten/pic")
else()
  set(CMAKE_LIBRARY_ARCHITECTURE "wasm32-emscripten/pic")
endif()


# Disable the usage of response file so objects are exposed to the commandline.
# Our export calculation logic in pywasmcross needs to read object files.
# TODO: support export calculation from the response file
set(CMAKE_C_USE_RESPONSE_FILE_FOR_LIBRARIES 0)
set(CMAKE_CXX_USE_RESPONSE_FILE_FOR_LIBRARIES 0)
set(CMAKE_C_USE_RESPONSE_FILE_FOR_OBJECTS 0)
set(CMAKE_CXX_USE_RESPONSE_FILE_FOR_OBJECTS 0)
set(CMAKE_C_USE_RESPONSE_FILE_FOR_INCLUDES 1)
set(CMAKE_CXX_USE_RESPONSE_FILE_FOR_INCLUDES 1)

# Allow some of the variables to be overridden by the user by env variable
# CMAKE_PROJECT_INCLUDE is a nice way to override some properties of the project
# It can be set by passing -DCMAKE_PROJECT_INCLUDE=... to cmake
# But some python packages will not allow users to pass extra arguments to cmake
# So this is a workaround to allow users to override CMAKE_PROJECT_INCLUDE by env variable
if ("${CMAKE_PROJECT_INCLUDE_BEFORE}" STREQUAL "" AND DEFINED ENV{CMAKE_PROJECT_INCLUDE_BEFORE})
  message(STATUS "Set CMAKE_PROJECT_INCLUDE_BEFORE to $ENV{CMAKE_PROJECT_INCLUDE_BEFORE} using env variable")
  set(CMAKE_PROJECT_INCLUDE_BEFORE "$ENV{CMAKE_PROJECT_INCLUDE_BEFORE}")
endif()

if ("${CMAKE_PROJECT_INCLUDE}" STREQUAL ""  AND DEFINED ENV{CMAKE_PROJECT_INCLUDE})
  message(STATUS "Set CMAKE_PROJECT_INCLUDE to $ENV{CMAKE_PROJECT_INCLUDE} using env variable")
  set(CMAKE_PROJECT_INCLUDE "$ENV{CMAKE_PROJECT_INCLUDE}")
endif()

# Set SIDE_MODULE_CFLAGS and SIDE_MODULE_LDFLAGS automatically
# This is automatically set for Python project, but we often omit these in libraries.
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} $ENV{SIDE_MODULE_CFLAGS}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} $ENV{SIDE_MODULE_CXXFLAGS}")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} $ENV{SIDE_MODULE_LDFLAGS}")
