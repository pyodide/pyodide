#!/bin/bash
FILES=$(git diff --cached --name-only *.c *.h *.js)
if [ -z "$FILES" ]; then
    exit 0
fi

# Change files, stage changes
clang-format-6.0 -verbose -i $FILES
git add $FILES
