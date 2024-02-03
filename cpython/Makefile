PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

ROOT=$(abspath .)

PYTHON_CFLAGS=$(CFLAGS_BASE) -DPY_CALL_TRAMPOLINE

BUILD=$(CPYTHONROOT)/build/Python-$(PYVERSION)
INSTALL=$(CPYTHONINSTALL)
TARBALL=$(ROOT)/downloads/Python-$(PYVERSION).tgz
LIB=libpython$(PYMAJOR).$(PYMINOR)$(CPYTHON_ABI_FLAGS).a

FFIBUILD=$(ROOT)/build/libffi
LIBFFIREPO=https://github.com/libffi/libffi
LIBFFI_COMMIT=f08493d249d2067c8b3207ba46693dd858f95db3

HIWIREBUILD=$(ROOT)/build/hiwire
HIWIREREPO=https://github.com/hoodmane/hiwire
HIWIRE_COMMIT=49f3450e34f3f50d4b8296e782dc321bb2e3264e

ifdef CPYTHON_DEBUG
	MAYBE_WITH_PYDEBUG=--with-pydebug
endif

all: $(INSTALL)/lib/$(LIB) $(INSTALL)/lib/libffi.a $(INSTALL)/lib/libhiwire.a

.PHONY=sysconfigdata
sysconfigdata:
	# Generate sysconfigdata. It outputs into a subfolder of build/, and
	# the subfolder is written to pybuilddir.txt.
	cd $(BUILD) && _PYTHON_SYSCONFIGDATA_NAME=$(SYSCONFIG_NAME) _PYTHON_PROJECT_BASE=$(BUILD) $(HOSTPYTHON) -m sysconfig --generate-posix-vars
	$(eval PYBUILDDIR=$(BUILD)/`cat $(BUILD)/pybuilddir.txt`)
	PYTHONPATH=$(PYBUILDDIR) python$(PYMAJOR).$(PYMINOR) adjust_sysconfig.py
	mkdir -p $(INSTALL)/lib/python$(PYMAJOR).$(PYMINOR)/
	mkdir -p $(SYSCONFIGDATA_DIR)
	cp $(PYBUILDDIR)/$(SYSCONFIG_NAME).py $(INSTALL)/lib/python$(PYMAJOR).$(PYMINOR)/
	cp $(PYBUILDDIR)/$(SYSCONFIG_NAME).py $(SYSCONFIGDATA_DIR)


$(INSTALL)/lib/$(LIB): $(BUILD)/$(LIB) sysconfigdata
	( \
		cd $(BUILD); \
		sed -i -e 's/libinstall:.*/libinstall:/' Makefile; \
		sed -i '/MODOBJS=/s/$$/ $$(LIBMPDEC_OBJS) $$(LIBEXPAT_OBJS) /' Makefile; \
		touch $(BUILD)/$(LIB) ; \
		emmake make PYTHON_FOR_BUILD=$(HOSTPYTHON) CROSS_COMPILE=yes inclinstall libinstall $(LIB) -j $${PYODIDE_JOBS:-3} && \
		cp $(LIB) $(INSTALL)/lib/ \
	)


.PHONY=rebuild
rebuild: sysconfigdata
	emmake make -C $(BUILD) PYTHON_FOR_BUILD=$(HOSTPYTHON) CROSS_COMPILE=yes inclinstall libinstall $(LIB) -j $${PYODIDE_JOBS:-3}
	cp $(BUILD)/$(LIB) $(INSTALL)/lib/


clean:
	-rm -fr $(ROOT)/build
	-rm -fr $(ROOT)/installs

clean-all: clean
	-rm -fr $(ROOT)/downloads


$(TARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(PYTHON_ARCHIVE_URL)
	@GOT_SHASUM=`shasum --algorithm 256 $(TARBALL) | cut -f1 -d' '` \
		&& (echo $$GOT_SHASUM | grep -q $(PYTHON_ARCHIVE_SHA256)) \
		|| (\
			   echo "Got unexpected shasum $$GOT_SHASUM" \
			&& echo "If you are updating the Python version, set PYTHON_ARCHIVE_SHA256 in Makefile.envs to this." \
			&& exit 1 \
		)



$(BUILD)/.patched: $(TARBALL)
	[ -d $(BUILD) ] || (mkdir -p $(dir $(BUILD)); tar -C $(dir $(BUILD)) -xf $(TARBALL))
	cat patches/*.patch | (cd $(BUILD) ; patch -p1)
	touch $@

$(INSTALL)/lib/libffi.a :
	rm -rf $(FFIBUILD)
	mkdir $(FFIBUILD)
	(\
		cd $(FFIBUILD) \
		&& git init \
		&& git fetch --depth 1 $(LIBFFIREPO) $(LIBFFI_COMMIT) \
		&& git checkout FETCH_HEAD \
		&& . $(PYODIDE_ROOT)/emsdk/emsdk/emsdk_env.sh \
		&& ./testsuite/emscripten/build.sh --wasm-bigint \
		&& make install \
	)
	cp $(FFIBUILD)/target/include/*.h $(BUILD)/Include/
	mkdir -p $(INSTALL)/lib
	cp $(FFIBUILD)/target/lib/libffi.a $(INSTALL)/lib/

$(INSTALL)/lib/libhiwire.a :
	rm -rf $(HIWIREBUILD)
	mkdir $(HIWIREBUILD)
	(\
		cd $(HIWIREBUILD) \
		&& git init \
		&& git fetch --depth 1 $(HIWIREREPO) $(HIWIRE_COMMIT) \
		&& git checkout FETCH_HEAD \
		&& . $(PYODIDE_ROOT)/emsdk/emsdk/emsdk_env.sh \
		&& CC=emcc EMSCRIPTEN_DEDUPLICATE=1 EXTERN_FAIL=1 make \
	)
	cp -r $(HIWIREBUILD)/dist/lib $(INSTALL)/
	cp -r $(HIWIREBUILD)/dist/include $(INSTALL)/include/hiwire

$(BUILD)/Makefile: $(BUILD)/.patched
	# --enable-big-digits=30 :
	#   Python integers have "digits" of size 15 by default on systems with 32
	#   bit pointers and size 30 on systems with 16 bit pointers. Python uses
	#   "digits" of size 15 by default on systems with 32 bit pointers and size
	#   30 on systems with 16 bit pointers. WASM has 32 bit pointers so Python
	#   will default to the size 15 digits but WASM has native 64 bit arithmetic
	#   so it is more efficient to use 30 bit digits.
	( \
		cd $(BUILD); \
		CONFIG_SITE=./Tools/wasm/config.site-wasm32-emscripten READELF=true emconfigure \
		  ./configure \
			  CFLAGS="${PYTHON_CFLAGS}" \
			  CPPFLAGS="-sUSE_BZIP2=1 -sUSE_ZLIB=1" \
			  PLATFORM_TRIPLET="$(PLATFORM_TRIPLET)" \
			  --without-pymalloc \
			  --disable-shared \
			  --disable-ipv6 \
			  --enable-big-digits=30 \
			  --enable-optimizations \
			  --host=wasm32-unknown-emscripten\
			  --build=$(shell $(BUILD)/config.guess) \
			  --prefix=$(INSTALL)  \
			  --with-build-python=$$(which python$(PYMAJOR).$(PYMINOR)) \
			  $(MAYBE_WITH_PYDEBUG) \
	)


$(BUILD)/Modules/Setup.local: Setup.local
	cp Setup.local $(BUILD)/Modules/

$(BUILD)/$(LIB): $(BUILD)/Makefile $(BUILD)/pyconfig.h $(BUILD)/Modules/Setup.local $(INSTALL)/lib/libffi.a
	cp Setup.local $(BUILD)/Modules/
	( \
		cd $(BUILD); \
		make regen-frozen; \
		emmake make CROSS_COMPILE=yes $(LIB) -j $${PYODIDE_JOBS:-3} \
	)
	touch $(BUILD)/$(LIB)
