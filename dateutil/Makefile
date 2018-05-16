PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

DATEUTILVERSION=2.7.2

ROOT=$(abspath .)

SRC=$(ROOT)/python-dateutil-$(DATEUTILVERSION)
BUILD=$(SRC)/build/lib/dateutil
TARBALL=$(ROOT)/downloads/python-dateutil-$(DATEUTILVERSION).tgz
URL=https://files.pythonhosted.org/packages/c5/39/4da7c2dbc4f023fba5fb2325febcadf0d0ce0efdc8bd12083a0f65d20653/python-dateutil-2.7.2.tar.gz


all: $(BUILD)/__init__.py


clean:
	-rm -fr downloads
	-rm -fr $(SRC)


$(TARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(URL)
	md5sum --quiet --check checksums || (rm $@; false)


$(SRC)/setup.py: $(TARBALL)
	tar -C . -xf $(TARBALL)
	touch $(SRC)/setup.py


$(BUILD)/__init__.py: $(ROOT)/.patched
	( \
		cd $(SRC) ; \
		$(HOSTPYTHON) setup.py build ; \
		touch build/lib/dateutil/__init__.py \
	)


$(ROOT)/.patched: $(SRC)/setup.py
	cat patches/*.patch | (cd $(SRC) ; patch -p1)
	touch $@
