# install zoneinfo data compatible with a unix system
import importlib.resources
from pathlib import Path
import shutil
import importlib
import js

try:
    dst_path=Path("/usr/share/zoneinfo")
    if not Path("/usr/share/zoneinfo").exists():
        with importlib.resources.as_file(importlib.resources.files("unix_timezones").joinpath("tzdata/usr/share/zoneinfo")) as src_path:
            shutil.copytree(src_path,dst_path)

        localtime_path = Path("/etc/localtime")
        if not localtime_path.exists():
            # get local timezone from browser js object
            timezone = js.Intl.DateTimeFormat().resolvedOptions().timeZone
            if timezone and str(timezone) != "":
                timezone = str(timezone)
                # make symbolic link to local time
                Path("/etc/").mkdir(parents=True, exist_ok=True)
                localtime_path.symlink_to(dst_path / timezone)
except (IOError):
    warnings.warn("Couldn't install timezone db to /usr/share/zoneinfo")
