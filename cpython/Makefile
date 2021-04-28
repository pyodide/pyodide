PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

ROOT=$(abspath .)

PYTHON_CFLAGS=$(CFLAGS_BASE)

BUILD=$(ROOT)/build/Python-$(PYVERSION)
INSTALL=$(ROOT)/installs/python-$(PYVERSION)
TARBALL=$(ROOT)/downloads/Python-$(PYVERSION).tgz
URL=https://www.python.org/ftp/python/$(PYVERSION)/Python-$(PYVERSION).tgz
LIB=libpython$(PYMINOR).a
SYSCONFIG_NAME=_sysconfigdata__emscripten_

ZLIBVERSION = 1.2.11
ZLIBTARBALL=$(ROOT)/downloads/zlib-$(ZLIBVERSION).tar.gz
ZLIBBUILD=$(ROOT)/build/zlib-$(ZLIBVERSION)
ZLIBURL=https://zlib.net/zlib-1.2.11.tar.gz

SQLITETARBALL=$(ROOT)/downloads/sqlite-autoconf-3270200.tar.gz
SQLITEBUILD=$(ROOT)/build/sqlite-autoconf-3270200
SQLITEURL=https://www.sqlite.org/2019/sqlite-autoconf-3270200.tar.gz

BZIP2TARBALL=$(ROOT)/downloads/bzip2-1.0.2.tar.gz
BZIP2BUILD=$(ROOT)/build/bzip2-1.0.2
BZIP2URL=https://sourceware.org/pub/bzip2/bzip2-1.0.2.tar.gz


all: $(INSTALL)/lib/$(LIB)


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
	_PYTHON_SYSCONFIGDATA_NAME=$(SYSCONFIG_NAME) _PYTHON_PROJECT_BASE=$(BUILD) python -m sysconfig --generate-posix-vars
	mv `cat pybuilddir.txt`/$(SYSCONFIG_NAME).py $(INSTALL)/lib/python$(PYMINOR)/
	rmdir `cat pybuilddir.txt`
	rm pybuilddir.txt
	cd $(INSTALL)/lib/python$(PYMINOR)/ && rm -rf `cat $(ROOT)/remove_modules.txt`


clean:
	-rm -fr $(BUILD)
	-rm -fr $(INSTALL)


$(TARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(URL)
	md5sum --quiet --check checksums || (rm $@; false)


$(ZLIBTARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(ZLIBURL)


$(SQLITETARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(SQLITEURL)


$(BZIP2TARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(BZIP2URL)



$(BUILD)/.patched: $(TARBALL)
	[ -d $(BUILD) ] || (mkdir -p $(dir $(BUILD)); tar -C $(dir $(BUILD)) -xf $(TARBALL))
	cat patches/*.patch | (cd $(BUILD) ; patch -p1)
	touch $@


$(ZLIBBUILD)/.configured: $(ZLIBTARBALL)
	[ -d $(ROOT)/build ] || (mkdir $(ROOT)/build)
	tar -C $(ROOT)/build/ -xf $(ROOT)/downloads/zlib-1.2.11.tar.gz
	cd $(ZLIBBUILD); emconfigure ./configure
	touch $@


$(SQLITEBUILD)/libsqlite3.la: $(SQLITETARBALL)
	[ -d $(ROOT)/build ] || (mkdir $(ROOT)/build)
	tar -C $(ROOT)/build/ -xf $(SQLITETARBALL)
	# sqlite fails to detect that popen is not available. We have to set it
	# as a CPPFLAG
	( \
		cd $(SQLITEBUILD); \
		emconfigure ./configure CFLAGS="$(PYTHON_CFLAGS)" CPPFLAGS="-DSQLITE_OMIT_POPEN"; \
		emmake make -j $${PYODIDE_JOBS:-3}; \
	)


$(BZIP2BUILD)/libbz2.a: $(BZIP2TARBALL)
	[ -d $(ROOT)/build ] || (mkdir $(ROOT)/build)
	tar -C $(ROOT)/build/ -xf $(BZIP2TARBALL)
	( \
		cd $(BZIP2BUILD); \
		emmake make -j $${PYODIDE_JOBS:-3} CC=emcc CFLAGS="$(PYTHON_CFLAGS) -D_FILE_OFFSET_BITS=64" AR=emar RANLIB=emranlib libbz2.a; \
	)


$(BUILD)/Makefile: $(BUILD)/.patched $(ZLIBBUILD)/.configured $(SQLITEBUILD)/libsqlite3.la $(BZIP2BUILD)/libbz2.a
	cp config.site $(BUILD)/
	( \
		cd $(BUILD); \
		CONFIG_SITE=./config.site READELF=true emconfigure \
		  ./configure \
			  CFLAGS="${PYTHON_CFLAGS}" \
			  CPPFLAGS="-I$(SQLITEBUILD) -I$(BZIP2BUILD) -I$(ZLIBBUILD)" \
			  --without-pymalloc \
			  --disable-shared \
			  --disable-ipv6 \
			  --without-gcc \
			  --host=wasm32-unknown-emscripten\
			  --build=$(shell $(BUILD)/config.guess) \
			  --prefix=$(INSTALL) ; \
	)


$(BUILD)/$(LIB): $(BUILD)/Makefile Setup.local
	cp Setup.local $(BUILD)/Modules/
	cat pyconfig.undefs.h >> $(BUILD)/pyconfig.h
	( \
		cd $(BUILD); \
		emmake make CROSS_COMPILE=yes $(LIB) -j $${PYODIDE_JOBS:-3} \
	)
	touch $(BUILD)/$(LIB)
