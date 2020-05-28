PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all: emsdk/.complete

emsdk/.complete:
	if [ -d emsdk ]; then rm -rf emsdk; fi
	git clone https://github.com/emscripten-core/emsdk.git
	( \
		cd emsdk && \
		./emsdk install --build=Release $(EMSCRIPTEN_VERSION)-fastcomp && \
		git clone --branch 1.38.32 --depth 1 https://github.com/WebAssembly/binaryen.git  && \
		cd .. && \
		(cat patches/*.patch | patch -p1) && \
		cd emsdk && \
		./emsdk activate --embedded --build=Release $(EMSCRIPTEN_VERSION)-fastcomp && \
		cd .. && \
	        cd binaryen && \
		cmake . && make && \
		cd .. && \
	        touch .complete \
	)

clean:
	rm -rf emsdk
