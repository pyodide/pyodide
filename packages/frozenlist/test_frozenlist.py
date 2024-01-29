from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["frozenlist"])
def test_subclass(selenium):
    from collections.abc import MutableSequence

    from frozenlist import FrozenList

    assert issubclass(FrozenList, MutableSequence)


@run_in_pyodide(packages=["frozenlist"])
def test_iface(selenium):
    from collections.abc import MutableSequence

    from frozenlist import FrozenList

    SKIP_METHODS = {"__abstractmethods__", "__slots__"}
    for name in set(dir(MutableSequence)) - SKIP_METHODS:
        if name.startswith("_") and not name.endswith("_"):
            continue
        assert hasattr(FrozenList, name)


@run_in_pyodide(packages=["frozenlist"])
def test_ctor_default(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([])
    assert not _list.frozen


@run_in_pyodide(packages=["frozenlist"])
def test_ctor(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1])
    assert not _list.frozen


@run_in_pyodide(packages=["frozenlist"])
def test_ctor_copy_list(selenium):
    from frozenlist import FrozenList

    orig = [1]
    _list = FrozenList(orig)
    del _list[0]
    assert _list != orig


@run_in_pyodide(packages=["frozenlist"])
def test_freeze(selenium):
    from frozenlist import FrozenList

    _list = FrozenList()
    _list.freeze()
    assert _list.frozen


@run_in_pyodide(packages=["frozenlist"])
def test_repr(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1])
    assert repr(_list) == "<FrozenList(frozen=False, [1])>"
    _list.freeze()
    assert repr(_list) == "<FrozenList(frozen=True, [1])>"


@run_in_pyodide(packages=["frozenlist"])
def test_getitem(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    assert _list[1] == 2


@run_in_pyodide(packages=["frozenlist"])
def test_setitem(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    _list[1] = 3
    assert _list[1] == 3


@run_in_pyodide(packages=["frozenlist"])
def test_delitem(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    del _list[0]
    assert len(_list) == 1
    assert _list[0] == 2


@run_in_pyodide(packages=["frozenlist"])
def test_len(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1])
    assert len(_list) == 1


@run_in_pyodide(packages=["frozenlist"])
def test_iter(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    assert list(iter(_list)) == [1, 2]


@run_in_pyodide(packages=["frozenlist"])
def test_reversed(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    assert list(reversed(_list)) == [2, 1]


@run_in_pyodide(packages=["frozenlist"])
def test_eq(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1])
    assert _list == [1]


@run_in_pyodide(packages=["frozenlist"])
def test_ne(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1])
    assert _list != [2]


@run_in_pyodide(packages=["frozenlist"])
def test_le(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1])
    assert _list <= [1]


@run_in_pyodide(packages=["frozenlist"])
def test_lt(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1])
    assert _list <= [3]


@run_in_pyodide(packages=["frozenlist"])
def test_ge(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1])
    assert _list >= [1]


@run_in_pyodide(packages=["frozenlist"])
def test_gt(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([2])
    assert _list > [1]


@run_in_pyodide(packages=["frozenlist"])
def test_insert(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([2])
    _list.insert(0, 1)
    assert _list == [1, 2]


@run_in_pyodide(packages=["frozenlist"])
def test_frozen_setitem(selenium):
    import pytest
    from frozenlist import FrozenList

    _list = FrozenList([1])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list[0] = 2


@run_in_pyodide(packages=["frozenlist"])
def test_frozen_delitem(selenium):
    import pytest
    from frozenlist import FrozenList

    _list = FrozenList([1])
    _list.freeze()
    with pytest.raises(RuntimeError):
        del _list[0]


@run_in_pyodide(packages=["frozenlist"])
def test_frozen_insert(selenium):
    import pytest
    from frozenlist import FrozenList

    _list = FrozenList([1])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list.insert(0, 2)


@run_in_pyodide(packages=["frozenlist"])
def test_contains(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([2])
    assert 2 in _list


@run_in_pyodide(packages=["frozenlist"])
def test_iadd(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1])
    _list += [2]
    assert _list == [1, 2]


@run_in_pyodide(packages=["frozenlist"])
def test_iadd_frozen(selenium):
    import pytest
    from frozenlist import FrozenList

    _list = FrozenList([1])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list += [2]
    assert _list == [1]


@run_in_pyodide(packages=["frozenlist"])
def test_index(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1])
    assert _list.index(1) == 0


@run_in_pyodide(packages=["frozenlist"])
def test_remove(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1])
    _list.remove(1)
    assert len(_list) == 0


@run_in_pyodide(packages=["frozenlist"])
def test_remove_frozen(selenium):
    import pytest
    from frozenlist import FrozenList

    _list = FrozenList([1])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list.remove(1)
    assert _list == [1]


@run_in_pyodide(packages=["frozenlist"])
def test_clear(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1])
    _list.clear()
    assert len(_list) == 0


@run_in_pyodide(packages=["frozenlist"])
def test_clear_frozen(selenium):
    import pytest
    from frozenlist import FrozenList

    _list = FrozenList([1])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list.clear()
    assert _list == [1]


@run_in_pyodide(packages=["frozenlist"])
def test_extend(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1])
    _list.extend([2])
    assert _list == [1, 2]


@run_in_pyodide(packages=["frozenlist"])
def test_extend_frozen(selenium):
    import pytest
    from frozenlist import FrozenList

    _list = FrozenList([1])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list.extend([2])
    assert _list == [1]


@run_in_pyodide(packages=["frozenlist"])
def test_reverse(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    _list.reverse()
    assert _list == [2, 1]


@run_in_pyodide(packages=["frozenlist"])
def test_reverse_frozen(selenium):
    import pytest
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list.reverse()
    assert _list == [1, 2]


@run_in_pyodide(packages=["frozenlist"])
def test_pop(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    assert _list.pop(0) == 1
    assert _list == [2]


@run_in_pyodide(packages=["frozenlist"])
def test_pop_default(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    assert _list.pop() == 2
    assert _list == [1]


@run_in_pyodide(packages=["frozenlist"])
def test_pop_frozen(selenium):
    import pytest
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list.pop()
    assert _list == [1, 2]


@run_in_pyodide(packages=["frozenlist"])
def test_append(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    _list.append(3)
    assert _list == [1, 2, 3]


@run_in_pyodide(packages=["frozenlist"])
def test_append_frozen(selenium):
    import pytest
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    _list.freeze()
    with pytest.raises(RuntimeError):
        _list.append(3)
    assert _list == [1, 2]


@run_in_pyodide(packages=["frozenlist"])
def test_hash(selenium):
    import pytest
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    with pytest.raises(RuntimeError):
        hash(_list)


@run_in_pyodide(packages=["frozenlist"])
def test_hash_frozen(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    _list.freeze()
    h = hash(_list)
    assert h == hash((1, 2))


@run_in_pyodide(packages=["frozenlist"])
def test_dict_key(selenium):
    import pytest
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    with pytest.raises(RuntimeError):
        {_list: "hello"}  # noqa: B018
    _list.freeze()
    {_list: "hello"}  # noqa: B018


@run_in_pyodide(packages=["frozenlist"])
def test_count(selenium):
    from frozenlist import FrozenList

    _list = FrozenList([1, 2])
    assert _list.count(1) == 1
