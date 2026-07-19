#!/usr/bin/env bash

set -e

if [[ -z "${NPM_ID_TOKEN}" ]]; then
    echo "Error: NPM_ID_TOKEN is not set. OIDC token is required for npm trusted publishing." >&2
    exit 1
fi

# Trusted publishing requires npm >= 11.5.1. Older versions produce misleading
# E404 / ENEEDAUTH errors instead of proper diagnostics (npm/cli#9088).
npm install -g npm@11.18.0

# Ensure leftover token auth does not interfere with OIDC trusted publishing.
if [[ -n "${NODE_AUTH_TOKEN}" ]]; then
    echo "Warning: NODE_AUTH_TOKEN is set. Unsetting it to avoid conflicts with OIDC trusted publishing." >&2
    unset NODE_AUTH_TOKEN
fi

echo "=== npm trusted-publishing diagnostics ==="
echo "node: $(node --version)"
echo "npm:  $(npm --version)"
echo "==========================================="

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "$SCRIPT_DIR"/..

# FIXME: since we release from dist directory, README file needs to be copied before release
cp src/js/README.md dist/
cp src/js/package.json dist/

cd dist/

PACKAGE_NAME=$(node -p "require('./package.json').name")
JS_VERSION=$(node -p "require('./package.json').version")
if [[ -n "${DRY_RUN}" ]]; then
    echo "Dry run: npm publish --tag dev"
    npm publish --dry-run --tag dev --loglevel verbose
elif [[ ${JS_VERSION} =~ (alpha|beta|rc|dev) ]]; then
    echo "Publishing an unstable release"
    npm publish --tag next --loglevel verbose
else
    echo "Publishing a stable release"
    npm publish --loglevel verbose
    npm dist-tag add "$PACKAGE_NAME"@"$JS_VERSION" next
fi

rm -f dist/README.md
