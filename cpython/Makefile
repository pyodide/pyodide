PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

ROOT=$(abspath .)

BUILD=$(ROOT)/build/Python-$(PYVERSION)
INSTALL=$(ROOT)/installs/python-$(PYVERSION)
TARBALL=$(ROOT)/downloads/Python-$(PYVERSION).tgz
URL=https://www.python.org/ftp/python/$(PYVERSION)/Python-$(PYVERSION).tgz
LIB=libpython$(PYMINOR).a


ZLIBVERSION = 1.2.11
ZLIBTARBALL=$(ROOT)/downloads/zlib-$(ZLIBVERSION).tar.gz
ZLIBBUILD=$(ROOT)/build/zlib-$(ZLIBVERSION)
ZLIBURL=https://zlib.net/zlib-1.2.11.tar.gz

SQLITETARBALL=$(ROOT)/downloads/sqlite-autoconf-3270200.tar.gz
SQLITEBUILD=$(ROOT)/build/sqlite-autoconf-3270200
SQLITEURL=https://www.sqlite.org/2019/sqlite-autoconf-3270200.tar.gz

BZIP2TARBALL=$(ROOT)/downloads/bzip2-1.0.2.tar.gz
BZIP2BUILD=$(ROOT)/build/bzip2-1.0.2
BZIP2URL=ftp://sourceware.org/pub/bzip2/v102/bzip2-1.0.2.tar.gz


all: $(INSTALL)/lib/$(LIB)


$(INSTALL)/lib/$(LIB): $(BUILD)/$(LIB)
	( \
		cd $(BUILD); \
		sed -i -e 's/libinstall:.*/libinstall:/' Makefile; \
		touch $(BUILD)/$(LIB) ; \
		emmake make PYTHON_FOR_BUILD=$(HOSTPYTHON) CROSS_COMPILE=yes inclinstall libinstall $(LIB) -j $${PYODIDE_JOBS:-3} && \
		cp $(LIB) $(INSTALL)/lib/ && \
		cp $(HOSTPYTHONROOT)/lib/python$(PYMINOR)/`$(HOSTPYTHON) -c "import sysconfig; print(sysconfig._get_sysconfigdata_name())"`.py $(INSTALL)/lib/python$(PYMINOR)/_sysconfigdata__emscripten_.py; \
		sed -i -e 's#'"$(PYODIDE_ROOT)"'##g' $(INSTALL)/lib/python$(PYMINOR)/_sysconfigdata__emscripten_.py; \
	)


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
	( \
		cd $(SQLITEBUILD); \
		emconfigure ./configure; \
		emmake make -j $${PYODIDE_JOBS:-3}; \
	)


$(BZIP2BUILD)/libbz2.a: $(BZIP2TARBALL)
	[ -d $(ROOT)/build ] || (mkdir $(ROOT)/build)
	tar -C $(ROOT)/build/ -xf $(BZIP2TARBALL)
	( \
		cd $(BZIP2BUILD); \
		emmake make -j $${PYODIDE_JOBS:-3} CC=emcc CFLAGS="-Wall -Winline -O2 -fomit-frame-pointer -D_FILE_OFFSET_BITS=64" AR=emar RANLIB=emranlib libbz2.a; \
	)


$(BUILD)/Makefile: $(BUILD)/.patched $(ZLIBBUILD)/.configured $(SQLITEBUILD)/libsqlite3.la $(BZIP2BUILD)/libbz2.a
	cp config.site $(BUILD)/
	( \
		cd $(BUILD); \
		EMCC_CFLAGS="-s WASM=0" CONFIG_SITE=./config.site READELF=true LD_RUN_PATH="$(SQLITEBUILD):$(BZIP2BUILD)" emconfigure \
		  ./configure \
			  CPPFLAGS="-I$(SQLITEBUILD) -I$(BZIP2BUILD) -I$(ZLIBBUILD)" \
			  LDFLAGS="-L$(SQLITEBUILD) -L$(BZIP2BUILD)" \
			  --without-pymalloc \
			  --disable-shared \
			  --disable-ipv6 \
			  --without-gcc \
			  --host=asmjs-unknown-emscripten \
			  --build=$(shell $(BUILD)/config.guess) \
			  --prefix=$(INSTALL) ; \
	)


$(BUILD)/$(LIB): $(BUILD)/Makefile Setup.local
	cp Setup.local $(BUILD)/Modules/
	cat pyconfig.undefs.h >> $(BUILD)/pyconfig.h
	( \
		cp $(HOSTPYTHONROOT)/lib/python$(PYMINOR)/`$(HOSTPYTHON) -c "import sysconfig; print(sysconfig._get_sysconfigdata_name())"`.py $(BUILD)/Lib/_sysconfigdata__emscripten_.py; \
		cd $(BUILD); \
		emmake make CROSS_COMPILE=yes $(LIB) -j $${PYODIDE_JOBS:-3} \
	)
	sed -i -e 's/\-undefined dynamic_lookup//' $(BUILD)/Lib/_sysconfigdata__emscripten_.py
	touch $(BUILD)/$(LIB)
