PYODIDE_ROOT=$(abspath ../..)
include ../../Makefile.envs

PARSOVERSION=0.7.1

ROOT=$(abspath .)

SRC=$(ROOT)/parso-$(PARSOVERSION)
BUILD=$(SRC)/build/lib/parso
TARBALL=$(ROOT)/downloads/parso-$(PARSOVERSION).tar.gz
URL=https://files.pythonhosted.org/packages/40/01/e0b8d2168fb299af90a78a5919257f821e5c21399bf0906c14c9e573db3f/parso-$(PARSOVERSION).tar.gz


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
