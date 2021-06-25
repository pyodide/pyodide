FILES="$(git ls-files --others --exclude-standard '*.js' '*.html')"
FILES+=" $(git diff HEAD --name-only '*.js' '*.html')"
if [[ $FILES != " " ]]; then
    prettier --write ${FILES}
fi

FILES="$(git ls-files --others --exclude-standard '*.c' '*.h')"
FILES+=" $(git diff HEAD --name-only '*.c' '*.h')"
if [[ $FILES != " " ]]; then
    clang-format-6.0 -i -verbose ${FILES}
fi

FILES="$(git ls-files --others --exclude-standard '*.py')"
FILES+=" $(git diff HEAD --name-only '*.py')"
if [[ $FILES != " " ]]; then
    black ${FILES}
fi
