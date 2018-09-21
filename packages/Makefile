PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all:
	../bin/pyodide buildall . ../build \
		--ldflags="$(SIDE_LDFLAGS)" --host=$(HOSTPYTHONROOT) --target=$(TARGETPYTHONROOT)

clean:
	rm -rf ./*/build
