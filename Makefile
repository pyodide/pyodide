PYVERSION=3.6.4
PYMINOR=$(basename $(PYVERSION))
CPYTHONROOT=cpython
CPYTHONLIB=$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/python$(PYMINOR)
CPYTHONINC=$(CPYTHONROOT)/installs/python-$(PYVERSION)/include/python$(PYMINOR)

CC=emcc
CXX=em++
OPTFLAGS=-O3
CXXFLAGS=-std=c++14 $(OPTFLAGS) -g -I $(CPYTHONINC) -Wno-warn-absolute-paths
LDFLAGS=$(OPTFLAGS) \
	$(CPYTHONROOT)/installs/python-$(PYVERSION)/lib/libpython$(PYMINOR).a \
  -s "BINARYEN_METHOD='native-wasm,interpret-binary,interpret-asm2wasm'" \
  -s TOTAL_MEMORY=268435456 \
  -s ASSERTIONS=2 \
  -s EMULATE_FUNCTION_POINTER_CASTS=1 \
  -s EXPORTED_FUNCTIONS='["_main"]' \
	-s WASM=1 \
  --memory-init-file 0


all: build/pyodide.asm.html build/pyodide.js


build/pyodide.asm.html: src/main.bc src/jsproxy.bc src/js2python.bc src/pylocals.bc \
                        src/pyproxy.bc src/python2js.bc src/runpython.bc root
	$(CC) -s EXPORT_NAME="'pyodide'" --bind -o $@ $(filter %.bc,$^) $(LDFLAGS) \
		$(foreach d,$(wildcard root/*),--preload-file $d@/$(notdir $d))


build/pyodide.js: src/pyodide.js
	cp $< $@


clean:
	-rm -fr root
	-rm build/*
	-rm src/*.bc
	make -C $(CPYTHONROOT) clean


%.bc: %.cpp $(CPYTHONLIB)
	$(CXX) --bind -o $@ $< $(CXXFLAGS)


root: $(CPYTHONLIB)
	mkdir -p root/lib
	cp -a $(CPYTHONLIB)/ root/lib
	( \
		cd root/lib/python$(PYMINOR); \
		rm -fr test distutils ensurepip idlelib __pycache__ tkinter; \
	)

$(CPYTHONLIB):
	make -C $(CPYTHONROOT)
