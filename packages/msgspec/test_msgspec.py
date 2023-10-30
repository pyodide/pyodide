from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["msgspec"])
def test_msgspec(selenium_standalone):
    import msgspec
    import pytest

    class User(msgspec.Struct):
        """A new type describing a User"""

        name: str
        groups: set[str] = set()
        email: str | None = None

    alice = User("alice", groups={"admin", "engineering"})
    msg = msgspec.json.encode(alice)

    # set order is undefined
    assert msg in [
        b'{"name":"alice","groups":["admin","engineering"],"email":null}',
        b'{"name":"alice","groups":["engineering","admin"],"email":null}',
    ]

    msgspec.json.decode(msg, type=User)

    with pytest.raises(msgspec.ValidationError, match=r"str.*int.*\$\.groups\[0\]"):
        msgspec.json.decode(b'{"name":"bob","groups":[123]}', type=User)
