PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

MPLVERSION=2.2.2
NPYVERSION=1.14.1

ROOT=$(abspath .)

HOSTROOT=$(ROOT)/host
HOSTDIR=$(HOSTROOT)/matplotlib-$(MPLVERSION)
HOSTBUILD=$(HOSTDIR)/build
HOSTSRC=$(HOSTDIR)/src
HOSTLIB=$(HOSTDIR)/lib/matplotlib
AGGINC=$(HOSTDIR)/extern/agg24-svn/include
AGGSRC=$(HOSTDIR)/extern/agg24-svn/src
TTCONVSRC=$(HOSTDIR)/extern/ttconv
QHULLSRC=$(HOSTDIR)/extern/libqhull

BUILD=$(ROOT)/build/matplotlib

TARBALL=$(ROOT)/downloads/matplotlib-$(MPLVERSION).tar.gz
URL=https://files.pythonhosted.org/packages/ec/ed/46b835da53b7ed05bd4c6cae293f13ec26e877d2e490a53a709915a9dcb7/matplotlib-2.2.2.tar.gz

CC=emcc
CXX=em++
AR=emar
CFLAGS=-Wsign-compare -DNDEBUG -g -fwrapv -O3 -Wall -Wstrict-prototypes -fPIC -I$(HOSTSRC) -I../numpy/host/numpy-$(NPYVERSION)/numpy/core/include -I../numpy/config -I../numpy/host/numpy-$(NPYVERSION)/build/src.$(PLATFORMSLUG)/numpy/core/include/numpy -I$(PYTHONINCLUDE) -Wno-unused-function -s USE_FREETYPE=1 -s USE_LIBPNG=1 -s USE_ZLIB=1 -I$(AGGINC) -I$(HOSTDIR)/extern -I$(HOSTDIR) -DMPL_DEVNULL=/dev/null -D__STDC_FORMAT_MACROS=1 -DNPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION


OBJECTS= \
	$(BUILD)/ft2font.so \
	$(BUILD)/_png.so \
	$(BUILD)/_image.so \
	$(BUILD)/ttconv.so \
	$(BUILD)/_path.so \
	$(BUILD)/_contour.so \
	$(BUILD)/backends/_backend_agg.so \
	$(BUILD)/_tri.so \
	$(BUILD)/_qhull.so


AGGOBJECTS = \
	$(AGGSRC)/agg_bezier_arc.bc \
	$(AGGSRC)/agg_curves.bc \
	$(AGGSRC)/agg_image_filters.bc \
	$(AGGSRC)/agg_trans_affine.bc \
	$(AGGSRC)/agg_vcgen_contour.bc \
	$(AGGSRC)/agg_vcgen_dash.bc \
	$(AGGSRC)/agg_vcgen_stroke.bc \
	$(AGGSRC)/agg_vpgen_segmentator.bc


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
	cp $(ROOT)/setup.cfg $(HOSTDIR)
	touch $(HOSTDIR)/setup.py


$(HOSTBUILD)/lib.$(PLATFORMSLUG)/matplotlib/__init__.py: $(ROOT)/.patched
	( \
	  cd $(HOSTDIR); \
    $(HOSTPYTHON) setup.py build \
	)


$(BUILD)/__init__.py: $(HOSTBUILD)/lib.$(PLATFORMSLUG)/matplotlib/__init__.py
	[ -d $(ROOT)/build ] || mkdir $(ROOT)/build
	cp -r $(HOSTBUILD)/lib.$(PLATFORMSLUG)/matplotlib $(ROOT)/build && \
	cp $(ROOT)/fontList.json $(BUILD)
	cp $(ROOT)/src/wasm_backend.py $(BUILD)/backends
	( \
		cd $(BUILD); \
		find . -name "*.so" -type f -delete; \
		rm -rf backends/qt_editor; \
		rm -rf backends/web_backend; \
		rm -rf sphinxext; \
  )


$(ROOT)/.patched: $(HOSTDIR)/setup.py
	cat patches/*.patch | (cd $(HOSTDIR) ; patch -p1)
	touch $@


$(BUILD)/ft2font.so: \
		$(HOSTSRC)/ft2font.bc \
		$(HOSTSRC)/ft2font_wrapper.bc \
		$(HOSTSRC)/mplutils.bc
	$(CC) $(SIDE_LDFLAGS) -lfreetype $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_png.so: \
		$(HOSTSRC)/_png.bc
	$(CC) ../emsdk/emsdk/.emscripten_cache/asmjs/libpng.bc $^ -o $@.wasm $(SIDE_LDFLAGS)
	mv $@.wasm $@


$(BUILD)/_image.so: \
		$(HOSTSRC)/_image.bc \
		$(HOSTSRC)/_image_wrapper.bc \
		$(HOSTSRC)/mplutils.bc \
		$(HOSTSRC)/py_converters.bc \
		$(AGGOBJECTS)
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/ttconv.so: \
		$(HOSTSRC)/_ttconv.bc \
		$(TTCONVSRC)/pprdrv_tt.bc \
		$(TTCONVSRC)/pprdrv_tt2.bc \
		$(TTCONVSRC)/ttutil.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_path.so: \
		$(HOSTSRC)/py_converters.bc \
		$(HOSTSRC)/_path_wrapper.bc \
		$(AGGOBJECTS)
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_contour.so: \
		$(HOSTSRC)/_contour.bc \
		$(HOSTSRC)/_contour_wrapper.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_qhull.so: \
		$(HOSTSRC)/qhull_wrap.bc \
		$(QHULLSRC)/geom.bc \
		$(QHULLSRC)/geom2.bc \
		$(QHULLSRC)/global.bc \
		$(QHULLSRC)/io.bc \
		$(QHULLSRC)/libqhull.bc \
		$(QHULLSRC)/mem.bc \
		$(QHULLSRC)/merge.bc \
		$(QHULLSRC)/poly.bc \
		$(QHULLSRC)/poly2.bc \
		$(QHULLSRC)/qset.bc \
		$(QHULLSRC)/random.bc \
		$(QHULLSRC)/rboxlib.bc \
		$(QHULLSRC)/stat.bc \
		$(QHULLSRC)/user.bc \
		$(QHULLSRC)/usermem.bc \
		$(QHULLSRC)/userprintf.bc \
		$(QHULLSRC)/userprintf_rbox.bc
	$(CC) $(SIDE_LDFLAGS) -lm $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/_tri.so: \
		$(HOSTLIB)/tri/_tri.bc \
		$(HOSTLIB)/tri/_tri_wrapper.bc \
		$(HOSTSRC)/mplutils.bc
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


$(BUILD)/backends/_backend_agg.so: \
		$(HOSTSRC)/mplutils.bc \
		$(HOSTSRC)/py_converters.bc \
		$(HOSTSRC)/_backend_agg.bc \
		$(HOSTSRC)/_backend_agg_wrapper.bc \
		$(AGGOBJECTS)
	$(CC) $(SIDE_LDFLAGS) $^ -o $@.wasm
	mv $@.wasm $@


%.bc: %.c
	$(CC) -DPY_ARRAY_UNIQUE_SYMBOL=_path_array_api $(CFLAGS) -c $< -o $@


%.bc: %.cpp
	$(CXX) -DPY_ARRAY_UNIQUE_SYMBOL=_path_array_api $(CFLAGS) -c $< -o $@
