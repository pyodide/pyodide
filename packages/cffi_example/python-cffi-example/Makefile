all: cffi_example/_person.so cffi_example/_fnmatch.so

cffi_example/_person.so: cffi_example/build_person.py
	python $<

cffi_example/_fnmatch.so: cffi_example/build_fnmatch.py
	python $<

clean:
	rm cffi_example/_*.c cffi_example/_*.o cffi_example/_*.so
