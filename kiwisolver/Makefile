PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

KIWIVERSION=1.0.1
NPYVERSION=1.14.1

ROOT=$(abspath .)

HOSTROOT=$(ROOT)/host
HOSTDIR=$(HOSTROOT)/kiwisolver-$(KIWIVERSION)
HOSTBUILD=$(HOSTDIR)/build
HOSTSRC=$(HOSTDIR)/src

BUILD=$(ROOT)/build

TARBALL=$(ROOT)/downloads/kiwisolver-$(KIWIVERSION).tar.gz
URL=https://files.pythonhosted.org/packages/31/60/494fcce70d60a598c32ee00e71542e52e27c978e5f8219fae0d4ac6e2864/kiwisolver-1.0.1.tar.gz

CC=emcc
CXX=em++
AR=emar
CFLAGS=-Wsign-compare -DNDEBUG -g -fwrapv -O3 -Wall -Wstrict-prototypes -fPIC -I$(HOSTSRC) -I../numpy/host/numpy-$(NPYVERSION)/build/src.$(PLATFORMSLUG)/numpy/core/include/numpy -I$(PYTHONINCLUDE) -I$(HOSTDIR) -Wno-unused-function


OBJECTS= \
	$(BUILD)/kiwisolver.so


all:
	make $(ROOT)/.patched
	make $(OBJECTS)


clean:
	rm -fr $(HOSTROOT)
	rm -fr $(BUILD)


$(TARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(URL)
	md5sum --quiet --check checksums || (rm $@; false)


$(HOSTDIR)/setup.py: $(TARBALL)
	[ -d $(HOSTROOT) ] || mkdir $(HOSTROOT)
	tar -xf $(TARBALL) -C $(HOSTROOT)
	touch $(HOSTDIR)/setup.py


$(BUILD)/kiwisolver.so: \
		$(HOSTDIR)/py/kiwisolver.bc \
		$(HOSTDIR)/py/constraint.bc \
		$(HOSTDIR)/py/expression.bc \
		$(HOSTDIR)/py/solver.bc \
		$(HOSTDIR)/py/strength.bc \
		$(HOSTDIR)/py/term.bc \
		$(HOSTDIR)/py/variable.bc \
		| .patched
	[ -d $(ROOT)/build ] || mkdir $(ROOT)/build
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@
	rm $@.wasm.pre


$(ROOT)/.patched: $(HOSTDIR)/setup.py
	cat patches/*.patch | (cd $(HOSTDIR) ; patch -p1)
	touch $@


%.bc: %.c
	$(CC) $(CFLAGS) -c $< -o $@


%.bc: %.cpp
	$(CXX) $(CFLAGS) -c $< -o $@
