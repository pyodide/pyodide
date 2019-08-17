PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

JEDIVERSION=0.15.1

ROOT=$(abspath .)

SRC=$(ROOT)/jedi-$(JEDIVERSION)
BUILD=$(SRC)/build/lib/jedi
TARBALL=$(ROOT)/downloads/jedi-$(JEDIVERSION).tar.gz
URL=https://files.pythonhosted.org/packages/85/03/cd5a6e44a5753b4d539288d9d1f9645caac889c17dd2950292a8818f86b2/jedi-$(JEDIVERSION).tar.gz


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
