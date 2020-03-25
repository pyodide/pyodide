PYODIDE_ROOT=$(abspath ..)
include ../Makefile.envs

CLAPACK_VERSION=3.2.1

ROOT=$(abspath .)

SRC=$(ROOT)/CLAPACK-WA


all: $(SRC)/lapack_WA.bc

clean:
	rm -rf CLAPACK-WA

$(SRC)/lapack_WA.bc:  $(SRC)/Makefile
	# We build BLAS/LAPACK only for target.
	# On host we include -LCLAPACK-WA path which has no effect on host.
	# On target it gets rewritten by pywasmcross to the full patch of
	# blas_WA.bc, lapack_WA.bc which are linked statically in scipy
	# in each module that needs them.
	emmake make -C CLAPACK-WA/


$(SRC)/Makefile:
	wget -q -O clapack.tgz http://www.netlib.org/clapack/clapack.tgz
	md5sum --quiet --check checksums || (rm -f clapack.tgz; false)
	tar xzf clapack.tgz
	rm -rf $(SRC)
	mv CLAPACK-$(CLAPACK_VERSION) $(SRC)
	( \
		cd $(SRC); \
		(cat ../patches/*.patch | patch -p1) \
	)
	touch $(SRC)/F2CLIBS/libf2c/arith.h
