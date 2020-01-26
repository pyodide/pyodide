#!/usr/bin/env python3
import argparse
import base64

parser = argparse.ArgumentParser(description='Embed a binary file in html.')
parser.add_argument('file_in', type=str, help='input (binary) file')

args = parser.parse_args()

file_in = args.file_in
file_out = file_in + '.html'

blocksize = 32 * 1024  # 32KiB



with open(file_in, 'rb') as f_in, open(file_out, 'w') as f_out:
    f_out.write(
    "<!DOCTYPE html>\n"
    "<html>\n"
    "<head>\n"
    "<script>\n"
    "  var id = window.location.search.substring(1).split('=')[1];\n"
    "  function send(data) {\n"
    "    var binary_string = window.atob(data);\n"
    "    var len = binary_string.length;\n"
    "    var bytes = new Uint8Array(len);\n"
    "    for (var i = 0; i < len; i++) {\n"
    "      bytes[i] = binary_string.charCodeAt(i);\n"
    "    }\n"
    "    var msg = {id: id, data: bytes};\n"
    "    window.parent.postMessage(msg, '*');\n"
    "    document.currentScript.remove();\n"
    "  }\n"
    "</script>\n")
    while True:
        data = f_in.read(blocksize)
        base64bytes = base64.encodebytes(data)
        f_out.write("<script>\n")
        f_out.write("send(`\n" + base64bytes.decode("utf-8") + "`);\n")
        f_out.write("</script>\n")
        if len(data)<blocksize: break

    f_out.write(
    "<script>\n"
    "send('')\n"
    "</script>\n"
    "</head>\n"
    "</html>\n")


