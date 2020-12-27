(serving_pyodide_packages)=
# Serving pyodide packages


If you built your pyodide distribution or downloaded the release tarball
you need to serve pyodide files with a appropriate headers.

Because browsers require WebAssembly files to have mimetype of
`application/wasm` we're unable to serve our files using Python's built-in
`SimpleHTTPServer` module.

Let's wrap Python's Simple HTTP Server and provide the appropiate mimetype for
WebAssembly files into a `pyodide_server.py` file (in the `pyodide_local`
directory):
```python
import sys
import socketserver
from http.server import SimpleHTTPRequestHandler


class Handler(SimpleHTTPRequestHandler):

    def end_headers(self):
        # Enable Cross-Origin Resource Sharing (CORS)
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()


if sys.version_info < (3, 7, 5):
    # Fix for WASM MIME type for older Python versions
    Handler.extensions_map['.wasm'] = 'application/wasm'


if __name__ == '__main__':
    port = 8000
    with socketserver.TCPServer(("", port), Handler) as httpd:
        print("Serving at: http://127.0.0.1:{}".format(port))
        httpd.serve_forever()
```

Let's test it out.
In your favourite shell, let's start our WebAssembly aware web server:
```bash
python pyodide_server.py
```

Point your WebAssembly aware browser to
[http://localhost:8000/index.html](http://localhost:8000/index.html) and open
your browser console to see the output from python via pyodide!
