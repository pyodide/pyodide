#!/usr/bin/env bash

failure_exit() {
  echo >&2 "Could not find ${1}.  Please install that before continuing."
  exit 1
}

check_python_version() {
  if ! command -v python3.9 &> /dev/null; then
    echo >&2 "Must compile with python 3.9."
    exit 1
  fi
}
check_python_headers() {
  local python_headers_present
  python_headers_present="$(pkg-config --libs python-3.9)"

  if [ ! "${python_headers_present}" ]; then
    failure_exit "Python 3.9 headers"
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

check_md5sum() {
  check_binary_present "md5sum"
}

check_fortran_dependencies() {
  check_binary_present "gfortran"
  check_binary_present "f2c"
}

check_pyyaml() {
  local pyyaml_import_check
  pyyaml_import_check="$(python3 -c 'import yaml' 2>&1)"
  if [ "${pyyaml_import_check}" ]; then
    failure_exit "PyYAML"
  fi
}

check_python_version
check_pkgconfig
#check_python_headers
check_fortran_dependencies
check_pyyaml
check_md5sum
