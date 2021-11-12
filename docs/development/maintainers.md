(maintainer-information)=

# Maintainer information

## Making a release

For branch organization we use a variation of the [Github
Flow](https://guides.github.com/introduction/flow/) with
the latest release branch named `stable` (due to ReadTheDocs constraints).

(making-major-release)=

### Making a major release

1. Make a new PR and for all occurrences of
   `https://cdn.jsdelivr.net/pyodide/dev/full/` in `./docs/` replace `dev` with
   the release version `vX.Y.Z` (note the presence of the leading `v`). This
   also applies to `docs/conf.py`
2. Set version in `src/py/pyodide/__init__.py`
3. Make sure the change log is up to date.
   - Indicate the release date in the change log.
   - Generate the list of contributors for the release at the end of the
     changelog entry with,
     ```bash
     git shortlog -s LAST_TAG.. | cut -f2- | sort --ignore-case | tr '\n' ';' | sed 's/;/, /g;s/, $//' | fold -s
     ```
     where `LAST_TAG` is the tag for the last release.
     Merge the PR.
4. Assuming the upstream `stable` branch exists, rename it to a release branch
   for the previous major version. For instance if last release was, `0.20.0`,
   the corresponding release branch would be `0.20.X`,
   ```bash
   git fetch upstream
   git checkout stable
   git checkout -b 0.20.X
   git push upstream 0.20.X
   git branch -D stable    # delete locally
   ```
5. Create a tag `X.Y.Z` (without leading `v`) and push
   it to upstream,
   ```bash
   git tag X.Y.Z
   git push upstream X.Y.Z
   ```
   Create a new `stable` branch from this tag,
   ```bash
   git checkout -b stable
   git push upstream stable --force
   ```
   Wait for the CI to pass and create the release on GitHub.
6. Release the pyodide-build package,
   ```bash
   pip install twine build
   cd pyodide-build/
   python -m build .
   ls dist/   # check the produced files
   twine check dist/*X.Y.Z*
   twine upload dist/*X.Y.Z*
   ```
7. Release the Pyodide JavaScript package,

   ```bash
   cd src/js
   npm publish
   ```

8. Build the pre-built Docker image locally and push,
   ```bash
   docker build -t pyodide/pyodide:X.Y.Z -f Dockerfile-prebuilt --build-arg VERSION=BB .
   docker push
   ```
   where `BB` is the last version of the `pyodide-env` Docker image.
9. Revert Step 1. and increment the version in
   `src/py/pyodide/__init__.py` to the next version specified by
   Semantic Versioning.

### Making a minor release

For a minor release, commits need to be added to the `stable` branch, ideally via a PR.
This can be done with either,

- git cherry picking individual commits,
  ```bash
  git checkout stable
  git pull
  git checkout -b backport-branch
  git cherry-pick <commit-hash>
  ```
- or with interactive rebase,
  ```bash
  git fetch upstream
  git checkout stable
  git pull
  git checkout -b backport-branch
  git rebase -i upstream/main
  ```
  and indicate which commits to take from `main` in the UI.

Then follow steps 2, 3, and 6 from {ref}`making-major-release`.

### Fixing documentation for a released version

Cherry pick the corresponding documentation commits to the `stable` branch. Use
`[skip ci]` in the commit message.
