PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

PYVERSION=3.6.4
PYMINOR=$(basename $(PYVERSION))

NPYVERSION=1.14.1

ROOT=$(abspath .)

HOSTPYTHONINSTALL=$(ROOT)/../cpython/build/$(PYVERSION)/host
HOSTPYTHON=$(HOSTPYTHONINSTALL)/bin/python3$(EXE)
PYTHONINCLUDE=$(ROOT)/../cpython/installs/python-$(PYVERSION)/include/python$(PYMINOR)

HOSTROOT=$(ROOT)/host
HOSTDIR=$(HOSTROOT)/numpy-$(NPYVERSION)
HOSTBUILD=$(HOSTDIR)/build

BUILD=$(ROOT)/build
BUILDCORE=$(BUILD)/numpy/core
BUILDLINALG=$(BUILD)/numpy/linalg
BUILDFFT=$(BUILD)/numpy/fft
BUILDRANDOM=$(BUILD)/numpy/random

ZIPFILE=$(ROOT)/downloads/numpy-$(NPYVERSION).zip
URL=https://pypi.python.org/packages/a3/99/74aa456fc740a7e8f733af4e8302d8e61e123367ec660cd89c53a3cd4d70/numpy-1.14.1.zip

PLATFORMSLUG=$(shell $(HOSTPYTHON) -c "import sysconfig; print(sysconfig.get_platform())")-$(PYMINOR)

INCLUDE=$(HOSTDIR)/numpy/core/include
SRC=$(HOSTDIR)/numpy/core/src
GENINCLUDE=$(HOSTBUILD)/src.$(PLATFORMSLUG)/numpy/core/include
GENSRC=$(HOSTBUILD)/src.$(PLATFORMSLUG)/numpy/core/src
LINALG_SRC=$(HOSTDIR)/numpy/linalg
LINALG_GENSRC=$(HOSTBUILD)/src.$(PLATFORMSLUG)/numpy/linalg
FFT_SRC=$(HOSTDIR)/numpy/fft
RANDOM_SRC=$(HOSTDIR)/numpy/random

CC=emcc
AR=emar
CFLAGS=-O3 -Werror -std=c99 -DNPY_INTERNAL_BUILD=1 -DHAVE_NPY_CONFIG_H=1 -D_FILE_OFFSET_BITS=64 -D_LARGEFILE_SOURCE=1 -D_LARGEFILE64_SOURCE=1 -I$(ROOT)/config -I$(INCLUDE) -I$(GENINCLUDE)/numpy -I$(INCLUDE)/private -I$(SRC) -I$(SRC)/.. -I$(SRC)/private -I$(SRC)/npymath -I$(SRC)/multiarray -I$(SRC)/umath -I$(SRC)/npysort -I$(PYTHONINCLUDE) -I$(GENSRC)/private -I$(GENSRC)/npymath -I$(GENSRC)/umath
LDFLAGS=\
	-Werror \
  -s EMULATED_FUNCTION_POINTERS=1 \
  -s EMULATE_FUNCTION_POINTER_CASTS=1 \
  -s SIDE_MODULE=1 \
	-s WASM=1 \
  --memory-init-file 0


all: \
	$(BUILD)/numpy/__init__.py \
	$(BUILDCORE)/multiarray.so \
	$(BUILDCORE)/umath.so \
	$(BUILDLINALG)/lapack_lite.so \
	$(BUILDLINALG)/_umath_linalg.so \
	$(BUILDRANDOM)/mtrand.so


clean:
	rm -fr $(HOSTROOT)
	rm -fr $(BUILD)


$(ZIPFILE):
	[ -d $(ROOT)/downloads ] || mkdir $(ROOT)/downloads
	wget -q -O $@ $(URL)
	md5sum --quiet --check checksums || (rm $@; false)


$(HOSTDIR)/setup.py: $(ZIPFILE)
	[ -d $(HOSTROOT) ] || mkdir $(HOSTROOT)
	unzip $(ZIPFILE) -d $(HOSTROOT)
	touch $(HOSTDIR)/setup.py


$(HOSTBUILD)/lib.$(PLATFORMSLUG)/numpy/__init__.py: $(ROOT)/.patched
	( \
	  cd $(HOSTDIR); \
    $(HOSTPYTHON) setup.py install \
	)


$(BUILD)/numpy/__init__.py: $(HOSTBUILD)/lib.$(PLATFORMSLUG)/numpy/__init__.py
	[ -d $(BUILD) ] || mkdir $(BUILD)
	cp -r $(HOSTBUILD)/lib.$(PLATFORMSLUG)/numpy $(BUILD) && \
	cd $(BUILD); find . -name "*.so" -type f -delete


$(ROOT)/.patched: $(HOSTDIR)/setup.py
	cat patches/*.patch | (cd $(HOSTDIR) ; patch -p1)
	touch $@


NPYMATH_SRC=\
	$(GENSRC)/npymath/ieee754.bc \
	$(GENSRC)/npymath/npy_math_complex.bc \
	$(SRC)/npymath/halffloat.bc \
	$(SRC)/npymath/npy_math.bc \


NPYSORT_SRC=\
	$(GENSRC)/npysort/binsearch.bc \
	$(GENSRC)/npysort/heapsort.bc \
	$(GENSRC)/npysort/mergesort.bc \
	$(GENSRC)/npysort/quicksort.bc \
	$(GENSRC)/npysort/selection.bc \


MULTIARRAY_SRC=\
	$(GENSRC)/multiarray/arraytypes.bc \
	$(GENSRC)/multiarray/einsum.bc \
	$(GENSRC)/multiarray/lowlevel_strided_loops.bc \
	$(GENSRC)/multiarray/nditer_templ.bc \
	$(GENSRC)/multiarray/scalartypes.bc \
	$(SRC)/multiarray/alloc.bc \
	$(SRC)/multiarray/array_assign.bc \
	$(SRC)/multiarray/array_assign_array.bc \
	$(SRC)/multiarray/array_assign_scalar.bc \
	$(SRC)/multiarray/arrayobject.bc \
	$(SRC)/multiarray/buffer.bc \
	$(SRC)/multiarray/calculation.bc \
	$(SRC)/multiarray/common.bc \
	$(SRC)/multiarray/compiled_base.bc \
	$(SRC)/multiarray/conversion_utils.bc \
	$(SRC)/multiarray/convert.bc \
	$(SRC)/multiarray/convert_datatype.bc \
	$(SRC)/multiarray/ctors.bc \
	$(SRC)/multiarray/datetime.bc \
	$(SRC)/multiarray/datetime_busday.bc \
	$(SRC)/multiarray/datetime_busdaycal.bc \
	$(SRC)/multiarray/datetime_strings.bc \
	$(SRC)/multiarray/descriptor.bc \
	$(SRC)/multiarray/dragon4.bc \
	$(SRC)/multiarray/dtype_transfer.bc \
	$(SRC)/multiarray/flagsobject.bc \
	$(SRC)/multiarray/getset.bc \
	$(SRC)/multiarray/hashdescr.bc \
	$(SRC)/multiarray/item_selection.bc \
	$(SRC)/multiarray/iterators.bc \
	$(SRC)/multiarray/mapping.bc \
	$(SRC)/multiarray/methods.bc \
	$(SRC)/multiarray/multiarraymodule.bc \
	$(SRC)/multiarray/nditer_api.bc \
	$(SRC)/multiarray/nditer_constr.bc \
	$(SRC)/multiarray/nditer_pywrap.bc \
	$(SRC)/multiarray/number.bc \
	$(SRC)/multiarray/numpyos.bc \
	$(SRC)/multiarray/refcount.bc \
	$(SRC)/multiarray/scalarapi.bc \
	$(SRC)/multiarray/sequence.bc \
	$(SRC)/multiarray/shape.bc \
	$(SRC)/multiarray/strfuncs.bc \
	$(SRC)/multiarray/temp_elide.bc \
	$(SRC)/multiarray/ucsnarrow.bc \
	$(SRC)/multiarray/usertypes.bc \
	$(SRC)/multiarray/vdot.bc \
	$(SRC)/private/mem_overlap.bc \
	$(SRC)/private/npy_longdouble.bc \
	$(SRC)/private/ufunc_override.bc


UMATH_SRC=\
	$(GENSRC)/umath/loops.bc \
	$(GENSRC)/umath/scalarmath.bc \
	$(SRC)/private/mem_overlap.bc \
	$(SRC)/private/npy_longdouble.bc \
	$(SRC)/private/ufunc_override.bc \
	$(SRC)/umath/extobj.bc \
	$(SRC)/umath/override.bc \
	$(SRC)/umath/reduction.bc \
	$(SRC)/umath/ufunc_object.bc \
	$(SRC)/umath/ufunc_type_resolution.bc \
	$(SRC)/umath/umathmodule.bc \


LAPACK_BLAS_SRC=\
	$(LINALG_SRC)/lapack_lite/python_xerbla.bc \
	$(LINALG_SRC)/lapack_lite/f2c_z_lapack.bc \
	$(LINALG_SRC)/lapack_lite/f2c_d_lapack.bc \
	$(LINALG_SRC)/lapack_lite/f2c_s_lapack.bc \
	$(LINALG_SRC)/lapack_lite/f2c_c_lapack.bc \
	$(LINALG_SRC)/lapack_lite/f2c_lapack.bc \
	$(LINALG_SRC)/lapack_lite/f2c_blas.bc \
	$(LINALG_SRC)/lapack_lite/f2c_config.bc \
	$(LINALG_SRC)/lapack_lite/f2c.bc


LAPACK_LITE_SRC=\
	$(LINALG_SRC)/lapack_litemodule.bc


UMATH_LINALG_SRC=\
	$(LINALG_GENSRC)/umath_linalg.bc


FFTPACK_LITE_SRC=\
	$(FFT_SRC)/fftpack_litemodule.bc \
  $(FFT_SRC)/fftpack.bc


MTRAND_SRC=\
	$(RANDOM_SRC)/mtrand/mtrand.bc \
	$(RANDOM_SRC)/mtrand/randomkit.bc \
	$(RANDOM_SRC)/mtrand/initarray.bc \
	$(RANDOM_SRC)/mtrand/distributions.bc


$(BUILDCORE)/multiarray.so: $(MULTIARRAY_SRC) $(NPYMATH_SRC) $(NPYSORT_SRC)
	$(CC) $(LDFLAGS) $^ -o $(BUILDCORE)/multiarray.wasm
	mv $(BUILDCORE)/multiarray.wasm $(BUILDCORE)/multiarray.so


$(BUILDCORE)/umath.so: $(UMATH_SRC) $(NPYMATH_SRC)
	$(CC) $(LDFLAGS) $^ -o $(BUILDCORE)/umath.wasm
	mv $(BUILDCORE)/umath.wasm $(BUILDCORE)/umath.so


$(BUILDLINALG)/lapack_lite.so: $(LAPACK_LITE_SRC) $(LAPACK_BLAS_SRC) $(NPYMATH_SRC)
	$(CC) $(LDFLAGS) $^ -o $(BUILDLINALG)/lapack_lite.wasm
	mv $(BUILDLINALG)/lapack_lite.wasm $(BUILDLINALG)/lapack_lite.so


$(BUILDLINALG)/_umath_linalg.so: $(UMATH_LINALG_SRC) $(LAPACK_BLAS_SRC) $(NPYMATH_SRC)
	$(CC) $(LDFLAGS) $^ -o $(BUILDLINALG)/_umath_linalg.wasm
	mv $(BUILDLINALG)/_umath_linalg.wasm $(BUILDLINALG)/_umath_linalg.so


$(BUILDFFT)/fftpack_lite.so: $(FFTPACK_LITE_SRC)
	$(CC) $(LDFLAGS) $^ -o $(BUILDFFT)/fftpack_lite.wasm
	mv $(BUILDFFT)/fftpack_lite.wasm $(BUILDFFT)/fftpack_lite.so


$(BUILDRANDOM)/mtrand.so: $(MTRAND_SRC)
	$(CC) $(LDFLAGS) $^ -o $(BUILDRANDOM)/mtrand.wasm
	mv $(BUILDRANDOM)/mtrand.wasm $(BUILDRANDOM)/mtrand.so


%.bc: %.c $(BUILD)/numpy/__init__.py
	$(CC) $(CFLAGS) -include math.h -c $< -o $@
