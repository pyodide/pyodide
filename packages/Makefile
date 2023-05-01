.PHONY=pyodide-build

export PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all:
	mkdir -p $(HOSTINSTALLDIR) $(WASM_LIBRARY_DIR)
	PYODIDE_ROOT=$(PYODIDE_ROOT) pyodide build-recipes \
	"$(PYODIDE_PACKAGES)" \
	--recipe-dir=./ \
	--install \
	--install-dir=../dist \
	--n-jobs $${PYODIDE_JOBS:-4} \
	--log-dir=./build-logs \
	--compression-level "$(PYODIDE_ZIP_COMPRESSION_LEVEL)"

update-all:
	for pkg in $$(find . -maxdepth 1 ! -name ".*" -type d -exec basename {} \; | tail -n +2); do \
		PYODIDE_ROOT=$(PYODIDE_ROOT) pyodide skeleton pypi "$${pkg}" --update-patched; \
	done

clean:
	rm -rf ./*/build ./*/build.log ./*/dist
	rm -rf ./.artifacts ./.libs
