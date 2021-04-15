FILES="$(git ls-files --others --exclude-standard '*.c' '*.h' '*.js')"
FILES+=" $(git diff HEAD --name-only '*.c' '*.h' '*.js')"
if [[ $FILES != " " ]]; then
    clang-format-6.0 -i -verbose ${FILES}
fi

FILES="$(git ls-files --others --exclude-standard '*.py')"
FILES+=" $(git diff HEAD --name-only '*.py')"
if [[ $FILES != " " ]]; then
    black ${FILES}
fi
