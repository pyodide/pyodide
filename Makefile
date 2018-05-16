PYODIDE_ROOT=$(abspath .)
include Makefile.envs

FILEPACKAGER=emsdk/emsdk/emscripten/incoming/tools/file_packager.py

CPYTHONROOT=cpython
CPYTHONLIB=$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/python$(PYMINOR)

CC=emcc
CXX=em++
OPTFLAGS=-O3
CFLAGS=$(OPTFLAGS) -g -I$(PYTHONINCLUDE) -Wno-warn-absolute-paths
CXXFLAGS=$(CFLAGS) -std=c++14
LDFLAGS=\
	-O3 \
	-s MODULARIZE=1 \
	$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/libpython$(PYMINOR).a \
  -s "BINARYEN_METHOD='native-wasm'" \
  -s TOTAL_MEMORY=536870912 \
	-s MAIN_MODULE=1 \
	-s EMULATED_FUNCTION_POINTERS=1 \
  -s EMULATE_FUNCTION_POINTER_CASTS=1 \
  -s EXPORTED_FUNCTIONS='["_main"]' \
  -s WASM=1 \
	-s SWAPPABLE_ASM_MODULE=1 \
  --memory-init-file 0

NUMPY_ROOT=numpy/build/numpy
NUMPY_LIBS=\
	$(NUMPY_ROOT)/core/multiarray.so \
	$(NUMPY_ROOT)/core/umath.so \
	$(NUMPY_ROOT)/linalg/lapack_lite.so \
	$(NUMPY_ROOT)/linalg/_umath_linalg.so \
	$(NUMPY_ROOT)/random/mtrand.so \
	$(NUMPY_ROOT)/fft/fftpack_lite.so

PANDAS_ROOT=pandas/build/pandas
PANDAS_LIBS=\
	$(PANDAS_ROOT)/_libs/lib.so

DATEUTIL_ROOT=dateutil/python-dateutil-2.7.2/build/lib/dateutil
DATEUTIL_LIBS=$(DATEUTIL_ROOT)/__init__.py

PYTZ_ROOT=pytz/pytz-2018.4/build/lib/pytz
PYTZ_LIBS=$(PYTZ_ROOT)/__init__.py

SIX_ROOT=six/six-1.11.0/build/lib
SIX_LIBS=$(SIX_ROOT)/six.py

SITEPACKAGES=root/lib/python$(PYMINOR)/site-packages

all: build/pyodide.asm.js \
	build/pyodide.js \
	build/pyodide_dev.js \
	build/python.html \
	build/renderedhtml.css \
	build/numpy.data \
	build/dateutil.data \
	build/pytz.data \
	build/pandas.data


build/pyodide.asm.js: src/main.bc src/jsimport.bc src/jsproxy.bc src/js2python.bc \
											src/pyimport.bc src/pyproxy.bc src/python2js.bc \
											src/runpython.bc src/dummy_thread.bc root/.built
	[ -d build ] || mkdir build
	$(CC) -s EXPORT_NAME="'pyodide'" --bind -o build/pyodide.asm.html $(filter %.bc,$^) \
	  $(LDFLAGS) $(foreach d,$(wildcard root/*),--preload-file $d@/$(notdir $d))
	rm build/pyodide.asm.asm.js
	rm build/pyodide.asm.wasm.pre
	rm build/pyodide.asm.html


build/pyodide_dev.js: src/pyodide.js
	cp $< $@
	sed -i -e "s#{{DEPLOY}}##g" $@


build/pyodide.js: src/pyodide.js
	cp $< $@
	sed -i -e 's#{{DEPLOY}}#https://iodide-project.github.io/pyodide-demo/#g' $@


build/python.html: src/python.html
	cp $< $@


build/test.html: src/test.html
	cp $< $@


build/renderedhtml.css: src/renderedhtml.less
	lessc $< $@


test: all build/test.html
	py.test test -v


benchmark: all build/test.html
	python benchmark/benchmark.py $(HOSTPYTHON) build/benchmarks.json
	python benchmark/plot_benchmark.py build/benchmarks.json build/benchmarks.png


clean:
	rm -fr root
	rm build/*
	rm src/*.bc
	echo "CPython and Numpy builds are not cleaned. cd into those directories to do so."


%.bc: %.cpp $(CPYTHONLIB)
	$(CXX) --bind -o $@ $< $(CXXFLAGS)


%.bc: %.c $(CPYTHONLIB)
	$(CC) -o $@ $< $(CFLAGS)


# TODO: It would be nice to generalize this
build/numpy.data: $(NUMPY_LIBS)
	python2 $(FILEPACKAGER) build/numpy.data --preload $(NUMPY_ROOT)@/lib/python3.6/site-packages/numpy --js-output=build/numpy.js --export-name=pyodide --exclude \*.wasm.pre --exclude __pycache__


build/dateutil.data: $(DATEUTIL_LIBS)
	python2 $(FILEPACKAGER) build/dateutil.data --preload $(DATEUTIL_ROOT)@/lib/python3.6/site-packages/dateutil --js-output=build/dateutil.js --export-name=pyodide --exclude \*.wasm.pre --exclude __pycache__


build/pytz.data: $(PYTZ_LIBS)
	python2 $(FILEPACKAGER) build/pytz.data --preload $(PYTZ_ROOT)@/lib/python3.6/site-packages/pytz --js-output=build/pytz.js --export-name=pyodide --exclude \*.wasm.pre --exclude __pycache__


build/pandas.data: $(PANDAS_LIBS)
	python2 $(FILEPACKAGER) build/pandas.data --preload $(PANDAS_ROOT)@/lib/python3.6/site-packages/pandas --js-output=build/pandas.js --export-name=pyodide --exclude \*.wasm.pre --exclude __pycache__


root/.built: \
		$(CPYTHONLIB) \
		$(SIX_LIBS) \
		src/lazy_import.py \
		src/sitecustomize.py \
		src/webbrowser.py \
		src/pyodide.py \
		remove_modules.txt
	rm -rf root
	mkdir -p root/lib
	cp -a $(CPYTHONLIB)/ root/lib
	cp $(SIX_LIBS) $(SITEPACKAGES)
	cp src/lazy_import.py $(SITEPACKAGES)
	cp src/sitecustomize.py $(SITEPACKAGES)
	cp src/webbrowser.py root/lib/python$(PYMINOR)
	cp src/_testcapi.py	root/lib/python$(PYMINOR)
	cp src/pystone.py root/lib/python$(PYMINOR)
	cp src/pyodide.py root/lib/python$(PYMINOR)/site-packages
	( \
		cd root/lib/python$(PYMINOR); \
		rm -fr `cat ../../../remove_modules.txt`; \
		rm encodings/cp*.py; \
		rm encodings/mac_*.py; \
		find . -name "*.wasm.pre" -type f -delete ; \
		find -type d -name __pycache__ -prune -exec rm -rf {} \; \
	)
	touch root/.built


$(CPYTHONLIB): emsdk/emsdk/emsdk
	make -C $(CPYTHONROOT)


$(NUMPY_LIBS): $(CPYTHONLIB)
	make -C numpy


$(PANDAS_LIBS): $(NUMPY_LIBS)
	make -C pandas


$(DATEUTIL_LIBS): $(CPYTHONLIB)
	make -C dateutil


$(PYTZ_LIBS): $(CPYTHONLIB)
	make -C pytz


$(SIX_LIBS): $(CPYTHONLIB)
	make -C six


emsdk/emsdk/emsdk:
	make -C emsdk
