import os
import pathlib

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext as build_ext_orig

os.environ['DISABLE_NUMCODECS_SSE2'] = "1"
os.environ['DISABLE_NUMCODECS_AVX2'] = "1"

class cmake_build_ext(build_ext_orig):

    def run(self):
        for ext in self.extensions:
            self.build_cmake(ext)
        print('==========>>cmake done')
        super().run()
        print('==========>>build done')

    def build_cmake(self, ext):
        cwd = pathlib.Path().absolute()
        # these dirs will be created in build_py, so if you don't have
        # any python sources to bundle, the dirs will be missing
        build_temp = pathlib.Path(self.build_temp)
        build_temp.mkdir(parents=True, exist_ok=True)
        extdir = pathlib.Path(self.get_ext_fullpath(ext.name))
        extdir.mkdir(parents=True, exist_ok=True)

        # example of cmake args
        config = 'Debug' if self.debug else 'Release'
        cmake_args = [
            '-DBUILD_BENCHMARKS=0',
            '-DBUILD_SHARED=0',
            '-DBUILD_TESTS=0',
            '-DDEACTIVATE_AVX2=1',
            '-DDEACTIVATE_SSE2=1',
            '-DCMAKE_LIBRARY_OUTPUT_DIRECTORY=' +
            str(extdir.parent.absolute()),
            '-DCMAKE_BUILD_TYPE=' + config
        ]

        # example of build args
        build_args = [
            '--config', config,
            '--', '-j4'
        ]

        os.chdir(str(build_temp))
        print('==========>>cmake', build_temp)
        self.spawn(['emcmake', 'cmake', str(cwd / 'c-blosc')] + cmake_args)
        print('==========>>cmake build')
        if not self.dry_run:
            self.spawn(['cmake', '--build', '.'] + build_args)
        # Troubleshooting: if fail on line above then delete all possible
        # temporary CMake files including "CMakeCache.txt" in top level dir.
        os.chdir(str(cwd))
        
