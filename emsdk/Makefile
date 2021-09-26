PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all: emsdk/.complete

emsdk/.complete: ../Makefile.envs $(wildcard patches/*.patch)
	if [ -d emsdk ]; then rm -rf emsdk; fi
	git clone --depth 1 https://github.com/emscripten-core/emsdk.git
	cd emsdk && ./emsdk install --build=Release $(PYODIDE_EMSCRIPTEN_VERSION) ccache-git-emscripten-64bit
	git clone https://github.com/WebAssembly/binaryen.git emsdk/binaryen
	cd emsdk/binaryen && git checkout $(PYODIDE_BINARYEN_VERSION)
	cat patches/*.patch | patch -p1
	cd emsdk && ./emsdk activate --embedded --build=Release $(PYODIDE_EMSCRIPTEN_VERSION)
	cd emsdk/binaryen && cmake -DBUILD_STATIC_LIB=ON -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
	make -C emsdk/binaryen -j5 wasm-opt
	cp emsdk/binaryen/bin/wasm-opt emsdk/upstream/bin/
	touch emsdk/.complete

.PHONY: test
test:
	pytest tests/ -v

clean:
	rm -rf emsdk
