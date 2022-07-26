import argparse
import os
import shutil
import tarfile
from pathlib import Path

from doit import create_after  # type: ignore[import]

from pyodide_build import buildall, buildpkg
from pyodide_build.buildpkg import get_bash_runner
from pyodide_build.common import get_make_flag, search_pyodide_root

# from doit.reporter import ZeroReporter

DOIT_CONFIG = {
    "verbosity": 2,
    "minversion": "0.36.0",
    "action_string_formatting": "both",
    "par_type": "thread",
    "backend": "sqlite3",
    # "reporter": ZeroReporter,
}

PYODIDE_ROOT = search_pyodide_root(os.getcwd())
PACKAGES_DIR = PYODIDE_ROOT / "packages"
JS_DIR = PYODIDE_ROOT / "src/js"
PYTHON_DIR = PYODIDE_ROOT / "src/py"
CORE_DIR = PYODIDE_ROOT / "src/core"
DIST_DIR = PYODIDE_ROOT / "dist"
TEMPLATES_DIR = PYODIDE_ROOT / "src/templates"


def run_with_env(*cmds, cwd=None):
    def _run(cmds):
        with get_bash_runner() as runner:
            for cmd in cmds:
                done = runner.run(cmd, cwd=cwd)
                if done.returncode != 0:
                    raise Exception(f"Command failed: {cmd}")

    return (_run, [cmds])


def create_archive(name, files, base="", mode="w"):
    def filter_pycache(f):
        if "__pycache__" in f.name:
            return None
        return f

    name = Path(name)
    name.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(name, mode, dereference=True) as tar:
        for file in files:
            arcname = file.relative_to(base)
            tar.add(file, filter=filter_pycache, arcname=arcname)


def copy(src, dst):
    src = Path(src)
    dst = Path(dst)

    if not src.exists():
        raise Exception(f"Source file {src} does not exist")

    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy(src, dst)

    return True


def task_package():
    def build_package(pkg):
        parser = buildpkg.make_parser(argparse.ArgumentParser())
        args = parser.parse_args([pkg])
        buildpkg.main(args)

    pkgs = [f for f in PACKAGES_DIR.glob("**/meta.yaml")]
    for pkg in pkgs:
        yield {
            "name": pkg.parent.name,
            "file_dep": [pkg],
            "actions": [(build_package, [pkg])],
            "targets": [pkg.parent / "build" / ".packaged"],
            "clean": True,
        }


def task_cpython():
    cpythonlib = Path(get_make_flag("CPYTHONLIB"))
    return {
        "file_dep": [PYODIDE_ROOT / "cpython/Makefile"],
        "actions": [run_with_env("make -C cpython")],
        "targets": [
            cpythonlib.parent / "libpython3.10.a",
        ],
        "task_dep": ["emsdk"],
        "clean": True,
    }


def task_emsdk():
    return {
        "file_dep": [PYODIDE_ROOT / "emsdk/Makefile"],
        "actions": ["make -C emsdk"],
        "targets": [PYODIDE_ROOT / "emsdk/emsdk/.complete"],
        "clean": True,
    }


def task_pyodide_core():
    compilers = {
        ".c": "emcc",
        ".cpp": "em++",
    }
    for ext, compiler in compilers.items():
        for source in CORE_DIR.glob(f"*{ext}"):
            target = source.with_suffix(".o")
            yield {
                "name": source.name,
                "file_dep": [source],
                "actions": [
                    run_with_env(
                        f"{compiler} -c {source} -o {target} $MAIN_MODULE_CFLAGS -I{str(CORE_DIR)}"
                    )
                ],
                "targets": [target],
                "task_dep": ["cpython"],
                "clean": True,
            }


def task_install_js_deps():
    return {
        "file_dep": [JS_DIR / "package.json", JS_DIR / "package-lock.json"],
        "actions": [
            f"cd {JS_DIR} && npm ci",
            f"ln -sfn {JS_DIR}/node_modules {PYODIDE_ROOT}/node_modules",
            f"touch {PYODIDE_ROOT}/node_modules/.installed",
        ],
        "targets": [PYODIDE_ROOT / "node_modules/.installed"],
        "clean": True,
    }


def task_pyproxy_gen():
    # We can't input pyproxy.js directly because CC will be unhappy about the file
    # extension. Instead cat it and have CC read from stdin.
    # -E : Only apply prepreocessor
    # -C : Leave comments alone (this allows them to be preserved in typescript
    #      definition files, rollup will strip them out)
    # -P : Don't put in macro debug info
    # -imacros pyproxy.c : include all of the macros definitions from pyproxy.c
    #
    # First we use sed to delete the segments of the file between
    # "// pyodide-skip" and "// end-pyodide-skip". This allows us to give typescript type
    # declarations for the macros which we need for intellisense
    # and documentation generation. The result of processing the type
    # declarations with the macro processor is a type error, so we snip them
    # out.

    return {
        "file_dep": [*CORE_DIR.glob("pyproxy.*"), *CORE_DIR.glob("*.h")],
        "actions": [
            run_with_env(
                f"""
                rm -f {JS_DIR}/pyproxy.gen.ts
                echo "// This file is generated by applying the C preprocessor to core/pyproxy.ts" >> {JS_DIR}/pyproxy.gen.ts
                echo "// It uses the macros defined in core/pyproxy.c" >> {JS_DIR}/pyproxy.gen.ts
                echo "// Do not edit it directly!" >> {JS_DIR}/pyproxy.gen.ts
                cat {CORE_DIR}/pyproxy.ts | \
                    sed '/^\\/\\/\\s*pyodide-skip/,/^\\/\\/\\s*end-pyodide-skip/d' | \
                    emcc -E -C -P -imacros {CORE_DIR}/pyproxy.c $MAIN_MODULE_CFLAGS - \
                    >> {JS_DIR}/pyproxy.gen.ts
                """
            )
        ],
        "targets": [JS_DIR / "pyproxy.gen.ts"],
        "clean": True,
    }


def task_error_handling():
    source = CORE_DIR / "error_handling.ts"
    target = JS_DIR / "error_handling.gen.ts"
    return {
        "file_dep": [source],
        "actions": [(copy, [source, target])],
        "targets": [target],
        "clean": True,
    }


def task_pyodide_js():
    build_config = JS_DIR / "rollup.config.js"
    return {
        "file_dep": [
            *JS_DIR.glob("*.ts"),
        ],
        "actions": [
            run_with_env(f"npx rollup -c {build_config}"),
        ],
        "targets": [DIST_DIR / "pyodide.js", JS_DIR / "_pyodide.out.js"],
        "task_dep": [
            "install_js_deps",
            "error_handling",
            "pyproxy_gen",
            "distutils",
        ],
        "clean": True,
    }


@create_after(executed="pyodide_core")
def task_pyodide_asm_js():
    target = DIST_DIR / "pyodide.asm.js"
    objs = [str(p) for p in CORE_DIR.glob("*.o")]
    return {
        "file_dep": [*objs],
        "actions": [
            run_with_env(
                'date +"[%F %T] Building pyodide.asm.js..."',
                f"""
                [ -d {DIST_DIR} ] || mkdir {DIST_DIR}
                emcc -o {target} {" ".join(objs)} $MAIN_MODULE_LDFLAGS
                """,
                f"""
                if [[ -n ${{PYODIDE_SOURCEMAP+x}} ]] || [[ -n ${{PYODIDE_SYMBOLS+x}} ]]; then \\
                    cd {DIST_DIR} && npx prettier -w pyodide.asm.js ; \\
                fi
                """,
                # Strip out C++ symbols which all start __Z.
                # There are 4821 of these and they have VERY VERY long names.
                # To show some stats on the symbols you can use the following:
                # cat {target} | grep -ohE 'var _{{0,5}}.' | sort | uniq -c | sort -nr | head -n 20
                f"""
                sed -i -E 's/var __Z[^;]*;//g' {target}
                sed -i '1i "use strict";' {target}
                """,
                # Remove last 6 lines of pyodide.asm.js, see issue #2282
                # Hopefully we will remove this after emscripten fixes it, upstream issue
                # emscripten-core/emscripten#16518
                # Sed nonsense from https://stackoverflow.com/a/13383331
                f"""
                sed -i -n -e :a -e '1,6!{{P;N;D;}};N;ba' {target}
                echo "globalThis._createPyodideModule = _createPyodideModule;" >> {target}
                """,
                'date +"[%F %T] done building pyodide.asm.js."',
            )
        ],
        "targets": [target],
        "task_dep": ["pyodide_core", "pyodide_js"],
        "clean": True,
    }


def task_pyodide_d_ts():
    return {
        "file_dep": [JS_DIR / "pyodide.ts"],
        "actions": [
            "npx dts-bundle-generator {dependencies} --export-referenced-types false",
            f"mv {JS_DIR / 'pyodide.d.ts'} dist",
        ],
        "targets": [DIST_DIR / "pyodide.d.ts"],
        "task_dep": ["pyodide_js", "error_handling", "pyproxy_gen"],
        "clean": True,
    }


def task_templates():
    targets = {
        "webworker.js": "webworker.js",
        "webworker_dev.js": "webworker.js",
        "module_webworker_dev.js": "module_webworker.js",
        "test.html": "test.html",
        "module_test.html": "module_test.html",
    }

    for target_name, source_name in targets.items():
        target_path = DIST_DIR / target_name
        source_path = TEMPLATES_DIR / source_name
        yield {
            "name": target_name,
            "file_dep": [source_path],
            "actions": [
                (copy, [source_path, target_path]),
            ],
            "targets": [target_path],
            "clean": True,
        }


def task_pyodide_py():
    pyodide = PYTHON_DIR / "pyodide"
    pyodide_internal = PYTHON_DIR / "_pyodide"
    target = DIST_DIR / "pyodide_py.tar"
    return {
        "file_dep": [*pyodide.glob("**/*.py"), *pyodide_internal.glob("**/*.py")],
        "actions": [
            (
                create_archive,
                [],
                {
                    "name": target,
                    "base": PYTHON_DIR,
                    "files": [pyodide, pyodide_internal],
                },
            )
        ],
        "targets": [target],
        "clean": True,
    }


def task_repodata_json():
    def build_packages(packages):
        parser = buildall.make_parser(argparse.ArgumentParser())
        packages_dir = PYODIDE_ROOT / "packages"
        args = parser.parse_args(
            [
                str(packages_dir),
                str(DIST_DIR),
                "--only",
                packages,
                "--n-jobs",
                os.environ.get("PYODIDE_JOBS", "4"),
                "--log-dir",
                str(packages_dir / "build-logs"),
            ]
        )
        buildall.main(args)

    return {
        "task_dep": ["cpython"],
        "params": [
            {
                "name": "packages",
                "long": "packages",
                "type": str,
                "default": "core",
            }
        ],
        "actions": [
            'date +"[%%F %%T] Building packages..."',
            (build_packages, []),
            'date +"[%%F %%T] done building packages..."',
        ],
        "targets": [DIST_DIR / "repodata.json"],
        "clean": True,
    }


def task_distutils():
    cpythonlib = Path(get_make_flag("CPYTHONLIB"))
    return {
        "task_dep": ["cpython"],
        "file_dep": [*(cpythonlib / "distutils").glob("**/*.py")],
        "actions": [
            (
                create_archive,
                [],
                {
                    "name": DIST_DIR / "distutils.tar",
                    "base": cpythonlib,
                    "files": [cpythonlib / "distutils"],
                },
            )
        ],
        "targets": [DIST_DIR / "distutils.tar"],
        "clean": True,
    }


def task_package_json():
    package_json = JS_DIR / "package.json"
    target = DIST_DIR / "package.json"
    return {
        "file_dep": [package_json],
        "actions": [(copy, [package_json, target])],
        "targets": [target],
        "clean": True,
    }


def task_console_html():
    console_html = TEMPLATES_DIR / "console.html"
    base_url = get_make_flag("PYODIDE_BASE_URL")
    return {
        "file_dep": [console_html],
        "actions": [
            run_with_env(
                f"cp {console_html} {DIST_DIR / 'console.html'}",
                f"sed -i -e 's#{{{{ PYODIDE_BASE_URL }}}}#{base_url}#g' {DIST_DIR / 'console.html'}",
            )
        ],
        "targets": [DIST_DIR / "console.html"],
        "clean": True,
    }


def task_dependency_check():
    return {"actions": ["echo FIXME!"]}


def task_test():
    test_extensions = [
        (
            "_testinternalcapi.c",
            "_testinternalcapi.o",
        ),
        ("_testcapimodule.c", "_testcapi.o"),
        ("_testbuffer.c", "_testbuffer.o"),
        ("_testimportmultiple.c", "_testimportmultiple.o"),
        ("_testmultiphase.c", "_testmultiphase.o"),
        ("_ctypes/_ctypes_test.c", "_ctypes_test.o"),
    ]
    cpythonbuild = Path(get_make_flag("CPYTHONBUILD"))
    cpythonlib = Path(get_make_flag("CPYTHONLIB"))
    test_module_cflags = (
        get_make_flag("SIDE_MODULE_CFLAGS")
        + f" -I {cpythonbuild}/Include/ -I {cpythonbuild} -I {cpythonbuild}/Include/internal/ -DPy_BUILD_CORE_MODULE"
    )
    for source, obj in test_extensions:
        lib = Path(obj).with_suffix(".so")
        yield {
            "name": source,
            "task_dep": ["cpython", "pyodide_asm_js"],
            "actions": [
                run_with_env(
                    f"emcc {test_module_cflags} -c Modules/{source} -o Modules/{obj}",
                    f"emcc Modules/{obj} -o {lib} $SIDE_MODULE_LDFLAGS",
                    f"rm -f {cpythonlib / lib} && ln -s {cpythonbuild / lib} {cpythonlib / lib}",
                    cwd=cpythonbuild,
                )
            ],
            "targets": [cpythonbuild / lib],
            "clean": True,
        }


@create_after(executed="test")
def task_dist_test():
    cpythonlib = Path(get_make_flag("CPYTHONLIB"))
    target = DIST_DIR / "test.tar"
    return {
        "task_dep": ["test"],
        "actions": [
            (
                create_archive,
                [],
                {
                    "name": target,
                    "base": cpythonlib,
                    "files": [
                        cpythonlib / "test",
                        cpythonlib / "unittest/test",
                        cpythonlib / "sqlite3/test",
                        cpythonlib / "ctypes/test",
                        *cpythonlib.glob("_*test*.so"),
                    ],
                },
            ),
            f"cd {cpythonlib} && rm *test*.so",
        ],
        "targets": [target],
        "clean": True,
    }


def task_pyodide():
    return {
        "task_dep": [
            "dependency_check",
            "pyodide_asm_js",
            "pyodide_js",
            "pyodide_d_ts",
            "package_json",
            "console_html",
            "distutils",
            "dist_test",
            "pyodide_py",
            "templates",
        ],
        "actions": ['echo "SUCCESS!"'],
        "clean": [lambda: shutil.rmtree(DIST_DIR, ignore_errors=True)],
    }
