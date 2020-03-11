PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

ROOT=$(abspath .)

HOSTINSTALL=$(ROOT)/build/$(PYVERSION)/host
HOSTBUILD=$(HOSTINSTALL)/Python-$(PYVERSION)
HOSTPYTHON=$(HOSTINSTALL)/bin/python3$(EXE)
HOSTPYTHON_CPPFLAGS="-I/usr/local/opt/openssl/include"
HOSTPYTHON_LDFLAGS="-L/usr/local/opt/openssl/lib"
HOSTPGEN=$(HOSTINSTALL)/bin/pgen$(EXE)

BUILD=$(ROOT)/build/$(PYVERSION)/Python-$(PYVERSION)
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
BZIP2URL=ftp://sources.redhat.com/pub/bzip2/v102/bzip2-1.0.2.tar.gz


all: $(INSTALL)/lib/$(LIB)


$(INSTALL)/lib/$(LIB): $(BUILD)/$(LIB)
	( \
		cd $(BUILD); \
		sed -i -e 's/libinstall:.*/libinstall:/' Makefile; \
		touch $(BUILD)/$(LIB) ; \
		emmake make HOSTPYTHON=$(HOSTPYTHON) PYTHON_FOR_BUILD=$(HOSTPYTHON) CROSS_COMPILE=yes inclinstall libinstall $(LIB) && \
		cp $(LIB) $(INSTALL)/lib/ && \
		cp $(HOSTINSTALL)/lib/python$(PYMINOR)/`$(HOSTPYTHON) -c "import sysconfig; print(sysconfig._get_sysconfigdata_name())"`.py $(INSTALL)/lib/python$(PYMINOR)/_sysconfigdata__emscripten_.py; \
		sed -i -e 's#'"$(PYODIDE_ROOT)"'##g' $(INSTALL)/lib/python$(PYMINOR)/_sysconfigdata__emscripten_.py; \
	)


clean:
	-rm -fr $(HOSTINSTALL)
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


$(HOSTPYTHON) $(HOSTPGEN): $(TARBALL)
	mkdir -p $(HOSTINSTALL)
	[ -d $(HOSTBUILD) ] || tar -C $(HOSTINSTALL) -xf $(TARBALL)
	( \
		cd $(HOSTBUILD); \
		PKG_CONFIG_PATH="/usr/local/opt/openssl/lib/pkgconfig" ./configure --prefix=$(HOSTINSTALL) || cat config.log && \
	  make regen-grammar && \
		make install && \
		cp Parser/pgen$(EXE) $(HOSTINSTALL)/bin/ && \
		make distclean \
	)


$(BUILD)/.patched: $(TARBALL)
	[ -d $(BUILD) ] || (mkdir -p $(dir $(BUILD)); tar -C $(dir $(BUILD)) -xf $(TARBALL))
	cat patches/*.patch | (cd $(BUILD) ; patch -p1)
	touch $@


$(ZLIBBUILD)/.patched: $(ZLIBTARBALL)
	[ -d $(ROOT)/build ] || (mkdir $(ROOT)/build)
	tar -C $(ROOT)/build/ -xf $(ROOT)/downloads/zlib-1.2.11.tar.gz
	cat patches/zlib/*.patch | (cd $(ZLIBBUILD) ; patch -p1)
	touch $@


$(SQLITEBUILD)/libsqlite3.la: $(SQLITETARBALL)
	[ -d $(ROOT)/build ] || (mkdir $(ROOT)/build)
	tar -C $(ROOT)/build/ -xf $(SQLITETARBALL)
	( \
		cd $(SQLITEBUILD); \
		emconfigure ./configure; \
		emmake make; \
	)


$(BZIP2BUILD)/libbz2.a: $(BZIP2TARBALL)
	[ -d $(ROOT)/build ] || (mkdir $(ROOT)/build)
	tar -C $(ROOT)/build/ -xf $(BZIP2TARBALL)
	( \
		cd $(BZIP2BUILD); \
		emmake make CC=emcc CFLAGS="-Wall -Winline -O2 -fomit-frame-pointer -D_FILE_OFFSET_BITS=64" AR=emar RANLIB=emranlib libbz2.a; \
	)


$(BUILD)/Makefile: $(BUILD)/.patched $(ZLIBBUILD)/.patched $(SQLITEBUILD)/libsqlite3.la $(BZIP2BUILD)/libbz2.a
	cp config.site $(BUILD)/
	( \
		cd $(BUILD); \
		CONFIG_SITE=./config.site READELF=true LD_RUN_PATH="$(SQLITEBUILD):$(BZIP2BUILD)" emconfigure \
		  ./configure \
			  CPPFLAGS="-I$(SQLITEBUILD) -I$(BZIP2BUILD)" \
			  LDFLAGS="-L$(SQLITEBUILD) -L$(BZIP2BUILD)" \
			  --without-pymalloc \
			  --disable-shared \
			  --disable-ipv6 \
			  --without-gcc \
			  --host=asmjs-unknown-emscripten \
			  --build=$(shell $(BUILD)/config.guess) \
			  --prefix=$(INSTALL) ; \
	)


$(BUILD)/$(LIB): $(BUILD)/Makefile $(HOSTPYTHON) $(HOSTPGEN) Setup.local
	cp Setup.local $(BUILD)/Modules/
	cat pyconfig.undefs.h >> $(BUILD)/pyconfig.h
	( \
		cp build/$(PYVERSION)/host/lib/python$(PYMINOR)/`$(HOSTPYTHON) -c "import sysconfig; print(sysconfig._get_sysconfigdata_name())"`.py build/$(PYVERSION)/Python-$(PYVERSION)/Lib/_sysconfigdata__emscripten_.py; \
		cd $(BUILD); \
		emmake make HOSTPYTHON=$(HOSTPYTHON) HOSTPGEN=$(HOSTPGEN) CROSS_COMPILE=yes $(LIB) \
	)
	sed -i -e 's/\-undefined dynamic_lookup//' build/$(PYVERSION)/Python-$(PYVERSION)/Lib/_sysconfigdata__emscripten_.py
	touch $(BUILD)/$(LIB)
