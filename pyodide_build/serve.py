import os
import sys
import argparse
import http.server
import socketserver
import pathlib

TEST_PATH = pathlib.Path(__file__).parents[0].resolve()
BUILD_PATH = TEST_PATH / '..' / 'build'


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()


Handler.extensions_map['.wasm'] = 'application/wasm'


def make_parser(parser):
    parser.description = ('Start a server with the supplied '
                          'build_dir and port.')
    parser.add_argument('--build_dir', action='store', type=str,
                        default=BUILD_PATH, help='set the build directory')
    parser.add_argument('--port', action='store', type=int,
                        default=8000, help='set the PORT number')
    return parser


def server(port):
    httpd = socketserver.TCPServer(('', port), Handler)
    return httpd


def main(args):
    build_dir = args.build_dir
    port = args.port
    httpd = server(port)
    os.chdir(build_dir)
    print("serving from {0} at localhost:".format(build_dir) + str(port))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n...shutting down http server")
        httpd.shutdown()
        sys.exit()


if __name__ == "__main__":
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
