#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import os

PORT = 8080
DIRECTORY = os.path.abspath('lib')

class DirHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

Handler = DirHandler
Handler.extensions_map={
        '.manifest': 'text/cache-manifest',
	'.html': 'text/html',
        '.png': 'image/png',
	'.jpg': 'image/jpg',
	'.svg':	'image/svg+xml',
	'.css':	'text/css',
	'.js':	'application/x-javascript',
	'.wasm': 'application/wasm',
	'.asm': 'application/wasm',
	'': 'application/octet-stream', # Default
    }

httpd = ThreadingHTTPServer(("", PORT), Handler)

print("serving at port", PORT)
httpd.serve_forever()
