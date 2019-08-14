PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

PARSOVERSION=0.5.1

ROOT=$(abspath .)

SRC=$(ROOT)/parso-$(PARSOVERSION)
BUILD=$(SRC)/build/lib/parso
TARBALL=$(ROOT)/downloads/parso-$(PARSOVERSION).tar.gz
URL=https://files.pythonhosted.org/packages/21/40/615957db4d178b7504c87b1a5b85fa5945b0b4fa5f5a845e31fc7aad6018/parso-$(PARSOVERSION).tar.gz


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
