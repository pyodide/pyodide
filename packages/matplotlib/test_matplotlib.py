def test_matplotlib(selenium_standalone):
    selenium = selenium_standalone
    selenium.load_package("matplotlib")
    selenium.run("from matplotlib import pyplot as plt")
    selenium.run("plt.figure()")
    selenium.run("plt.plot([1,2,3])")
    selenium.run("plt.show()")


def test_svg(selenium):
    selenium.load_package("matplotlib")
    selenium.run("from matplotlib import pyplot as plt")
    selenium.run("plt.figure()")
    selenium.run("x = plt.plot([1,2,3])")
    selenium.run("import io")
    selenium.run("fd = io.BytesIO()")
    selenium.run("plt.savefig(fd, format='svg')")
    content = selenium.run("fd.getvalue().decode('utf8')")
    assert len(content) == 16283
    assert content.startswith("<?xml")


def test_pdf(selenium):
    selenium.load_package("matplotlib")
    selenium.run("from matplotlib import pyplot as plt")
    selenium.run("plt.figure()")
    selenium.run("x = plt.plot([1,2,3])")
    selenium.run("import io")
    selenium.run("fd = io.BytesIO()")
    selenium.run("plt.savefig(fd, format='pdf')")


def test_font_manager(selenium):
    """
    Comparing vendored fontlist.json version with the one built
    by font_manager.py.

    If you try to update Matplotlib and this test fails, try to
    update fontlist.json.
    """
    selenium.load_package("matplotlib")
    selenium.run(
        """
    from matplotlib import font_manager as fm
    import os
    import json

    # get fontlist form file
    fontist_file = os.path.join(os.path.dirname(fm.__file__), 'fontlist.json')
    with open(fontist_file) as f:
        fontlist_vendor = json.loads(f.read())

    # get fontlist from build
    fontlist_built = json.loads(json.dumps(fm.FontManager(), cls=fm._JSONEncoder))

    # reodering list to compare
    for list in ('afmlist', 'ttflist'):
        for fontlist in (fontlist_vendor, fontlist_built):
            fontlist[list].sort(key=lambda x: x['fname'])
    """
    )
    assert selenium.run("fontlist_built == fontlist_vendor")
