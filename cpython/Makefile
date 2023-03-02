PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

ROOT=$(abspath .)

PYTHON_CFLAGS=$(CFLAGS_BASE) -DPY_CALL_TRAMPOLINE

BUILD=$(CPYTHONROOT)/build/Python-$(PYVERSION)
INSTALL=$(CPYTHONINSTALL)
TARBALL=$(ROOT)/downloads/Python-$(PYVERSION).tgz
URL=https://www.python.org/ftp/python/$(PYVERSION)/Python-$(PYVERSION).tgz
LIB=libpython$(PYMAJOR).$(PYMINOR).a

FFIBUILD=$(ROOT)/build/libffi
LIBFFIREPO=https://github.com/hoodmane/libffi-emscripten
LIBFFI_TAG=2022-06-23

all: $(INSTALL)/lib/$(LIB) $(INSTALL)/lib/libffi.a


$(INSTALL)/lib/$(LIB): $(BUILD)/$(LIB)
	( \
		cd $(BUILD); \
		sed -i -e 's/libinstall:.*/libinstall:/' Makefile; \
		sed -i '/MODOBJS=/s/$$/ $$(LIBMPDEC_OBJS) $$(LIBEXPAT_OBJS) /' Makefile; \
		touch $(BUILD)/$(LIB) ; \
		emmake make PYTHON_FOR_BUILD=$(HOSTPYTHON) CROSS_COMPILE=yes inclinstall libinstall $(LIB) -j $${PYODIDE_JOBS:-3} && \
		cp $(LIB) $(INSTALL)/lib/ \
	)
	# Generate sysconfigdata. It outputs into a subfolder of build/, and
	# the subfolder is written to pybuilddir.txt.
	_PYTHON_SYSCONFIGDATA_NAME=$(SYSCONFIG_NAME) _PYTHON_PROJECT_BASE=$(BUILD) $(HOSTPYTHON) -m sysconfig --generate-posix-vars

	$(eval PYBUILDDIR=`cat pybuilddir.txt`)
	PYTHONPATH=$(PYBUILDDIR) python adjust_sysconfig.py
	cp $(PYBUILDDIR)/$(SYSCONFIG_NAME).py $(INSTALL)/lib/python$(PYMAJOR).$(PYMINOR)/
	mkdir -p $(SYSCONFIGDATA_DIR)
	cp $(PYBUILDDIR)/$(SYSCONFIG_NAME).py $(SYSCONFIGDATA_DIR)
	rm -rf $(PYBUILDDIR)
	rm pybuilddir.txt


clean:
	-rm -fr $(ROOT)/build
	-rm -fr $(ROOT)/installs

clean-all: clean
	-rm -fr $(ROOT)/downloads


$(TARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(URL)
	shasum --algorithm 256 --check checksums --quiet || (rm $@; false)


$(BUILD)/.patched: $(TARBALL)
	[ -d $(BUILD) ] || (mkdir -p $(dir $(BUILD)); tar -C $(dir $(BUILD)) -xf $(TARBALL))
	cat patches/*.patch | (cd $(BUILD) ; patch -p1)
	touch $@

$(INSTALL)/lib/libffi.a :
	rm -rf $(FFIBUILD)
	git clone $(LIBFFIREPO) --depth 1 --branch $(LIBFFI_TAG) $(FFIBUILD)
	. $(PYODIDE_ROOT)/emsdk/emsdk/emsdk_env.sh && cd $(FFIBUILD) && ./build.sh && make install
	cp $(FFIBUILD)/target/include/*.h $(BUILD)/Include/
	mkdir -p $(INSTALL)/lib
	cp $(FFIBUILD)/target/lib/libffi.a $(INSTALL)/lib/

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
			  --with-build-python=$$(which python3.11) \
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
