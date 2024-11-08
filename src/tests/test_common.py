import pytest


def test_install_files_simple(tmp_path):
    from pyodide.common import install_files

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "a.txt").write_text("a")
    (src_dir / "b").mkdir()
    (src_dir / "b/c.txt").write_text("c")

    dest_dir = tmp_path / "dest"
    install_files(src_dir, dest_dir)

    assert (dest_dir / "a.txt").read_text() == "a"
    assert (dest_dir / "b/c.txt").read_text() == "c"


def test_install_files_error(tmp_path):
    from pyodide.common import install_files

    with pytest.raises(ValueError, match="nonexistent is not a directory."):
        install_files(tmp_path / "nonexistent", tmp_path / "dest")

    with pytest.raises(ValueError, match="dest is not a directory."):
        (tmp_path / "empty").mkdir()
        (tmp_path / "dest").write_text("a")
        install_files(tmp_path / "empty", tmp_path / "dest")


def test_install_files_overwrite(tmp_path):
    from pyodide.common import install_files

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "a.txt").write_text("a")
    (src_dir / "b").mkdir()
    (src_dir / "b/c.txt").write_text("c")

    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    (dest_dir / "a.txt").write_text("A")
    (dest_dir / "b").mkdir()
    (dest_dir / "b/c.txt").write_text("C")
    (dest_dir / "b/d.txt").write_text("D")

    install_files(src_dir, dest_dir)

    assert (dest_dir / "a.txt").read_text() == "a"
    assert (dest_dir / "b/c.txt").read_text() == "c"
    assert (dest_dir / "b/d.txt").read_text() == "D"


def test_install_files_multiple_times(tmp_path):
    from pyodide.common import install_files

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "a.txt").write_text("a")
    (src_dir / "b").mkdir()
    (src_dir / "b/c.txt").write_text("c")

    dest_dir = tmp_path / "dest"
    install_files(src_dir, dest_dir)
    install_files(src_dir, dest_dir)

    assert (dest_dir / "a.txt").read_text() == "a"
    assert (dest_dir / "b/c.txt").read_text() == "c"
