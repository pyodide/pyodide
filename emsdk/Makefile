PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all: $(PYODIDE_EMSDK_DIR)/.complete

$(PYODIDE_EMSDK_DIR)/.complete: ../Makefile.envs $(wildcard patches/*.patch)
	if [ -d $(PYODIDE_EMSDK_DIR) ]; then rm -rf $(PYODIDE_EMSDK_DIR); fi
	git clone --depth 1 https://github.com/emscripten-core/emsdk.git $(PYODIDE_EMSDK_DIR)
	cd $(PYODIDE_EMSDK_DIR) && ./emsdk install --build=Release $(PYODIDE_EMSCRIPTEN_VERSION)
	cd $(PYODIDE_EMSDK_DIR)/upstream/emscripten/ && cat ../../../patches/*.patch | patch -p1 --verbose
	cd $(PYODIDE_EMSDK_DIR) && ./emsdk install --build=Release $(PYODIDE_EMSCRIPTEN_VERSION) ccache-git-emscripten-64bit
	cd $(PYODIDE_EMSDK_DIR) && ./emsdk activate --embedded --build=Release $(PYODIDE_EMSCRIPTEN_VERSION)

	# Check that generated_struct_info is up to date.
	git diff --no-index --ignore-all-space $(PYODIDE_EMSDK_DIR)/upstream/emscripten/src/struct_info_generated.json ../src/js/struct_info_generated.json > /dev/null || \
		( \
			echo "" && \
			echo "The vendored copy of struct_info_generated.json does not match the copy in Emscripten" && \
			exit 1 \
		)

	touch $(PYODIDE_EMSDK_DIR)/.complete


update_struct_info:
	rm -f ../src/js/struct_info_generated.json
	cd ../src/js && wget "https://raw.githubusercontent.com/emscripten-core/emscripten/$(PYODIDE_EMSCRIPTEN_VERSION)/src/struct_info_generated.json"


clean:
	rm -rf $(PYODIDE_EMSDK_DIR)
