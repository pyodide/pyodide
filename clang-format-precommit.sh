#!/bin/bash
FILES=$(git diff --cached --name-only *.c *.h *.js)
WORKING_CHANGED_FILES=$(git diff --name-only *.c *.h *.js)
if [ -z "$FILES" ]; then
    exit 0
fi

# Save working tree files so we don't stage extra changes that
# were not supposed to be in the commit.
if [ -n "$WORKING_CHANGED_FILES" ]; then
    git stash push --keep-index $WORKING_CHANGED_FILES
fi

# Change files, stage changes
clang-format-6.0 -verbose -i $FILES
git add $FILES

# restore working tree
if [ -n "$WORKING_CHANGED_FILES" ]; then
    git stash pop
fi
