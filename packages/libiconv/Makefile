PYODIDE_ROOT=$(abspath ../..)
include ../../Makefile.envs

LIBICONVVERSION=1.16

ROOT=$(abspath .)

SRC=$(ROOT)/libiconv-$(LIBICONVVERSION)
TARBALL=$(ROOT)/downloads/libiconv-$(LIBICONVVERSION).tar.gz
URL=https://ftp.gnu.org/pub/gnu/libiconv/libiconv-$(LIBICONVVERSION).tar.gz


all: $(SRC)/libiconv.a


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
$(SRC)/libiconv.a: $(SRC)/Makefile
	( \
		cd $(SRC) ; \
		emconfigure ./configure \
			--disable-dependency-tracking \
			--disable-shared ; \
		emmake make -j $${PYODIDE_JOBS:-3} ; \
	)
