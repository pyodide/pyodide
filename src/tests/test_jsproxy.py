# See also test_typeconversions, and test_python.


def test_jsproxy(selenium):
    assert (
        selenium.run(
            """
        from js import document
        el = document.createElement('div')
        document.body.appendChild(el)
        document.body.children.length"""
        )
        == 1
    )
    assert selenium.run("document.body.children[0].tagName") == "DIV"
    assert selenium.run("repr(document)") == "[object HTMLDocument]"
    selenium.run_js("window.square = function (x) { return x*x; }")
    assert selenium.run("from js import square\n" "square(2)") == 4
    assert selenium.run("from js import ImageData\n" "ImageData.new(64, 64)")
    assert selenium.run("from js import ImageData\n" "ImageData.typeof") == "function"
    selenium.run_js(
        """
        class Point {
          constructor(x, y) {
            this.x = x;
            this.y = y;
          }
        }
        window.TEST = new Point(42, 43);"""
    )
    assert (
        selenium.run(
            """
        from js import TEST
        del TEST.y
        hasattr(TEST, 'y')"""
        )
        is False
    )
    selenium.run_js(
        """
        class Point {
          constructor(x, y) {
            this.x = x;
            this.y = y;
          }
        }
        window.TEST = new Point(42, 43);"""
    )
    assert (
        selenium.run(
            """
        from js import TEST
        del TEST['y']
        'y' in TEST"""
        )
        is False
    )
    assert selenium.run(
        """
        from js import TEST
        TEST == TEST
        """
    )
    assert selenium.run(
        """
        from js import TEST
        TEST != 'foo'
        """
    )
    selenium.run_js(
        """
        window.TEST = {foo: 'bar', baz: 'bap'}
        """
    )
    assert (
        selenium.run(
            """
        from js import TEST
        dict(TEST) == {'foo': 'bar', 'baz': 'bap'}
        """
        )
        is True
    )
    assert (
        selenium.run(
            """
        from js import document
        el = document.createElement('div')
        len(dir(el)) >= 200 and 'appendChild' in dir(el)
        """
        )
        is True
    )


def test_jsproxy_iter(selenium):
    selenium.run_js(
        """
        function makeIterator(array) {
          var nextIndex = 0;
          return {
            next: function() {
              return nextIndex < array.length ?
                {value: array[nextIndex++], done: false} :
                {done: true};
            }
          };
        }
        window.ITER = makeIterator([1, 2, 3]);"""
    )
    assert selenium.run("from js import ITER\n" "list(ITER)") == [1, 2, 3]


def test_jsproxy_implicit_iter(selenium):
    selenium.run_js(
        """
        window.ITER = [1, 2, 3];"""
    )
    assert selenium.run("from js import ITER, Object\n" "list(ITER)") == [1, 2, 3]
    assert selenium.run("from js import ITER, Object\n" "list(ITER.values())") == [
        1,
        2,
        3,
    ]
    assert selenium.run(
        "from js import ITER, Object\n" "list(Object.values(ITER))"
    ) == [1, 2, 3]


def test_jsproxy_kwargs(selenium):
    selenium.run_js(
        """
        window.kwarg_function = ({ a = 1, b = 1 }) => {
            return a / b;
        };
        """
    )
    assert (
        selenium.run(
            """
        from js import kwarg_function
        kwarg_function(b = 2, a = 10)
        """
        )
        == 5
    )
