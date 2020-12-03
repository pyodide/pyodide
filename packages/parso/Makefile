PYODIDE_ROOT=$(abspath ../..)
include ../../Makefile.envs

PARSOVERSION=0.8.0

ROOT=$(abspath .)

SRC=$(ROOT)/parso-$(PARSOVERSION)
BUILD=$(SRC)/build/lib/parso
TARBALL=$(ROOT)/downloads/parso-$(PARSOVERSION).tar.gz
URL=https://files.pythonhosted.org/packages/cb/1b/1d846fff1f5b10907fbfece4901410823ec529f9ee9193451278451fcb6e/parso-$(PARSOVERSION).tar.gz


all: $(SRC)/setup.py


clean:
	-rm -fr downloads
	-rm -fr $(SRC)


$(TARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(URL)
	sha256sum --quiet --check checksums || (rm $@; false)


$(SRC)/setup.py: $(TARBALL)
	tar -C . -xf $(TARBALL)
	touch $(SRC)/setup.py
