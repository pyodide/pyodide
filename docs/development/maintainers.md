(maintainer-information)=

# Maintainer information

## Making a release

For branch organization we use a variation of the [GitHub
Flow](https://guides.github.com/introduction/flow/) with
the latest release branch named `stable` (due to ReadTheDocs constraints).

(making-major-release)=

### Making a major release

1. From the root directory of the repository,

   ```bash
   ./tools/bump_version.py --new-version <new_version>
   # ./tools/bump_version.py --new_version <new_version> --dry-run
   ```

   check that the diff is correct with `git diff` before committing.

   After this, try using `ripgrep` to make sure there are no extra old versions
   lying around e.g., `rg -F "0.18"`, `rg -F dev0`, `rg -F dev.0`.

2. Make sure the change log is up-to-date.

   - Indicate the release date in the change log.
   - Generate the list of contributors for the release at the end of the
     changelog entry with,
     ```bash
     git shortlog -s LAST_TAG.. | cut -f2- | sort --ignore-case | tr '\n' ';' | sed 's/;/, /g;s/, $//' | fold -s
     ```
     where `LAST_TAG` is the tag for the last release.
     Merge the PR.

3. Assuming the upstream `stable` branch exists, rename it to a release branch
   for the previous major version. For instance if last release was, `0.20.0`,
   the corresponding release branch would be `0.20.X`,
   ```bash
   git fetch upstream
   git checkout stable
   git checkout -b 0.20.X
   git push upstream 0.20.X
   git branch -D stable    # delete locally
   ```
4. Create a tag `X.Y.Z` (without leading `v`) and push
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

5. Release the Pyodide JavaScript package:

   ```bash
   make clean && make
   cd dist
   npm publish # Note: use "--tag next" for prereleases
   npm dist-tag add pyodide@a.b.c next # Label this release as also the latest unstable release
   ```

6. Increment the version to the next version
   specified by Semantic Versioning. Set `dev` version if needed.

   ```sh
   # For example, if you just released 0.22.0, then set the version to 0.22.1.dev0
   ./tools/bump_version.py --new-version 0.22.1.dev0
   ```

7. Update this file with any relevant changes.

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

Then follow steps 1, 2, 5 and 6 from {ref}`making-major-release`.

### Making an alpha release

Follow steps 1, 5, and 6 from {ref}`making-major-release`. Name the first
alpha release `x.x.xa0` and in subsequent alphas increment the final number. For
the npm package the alpha should have version in the format `x.x.x-alpha.0`. For
the node package make sure to use `npm publish --tag next` to avoid setting the
alpha version as the stable release.

If you accidentally publish the alpha release over the stable `latest` tag, you
can fix it with: `npm dist-tag add pyodide@a.b.c latest` where `a.b.c` should be
the latest stable version. Then use
`npm dist-tag add pyodide@a.b.c-alpha.d next` to set the `next` tag to point to the
just-published alpha release.

### Fixing documentation for a released version

Cherry pick the corresponding documentation commits to the `stable` branch. Use
`[skip ci]` in the commit message.
