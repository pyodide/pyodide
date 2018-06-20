import os
import yaml

ROOTDIR = os.path.abspath(os.path.dirname(__file__))
HOSTPYTHON = os.path.abspath(os.path.join(ROOTDIR, '..', 'cpython', 'build', '3.6.4', 'host'))
TARGETPYTHON = os.path.abspath(os.path.join(ROOTDIR, '..', 'cpython', 'installs', 'python-3.6.4'))
DEFAULT_LD = ' '.join([
    '-O3',
    '-s', "BINARYEN_METHOD='native-wasm'",
	'-Werror',
    '-s', 'EMULATED_FUNCTION_POINTERS=1',
    '-s', 'EMULATE_FUNCTION_POINTER_CASTS=1',
    '-s', 'SIDE_MODULE=1',
    '-s', 'WASM=1',
    '--memory-init-file', '0'
    ])


def parse_package(package):
    # TODO: Validate against a schema
    with open(package) as fd:
        return yaml.load(fd)
