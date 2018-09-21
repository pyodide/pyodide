PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all:
	python -m pyodide_build buildall . ../build \
		--ldflags="$(SIDE_LDFLAGS)" --host=$(HOSTPYTHONROOT) --target=$(TARGETPYTHONROOT)

clean:
	rm -rf ./*/build
