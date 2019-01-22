PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all: deps
	../bin/pyodide buildall . ../build \
		--package_abi=$(PYODIDE_PACKAGE_ABI) --ldflags="$(SIDE_LDFLAGS)" --host=$(HOSTPYTHONROOT) --target=$(TARGETPYTHONROOT)
deps:
	# Install build dependencies
	$(HOSTPYTHON) -m pip install Cython Tempita

clean:
	rm -rf ./*/build
