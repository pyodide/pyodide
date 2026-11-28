from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext

# Two side modules: `_catch` (a regular extension module) links against
# `libthrow.so` (a plain shared library), so C++ exceptions and longjmp cross a
# shared library boundary. `libthrow.so` is found next to `_catch` at runtime
# through the `$ORIGIN` rpath.
THROW = "cpp_exceptions_test.libthrow"
CATCH = "cpp_exceptions_test._catch"


class BuildExt(build_ext):
    def get_ext_filename(self, fullname):
        # Called with either the full or the last component of the name.
        if THROW.endswith(fullname):
            return fullname.replace(".", "/") + ".so"
        return super().get_ext_filename(fullname)

    def build_extensions(self):
        throw, catch = (
            next(ext for ext in self.extensions if ext.name == name)
            for name in (THROW, CATCH)
        )
        self.build_extension(throw)
        catch.extra_objects = [self.get_ext_fullpath(THROW)]
        self.build_extension(catch)


setup(
    name="test-cpp-exceptions",
    version="0.1",
    packages=["cpp_exceptions_test"],
    ext_modules=[
        Extension(THROW, sources=["throw.cpp"], language="c++"),
        Extension(
            CATCH,
            sources=["catch.cpp"],
            language="c++",
            extra_compile_args=["-mreference-types"],
            extra_link_args=["-Wl,-rpath,$ORIGIN"],
        ),
    ],
    cmdclass={"build_ext": BuildExt},
)
