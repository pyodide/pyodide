PYODIDE_ROOT=$(abspath .)
include Makefile.envs
.PHONY=check

FILEPACKAGER=$(PYODIDE_ROOT)/tools/file_packager.py

CPYTHONROOT=cpython
CPYTHONLIB=$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/python$(PYMINOR)

LZ4LIB=lz4/lz4-1.8.3/lib/liblz4.a
CLAPACK=CLAPACK/CLAPACK-WA/lapack_WA.bc

PYODIDE_EMCC=$(PYODIDE_ROOT)/ccache/emcc
PYODIDE_CXX=$(PYODIDE_ROOT)/ccache/em++

SHELL := /bin/bash
CC=emcc
CXX=em++
OPTFLAGS=-O3
CFLAGS=$(OPTFLAGS) -g -I$(PYTHONINCLUDE) -Wno-warn-absolute-paths
CXXFLAGS=$(CFLAGS) -std=c++14


LDFLAGS=\
	-O3 \
	-s MODULARIZE=1 \
	$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/libpython$(PYMINOR).a \
	$(LZ4LIB) \
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

SIX_ROOT=six/six-1.11.0/build/lib
SIX_LIBS=$(SIX_ROOT)/six.py

JEDI_ROOT=jedi/jedi-0.15.1/jedi
JEDI_LIBS=$(JEDI_ROOT)/__init__.py

PARSO_ROOT=parso/parso-0.5.1/parso
PARSO_LIBS=$(PARSO_ROOT)/__init__.py

SITEPACKAGES=root/lib/python$(PYMINOR)/site-packages

all: check \
	build/pyodide.asm.js \
	build/pyodide.asm.data \
	build/pyodide.js \
	build/pyodide_dev.js \
	build/console.html \
	build/renderedhtml.css \
	build/test.data \
	build/packages.json \
	build/test.html \
	build/webworker.js \
	build/webworker_dev.js
	echo -e "\nSUCCESS!"


build/pyodide.asm.js: src/main.bc src/jsimport.bc src/jsproxy.bc src/js2python.bc \
		src/pyimport.bc src/pyproxy.bc src/python2js.bc src/python2js_buffer.bc \
		src/runpython.bc src/hiwire.bc
	[ -d build ] || mkdir build
	$(CXX) -s EXPORT_NAME="'pyodide'" -o build/pyodide.asm.html $(filter %.bc,$^) \
		$(LDFLAGS) -s FORCE_FILESYSTEM=1
	rm build/pyodide.asm.html


env:
	env


build/pyodide.asm.data: root/.built
	( \
		cd build; \
		python $(FILEPACKAGER) pyodide.asm.data --abi=$(PYODIDE_PACKAGE_ABI) --lz4 --preload ../root/lib@lib --js-output=pyodide.asm.data.js --use-preload-plugins \
	)
	uglifyjs build/pyodide.asm.data.js -o build/pyodide.asm.data.js


build/pyodide_dev.js: src/pyodide.js
	cp $< $@
	sed -i -e "s#{{DEPLOY}}#./#g" $@
	sed -i -e "s#{{ABI}}#$(PYODIDE_PACKAGE_ABI)#g" $@


build/pyodide.js: src/pyodide.js
	cp $< $@
	sed -i -e 's#{{DEPLOY}}#https://pyodide-cdn2.iodide.io/v0.15.0/full/#g' $@

	sed -i -e "s#{{ABI}}#$(PYODIDE_PACKAGE_ABI)#g" $@


build/test.html: src/test.html
	cp $< $@


build/console.html: src/console.html
	cp $< $@


build/renderedhtml.css: src/renderedhtml.less
	lessc $< $@

build/webworker.js: src/webworker.js
	cp $< $@
	sed -i -e 's#{{DEPLOY}}#https://pyodide-cdn2.iodide.io/v0.15.0/full/#g' $@

build/webworker_dev.js: src/webworker.js
	cp $< $@
	sed -i -e "s#{{DEPLOY}}#./#g" $@
	sed -i -e "s#pyodide.js#pyodide_dev.js#g" $@

test: all
	pytest test packages pyodide_build -v


lint:
	flake8 src test tools pyodide_build benchmark
	clang-format -output-replacements-xml src/*.c src/*.h src/*.js | (! grep '<replacement ')


benchmark: all
	python benchmark/benchmark.py $(HOSTPYTHON) build/benchmarks.json
	python benchmark/plot_benchmark.py build/benchmarks.json build/benchmarks.png


clean:
	rm -fr root
	rm -fr build/*
	rm -fr src/*.bc
	make -C packages clean
	make -C six clean
	make -C jedi clean
	make -C parso clean
	make -C lz4 clean
	echo "The Emsdk, CPython and CLAPACK are not cleaned. cd into those directories to do so."


%.bc: %.c $(CPYTHONLIB) $(LZ4LIB)
	$(CC) -o $@ -c $< $(CFLAGS)


build/test.data: $(CPYTHONLIB)
	( \
		cd $(CPYTHONLIB)/test; \
		find . -type d -name __pycache__ -prune -exec rm -rf {} \; \
	)
	( \
		cd build; \
		python $(FILEPACKAGER) test.data --abi=$(PYODIDE_PACKAGE_ABI) --lz4 --preload ../$(CPYTHONLIB)/test@/lib/python3.7/test --js-output=test.js --export-name=pyodide._module --exclude __pycache__ \
	)
	uglifyjs build/test.js -o build/test.js


root/.built: \
		$(CPYTHONLIB) \
		$(SIX_LIBS) \
		$(JEDI_LIBS) \
		$(PARSO_LIBS) \
		src/sitecustomize.py \
		src/webbrowser.py \
		src/pyodide.py \
		remove_modules.txt
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
	cp src/pyodide.py root/lib/python$(PYMINOR)/site-packages
	( \
		cd root/lib/python$(PYMINOR); \
		rm -fr `cat ../../../remove_modules.txt`; \
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
	 		ln -s emsdk/emsdk/emscripten/tag-$(EMSCRIPTEN_VERSION)/emcc $@; \
		fi; \
	fi


$(PYODIDE_CXX):
	mkdir -p $(PYODIDE_ROOT)/ccache ; \
	if test ! -h $@; then \
		if hash ccache &>/dev/null; then \
			ln -s `which ccache` $@ ; \
		else \
			ln -s emsdk/emsdk/emscripten/tag-$(EMSCRIPTEN_VERSION)/em++ $@; \
		fi; \
	fi


$(CPYTHONLIB): emsdk/emsdk/.complete $(PYODIDE_EMCC) $(PYODIDE_CXX)
	make -C $(CPYTHONROOT)


$(LZ4LIB):
	make -C lz4


$(SIX_LIBS): $(CPYTHONLIB)
	make -C six


$(JEDI_LIBS): $(CPYTHONLIB)
	make -C jedi


$(PARSO_LIBS): $(CPYTHONLIB)
	make -C parso


$(CLAPACK): $(CPYTHONLIB)
ifdef PYODIDE_PACKAGES
	echo "Skipping BLAS/LAPACK build due to PYODIDE_PACKAGES being defined."
	echo "Build it manually with make -C CLAPACK if needed."
	mkdir -p CLAPACK/CLAPACK-WA/
	touch $(CLAPACK)
else
	make -C CLAPACK
endif



build/packages.json: $(CLAPACK) FORCE
	make -C packages

emsdk/emsdk/.complete:
	make -C emsdk

FORCE:

check:
	./tools/dependency-check.sh
