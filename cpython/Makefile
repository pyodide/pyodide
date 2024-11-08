PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

ROOT=$(abspath .)

PYTHON_CFLAGS=$(CFLAGS_BASE) -DPY_CALL_TRAMPOLINE

PYBUILD=$(CPYTHONROOT)/build/Python-$(PYVERSION)
PYINSTALL=$(CPYTHONINSTALL)
PYTARBALL=$(ROOT)/downloads/Python-$(PYVERSION).tgz
PYLIB=libpython$(PYMAJOR).$(PYMINOR)$(CPYTHON_ABI_FLAGS).a

FFIBUILD=$(ROOT)/build/libffi
LIBFFIREPO=https://github.com/libffi/libffi
LIBFFI_COMMIT=f08493d249d2067c8b3207ba46693dd858f95db3

HIWIREBUILD=$(ROOT)/build/hiwire
HIWIREREPO=https://github.com/hoodmane/hiwire
HIWIRE_COMMIT=49f3450e34f3f50d4b8296e782dc321bb2e3264e

ifdef CPYTHON_DEBUG
	MAYBE_WITH_PYDEBUG=--with-pydebug
endif

all: $(PYINSTALL)/lib/$(PYLIB) $(PYINSTALL)/lib/libffi.a $(PYINSTALL)/lib/libhiwire.a

.PHONY=sysconfigdata
sysconfigdata:
	# Generate sysconfigdata. It outputs into a subfolder of build/, and
	# the subfolder is written to pybuilddir.txt.
	cd $(PYBUILD) && _PYTHON_SYSCONFIGDATA_NAME=$(SYSCONFIG_NAME) _PYTHON_PROJECT_BASE=$(PYBUILD) $(HOSTPYTHON) -m sysconfig --generate-posix-vars
	$(eval PYBUILDDIR=$(PYBUILD)/`cat $(PYBUILD)/pybuilddir.txt`)
	PYODIDE_ROOT=$(PYODIDE_ROOT) PYTHONPATH=$(PYBUILDDIR) python$(PYMAJOR).$(PYMINOR) adjust_sysconfig.py
	mkdir -p $(PYINSTALL)/lib/python$(PYMAJOR).$(PYMINOR)/
	mkdir -p $(SYSCONFIGDATA_DIR)
	cp $(PYBUILDDIR)/$(SYSCONFIG_NAME).py $(PYINSTALL)/lib/python$(PYMAJOR).$(PYMINOR)/
	cp $(PYBUILDDIR)/$(SYSCONFIG_NAME).py $(SYSCONFIGDATA_DIR)

LIBPYTHON_EXTRA_OBJECTS=$$(LIBMPDEC_OBJS) $$(LIBEXPAT_OBJS) $$(LIBHACL_SHA2_OBJS)

$(PYBUILD)/.patched_makefile:
	# Clear out libinstall deps (we build what we want explicitly first)
	cd $(PYBUILD) && sed -i -e 's/libinstall:.*/libinstall:/' Makefile;
	# Inject extra objects into libpython3.12.a so we don't have to link them
	# separately
	cd $(PYBUILD) && sed -i '/MODOBJS=/s/$$/ $(LIBPYTHON_EXTRA_OBJECTS)/' Makefile
	touch $(PYBUILD)/.patched_makefile

$(PYINSTALL)/lib/$(PYLIB): $(PYBUILD)/$(PYLIB) sysconfigdata $(PYBUILD)/.patched_makefile
	# touch libpython3.12.a so we don't remake it due to modified Makefile(??)
	touch $(PYBUILD)/$(PYLIB)
	CFLAGS="$(CFLAGS_BASE)" emmake make -C $(PYBUILD) PYTHON_FOR_BUILD=$(HOSTPYTHON) CROSS_COMPILE=yes inclinstall libinstall $(PYLIB) -j $${PYODIDE_JOBS:-3}
	cp $(PYBUILD)/$(PYLIB) $(PYINSTALL)/lib/


.PHONY=rebuild
rebuild: sysconfigdata
	CFLAGS="$(CFLAGS_BASE)" emmake make -C $(PYBUILD) PYTHON_FOR_BUILD=$(HOSTPYTHON) CROSS_COMPILE=yes inclinstall libinstall $(PYLIB) -j $${PYODIDE_JOBS:-3}
	cp $(PYBUILD)/$(PYLIB) $(PYINSTALL)/lib/


.PHONY=rebuild-all
rebuild-all:
# touching abstract.h is enough to force most stuff to be rebuilt...
	touch $(PYBUILD)/Include/abstract.h
	make rebuild


clean:
	-rm -fr $(ROOT)/build
	-rm -fr $(ROOT)/installs

clean-all: clean
	-rm -fr $(ROOT)/downloads


$(PYTARBALL):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(PYTHON_ARCHIVE_URL)
	@GOT_SHASUM=`shasum --algorithm 256 $(PYTARBALL) | cut -f1 -d' '` \
		&& (echo $$GOT_SHASUM | grep -q $(PYTHON_ARCHIVE_SHA256)) \
		|| (\
			   rm $@ \
			&& echo "Got unexpected shasum $$GOT_SHASUM" \
			&& echo "If you are updating the Python version, set PYTHON_ARCHIVE_SHA256 in Makefile.envs to this." \
			&& exit 1 \
		)


prepare-source: $(PYBUILD)/.patched

$(PYBUILD)/.patched: $(PYTARBALL)
	[ -d $(PYBUILD) ] || (mkdir -p $(dir $(PYBUILD)); tar -C $(dir $(PYBUILD)) -xf $(PYTARBALL))
	cat patches/*.patch | (cd $(PYBUILD) ; patch -p1)
	touch $@

$(PYINSTALL)/lib/libffi.a :
	rm -rf $(FFIBUILD)
	mkdir $(FFIBUILD)
	(\
		cd $(FFIBUILD) \
		&& git init \
		&& git fetch --depth 1 $(LIBFFIREPO) $(LIBFFI_COMMIT) \
		&& git checkout FETCH_HEAD \
		&& . $(PYODIDE_ROOT)/emsdk/emsdk/emsdk_env.sh \
		&& ./testsuite/emscripten/build.sh --wasm-bigint \
		&& make install \
	)
	cp $(FFIBUILD)/target/include/*.h $(PYBUILD)/Include/
	mkdir -p $(PYINSTALL)/lib
	cp $(FFIBUILD)/target/lib/libffi.a $(PYINSTALL)/lib/

$(PYINSTALL)/lib/libhiwire.a :
	rm -rf $(HIWIREBUILD)
	mkdir $(HIWIREBUILD)
	(\
		cd $(HIWIREBUILD) \
		&& git init \
		&& git fetch --depth 1 $(HIWIREREPO) $(HIWIRE_COMMIT) \
		&& git checkout FETCH_HEAD \
		&& . $(PYODIDE_ROOT)/emsdk/emsdk/emsdk_env.sh \
		&& CC=emcc EMSCRIPTEN_DEDUPLICATE=1 EXTERN_FAIL=1 make \
	)
	cp -r $(HIWIREBUILD)/dist/lib $(PYINSTALL)/
	cp -r $(HIWIREBUILD)/dist/include $(PYINSTALL)/include/hiwire

python-makefile: $(PYBUILD)/Makefile

$(PYBUILD)/Makefile: $(PYBUILD)/.patched
	# --enable-big-digits=30 :
	#   Python integers have "digits" of size 15 by default on systems with 32
	#   bit pointers and size 30 on systems with 16 bit pointers. Python uses
	#   "digits" of size 15 by default on systems with 32 bit pointers and size
	#   30 on systems with 16 bit pointers. WASM has 32 bit pointers so Python
	#   will default to the size 15 digits but WASM has native 64 bit arithmetic
	#   so it is more efficient to use 30 bit digits.
	( \
		cd $(PYBUILD); \
		CONFIG_SITE=./Tools/wasm/config.site-wasm32-emscripten READELF=true emconfigure \
		  ./configure \
			  CFLAGS="${PYTHON_CFLAGS}" \
			  CPPFLAGS="-sUSE_BZIP2=1 -sUSE_ZLIB=1" \
			  PLATFORM_TRIPLET="$(PLATFORM_TRIPLET)" \
			  ac_cv_lib_sqlite3_sqlite3_load_extension=yes \
			  --without-pymalloc \
			  --disable-shared \
			  --disable-ipv6 \
			  --enable-big-digits=30 \
			  --enable-optimizations \
			  --enable-loadable-sqlite-extensions \
			  --host=wasm32-unknown-emscripten\
			  --build=$(shell $(PYBUILD)/config.guess) \
			  --prefix=$(PYINSTALL)  \
			  --with-build-python=$$(which python$(PYMAJOR).$(PYMINOR)) \
			  $(MAYBE_WITH_PYDEBUG) \
	)


$(PYBUILD)/Modules/Setup.local: Setup.local
	cp Setup.local $(PYBUILD)/Modules/

$(PYBUILD)/$(PYLIB): $(PYBUILD)/Makefile $(PYBUILD)/pyconfig.h $(PYBUILD)/Modules/Setup.local $(PYINSTALL)/lib/libffi.a
	cp Setup.local $(PYBUILD)/Modules/
	( \
		cd $(PYBUILD); \
		make regen-frozen; \
		emmake make CROSS_COMPILE=yes $(PYLIB) -j $${PYODIDE_JOBS:-3} \
	)
	touch $(PYBUILD)/$(PYLIB)
