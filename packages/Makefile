PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all: deps
	../bin/pyodide buildall . ../build \
		--ldflags="$(SIDE_LDFLAGS)" --host=$(HOSTPYTHONROOT) --target=$(TARGETPYTHONROOT)
deps:
	# Install build dependencies
	$(HOSTPYTHON) -m pip install Cython Tempita

clean:
	rm -rf ./*/build
