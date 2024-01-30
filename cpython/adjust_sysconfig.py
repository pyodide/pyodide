import os
import pprint
from textwrap import dedent


def load_sysconfig(sysconfig_name: str):
    _temp = __import__(sysconfig_name, globals(), locals(), ["build_time_vars"], 0)
    config_vars = _temp.build_time_vars
    return config_vars, _temp.__file__


def write_sysconfig(destfile: str, config_vars: dict[str, str]):
    with open(destfile, "w", encoding="utf8") as f:
        f.write("# system configuration generated and used by the sysconfig module\n")
        f.write("build_time_vars = ")
        pprint.pprint(config_vars, stream=f)
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


if __name__ == "__main__":
    sysconfig_name = os.environ["SYSCONFIG_NAME"]
    config_vars, file = load_sysconfig(sysconfig_name)
    adjust_sysconfig(config_vars)
    write_sysconfig(file, config_vars)
