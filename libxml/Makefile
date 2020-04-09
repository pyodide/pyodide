PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

LIBXMLVERSION=2.9.9

ROOT=$(abspath .)

SRC=$(ROOT)/libxml2-$(LIBXMLVERSION)
TARBALL=$(ROOT)/downloads/libxml-$(LIBXMLVERSION).tgz
URL=ftp://xmlsoft.org/libxml2/libxml2-$(LIBXMLVERSION).tar.gz


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


$(SRC)/.libs/libxml2.a: $(SRC)/Makefile
	( \
		cd $(SRC) ; \
		emconfigure ./configure --with-python=${PYODIDE_ROOT}/cpython/build/${PYVERSION}/host/include/python3.7m/ ; \
		emmake make ; \
	)
