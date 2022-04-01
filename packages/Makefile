.PHONY=pyodide-build

export PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

ifeq ($(strip $(PYODIDE_PACKAGES)),)
else
	ONLY_PACKAGES=--only "$(PYODIDE_PACKAGES)"
endif

all: pyodide-build
	PYODIDE_ROOT=$(PYODIDE_ROOT) python -m pyodide_build buildall . $(PYODIDE_ROOT)/build \
	$(ONLY_PACKAGES) --n-jobs $${PYODIDE_JOBS:-4} \
	--log-dir=./build-logs

pyodide-build: ../pyodide-build/pyodide_build/**
	mkdir -p $(HOSTINSTALLDIR)
	$(HOSTPYTHON) -m pip install -q --user --upgrade --force-reinstall ../pyodide-build

update-all:
	for pkg in $$(find . -maxdepth 1 ! -name ".*" -type d -exec basename {} \; | tail -n +2); do \
		PYODIDE_ROOT=$(PYODIDE_ROOT) python -m pyodide_build mkpkg "$${pkg}" --update; \
	done

clean:
	rm -rf ./*/build ./*/build.log ./*/dist
	rm -rf ./.artifacts
