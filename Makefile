PYVERSION=3.5.2
PYMINOR=$(basename $(PYVERSION))
CPYTHON_EMSCRIPTEN_ROOT=../cpython-emscripten

CC=emcc
CXX=em++
OPTFLAGS=-O2
CXXFLAGS=-std=c++14 $(OPTFLAGS) -g -I $(CPYTHON_EMSCRIPTEN_ROOT)/installs/python-$(PYVERSION)/include/python$(PYMINOR)/ -Wno-warn-absolute-paths
LDFLAGS=$(OPTFLAGS) $(CPYTHON_EMSCRIPTEN_ROOT)/installs/python-$(PYVERSION)/lib/libpython$(PYMINOR).a \
  -s "BINARYEN_METHOD='native-wasm,interpret-binary,interpret-asm2wasm'" \
  -s TOTAL_MEMORY=268435456 \
  -s ASSERTIONS=2 \
  -s EMULATE_FUNCTION_POINTER_CASTS=1 \
  -s EXPORTED_FUNCTIONS='["_main"]' \
  --memory-init-file 0


all: pyodide.asm.html


pyodide.asm.html: main.bc root
	$(CC) -s WASM=1 --bind -o $@ $(filter %.bc,$^) $(LDFLAGS) \
		$(foreach d,$(wildcard root/*),--preload-file $d@/$(notdir $d))


clean:
	-rm -fr root
	-rm pyodide.asm.*
	-rm *.bc


%.bc: %.cpp $(CPYTHON_EMSCRIPTEN_ROOT)/installs/python-$(PYVERSION)/lib/python$(PYMINOR)
	$(CXX) --bind -o $@ $< $(CXXFLAGS)


root: $(CPYTHON_EMSCRIPTEN_ROOT)/installs/python-$(PYVERSION)/lib/python$(PYMINOR)
	mkdir -p root/lib
	cp -a $(CPYTHON_EMSCRIPTEN_ROOT)/installs/python-$(PYVERSION)/lib/python$(PYMINOR)/ root/lib
	( \
		cd root/lib/python$(PYMINOR); \
		rm -fr test distutils ensurepip idlelib __pycache__ tkinter; \
	)


$(CPYTHON_EMSCRIPTEN_ROOT)/installs/python-$(PYVERSION)/lib/python$(PYMINOR):
	make -C $(CPYTHON_EMSCRIPTEN_ROOT)/$(PYVERSION)
