PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all: emsdk/.complete

# We hack the CPU_CORES, because if you use all of the cores on Circle-CI, you
# run out of memory.

emsdk/.complete:
	if [ -d emsdk ]; then rm -rf emsdk; fi
	git clone https://github.com/juj/emsdk.git
	sed -i -e "s#CPU_CORES = max(multiprocessing.cpu_count()-1, 1)#CPU_CORES = 3#g" emsdk/emsdk
	( \
		cd emsdk && \
		./emsdk install --build=Release sdk-tag-$(EMSCRIPTEN_VERSION)-64bit binaryen-tag-$(EMSCRIPTEN_VERSION)-64bit && \
		cd .. && \
		(cat patches/*.patch | patch -p1) && \
		cd emsdk/binaryen/tag-$(EMSCRIPTEN_VERSION)_64bit_binaryen/ && \
    make && \
	  cd ../../.. && \
		cd emsdk/clang/tag-e$(EMSCRIPTEN_VERSION)/build_tag-e$(EMSCRIPTEN_VERSION)_64/ && \
    make && \
    cd ../../.. && \
		./emsdk activate --embedded --build=Release sdk-tag-$(EMSCRIPTEN_VERSION)-64bit binaryen-tag-$(EMSCRIPTEN_VERSION)-64bit && \
    touch .complete \
	)

clean:
	rm -rf emsdk
