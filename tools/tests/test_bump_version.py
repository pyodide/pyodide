import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

BUMP_VERSION_SCRIPT = Path(__file__).parents[1] / "bump_version.py"


def run(args, **kwargs):
    return subprocess.run(args, check=False, capture_output=True, text=True, **kwargs)


def bump_version(args, tmp_path):
    """Run bump_version.py with the given arguments in tmp_path."""
    result = run(
        [sys.executable, tmp_path / "tools/bump_version.py", *args],
        cwd=tmp_path,
    )
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    return result


def create_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content))


def setup_test_repo(tmp_path: Path, version: str = "0.27.0"):
    """Create a test git repository with facsimile files."""
    # Initialize git repo
    run(["git", "init"], cwd=tmp_path)
    run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path)
    run(["git", "config", "user.name", "Test User"], cwd=tmp_path)

    # Copy bump_version.py into the temp repo
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    shutil.copy(BUMP_VERSION_SCRIPT, tools_dir / "bump_version.py")

    # Create Makefile.envs
    create_file(
        tmp_path / "Makefile.envs",
        """\
        # Pyodide version settings
        PYODIDE_VERSION ?= %s
        """
        % version,
    )

    # Create src/py/pyodide/__init__.py
    create_file(
        tmp_path / "src/py/pyodide/__init__.py",
        '''\
        """Pyodide package"""
        __version__ = "%s"
        '''
        % version,
    )

    # Create src/py/pyproject.toml
    create_file(
        tmp_path / "src/py/pyproject.toml",
        """\
        [project]
        name = "pyodide"
        version = "%s"
        """
        % version,
    )

    # Create docs/project/about.md
    create_file(
        tmp_path / "docs/project/about.md",
        """\
        # About Pyodide

        version = {%s}
        """
        % version,
    )

    # Create src/js/version.ts
    create_file(
        tmp_path / "src/js/version.ts",
        """\
        export const version: string = "%s";
        """
        % version,
    )

    # Create src/core/pre.js
    create_file(
        tmp_path / "src/core/pre.js",
        """\
        API.version = "%s";
        """
        % version,
    )

    # Create src/js/package.json
    create_file(
        tmp_path / "src/js/package.json",
        """\
        {
            "name": "pyodide",
            "version": "%s"
        }
        """
        % version,
    )

    # Create src/js/package-lock.json
    create_file(
        tmp_path / "src/js/package-lock.json",
        """\
        {
            "name": "pyodide",
            "version": "%s",
            "lockfileVersion": 3
        }
        """
        % version,
    )

    # Commit initial files
    run(["git", "add", "."], cwd=tmp_path)
    run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path)

    return tmp_path


def test_bump_version_dry_run(tmp_path):
    """Test bump_version with --dry-run flag."""
    setup_test_repo(tmp_path, "0.27.0")

    result = bump_version(["0.28.0", "--dry-run"], tmp_path)

    assert result.returncode == 0

    # Verify diff is written to stdout
    assert "[*] Diff of" in result.stdout
    assert "-PYODIDE_VERSION ?= 0.27.0" in result.stdout
    assert "+PYODIDE_VERSION ?= 0.28.0" in result.stdout

    # Verify files were NOT modified (dry run)
    makefile = (tmp_path / "Makefile.envs").read_text()
    assert "0.27.0" in makefile
    assert "0.28.0" not in makefile


def test_bump_version_check_no_changes(tmp_path):
    """Test bump_version --check when no changes are needed (same version)."""
    setup_test_repo(tmp_path, "0.27.0")

    result = bump_version(["0.27.0", "--check"], tmp_path)

    assert result.returncode == 0


def test_bump_version_check_with_changes(tmp_path):
    """Test bump_version --check when changes would be needed."""
    setup_test_repo(tmp_path, "0.27.0")

    result = bump_version(["0.28.0", "--check"], tmp_path)

    # Should fail because files would change
    assert result.returncode == 1


def test_bump_version_updates_files(tmp_path):
    """Test that bump_version actually updates version strings."""
    setup_test_repo(tmp_path, "0.27.0")

    result = bump_version(["0.28.0"], tmp_path)

    assert result.returncode == 0

    # Verify files were updated
    makefile = (tmp_path / "Makefile.envs").read_text()
    assert "0.28.0" in makefile
    assert "0.27.0" not in makefile

    init_py = (tmp_path / "src/py/pyodide/__init__.py").read_text()
    assert "0.28.0" in init_py

    pyproject = (tmp_path / "src/py/pyproject.toml").read_text()
    assert "0.28.0" in pyproject

    version_ts = (tmp_path / "src/js/version.ts").read_text()
    assert "0.28.0" in version_ts

    pre_js = (tmp_path / "src/core/pre.js").read_text()
    assert "0.28.0" in pre_js

    package_json = (tmp_path / "src/js/package.json").read_text()
    assert "0.28.0" in package_json

    package_lock = (tmp_path / "src/js/package-lock.json").read_text()
    assert "0.28.0" in package_lock


def test_bump_version_dev_version(tmp_path):
    """Test bump_version with --dev flag."""
    setup_test_repo(tmp_path, "0.27.0")

    result = bump_version(["0.28.0", "--dev"], tmp_path)

    assert result.returncode == 0

    # Verify dev version was used
    init_py = (tmp_path / "src/py/pyodide/__init__.py").read_text()
    assert "0.28.0.dev0" in init_py


def test_bump_version_prerelease(tmp_path):
    """Test bump_version with prerelease version (alpha)."""
    setup_test_repo(tmp_path, "0.27.0")

    result = bump_version(["0.28.0a1"], tmp_path)

    assert result.returncode == 0

    # Verify Python version format in Python files
    init_py = (tmp_path / "src/py/pyodide/__init__.py").read_text()
    assert "0.28.0a1" in init_py

    # Verify JS version format in JS files (alpha.1)
    package_json = (tmp_path / "src/js/package.json").read_text()
    assert "0.28.0-alpha.1" in package_json


def test_bump_version_dirty_working_tree(tmp_path):
    """Test that bump_version fails with dirty working tree."""
    setup_test_repo(tmp_path, "0.27.0")

    # Create an uncommitted change
    (tmp_path / "uncommitted.txt").write_text("dirty")
    run(["git", "add", "uncommitted.txt"], cwd=tmp_path)

    result = bump_version(["0.28.0"], tmp_path)

    assert result.returncode == 1
    assert "Working tree not clean" in result.stderr
