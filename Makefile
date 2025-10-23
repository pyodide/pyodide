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
src/core/pyodide_pre.o: src/core/pyodide_pre.c src/core/pyodide_pre.gen.dat
	unset _EMCC_CCACHE && emcc --std=c23 -c $< -o $@

src/core/sentinel.wasm: src/core/sentinel.wat | emsdk/emsdk/.complete
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

	@echo "[START] Creating /src/core/libpyodide.a..."
	emar rcs src/core/libpyodide.a $(filter %.o,$^)
	@echo "[END] Created /src/core/libpyodide.a."

# #(CPYTHONLIB) 이전에 수행
$(CPYTHONINSTALL)/include/pyodide/.installed: src/core/*.h
	@echo "[START] include/pyodide/.installed headers..."
	mkdir -p $(@D)
	cp $? $(@D)
	touch $@
	@echo "[END] include/pyodide/.installed to $(@D)"

# $(CPYTHONLIB 호출 주체)
$(CPYTHONINSTALL)/lib/libpyodide.a: src/core/libpyodide.a
	@echo "[START] /lib/libpyodide.a ..."
	mkdir -p $(@D)
	cp $< $@
	@echo "[END] /lib/libpyodide.a to $(@D)"

$(CPYTHONINSTALL)/.installed-pyodide: $(CPYTHONINSTALL)/include/pyodide/.installed $(CPYTHONINSTALL)/lib/libpyodide.a
	@echo "[START] .installed-pyodide."
	touch $@
	@echo "[END] .installed-pyodide."

dist/pyodide.asm.js: \
	src/core/main.o  \
	$(wildcard src/py/lib/*.py) \
	$(CPYTHONLIB) \
	$(CPYTHONINSTALL)/.installed-pyodide

	@echo "[START] Building pyodide.asm.js..."
	@date +"[%F %T] Building pyodide.asm.js..."
	[ -d dist ] || mkdir dist
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
	$(SED) -i -E 's/var __Z[^;]*;//g' dist/pyodide.asm.js
	$(SED) -i '1i "use strict";' dist/pyodide.asm.js
	# Remove last 7 lines of pyodide.asm.js, see issue #2282
	# Hopefully we will remove this after emscripten fixes it, upstream issue
	# emscripten-core/emscripten#16518
	# Sed nonsense from https://stackoverflow.com/a/13383331
	$(SED) -i -n -e :a -e '1,7!{P;N;D;};N;ba' dist/pyodide.asm.js
	echo "globalThis._createPyodideModule = _createPyodideModule;" >> dist/pyodide.asm.js

	@date +"[%F %T] done building pyodide.asm.js."
	@echo "[END] Built pyodide.asm.js."

env:
	env


node_modules/.installed : $(CPYTHONLIB) src/js/package.json src/js/package-lock.json
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

src/core/stack_switching/stack_switching.out.js : src/core/stack_switching/*.mjs node_modules/.installed
	node src/core/stack_switching/esbuild.config.mjs

dist/package.json : src/js/package.json
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
	echo "[START] src/js/generated/\$1"
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
	echo "[END] src/js/generated/\$1"
endef


$(eval $(call preprocess-js,pyproxy.ts))
$(eval $(call preprocess-js,python2js_buffer.js))
$(eval $(call preprocess-js,js2python.js))

pyodide_build .pyodide_build_installed: $(CPYTHONLIB)
	pip install -e ./pyodide-build
	@which pyodide >/dev/null
	touch .pyodide_build_installed


# Recursive wildcard
rwildcard=$(wildcard $1) $(foreach d,$1,$(call rwildcard,$(addsuffix /$(notdir $d),$(wildcard $(dir $d)*))))

dist/python_stdlib.zip: $(call rwildcard,src/py/*) $(CPYTHONLIB) .pyodide_build_installed
	pyodide create-zipfile $(CPYTHONLIB) src/py --exclude "$(PYZIP_EXCLUDE_FILES)" --stub "$(PYZIP_JS_STUBS)" --compression-level "$(PYODIDE_ZIP_COMPRESSION_LEVEL)" --output $@

dist/test.html: src/templates/test.html
	@echo "[START] dist/test.html..."
	cp $< $@
	@echo "[END] dist/test.html."

dist/makesnap.mjs: src/templates/makesnap.mjs
	@echo "[START] dist/makesnap.mjs..."
	cp $< $@
	@echo "[END] dist/makesnap.mjs."

dist/snapshot.bin: all-but-packages dist/pyodide-lock.json dist/makesnap.mjs
	@echo "[START] Building snapshot.bin..."
	cd dist && node --experimental-wasm-stack-switching makesnap.mjs
	@echo "[END] Built snapshot.bin."

dist/module_test.html: src/templates/module_test.html
	cp $< $@

dist/python: src/templates/python
	cp $< $@

dist/python_cli_entry.mjs: src/templates/python_cli_entry.mjs
	cp $< $@


.PHONY: dist/console.html
dist/console.html: src/templates/console.html
	cp $< $@
	$(SED) -i -e 's#{{ PYODIDE_BASE_URL }}#$(PYODIDE_BASE_URL)#g' $@

.PHONY: dist/console-v2.html
dist/console-v2.html: src/templates/console-v2.html
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
	rm -fr dist/*
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
	@echo "[START] Compiling $<"
	$(CC) -o $@ -c $< $(MAIN_MODULE_CFLAGS) -Isrc/core/
	@echo "[END] Compiled $<"

$(CPYTHONLIB): emsdk/emsdk/.complete | check-emcc
	@echo "[START] Building cpython..."
	@date +"[%F %T] Building cpython..."
	make -C $(CPYTHONROOT)
	@date +"[%F %T] done building cpython..."
	@echo "[END] Built cpython."

dist/pyodide-lock.json: .pyodide_build_installed
	@date +"[%F %T] Building packages..."
	make -C packages
	@date +"[%F %T] done building packages..."


emsdk/emsdk/.complete:
	@echo "[START] Building emsdk..."
	@date +"[%F %T] Building emsdk..."
	make -C emsdk
	@date +"[%F %T] done building emsdk."
	@echo "[END] emsdk build complete."

rust:
	echo -e '\033[0;31m[WARNING] The target `make rust` is only for development and we do not guarantee that it will work or be maintained.\033[0m'
	wget -q -O - https://sh.rustup.rs | sh -s -- -y
	source $(HOME)/.cargo/env && rustup toolchain install $(RUST_TOOLCHAIN) && rustup default $(RUST_TOOLCHAIN)
	source $(HOME)/.cargo/env && rustup target add wasm32-unknown-emscripten --toolchain $(RUST_TOOLCHAIN)


check:
	@echo "[START] check dependencies..."
	@./tools/dependency-check.sh
	@echo "[END] check dependencies."


check-emcc: | emsdk/emsdk/.complete
	@echo "[START] check-emcc..."
	@python3 tools/check_ccache.py
	@echo "[END] check-emcc."


debug:
	EXTRA_CFLAGS+=" -D DEBUG_F" \
	make

.PHONY: py-compile
py-compile:
	pyodide py-compile --compression-level "$(PYODIDE_ZIP_COMPRESSION_LEVEL)" --exclude "$(PYCOMPILE_EXCLUDE_FILES)" dist/
