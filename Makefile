PYODIDE_ROOT=$(abspath .)

include Makefile.envs

.PHONY: check check-emcc

CC=emcc
CXX=em++


all: \
	all-but-packages \
	dist/pyodide-lock.json \
	dist/pyodide.d.ts \
	dist/snapshot.bin \


all-but-packages: \
	check \
	check-emcc \
	$(CPYTHONINSTALL)/.installed-pyodide \
	dist/pyodide.asm.js \
	dist/pyodide.js \
	dist/package.json \
	dist/python \
	dist/python_cli_entry.mjs \
	dist/python_stdlib.zip \
	dist/test.html \
	dist/console.html \
	dist/console-v2.html \
	dist/module_test.html \


src/core/pyodide_pre.gen.dat: src/js/generated/_pyodide.out.js src/core/pre.js src/core/stack_switching/stack_switching.out.js
# Our goal here is to inject src/js/generated/_pyodide.out.js into an archive
# file so that when linked, Emscripten will include it. We use the same pathway
# that EM_JS uses, but EM_JS is itself unsuitable. Why? Because the C
# preprocessor / compiler modified strings and there is no "raw" strings
# feature. In particular, it seems to choke on regex in the JavaScript code. Our
# bundle includes vendored npm packages which we have no control over, so it is
# not simple to rewrite the code to restrict it to syntax that is legal inside
# of EM_JS.
#
# To get around this problem, we use an array initializer instead of a string
# initializer, with #embed.
#
# EM_JS works by injecting a string variable into a special section called em_js
# called __em_js__<function_name>. The contents of this variable are of the form
# "argspec<::>body". The argspec is used to generate the JavaScript function
# declaration:
# https://github.com/emscripten-core/emscripten/blob/085fe968d43c7d3674376f29667d6e5f42b24966/emscripten.py?plain=1#L603
#
# The body has to start with a function block, but it is possible to inject
# extra stuff after the block ends. We make a 0-argument function called
# pyodide_js_init. Immediately after that we inject pre.js and then a call to
# the init function.
	rm -f $@
	echo '()<::>{' >> $@                       # zero argument argspec and start body
	cat src/js/generated/_pyodide.out.js >> $@ # All of _pyodide.out.js is body
	echo '}' >> $@                             # Close function body
	cat src/core/stack_switching/stack_switching.out.js >> $@
	cat src/core/pre.js >> $@                  # Execute pre.js too
	echo "pyodide_js_init();" >> $@            # Then execute the function.


# Don't use ccache here because it does not support #embed properly.
# https://github.com/ccache/ccache/discussions/1366
src/core/pyodide_pre.o: src/core/pyodide_pre.c src/core/pyodide_pre.gen.dat emsdk/emsdk/.complete
	unset _EMCC_CCACHE && emcc --std=c23 -c $< -o $@

src/core/sentinel.wasm: src/core/sentinel.wat emsdk/emsdk/.complete
	./emsdk/emsdk/upstream/bin/wasm-as $< -o $@ -all

src/core/libpyodide.a: \
	src/core/docstring.o \
	src/core/error_handling.o \
	src/core/hiwire.o \
	src/core/_pyodide_core.o \
	src/core/js2python.o \
	src/core/jsproxy.o \
	src/core/jsproxy_call.o \
	src/core/jsbind.o \
	src/core/pyproxy.o \
	src/core/python2js_buffer.o \
	src/core/jslib.o \
	src/core/jsbind.o \
	src/core/python2js.o \
	src/core/pyodide_pre.o \
	src/core/stack_switching/pystate.o \
	src/core/stack_switching/suspenders.o \
	src/core/print.o

	emar rcs src/core/libpyodide.a $(filter %.o,$^)

$(CPYTHONINSTALL)/include/pyodide/.installed: src/core/*.h
	mkdir -p $(@D)
	cp $? $(@D)
	touch $@

$(CPYTHONINSTALL)/lib/libpyodide.a: src/core/libpyodide.a
	mkdir -p $(@D)
	cp $< $@

$(CPYTHONINSTALL)/.installed-pyodide: $(CPYTHONINSTALL)/include/pyodide/.installed $(CPYTHONINSTALL)/lib/libpyodide.a
	touch $@

dist/pyodide.asm.js: \
	dist \
	src/core/main.o  \
	$(wildcard src/py/lib/*.py) \
	$(CPYTHONLIB) \
	$(CPYTHONINSTALL)/.installed-pyodide

	@date +"[%F %T] Building pyodide.asm.js..."
   # TODO(ryanking13): Link libgl to a side module not to the main module.
   # For unknown reason, a side module cannot see symbols when libGL is linked to it.
	embuilder build libgl
	$(CXX) -o dist/pyodide.asm.js -lpyodide src/core/main.o $(MAIN_MODULE_LDFLAGS)

	if [[ -n $${PYODIDE_SOURCEMAP+x} ]] || [[ -n $${PYODIDE_SYMBOLS+x} ]] || [[ -n $${PYODIDE_DEBUG_JS+x} ]]; then \
		cd dist && npx prettier -w pyodide.asm.js ; \
	fi

   # Strip out C++ symbols which all start __Z.
   # There are 4821 of these and they have VERY VERY long names.
   # To show some stats on the symbols you can use the following:
   # cat dist/pyodide.asm.js | grep -ohE 'var _{0,5}.' | sort | uniq -c | sort -nr | head -n 20
	$(SED) -i -E 's/__Z[a-zA-Z0-9_]*,//g' dist/pyodide.asm.js
	$(SED) -i -E 's/var __Z[^;]*;//g' dist/pyodide.asm.js
	$(SED) -i -E 's/__Z[^;]*wasmExports[^;]*;//g' dist/pyodide.asm.js
	$(SED) -i '1i "use strict";' dist/pyodide.asm.js
	# Remove compatibility issues with requirejs see issue #2282
	# Hopefully we will remove this after emscripten fixes it, upstream issue
	# emscripten-core/emscripten#16518
	$(SED) -i 's/if(typeof exports==="object"&&typeof module==="object"){module\.exports=_createPyodideModule;module\.exports\.default=_createPyodideModule}else if(typeof define==="function"&&define\["amd"\])define(\[\],()=>_createPyodideModule);//g' dist/pyodide.asm.js
	echo "globalThis._createPyodideModule = _createPyodideModule;" >> dist/pyodide.asm.js

	@date +"[%F %T] done building pyodide.asm.js."

env:
	env


node_modules/.installed: src/js/package.json src/js/package-lock.json
	cd src/js && npm ci
	ln -sfn src/js/node_modules/ node_modules
	touch $@

src/js/generated/_pyodide.out.js:            \
		src/js/*.ts                          \
		src/js/common/*                      \
		src/js/vendor/*                      \
		src/js/generated/pyproxy.ts          \
		src/js/generated/python2js_buffer.js \
		src/js/generated/js2python.js        \
		node_modules/.installed
	cd src/js && npm run build-inner && cd -

dist/pyodide.js:                             \
		dist/pyodide.asm.js            		 \
		src/js/generated/_pyodide.out.js  	 \
		src/js/pyodide.ts                    \
		src/js/compat.ts                     \
		src/js/emscripten-settings.ts        \
		src/js/version.ts                    \
		src/core/sentinel.wasm
	cd src/js && npm run build

src/core/stack_switching/stack_switching.out.js: src/core/stack_switching/*.mjs node_modules/.installed
	node src/core/stack_switching/esbuild.config.mjs

dist/package.json: src/js/package.json dist
	cp $< $@

.PHONY: npm-link
npm-link: dist/package.json
	cd src/test-js && npm ci && npm link ../../dist

dist/pyodide.d.ts dist/pyodide/ffi.d.ts: dist/pyodide.js src/js/*.ts src/js/generated/pyproxy.ts node_modules/.installed
	npx dts-bundle-generator src/js/{pyodide,ffi}.ts --export-referenced-types false --project src/js/tsconfig.json
	mv src/js/{pyodide,ffi}.d.ts dist
	python3 tools/fixup-type-definitions.py dist/pyodide.d.ts
	python3 tools/fixup-type-definitions.py dist/ffi.d.ts


define preprocess-js

src/js/generated/$1: $(CPYTHONLIB) src/core/$1 src/core/pyproxy.c src/core/*.h
	# We can't input a js/ts file directly because CC will be unhappy about the file
	# extension. Instead cat it and have CC read from stdin.
	# -E : Only apply prepreocessor
	# -C : Leave comments alone (this allows them to be preserved in typescript
	#      definition files, rollup will strip them out)
	# -P : Don't put in macro debug info
	# -imacros pyproxy.c : include all of the macros definitions from pyproxy.c
	#
	# First we use sed to delete the segments of the file between
	# "// pyodide-skip" and "// end-pyodide-skip". This allows us to give
	# typescript type declarations for the macros which we need for intellisense
	# and documentation generation. The result of processing the type
	# declarations with the macro processor is a type error, so we snip them
	# out.
	rm -f $$@
	mkdir -p src/js/generated
	echo "// This file is generated by applying the C preprocessor to src/core/$1" >> $$@
	echo "// Do not edit it directly!" >> $$@
	cat src/core/$1 | \
		$(SED) '/^\/\/\s*pyodide-skip/,/^\/\/\s*end-pyodide-skip/d' | \
		$(CC) -E -C -P -imacros src/core/pyproxy.c $(MAIN_MODULE_CFLAGS) - | \
		$(SED) 's/^#pragma clang.*//g' \
		>> $$@
endef


$(eval $(call preprocess-js,pyproxy.ts))
$(eval $(call preprocess-js,python2js_buffer.js))
$(eval $(call preprocess-js,js2python.js))

pyodide_build .pyodide_build_installed:
	pip install -e ./pyodide-build
	@which pyodide >/dev/null
	touch .pyodide_build_installed


# Recursive wildcard
rwildcard=$(wildcard $1) $(foreach d,$1,$(call rwildcard,$(addsuffix /$(notdir $d),$(wildcard $(dir $d)*))))

dist:
	[ -d dist ] || mkdir dist

dist/python_stdlib.zip: $(call rwildcard,src/py/*) $(CPYTHONLIB) .pyodide_build_installed
	pyodide create-zipfile $(CPYTHONLIB) src/py --exclude "$(PYZIP_EXCLUDE_FILES)" --stub "$(PYZIP_JS_STUBS)" --compression-level "$(PYODIDE_ZIP_COMPRESSION_LEVEL)" --output $@

dist/test.html: src/templates/test.html dist
	cp $< $@

dist/makesnap.mjs: src/templates/makesnap.mjs dist
	cp $< $@

dist/snapshot.bin: all-but-packages dist/pyodide-lock.json dist/makesnap.mjs
	cd dist && node --experimental-wasm-stack-switching makesnap.mjs

dist/module_test.html: src/templates/module_test.html dist
	cp $< $@

dist/python: src/templates/python dist
	cp $< $@

dist/python_cli_entry.mjs: src/templates/python_cli_entry.mjs dist
	cp $< $@


.PHONY: dist/console.html dist/console-v2.html
dist/console.html: src/templates/console.html dist
	cp $< $@
	$(SED) -i -e 's#{{ PYODIDE_BASE_URL }}#$(PYODIDE_BASE_URL)#g' $@

dist/console-v2.html: src/templates/console-v2.html dist
	cp $< $@
	sed -i -e 's#{{ PYODIDE_BASE_URL }}#$(PYODIDE_BASE_URL)#g' $@


# Prepare the dist directory for the release by removing unneeded files
.PHONY: clean-dist-dir
clean-dist-dir:
	# Remove snapshot files
	rm dist/makesnap.mjs
	rm dist/snapshot.bin
	rm dist/module_test.html dist/test.html

	# TODO: Source maps aren't useful outside of debug builds I don't think. But
	# removing them adds "missing sourcemap" warnings to JS console. We should
	# not generate them in the first place?
	# rm dist/*.map


.PHONY: lint
lint:
	pre-commit run -a --show-diff-on-failure

benchmark: all
	$(HOSTPYTHON) benchmark/benchmark.py all --output dist/benchmarks.json
	$(HOSTPYTHON) benchmark/plot_benchmark.py dist/benchmarks.json dist/benchmarks.png


clean:
	rm -fr dist
	rm -fr node_modules
	find src -name '*.o' -delete
	find src -name '*.wasm' -delete
	find src -name '*.gen.*' -delete
	find src -name '*.out.*' -delete
	rm -fr src/js/generated
	make -C packages clean
	rm -f .pyodide_build_installed
	echo "The Emsdk, CPython are not cleaned. cd into those directories to do so."

clean-python: clean
	make -C cpython clean

clean-all: clean
	make -C emsdk clean
	make -C cpython clean-all

%.o: %.c $(CPYTHONLIB) $(wildcard src/core/*.h src/core/*.js)
	$(CC) -o $@ -c $< $(MAIN_MODULE_CFLAGS) -Isrc/core/

$(CPYTHONLIB): emsdk/emsdk/.complete
	@date +"[%F %T] Building cpython..."
	make -C $(CPYTHONROOT)
	@date +"[%F %T] done building cpython..."

dist/pyodide-lock.json: $(CPYTHONLIB) .pyodide_build_installed
	@date +"[%F %T] Building packages..."
	make -C packages
	@date +"[%F %T] done building packages..."


emsdk/emsdk/.complete:
	@date +"[%F %T] Building emsdk..."
	make -C emsdk
	@date +"[%F %T] done building emsdk."

rust:
	echo -e '\033[0;31m[WARNING] The target `make rust` is only for development and we do not guarantee that it will work or be maintained.\033[0m'
	wget -q -O - https://sh.rustup.rs | sh -s -- -y
	source $(HOME)/.cargo/env && rustup toolchain install $(RUST_TOOLCHAIN) && rustup default $(RUST_TOOLCHAIN)
	source $(HOME)/.cargo/env && rustup target add wasm32-unknown-emscripten --toolchain $(RUST_TOOLCHAIN)


check:
	@./tools/dependency-check.sh

check-emcc: emsdk/emsdk/.complete
	@python3 tools/check_ccache.py

debug:
	EXTRA_CFLAGS+=" -D DEBUG_F" \
	make

.PHONY: py-compile
py-compile:
	pyodide py-compile --compression-level "$(PYODIDE_ZIP_COMPRESSION_LEVEL)" --exclude "$(PYCOMPILE_EXCLUDE_FILES)" dist/
