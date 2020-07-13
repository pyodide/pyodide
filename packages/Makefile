PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all: deps
	../bin/pyodide buildall . ../build \
		--package_abi=$(PYODIDE_PACKAGE_ABI) --ldflags="$(SIDE_LDFLAGS)" --host=$(HOSTPYTHONROOT) --target=$(TARGETPYTHONROOT) --only $(PYODIDE_PACKAGES)

update-all:
	for pkg in $$(find . -maxdepth 1 -type d -exec basename {} \; | tail -n +2); do \
		../bin/pyodide mkpkg "$${pkg}" --update; \
	done

deps:
	# Install build dependencies
	$(HOSTPYTHON) -m pip install "Cython<0.30.0" Tempita

clean:
	rm -rf ./*/build
