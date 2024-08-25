# Test suite for the crc32c Pyodide package, based on the original test suite:
# https://github.com/ICRAR/crc32c/blob/master/test/test_crc32c.py

import pytest
from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["crc32c"])
def test_zero(selenium):
    import crc32c

    assert crc32c.crc32c(b"") == 0


TEST_DATA = [
    ("Numbers1", b"123456789", 0xE3069283),
    ("Numbers2", b"23456789", 0xBFE92A83),
    ("Numbers3", b"1234567890", 0xF3DBD4FE),
    ("Phrase", b"The quick brown fox jumps over the lazy dog", 0x22620404),
    (
        "LongPhrase",
        (
            b"Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nunc omni virtuti vitium contrario nomine opponitur. "
            b"Conferam tecum, quam cuique verso rem subicias; Te ipsum, dignissimum maioribus tuis, voluptasne induxit, ut adolescentulus eriperes "
            b"P. Conclusum est enim contra Cyrenaicos satis acute, nihil ad Epicurum. Duo Reges: constructio interrete. Tum Torquatus: Prorsus, inquit, assentior;\n"
            b"Quando enim Socrates, qui parens philosophiae iure dici potest, quicquam tale fecit? Sed quid sentiat, non videtis. Haec quo modo conveniant, non "
            b"sane intellego. Sed ille, ut dixi, vitiose. Dic in quovis conventu te omnia facere, ne doleas. Quod si ita se habeat, non possit beatam praestare "
            b"vitam sapientia. Quis suae urbis conservatorem Codrum, quis Erechthei filias non maxime laudat? Primum divisit ineleganter; Huic mori optimum esse "
            b"propter desperationem sapientiae, illi propter spem vivere."
        ),
        0xFCB7575A,
    ),
]


@run_in_pyodide(packages=["crc32c"])
@pytest.mark.parametrize("name, val, checksum", TEST_DATA)
def test_all(selenium, name, val, checksum):
    import crc32c

    assert crc32c.crc32c(val) == checksum


@run_in_pyodide(packages=["crc32c"])
@pytest.mark.parametrize("name, val, checksum", TEST_DATA)
def test_piece_by_piece(selenium, name, val, checksum):
    # The initial CRC value
    c = 0

    # A generator that yields each byte of the input value
    # as a separate byte
    def as_individual_bytes(val):
        for byte in val:
            yield bytes([byte])

    for x in as_individual_bytes(val):
        import crc32c

        c = crc32c.crc32c(x, c)
    assert c == checksum
