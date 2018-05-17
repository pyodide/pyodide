PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

PYPARSINGVERSION=2.2.0

ROOT=$(abspath .)

SRC=$(ROOT)/pyparsing-$(PYPARSINGVERSION)
BUILD=$(SRC)/build/lib/dateutil
TARBALL=$(ROOT)/downloads/pyparsing-$(PYPARSINGVERSION).tgz
URL=https://files.pythonhosted.org/packages/3c/ec/a94f8cf7274ea60b5413df054f82a8980523efd712ec55a59e7c3357cf7c/pyparsing-2.2.0.tar.gz


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
		touch build/lib/pyparsing.py \
	)


$(ROOT)/.patched: $(SRC)/setup.py
	cat patches/*.patch | (cd $(SRC) ; patch --binary -p1)
	touch $@
