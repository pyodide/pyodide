#!/usr/bin/env bash

failure_exit() {
  echo >&2 "Could not find ${1}.  Please install that before continuing."
  exit 1
}

check_python_version() {
  if [ -z "$PYMAJOR$PYMINOR" ]; then
    echo >&2 "$0: This script expects that environment variables PYMAJOR and PYMINOR are set; skipping check_python_version"
    return
  fi
  if ! command -v python"$PYMAJOR"."$PYMINOR" &> /dev/null; then
    echo >&2 "Must compile with python $PYMAJOR.$PYMINOR."
    exit 1
  fi
}

check_python_headers() {
  if [ -z "$PYMAJOR$PYMINOR" ]; then
    echo >&2 "$0: This script expects that environment variables PYMAJOR and PYMINOR are set; skipping check_python_headers"
    return
  fi
  local python_headers_present
  python_headers_present=$(pkg-config --libs python-"$PYMAJOR"."$PYMINOR")

  if [ ! "${python_headers_present}" ]; then
    failure_exit "Python $PYMAJOR.$PYMINOR headers"
  fi
}

check_binary_present() {
  local binary_exists
  binary_exists="$(command -v "${1}")"
  if [ ! "${binary_exists}" ]; then
    failure_exit "${1}"
  fi
}

check_pkgconfig() {
  check_binary_present "pkg-config"
}

check_shasum() {
  check_binary_present "shasum"
}

check_cmake() {
  check_binary_present "cmake"

  CMAKE_FULL_VERSION=$(cmake --version | head -n1 | cut -d " " -f 3)
  CMAKE_MAJOR_VERSION=$(echo "${CMAKE_FULL_VERSION}" | cut -d "." -f 1)

  if (( "${CMAKE_MAJOR_VERSION}" != "3" )); then
    echo >&2 "Pyodide requires cmake 3."
    echo >&2 "If you are on macOS brew would install higher version. You can install it with 'pip install cmake==3.31'"
    exit 1
  fi
}

check_sed() {
  check_binary_present "sed"
  gnu_sed_found=$(sed --help | grep -q gnu.org)

  if [ "${gnu_sed_found}" ]; then
    echo >&2 "Pyodide requires GNU sed."
    echo >&2 "If you are on macOS you can install it with 'brew install gnu-sed' and then add it to your PATH."
    exit 1
  fi
}

check_patch() {
  check_binary_present "patch"
  gnu_patch_found=$(patch --help | grep -q gnu.org)

  if [ "${gnu_patch_found}" ]; then
    echo >&2 "Pyodide requires GNU patch."
    echo >&2 "If you are on macOS you can install it with 'brew install gpatch' and then add it to your PATH."
    exit 1
  fi
}

check_python_version
check_pkgconfig
check_cmake
check_sed
check_patch
#check_python_headers
check_shasum
