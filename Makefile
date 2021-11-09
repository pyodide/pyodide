PYODIDE_ROOT=$(abspath .)

include Makefile.envs

.PHONY=check


CPYTHONROOT=cpython
CPYTHONLIB=$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/python$(PYMAJOR).$(PYMINOR)

CC=emcc
CXX=em++


all: check \
	build/pyodide.asm.js \
	build/pyodide.js \
	build/console.html \
	build/test.data \
	build/distutils.data \
	build/packages.json \
	build/test.html \
	build/webworker.js \
	build/webworker_dev.js
	echo -e "\nSUCCESS!"

$(CPYTHONLIB)/tzdata :
	pip install tzdata --target=$(CPYTHONLIB)

build/pyodide.asm.js: \
	src/core/docstring.o \
	src/core/error_handling.o \
	src/core/numpy_patch.o \
	src/core/hiwire.o \
	src/core/js2python.o \
	src/core/jsproxy.o \
	src/core/keyboard_interrupt.o \
	src/core/main.o  \
	src/core/pyproxy.o \
	src/core/python2js_buffer.o \
	src/core/python2js.o \
	$(wildcard src/lib/**/*) \
	$(CPYTHONLIB)/tzdata \
	$(wildcard src/py/pyodide/*.py) \
	$(wildcard src/py/_pyodide/*.py) \
	$(CPYTHONLIB)
	date +"[%F %T] Building pyodide.asm.js..."
	[ -d build ] || mkdir build
	$(CXX) -s EXPORT_NAME="'_createPyodideModule'" -o build/pyodide.asm.js $(filter %.o,$^) \
		$(MAIN_MODULE_LDFLAGS) -s FORCE_FILESYSTEM=1 \
		-lidbfs.js \
		-lnodefs.js \
		-lproxyfs.js \
		-lworkerfs.js \
		--preload-file $(CPYTHONLIB)@/lib/python$(PYMAJOR).$(PYMINOR) \
		--preload-file src/py/lib@/lib/python$(PYMAJOR).$(PYMINOR)/\
		--preload-file src/py/@/lib/python$(PYMAJOR).$(PYMINOR)/site-packages/ \
		--exclude-file "*__pycache__*" \
		--exclude-file "*/test/*" \
		--exclude-file "*/tests/*" \
		--exclude-file "*/distutils/*"
   # Strip out C++ symbols which all start __Z.
   # There are 4821 of these and they have VERY VERY long names.
   # To show some stats on the symbols you can use the following:
   # cat build/pyodide.asm.js | grep -ohE 'var _{0,5}.' | sort | uniq -c | sort -nr | head -n 20
	sed -i -E 's/var __Z[^;]*;//g' build/pyodide.asm.js
	sed -i '1i\
		"use strict";\
		let setImmediate = globalThis.setImmediate;\
		let clearImmediate = globalThis.clearImmediate;\
		let baseName, fpcGOT, dyncallGOT, fpVal, dcVal;\
	' build/pyodide.asm.js
	echo "globalThis._createPyodideModule = _createPyodideModule;" >> build/pyodide.asm.js
	date +"[%F %T] done building pyodide.asm.js."


env:
	env


node_modules/.installed : src/js/package.json
	cd src/js && npm install --save-dev
	ln -sfn src/js/node_modules/ node_modules
	touch node_modules/.installed

build/pyodide.js: src/js/*.js src/js/pyproxy.gen.js node_modules/.installed
	npx typescript --project src/js
	npx rollup -c src/js/rollup.config.js

src/js/pyproxy.gen.js : src/core/pyproxy.* src/core/*.h
	# We can't input pyproxy.js directly because CC will be unhappy about the file
	# extension. Instead cat it and have CC read from stdin.
	# -E : Only apply prepreocessor
	# -C : Leave comments alone (this allows them to be preserved in typescript
	#      definition files, rollup will strip them out)
	# -P : Don't put in macro debug info
	# -imacros pyproxy.c : include all of the macros definitions from pyproxy.c
	rm -f $@
	echo "// This file is generated by applying the C preprocessor to core/pyproxy.js" >> $@
	echo "// It uses the macros defined in core/pyproxy.c" >> $@
	echo "// Do not edit it directly!" >> $@
	cat src/core/pyproxy.js | $(CC) -E -C -P -imacros src/core/pyproxy.c $(MAIN_MODULE_CFLAGS) - >> $@

build/test.html: src/templates/test.html
	cp $< $@


.PHONY: build/console.html
build/console.html: src/templates/console.html
	cp $< $@
	sed -i -e 's#{{ PYODIDE_BASE_URL }}#$(PYODIDE_BASE_URL)#g' $@


.PHONY: docs/_build/html/console.html
docs/_build/html/console.html: src/templates/console.html
	mkdir -p docs/_build/html
	cp $< $@
	sed -i -e 's#{{ PYODIDE_BASE_URL }}#$(PYODIDE_BASE_URL)#g' $@


.PHONY: build/webworker.js
build/webworker.js: src/templates/webworker.js
	cp $< $@
	sed -i -e 's#{{ PYODIDE_BASE_URL }}#$(PYODIDE_BASE_URL)#g' $@


.PHONY: build/webworker_dev.js
build/webworker_dev.js: src/templates/webworker.js
	cp $< $@
	sed -i -e 's#{{ PYODIDE_BASE_URL }}#./#g' $@


update_base_url: \
	build/console.html \
	build/webworker.js


test: all
	pytest src emsdk/tests packages/*/test* pyodide-build -v

lint: node_modules/.installed
	# check for unused imports, the rest is done by black
	flake8 --select=F401 src tools pyodide-build benchmark conftest.py docs packages/matplotlib/src/
	find src -type f -regex '.*\.\(c\|h\)' \
		| xargs clang-format-6.0 -output-replacements-xml \
		| (! grep '<replacement ')
	npx prettier --check src
	black --check .
	mypy --ignore-missing-imports    \
		pyodide-build/pyodide_build/ \
		src/ 					     \
		packages/*/test* 			 \
		conftest.py 				 \
		docs
	# mypy gets upset about there being both: src/py/setup.py and
	# packages/micropip/src/setup.py. There is no easy way to fix this right now
	# see python/mypy#10428. This will also cause trouble with pre-commit if you
	# modify both setup.py files in the same commit.
	mypy --ignore-missing-imports    \
		packages/micropip/src/



benchmark: all
	$(HOSTPYTHON) benchmark/benchmark.py $(HOSTPYTHON) build/benchmarks.json
	$(HOSTPYTHON) benchmark/plot_benchmark.py build/benchmarks.json build/benchmarks.png


clean:
	rm -fr build/*
	rm -fr src/*/*.o
	rm -fr node_modules
	make -C packages clean
	echo "The Emsdk, CPython are not cleaned. cd into those directories to do so."


clean-all: clean
	make -C emsdk clean
	make -C cpython clean
	rm -fr cpython/build

%.o: %.c $(CPYTHONLIB) $(wildcard src/core/*.h src/core/python2js_buffer.js)
	$(CC) -o $@ -c $< $(MAIN_MODULE_CFLAGS) -Isrc/core/


# Stdlib modules that we repackage as standalone packages

# TODO: also include test directories included in other stdlib modules
build/test.data: $(CPYTHONLIB) node_modules/.installed
	./tools/file_packager.sh build/test.data --js-output=build/test.js \
		--preload $(CPYTHONLIB)/test@/lib/python$(PYMAJOR).$(PYMINOR)/test
	npx terser build/test.js -o build/test.js


build/distutils.data: $(CPYTHONLIB) node_modules/.installed
	./tools/file_packager.sh build/distutils.data --js-output=build/distutils.js \
		--preload $(CPYTHONLIB)/distutils@/lib/python$(PYMAJOR).$(PYMINOR)/distutils \
		--exclude tests
	npx terser build/distutils.js -o build/distutils.js


$(CPYTHONLIB): emsdk/emsdk/.complete $(PYODIDE_EMCC) $(PYODIDE_CXX)
	date +"[%F %T] Building cpython..."
	make -C $(CPYTHONROOT)
	date +"[%F %T] done building cpython..."


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


debug :
	EXTRA_CFLAGS+=" -D DEBUG_F" \
	make
