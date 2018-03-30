all: emsdk/emsdk_env.sh

emsdk/emsdk_env.sh:
	git clone https://github.com/juj/emsdk.git
	( \
		cd emsdk ; \
		./emsdk install --build=Release sdk-incoming-64bit binaryen-master-64bit ; \
		cd .. ; \
		(cat patches/*.patch | patch -p1) ; \
		cd emsdk ; \
		./emsdk install --build=Release sdk-incoming-64bit binaryen-master-64bit ; \
		./emsdk activate --embedded --build=Release sdk-incoming-64bit binaryen-master-64bit \
	)

clean:
	rm -rf emsdk
