PYODIDE_ROOT=$(abspath ../..)
include ../../Makefile.envs

LIBXSLTVERSION=1.1.33

ROOT=$(abspath .)

SRC=$(ROOT)/libxslt-$(LIBXSLTVERSION)
TARBALL=$(ROOT)/downloads/libxslt-$(LIBXSLTVERSION).tgz
URL=ftp://xmlsoft.org/libxml2/libxslt-$(LIBXSLTVERSION).tar.gz


all: $(SRC)/libxslt/.libs/libxslt.a


clean:
	-rm -fr downloads
	-rm -fr $(SRC)


$(TARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(URL)
	sha256sum --quiet --check checksums || (rm $@; false)


# Configure as https://github.com/lxml/lxml/blob/lxml-4.4/buildlibxml.py
$(SRC)/Makefile: $(TARBALL)
	tar -C . -xf $(TARBALL)
	touch $(SRC)/Makefile
	( \
		cd $(SRC) ; \
		emconfigure ./configure \
			--disable-dependency-tracking \
			--disable-shared \
			--without-python \
			--with-libxml-src=${PYODIDE_ROOT}/packages/libxml/libxml2-2.9.10 \
			--without-crypto ; \
	)


$(SRC)/libxslt/.libs/libxslt.a: $(SRC)/Makefile
	( \
		cd $(SRC) ; \
		emmake make -j $${PYODIDE_JOBS:-3} ; \
	)
