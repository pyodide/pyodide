import pytest
from pydantic.error_wrappers import ValidationError

from pyodide_build.io import MetaConfig, _BuildSpec, _SourceSpec


def test_wheel_and_host_deps():
    """Check that when source URL is a wheel

    there can be no host dependencies
    """
    msg = (
        "When source -> url is a wheel .test.whl. the package cannot have "
        "host dependencies. Found .'b'."
    )
    with pytest.raises(ValidationError, match=msg):
        MetaConfig(
            package={"name": "a", "version": "0.2"},
            source={"url": "test.whl", "sha256": ""},
            requirements={"host": ["b"]},
        )


def test_source_fields():
    """Test consistency of source meta.yaml fields"""

    msg = "Source section should not have both a 'url' and a 'path' key"
    with pytest.raises(ValidationError, match=msg):
        _SourceSpec(url="a", path="b")

    msg = "If source is downloaded from url, it must have a 'source/sha256' hash"
    with pytest.raises(ValidationError, match=msg):
        _SourceSpec(url="a")

    msg = "If source is in tree, 'source/patches' and 'source/extras' keys are not allowed"
    with pytest.raises(ValidationError, match=msg):
        _SourceSpec(path="b", patches=["a"])

    msg = "If source is a wheel, 'source/patches' and 'source/extras' keys are not allowed"
    with pytest.raises(ValidationError, match=msg):
        _SourceSpec(url="b.whl", patches=["a"])


def test_build_fields():
    """Test consistency of source meta.yaml fields"""
    msg = "If building a static_library, 'build/post' key is not allowed."
    with pytest.raises(ValidationError, match=msg):
        _BuildSpec(type="static_library", post="a")
