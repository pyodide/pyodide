# install zoneinfo data compatible with a unix system
import importlib
import importlib.resources
import shutil
import warnings
from pathlib import Path

import js

try:
    dst_path = Path("/usr/share/zoneinfo")
    if not Path("/usr/share/zoneinfo").exists():
        with importlib.resources.as_file(
            importlib.resources.files("unix_timezones").joinpath(
                "tzdata/usr/share/zoneinfo"
            )
        ) as src_path:
            shutil.copytree(src_path, dst_path)

        localtime_path = Path("/etc/localtime")
        if not localtime_path.exists():
            # get local timezone from browser js object            
            timezone = js.Intl.DateTimeFormat().resolvedOptions().timeZone # type: ignore[attr-defined]
            if timezone and str(timezone) != "":
                timezone = str(timezone)
                # make symbolic link to local time
                Path("/etc/").mkdir(parents=True, exist_ok=True)
                localtime_path.symlink_to(dst_path / timezone)
except OSError:
    warnings.warn(
        "Couldn't install timezone db to /usr/share/zoneinfo",
        ImportWarning,
        stacklevel=2,
    )
