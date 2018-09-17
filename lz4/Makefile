PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

LZ4VERSION=1.8.3

ROOT=$(abspath .)

SRC=$(ROOT)/lz4-$(LZ4VERSION)
TARBALL=$(ROOT)/downloads/lz4-$(LZ4VERSION).tgz
URL=https://github.com/lz4/lz4/archive/v$(LZ4VERSION).tar.gz


all: $(SRC)/lib/liblz4.a


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


$(SRC)/lib/liblz4.a: $(SRC)/Makefile
	( \
		cd $(SRC) ; \
		emmake make ; \
	)
