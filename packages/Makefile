export PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

export NUMPY_LIB=$(PYODIDE_ROOT)/packages/numpy/build/numpy-1.21.4/install/lib/python$(PYMAJOR).$(PYMINOR)/site-packages/numpy/core/lib/


ifeq ($(strip $(PYODIDE_PACKAGES)),)
else
	ONLY_PACKAGES=--only "$(PYODIDE_PACKAGES)"
endif

all: .artifacts/bin/pyodide-build
	mkdir -p build-logs
	echo PYTHONPATH="$(HOSTINSTALLDIR)/lib/python:$(PYODIDE_ROOT)/pyodide-build/"
	PYTHONPATH="$(HOSTINSTALLDIR)/lib/python:$(PYODIDE_ROOT)/pyodide-build/" python -m pyodide_build buildall . ../build \
		$(ONLY_PACKAGES) --n-jobs $${PYODIDE_JOBS:-4} \
		--log-dir=build-logs

.artifacts/bin/pyodide-build: ../pyodide-build/pyodide_build/**
	mkdir -p $(HOSTINSTALLDIR)
	$(HOSTPYTHON) -m pip install -e ../pyodide-build --no-deps --prefix $(HOSTINSTALLDIR)

update-all:
	for pkg in $$(find . -maxdepth 1 ! -name ".*" -type d -exec basename {} \; | tail -n +2); do \
		pyodide-build mkpkg "$${pkg}" --update; \
	done

clean:
	rm -rf ./*/build ./*/build.log
	rm -rf ./.artifacts
