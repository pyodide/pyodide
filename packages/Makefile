export PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

ifeq ($(strip $(PYODIDE_PACKAGES)),)
else
	ONLY_PACKAGES=--only "$(PYODIDE_PACKAGES)"
endif


all: .artifacts/bin/pyodide-build
	PYTHONPATH="$(PYODIDE_ROOT)/pyodide-build/"\
		python -m pyodide_build buildall . ../build \
		$(ONLY_PACKAGES) --n-jobs $${PYODIDE_JOBS:-4} \
		--log-dir=./build-logs

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
