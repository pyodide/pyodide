from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["frozenlist"])
def test_subclass(self) -> None:
    from collections.abc import MutableSequence
    from frozenlist import FrozenList
    assert issubclass(FrozenList, MutableSequence)

@run_in_pyodide(packages=["frozenlist"])
def test_iface(self) -> None:
    from collections.abc import MutableSequence
    from frozenlist import FrozenList
    SKIP_METHODS = {"__abstractmethods__", "__slots__"}
    for name in set(dir(MutableSequence)) - SKIP_METHODS
        if name.startswith("_") and not name.endswith("_"):
            continue
        assert hasattr(FrozenList, name)

@run_in_pyodide(packages=["frozenlist"])
def test_ctor_default(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([])
    assert not _list.frozen

@run_in_pyodide(packages=["frozenlist"])
def test_ctor(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1])
    assert not _list.frozen

@run_in_pyodide(packages=["frozenlist"])
def test_ctor_copy_list(self) -> None:
    from frozenlist import FrozenList
    orig = [1]
    _list = FrozenList(orig)
    del _list[0]
    assert _list != orig

@run_in_pyodide(packages=["frozenlist"])
def test_freeze(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList()
    _list.freeze()
    assert _list.frozen

@run_in_pyodide(packages=["frozenlist"])
def test_repr(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1])
    assert repr(_list) == "<FrozenList(frozen=False, [1])>"
    _list.freeze()
    assert repr(_list) == "<FrozenList(frozen=True, [1])>"

@run_in_pyodide(packages=["frozenlist"])
def test_getitem(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1, 2])
    assert _list[1] == 2

@run_in_pyodide(packages=["frozenlist"])
def test_setitem(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1, 2])
    _list[1] = 3
    assert _list[1] == 3

@run_in_pyodide(packages=["frozenlist"])
def test_delitem(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1, 2])
    del _list[0]
    assert len(_list) == 1
    assert _list[0] == 2

@run_in_pyodide(packages=["frozenlist"])
def test_len(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1])
    assert len(_list) == 1

@run_in_pyodide(packages=["frozenlist"])
def test_iter(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1, 2])
    assert list(iter(_list)) == [1, 2]

@run_in_pyodide(packages=["frozenlist"])
def test_reversed(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1, 2])
    assert list(reversed(_list)) == [2, 1]

@run_in_pyodide(packages=["frozenlist"])
def test_eq(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1])
    assert _list == [1]

@run_in_pyodide(packages=["frozenlist"])
def test_ne(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1])
    assert _list != [2]

@run_in_pyodide(packages=["frozenlist"])
def test_le(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1])
    assert _list <= [1]

@run_in_pyodide(packages=["frozenlist"])
def test_lt(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1])
    assert _list <= [3]

@run_in_pyodide(packages=["frozenlist"])
def test_ge(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1])
    assert _list >= [1]

@run_in_pyodide(packages=["frozenlist"])
def test_gt(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([2])
    assert _list > [1]

@run_in_pyodide(packages=["frozenlist"])
def test_insert(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([2])
    _list.insert(0, 1)
    assert _list == [1, 2]

@run_in_pyodide(packages=["frozenlist"])
def test_frozen_setitem(self) -> None:
    from frozenlist import FrozenList
    import pytest
    _list = FrozenList([1])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list[0] = 2

@run_in_pyodide(packages=["frozenlist"])
def test_frozen_delitem(self) -> None:
    from frozenlist import FrozenList
    import pytest
    _list = FrozenList([1])
    _list.freeze()
    with pytest.raises(RuntimeError):
        del _list[0]

@run_in_pyodide(packages=["frozenlist"])
def test_frozen_insert(self) -> None:
    from frozenlist import FrozenList
    import pytest
    _list = FrozenList([1])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list.insert(0, 2)

@run_in_pyodide(packages=["frozenlist"])
def test_contains(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([2])
    assert 2 in _list

@run_in_pyodide(packages=["frozenlist"])
def test_iadd(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1])
    _list += [2]
    assert _list == [1, 2]

@run_in_pyodide(packages=["frozenlist"])
def test_iadd_frozen(self) -> None:
    from frozenlist import FrozenList
    import pytest
    _list = FrozenList([1])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list += [2]
    assert _list == [1]

@run_in_pyodide(packages=["frozenlist"])
def test_index(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1])
    assert _list.index(1) == 0

@run_in_pyodide(packages=["frozenlist"])
def test_remove(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1])
    _list.remove(1)
    assert len(_list) == 0

@run_in_pyodide(packages=["frozenlist"])
def test_remove_frozen(self) -> None:
    from frozenlist import FrozenList
    import pytest
    _list = FrozenList([1])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list.remove(1)
    assert _list == [1]

@run_in_pyodide(packages=["frozenlist"])
def test_clear(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1])
    _list.clear()
    assert len(_list) == 0

@run_in_pyodide(packages=["frozenlist"])
def test_clear_frozen(self) -> None:
    from frozenlist import FrozenList
    import pytest
    _list = FrozenList([1])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list.clear()
    assert _list == [1]

@run_in_pyodide(packages=["frozenlist"])
def test_extend(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1])
    _list.extend([2])
    assert _list == [1, 2]

@run_in_pyodide(packages=["frozenlist"])
def test_extend_frozen(self) -> None:
    from frozenlist import FrozenList
    import pytest
    _list = FrozenList([1])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list.extend([2])
    assert _list == [1]

@run_in_pyodide(packages=["frozenlist"])
def test_reverse(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1, 2])
    _list.reverse()
    assert _list == [2, 1]

@run_in_pyodide(packages=["frozenlist"])
def test_reverse_frozen(self) -> None:
    from frozenlist import FrozenList
    import pytest
    _list = FrozenList([1, 2])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list.reverse()
    assert _list == [1, 2]

@run_in_pyodide(packages=["frozenlist"])
def test_pop(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1, 2])
    assert _list.pop(0) == 1
    assert _list == [2]

@run_in_pyodide(packages=["frozenlist"])
def test_pop_default(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1, 2])
    assert _list.pop() == 2
    assert _list == [1]

@run_in_pyodide(packages=["frozenlist"])
def test_pop_frozen(self) -> None:
    from frozenlist import FrozenList
    import pytest
    _list = FrozenList([1, 2])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list.pop()
    assert _list == [1, 2]

@run_in_pyodide(packages=["frozenlist"])
def test_append(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1, 2])
    _list.append(3)
    assert _list == [1, 2, 3]

@run_in_pyodide(packages=["frozenlist"])
def test_append_frozen(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1, 2])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list.append(3)
    assert _list == [1, 2]

@run_in_pyodide(packages=["frozenlist"])
def test_hash(self) -> None:
    from frozenlist import FrozenList
    import pytest
    _list = FrozenList([1, 2])
    with pytest.raises(RuntimeError):
        hash(_list)

@run_in_pyodide(packages=["frozenlist"])
def test_hash_frozen(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1, 2])
    _list.freeze()
    h = hash(_list)
    assert h == hash((1, 2))

@run_in_pyodide(packages=["frozenlist"])
def test_dict_key(self) -> None:
    from frozenlist import FrozenList
    import pytest
    _list = FrozenList([1, 2])
    with pytest.raises(RuntimeError):
        {_list: "hello"}
    _list.freeze()
    {_list: "hello"}

@run_in_pyodide(packages=["frozenlist"])
def test_count(self) -> None:
    from frozenlist import FrozenList
    _list = FrozenList([1, 2])
    assert _list.count(1) == 1
