#!/bin/bash

# Smoke test for d8

set -x
TOOLS=$(dirname "${BASH_SOURCE[0]}")

npx jsvu --engines=v8 --os=linux64
echo $?

"${HOME}"/.jsvu/bin/v8 --enable-os-system --module "${TOOLS}"/d8-test.mjs
