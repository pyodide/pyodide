PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

PYTZVERSION=2018.4

ROOT=$(abspath .)

SRC=$(ROOT)/pytz-$(PYTZVERSION)
BUILD=$(SRC)/build/lib/pytz
TARBALL=$(ROOT)/downloads/pytz-$(PYTZVERSION).tgz
URL=https://files.pythonhosted.org/packages/10/76/52efda4ef98e7544321fd8d5d512e11739c1df18b0649551aeccfb1c8376/pytz-$(PYTZVERSION).tar.gz


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
		touch build/lib/pytz/__init__.py \
	)


$(ROOT)/.patched: $(SRC)/setup.py
	cat patches/*.patch | (cd $(SRC) ; patch -p1)
	touch $@
