export PYODIDE_ROOT=$(abspath ..)
PYODIDE_LIBRARIES=$(abspath ./.artifacts)
CPYTHONROOT=$(PYODIDE_ROOT)/cpython
include ../Makefile.envs

export NUMPY_LIB=$(PYODIDE_ROOT)/packages/numpy/build/numpy-1.21.4/build/temp.emscripten_wasm32-3.9/


ifeq ($(strip $(PYODIDE_PACKAGES)),)
else
	ONLY_PACKAGES=--only "$(PYODIDE_PACKAGES)"
endif

all: .artifacts/bin/pyodide-build .artifacts/bin/wheel
	mkdir -p build-logs
	PYTHONPATH="$(PYODIDE_LIBRARIES)/lib/python:$(PYODIDE_ROOT)/pyodide-build/" pyodide-build buildall . ../build \
		--target=$(TARGETPYTHONROOT) $(ONLY_PACKAGES) --install-dir $(PYODIDE_LIBRARIES) --n-jobs $${PYODIDE_JOBS:-4} \
		--log-dir=build-logs

.artifacts/bin/pyodide-build: ../pyodide-build/pyodide_build/**
	mkdir -p $(PYODIDE_LIBRARIES)
	$(HOSTPYTHON) -m pip install -e ../pyodide-build --no-deps --prefix $(PYODIDE_LIBRARIES)

.artifacts/bin/wheel:
	# For the moment we need a fork of the wheel package because it doesn't properly handle commas in file names.
	# statsmodels has commas in file names, so this fork is resiliant to that.
	# See my PR here: https://github.com/pypa/wheel/pull/427
	git clone https://github.com/hoodmane/wheel.git --branch handle-files-with-commas --depth 1 .artifacts/bin/wheel

update-all:
	for pkg in $$(find . -maxdepth 1 ! -name ".*" -type d -exec basename {} \; | tail -n +2); do \
		pyodide-build mkpkg "$${pkg}" --update; \
	done

clean:
	rm -rf ./*/build ./*/build.log ./*/dist
	rm -rf ./.artifacts
