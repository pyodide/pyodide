#!/usr/bin/env bash

set -e

echo "//registry.npmjs.org/:_authToken=${NPM_TOKEN}" > ~/.npmrc

# FIXME: since we release from dist directory, README file needs to be copied before release
cp src/js/README.md dist/

cd dist/

PACKAGE_NAME=$(node -p "require('./package.json').name")
JS_VERSION=$(node -p "require('./package.json').version")
if [[ ${JS_VERSION} =~ [alpha|beta|rc|dev] ]]; then
    echo "Publishing an unstable release"
    npm publish --tag next
else
    echo "Publishing a stable release"
    npm publish
    npm dist-tag add "$PACKAGE_NAME"@"$JS_VERSION" next
fi

rm -f dist/README.md
