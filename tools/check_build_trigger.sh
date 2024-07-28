#!/bin/bash

set -e
set -x

COMMIT_MSG=$(git log --no-merges -1 --oneline)

# The scipy tests will be triggered on push or on pull_request when the commit
# message contains "[scipy]"
if [[ "$GITHUB_EVENT_NAME" == push ||
      "$COMMIT_MSG" =~ \[scipy\] ]]; then
    echo "trigger=true" >> "$GITHUB_OUTPUT"
fi
