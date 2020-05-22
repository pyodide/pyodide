PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all: emsdk/.complete

emsdk/.complete:
	if [ -d emsdk ]; then rm -rf emsdk; fi
	git clone https://github.com/emscripten-core/emsdk.git
	( \
		cd emsdk && \
		./emsdk install --build=Release $(EMSCRIPTEN_VERSION)-fastcomp && \
		cd .. && \
		(cat patches/*.patch | patch -p1) && \
		cd emsdk && \
		./emsdk activate --embedded --build=Release $(EMSCRIPTEN_VERSION)-fastcomp && \
	        touch .complete \
	)

clean:
	rm -rf emsdk
