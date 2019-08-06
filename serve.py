#!/usr/bin/env python3
import os
import socketserver
from http.server import SimpleHTTPRequestHandler

PORT = 8181
os.chdir("build")


class pyodideHttpServer(SimpleHTTPRequestHandler):

    def __init__(self, request, client_address, server):
        self.extensions_map.update({
            '.wasm': 'application/wasm',
        })

        super().__init__(request, client_address, server)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


Handler = pyodideHttpServer

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    httpd.allow_reuse_address = True
    print("serving at port", PORT)
    httpd.serve_forever()
