# New Pyodide CLI design document

This document describes the new CLI for Pyodide.

> Note: This document is inspired from the new [scipy](https://github.com/scipy/scipy/issues/15489) CLI RFC.

- Related issue: [#1977](https://github.com/pyodide/pyodide/issues/1977)

## Goal

The goal of introducing a new CLI is to unify all developer tools for building and testing Pyodide,
which gives a better user/developer performance.

Currently, we have several tools such as:

- `make`: to build Pyodide
- `pyodide-build`: to deal with packages, often used in Makefile internally, but also used as a command-line tool.
- `pytest` or `tools/pytest_wrapper.py`: to run tests
- `benchmark.py` or `make benchmark`: to run the benchmark
- `sphinx (make html)`: to build a document

## Requirements

The required properties or the new CLI are:

- Completeness: we have all development tasks implemented in it
- Hierarchical: if there are several build-related tasks, they should be discoverable and runnable like: pyodide build python, pyodide build numpy
- Easy-to-use: one should easily discover how to use CLI commands, and it needs a simple way to install.
- Easy-to-extend: it should be easy for one can add a new command/subcommand.

## CLI Commands

- `pyodide build`: Build pyodide components. The types of components can be specified as arguments

  - e.g.) pyodide build: build all components
  - e.g.) pyodide build python: build cpython
  - e.g.) pyodide build numpy pandas: build numpy and pandas

- `pyodide generate`: From built components, generate a distribution.

- `pyodide package`

  - `pyodide package new`: Create a new Pyodide Package, replacing `pyodide-build mkpkg`
  - `pyodide package update`: Update an existing Pyodide Package, replacing `pyodide-build mkpkg --update`

- `pyodide clean`: clean build components

  - `pyodide clean package numpy pandas`
  - `pyodide clean python`
  - `pyodide clean emsdk`

- `pyodide test`: Replaces `pytest` and `tools/pytest_wrapper.py`

  - `pyodide test --retry`

- `pyodide benchmark`
  - `pyodide benchmark numpy`
  - `pyodide benchmakr matplotlib`
  - ...

### Non-primary CLI commands

- `pyodide serve`: Run a simple HTTP server serving Pyodide components.

  - `pyodide serve --open-console`

- `pyodide builddoc`: Build Pyodide documents

  - `pyodide builddoc --serve`

- `pyodide check`: Check build dependencies

- `pyodide install`: Install build dependencies

- `pyodide package list`: List Pyodide packages

- `pyodide package get`: Get Pyodide package from 3rdparty repository

- ...

## Global Config File for Pyodide

A global config file for Pyodide, possibly `pyodide.[json|yml|toml]`.

This config file is used for the new CLI to decide build options, packages to be built, debug options,
experimental build flags (threading enabled/disabled, ...).

In the future, if we support out-of-tree build (per-package build), this config file may exist per each project.

```yml
# example config
build:
  - debug: true
  - optimization: -O2
package:
  - micropip
  - numpy
  - pandas
experimental:
  - enable-threading: true
  - enable-socket: true
```

## CHANGELOG

- 05/17/2022: Initial draft
