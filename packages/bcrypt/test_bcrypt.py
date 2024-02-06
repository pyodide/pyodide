import pytest
from pytest_pyodide import run_in_pyodide

_test_vectors = [
    (
        b"Kk4DQuMMfZL9o",
        b"$2b$04$cVWp4XaNU8a4v1uMRum2SO",
        b"$2b$04$cVWp4XaNU8a4v1uMRum2SO026BWLIoQMD/TXg5uZV.0P.uO8m3YEm",
    ),
    (
        b"9IeRXmnGxMYbs",
        b"$2b$04$pQ7gRO7e6wx/936oXhNjrO",
        b"$2b$04$pQ7gRO7e6wx/936oXhNjrOUNOHL1D0h1N2IDbJZYs.1ppzSof6SPy",
    ),
    (
        b"xVQVbwa1S0M8r",
        b"$2b$04$SQe9knOzepOVKoYXo9xTte",
        b"$2b$04$SQe9knOzepOVKoYXo9xTteNYr6MBwVz4tpriJVe3PNgYufGIsgKcW",
    ),
    (
        b"Zfgr26LWd22Za",
        b"$2b$04$eH8zX.q5Q.j2hO1NkVYJQO",
        b"$2b$04$eH8zX.q5Q.j2hO1NkVYJQOM6KxntS/ow3.YzVmFrE4t//CoF4fvne",
    ),
    (
        b"Tg4daC27epFBE",
        b"$2b$04$ahiTdwRXpUG2JLRcIznxc.",
        b"$2b$04$ahiTdwRXpUG2JLRcIznxc.s1.ydaPGD372bsGs8NqyYjLY1inG5n2",
    ),
    (
        b"xhQPMmwh5ALzW",
        b"$2b$04$nQn78dV0hGHf5wUBe0zOFu",
        b"$2b$04$nQn78dV0hGHf5wUBe0zOFu8n07ZbWWOKoGasZKRspZxtt.vBRNMIy",
    ),
    (
        b"59je8h5Gj71tg",
        b"$2b$04$cvXudZ5ugTg95W.rOjMITu",
        b"$2b$04$cvXudZ5ugTg95W.rOjMITuM1jC0piCl3zF5cmGhzCibHZrNHkmckG",
    ),
    (
        b"wT4fHJa2N9WSW",
        b"$2b$04$YYjtiq4Uh88yUsExO0RNTu",
        b"$2b$04$YYjtiq4Uh88yUsExO0RNTuEJ.tZlsONac16A8OcLHleWFjVawfGvO",
    ),
    (
        b"uSgFRnQdOgm4S",
        b"$2b$04$WLTjgY/pZSyqX/fbMbJzf.",
        b"$2b$04$WLTjgY/pZSyqX/fbMbJzf.qxCeTMQOzgL.CimRjMHtMxd/VGKojMu",
    ),
    (
        b"tEPtJZXur16Vg",
        b"$2b$04$2moPs/x/wnCfeQ5pCheMcu",
        b"$2b$04$2moPs/x/wnCfeQ5pCheMcuSJQ/KYjOZG780UjA/SiR.KsYWNrC7SG",
    ),
    (
        b"vvho8C6nlVf9K",
        b"$2b$04$HrEYC/AQ2HS77G78cQDZQ.",
        b"$2b$04$HrEYC/AQ2HS77G78cQDZQ.r44WGcruKw03KHlnp71yVQEwpsi3xl2",
    ),
    (
        b"5auCCY9by0Ruf",
        b"$2b$04$vVYgSTfB8KVbmhbZE/k3R.",
        b"$2b$04$vVYgSTfB8KVbmhbZE/k3R.ux9A0lJUM4CZwCkHI9fifke2.rTF7MG",
    ),
    (
        b"GtTkR6qn2QOZW",
        b"$2b$04$JfoNrR8.doieoI8..F.C1O",
        b"$2b$04$JfoNrR8.doieoI8..F.C1OQgwE3uTeuardy6lw0AjALUzOARoyf2m",
    ),
    (
        b"zKo8vdFSnjX0f",
        b"$2b$04$HP3I0PUs7KBEzMBNFw7o3O",
        b"$2b$04$HP3I0PUs7KBEzMBNFw7o3O7f/uxaZU7aaDot1quHMgB2yrwBXsgyy",
    ),
    (
        b"I9VfYlacJiwiK",
        b"$2b$04$xnFVhJsTzsFBTeP3PpgbMe",
        b"$2b$04$xnFVhJsTzsFBTeP3PpgbMeMREb6rdKV9faW54Sx.yg9plf4jY8qT6",
    ),
    (
        b"VFPO7YXnHQbQO",
        b"$2b$04$WQp9.igoLqVr6Qk70mz6xu",
        b"$2b$04$WQp9.igoLqVr6Qk70mz6xuRxE0RttVXXdukpR9N54x17ecad34ZF6",
    ),
    (
        b"VDx5BdxfxstYk",
        b"$2b$04$xgZtlonpAHSU/njOCdKztO",
        b"$2b$04$xgZtlonpAHSU/njOCdKztOPuPFzCNVpB4LGicO4/OGgHv.uKHkwsS",
    ),
    (
        b"dEe6XfVGrrfSH",
        b"$2b$04$2Siw3Nv3Q/gTOIPetAyPr.",
        b"$2b$04$2Siw3Nv3Q/gTOIPetAyPr.GNj3aO0lb1E5E9UumYGKjP9BYqlNWJe",
    ),
    (
        b"cTT0EAFdwJiLn",
        b"$2b$04$7/Qj7Kd8BcSahPO4khB8me",
        b"$2b$04$7/Qj7Kd8BcSahPO4khB8me4ssDJCW3r4OGYqPF87jxtrSyPj5cS5m",
    ),
    (
        b"J8eHUDuxBB520",
        b"$2b$04$VvlCUKbTMjaxaYJ.k5juoe",
        b"$2b$04$VvlCUKbTMjaxaYJ.k5juoecpG/7IzcH1AkmqKi.lIZMVIOLClWAk.",
    ),
    (
        b"U*U",
        b"$2a$05$CCCCCCCCCCCCCCCCCCCCC.",
        b"$2a$05$CCCCCCCCCCCCCCCCCCCCC.E5YPO9kmyuRGyh0XouQYb4YMJKvyOeW",
    ),
    (
        b"U*U*",
        b"$2a$05$CCCCCCCCCCCCCCCCCCCCC.",
        b"$2a$05$CCCCCCCCCCCCCCCCCCCCC.VGOzA784oUp/Z0DY336zx7pLYAy0lwK",
    ),
    (
        b"U*U*U",
        b"$2a$05$XXXXXXXXXXXXXXXXXXXXXO",
        b"$2a$05$XXXXXXXXXXXXXXXXXXXXXOAcXxm9kjPGEMsLznoKqmqw7tc8WCx4a",
    ),
    (
        b"0123456789abcdefghijklmnopqrstuvwxyz"
        b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        b"chars after 72 are ignored",
        b"$2a$05$abcdefghijklmnopqrstuu",
        b"$2a$05$abcdefghijklmnopqrstuu5s2v8.iXieOjg/.AySBTTZIIVFJeBui",
    ),
    (
        b"\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa"
        b"\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa"
        b"\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa"
        b"\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa"
        b"\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa"
        b"\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa\xaa"
        b"chars after 72 are ignored as usual",
        b"$2a$05$/OK.fbVrR/bpIqNJ5ianF.",
        b"$2a$05$/OK.fbVrR/bpIqNJ5ianF.swQOIzjOiJ9GHEPuhEkvqrUyvWhEMx6",
    ),
    (
        b"\xa3",
        b"$2a$05$/OK.fbVrR/bpIqNJ5ianF.",
        b"$2a$05$/OK.fbVrR/bpIqNJ5ianF.Sa7shbm4.OzKpvFnX1pQLmQW96oUlCq",
    ),
    (
        b"}>\xb3\xfe\xf1\x8b\xa0\xe6(\xa2Lzq\xc3P\x7f\xcc\xc8b{\xf9\x14\xf6"
        b"\xf6`\x81G5\xec\x1d\x87\x10\xbf\xa7\xe1}I7 \x96\xdfc\xf2\xbf\xb3Vh"
        b"\xdfM\x88q\xf7\xff\x1b\x82~z\x13\xdd\xe9\x84\x00\xdd4",
        b"$2b$10$keO.ZZs22YtygVF6BLfhGO",
        b"$2b$10$keO.ZZs22YtygVF6BLfhGOI/JjshJYPp8DZsUtym6mJV2Eha2Hdd.",
    ),
    (
        b"g7\r\x01\xf3\xd4\xd0\xa9JB^\x18\x007P\xb2N\xc7\x1c\xee\x87&\x83C"
        b"\x8b\xe8\x18\xc5>\x86\x14/\xd6\xcc\x1cJ\xde\xd7ix\xeb\xdeO\xef"
        b"\xe1i\xac\xcb\x03\x96v1' \xd6@.m\xa5!\xa0\xef\xc0(",
        b"$2a$04$tecY.9ylRInW/rAAzXCXPO",
        b"$2a$04$tecY.9ylRInW/rAAzXCXPOOlyYeCNzmNTzPDNSIFztFMKbvs/s5XG",
    ),
]

_2y_test_vectors = [
    (
        b"\xa3",
        b"$2y$05$/OK.fbVrR/bpIqNJ5ianF.Sa7shbm4.OzKpvFnX1pQLmQW96oUlCq",
        b"$2y$05$/OK.fbVrR/bpIqNJ5ianF.Sa7shbm4.OzKpvFnX1pQLmQW96oUlCq",
    ),
    (
        b"\xff\xff\xa3",
        b"$2y$05$/OK.fbVrR/bpIqNJ5ianF.CE5elHaaO4EbggVDjb8P19RukzXSM3e",
        b"$2y$05$/OK.fbVrR/bpIqNJ5ianF.CE5elHaaO4EbggVDjb8P19RukzXSM3e",
    ),
]


@run_in_pyodide(packages=["bcrypt"])
def test_gensalt_basic(selenium, monkeypatch):
    import bcrypt

    salt = bcrypt.gensalt()
    assert salt.startswith(b"$2b$12$")


@pytest.mark.parametrize(
    ("rounds", "expected_prefix"),
    [
        (4, b"$2b$04$"),
        (5, b"$2b$05$"),
        (6, b"$2b$06$"),
        (7, b"$2b$07$"),
        (8, b"$2b$08$"),
        (9, b"$2b$09$"),
        (10, b"$2b$10$"),
        (11, b"$2b$11$"),
        (12, b"$2b$12$"),
        (13, b"$2b$13$"),
        (14, b"$2b$14$"),
        (15, b"$2b$15$"),
        (16, b"$2b$16$"),
        (17, b"$2b$17$"),
        (18, b"$2b$18$"),
        (19, b"$2b$19$"),
        (20, b"$2b$20$"),
        (21, b"$2b$21$"),
        (22, b"$2b$22$"),
        (23, b"$2b$23$"),
        (24, b"$2b$24$"),
    ],
)
@run_in_pyodide(packages=["bcrypt"])
def test_gensalt_rounds_valid(selenium, rounds, expected_prefix):
    import bcrypt

    salt = bcrypt.gensalt(rounds)

    assert salt.startswith(expected_prefix)


@pytest.mark.parametrize("rounds", list(range(1, 4)))
@run_in_pyodide(packages=["bcrypt"])
def test_gensalt_rounds_invalid(selenium, rounds):
    import bcrypt
    import pytest

    with pytest.raises(ValueError):
        bcrypt.gensalt(rounds)


@run_in_pyodide(packages=["bcrypt"])
def test_gensalt_bad_prefix(selenium):
    import bcrypt
    import pytest

    with pytest.raises(ValueError):
        bcrypt.gensalt(prefix=b"bad")


@run_in_pyodide(packages=["bcrypt"])
def test_gensalt_2a_prefix(selenium):
    import bcrypt

    salt = bcrypt.gensalt(prefix=b"2a")
    assert salt.startswith(b"$2a$12$")


@pytest.mark.parametrize(("password", "salt", "hashed"), _test_vectors)
@run_in_pyodide(packages=["bcrypt"])
def test_hashpw_new(selenium, password, salt, hashed):
    import bcrypt

    assert bcrypt.hashpw(password, salt) == hashed


@pytest.mark.parametrize(("password", "salt", "hashed"), _test_vectors)
@run_in_pyodide(packages=["bcrypt"])
def test_checkpw(selenium, password, salt, hashed):
    import bcrypt

    assert bcrypt.checkpw(password, hashed) is True


@pytest.mark.parametrize(("password", "salt", "hashed"), _test_vectors)
@run_in_pyodide(packages=["bcrypt"])
def test_hashpw_existing(selenium, password, salt, hashed):
    import bcrypt

    assert bcrypt.hashpw(password, hashed) == hashed


@pytest.mark.parametrize(("password", "hashed", "expected"), _2y_test_vectors)
@run_in_pyodide(packages=["bcrypt"])
def test_hashpw_2y_prefix(selenium, password, hashed, expected):
    import bcrypt

    assert bcrypt.hashpw(password, hashed) == expected


@pytest.mark.parametrize(("password", "hashed", "expected"), _2y_test_vectors)
@run_in_pyodide(packages=["bcrypt"])
def test_checkpw_2y_prefix(selenium, password, hashed, expected):
    import bcrypt

    assert bcrypt.checkpw(password, hashed) is True


@run_in_pyodide(packages=["bcrypt"])
def test_hashpw_invalid(selenium):
    import bcrypt
    import pytest

    with pytest.raises(ValueError):
        bcrypt.hashpw(b"password", b"$2z$04$cVWp4XaNU8a4v1uMRum2SO")


@run_in_pyodide(packages=["bcrypt"])
def test_checkpw_wrong_password(selenium):
    import bcrypt

    assert (
        bcrypt.checkpw(
            b"badpass",
            b"$2b$04$2Siw3Nv3Q/gTOIPetAyPr.GNj3aO0lb1E5E9UumYGKjP9BYqlNWJe",
        )
        is False
    )


@run_in_pyodide(packages=["bcrypt"])
def test_checkpw_bad_salt(selenium):
    import bcrypt
    import pytest

    with pytest.raises(ValueError):
        bcrypt.checkpw(
            b"badpass",
            b"$2b$04$?Siw3Nv3Q/gTOIPetAyPr.GNj3aO0lb1E5E9UumYGKjP9BYqlNWJe",
        )
    with pytest.raises(ValueError):
        bcrypt.checkpw(
            b"password",
            b"$2b$3$mdEQPMOtfPX.WGZNXgF66OhmBlOGKEd66SQ7DyJPGucYYmvTJYviy",
        )


@run_in_pyodide(packages=["bcrypt"])
def test_checkpw_str_password(selenium):
    import bcrypt
    import pytest

    with pytest.raises(TypeError):
        bcrypt.checkpw("password", b"$2b$04$cVWp4XaNU8a4v1uMRum2SO")


@run_in_pyodide(packages=["bcrypt"])
def test_checkpw_str_salt(selenium):
    import bcrypt
    import pytest

    with pytest.raises(TypeError):
        bcrypt.checkpw(b"password", "$2b$04$cVWp4XaNU8a4v1uMRum2SO")


@run_in_pyodide(packages=["bcrypt"])
def test_hashpw_str_password(selenium):
    import bcrypt
    import pytest

    with pytest.raises(TypeError):
        bcrypt.hashpw("password", b"$2b$04$cVWp4XaNU8a4v1uMRum2SO")


@run_in_pyodide(packages=["bcrypt"])
def test_hashpw_str_salt(selenium):
    import bcrypt
    import pytest

    with pytest.raises(TypeError):
        bcrypt.hashpw(b"password", "$2b$04$cVWp4XaNU8a4v1uMRum2SO")


@run_in_pyodide(packages=["bcrypt"])
def test_checkpw_nul_byte(selenium):
    import bcrypt
    import pytest

    bcrypt.checkpw(
        b"abc\0def",
        b"$2b$04$2Siw3Nv3Q/gTOIPetAyPr.GNj3aO0lb1E5E9UumYGKjP9BYqlNWJe",
    )

    with pytest.raises(ValueError):
        bcrypt.checkpw(
            b"abcdef",
            b"$2b$04$2S\0w3Nv3Q/gTOIPetAyPr.GNj3aO0lb1E5E9UumYGKjP9BYqlNWJe",
        )


@run_in_pyodide(packages=["bcrypt"])
def test_hashpw_nul_byte(selenium):
    import bcrypt

    salt = bcrypt.gensalt(4)
    hashed = bcrypt.hashpw(b"abc\0def", salt)
    assert bcrypt.checkpw(b"abc\0def", hashed)
    # assert that we are sensitive to changes in the password after the first
    # null byte:
    assert not bcrypt.checkpw(b"abc\0deg", hashed)
    assert not bcrypt.checkpw(b"abc\0def\0", hashed)
    assert not bcrypt.checkpw(b"abc\0def\0\0", hashed)


@run_in_pyodide(packages=["bcrypt"])
def test_checkpw_extra_data(selenium):
    import bcrypt

    salt = bcrypt.gensalt(4)
    hashed = bcrypt.hashpw(b"abc", salt)

    assert bcrypt.checkpw(b"abc", hashed)
    assert bcrypt.checkpw(b"abc", hashed + b"extra") is False
    assert bcrypt.checkpw(b"abc", hashed[:-10]) is False


@pytest.mark.parametrize(
    ("rounds", "password", "salt", "expected"),
    [
        [
            4,
            b"password",
            b"salt",
            b"\x5b\xbf\x0c\xc2\x93\x58\x7f\x1c\x36\x35\x55\x5c\x27\x79\x65\x98"
            b"\xd4\x7e\x57\x90\x71\xbf\x42\x7e\x9d\x8f\xbe\x84\x2a\xba\x34\xd9",
        ],
        [
            4,
            b"password",
            b"\x00",
            b"\xc1\x2b\x56\x62\x35\xee\xe0\x4c\x21\x25\x98\x97\x0a\x57\x9a\x67",
        ],
        [
            4,
            b"\x00",
            b"salt",
            b"\x60\x51\xbe\x18\xc2\xf4\xf8\x2c\xbf\x0e\xfe\xe5\x47\x1b\x4b\xb9",
        ],
        [
            # nul bytes in password and string
            4,
            b"password\x00",
            b"salt\x00",
            b"\x74\x10\xe4\x4c\xf4\xfa\x07\xbf\xaa\xc8\xa9\x28\xb1\x72\x7f\xac"
            b"\x00\x13\x75\xe7\xbf\x73\x84\x37\x0f\x48\xef\xd1\x21\x74\x30\x50",
        ],
        [
            4,
            b"pass\x00wor",
            b"sa\0l",
            b"\xc2\xbf\xfd\x9d\xb3\x8f\x65\x69\xef\xef\x43\x72\xf4\xde\x83\xc0",
        ],
        [
            4,
            b"pass\x00word",
            b"sa\0lt",
            b"\x4b\xa4\xac\x39\x25\xc0\xe8\xd7\xf0\xcd\xb6\xbb\x16\x84\xa5\x6f",
        ],
        [
            # bigger key
            8,
            b"password",
            b"salt",
            b"\xe1\x36\x7e\xc5\x15\x1a\x33\xfa\xac\x4c\xc1\xc1\x44\xcd\x23\xfa"
            b"\x15\xd5\x54\x84\x93\xec\xc9\x9b\x9b\x5d\x9c\x0d\x3b\x27\xbe\xc7"
            b"\x62\x27\xea\x66\x08\x8b\x84\x9b\x20\xab\x7a\xa4\x78\x01\x02\x46"
            b"\xe7\x4b\xba\x51\x72\x3f\xef\xa9\xf9\x47\x4d\x65\x08\x84\x5e\x8d",
        ],
        [
            # more rounds
            42,
            b"password",
            b"salt",
            b"\x83\x3c\xf0\xdc\xf5\x6d\xb6\x56\x08\xe8\xf0\xdc\x0c\xe8\x82\xbd",
        ],
        [
            # longer password
            8,
            b"Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do"
            b" eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut "
            b"enim ad minim veniam, quis nostrud exercitation ullamco laboris "
            b"nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor "
            b"in reprehenderit in voluptate velit esse cillum dolore eu fugiat"
            b" nulla pariatur. Excepteur sint occaecat cupidatat non proident,"
            b" sunt in culpa qui officia deserunt mollit anim id est laborum.",
            b"salis\x00",
            b"\x10\x97\x8b\x07\x25\x3d\xf5\x7f\x71\xa1\x62\xeb\x0e\x8a\xd3\x0a",
        ],
        [
            # "unicode"
            8,
            b"\x0d\xb3\xac\x94\xb3\xee\x53\x28\x4f\x4a\x22\x89\x3b\x3c\x24\xae",
            b"\x3a\x62\xf0\xf0\xdb\xce\xf8\x23\xcf\xcc\x85\x48\x56\xea\x10\x28",
            b"\x20\x44\x38\x17\x5e\xee\x7c\xe1\x36\xc9\x1b\x49\xa6\x79\x23\xff",
        ],
        [
            # very large key
            8,
            b"\x0d\xb3\xac\x94\xb3\xee\x53\x28\x4f\x4a\x22\x89\x3b\x3c\x24\xae",
            b"\x3a\x62\xf0\xf0\xdb\xce\xf8\x23\xcf\xcc\x85\x48\x56\xea\x10\x28",
            b"\x20\x54\xb9\xff\xf3\x4e\x37\x21\x44\x03\x34\x74\x68\x28\xe9\xed"
            b"\x38\xde\x4b\x72\xe0\xa6\x9a\xdc\x17\x0a\x13\xb5\xe8\xd6\x46\x38"
            b"\x5e\xa4\x03\x4a\xe6\xd2\x66\x00\xee\x23\x32\xc5\xed\x40\xad\x55"
            b"\x7c\x86\xe3\x40\x3f\xbb\x30\xe4\xe1\xdc\x1a\xe0\x6b\x99\xa0\x71"
            b"\x36\x8f\x51\x8d\x2c\x42\x66\x51\xc9\xe7\xe4\x37\xfd\x6c\x91\x5b"
            b"\x1b\xbf\xc3\xa4\xce\xa7\x14\x91\x49\x0e\xa7\xaf\xb7\xdd\x02\x90"
            b"\xa6\x78\xa4\xf4\x41\x12\x8d\xb1\x79\x2e\xab\x27\x76\xb2\x1e\xb4"
            b"\x23\x8e\x07\x15\xad\xd4\x12\x7d\xff\x44\xe4\xb3\xe4\xcc\x4c\x4f"
            b"\x99\x70\x08\x3f\x3f\x74\xbd\x69\x88\x73\xfd\xf6\x48\x84\x4f\x75"
            b"\xc9\xbf\x7f\x9e\x0c\x4d\x9e\x5d\x89\xa7\x78\x39\x97\x49\x29\x66"
            b"\x61\x67\x07\x61\x1c\xb9\x01\xde\x31\xa1\x97\x26\xb6\xe0\x8c\x3a"
            b"\x80\x01\x66\x1f\x2d\x5c\x9d\xcc\x33\xb4\xaa\x07\x2f\x90\xdd\x0b"
            b"\x3f\x54\x8d\x5e\xeb\xa4\x21\x13\x97\xe2\xfb\x06\x2e\x52\x6e\x1d"
            b"\x68\xf4\x6a\x4c\xe2\x56\x18\x5b\x4b\xad\xc2\x68\x5f\xbe\x78\xe1"
            b"\xc7\x65\x7b\x59\xf8\x3a\xb9\xab\x80\xcf\x93\x18\xd6\xad\xd1\xf5"
            b"\x93\x3f\x12\xd6\xf3\x61\x82\xc8\xe8\x11\x5f\x68\x03\x0a\x12\x44",
        ],
        [
            # UTF-8 Greek characters "odysseus" / "telemachos"
            8,
            b"\xe1\xbd\x88\xce\xb4\xcf\x85\xcf\x83\xcf\x83\xce\xb5\xcf\x8d\xcf\x82",
            b"\xce\xa4\xce\xb7\xce\xbb\xce\xad\xce\xbc\xce\xb1\xcf\x87\xce\xbf"
            b"\xcf\x82",
            b"\x43\x66\x6c\x9b\x09\xef\x33\xed\x8c\x27\xe8\xe8\xf3\xe2\xd8\xe6",
        ],
    ],
)
@run_in_pyodide(packages=["bcrypt"])
def test_kdf(selenium, rounds, password, salt, expected):
    import bcrypt

    derived = bcrypt.kdf(password, salt, len(expected), rounds, ignore_few_rounds=True)
    assert derived == expected


@run_in_pyodide(packages=["bcrypt"])
def test_kdf_str_password(selenium):
    import bcrypt
    import pytest

    with pytest.raises(TypeError):
        bcrypt.kdf("password", b"$2b$04$cVWp4XaNU8a4v1uMRum2SO", 10, 10)


@run_in_pyodide(packages=["bcrypt"])
def test_kdf_str_salt(selenium):
    import bcrypt
    import pytest

    with pytest.raises(TypeError):
        bcrypt.kdf(b"password", "salt", 10, 10)


@run_in_pyodide(packages=["bcrypt"])
def test_kdf_no_warn_rounds(selenium):
    import bcrypt

    bcrypt.kdf(b"password", b"salt", 10, 10, True)


@run_in_pyodide(packages=["bcrypt"])
def test_kdf_warn_rounds(selenium):
    import bcrypt
    import pytest

    with pytest.warns(UserWarning):
        bcrypt.kdf(b"password", b"salt", 10, 10)


@pytest.mark.parametrize(
    ("password", "salt", "desired_key_bytes", "rounds", "error"),
    [
        ("pass", b"$2b$04$cVWp4XaNU8a4v1uMRum2SO", 10, 10, TypeError),
        (b"password", "salt", 10, 10, TypeError),
        (b"", b"$2b$04$cVWp4XaNU8a4v1uMRum2SO", 10, 10, ValueError),
        (b"password", b"", 10, 10, ValueError),
        (b"password", b"$2b$04$cVWp4XaNU8a4v1uMRum2SO", 0, 10, ValueError),
        (b"password", b"$2b$04$cVWp4XaNU8a4v1uMRum2SO", -3, 10, OverflowError),
        (b"password", b"$2b$04$cVWp4XaNU8a4v1uMRum2SO", 513, 10, ValueError),
        (b"password", b"$2b$04$cVWp4XaNU8a4v1uMRum2SO", 20, 0, ValueError),
    ],
)
@run_in_pyodide(packages=["bcrypt"])
def test_invalid_params(selenium, password, salt, desired_key_bytes, rounds, error):
    import bcrypt
    import pytest

    with pytest.raises(error):
        bcrypt.kdf(password, salt, desired_key_bytes, rounds)


@run_in_pyodide(packages=["bcrypt"])
def test_2a_wraparound_bug(selenium):
    import bcrypt

    assert (
        bcrypt.hashpw((b"0123456789" * 26)[:255], b"$2a$04$R1lJ2gkNaoPGdafE.H.16.")
        == b"$2a$04$R1lJ2gkNaoPGdafE.H.16.1MKHPvmKwryeulRe225LKProWYwt9Oi"
    )
