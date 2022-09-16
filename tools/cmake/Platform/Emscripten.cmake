###############################################################################################
# This file is a 'toolchain description file' for CMake.                                      #
# The content of this file is mostly adapted from Emscripten CMake toolchain file,            #
# with some modifications to make it work with Pyodide build system:                          #
# - set TARGET_SUPPORTS_SHARED_LIBS to TRUE                                                   #
# - set CMAKE_INSTALL_PREFIX to WASM_LIBRARY_DIR                                              #
# - disable the usage of response file for object and libraries                               #
# - allow to overwrite CMAKE_PROJECT_INCLUDE, CMAKE_PROJECT_INCLUDE_BEFORE with env variable  #
# - append SIDE_MODULE_CFLAGS and SIDE_MODULE_LDFLAGS automatically                           #
###############################################################################################

set(CMAKE_SYSTEM_NAME Emscripten)
set(CMAKE_SYSTEM_VERSION 1)

set(CMAKE_CROSSCOMPILING TRUE)

# Note: this is False in original Emscripten toolchain,
#       however we always want to allow build shared libs
#       (See also: https://github.com/emscripten-core/emscripten/pull/16281)
set_property(GLOBAL PROPERTY TARGET_SUPPORTS_SHARED_LIBS TRUE)

# Advertise Emscripten as a 32-bit platform (as opposed to
# CMAKE_SYSTEM_PROCESSOR=x86_64 for 64-bit platform), since some projects (e.g.
# OpenCV) use this to detect bitness.
# Allow users to overwrite this on the command line with -DEMSCRIPTEN_SYSTEM_PROCESSOR=arm.
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

# Do a no-op access on the CMAKE_TOOLCHAIN_FILE variable so that CMake will not
# issue a warning on it being unused.
if (CMAKE_TOOLCHAIN_FILE)
endif()

execute_process(COMMAND "em-config" "EMSCRIPTEN_ROOT"
  RESULT_VARIABLE _emconfig_result
  OUTPUT_VARIABLE _emconfig_output
  OUTPUT_STRIP_TRAILING_WHITESPACE)
if (NOT _emconfig_result EQUAL 0)
  message(FATAL_ERROR "Failed to find emscripten root directory with command \"em-config EMSCRIPTEN_ROOT\"! Process returned with error code ${_emcache_result}.")
endif()

file(TO_CMAKE_PATH "${_emconfig_output}" _emcache_output)
set(EMSCRIPTEN_ROOT_PATH "${_emconfig_output}" CACHE FILEPATH "Path to Emscripten Root")

list(APPEND CMAKE_MODULE_PATH "${EMSCRIPTEN_ROOT_PATH}/cmake/Modules")

if (CMAKE_HOST_WIN32)
  set(EMCC_SUFFIX ".bat")
else()
  set(EMCC_SUFFIX "")
endif()

# Specify the compilers to use for C and C++
if ("${CMAKE_C_COMPILER}" STREQUAL "")
  set(CMAKE_C_COMPILER "${EMSCRIPTEN_ROOT_PATH}/emcc${EMCC_SUFFIX}" CACHE FILEPATH "Emscripten emcc")
endif()
if ("${CMAKE_CXX_COMPILER}" STREQUAL "")
  set(CMAKE_CXX_COMPILER "${EMSCRIPTEN_ROOT_PATH}/em++${EMCC_SUFFIX}" CACHE FILEPATH "Emscripten em++")
endif()

if ("${CMAKE_AR}" STREQUAL "")
  set(CMAKE_AR "${EMSCRIPTEN_ROOT_PATH}/emar${EMCC_SUFFIX}" CACHE FILEPATH "Emscripten ar")
endif()

if ("${CMAKE_RANLIB}" STREQUAL "")
  set(CMAKE_RANLIB "${EMSCRIPTEN_ROOT_PATH}/emranlib${EMCC_SUFFIX}" CACHE FILEPATH "Emscripten ranlib")
endif()

if ("${CMAKE_C_COMPILER_AR}" STREQUAL "")
  set(CMAKE_C_COMPILER_AR "${CMAKE_AR}" CACHE FILEPATH "Emscripten ar")
endif()
if ("${CMAKE_CXX_COMPILER_AR}" STREQUAL "")
  set(CMAKE_CXX_COMPILER_AR "${CMAKE_AR}" CACHE FILEPATH "Emscripten ar")
endif()
if ("${CMAKE_C_COMPILER_RANLIB}" STREQUAL "")
  set(CMAKE_C_COMPILER_RANLIB "${CMAKE_RANLIB}" CACHE FILEPATH "Emscripten ranlib")
endif()
if ("${CMAKE_CXX_COMPILER_RANLIB}" STREQUAL "")
  set(CMAKE_CXX_COMPILER_RANLIB "${CMAKE_RANLIB}" CACHE FILEPATH "Emscripten ranlib")
endif()

# Don't allow CMake to autodetect the compiler, since it does not understand
# Emscripten.
# Pass -DEMSCRIPTEN_FORCE_COMPILERS=OFF to disable (sensible mostly only for
# testing/debugging purposes).
option(EMSCRIPTEN_FORCE_COMPILERS "Force C/C++ compiler" ON)
if (EMSCRIPTEN_FORCE_COMPILERS)

  # Detect version of the 'emcc' executable. Note that for CMake, we tell it the
  # version of the Clang compiler and not the version of Emscripten, because
  # CMake understands Clang better.
  # Toolchain script is interpreted multiple times, so don't rerun the check if
  # already done before.
  if (NOT CMAKE_C_COMPILER_VERSION)
    execute_process(COMMAND "${CMAKE_C_COMPILER}" "-v" RESULT_VARIABLE _cmake_compiler_result ERROR_VARIABLE _cmake_compiler_output OUTPUT_QUIET)
    if (NOT _cmake_compiler_result EQUAL 0)
      message(FATAL_ERROR "Failed to fetch compiler version information with command \"'${CMAKE_C_COMPILER}' -v\"! Process returned with error code ${_cmake_compiler_result}.")
    endif()
    if (NOT "${_cmake_compiler_output}" MATCHES "[Ee]mscripten")
      message(FATAL_ERROR "System LLVM compiler cannot be used to build with Emscripten! Check Emscripten's LLVM toolchain location in .emscripten configuration file, and make sure to point CMAKE_C_COMPILER to where emcc is located. (was pointing to \"${CMAKE_C_COMPILER}\")")
    endif()
    string(REGEX MATCH "clang version ([0-9\\.]+)" _dummy_unused "${_cmake_compiler_output}")
    if (NOT CMAKE_MATCH_1)
      message(FATAL_ERROR "Failed to regex parse Clang compiler version from version string: ${_cmake_compiler_output}")
    endif()

    set(CMAKE_C_COMPILER_VERSION "${CMAKE_MATCH_1}")
    set(CMAKE_CXX_COMPILER_VERSION "${CMAKE_MATCH_1}")
    if (${CMAKE_C_COMPILER_VERSION} VERSION_LESS 3.9.0)
      message(WARNING "CMAKE_C_COMPILER version looks too old. Was ${CMAKE_C_COMPILER_VERSION}, should be at least 3.9.0.")
    endif()
  endif()

  # Capture the Emscripten version to EMSCRIPTEN_VERSION variable.
  if (NOT EMSCRIPTEN_VERSION)
    execute_process(COMMAND "${CMAKE_C_COMPILER}" "-v" RESULT_VARIABLE _cmake_compiler_result ERROR_VARIABLE _cmake_compiler_output OUTPUT_QUIET)
    if (NOT _cmake_compiler_result EQUAL 0)
      message(FATAL_ERROR "Failed to fetch Emscripten version information with command \"'${CMAKE_C_COMPILER}' -v\"! Process returned with error code ${_cmake_compiler_result}.")
    endif()
    string(REGEX MATCH "emcc \\(.*\\) ([0-9\\.]+)" _dummy_unused "${_cmake_compiler_output}")
    if (NOT CMAKE_MATCH_1)
      message(FATAL_ERROR "Failed to regex parse Emscripten compiler version from version string: ${_cmake_compiler_output}")
    endif()

    set(EMSCRIPTEN_VERSION "${CMAKE_MATCH_1}")
  endif()

  set(CMAKE_C_COMPILER_ID_RUN TRUE)
  set(CMAKE_C_COMPILER_FORCED TRUE)
  set(CMAKE_C_COMPILER_WORKS TRUE)
  set(CMAKE_C_COMPILER_ID Clang)
  set(CMAKE_C_COMPILER_FRONTEND_VARIANT GNU)
  set(CMAKE_C_STANDARD_COMPUTED_DEFAULT 11)

  set(CMAKE_CXX_COMPILER_ID_RUN TRUE)
  set(CMAKE_CXX_COMPILER_FORCED TRUE)
  set(CMAKE_CXX_COMPILER_WORKS TRUE)
  set(CMAKE_CXX_COMPILER_ID Clang)
  set(CMAKE_CXX_COMPILER_FRONTEND_VARIANT GNU)
  set(CMAKE_CXX_STANDARD_COMPUTED_DEFAULT 98)

  set(CMAKE_C_PLATFORM_ID "emscripten")
  set(CMAKE_CXX_PLATFORM_ID "emscripten")

  if ("${CMAKE_VERSION}" VERSION_LESS "3.8")
    set(CMAKE_C_COMPILE_FEATURES "c_function_prototypes;c_restrict;c_variadic_macros;c_static_assert")
    set(CMAKE_C90_COMPILE_FEATURES "c_function_prototypes")
    set(CMAKE_C99_COMPILE_FEATURES "c_restrict;c_variadic_macros")
    set(CMAKE_C11_COMPILE_FEATURES "c_static_assert")

    set(CMAKE_CXX_COMPILE_FEATURES "cxx_template_template_parameters;cxx_alias_templates;cxx_alignas;cxx_alignof;cxx_attributes;cxx_auto_type;cxx_constexpr;cxx_decltype;cxx_decltype_incomplete_return_types;cxx_default_function_template_args;cxx_defaulted_functions;cxx_defaulted_move_initializers;cxx_delegating_constructors;cxx_deleted_functions;cxx_enum_forward_declarations;cxx_explicit_conversions;cxx_extended_friend_declarations;cxx_extern_templates;cxx_final;cxx_func_identifier;cxx_generalized_initializers;cxx_inheriting_constructors;cxx_inline_namespaces;cxx_lambdas;cxx_local_type_template_args;cxx_long_long_type;cxx_noexcept;cxx_nonstatic_member_init;cxx_nullptr;cxx_override;cxx_range_for;cxx_raw_string_literals;cxx_reference_qualified_functions;cxx_right_angle_brackets;cxx_rvalue_references;cxx_sizeof_member;cxx_static_assert;cxx_strong_enums;cxx_thread_local;cxx_trailing_return_types;cxx_unicode_literals;cxx_uniform_initialization;cxx_unrestricted_unions;cxx_user_literals;cxx_variadic_macros;cxx_variadic_templates;cxx_aggregate_default_initializers;cxx_attribute_deprecated;cxx_binary_literals;cxx_contextual_conversions;cxx_decltype_auto;cxx_digit_separators;cxx_generic_lambdas;cxx_lambda_init_captures;cxx_relaxed_constexpr;cxx_return_type_deduction;cxx_variable_templates")
    set(CMAKE_CXX98_COMPILE_FEATURES "cxx_template_template_parameters")
    set(CMAKE_CXX11_COMPILE_FEATURES "cxx_alias_templates;cxx_alignas;cxx_alignof;cxx_attributes;cxx_auto_type;cxx_constexpr;cxx_decltype;cxx_decltype_incomplete_return_types;cxx_default_function_template_args;cxx_defaulted_functions;cxx_defaulted_move_initializers;cxx_delegating_constructors;cxx_deleted_functions;cxx_enum_forward_declarations;cxx_explicit_conversions;cxx_extended_friend_declarations;cxx_extern_templates;cxx_final;cxx_func_identifier;cxx_generalized_initializers;cxx_inheriting_constructors;cxx_inline_namespaces;cxx_lambdas;cxx_local_type_template_args;cxx_long_long_type;cxx_noexcept;cxx_nonstatic_member_init;cxx_nullptr;cxx_override;cxx_range_for;cxx_raw_string_literals;cxx_reference_qualified_functions;cxx_right_angle_brackets;cxx_rvalue_references;cxx_sizeof_member;cxx_static_assert;cxx_strong_enums;cxx_thread_local;cxx_trailing_return_types;cxx_unicode_literals;cxx_uniform_initialization;cxx_unrestricted_unions;cxx_user_literals;cxx_variadic_macros;cxx_variadic_templates")
    set(CMAKE_CXX14_COMPILE_FEATURES "cxx_aggregate_default_initializers;cxx_attribute_deprecated;cxx_binary_literals;cxx_contextual_conversions;cxx_decltype_auto;cxx_digit_separators;cxx_generic_lambdas;cxx_lambda_init_captures;cxx_relaxed_constexpr;cxx_return_type_deduction;cxx_variable_templates")
  else() # 3.8+
    set(CMAKE_C90_COMPILE_FEATURES "c_std_90;c_function_prototypes")
    set(CMAKE_C99_COMPILE_FEATURES "c_std_99;c_restrict;c_variadic_macros")
    set(CMAKE_C11_COMPILE_FEATURES "c_std_11;c_static_assert")

    set(CMAKE_CXX98_COMPILE_FEATURES "cxx_std_98;cxx_template_template_parameters")
    set(CMAKE_CXX11_COMPILE_FEATURES "cxx_std_11;cxx_alias_templates;cxx_alignas;cxx_alignof;cxx_attributes;cxx_auto_type;cxx_constexpr;cxx_decltype;cxx_decltype_incomplete_return_types;cxx_default_function_template_args;cxx_defaulted_functions;cxx_defaulted_move_initializers;cxx_delegating_constructors;cxx_deleted_functions;cxx_enum_forward_declarations;cxx_explicit_conversions;cxx_extended_friend_declarations;cxx_extern_templates;cxx_final;cxx_func_identifier;cxx_generalized_initializers;cxx_inheriting_constructors;cxx_inline_namespaces;cxx_lambdas;cxx_local_type_template_args;cxx_long_long_type;cxx_noexcept;cxx_nonstatic_member_init;cxx_nullptr;cxx_override;cxx_range_for;cxx_raw_string_literals;cxx_reference_qualified_functions;cxx_right_angle_brackets;cxx_rvalue_references;cxx_sizeof_member;cxx_static_assert;cxx_strong_enums;cxx_thread_local;cxx_trailing_return_types;cxx_unicode_literals;cxx_uniform_initialization;cxx_unrestricted_unions;cxx_user_literals;cxx_variadic_macros;cxx_variadic_templates")
    set(CMAKE_CXX14_COMPILE_FEATURES "cxx_std_14;cxx_aggregate_default_initializers;cxx_attribute_deprecated;cxx_binary_literals;cxx_contextual_conversions;cxx_decltype_auto;cxx_digit_separators;cxx_generic_lambdas;cxx_lambda_init_captures;cxx_relaxed_constexpr;cxx_return_type_deduction;cxx_variable_templates")
    set(CMAKE_CXX17_COMPILE_FEATURES "cxx_std_17")
    if ("${CMAKE_VERSION}" VERSION_LESS "3.12") # [3.8, 3.12)
      set(CMAKE_C_COMPILE_FEATURES "c_std_90;c_function_prototypes;c_std_99;c_restrict;c_variadic_macros;c_std_11;c_static_assert")
      set(CMAKE_CXX_COMPILE_FEATURES "cxx_std_98;cxx_template_template_parameters;cxx_std_11;cxx_alias_templates;cxx_alignas;cxx_alignof;cxx_attributes;cxx_auto_type;cxx_constexpr;cxx_decltype;cxx_decltype_incomplete_return_types;cxx_default_function_template_args;cxx_defaulted_functions;cxx_defaulted_move_initializers;cxx_delegating_constructors;cxx_deleted_functions;cxx_enum_forward_declarations;cxx_explicit_conversions;cxx_extended_friend_declarations;cxx_extern_templates;cxx_final;cxx_func_identifier;cxx_generalized_initializers;cxx_inheriting_constructors;cxx_inline_namespaces;cxx_lambdas;cxx_local_type_template_args;cxx_long_long_type;cxx_noexcept;cxx_nonstatic_member_init;cxx_nullptr;cxx_override;cxx_range_for;cxx_raw_string_literals;cxx_reference_qualified_functions;cxx_right_angle_brackets;cxx_rvalue_references;cxx_sizeof_member;cxx_static_assert;cxx_strong_enums;cxx_thread_local;cxx_trailing_return_types;cxx_unicode_literals;cxx_uniform_initialization;cxx_unrestricted_unions;cxx_user_literals;cxx_variadic_macros;cxx_variadic_templates;cxx_std_14;cxx_aggregate_default_initializers;cxx_attribute_deprecated;cxx_binary_literals;cxx_contextual_conversions;cxx_decltype_auto;cxx_digit_separators;cxx_generic_lambdas;cxx_lambda_init_captures;cxx_relaxed_constexpr;cxx_return_type_deduction;cxx_variable_templates;cxx_std_17")
    else() # 3.12+
      set(CMAKE_CXX20_COMPILE_FEATURES "cxx_std_20")
      if ("${CMAKE_VERSION}" VERSION_LESS "3.20") # [3.12, 3.20)
        set(CMAKE_C_COMPILE_FEATURES "c_std_90;c_function_prototypes;c_std_99;c_restrict;c_variadic_macros;c_std_11;c_static_assert")
        set(CMAKE_CXX_COMPILE_FEATURES "cxx_std_98;cxx_template_template_parameters;cxx_std_11;cxx_alias_templates;cxx_alignas;cxx_alignof;cxx_attributes;cxx_auto_type;cxx_constexpr;cxx_decltype;cxx_decltype_incomplete_return_types;cxx_default_function_template_args;cxx_defaulted_functions;cxx_defaulted_move_initializers;cxx_delegating_constructors;cxx_deleted_functions;cxx_enum_forward_declarations;cxx_explicit_conversions;cxx_extended_friend_declarations;cxx_extern_templates;cxx_final;cxx_func_identifier;cxx_generalized_initializers;cxx_inheriting_constructors;cxx_inline_namespaces;cxx_lambdas;cxx_local_type_template_args;cxx_long_long_type;cxx_noexcept;cxx_nonstatic_member_init;cxx_nullptr;cxx_override;cxx_range_for;cxx_raw_string_literals;cxx_reference_qualified_functions;cxx_right_angle_brackets;cxx_rvalue_references;cxx_sizeof_member;cxx_static_assert;cxx_strong_enums;cxx_thread_local;cxx_trailing_return_types;cxx_unicode_literals;cxx_uniform_initialization;cxx_unrestricted_unions;cxx_user_literals;cxx_variadic_macros;cxx_variadic_templates;cxx_std_14;cxx_aggregate_default_initializers;cxx_attribute_deprecated;cxx_binary_literals;cxx_contextual_conversions;cxx_decltype_auto;cxx_digit_separators;cxx_generic_lambdas;cxx_lambda_init_captures;cxx_relaxed_constexpr;cxx_return_type_deduction;cxx_variable_templates;cxx_std_17;cxx_std_20")
      else() # 3.20+
        set(CMAKE_CXX23_COMPILE_FEATURES "cxx_std_23")
        set(CMAKE_CXX_COMPILE_FEATURES "cxx_std_98;cxx_template_template_parameters;cxx_std_11;cxx_alias_templates;cxx_alignas;cxx_alignof;cxx_attributes;cxx_auto_type;cxx_constexpr;cxx_decltype;cxx_decltype_incomplete_return_types;cxx_default_function_template_args;cxx_defaulted_functions;cxx_defaulted_move_initializers;cxx_delegating_constructors;cxx_deleted_functions;cxx_enum_forward_declarations;cxx_explicit_conversions;cxx_extended_friend_declarations;cxx_extern_templates;cxx_final;cxx_func_identifier;cxx_generalized_initializers;cxx_inheriting_constructors;cxx_inline_namespaces;cxx_lambdas;cxx_local_type_template_args;cxx_long_long_type;cxx_noexcept;cxx_nonstatic_member_init;cxx_nullptr;cxx_override;cxx_range_for;cxx_raw_string_literals;cxx_reference_qualified_functions;cxx_right_angle_brackets;cxx_rvalue_references;cxx_sizeof_member;cxx_static_assert;cxx_strong_enums;cxx_thread_local;cxx_trailing_return_types;cxx_unicode_literals;cxx_uniform_initialization;cxx_unrestricted_unions;cxx_user_literals;cxx_variadic_macros;cxx_variadic_templates;cxx_std_14;cxx_aggregate_default_initializers;cxx_attribute_deprecated;cxx_binary_literals;cxx_contextual_conversions;cxx_decltype_auto;cxx_digit_separators;cxx_generic_lambdas;cxx_lambda_init_captures;cxx_relaxed_constexpr;cxx_return_type_deduction;cxx_variable_templates;cxx_std_17;cxx_std_20;cxx_std_23")
        if ("${CMAKE_VERSION}" VERSION_LESS "3.21") # 3.20
          set(CMAKE_C_COMPILE_FEATURES "c_std_90;c_function_prototypes;c_std_99;c_restrict;c_variadic_macros;c_std_11;c_static_assert")
        else() # 3.21+
          set(CMAKE_C17_COMPILE_FEATURES "c_std_17")
          set(CMAKE_C23_COMPILE_FEATURES "c_std_23")
          set(CMAKE_C_COMPILE_FEATURES "c_std_90;c_function_prototypes;c_std_99;c_restrict;c_variadic_macros;c_std_11;c_static_assert;c_std_17;c_std_23")
        endif()
      endif()
    endif()
  endif()
endif()

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

# We build libraries into WASM_LIBRARY_DIR, so lets tell CMake
# to find libraries from there.
if (NOT "$ENV{WASM_LIBRARY_DIR}" STREQUAL "")
  list(APPEND CMAKE_FIND_ROOT_PATH "$ENV{WASM_LIBRARY_DIR}")
  if (CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
    set(CMAKE_INSTALL_PREFIX "$ENV{WASM_LIBRARY_DIR}" CACHE PATH
      "Install path prefix, prepended onto install directories." FORCE)
  endif()
endif()

if ($ENV{CFLAGS} MATCHES "MEMORY64")
  set(CMAKE_LIBRARY_ARCHITECTURE "wasm64-emscripten")
else()
  set(CMAKE_LIBRARY_ARCHITECTURE "wasm32-emscripten")
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

# Allow some of the variables to be overridden by the user by env variable
if ("${CMAKE_PROJECT_INCLUDE_BEFORE}" STREQUAL "" AND DEFINED ENV{CMAKE_PROJECT_INCLUDE_BEFORE})
  message(STATUS "Set CMAKE_PROJECT_INCLUDE_BEFORE to $ENV{CMAKE_PROJECT_INCLUDE_BEFORE} using env variable")
  set(CMAKE_PROJECT_INCLUDE_BEFORE "$ENV{CMAKE_PROJECT_INCLUDE_BEFORE}")
endif()

if ("${CMAKE_PROJECT_INCLUDE}" STREQUAL ""  AND DEFINED ENV{CMAKE_PROJECT_INCLUDE})
  message(STATUS "Set CMAKE_PROJECT_INCLUDE to $ENV{CMAKE_PROJECT_INCLUDE} using env variable")
  set(CMAKE_PROJECT_INCLUDE "$ENV{CMAKE_PROJECT_INCLUDE}")
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

option(EMSCRIPTEN_GENERATE_BITCODE_STATIC_LIBRARIES "If set, static library targets generate LLVM bitcode files (.bc). If disabled (default), UNIX ar archives (.a) are generated." OFF)
if (EMSCRIPTEN_GENERATE_BITCODE_STATIC_LIBRARIES)
  message(FATAL_ERROR "EMSCRIPTEN_GENERATE_BITCODE_STATIC_LIBRARIES is not compatible with the llvm backend")
endif()

set(CMAKE_EXECUTABLE_SUFFIX ".js")

# Note: Disable the usage of response file so objects are exposed to the commandline.
#       Our export calculation logic in pywasmcross needs to read object files.
set(CMAKE_C_USE_RESPONSE_FILE_FOR_LIBRARIES 0)
set(CMAKE_CXX_USE_RESPONSE_FILE_FOR_LIBRARIES 0)
set(CMAKE_C_USE_RESPONSE_FILE_FOR_OBJECTS 0)
set(CMAKE_CXX_USE_RESPONSE_FILE_FOR_OBJECTS 0)
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

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} $ENV{SIDE_MODULE_CFLAGS}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} $ENV{SIDE_MODULE_CXXFLAGS}")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} $ENV{SIDE_MODULE_LDFLAGS}")

if (NOT DEFINED CMAKE_CROSSCOMPILING_EMULATOR)
  find_program(NODE_JS_EXECUTABLE NAMES nodejs node)
  if(NODE_JS_EXECUTABLE)
    set(CMAKE_CROSSCOMPILING_EMULATOR "${NODE_JS_EXECUTABLE}" CACHE FILEPATH "Path to the emulator for the target system.")
  endif()
endif()

# No-op on CMAKE_CROSSCOMPILING_EMULATOR so older versions of cmake do not
# complain about unused CMake variable.
if (CMAKE_CROSSCOMPILING_EMULATOR)
endif()

# TODO: CMake appends <sysroot>/usr/include to implicit includes; switching to use usr/include will make this redundant.
if ("${CMAKE_C_IMPLICIT_INCLUDE_DIRECTORIES}" STREQUAL "")
  set(CMAKE_C_IMPLICIT_INCLUDE_DIRECTORIES "${EMSCRIPTEN_SYSROOT}/include")
endif()
if ("${CMAKE_CXX_IMPLICIT_INCLUDE_DIRECTORIES}" STREQUAL "")
  set(CMAKE_CXX_IMPLICIT_INCLUDE_DIRECTORIES "${EMSCRIPTEN_SYSROOT}/include")
endif()
unset(_em_sysroot_include)
