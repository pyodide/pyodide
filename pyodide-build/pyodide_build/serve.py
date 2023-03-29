import argparse
import http.server
import os
import pathlib
import socketserver
import sys


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


def make_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.description = "Start a server with the supplied dist-dir and port."
    parser.add_argument(
        "--dist-dir",
        action="store",
        type=str,
        default="dist",
        help="set the dist directory (default: %(default)s)",
    )
    parser.add_argument(
        "--port",
        action="store",
        type=int,
        default=8000,
        help="set the PORT number (default: %(default)s)",
    )
    return parser


def server(port: int) -> socketserver.TCPServer:
    httpd = socketserver.TCPServer(("", port), Handler)
    return httpd


def main(args: argparse.Namespace) -> None:
    build_dir = pathlib.Path(args.build_dir).resolve()
    port = args.port
    httpd = server(port)
    os.chdir(build_dir)
    print(f"serving from {build_dir} at localhost:{port}")
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
