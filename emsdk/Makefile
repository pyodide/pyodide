PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all: emsdk/.complete

# We hack the CPU_CORES, because if you use all of the cores on Circle-CI, you
# run out of memory.

emsdk/.complete:
	if [ -d emsdk ]; then rm -rf emsdk; fi
	git clone https://github.com/emscripten-core/emsdk.git
	sed -i -e "s#CPU_CORES = max(multiprocessing.cpu_count()-1, 1)#CPU_CORES = 3#g" emsdk/emsdk
	( \
		cd emsdk && \
		./emsdk install --build=Release $(EMSCRIPTEN_VERSION)-upstream && \
		./emsdk activate --embedded --build=Release $(EMSCRIPTEN_VERSION)-upstream && \
		touch .complete \
	)

clean:
	rm -rf emsdk
