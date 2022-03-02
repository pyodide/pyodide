export PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

ifeq ($(strip $(PYODIDE_PACKAGES)),)
else
	ONLY_PACKAGES=--only "$(PYODIDE_PACKAGES)"
endif

SP1=$(HOSTINSTALLDIR)/lib/$(PY_MAJOR).$(PY_MINOR)/site-packages/
SP2=$(HOSTINSTALLDIR)/usr/local/lib/$(PY_MAJOR_MINOR)/site-packages/
SPBOTH=$(SP1):$(SP2)

all: .artifacts/bin/pyodide-build
	mkdir -p build-logs
	PYTHONPATH="$(SPBOTH):$(PYODIDE_ROOT)/pyodide-build/"\
		python -m pyodide_build buildall . ../build \
		$(ONLY_PACKAGES) --n-jobs $${PYODIDE_JOBS:-4} \
		--log-dir=build-logs

.artifacts/bin/pyodide-build: ../pyodide-build/pyodide_build/**
	mkdir -p $(HOSTINSTALLDIR)
	$(HOSTPYTHON) -m pip install -e ../pyodide-build --no-deps --prefix $(HOSTINSTALLDIR)

update-all:
	for pkg in $$(find . -maxdepth 1 ! -name ".*" -type d -exec basename {} \; | tail -n +2); do \
		python -m pyodide_build mkpkg "$${pkg}" --update; \
	done

clean:
	rm -rf ./*/build ./*/build.log ./*/dist
	rm -rf ./.artifacts
