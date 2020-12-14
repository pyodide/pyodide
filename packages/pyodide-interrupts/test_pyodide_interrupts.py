def test_pyodide_interrupts(selenium):
    selenium.load_package("pyodide-interrupts")
    selenium.run("from pyodide_interrupts import check_interrupts")
    assert (
        selenium.run(
            "x = 0\n"
            "def callback():\n"
            "    global x\n"
            "    print('check')\n"
            "    x += 1\n"
            "with check_interrupts(callback, 10):\n"
            "    for i in range(50):\n"
            "        print(i, end=',')\n"
            "x"
        )
        == 11
    )
