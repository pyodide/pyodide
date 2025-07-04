.PHONY=pyodide-build

export PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

all:
ifeq ($(ENABLE_PREBUILT_PACKAGES),1)
	@date +"[%F %T] using prebuilt packages..."
	# wget -q -O - $(PYODIDE_PREBUILT_PACKAGES_URL) | tar -xz -C $(PYODIDE_ROOT)/dist
	# override the pyodide runtime version stored in the prebuilt lockfile to match the current runtime version
	jq -c ".info.version = \"$(PYODIDE_VERSION)\"" $(PYODIDE_ROOT)/dist/pyodide-lock.json > $(PYODIDE_ROOT)/dist/pyodide-lock.json.tmp && \
	mv $(PYODIDE_ROOT)/dist/pyodide-lock.json.tmp $(PYODIDE_ROOT)/dist/pyodide-lock.json
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
