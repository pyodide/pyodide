(maintainer-information)=

# Maintainer information

## Making a release

For branch organization we use a variation of the [GitHub
Flow](https://guides.github.com/introduction/flow/) with
the latest release branch named `stable` (due to ReadTheDocs constraints).

(release-instructions)=

### Release Instructions

1. From the root directory of the repository run

   ```bash
   ./tools/bump_version.py --new-version <new_version>
   # ./tools/bump_version.py --new_version <new_version> --dry-run
   ```

   and check that the diff is correct with `git diff`. Try using `ripgrep` to
   make sure there are no extra old versions lying around e.g., `rg -F "0.18"`,
   `rg -F dev0`, `rg -F dev.0`.

2. Make sure the change log is up-to-date. (Skip for alpha releases.)

   - Indicate the release date in the change log.
   - Generate the list of contributors for the release at the end of the
     changelog entry with,
     ```bash
     git shortlog -s LAST_TAG.. | cut -f2- | sort --ignore-case | tr '\n' ';' | sed 's/;/, /g;s/, $//' | fold -s
     ```
     where `LAST_TAG` is the tag for the last release.

3. Make a PR with the updates from steps 1 and 2. Merge the PR.

4. (Major release only.) Assuming the upstream `stable` branch exists,
   rename it to a release branch for the previous major version. For instance if
   last release was, `0.20.0`, the corresponding release branch would be
   `0.20.X`,

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

   Wait for the CI to pass and create the release on GitHub.

6. (Major release only). Create a new `stable` branch from this tag,

   ```bash
   git checkout -b stable
   git push upstream stable --force
   ```

7. Revert the release commit. If making a major release, increment the version
   to the next development version specified by Semantic Versioning.

   ```sh
   # If you just released 0.22.0, then set the next version to 0.23.0
   ./tools/bump_version.py --new-version 0.23.0.dev0
   ```

8. Update these instructions with any relevant changes.

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

Then follow the relevant steps from {ref}`release-instructions`.

### Making an alpha release

Name the first alpha release `x.x.xa1` and in subsequent alphas increment the
final number. Follow the relevant steps from {ref}`release-instructions`.

### Fixing documentation for a released version

Cherry pick the corresponding documentation commits to the `stable` branch. Use
`[skip ci]` in the commit message.
