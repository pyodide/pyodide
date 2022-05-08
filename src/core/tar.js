JS_FILE(tar_init_js, () => {
  0, 0; /* Magic, see include_js_file.h */

  function loadTar(buffer, path) {
    if (!path.startsWith("/")) {
      throw new Error("Expected absolute path");
    }
    FS.createPath(FS.root, path);
    const curdir = FS.currentPath;
    try {
      FS.chdir(path);
      loadTarInner(buffer);
    } finally {
      FS.chdir(curdir);
    }
  }

  function loadTarInner(buffer) {
    const up_to_first_zero = (buffer) => buffer.subarray(0, buffer.indexOf(0));
    const text_decoder = new TextDecoder();
    let offset = 0;
    let name,
      mode,
      uid,
      gid,
      length,
      lastModified,
      checksum,
      linkType,
      linkName;
    // Convince tools that these are used (they are used by our macros)
    up_to_first_zero;
    text_decoder;
    const curnode = FS.lookupPath(FS.currentPath).node;
    while (true) {
      // parse header
      SET_STRING(name, 100);
      if (name === "") {
        return;
      }
      SKIP_STRING(mode, 8);
      SKIP_STRING(uid, 8);
      SKIP_STRING(gid, 8);
      SET_OCTAL(length, 12);
      SKIP_OCTAL(lastModified, 12);
      SKIP_OCTAL(checksum, 8);
      buffer.subarray(offset - 8, offset).set(0);
      SET_STRING(linkType, 1);
      SKIP_STRING(linkName, 100);
      ALIGN_ADDRESS_UP(offset, 0x200);

      if (linkType !== "" && linkType !== "0") {
        throw new Error("Link support not implemented");
      }
      if (length === 0) {
        FS.createPath(curnode, name);
      } else {
        FS.writeFile(name, LOAD(length), 0, length, undefined, true);
      }
      ALIGN_ADDRESS_UP(offset, 0x200);
    }
  }
  API.loadTar = loadTar;
});
