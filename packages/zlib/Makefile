PYODIDE_ROOT=$(abspath ../..)
include ../../Makefile.envs

ZLIBVERSION=1.2.11

ROOT=$(abspath .)

SRC=$(ROOT)/zlib-$(ZLIBVERSION)
TARBALL=$(ROOT)/downloads/zlib-$(ZLIBVERSION).tar.gz
URL=https://zlib.net/zlib-$(ZLIBVERSION).tar.gz


all: $(SRC)/zlib.a


clean:
	-rm -fr downloads
	-rm -fr $(SRC)


$(TARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -O $@ $(URL)
	sha256sum --quiet --check checksums || (rm $@; false)


$(SRC)/Makefile: $(TARBALL)
	tar -C . -xf $(TARBALL)
	touch $(SRC)/Makefile


$(SRC)/zlib.a: $(SRC)/Makefile
	( \
		cd $(SRC) ; \
		emconfigure ./configure  --prefix=$(SRC) ; \
		emmake make install -j $${PYODIDE_JOBS:-3} ; \
	)
