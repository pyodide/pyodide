import os
from textwrap import dedent

PYODIDE_ROOT = os.environ["PYODIDE_ROOT"]


def load_sysconfig(sysconfig_name: str):
    _temp = __import__(sysconfig_name, globals(), locals(), ["build_time_vars"], 0)
    config_vars = _temp.build_time_vars
    return config_vars, _temp.__file__


def write_sysconfig(destfile: str, fmted_config_vars: dict[str, str]):
    with open(destfile, "w", encoding="utf8") as f:
        f.write("# system configuration generated and used by the sysconfig module\n")
        # Set PYODIDE_ROOT
        f.write("import os\n")
        f.write(f'PYODIDE_ROOT = os.environ.get("PYODIDE_ROOT", "{PYODIDE_ROOT}")\n')
        f.write("build_time_vars = ")
        f.write(fmted_config_vars)
        # at build time, packages that are looking for the Python includes and
        # libraries can get deceived by the values of platbase and
        # installed_base (and possibly others, but we haven't run into trouble
        # with them yet).
        #
        # At run time, the default behavior is correct. We look for the
        # "PYODIDE" environment variable which is defined at build time but not
        # at run time.
        f.write(
            dedent(
                """
                import os
                if os.environ.get("PYODIDE", None) == "1":
                    build_time_vars["installed_base"] = build_time_vars["prefix"]
                    build_time_vars["platbase"] = build_time_vars["prefix"]
                """
            )
        )


def adjust_sysconfig(config_vars: dict[str, str]):
    config_vars.update(
        CC="cc",
        MAINCC="cc",
        LDSHARED="cc",
        LINKCC="cc",
        BLDSHARED="cc",
        CXX="c++",
        LDCXXSHARED="c++",
    )
    config_vars["PYODIDE_ABI_VERSION"] = os.environ["PYODIDE_ABI_VERSION"]
    for [key, val] in config_vars.items():
        if not isinstance(val, str):
            continue
        # Make sysconfigdata relocatable.
        # Replace all instances of "/path/to/pyodide" with "{PYODIDE_ROOT}"
        val = val.replace(f"{PYODIDE_ROOT}", "{PYODIDE_ROOT}")
        # If we made a replacement, then prefix the string with `--tofstring--`
        # so we can convert it to an fstring below
        if "PYODIDE_ROOT" in val:
            val = "--tofstring--" + val
        config_vars[key] = val


def format_sysconfig(config_vars: dict[str, str]) -> str:
    fmted_config_vars = repr(config_vars)
    # Make any string that begins with `--tofstring--` into an fstring and
    # remove the prefix.
    fmted_config_vars = fmted_config_vars.replace("'--tofstring--", "f'")
    fmted_config_vars = fmted_config_vars.replace('"--tofstring--', 'f"')
    return fmted_config_vars


if __name__ == "__main__":
    sysconfig_name = os.environ["SYSCONFIG_NAME"]
    config_vars, file = load_sysconfig(sysconfig_name)
    adjust_sysconfig(config_vars)
    fmted_config_vars = format_sysconfig(config_vars)
    write_sysconfig(file, fmted_config_vars)

    import json, pathlib, re
    pyfile = pathlib.Path(file)
    json_name = re.sub(r"_sysconfigdata__", "_sysconfig_vars__", pyfile.stem) + ".json"
    json_path = pyfile.with_name(json_name)
    json_path.write_text(json.dumps(config_vars, indent=1, sort_keys=True))
    print(f"[adjust_sysconfig] wrote {json_path.relative_to(pathlib.Path.cwd())}")

    import json, pathlib, sys

    details_path = pathlib.Path(file).with_name("build-details.json")
    details = {
            "py_version": f"{os.environ['PYMAJOR']}.{os.environ['PYMINOR']}",
            "platform_triplet": "wasm32-emscripten",
            "abi_flags": os.environ.get("CPYTHON_ABI_FLAGS", ""),
        }
    details_path.write_text(json.dumps(details, indent=2), encoding="utf8")