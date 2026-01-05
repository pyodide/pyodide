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
HIWIREREPO=https://github.com/pyodide/hiwire
HIWIRE_COMMIT=6a1e67280a15d929ebeceee54a6358c9c8d5f697

LZMABUILD=$(ROOT)/build/lzma
LZMATARBALL=https://github.com/xz-mirror/xz/releases/download/v5.2.2/xz-5.2.2.tar.gz

OPENSSLBUILD=$(ROOT)/build/openssl
OPENSSLREPO=https://github.com/openssl/openssl
OPENSSL_COMMIT=e04bd3433fd84e1861bf258ea37928d9845e6a86

# Not mandatory, but try to match the version of SQLite used in Emscripten
# https://github.com/emscripten-core/emscripten/blob/4.0.9/tools/ports/sqlite3.py
SQLITE3BUILD=$(ROOT)/build/sqlite3
SQLITE3TARBALL=https://www.sqlite.org/2022/sqlite-autoconf-3390000.tar.gz

ifdef CPYTHON_DEBUG
	MAYBE_WITH_PYDEBUG=--with-pydebug
endif

all: $(PYINSTALL)/lib/$(PYLIB) libffi libhiwire liblzma libopenssl

libffi: $(PYINSTALL)/lib/libffi.a

libhiwire: $(PYINSTALL)/lib/libhiwire.a

liblzma: $(PYINSTALL)/lib/liblzma.a

libopenssl: $(PYINSTALL)/lib/libssl.a

libsqlite3: $(PYINSTALL)/lib/libsqlite3.a

.PHONY: sysconfigdata
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
	cd $(PYBUILD) && $(SED) -i -e 's/libinstall:.*/libinstall:/' Makefile;
	# Inject extra objects into libpython3.13.a so we don't have to link them
	# separately
	cd $(PYBUILD) && $(SED) -i '/MODOBJS=/s/$$/ $(LIBPYTHON_EXTRA_OBJECTS)/' Makefile
	touch $(PYBUILD)/.patched_makefile

$(PYINSTALL)/lib/$(PYLIB): $(PYBUILD)/$(PYLIB) sysconfigdata $(PYBUILD)/.patched_makefile
	# touch libpython3.13.a so we don't remake it due to modified Makefile(??)
	touch $(PYBUILD)/$(PYLIB)
	CFLAGS="$(CFLAGS_BASE)" emmake make -C $(PYBUILD) CROSS_COMPILE=yes inclinstall libinstall $(PYLIB) -j $${PYODIDE_JOBS:-3}
	cp $(PYBUILD)/$(PYLIB) $(PYINSTALL)/lib/


.PHONY: rebuild
rebuild: sysconfigdata
	CFLAGS="$(CFLAGS_BASE)" emmake make -C $(PYBUILD) CROSS_COMPILE=yes inclinstall libinstall $(PYLIB) -j $${PYODIDE_JOBS:-3}
	cp $(PYBUILD)/$(PYLIB) $(PYINSTALL)/lib/


.PHONY: rebuild-all
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
	rm -rf $(PYINSTALL)/include/hiwire
	cp -r $(HIWIREBUILD)/dist/include/ $(PYINSTALL)/include/hiwire

$(PYINSTALL)/lib/liblzma.a :
	rm -rf $(LZMABUILD)
	mkdir $(LZMABUILD)
	(\
		cd $(LZMABUILD) \
		&& wget -q -O - $(LZMATARBALL) | tar -xz --strip-components=1 \
		&& . $(PYODIDE_ROOT)/emsdk/emsdk/emsdk_env.sh \
		&& . $(PYODIDE_ROOT)/pyodide_env.sh \
		&& emconfigure ./configure \
			CFLAGS="-fPIC -Os" \
			--disable-xz \
			--disable-xzdec \
			--disable-lzmadec \
			--disable-lzmainfo \
			--disable-lzma-links \
			--disable-scripts \
			--disable-doc \
			--enable-shared=no \
			--disable-dependency-tracking \
			--prefix=$(LZMABUILD)/dist \
		&& emmake make \
		&& emmake make install \
	)

	cp -r $(LZMABUILD)/dist/lib $(PYINSTALL)/
	rm -rf $(PYINSTALL)/include/lzma
	mkdir -p $(PYINSTALL)/include/lzma
	cp -r $(LZMABUILD)/dist/include/* $(PYINSTALL)/include/lzma

# We are disabling a lot of features to minimize the size of the resulting
# OpenSSL libraries.
# Useful link:
# - https://github.com/openssl/openssl/discussions/23542
# - https://wiki.openssl.org/index.php/Compilation_and_Installation
# - https://github.com/openwrt/openwrt/blob/master/package/libs/openssl/Makefile
# - https://stackoverflow.com/questions/23772816/when-do-i-need-zlib-in-openssl
$(PYINSTALL)/lib/libssl.a :
	rm -rf $(OPENSSLBUILD)
	mkdir -p $(OPENSSLBUILD)
	(\
		cd $(OPENSSLBUILD) \
		&& git init \
		&& git fetch --depth 1 $(OPENSSLREPO) $(OPENSSL_COMMIT) \
		&& git checkout FETCH_HEAD \
		&& . $(PYODIDE_ROOT)/emsdk/emsdk/emsdk_env.sh \
		&& . $(PYODIDE_ROOT)/pyodide_env.sh \
		&& emconfigure ./Configure \
			gcc \
			no-ui-console \
			no-tests \
			no-err \
			no-ssl2 \
			no-ssl3 \
			no-comp \
			no-hw \
			no-engine \
			no-dso \
			no-srp \
			no-psk \
			no-weak-ssl-ciphers \
			no-sse2 \
			no-threads \
			no-zlib \
			no-md2 \
			no-md4 \
			no-rc2 \
			no-rc4 \
			no-rc5 \
			no-mdc2 \
			no-whirlpool \
			no-ripemd \
			no-idea \
			no-bf \
			no-cast \
			no-seed \
			no-camellia \
			no-aria \
			no-sm2 \
			no-sm3 \
			no-sm4 \
			no-dsa \
			no-cms \
			no-ts \
			no-ct \
			no-dtls \
			no-dtls1 \
			no-dtls1-method \
			no-tls1 \
			no-tls1-method \
			no-ssl3-method \
			no-ocsp \
			no-sctp \
			no-srtp \
			no-nextprotoneg \
			no-gost \
			no-heartbeats \
			no-fuzz-afl \
			no-fuzz-libfuzzer \
			no-unit-test \
			no-crypto-mdebug \
			no-crypto-mdebug-backtrace \
			no-dynamic-engine \
			no-autoerrinit \
			-DHAVE_FORK=0 \
			-DOPENSSL_NO_SECURE_MEMORY \
			-fPIC \
			-DNO_SYSLOG \
			-Os \
		&& sed -i 's!^CROSS_COMPILE=.*!!g' Makefile \
		&& make build_generated \
		&& make libcrypto.a \
		&& make libssl.a \
		&& emar -d libcrypto.a liblegacy-lib-bn_asm.o liblegacy-lib-des_enc.o liblegacy-lib-fcrypt_b.o \
	)

	rm -rf $(PYINSTALL)/include/openssl
	mkdir -p $(PYINSTALL)/include/openssl
	mkdir -p $(PYINSTALL)/lib
	cp -r $(OPENSSLBUILD)/include/openssl $(PYINSTALL)/include/
	cp $(OPENSSLBUILD)/libssl.a $(PYINSTALL)/lib/libssl.a
	cp $(OPENSSLBUILD)/libcrypto.a $(PYINSTALL)/lib/libcrypto.a

$(PYINSTALL)/lib/libsqlite3.a:
	rm -rf $(SQLITE3BUILD)
	mkdir $(SQLITE3BUILD)
	(\
		cd $(SQLITE3BUILD) \
		&& wget -q -O - $(SQLITE3TARBALL) | tar -xz --strip-components=1 \
		&& . $(PYODIDE_ROOT)/emsdk/emsdk/emsdk_env.sh \
		&& . $(PYODIDE_ROOT)/pyodide_env.sh \
		&& emconfigure ./configure \
			CFLAGS="-fPIC -Os" \
			--disable-readline \
			--disable-threadsafe \
			--disable-shared \
			--enable-static \
			--disable-static-shell \
			--disable-dependency-tracking \
			--prefix=$(SQLITE3BUILD)/dist \
		&& emmake make libsqlite3.la \
		&& emmake make install-libLTLIBRARIES install-includeHEADERS \
	)

	rm -rf $(PYINSTALL)/include/sqlite3
	mkdir -p $(PYINSTALL)/include/sqlite3
	mkdir -p $(PYINSTALL)/lib
	cp -r $(SQLITE3BUILD)/dist/lib/* $(PYINSTALL)/lib/
	cp -r $(SQLITE3BUILD)/dist/include/* $(PYINSTALL)/include/sqlite3


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
			  --without-pymalloc \
			  --disable-shared \
			  --disable-ipv6 \
			  --enable-big-digits=30 \
			  --enable-optimizations \
			  --host=wasm32-unknown-emscripten\
			  --build=$(shell $(PYBUILD)/config.guess) \
			  --prefix=$(PYINSTALL)  \
			  --with-build-python=$$(which python$(PYMAJOR).$(PYMINOR)) \
			  $(MAYBE_WITH_PYDEBUG) \
	)


$(PYBUILD)/Modules/Setup.local: Setup.local
	cp Setup.local $(PYBUILD)/Modules/

$(PYBUILD)/$(PYLIB): $(PYBUILD)/Makefile $(PYBUILD)/pyconfig.h $(PYBUILD)/Modules/Setup.local $(PYINSTALL)/lib/libffi.a $(PYINSTALL)/lib/liblzma.a $(PYINSTALL)/lib/libsqlite3.a
	cp Setup.local $(PYBUILD)/Modules/
	( \
		cd $(PYBUILD); \
		make regen-frozen; \
		emmake make CROSS_COMPILE=yes $(PYLIB) -j $${PYODIDE_JOBS:-3} \
	)
	touch $(PYBUILD)/$(PYLIB)
