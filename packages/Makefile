PYODIDE_ROOT=$(abspath ..)
PYODIDE_LIBRARIES=$(abspath ./.artifacts)
include ../Makefile.envs

all:
	mkdir -p $(PYODIDE_LIBRARIES)
	PYTHONPATH=$(PYODIDE_LIBRARIES)/lib/python ../bin/pyodide buildall . ../build \
		--package_abi=$(PYODIDE_PACKAGE_ABI) --target=$(TARGETPYTHONROOT) --only $(PYODIDE_PACKAGES) --install-dir $(PYODIDE_LIBRARIES)

update-all:
	for pkg in $$(find . -maxdepth 1 -type d -exec basename {} \; | tail -n +2); do \
		../bin/pyodide mkpkg "$${pkg}" --update; \
	done

clean:
	rm -rf ./*/build ./*/build.log
	rm -rf ./.artifacts
