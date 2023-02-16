from sphinx.application import Sphinx
from sphinx.ext.intersphinx import InventoryAdapter

DATA = {
    "js:function": {
        "setTimeout": "API/",
        "clearTimeout": "API/",
        "setInterval": "API/",
        "clearInterval": "API/",
        "fetch": "API/",
        "eval": "$global/",
        "Object.fromEntries": "$global/",
        "Reflect.ownKeys": "$global/",
        "Array.from": "$global/",
        "Atomics.wait": "$global/",
    },
    "js:class": {
        "Array": "$global/",
        "NodeList": "API/",
        "HTMLCollection": "API/",
        "Generator": "$global/",
        "AsyncGenerator": "$global/",
        "Date": "$global/",
        "ArrayBuffer": "$global/",
        "SharedArrayBuffer": "$global/",
        "TypedArray": "$global/",
        "TextEncoder": "$global/",
        "TextDecoder": "$global/",
        "DataView": "$global/",
        "Uint8Array": "$global/",
        "Map": "$global/",
        "Set": "$global/",
        # the JavaScript domain has no exception type for some reason...
        "Error": "$global/",
        "Function": "$global/",
        "Promise": "$global/",
        "FileSystemDirectoryHandle": "API/",
    },
    "js:method": {
        "Iterator.next": "$reference/Iteration_protocols#next",
        "AsyncIterator.next": "$reference/Iteration_protocols#next_2",
        "Generator.next": "$global/",
        "Generator.throw": "$global/",
        "Generator.return": "$global/",
        "AsyncGenerator.next": "$global/",
        "AsyncGenerator.throw": "$global/",
        "AsyncGenerator.return": "$global/",
        "Response.clone": "API/",
        "Response.arrayBuffer": "API/",
        "EventTarget.addEventListener": "API/",
        "EventTarget.removeEventListener": "API/",
        "Promise.then": "$global/",
        "Promise.catch": "$global/",
        "Promise.finally": "$global/",
        "Function.apply": "$global/",
        "Function.bind": "$global/",
        "Function.call": "$global/",
    },
    "js:data": {
        "Iterable": "$reference/Iteration_protocols#the_iterable_protocol",
        "IteratorResult": "$reference/Iteration_protocols#next",
        "Iterator": "$reference/Iteration_protocols#the_iterator_protocol",
        "AsyncIterator": "$reference/Iteration_protocols#the_async_iterator_and_async_iterable_protocols",
        "Symbol.asyncIterator": "$global/",
        "Symbol.iterator": "$global/",
        "Symbol.toStringTag": "$global/",
        "FinalizationRegistry": "$global/",
        "globalThis": "$global/",
        "NaN": "$global/",
        "undefined": "$global/",
        "BigInt": "$global/",
        "Number": "$global/",
        "String": "$global/",
        "Boolean": "$global/",
        "Object": "$global/",
        "Number.MAX_SAFE_INTEGER": "$global/",
        "null": "$reference/Operators/",
        "Response": "API/",
        "TypedArray.BYTES_PER_ELEMENT": "$global/",
    },
    "js:attribute": {
        "TypedArray.byteLength": "$global/",
        "Response.type": "API/",
        "Response.url": "API/",
        "Response.statusText": "API/",
        "Response.bodyUsed": "API/",
        "Response.ok": "API/",
        "Response.redirected": "API/",
        "Response.status": "API/",
    },
    "std:label": {"async function": "$reference/Statements/async_function"},
}

JSDATA = set(DATA["js:data"].keys())
JSDATA.update([x.lower() for x in JSDATA])
JSDATA.add("void")
JSDATA.add("any")
JSCLASS = set(DATA["js:class"].keys())

# Each entry is a four tuple:
# (project_name, project_version, url, link_text)
#
# If link_text is "-" the original name of the xref will be used as the link
# text which is good enough for us.
PROJECT_NAME = "MDN docs"
PROJECT_VERSION = ""  # MDN docs are not really versioned
USE_NAME_AS_LINK_TEXT = "-"

INVDATA: dict[str, dict[str, tuple[str, str, str, str]]] = {}
for type, entries in DATA.items():
    type_values = INVDATA.setdefault(type, {})
    for key, value in entries.items():
        value = value.replace("$reference", "JavaScript/Reference")
        value = value.replace("$global", "JavaScript/Reference/Global_Objects")
        if value.endswith("/"):
            value += key.replace(".", "/")
        url = f"https://developer.mozilla.org/en-US/docs/Web/{value}"
        type_values[key] = (PROJECT_NAME, PROJECT_VERSION, url, USE_NAME_AS_LINK_TEXT)
        type_values[key.lower()] = (
            PROJECT_NAME,
            PROJECT_VERSION,
            url,
            USE_NAME_AS_LINK_TEXT,
        )

for key, url in [
    ("void", "https://www.typescriptlang.org/docs/handbook/2/functions.html#void"),
    ("any", "https://www.typescriptlang.org/docs/handbook/2/everyday-types.html#any"),
]:
    INVDATA["js:data"][key] = (
        "typescript docs",
        "",
        url,
        "-",
    )

for key in ["stdin", "stdout", "stderr"]:
    INVDATA["js:data"][f"process.{key}"] = (
        "node docs",
        "",
        f"https://nodejs.org/api/process.html#process{key}",
        "-",
    )


def add_mdn_xrefs(app: Sphinx) -> None:
    """Add cross referencing to Mozilla Developer Network documentation"""
    inventories = InventoryAdapter(app.builder.env)
    inventories.named_inventory["mdn"] = INVDATA
    for type, objects in INVDATA.items():
        inventories.main_inventory.setdefault(type, {}).update(objects)


__all__ = ["add_mdn_xrefs"]
