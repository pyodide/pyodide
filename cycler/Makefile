PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

CYCLERVERSION=0.10.0

ROOT=$(abspath .)

SRC=$(ROOT)/cycler-$(CYCLERVERSION)
BUILD=$(SRC)/build/lib/dateutil
TARBALL=$(ROOT)/downloads/cycler-$(CYCLERVERSION).tgz
URL=https://files.pythonhosted.org/packages/c2/4b/137dea450d6e1e3d474e1d873cd1d4f7d3beed7e0dc973b06e8e10d32488/cycler-0.10.0.tar.gz


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
		touch build/lib/cycler.py \
	)


$(ROOT)/.patched: $(SRC)/setup.py
	cat patches/*.patch | (cd $(SRC) ; patch -p1)
	touch $@
