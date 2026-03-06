def read_leb128(data, offset):
    """Read unsigned LEB128, return (value, bytes_consumed)."""
    result = 0
    shift = 0
    size = 0
    while True:
        b = data[offset + size]
        result |= (b & 0x7F) << shift
        size += 1
        if not (b & 0x80):
            break
        shift += 7
    return result, size


def encode_leb128(value):
    """Encode unsigned integer as LEB128."""
    result = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            byte |= 0x80
        result.append(byte)
        if not value:
            break
    return bytes(result)


def encode_leb128_padded(value, num_bytes):
    """Encode unsigned LEB128 padded to exactly num_bytes."""
    result = bytearray()
    for i in range(num_bytes):
        byte = value & 0x7F
        value >>= 7
        if i < num_bytes - 1:
            byte |= 0x80
        result.append(byte)
    assert value == 0, f"value doesn't fit in {num_bytes} LEB128 bytes"
    return bytes(result)


# llvm lowers the wasm assembly in a funny way. inserting the following patterns to the dispatch table 256 times:
#
# local.set 9
# local.set 8
# local.set 7
# local.set 6
# local.tee 5
# local.get 6
# local.get 7
# local.get 8
# local.get 9
#
# Additionally, it add locals to store these.
# This function just hacks all that out in a brute force fashion.
def patch_wasm(input_file, output_file, target_name):
    with open(input_file, "rb") as f:
        data = bytearray(f.read())

    # Locate the code section (id=10)
    pos = 8  # skip magic + version
    code_sec = None
    while pos < len(data):
        sec_id = data[pos]
        pos += 1
        sec_size, sec_size_leb = read_leb128(data, pos)
        if sec_id == 10:
            code_sec = {
                "size_offset": pos,
                "size_leb": sec_size_leb,
                "size": sec_size,
                "content_start": pos + sec_size_leb,
            }
        pos += sec_size_leb + sec_size
    assert code_sec, "Code section not found"
    print(f"Code section: size={code_sec['size']} at 0x{code_sec['size_offset']:x}")

    # Find the export and resolve function index
    name_bytes = target_name.encode("utf-8")
    export_needle = bytes([len(name_bytes)]) + name_bytes + b"\x00"
    exp_pos = data.find(export_needle)
    assert exp_pos >= 0, f"Export {target_name} not found"
    func_idx, _ = read_leb128(data, exp_pos + len(export_needle))
    print(f"Export '{target_name}' -> func index {func_idx}")

    # Count function imports to get code-section-relative index
    # Import section (id=2)
    pos = 8
    import_sec_content = None
    while pos < len(data):
        sec_id = data[pos]
        pos += 1
        sec_size, sec_size_leb = read_leb128(data, pos)
        if sec_id == 2:
            import_sec_content = pos + sec_size_leb
        pos += sec_size_leb + sec_size

    func_imports = 0
    ipos = import_sec_content
    import_count, ll = read_leb128(data, ipos)
    ipos += ll
    for _ in range(import_count):
        mod_len, ll = read_leb128(data, ipos)
        ipos += ll
        ipos += mod_len
        name_len, ll = read_leb128(data, ipos)
        ipos += ll
        ipos += name_len
        kind = data[ipos]
        ipos += 1
        if kind == 0:  # func
            func_imports += 1
            _, ll = read_leb128(data, ipos)
            ipos += ll
        elif kind == 1:  # table
            ipos += 1  # elemtype
            flags = data[ipos]
            ipos += 1
            _, ll = read_leb128(data, ipos)
            ipos += ll
            if flags & 1:
                _, ll = read_leb128(data, ipos)
                ipos += ll
        elif kind == 2:  # memory
            flags = data[ipos]
            ipos += 1
            _, ll = read_leb128(data, ipos)
            ipos += ll
            if flags & 1:
                _, ll = read_leb128(data, ipos)
                ipos += ll
        elif kind == 3:  # global
            ipos += 2  # valtype + mutability

    code_idx = func_idx - func_imports
    print(f"Function imports: {func_imports}, code index: {code_idx}")

    # Navigate to the target function body
    pos = code_sec["content_start"]
    func_count, ll = read_leb128(data, pos)
    pos += ll
    for _ in range(code_idx):
        body_size, ll = read_leb128(data, pos)
        pos += ll + body_size

    body_size_offset = pos
    body_size, body_size_leb = read_leb128(data, pos)
    body_content_start = pos + body_size_leb
    body_end = body_content_start + body_size
    print(f"Function body: size={body_size} at 0x{body_size_offset:x}")

    # Parse local declarations
    lpos = body_content_start
    local_decl_count, ll = read_leb128(data, lpos)
    locals_start = lpos
    lpos += ll
    for _ in range(local_decl_count):
        _, ll2 = read_leb128(data, lpos)
        lpos += ll2 + 1  # count + valtype
    locals_end = lpos
    bytecode_start = lpos
    print(
        f"Locals: {local_decl_count} decl(s), {locals_end - locals_start} bytes "
        f"({data[locals_start:locals_end].hex()})"
    )

    # Collect byte ranges to remove
    # This is the encoding of that push pop sequence
    garbage_pattern = (
        b"\x21\x09\x21\x08\x21\x07\x21\x06\x22\x05\x20\x06\x20\x07\x20\x08\x20\x09"
    )
    removals = []

    # Remove the local declarations
    removals.append((locals_start + 1, locals_end))

    # Remove all garbage patterns in the bytecode
    bytecode = data[bytecode_start:body_end]
    search_pos = 0
    while True:
        idx = bytecode.find(garbage_pattern, search_pos)
        if idx == -1:
            break
        abs_start = bytecode_start + idx
        removals.append((abs_start, abs_start + len(garbage_pattern)))
        search_pos = idx + len(garbage_pattern)

    pat_count = len(removals) - 1  # subtract the locals removal
    print(f"Found {pat_count} garbage patterns to remove")
    assert pat_count == 256, "can't find pattern"

    # Sort removals by start offset
    removals.sort()
    total_removed = sum(end - start for start, end in removals)
    print(f"Total bytes to remove from function body: {total_removed}")

    # --- Second pass: build new function body ---
    # Copy the body content, skipping removal ranges
    new_body = bytearray()
    # Write new locals declaration: just 0x00 (0 local declarations)
    new_body.append(0x00)
    # Copy bytecode, skipping garbage patterns
    copy_pos = bytecode_start
    for rm_start, rm_end in removals:
        if rm_start < bytecode_start:
            continue  # skip the locals removal
        new_body.extend(data[copy_pos:rm_start])
        copy_pos = rm_end
    new_body.extend(data[copy_pos:body_end])

    new_body_size = len(new_body)
    print(
        f"New body size: {new_body_size} (was {body_size}, delta={body_size - new_body_size})"
    )

    # --- Reconstruct the binary ---
    new_body_size_enc = encode_leb128_padded(new_body_size, body_size_leb)

    out = bytearray()
    out.extend(data[:body_size_offset])
    out.extend(new_body_size_enc)
    out.extend(new_body)
    out.extend(data[body_end:])

    # Fix the code section size
    new_code_sec_size = code_sec["size"] - total_removed
    new_code_sec_size_enc = encode_leb128_padded(
        new_code_sec_size, code_sec["size_leb"]
    )
    cs_off = code_sec["size_offset"]
    out[cs_off : cs_off + code_sec["size_leb"]] = new_code_sec_size_enc
    print(f"Code section size: {code_sec['size']} -> {new_code_sec_size}")

    with open(output_file, "wb") as f:
        f.write(out)
    print(
        f"Wrote {len(out)} bytes to {output_file} (was {len(data)}, saved {len(data) - len(out)})"
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path-to-pyodide.asm.wasm>", file=sys.stderr)
        sys.exit(1)
    patch_wasm(sys.argv[1], sys.argv[1], "tail_call_dispatcher")
