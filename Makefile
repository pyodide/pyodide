PYVERSION=3.6.4
PYMINOR=$(basename $(PYVERSION))
CPYTHONROOT=cpython
CPYTHONLIB=$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/python$(PYMINOR)
CPYTHONINC=$(CPYTHONROOT)/installs/python-$(PYVERSION)/include/python$(PYMINOR)

CC=emcc
CXX=em++
OPTFLAGS=-O3
CXXFLAGS=-std=c++14 $(OPTFLAGS) -g -I$(CPYTHONINC) -Wno-warn-absolute-paths
LDFLAGS=$(OPTFLAGS) \
	$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/libpython$(PYMINOR).a \
  -s "BINARYEN_METHOD='native-wasm'" \
  -s TOTAL_MEMORY=268435456 \
	-s MAIN_MODULE=1 \
  -s ASSERTIONS=2 \
	-s EMULATED_FUNCTION_POINTERS=1 \
  -s EMULATE_FUNCTION_POINTER_CASTS=1 \
  -s EXPORTED_FUNCTIONS='["_main"]' \
  --memory-init-file 0

NUMPY_ROOT=numpy/build/numpy
NUMPY_LIBS=\
	$(NUMPY_ROOT)/core/multiarray.so \
	$(NUMPY_ROOT)/core/umath.so \
	$(NUMPY_ROOT)/linalg/lapack_lite.so \
	$(NUMPY_ROOT)/linalg/_umath_linalg.so \
  $(NUMPY_ROOT)/fft/fftpack_lite.so \
	$(NUMPY_ROOT)/random/mtrand.so


all: build/pyodide.asm.html build/pyodide.js


build:
	[ -d build ] || mkdir build


build/pyodide.asm.html: src/main.bc src/jsimport.bc src/jsproxy.bc src/js2python.bc \
                        src/pyimport.bc src/pyproxy.bc src/python2js.bc \
												src/runpython.bc root/.built build
	$(CC) -s EXPORT_NAME="'pyodide'" --bind -o $@ $(filter %.bc,$^) $(LDFLAGS) \
		$(foreach d,$(wildcard root/*),--preload-file $d@/$(notdir $d))


build/pyodide.js: src/pyodide.js build
	cp $< $@


clean:
	rm -fr root
	rm build/*
	rm src/*.bc
	echo "CPython and Numpy builds were not cleaned"


%.bc: %.cpp $(CPYTHONLIB)
	$(CXX) --bind -o $@ $< $(CXXFLAGS)


root/.built: $(CPYTHONLIB) $(NUMPY_LIBS)
	mkdir -p root/lib
	cp -a $(CPYTHONLIB)/ root/lib
	cp -a numpy/build/numpy root/lib/python$(PYMINOR)/site-packages
	rm -fr root/lib/python$(PYMINOR)/site-packages/numpy/distutils
	( \
		cd root/lib/python$(PYMINOR); \
		rm -fr test distutils ensurepip idlelib __pycache__ tkinter; \
	)
	touch root/.built


$(CPYTHONLIB):
	make -C $(CPYTHONROOT)


$(NUMPY_LIBS):
	make -C numpy
