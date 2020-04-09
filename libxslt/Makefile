PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

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


$(SRC)/Makefile: $(TARBALL)
	tar -C . -xf $(TARBALL)
	touch $(SRC)/Makefile
	( \
		cd $(SRC) ; \
		emconfigure ./configure	\
			--with-python=${PYODIDE_ROOT}/cpython/build/${PYVERSION}/host/include/python3.7m/ \
			--with-libxml-include-prefix=${PYODIDE_ROOT}/libxml/libxml2-2.9.9/include/ \
			--with-libxml-libs-prefix=${PYODIDE_ROOT}/libxml/libxml2-2.9.9/.libs/ ; \
	)


$(SRC)/libxslt/.libs/libxslt.a: $(SRC)/Makefile
	( \
		cd $(SRC) ; \
		emmake make ; \
	)
