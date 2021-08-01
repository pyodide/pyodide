#!/bin/sh
# Use emcc.py because emcc may be a ccache symlink
EM_DIR=`dirname $(which emcc.py)`
FILENAME=$1
shift
python3 $EM_DIR/tools/file_packager.py $FILENAME \
    --lz4 \
    --export-name=globalThis.__pyodide_module \
    --exclude *__pycache__* \
    --use-preload-plugins \
    $@
