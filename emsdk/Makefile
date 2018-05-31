all: emsdk/emsdk

emsdk/emsdk:
	git clone https://github.com/juj/emsdk.git
	( \
		cd emsdk ; \
		./emsdk install --build=Release sdk-tag-1.38.4-64bit binaryen-tag-1.38.4-64bit ; \
		cd .. ; \
		(cat patches/*.patch | patch -p1) ; \
		cd emsdk ; \
		./emsdk install --build=Release sdk-tag-1.37.39-64bit binaryen-tag-1.38.4-64bit ; \
		./emsdk activate --embedded --build=Release sdk-tag-1.38.4-64bit binaryen-tag-1.38.4-64bit \
	)

clean:
	rm -rf emsdk
