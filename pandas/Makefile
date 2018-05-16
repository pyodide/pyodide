PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

PDVERSION=0.22.0
NPYVERSION=1.14.1

ROOT=$(abspath .)

HOSTROOT=$(ROOT)/host
HOSTDIR=$(HOSTROOT)/pandas-$(PDVERSION)
HOSTBUILD=$(HOSTDIR)/build

BUILD=$(ROOT)/build/pandas

TARBALL=$(ROOT)/downloads/pandas-$(PDVERSION).tar.gz
URL=https://pypi.python.org/packages/08/01/803834bc8a4e708aedebb133095a88a4dad9f45bbaf5ad777d2bea543c7e/pandas-0.22.0.tar.gz

CC=emcc
CXX=em++
AR=emar
CFLAGS=-Wsign-compare -DNDEBUG -g -fwrapv -O3 -Wall -Wstrict-prototypes -fPIC -I$(HOSTDIR)/pandas/_libs/src/klib -I$(HOSTDIR)/pandas/_libs/src -I../numpy/host/numpy-$(NPYVERSION)/numpy/core/include -I../numpy/config -I../numpy/host/numpy-$(NPYVERSION)/build/src.$(PLATFORMSLUG)/numpy/core/include/numpy -I$(PYTHONINCLUDE) -I$(HOSTDIR)/pandas/_libs/src/ujson/lib -I$(HOSTDIR)/pandas/_libs/src/datetime -Wno-unused-function

OBJECTS = \
	$(BUILD)/_libs/algos.so \
	$(BUILD)/_libs/groupby.so \
	$(BUILD)/_libs/hashtable.so \
	$(BUILD)/_libs/index.so \
	$(BUILD)/_libs/interval.so \
	$(BUILD)/_libs/join.so \
	$(BUILD)/_libs/reshape.so \
	$(BUILD)/_libs/json.so \
	$(BUILD)/_libs/lib.so \
	$(BUILD)/_libs/parsers.so \
	$(BUILD)/_libs/period.so \
	$(BUILD)/_libs/tslibs/parsing.so \
	$(BUILD)/_libs/properties.so \
	$(BUILD)/_libs/sparse.so \
	$(BUILD)/_libs/hashing.so \
	$(BUILD)/_libs/tslib.so \
	$(BUILD)/_libs/tslibs/fields.so \
	$(BUILD)/_libs/tslibs/frequencies.so \
	$(BUILD)/_libs/tslibs/strptime.so \
	$(BUILD)/_libs/tslibs/timedeltas.so \
	$(BUILD)/_libs/tslibs/timezones.so \
	$(BUILD)/_libs/window.so \
	$(BUILD)/io/msgpack/_packer.so \
	$(BUILD)/io/msgpack/_unpacker.so \
	$(BUILD)/_libs/testing.so \
	$(BUILD)/io/sas/_sas.so \
	$(BUILD)/util/_move.so \


all:
	make $(BUILD)/__init__.py
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


$(HOSTBUILD)/lib.$(PLATFORMSLUG)/pandas/__init__.py: $(ROOT)/.patched
	( \
	  cd $(HOSTDIR); \
    $(HOSTPYTHON) setup.py build \
	)


$(BUILD)/__init__.py: $(HOSTBUILD)/lib.$(PLATFORMSLUG)/pandas/__init__.py
	[ -d $(ROOT)/build ] || mkdir $(ROOT)/build
	cp -r $(HOSTBUILD)/lib.$(PLATFORMSLUG)/pandas $(ROOT)/build && \
	cd $(BUILD); find . -name "*.so" -type f -delete


$(ROOT)/.patched: $(HOSTDIR)/setup.py
	cat patches/*.patch | (cd $(HOSTDIR) ; patch -p1)
	touch $@


$(BUILD)/_libs/lib.so: $(HOSTDIR)/pandas/_libs/lib.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/properties.so: $(HOSTDIR)/pandas/_libs/properties.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/hashtable.so: $(HOSTDIR)/pandas/_libs/hashtable.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/tslibs/strptime.so: \
		$(HOSTDIR)/pandas/_libs/tslibs/strptime.bc \
		$(HOSTDIR)/pandas/_libs/src/datetime/np_datetime.bc \
		$(HOSTDIR)/pandas/_libs/src/datetime/np_datetime_strings.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/tslib.so: \
		$(HOSTDIR)/pandas/_libs/tslib.bc \
		$(HOSTDIR)/pandas/_libs/src/datetime/np_datetime.bc \
		$(HOSTDIR)/pandas/_libs/src/datetime/np_datetime_strings.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/tslibs/timedeltas.so: \
		$(HOSTDIR)/pandas/_libs/tslibs/timedeltas.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/tslibs/timezones.so: \
		$(HOSTDIR)/pandas/_libs/tslibs/timezones.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/tslibs/fields.so: \
		$(HOSTDIR)/pandas/_libs/tslibs/fields.bc \
		$(HOSTDIR)/pandas/_libs/src/datetime/np_datetime.bc \
		$(HOSTDIR)/pandas/_libs/src/datetime/np_datetime_strings.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/period.so: \
		$(HOSTDIR)/pandas/_libs/period.bc \
		$(HOSTDIR)/pandas/_libs/src/datetime/np_datetime.bc \
		$(HOSTDIR)/pandas/_libs/src/datetime/np_datetime_strings.bc \
		$(HOSTDIR)/pandas/_libs/src/period_helper.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/tslibs/parsing.so: \
		$(HOSTDIR)/pandas/_libs/tslibs/parsing.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/tslibs/frequencies.so: \
		$(HOSTDIR)/pandas/_libs/tslibs/frequencies.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/index.so: \
		$(HOSTDIR)/pandas/_libs/index.bc \
		$(HOSTDIR)/pandas/_libs/src/datetime/np_datetime.bc \
		$(HOSTDIR)/pandas/_libs/src/datetime/np_datetime_strings.bc \
		$(HOSTDIR)/pandas/_libs/src/period_helper.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/algos.so: \
		$(HOSTDIR)/pandas/_libs/algos.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/groupby.so: \
		$(HOSTDIR)/pandas/_libs/groupby.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/join.so: \
		$(HOSTDIR)/pandas/_libs/join.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/reshape.so: \
		$(HOSTDIR)/pandas/_libs/reshape.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/interval.so: \
		$(HOSTDIR)/pandas/_libs/interval.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/window.so: \
		$(HOSTDIR)/pandas/_libs/window.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/parsers.so: \
		$(HOSTDIR)/pandas/_libs/parsers.bc \
		$(HOSTDIR)/pandas/_libs/src/parser/tokenizer.bc \
		$(HOSTDIR)/pandas/_libs/src/parser/io.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/sparse.so: \
		$(HOSTDIR)/pandas/_libs/sparse.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/hashing.so: \
		$(HOSTDIR)/pandas/_libs/hashing.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/io/sas/_sas.so: \
		$(HOSTDIR)/pandas/io/sas/sas.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/testing.so: \
		$(HOSTDIR)/pandas/_libs/testing.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/io/msgpack/_packer.so: \
		$(HOSTDIR)/pandas/io/msgpack/_packer.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/io/msgpack/_unpacker.so: \
		$(HOSTDIR)/pandas/io/msgpack/_unpacker.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_libs/json.so: \
		$(HOSTDIR)/pandas/_libs/src/ujson/python/ujson.bc \
		$(HOSTDIR)/pandas/_libs/src/ujson/python/objToJSON.bc \
		$(HOSTDIR)/pandas/_libs/src/ujson/python/JSONtoObj.bc \
		$(HOSTDIR)/pandas/_libs/src/ujson/lib/ultrajsonenc.bc \
		$(HOSTDIR)/pandas/_libs/src/ujson/lib/ultrajsondec.bc \
		$(HOSTDIR)/pandas/_libs/src/datetime/np_datetime.bc \
		$(HOSTDIR)/pandas/_libs/src/datetime/np_datetime_strings.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/util/_move.so: \
		$(HOSTDIR)/pandas/util/move.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


%.bc: %.c
	$(CC) $(CFLAGS) -include src/state.h -c $< -o $@


%.bc: %.cpp
	$(CXX) $(CFLAGS) -include src/state.h -c $< -o $@
