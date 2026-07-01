"""Serve a directory with the cross-origin isolation headers.

SharedArrayBuffer (required by pthread builds) is only available on
cross-origin isolated pages, so plain ``python -m http.server`` is not enough
to test a PYODIDE_PTHREADS build in a browser. Usage:

    python tools/serve_coi.py [port] [--directory dist]

Then open http://localhost:8000/console.html and check that
``crossOriginIsolated`` is true in the devtools console.
"""

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class COIRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        super().end_headers()


def main() -> None:
    port = 8000
    directory = "dist"
    args = sys.argv[1:]
    if "--directory" in args:
        i = args.index("--directory")
        directory = args[i + 1]
        del args[i : i + 2]
    if args:
        port = int(args[0])
    handler = partial(COIRequestHandler, directory=directory)
    with ThreadingHTTPServer(("", port), handler) as httpd:
        print(f"Serving {directory} at http://localhost:{port} with COOP/COEP")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
