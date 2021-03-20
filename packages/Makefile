export PYODIDE_ROOT=$(abspath ..)
PYODIDE_LIBRARIES=$(abspath ./.artifacts)
include ../Makefile.envs

ifeq ($(strip $(PYODIDE_PACKAGES)),)
else
	ONLY_PACKAGES=--only "$(PYODIDE_PACKAGES)"
endif

all:
	mkdir -p $(PYODIDE_LIBRARIES)
	PYTHONPATH=$(PYODIDE_LIBRARIES)/lib/python ../bin/pyodide buildall . ../build \
		--target=$(TARGETPYTHONROOT) $(ONLY_PACKAGES) --install-dir $(PYODIDE_LIBRARIES)


update-all:
	for pkg in $$(find . -maxdepth 1 -type d -exec basename {} \; | tail -n +2); do \
		../bin/pyodide mkpkg "$${pkg}" --update; \
	done

clean:
	rm -rf ./*/build ./*/build.log
	rm -rf ./.artifacts
