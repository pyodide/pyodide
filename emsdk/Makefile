PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all: emsdk/.complete

emsdk/.complete: ../Makefile.envs $(wildcard patches/*.patch)
	if [ -d emsdk ]; then rm -rf emsdk; fi
	git clone --depth 1 https://github.com/emscripten-core/emsdk.git
	cd emsdk && ./emsdk install --build=Release $(PYODIDE_EMSCRIPTEN_VERSION)
	cat patches/*.patch | patch -p1
	cd emsdk && ./emsdk install --build=Release $(PYODIDE_EMSCRIPTEN_VERSION) ccache-git-emscripten-64bit
	cd emsdk && ./emsdk activate --embedded --build=Release $(PYODIDE_EMSCRIPTEN_VERSION)
	touch emsdk/.complete

clean:
	rm -rf emsdk
