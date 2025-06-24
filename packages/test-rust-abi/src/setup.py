from setuptools import setup
from setuptools_rust import Binding, RustExtension

setup(
    name="test_rust_abi",
    version="1.0",
    rust_extensions=[
        RustExtension("test_rust_abi", "Cargo.toml", binding=Binding.PyO3)
    ],
    # rust extensions are not zip safe, just like C-extensions.
    zip_safe=False,
)
