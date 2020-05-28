PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all: emsdk/.complete

emsdk/.complete:
	if [ -d emsdk ]; then rm -rf emsdk; fi
	git clone https://github.com/juj/emsdk.git
	( \
		cd emsdk && \
		./emsdk install --build=Release sdk-fastcomp-tag-$(EMSCRIPTEN_VERSION)-64bit binaryen-tag-$(EMSCRIPTEN_VERSION)-64bit && \
		cd .. && \
		(cat patches/*.patch | patch -p1) && \
		cd emsdk/binaryen/tag-$(EMSCRIPTEN_VERSION)_64bit_binaryen/ && \
    make && \
	  cd ../.. && \
		./emsdk activate --embedded --build=Release sdk-fastcomp-tag-$(EMSCRIPTEN_VERSION)-64bit binaryen-tag-$(EMSCRIPTEN_VERSION)-64bit && \
    touch .complete \
	)

clean:
	rm -rf emsdk
