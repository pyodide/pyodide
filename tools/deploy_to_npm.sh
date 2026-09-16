#!/usr/bin/env bash

set -e

if [[ -z "${NPM_ID_TOKEN}" && -z "${DRY_RUN}" ]]; then
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

# Return 0 if $1 is a higher version than $2 (plain X.Y.Z versions only).
version_gt() {
    [[ "$1" != "$2" ]] && [[ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -n1)" == "$1" ]]
}

if [[ -n "${DRY_RUN}" ]]; then
    echo "Dry run: npm publish --tag dev"
    npm publish --dry-run --tag dev --loglevel verbose
elif [[ ${JS_VERSION} =~ (alpha|beta|rc|dev) ]]; then
    echo "Publishing an unstable release"
    npm publish --tag next --loglevel verbose
else
    # `npm publish` without --tag implicitly moves "latest". npm refuses to move
    # latest for maintenance releases from older release branches. So compare
    # against the registry and publish those under a per-release-line tag
    # instead.
    CURRENT_LATEST=$(npm view "${PACKAGE_NAME}" dist-tags.latest 2>/dev/null || echo "0.0.0")
    if version_gt "${JS_VERSION}" "${CURRENT_LATEST}"; then
        echo "Publishing a stable release (latest: ${CURRENT_LATEST} -> ${JS_VERSION})"
        npm publish --loglevel verbose
    else
        # e.g. pyodide@stable-0.29
        LINE_TAG="stable-$(echo "${JS_VERSION}" | cut -d. -f1,2)"
        echo "Publishing a maintenance release as '${LINE_TAG}' (latest stays ${CURRENT_LATEST})"
        npm publish --tag "${LINE_TAG}" --loglevel verbose
    fi
fi

rm -f README.md
