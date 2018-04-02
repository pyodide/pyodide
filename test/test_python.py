import time


def test_init(selenium):
    assert 'Python initialization complete' in selenium.logs
    assert len(selenium.driver.window_handles) == 1


def test_webbrowser(selenium):
    selenium.run("import antigravity")
    time.sleep(2)
    assert len(selenium.driver.window_handles) == 2


def test_print(selenium):
    selenium.run("print('This should be logged')")
    assert 'This should be logged' in selenium.logs
