from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["lxml"])
def test_lxml(selenium):
    from lxml import etree

    root = etree.XML(
        """<root>
        <TEXT1 class="myitem">one</TEXT1>
        <TEXT2 class="myitem">two</TEXT2>
        <TEXT3 class="myitem">three</TEXT3>
        <v-TEXT4 class="v-list">four</v-TEXT4>
    </root>"""
    )

    items = root.xpath("//*[@class='myitem']")
    assert ["one", "two", "three"] == [item.text for item in items]
