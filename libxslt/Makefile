PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

LIBXSLTVERSION=1.1.33

ROOT=$(abspath .)

SRC=$(ROOT)/libxslt-$(LIBXSLTVERSION)
TARBALL=$(ROOT)/downloads/libxslt-$(LIBXSLTVERSION).tgz
URL=ftp://xmlsoft.org/libxml2/libxslt-$(LIBXSLTVERSION).tar.gz


all: $(SRC)/.libs/libxslt.a


clean:
	-rm -fr downloads
	-rm -fr $(SRC)


$(TARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(URL)
#	md5sum --quiet --check checksums || (rm $@; false)


$(SRC)/Makefile: $(TARBALL)
	tar -C . -xf $(TARBALL)
	touch $(SRC)/Makefile
	( \
		cd $(SRC) ; \
		emconfigure ./configure --with-python=/src/cpython/build/3.7.0/host/include/python3.7m/ ; \
	)


$(SRC)/.libs/libxslt.a: $(SRC)/Makefile
	( \
		cd $(SRC) ; \
		emmake make ; \
	)
