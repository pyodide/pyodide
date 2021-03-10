PYODIDE_ROOT=$(abspath .)

include Makefile.envs

.PHONY=check

FILEPACKAGER=$$EM_DIR/tools/file_packager.py
UGLIFYJS=$(PYODIDE_ROOT)/node_modules/.bin/uglifyjs

CPYTHONROOT=cpython
CPYTHONLIB=$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/python$(PYMINOR)

CC=emcc
CXX=em++
OPTFLAGS=-O2
CFLAGS=\
	$(OPTFLAGS) \
	-g \
	-I$(PYTHONINCLUDE) \
	-fPIC \
	-Wno-warn-absolute-paths \
	-Werror=int-conversion \
	-Werror=incompatible-pointer-types \
	$(EXTRA_CFLAGS)
LDFLAGS=\
	-s BINARYEN_EXTRA_PASSES="--pass-arg=max-func-params@61" \
	$(OPTFLAGS) \
	-s MODULARIZE=1 \
	$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/libpython$(PYMINOR).a \
	-s TOTAL_MEMORY=20971520 \
	-s ALLOW_MEMORY_GROWTH=1 \
    --use-preload-plugins \
	-s MAIN_MODULE=1 \
	-s EMULATE_FUNCTION_POINTER_CASTS=1 \
	-s LINKABLE=1 \
	-s EXPORT_ALL=1 \
	-s EXPORTED_FUNCTIONS='["___cxa_guard_acquire", "__ZNSt3__28ios_base4initEPv", "_main"]' \
	-s WASM=1 \
	-s USE_FREETYPE=1 \
	-s USE_LIBPNG=1 \
	-std=c++14 \
	-L$(wildcard $(CPYTHONROOT)/build/sqlite*/.libs) -lsqlite3 \
	$(wildcard $(CPYTHONROOT)/build/bzip2*/libbz2.a) \
	-lstdc++ \
	--memory-init-file 0 \
	-s LZ4=1 \
	$(EXTRA_LDFLAGS)

all: check \
	build/pyodide.asm.js \
	build/pyodide.js \
	build/console.html \
	build/test.data \
	build/packages.json \
	build/test.html \
	build/webworker.js \
	build/webworker_dev.js
	echo -e "\nSUCCESS!"


build/pyodide.asm.js: \
	src/core/error_handling.o \
	src/core/hiwire.o \
	src/core/js2python.o \
	src/core/jsproxy.o \
	src/core/keyboard_interrupt.o \
	src/core/main.o  \
	src/core/pyproxy.o \
	src/core/python2js_buffer.o \
	src/core/python2js.o \
	src/pystone.py \
	src/_testcapi.py \
	src/webbrowser.py \
	$(wildcard src/pyodide-py/pyodide/*.py) \
	$(CPYTHONLIB)
	date +"[%F %T] Building pyodide.asm.js..."
	[ -d build ] || mkdir build
	$(CXX) -s EXPORT_NAME="'pyodide'" -o build/pyodide.asm.js $(filter %.o,$^) \
		$(LDFLAGS) -s FORCE_FILESYSTEM=1 \
		--preload-file $(CPYTHONLIB)@/lib/python$(PYMINOR) \
		--preload-file src/webbrowser.py@/lib/python$(PYMINOR)/webbrowser.py \
		--preload-file src/_testcapi.py@/lib/python$(PYMINOR)/_testcapi.py \
		--preload-file src/pystone.py@/lib/python$(PYMINOR)/pystone.py \
		--preload-file src/pyodide-py/pyodide@/lib/python$(PYMINOR)/site-packages/pyodide \
		--exclude-file "*__pycache__*" \
		--exclude-file "*/test/*"
	date +"[%F %T] done building pyodide.asm.js."


env:
	env


build/pyodide.js: src/pyodide.js
	cp $< $@
	sed -i -e 's#{{ PYODIDE_BASE_URL }}#$(PYODIDE_BASE_URL)#g' $@


build/test.html: src/templates/test.html
	cp $< $@


build/console.html: src/templates/console.html
	cp $< $@
	sed -i -e 's#{{ PYODIDE_BASE_URL }}#$(PYODIDE_BASE_URL)#g' $@


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
	flake8 --select=F401 src tools pyodide_build benchmark conftest.py
	clang-format-6.0 -output-replacements-xml `find src -type f -regex ".*\.\(c\|h\|js\)"` | (! grep '<replacement ')
	black --check .
	mypy --ignore-missing-imports pyodide_build/ src/ packages/micropip/micropip/ packages/*/test* conftest.py


apply-lint:
	./tools/apply-lint.sh

benchmark: all
	python benchmark/benchmark.py $(HOSTPYTHON) build/benchmarks.json
	python benchmark/plot_benchmark.py build/benchmarks.json build/benchmarks.png


clean:
	rm -fr build/*
	rm -fr src/*.o
	rm -fr node_modules
	make -C packages clean
	echo "The Emsdk, CPython are not cleaned. cd into those directories to do so."

clean-all: clean
	make -C emsdk clean
	make -C cpython clean
	rm -fr cpython/build

%.o: %.c $(CPYTHONLIB) $(wildcard src/**/*.h)
	$(CC) -o $@ -c $< $(CFLAGS) -Isrc/core/


build/test.data: $(CPYTHONLIB) $(UGLIFYJS)
	( \
		cd $(CPYTHONLIB)/test; \
		find . -type d -name __pycache__ -prune -exec rm -rf {} \; \
	)
	( \
		cd build; \
		python $(FILEPACKAGER) test.data --lz4 --preload ../$(CPYTHONLIB)/test@/lib/python$(PYMINOR)/test --js-output=test.js --export-name=pyodide._module --exclude __pycache__ \
	)
	$(UGLIFYJS) build/test.js -o build/test.js


$(UGLIFYJS): emsdk/emsdk/.complete
	npm i --no-save uglify-js
	touch -h $(UGLIFYJS)


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

minimal :
	PYODIDE_PACKAGES="micropip" make

debug :
	EXTRA_CFLAGS="-D DEBUG_F" \
	EXTRA_LDFLAGS="-s ASSERTIONS=2" \
	PYODIDE_PACKAGES+="micropip,pyparsing,pytz,packaging,kiwisolver,pytest" \
	make
