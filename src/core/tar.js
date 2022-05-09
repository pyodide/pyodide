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
    let name, mode, uid, gid, length, lastModified, checksum, type, linkName;
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
      SET_STRING(type, 1);
      SKIP_STRING(linkName, 100);
      ALIGN_ADDRESS_UP(offset, 0x200);

      if (type !== "" && type !== "0") {
        throw new Error("Link support not implemented");
      }
      // GNU TAR ensures that the file name of a directory ends with a /
      // See https://git.savannah.gnu.org/cgit/tar.git/tree/src/create.c?h=release_1_34#n1265
      // It seems like it also puts this info into "type" which seems like a better way to do it
      // (cf same file line #n1142) but as per the check above the type always seems to be empty
      // in our tar files.
      if (name.endsWith("/")) {
        FS.createPath(curnode, name);
      } else {
        FS.writeFile(name, LOAD(length), 0, length, undefined, true);
      }
      ALIGN_ADDRESS_UP(offset, 0x200);
    }
  }
  API.loadTar = loadTar;
});
