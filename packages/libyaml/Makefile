PYODIDE_ROOT=$(abspath ../..)
include ../../Makefile.envs

LIBYAMLVERSION=0.2.1

ROOT=$(abspath .)

SRC=$(ROOT)/libyaml-$(LIBYAMLVERSION)
BUILDDIR=$(ROOT)/build
TARBALL=$(ROOT)/downloads/$(LIBYAMLVERSION).zip
URL=https://github.com/yaml/libyaml/archive/$(LIBYAMLVERSION).zip


all: $(BUILDDIR)/libyaml.a



$(TARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(URL)
	unzip $(TARBALL)
	

$(BUILDDIR)/libyaml.a: $(TARBALL)
	( \
		cd $(SRC) ; \
		mkdir -p $(BUILDDIR); \
		cd $(BUILDDIR); \
		emcmake cmake -DCMAKE_INSTALL_PREFIX=$(BUILDDIR) $(SRC); \
		emmake make install -j 20; \
		ln $(BUILDDIR)/lib/libyaml_static.a $(BUILDDIR)/lib/libyaml.a; \
		ln $(BUILDDIR)/libyaml_static.a $@; \
	)

clean:
	-rm -fr downloads installs build build.log
	-rm -fr $(SRC)

