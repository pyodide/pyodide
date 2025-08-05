.PHONY=pyodide-build

export PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

# Set default packages if not specified
# These are enough to run the core test suite
PYODIDE_PACKAGES ?= tag:pytest,tag:pyodide.test

all:
ifeq ($(ENABLE_PREBUILT_PACKAGES),1)
	@date +"[%F %T] using prebuilt packages..."
	wget -q -O - $(PYODIDE_PREBUILT_PACKAGES_URL) | tar -xz -C $(PYODIDE_ROOT)/dist
else
	pyodide build-recipes "$(PYODIDE_PACKAGES)" \
		--install \
		--metadata-files \
		--n-jobs $${PYODIDE_JOBS:-4} \
		--log-dir=./build-logs \
		--compression-level "$(PYODIDE_ZIP_COMPRESSION_LEVEL)"
endif


update-all:
	for pkg in $$(find . -maxdepth 1 ! -name ".*" -type d -exec basename {} \; | tail -n +2); do \
		PYODIDE_ROOT=$(PYODIDE_ROOT) pyodide skeleton pypi "$${pkg}" --update-patched; \
	done

clean:
	rm -rf ./*/build ./*/build.log ./*/dist
	rm -rf ./.artifacts ./.libs
