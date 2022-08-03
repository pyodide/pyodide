PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

ROOT=$(abspath .)

PYTHON_CFLAGS=$(CFLAGS_BASE)

BUILD=$(CPYTHONROOT)/build/Python-$(PYVERSION)
INSTALL=$(CPYTHONINSTALL)
TARBALL=$(ROOT)/downloads/Python-$(PYVERSION).tgz
URL=https://www.python.org/ftp/python/$(PYVERSION)/Python-$(PYVERSION).tgz
LIB=libpython$(PYMAJOR).$(PYMINOR).a

SQLITETARBALL=$(ROOT)/downloads/sqlite-autoconf-3380500.tar.gz
SQLITEBUILD=$(ROOT)/build/sqlite-autoconf-3380500
SQLITEURL=https://sqlite.org/2022/sqlite-autoconf-3380500.tar.gz

FFIBUILD=$(ROOT)/build/libffi
LIBFFIREPO=https://github.com/hoodmane/libffi-emscripten
LIBFFI_TAG=2022-06-23

all: $(INSTALL)/lib/$(LIB) $(INSTALL)/lib/libffi.a


$(INSTALL)/lib/$(LIB): $(BUILD)/$(LIB) remove_modules.txt
	( \
		cd $(BUILD); \
		sed -i -e 's/libinstall:.*/libinstall:/' Makefile; \
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
	cd $(INSTALL)/lib/python$(PYMAJOR).$(PYMINOR)/ && rm -rf `cat $(ROOT)/remove_modules.txt`
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


$(SQLITETARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(SQLITEURL)



$(BUILD)/.patched: $(TARBALL)
	[ -d $(BUILD) ] || (mkdir -p $(dir $(BUILD)); tar -C $(dir $(BUILD)) -xf $(TARBALL))
	cat patches/*.patch | (cd $(BUILD) ; patch -p1)
	touch $@


$(INSTALL)/lib/libsqlite3.a: $(SQLITETARBALL)
	[ -d $(ROOT)/build ] || (mkdir $(ROOT)/build)
	tar -C $(ROOT)/build/ -xf $(SQLITETARBALL)
	# sqlite fails to detect that popen is not available. We have to set it
	# as a CPPFLAG
	( \
		cd $(SQLITEBUILD); \
		emconfigure ./configure CFLAGS="$(PYTHON_CFLAGS)" CPPFLAGS="-DSQLITE_OMIT_POPEN"; \
		emmake make -j $${PYODIDE_JOBS:-3}; \
	)
	mkdir -p $(INSTALL)/lib/
	cp $(SQLITEBUILD)/.libs/libsqlite3.a $(INSTALL)/lib/libsqlite3.a


$(INSTALL)/lib/libffi.a :
	rm -rf $(FFIBUILD)
	git clone $(LIBFFIREPO) --depth 1 --branch $(LIBFFI_TAG) $(FFIBUILD)
	. $(PYODIDE_ROOT)/emsdk/emsdk/emsdk_env.sh && cd $(FFIBUILD) && ./build.sh && make install
	cp $(FFIBUILD)/target/include/*.h $(BUILD)/Include/
	mkdir -p $(INSTALL)/lib
	cp $(FFIBUILD)/target/lib/libffi.a $(INSTALL)/lib/

$(BUILD)/Makefile: $(BUILD)/.patched $(INSTALL)/lib/libsqlite3.a
	# --enable-big-digits=30 :
	#   Python integers have "digits" of size 15 by default on systems with 32
	#   bit pointers and size 30 on systems with 16 bit pointers. Python uses
	#   "digits" of size 15 by default on systems with 32 bit pointers and size
	#   30 on systems with 16 bit pointers. WASM has 32 bit pointers so Python
	#   will default to the size 15 digits but WASM has native 64 bit arithmetic
	#   so it is more efficient to use 30 bit digits.
	cp config.site $(BUILD)/
	( \
		cd $(BUILD); \
		CONFIG_SITE=./config.site READELF=true emconfigure \
		  ./configure \
			  CFLAGS="${PYTHON_CFLAGS}" \
			  CPPFLAGS="-I$(SQLITEBUILD) -sUSE_BZIP2=1 -sUSE_ZLIB=1" \
			  PLATFORM_TRIPLET="$(PLATFORM_TRIPLET)" \
			  --without-pymalloc \
			  --disable-shared \
			  --disable-ipv6 \
			  --enable-big-digits=30 \
			  --enable-optimizations \
			  --host=wasm32-unknown-emscripten\
			  --build=$(shell $(BUILD)/config.guess) \
			  --prefix=$(INSTALL)  \
	)


$(BUILD)/Modules/Setup.local : Setup.local
	cp Setup.local $(BUILD)/Modules/

$(BUILD)/$(LIB): $(BUILD)/Makefile $(BUILD)/pyconfig.h $(BUILD)/Modules/Setup.local $(INSTALL)/lib/libffi.a
	cp Setup.local $(BUILD)/Modules/
	cat pyconfig.undefs.h >> $(BUILD)/pyconfig.h
	( \
		cd $(BUILD); \
		emmake make CROSS_COMPILE=yes $(LIB) -j $${PYODIDE_JOBS:-3} \
	)
	touch $(BUILD)/$(LIB)
