PYODIDE_ROOT=$(abspath .)
include Makefile.envs
.PHONY=check

FILEPACKAGER=$(PYODIDE_ROOT)/tools/file_packager.py

CPYTHONROOT=cpython
CPYTHONLIB=$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/python$(PYMINOR)

PYODIDE_EMCC=$(PYODIDE_ROOT)/ccache/emcc
PYODIDE_CXX=$(PYODIDE_ROOT)/ccache/em++

SHELL := /bin/bash
CC=emcc
CXX=em++
OPTFLAGS=-O2
CFLAGS=$(OPTFLAGS) -g -I$(PYTHONINCLUDE) -Wno-warn-absolute-paths
CXXFLAGS=$(CFLAGS) -std=c++14


LDFLAGS=\
	-O2 \
	-s MODULARIZE=1 \
	$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/libpython$(PYMINOR).a \
	-s "BINARYEN_METHOD='native-wasm'" \
	-s TOTAL_MEMORY=10485760 \
	-s ALLOW_MEMORY_GROWTH=1 \
	-s MAIN_MODULE=1 \
	-s EMULATED_FUNCTION_POINTERS=1 \
	-s EMULATE_FUNCTION_POINTER_CASTS=1 \
	-s LINKABLE=1 \
	-s EXPORT_ALL=1 \
	-s EXPORTED_FUNCTIONS='["___cxa_guard_acquire", "__ZNSt3__28ios_base4initEPv"]' \
	-s WASM=1 \
	-s SWAPPABLE_ASM_MODULE=1 \
	-s USE_FREETYPE=1 \
	-s USE_LIBPNG=1 \
	-std=c++14 \
	-L$(wildcard $(CPYTHONROOT)/build/sqlite*/.libs) -lsqlite3 \
	$(wildcard $(CPYTHONROOT)/build/bzip2*/libbz2.a) \
	-lstdc++ \
	--memory-init-file 0 \
	-s "BINARYEN_TRAP_MODE='clamp'" \
	-s TEXTDECODER=0 \
	-s LZ4=1

SIX_ROOT=packages/six/six-1.11.0/build/lib
SIX_LIBS=$(SIX_ROOT)/six.py

JEDI_ROOT=packages/jedi/jedi-0.17.2/jedi
JEDI_LIBS=$(JEDI_ROOT)/__init__.py

PARSO_ROOT=packages/parso/parso-0.7.1/parso
PARSO_LIBS=$(PARSO_ROOT)/__init__.py

SITEPACKAGES=root/lib/python$(PYMINOR)/site-packages

all: check \
	build/pyodide.asm.js \
	build/pyodide.asm.data \
	build/pyodide.js \
	build/console.html \
	build/renderedhtml.css \
	build/test.data \
	build/packages.json \
	build/test.html \
	build/webworker.js \
	build/webworker_dev.js
	echo -e "\nSUCCESS!"


build/pyodide.asm.js: src/main.bc src/type_conversion/jsimport.bc \
	        src/type_conversion/jsproxy.bc src/type_conversion/js2python.bc \
		src/type_conversion/pyimport.bc src/type_conversion/pyproxy.bc \
		src/type_conversion/python2js.bc \
		src/type_conversion/python2js_buffer.bc \
		src/type_conversion/runpython.bc src/type_conversion/hiwire.bc
	date +"[%F %T] Building pyodide.asm.js..."
	[ -d build ] || mkdir build
	$(CXX) -s EXPORT_NAME="'pyodide'" -o build/pyodide.asm.html $(filter %.bc,$^) \
		$(LDFLAGS) -s FORCE_FILESYSTEM=1
	rm build/pyodide.asm.html
	date +"[%F %T] done building pyodide.asm.js."


env:
	env


build/pyodide.asm.data: root/.built
	( \
		cd build; \
		python $(FILEPACKAGER) pyodide.asm.data --abi=$(PYODIDE_PACKAGE_ABI) --lz4 --preload ../root/lib@lib --js-output=pyodide.asm.data.js --use-preload-plugins \
	)
	uglifyjs build/pyodide.asm.data.js -o build/pyodide.asm.data.js


build/pyodide.js: src/pyodide.js
	cp $< $@
	sed -i -e 's#{{ PYODIDE_BASE_URL }}#$(PYODIDE_BASE_URL)#g' $@
	sed -i -e "s#{{ PYODIDE_PACKAGE_ABI }}#$(PYODIDE_PACKAGE_ABI)#g" $@


build/test.html: src/templates/test.html
	cp $< $@


build/console.html: src/templates/console.html
	cp $< $@
	sed -i -e 's#{{ PYODIDE_BASE_URL }}#$(PYODIDE_BASE_URL)#g' $@


build/renderedhtml.css: src/css/renderedhtml.less
	lessc $< $@

build/webworker.js: src/webworker.js
	cp $< $@
	sed -i -e 's#{{ PYODIDE_BASE_URL }}#$(PYODIDE_BASE_URL)#g' $@

build/webworker_dev.js: src/webworker.js
	cp $< $@
	sed -i -e 's#{{ PYODIDE_BASE_URL }}#./#g' $@

test: all
	pytest src emsdk/tests packages/*/test* pyodide_build -v


lint:
	# check for unused imports, the rest is done by black
	flake8 --select=F401 src tools pyodide_build benchmark
	clang-format-6.0 -output-replacements-xml src/*.c src/*.h src/*.js src/*/*.c src/*/*.h src/*/*.js | (! grep '<replacement ')
	black --check --exclude tools/file_packager.py .
	mypy --ignore-missing-imports pyodide_build/ src/ packages/micropip/micropip/ packages/*/test*


apply-lints:
	clang-format-6.0 -i src/*.c src/*.h src/*.js src/*/*.c src/*/*.h src/*/*.js
	black --exclude tools/file_packager.py .

benchmark: all
	python benchmark/benchmark.py $(HOSTPYTHON) build/benchmarks.json
	python benchmark/plot_benchmark.py build/benchmarks.json build/benchmarks.png


clean:
	rm -fr root
	rm -fr build/*
	rm -fr src/*.bc
	make -C packages clean
	make -C packages/six clean
	make -C packages/jedi clean
	make -C packages/parso clean
	make -C packages/libxslt clean
	make -C packages/libxml clean
	make -C packages/libiconv clean
	make -C packages/zlib clean
	echo "The Emsdk, CPython and CLAPACK are not cleaned. cd into those directories to do so."

clean-all: clean
	make -C emsdk clean
	make -C cpython clean
	rm -fr cpython/build

%.bc: %.c $(CPYTHONLIB)
	$(CC) -o $@ -c $< $(CFLAGS) -Isrc/type_conversion/


build/test.data: $(CPYTHONLIB)
	( \
		cd $(CPYTHONLIB)/test; \
		find . -type d -name __pycache__ -prune -exec rm -rf {} \; \
	)
	( \
		cd build; \
		python $(FILEPACKAGER) test.data --abi=$(PYODIDE_PACKAGE_ABI) --lz4 --preload ../$(CPYTHONLIB)/test@/lib/python3.8/test --js-output=test.js --export-name=pyodide._module --exclude __pycache__ \
	)
	uglifyjs build/test.js -o build/test.js


root/.built: \
		$(CPYTHONLIB) \
		$(SIX_LIBS) \
		$(JEDI_LIBS) \
		$(PARSO_LIBS) \
		src/sitecustomize.py \
		src/webbrowser.py \
		src/pyodide-py/ \
		cpython/remove_modules.txt
	rm -rf root
	mkdir -p root/lib
	cp -r $(CPYTHONLIB) root/lib
	mkdir -p $(SITEPACKAGES)
	cp $(SIX_LIBS) $(SITEPACKAGES)
	cp -r $(JEDI_ROOT) $(SITEPACKAGES)
	cp -r $(PARSO_ROOT) $(SITEPACKAGES)
	cp src/sitecustomize.py $(SITEPACKAGES)
	cp src/webbrowser.py root/lib/python$(PYMINOR)
	cp src/_testcapi.py	root/lib/python$(PYMINOR)
	cp src/pystone.py root/lib/python$(PYMINOR)
	cp -r src/pyodide-py/pyodide/ $(SITEPACKAGES)
	( \
		cd root/lib/python$(PYMINOR); \
		rm -fr `cat ../../../cpython/remove_modules.txt`; \
		rm -fr test; \
		find . -type d -name __pycache__ -prune -exec rm -rf {} \; \
	)
	touch root/.built


$(PYODIDE_EMCC):
	mkdir -p $(PYODIDE_ROOT)/ccache ; \
	if test ! -h $@; then \
		if hash ccache &>/dev/null; then \
			ln -s `which ccache` $@ ; \
		else \
			ln -s emsdk/emsdk/fastcomp/emscripten/emcc $@; \
		fi; \
	fi


$(PYODIDE_CXX):
	mkdir -p $(PYODIDE_ROOT)/ccache ; \
	if test ! -h $@; then \
		if hash ccache &>/dev/null; then \
			ln -s `which ccache` $@ ; \
		else \
			ln -s emsdk/emsdk/fastcomp/emscripten/em++ $@; \
		fi; \
	fi


$(CPYTHONLIB): emsdk/emsdk/.complete $(PYODIDE_EMCC) $(PYODIDE_CXX)
	date +"[%F %T] Building cpython..."
	make -C $(CPYTHONROOT)
	date +"[%F %T] done building cpython..."


$(SIX_LIBS): $(CPYTHONLIB)
	date +"[%F %T] Building six..."
	make -C packages/six
	date +"[%F %T] done building six."


$(JEDI_LIBS): $(CPYTHONLIB)
	date +"[%F %T] Building jedi..."
	make -C packages/jedi
	date +"[%F %T] done building jedi."


$(PARSO_LIBS): $(CPYTHONLIB)
	date +"[%F %T] Building parso..."
	make -C packages/parso
	date +"[%F %T] done building parso."


build/packages.json: FORCE
	date +"[%F %T] Building packages..."
	make -C packages
	date +"[%F %T] done building packages..."

emsdk/emsdk/.complete:
	date +"[%F %T] Building emsdk..."
	make -C emsdk
	date +"[%F %T] done building emsdk."

FORCE:

check:
	./tools/dependency-check.sh
