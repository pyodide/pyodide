#!/usr/bin/env bash
set -euo pipefail

LOCAL_DIR=$(dirname $0)
cd "$LOCAL_DIR/../.."

# --- loop build ---
if [ -d "$LOCAL_DIR/dist-loop" ]; then
    echo "=== Skipping loop build ==="
else
    echo "=== Building loop variant ==="
    # clear cpython build
    (cd cpython && make clean)
    # full build to initially populate dist/
    make clean
    make
    cp -r dist/ "$LOCAL_DIR//dist-loop"
fi

# --- tail call variants 0-6 ---
for i in 0 1 2 3 4 5 6; do
    if [ -d "$LOCAL_DIR/dist-tail-$i" ]; then
        echo "=== Skipping tail call variant $i ==="
        continue
    fi
    echo "=== Building tail call variant $i ==="
    # clear cpython dir as we are setting new flags and
    # just build the wasm module since the rest is already built
    (cd cpython && make clean)
    # force remove the files we care about
    rm -f dist/pyodide.asm.*
    TAIL_CALL_DISPATCH=$i make dist/pyodide.asm.js
    cp -r dist/ "$LOCAL_DIR/dist-tail-$i"
done
