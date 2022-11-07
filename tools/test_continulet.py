import pytest
from pytest import raises

from pyodide._continulet import Continulet

continulet = Continulet


def test_new_empty():
    def empty_callback(c):
        never_called

    c = continulet(empty_callback)
    assert type(c) is continulet


def test_call_empty():
    def empty_callback(c1):
        assert c1 is c
        seen.append(1)
        return 42

    seen = []
    c = continulet(empty_callback)
    res = c.switch()
    assert res == 42
    assert seen == [1]


def test_no_double_init():
    def empty_callback(c1):
        never_called

    c = continulet(empty_callback)
    with raises(RuntimeError):
        c.__init__(empty_callback)


def test_no_init_after_started():
    def empty_callback(c1):
        with raises(RuntimeError):
            c1.__init__(empty_callback)
        return 42

    c = continulet(empty_callback)
    res = c.switch()
    assert res == 42


def test_no_init_after_finished():
    def empty_callback(c1):
        return 42

    c = continulet(empty_callback)
    res = c.switch()
    assert res == 42
    with raises(RuntimeError):
        c.__init__(empty_callback)


def test_propagate_exception():
    def empty_callback(c1):
        assert c1 is c
        seen.append(42)
        raise ValueError

    seen = []
    c = continulet(empty_callback)
    with raises(ValueError):
        c.switch()
    assert seen == [42]


def test_callback_with_arguments():
    def empty_callback(c1, *args, **kwds):
        seen.append(c1)
        seen.append(args)
        seen.append(kwds)
        return 42

    seen = []
    c = Continulet(empty_callback, 42, 43, foo=44, bar=45)
    res = c.switch()
    assert res == 42
    assert seen == [c, (42, 43), {"foo": 44, "bar": 45}]


def test_switch():
    def switchbackonce_callback(c):
        seen.append(1)
        print("seen once")
        res = c.switch("a")
        print("seen twice", res)
        assert res == "b"
        seen.append(3)
        return "c"

    seen = []
    c = continulet(switchbackonce_callback)
    seen.append(0)
    res = c.switch()
    print("outer res", res)
    assert res == "a"
    seen.append(2)
    res = c.switch("b")
    print("outer res2", res)
    assert res == "c"
    assert seen == [0, 1, 2, 3]


def test_initial_switch_must_give_None():
    def empty_callback(c):
        return "ok"

    c = continulet(empty_callback)
    res = c.switch(None)
    assert res == "ok"
    c = continulet(empty_callback)
    with raises(TypeError):
        c.switch("foo")  # "can't send non-None value"


def test_continuation_error():
    def empty_callback(c):
        return 42

    c = continulet(empty_callback)
    c.switch()
    with raises(RuntimeError, match="continulet already finished"):
        c.switch()


def test_go_depth2():
    def depth2(c):
        seen.append(3)
        return 4

    def depth1(c):
        seen.append(1)
        c2 = continulet(depth2)
        seen.append(2)
        res = c2.switch()
        seen.append(res)
        return 5

    seen = []
    c = continulet(depth1)
    seen.append(0)
    res = c.switch()
    seen.append(res)
    assert seen == [0, 1, 2, 3, 4, 5]


def test_exception_depth2():
    def depth2(c):
        seen.append(2)
        raise ValueError

    def depth1(c):
        seen.append(1)
        try:
            continulet(depth2).switch()
        except ValueError:
            seen.append(3)
        return 4

    seen = []
    c = continulet(depth1)
    res = c.switch()
    seen.append(res)
    assert seen == [1, 2, 3, 4]


def test_exception_with_switch():
    def depth1(c):
        seen.append(1)
        c.switch()
        seen.append(3)
        raise ValueError

    seen = []
    c = continulet(depth1)
    seen.append(0)
    c.switch()
    seen.append(2)
    with raises(ValueError):
        c.switch()
    assert seen == [0, 1, 2, 3]


def test_is_pending():
    def switchbackonce_callback(c):
        assert c.is_pending()
        res = c.switch("a")
        assert res == "b"
        assert c.is_pending()
        return "c"

    c = continulet.__new__(continulet)
    assert not c.is_pending()
    c.__init__(switchbackonce_callback)
    assert c.is_pending()
    res = c.switch()
    assert res == "a"
    assert c.is_pending()
    res = c.switch("b")
    assert res == "c"
    assert not c.is_pending()


def test_switch_alternate():
    def func_lower(c):
        res = c.switch("a")
        assert res == "b"
        res = c.switch("c")
        assert res == "d"
        return "e"

    def func_upper(c):
        res = c.switch("A")
        assert res == "B"
        res = c.switch("C")
        assert res == "D"
        return "E"

    c_lower = continulet(func_lower)
    c_upper = continulet(func_upper)
    res = c_lower.switch()
    assert res == "a"
    res = c_upper.switch()
    assert res == "A"
    res = c_lower.switch("b")
    assert res == "c"
    res = c_upper.switch("B")
    assert res == "C"
    res = c_lower.switch("d")
    assert res == "e"
    res = c_upper.switch("D")
    assert res == "E"


def test_switch_not_initialized():

    c0 = continulet.__new__(continulet)
    res = c0.switch()
    assert res is None
    res = c0.switch(123)
    assert res == 123
    with raises(ValueError):
        c0.throw(ValueError("oops!"))


def test_exception_with_switch_depth2():
    def depth2(c):
        seen.append(4)
        c.switch()
        seen.append(6)
        raise ValueError

    def depth1(c):
        seen.append(1)
        c.switch()
        seen.append(3)
        c2 = continulet(depth2)
        c2.switch()
        seen.append(5)
        with raises(ValueError):
            c2.switch()
        assert not c2.is_pending()
        seen.append(7)
        assert c.is_pending()
        raise KeyError

    seen = []
    c = continulet(depth1)
    c.switch()
    seen.append(2)
    with raises(KeyError):
        c.switch()
    assert not c.is_pending()
    assert seen == [1, 2, 3, 4, 5, 6, 7]


def test_random_switching():

    seen = []

    def t1(c1):
        seen.append(3)
        res = c1.switch()
        seen.append(6)
        return res

    def s1(c1, n):
        seen.append(2)
        assert n == 123
        c2 = t1(c1)
        seen.append(7)
        res = c1.switch("a") + 1
        seen.append(10)
        return res

    def s2(c2, c1):
        seen.append(5)
        res = c1.switch(c2)
        seen.append(8)
        assert res == "a"
        res = c2.switch("b") + 2
        seen.append(12)
        return res

    def f():
        seen.append(1)
        c1 = continulet(s1, 123)
        c2 = continulet(s2, c1)
        c1.switch()
        seen.append(4)
        res = c2.switch()
        seen.append(9)
        assert res == "b"
        res = c1.switch(1000)
        seen.append(11)
        assert res == 1001
        res = c2.switch(2000)
        seen.append(13)
        return res

    res = f()
    assert res == 2002
    assert seen == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]


@pytest.mark.skip("Confusing!")
def test_f_back():
    import inspect
    import sys

    n = len(inspect.stack()) - 1

    def stack():
        res = [x.function for x in inspect.stack()[-n - 1 : 0 : -1]]
        print(res)
        return res

    def bar(c):
        assert stack() == ["bar", "foo", "test_f_back"]
        c.switch(sys._getframe(0))
        c.switch(sys._getframe(0).f_back)
        c.switch(sys._getframe(1))

        assert stack() == ["bar", "foo", "main", "test_f_back"]
        c.switch(sys._getframe(1).f_back)

        assert stack() == ["bar", "foo", "main2", "test_f_back"]
        assert sys._getframe(2) is f3_foo.f_back
        c.switch(sys._getframe(2))

    def foo(c):
        bar(c)

    print(stack())
    assert stack() == ["test_f_back"]
    c = continulet(foo)
    f1_bar = c.switch()
    assert f1_bar.f_code.co_name == "bar"
    f2_foo = c.switch()
    assert f2_foo.f_code.co_name == "foo"
    f3_foo = c.switch()
    assert f3_foo is f2_foo
    assert f1_bar.f_back is f3_foo

    def main():
        f4_main = c.switch()
        assert f4_main.f_code.co_name == "main"
        assert f3_foo.f_back is f1_bar  # not running, so a loop
        assert stack() == ["main", "test_f_back"]
        assert stack(f1_bar) == ["bar", "foo", "..."]

    def main2():
        f5_main2 = c.switch()
        assert f5_main2.f_code.co_name == "main2"
        assert f3_foo.f_back is f1_bar  # not running, so a loop
        assert stack(f1_bar) == ["bar", "foo", "..."]

    main()
    main2()
    res = c.switch()
    assert res is None
    assert f3_foo.f_back is None


def test_traceback_is_complete():
    import sys

    def g():
        raise KeyError

    def f(c):
        g()

    def do(c):
        c.switch()

    c = continulet(f)
    try:
        do(c)
    except KeyError:
        tb = sys.exc_info()[2]
    else:
        raise AssertionError("should have raised!")

    import traceback

    traceback.print_tb(tb)
    assert tb.tb_next.tb_frame.f_code.co_name == "do"
    assert tb.tb_next.tb_next.tb_frame.f_code.co_name == "switch"
    assert tb.tb_next.tb_next.tb_next.tb_frame.f_code.co_name == "f"
    assert tb.tb_next.tb_next.tb_next.tb_next.tb_frame.f_code.co_name == "g"
    assert tb.tb_next.tb_next.tb_next.tb_next.tb_next is None


def test_switch2_simple():
    def f1(c1):
        res = c1.switch("started 1")
        assert res == "a"
        print("=============", "f1-1", res)
        res = c1.switch("b", to=c2)
        print("=============", "f1-2", res)
        assert res == "c"
        return 42

    def f2(c2):
        res = c2.switch("started 2")
        assert res == "b"
        print("=============", "f2-1")
        res = c2.switch("c", to=c1)
        not_reachable

    c1 = continulet(f1)
    c2 = continulet(f2)
    res = c1.switch()
    assert res == "started 1"
    res = c2.switch()
    assert res == "started 2"
    res = c1.switch("a")
    assert res == 42


def test_switch2_pingpong():
    def f1(c1):
        res = c1.switch("started 1")
        assert res == "go"
        for i in range(10):
            res = c1.switch(i, to=c2)
            assert res == 100 + i
        return 42

    def f2(c2):
        res = c2.switch("started 2")
        for i in range(10):
            assert res == i
            res = c2.switch(100 + i, to=c1)
        not_reachable

    c1 = continulet(f1)
    c2 = continulet(f2)
    res = c1.switch()
    assert res == "started 1"
    res = c2.switch()
    assert res == "started 2"
    res = c1.switch("go")
    assert res == 42


def test_switch2_more_complex():
    def f1(c1):
        print("f1-1")
        res = c1.switch(to=c2)
        print("f1-2", res)
        assert res == "a"
        res = c1.switch("b", to=c2)
        print("f1-3", res)
        assert res == "c"
        return 41

    def f2(c2):
        print("f2-1")
        res = c2.switch("a", to=c1)
        print("f2-2", res)
        assert res == "b"
        return 42

    c1 = continulet(f1)
    c2 = continulet(f2)
    print("c1 switch")
    res = c1.switch()
    print("res??\n\n", res)
    print("???")
    assert res == 42
    assert not c2.is_pending()  # finished by returning 42
    print("c1 switch c")
    res = c1.switch("c")
    assert res == 41


def test_switch2_no_op():
    def f1(c1):
        res = c1.switch("a", to=c1)
        assert res == "a"
        return 42

    c1 = continulet(f1)
    res = c1.switch()
    assert res == 42


def test_switch2_immediately_away():
    def f1(c1):
        print("in f1")
        return "m"

    def f2(c2):
        res = c2.switch("z")
        print("got there!")
        assert res == "a"
        return None

    c1 = continulet(f1)
    c2 = continulet(f2)
    res = c2.switch()
    assert res == "z"
    assert c1.is_pending()
    assert c2.is_pending()
    print("calling!")
    res = c1.switch("a", to=c2)
    print("back")
    assert res == "m"


def test_switch2_immediately_away_corner_case():
    def f1(c1):
        this_is_never_seen

    def f2(c2):
        res = c2.switch("z")
        assert res is None
        return "b"  # this goes back into the caller, which is f1,
        # but f1 didn't start yet, so a None-value value
        # has nowhere to go to...

    c1 = continulet(f1)
    c2 = continulet(f2)
    res = c2.switch()
    assert res == "z"
    with raises(TypeError):
        c1.switch(to=c2)  # "can't send non-None value"


def test_switch2_not_initialized():

    c0 = continulet.__new__(continulet)
    c0bis = continulet.__new__(continulet)
    res = c0.switch(123, to=c0)
    assert res == 123
    res = c0.switch(123, to=c0bis)
    assert res == 123
    with raises(ValueError):
        c0.throw(ValueError, to=c0)
    with raises(ValueError):
        c0.throw(ValueError, to=c0bis)

    def f1(c1):
        c1.switch("a")
        with raises(ValueError):
            c1.switch("b")
        with raises(KeyError):
            c1.switch("c")
        return "d"

    c1 = continulet(f1)
    res = c0.switch(to=c1)
    assert res == "a"
    res = c1.switch(to=c0)
    assert res == "b"
    res = c1.throw(ValueError, to=c0)
    assert res == "c"
    res = c0.throw(KeyError("oops"), to=c1)
    assert res == "d"


def test_switch2_already_finished():
    def f1(c1):
        not_reachable

    def empty_callback(c):
        return 42

    c1 = continulet(f1)
    c2 = continulet(empty_callback)
    c2.switch()
    with raises(RuntimeError, match="continulet already finished"):
        c1.switch(to=c2)


def test_throw1():
    def f1(c1):
        raise RuntimeError("oops")

    c1 = continulet(f1)
    with pytest.raises(RuntimeError):
        c1.switch()


def test_throw2():
    def f1(c1):
        c1.switch()
        raise RuntimeError("oops")

    c1 = continulet(f1)
    c1.switch()
    with pytest.raises(RuntimeError):
        c1.switch()


def test_throw3():
    def f1(c1):
        c1.switch()

    c1 = continulet(f1)
    c1.switch()
    with pytest.raises(RuntimeError):
        c1.throw(RuntimeError("oops"))


def test_throw_to_starting():
    def f1(c1):
        not_reached

    c1 = continulet(f1)
    with raises(IndexError):
        c1.throw(IndexError)


def test_throw2_simple():
    def f1(c1):
        not_reached

    def f2(c2):
        try:
            c2.switch("ready")
        except IndexError:
            raise ValueError

    c1 = continulet(f1)
    c2 = continulet(f2)
    res = c2.switch()
    assert res == "ready"
    assert c1.is_pending()
    assert c2.is_pending()
    with pytest.raises(ValueError):
        c1.throw(IndexError, to=c2)
    assert not c1.is_pending()
    assert not c2.is_pending()


def test_throw2_no_op():
    def f1(c1):
        with pytest.raises(ValueError):
            c1.throw(ValueError, to=c1)
        return "ok"

    c1 = continulet(f1)
    res = c1.switch()
    assert res == "ok"


def test_bug_finish_with_already_finished_stacklet():
    # make an already-finished continulet
    c1 = continulet(lambda x: x)
    c1.switch()
    # make another continulet
    c2 = continulet(lambda x: x)
    # this switch is forbidden, because it causes a crash when c2 finishes
    with raises(RuntimeError):
        c1.switch(to=c2)


def test_exc_info_doesnt_follow_continuations():
    import sys

    def f1(c1):
        return sys.exc_info()

    c1 = continulet(f1)
    try:
        1 // 0
    except ZeroDivisionError:
        got = c1.switch()
    assert got == (None, None, None)


def test_bug_issue1984():
    c1 = continulet.__new__(continulet)
    c2 = continulet(lambda g: None)

    continulet.switch(c1, to=c2)
    with raises(RuntimeError):
        continulet.switch(c1, to=c2)


if __name__ == "__main__":
    test_throw2()
