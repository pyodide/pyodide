PYODIDE_ROOT=$(abspath ../..)
include ../../Makefile.envs

JEDIVERSION=0.17.2

ROOT=$(abspath .)

SRC=$(ROOT)/jedi-$(JEDIVERSION)
BUILD=$(SRC)/build/lib/jedi
TARBALL=$(ROOT)/downloads/jedi-$(JEDIVERSION).tar.gz
URL=https://files.pythonhosted.org/packages/39/67/50d1653038dafe06ca2cc55c4598c5f8318d519c12a7a288d7826280ee22/jedi-$(JEDIVERSION).tar.gz


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
