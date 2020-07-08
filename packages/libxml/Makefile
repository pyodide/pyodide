PYODIDE_ROOT=$(abspath ../..)
include ../../Makefile.envs

LIBXMLVERSION=2.9.10

ROOT=$(abspath .)

SRC=$(ROOT)/libxml2-$(LIBXMLVERSION)
TARBALL=$(ROOT)/downloads/libxml-$(LIBXMLVERSION).tgz
URL=ftp://xmlsoft.org/libxml2/libxml2-$(LIBXMLVERSION).tar.gz
LIBICONV_DIR=$(ROOT)/../libiconv/libiconv-1.16/lib/.libs
LIBZ_DIR=$(ROOT)/../zlib/zlib-1.2.11


all: $(SRC)/.libs/libxml2.a


clean:
	-rm -fr downloads
	-rm -fr $(SRC)


$(TARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(URL)
	sha256sum --quiet --check checksums || (rm $@; false)


$(SRC)/Makefile: $(TARBALL)
	tar -C . -xf $(TARBALL)
	touch $(SRC)/Makefile

# Configure as https://github.com/lxml/lxml/blob/lxml-4.4/buildlibxml.py
$(SRC)/.libs/libxml2.a: $(SRC)/Makefile
	( \
		cd $(SRC) ; \
		emconfigure ./configure \
			--disable-dependency-tracking \
			--disable-shared \
			--without-python \
			--with-iconv=$(LIBICONV_DIR) \
			--with-zlib=$(LIBZ_DIR) ; \
		emmake make -j $${PYODIDE_JOBS:-3} ; \
	)
