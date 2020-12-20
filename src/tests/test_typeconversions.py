import pytest
from selenium.common.exceptions import WebDriverException


def test_del_jsproxy(selenium):
    selenium.run_js(
        """
        class Point {
            constructor(x, y) {
                this.x = x;
                this.y = y;
            }
        }
        window.point = new Point(42, 43)
        """
    )
    selenium.run(
        """
        from js import point
        assert point.y == 43
        """
    )

    msg = "AttributeError: z"
    with pytest.raises(WebDriverException, match=msg):
        selenium.run("point.z")

    selenium.run("del point.y")
    msg = "AttributeError: y"
    with pytest.raises(WebDriverException, match=msg):
        selenium.run("point.y")
    assert selenium.run_js("return point.y;") is None
