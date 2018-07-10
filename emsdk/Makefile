all: emsdk/emsdk

# We hack the CPU_CORES, because if you use all of the cores on Circle-CI, you
# run out of memory

emsdk/emsdk:
	git clone https://github.com/juj/emsdk.git
	sed -i -e "s#CPU_CORES = max(multiprocessing.cpu_count()-1, 1)#CPU_CORES = 3#g" emsdk/emsdk
	( \
		cd emsdk ; \
		./emsdk install --build=Release sdk-tag-1.38.4-64bit binaryen-tag-1.38.4-64bit ; \
		cd .. ; \
		(cat patches/*.patch | patch -p1) ; \
    cp files/* emsdk/emscripten/tag-1.38.4/src/ ; \
		cd emsdk/binaryen/tag-1.38.4_64bit_binaryen/ ; \
    make ; \
	  cd ../.. ; \
		./emsdk activate --embedded --build=Release sdk-tag-1.38.4-64bit binaryen-tag-1.38.4-64bit \
	)

clean:
	rm -rf emsdk
