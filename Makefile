PYODIDE_ROOT=$(abspath .)
include Makefile.envs

FILEPACKAGER=emsdk/emsdk/emscripten/tag-1.38.4/tools/file_packager.py

CPYTHONROOT=cpython
CPYTHONLIB=$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/python$(PYMINOR)

CC=emcc
CXX=em++
OPTFLAGS=-O3
CFLAGS=$(OPTFLAGS) -g -I$(PYTHONINCLUDE) -Wno-warn-absolute-paths
CXXFLAGS=$(CFLAGS) -std=c++14

# __ZNKSt3__220__vector_base_commonILb1EE20__throw_length_errorEv is in
# EXPORTED_FUNCTIONS to keep the C++ standard library in the core, even though
# there isn't any C++ there, for the sake of loading dynamic modules written in
# C++, such as those in matplotlib.
LDFLAGS=\
	-O3 \
	-s MODULARIZE=1 \
	$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/libpython$(PYMINOR).a \
  -s "BINARYEN_METHOD='native-wasm'" \
  -s TOTAL_MEMORY=536870912 \
	-s MAIN_MODULE=1 \
	-s EMULATED_FUNCTION_POINTERS=1 \
  -s EMULATE_FUNCTION_POINTER_CASTS=1 \
  -s EXPORTED_FUNCTIONS='["_main", "__ZNKSt3__220__vector_base_commonILb1EE20__throw_length_errorEv"]' \
  -s WASM=1 \
	-s SWAPPABLE_ASM_MODULE=1 \
	-s USE_FREETYPE=1 \
	-std=c++14 \
  -lstdc++ \
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

MATPLOTLIB_ROOT=matplotlib/build/matplotlib
MATPLOTLIB_LIBS=\
	$(MATPLOTLIB_ROOT)/_path.so

DATEUTIL_ROOT=dateutil/python-dateutil-2.7.2/build/lib/dateutil
DATEUTIL_LIBS=$(DATEUTIL_ROOT)/__init__.py

PYTZ_ROOT=pytz/pytz-2018.4/build/lib/pytz
PYTZ_LIBS=$(PYTZ_ROOT)/__init__.py

SIX_ROOT=six/six-1.11.0/build/lib
SIX_LIBS=$(SIX_ROOT)/six.py

PYPARSING_ROOT=pyparsing/pyparsing-2.2.0/build/lib
PYPARSING_LIBS=$(PYPARSING_ROOT)/pyparsing.py

CYCLER_ROOT=cycler/cycler-0.10.0/build/lib
CYCLER_LIBS=$(CYCLER_ROOT)/cycler.py

KIWISOLVER_ROOT=kiwisolver/build
KIWISOLVER_LIBS=$(KIWISOLVER_ROOT)/kiwisolver.so

SITEPACKAGES=root/lib/python$(PYMINOR)/site-packages

all: build/pyodide.asm.js \
	build/pyodide.asm.data \
	build/pyodide.js \
	build/pyodide_dev.js \
	build/python.html \
	build/matplotlib.html \
	build/matplotlib-sideload.html \
	build/renderedhtml.css \
  build/test.data \
	build/numpy.data \
	build/dateutil.data \
	build/pytz.data \
	build/pandas.data \
	build/matplotlib.data \
	build/kiwisolver.data \
	build/pyparsing.data \
	build/cycler.data


build/pyodide.asm.js: src/main.bc src/jsimport.bc src/jsproxy.bc src/js2python.bc \
											src/pyimport.bc src/pyproxy.bc src/python2js.bc \
											src/runpython.bc src/dummy_thread.bc src/hiwire.bc
	[ -d build ] || mkdir build
	$(CXX) -s EXPORT_NAME="'pyodide'" -o build/pyodide.asm.html $(filter %.bc,$^) \
	  $(LDFLAGS) -s FORCE_FILESYSTEM=1
	rm build/pyodide.asm.asm.js
	rm build/pyodide.asm.wasm.pre
	rm build/pyodide.asm.html


build/pyodide.asm.data: root/.built
	python2 $(FILEPACKAGER) build/pyodide.asm.data --preload root/lib@lib --js-output=build/pyodide.asm.data.js
	uglifyjs build/pyodide.asm.data.js -o build/pyodide.asm.data.js


build/pyodide_dev.js: src/pyodide.js
	cp $< $@
	sed -i -e "s#{{DEPLOY}}##g" $@


build/pyodide.js: src/pyodide.js
	cp $< $@
	sed -i -e 's#{{DEPLOY}}#https://iodide.io/pyodide-demo/#g' $@


build/python.html: src/python.html
	cp $< $@


build/matplotlib.html: src/matplotlib.html
	cp $< $@


build/matplotlib-sideload.html: src/matplotlib-sideload.html
	cp $< $@


build/test.html: src/test.html
	cp $< $@


build/renderedhtml.css: src/renderedhtml.less
	lessc $< $@


test: all build/test.html
	py.test test -v


lint:
	flake8 src
	flake8 test
	clang-format -output-replacements-xml src/*.c src/*.h src/*.js | (! grep '<replacement ')

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
	./packager.sh numpy	$(NUMPY_ROOT)@/lib/python3.6/site-packages/numpy


build/dateutil.data: $(DATEUTIL_LIBS)
	./packager.sh dateutil $(DATEUTIL_ROOT)@/lib/python3.6/site-packages/dateutil


build/pytz.data: $(PYTZ_LIBS)
	./packager.sh pytz $(PYTZ_ROOT)@/lib/python3.6/site-packages/pytz


build/pandas.data: $(PANDAS_LIBS)
	./packager.sh pandas $(PANDAS_ROOT)@/lib/python3.6/site-packages/pandas


build/matplotlib.data: $(MATPLOTLIB_LIBS)
	./packager.sh matplotlib $(MATPLOTLIB_ROOT)@/lib/python3.6/site-packages/matplotlib


build/kiwisolver.data: $(KIWISOLVER_LIBS)
	./packager.sh kiwisolver kiwisolver/build@/lib/python3.6/site-packages


build/cycler.data: $(CYCLER_LIBS)
	./packager.sh cycler $(CYCLER_ROOT)@/lib/python3.6/site-packages


build/pyparsing.data: $(CYCLER_LIBS)
	./packager.sh pyparsing $(PYPARSING_ROOT)@/lib/python3.6/site-packages


build/test.data: $(CPYTHONLIB)
	./packager.sh test $(CPYTHONLIB)/test@/lib/python3.6/test


root/.built: \
		$(CPYTHONLIB) \
		$(SIX_LIBS) \
		src/sitecustomize.py \
		src/webbrowser.py \
		src/pyodide.py \
		remove_modules.txt
	rm -rf root
	mkdir -p root/lib
	cp -a $(CPYTHONLIB)/ root/lib
	cp $(SIX_LIBS) $(SITEPACKAGES)
	cp src/sitecustomize.py $(SITEPACKAGES)
	cp src/webbrowser.py root/lib/python$(PYMINOR)
	cp src/_testcapi.py	root/lib/python$(PYMINOR)
	cp src/pystone.py root/lib/python$(PYMINOR)
	cp src/pyodide.py root/lib/python$(PYMINOR)/site-packages
	( \
		cd root/lib/python$(PYMINOR); \
		rm -fr `cat ../../../remove_modules.txt`; \
		rm encodings/mac_*.py; \
		rm -fr test; \
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


$(MATPLOTLIB_LIBS): $(NUMPY_LIBS)
	make -C matplotlib


$(DATEUTIL_LIBS): $(CPYTHONLIB)
	make -C dateutil


$(PYTZ_LIBS): $(CPYTHONLIB)
	make -C pytz


$(SIX_LIBS): $(CPYTHONLIB)
	make -C six


$(PYPARSING_LIBS): $(CPYTHONLIB)
	make -C pyparsing


$(CYCLER_LIBS): $(CPYTHONLIB)
	make -C cycler


$(KIWISOLVER_LIBS): $(CPYTHONLIB)
	make -C kiwisolver


emsdk/emsdk/emsdk:
	make -C emsdk
