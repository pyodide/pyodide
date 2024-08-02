import pathlib

import pytest
from pytest_pyodide import run_in_pyodide

TEST_PATH = pathlib.Path(__file__).parent / "test_data"


def test_self_extend(selenium):
    @run_in_pyodide(packages=["pikepdf"])
    def run(selenium, fourpages):
        from pikepdf import Pdf

        with Pdf.open(fourpages) as pdf:
            pdf.pages.extend(pdf.pages)
            assert len(pdf.pages) == 8

    fourpages = (TEST_PATH / "fourpages.pdf").read_bytes()
    run(selenium, fourpages)


def test_one_based_pages(selenium):
    @run_in_pyodide(packages=["pikepdf"])
    def run(selenium, fourpages):
        from pikepdf import Pdf

        with Pdf.open(fourpages) as pdf:
            assert pdf.pages.p(1) == pdf.pages[0]
            assert pdf.pages.p(4) == pdf.pages[-1]
            with pytest.raises(IndexError):
                pdf.pages.p(5)
            with pytest.raises(IndexError):
                pdf.pages.p(0)
            with pytest.raises(IndexError):
                pdf.pages.p(-1)

    fourpages = (TEST_PATH / "fourpages.pdf").read_bytes()
    run(selenium, fourpages)


def test_rotate_and_save(selenium):
    @run_in_pyodide(packages=["pikepdf"])
    def run(selenium, fourpages):
        from pikepdf import Pdf

        with Pdf.open(fourpages) as pdf:
            for p in pdf.pages:
                p.rotate(90, True)
            pdf.save("output.pdf")

    fourpages = (TEST_PATH / "fourpages.pdf").read_bytes()
    run(selenium, fourpages)
