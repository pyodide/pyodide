#!/usr/bin/env bash

failure_exit() {
  echo >&2 "Could not find ${1}.  Please install that before continuing."
  exit 1
}

check_python_version() {
  if ! command -v python"$PYMAJOR"."$PYMINOR" &> /dev/null; then
    echo >&2 "Must compile with python $PYMAJOR.$PYMINOR."
    exit 1
  fi
}
check_python_headers() {
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
}

check_python_version
check_pkgconfig
check_cmake
#check_python_headers
check_shasum
