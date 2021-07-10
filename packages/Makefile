export PYODIDE_ROOT=$(abspath ..)
PYODIDE_LIBRARIES=$(abspath ./.artifacts)
include ../Makefile.envs

export NUMPY_LIB=$(PYODIDE_ROOT)/packages/numpy/build/numpy-1.17.5/install/lib/python$(PYMAJOR).$(PYMINOR)/site-packages/numpy/core/lib/


ifeq ($(strip $(PYODIDE_PACKAGES)),)
else
	ONLY_PACKAGES=--only "$(PYODIDE_PACKAGES)"
endif

all: .artifacts/bin/pyodide-build
	mkdir -p build-logs
	PYTHONPATH="$(PYODIDE_LIBRARIES)/lib/python:$(PYODIDE_ROOT)/pyodide-build/" pyodide-build buildall . ../build \
		--target=$(TARGETPYTHONROOT) $(ONLY_PACKAGES) --install-dir $(PYODIDE_LIBRARIES) --n-jobs $${PYODIDE_JOBS:-4} \
		--log-dir=build-logs

.artifacts/bin/pyodide-build: ../pyodide-build/pyodide_build/**
	mkdir -p $(PYODIDE_LIBRARIES)
	python3 -m pip install -e ../pyodide-build --no-deps --prefix $(PYODIDE_LIBRARIES)

update-all:
	for pkg in $$(find . -maxdepth 1 ! -name ".*" -type d -exec basename {} \; | tail -n +2); do \
		pyodide-build mkpkg "$${pkg}" --update; \
	done

clean:
	rm -rf ./*/build ./*/build.log
	rm -rf ./.artifacts
