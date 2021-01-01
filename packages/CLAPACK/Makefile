PYODIDE_ROOT=$(abspath ../..)
include ../../Makefile.envs

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
	emmake make -C CLAPACK-WA/ -j $${PYODIDE_JOBS:-3} blaslib lapacklib

clapack.tgz:
	wget -q -O clapack.tgz http://www.netlib.org/clapack/clapack.tgz
	md5sum --quiet --check checksums || (rm -f clapack.tgz; false)

$(SRC)/Makefile: clapack.tgz
	tar xzf clapack.tgz
	rm -rf $(SRC)
	mv CLAPACK-$(CLAPACK_VERSION) $(SRC)

	# The archive's contents have default permission 0750. If we use docker
	# to build, then we will not own the contents in the host, which means
	# we cannot navigate into the folder. Setting it to 0750 makes it
	# easier to debug.
	chmod -R o+rx $(SRC)

	cd $(SRC); cat ../patches/*.patch | patch -p1
	cp make.inc $(SRC)

	# In CLAPACK's Makefiles, some commands are mistakenly (?) hardcoded
	# instead of using the right variables
	sed -i 's/^	-ranlib /^	$(RANLIB)/' **/Makefile
	sed -i 's/^	ar /^	$(ARCH)/' **/Makefile
	sed -i 's/^	ld /^	$(LD)/' **/Makefile
