PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

export PATH := /usr/lib/ccache:$(PATH)

all: emsdk/.complete

emsdk/.complete: ../Makefile.envs $(wildcard patches/*.patch)
	if [ -d emsdk ]; then rm -rf emsdk; fi
	git clone --depth 1 https://github.com/emscripten-core/emsdk.git
	cd emsdk && ./emsdk install --build=Release $(EMSCRIPTEN_VERSION)
	git clone -b $(BINARYEN_VERSION) --depth 1 https://github.com/WebAssembly/binaryen.git emsdk/binaryen
	cat patches/*.patch | patch -p1
	cd emsdk && ./emsdk activate --embedded --build=Release $(EMSCRIPTEN_VERSION)
	cmake -S emsdk/binaryen -B emsdk/binaryen -DBUILD_STATIC_LIB=ON
	make -C emsdk/binaryen -j5 wasm-opt
	cp emsdk/binaryen/bin/wasm-opt emsdk/upstream/bin/
	touch emsdk/.complete

.PHONY: test
test:
	pytest tests/ -v

clean:
	rm -rf emsdk
