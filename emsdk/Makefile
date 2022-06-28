PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all: copy-ports emsdk/.complete

emsdk/.complete: ../Makefile.envs $(wildcard patches/*.patch)
	if [ -d emsdk ]; then rm -rf emsdk; fi
	git clone --depth 1 https://github.com/emscripten-core/emsdk.git
	cd emsdk && ./emsdk install --build=Release $(PYODIDE_EMSCRIPTEN_VERSION)
	cd emsdk/upstream/emscripten/ && cat ../../../patches/*.patch | patch -p1 --verbose
	cd emsdk && ./emsdk install --build=Release $(PYODIDE_EMSCRIPTEN_VERSION) ccache-git-emscripten-64bit
	cd emsdk && ./emsdk activate --embedded --build=Release $(PYODIDE_EMSCRIPTEN_VERSION)
	touch emsdk/.complete

.PHONY: copy-ports
copy-ports: emsdk/.complete
	cp ports/*.py emsdk/upstream/emscripten/tools/ports

clean:
	rm -rf emsdk
