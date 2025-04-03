It is important that the fontlist.json included in `extras` matches the format
used in the current version of matplotlib, and also that it doesn't include
fonts installed on a desktop system that wouldn't exist in a pyodide
environment.

To regenerate the fontlist.json from a new version of matplotlib, run the
following in pyodide:

```
import matplotlib
from pathlib import Path

with open(Path(matplotlib.__file__).parent / "fontlist.json") as fd:
    print(fd.read())
```

and copy and paste the output to the `fontlist.json` file.
