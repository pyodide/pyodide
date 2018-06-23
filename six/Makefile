PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

SIXVERSION=1.11.0

ROOT=$(abspath .)

SRC=$(ROOT)/six-$(SIXVERSION)
BUILD=$(SRC)/build/lib/six
TARBALL=$(ROOT)/downloads/six-$(SIXVERSION).tgz
URL=https://files.pythonhosted.org/packages/16/d8/bc6316cf98419719bd59c91742194c111b6f2e85abac88e496adefaf7afe/six-1.11.0.tar.gz


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


$(BUILD)/__init__.py: $(SRC)/setup.py
	( \
		cd $(SRC) ; \
		$(HOSTPYTHON) setup.py build ; \
		touch build/lib/six.py \
	)
