(maintainer-information)=

# Maintainer information

## Making a release

For branch organization we use a variation of the [GitHub
Flow](https://guides.github.com/introduction/flow/) with
the latest release branch named `stable` (due to ReadTheDocs constraints).

### Preparation for making a major release

Generally we make a tracking issue with a title like "0.25.0 release planning".

Follow the steps in {ref}`updating-packages`.

Read the changelog and tidy it up by adding subsections and proof reading it.

Generate the list of contributors for the release at the end of the
changelog entry with

```sh
git shortlog -s LAST_TAG.. | cut -f2- | grep -v '\[bot\]' | sort --ignore-case | tr '\n' ';' | sed 's/;/, /g;s/, $//' | fold -s
```

where `LAST_TAG` is the tag for the last release.

Make a pull request with these changes titled "Rearrange changelog for 0.25.0
release" and merge it.

### Preparation for making a minor release

Make a branch called `backports-for-v.vv.v`:

```sh
git checkout stable
git pull upstream
git checkout -b backports-for-0.23.1
```

Locate the commits you want to backport in the main branch and cherry pick them:

```sh
git cherry-pick <commit-hash>
```

Make a pull request from `backports-for-0.23.1` targeting the stable branch. If
you're using the github cli this can be done with:

```sh
gh pr create -w -B stable
```

In the pull request description add a task:

```md
- [ ] Merge don't squash
```

This pull request is a good place to @mention various people to ask if they have
opinions about what should be backported.

Add an extra commit organizing the changelog into sections and editing changelog
messages. Generate the list of contributors for the release at the end of the
changelog entry with

```sh
git shortlog -s LAST_TAG.. | cut -f2- | grep -v '\[bot\]' | sort --ignore-case | tr '\n' ';' | sed 's/;/, /g;s/, $//' | fold -s
```

where `LAST_TAG` is the tag for the last release. Make a branch from main called
`changelog-for-v.vv.v` and apply the same changelog rearrangements there.

Merge `changelog-for-v.vv.v` and `backports-for-v.vv.v` and then follow the
relevant steps from {ref}`release-instructions`.

### Preparation for making an alpha release

Name the first alpha release `x.x.xa1` and in subsequent alphas increment the
final number. No prepration is necessary. Don't update anything in the
changelog. Follow the relevant steps from {ref}`release-instructions`.

(release-instructions)=

### Release Instructions

1. From the root directory of the repository run

   ```sh
   ./tools/bump_version.py --new-version <new_version>
   # ./tools/bump_version.py --new_version <new_version> --dry-run
   ```

   and check that the diff is correct with `git diff`. Try using `ripgrep` to
   make sure there are no extra old versions lying around e.g., `rg -F "0.18"`,
   `rg -F dev0`, `rg -F dev.0`.

2. (Skip for alpha release.) Add a heading to the changelog indicating version
   and release date

3. Make a PR with the updates from steps 1 and 2. Merge the PR.

4. (Major release only.) Rename the `stable` branch to a release branch for the
   previous major version. For instance if last release was, `0.20.0`, the
   corresponding release branch would be `0.20.X`:

   ```sh
   git fetch upstream stable:stable
   git branch 0.20.X stable
   git push -u upstream 0.20.X
   ```

5. Create a tag `X.Y.Z` (without leading `v`) and push
   it to upstream,

   ```sh
   git checkout main
   git pull upstream
   git tag X.Y.Z
   git push upstream X.Y.Z
   ```

   Wait for the CI to pass and create the release on GitHub.

6. (Major release only). Create a new `stable` branch from this tag,

   ```sh
   git checkout main
   git checkout -B stable
   git push upstream stable --force
   ```

7. (Major or alpha but not minor release.) Set the version number back to the
   development version. If you just released `0.22.0`, set the version to
   `0.23.0.dev0`. If you just released `0.22.0a1` then you'll set the version to
   `0.22.0.dev0`. Make a new commit from this and push it to upstream.
   ```sh
   git checkout main
   ./tools/bump_version.py --new-version 0.23.0.dev0
   git add -u
   git commit -m "0.23.0.dev0"
   git push upstream main
   ```

## Fixing documentation for a released version

Cherry pick the corresponding documentation commits to the `stable` branch. Use
`git commit --amend` to add `[skip ci]` to the commit message.

## Updating the Docker image

Anyone with an account on hub.docker.com can follow the following steps:

1. Make whatever changes are needed to the Dockerfile.
2. Build the docker image with `docker build .` in the Pyodide root directory.
   If the build succeeds, docker will give you a hash for the built image.
3. Use `python ./tools/docker_image_tag.py` to find out what the new image tag
   should be. Tag the image with:
   ```sh
   docker image tag <image-hash> <your-docker-username>/pyodide-env:<image-tag>
   ```
4. Push the image with:
   ```sh
   docker image push <your-docker-username>/pyodide-env:<image-tag>
   ```
5. Replace the image in `.circleci/config.yml` with your newly created image.
   Open a pull request with your changes to `Dockerfile` and `.circleci/config.yml`.
6. When the tests pass and the pull request is approved, a maintainer must copy
   the new image into the `pyodide` dockerhub account.
7. Then replace the image tag in `.circleci/config.yml`,
   `.devcontainer/devcontainer.json`, and `run_docker` with the new image under
   the `pyodide` dockerhub account.

It's also possible to update the docker image by pushing your changes to the
`Dockerfile` to a branch in the `pyodide/pyodide` repo (not on a fork) and
clicking `Run workflow` on
https://github.com/pyodide/pyodide/actions/workflows/docker_image.yml.

(updating-packages)=

## Updating packages

Before updating the Python version and before making a major Pyodide release, we
try to update all packages that are not too much trouble. Run

```sh
make -C packages update-all
```

to update all packages and make a pull request with these changes. There will be
build/test failures, revert the packages that fail the build or tests and make a
note to update them independently.

## Updating pyodide-build

to change the version of pyodide-build, change the commit of the pyodide-build submodule.

```bash
cd pyodide-build
git checkout "<COMMIT HASH>"
```

to test with the fork of pyodide-build, change the `.gitmodules` file to point to your fork and update the commit hash

```ini
# .gitmodules
[submodule "pyodide-build"]
	path = pyodide-build
	url = https://github.com/<yourfork>/pyodide-build
```

```bash
git submodule sync
cd pyodide-build
git checkout "<COMMIT HASH"
```

## Upgrading pyodide to a new version of CPython

### Prerequisites

The desired version of CPython must be available at:

1. The `specific release` section of https://www.python.org/downloads
2. https://hub.docker.com/_/python
3. https://github.com/actions/python-versions/releases

If doing a major version update, save time by {ref}`updating-packages` first.

### Steps

1. Follow the steps in "Updating the Docker image" to create a docker image for
   the new Python version.

2. Make sure you are in a Python virtual environment with the new version of
   Python and with `requirements.txt` installed. (It is also possible to work in
   the docker image as an alternative.)

3. Update the Python version in Makefile.envs

4. Update the Python version in the following locations:

   - `.github/workflows/main.yml`
   - `docs/conf.py`
   - `docs/development/contributing.md`
   - `docs/development/building-and-testing-packages.md`
   - `environment.yml`
   - `.pre-commit-config.yaml`
   - `pyproject.toml`

   (TODO: make this list shorter.)

5. Rebase the patches:

   - Clone cpython and cd into it. Checkout the Python version you are upgrading
     from. For instance, if the old version is 3.11.3, use `git checkout v3.11.3`
     (Python tags have a leading v.) Run

     ```sh
     git am ~/path/to/pyodide/cpython/patches/*
     ```

   - Rebase the patches onto the new version of Python. For instance if updating
     from Python v3.11.3 to Python 3.12.1:

     ```sh
     git rebase v3.11.3 --onto v3.12.1
     ```

   - Resolve conflicts / drop patches that have been upstreamed. If you have
     conflicts, make sure you are using diff3:

     ```sh
     git config --global merge.conflictstyle diff3
     ```

   - Generate the new patches:
     ```sh
     rm ~/path/to/pyodide/cpython/patches/*
     git format-patch v3.12.1 -o ~/path/to/pyodide/cpython/patches/
     ```

6. Try to build Python with `make -C cpython`. Fix any build errors. If you
   modify the Python source in tree after a failed build it may be useful to run
   `make rebuild`.

7. Try to finish the build with a top level `make`. Fix compile errors in
   `src/core` and any link errors. It may be useful to apply
   `upgrade_pythoncapi.py --no-compat` to the C extension in `src/code`.
   https://github.com/python/pythoncapi-compat/blob/main/upgrade_pythoncapi.py

   The file most tightly coupled to the CPython version is
   `src/core/stack_switching/pystate.c`. Consult the following greenlet file to
   figure out how to fix it:
   https://github.com/python-greenlet/greenlet/blob/master/src/greenlet/TPythonState.cpp

8. Run

   ```sh
   python tools/make_test_list.py
   ```

   Then run the core tests `pytest src/tests/test_core_python.py` and either fix
   the failures or update `src/tests/python_tests.yaml` to skip or xfail them.

9. Try to build packages with:

   ```sh
   pyodide build-recipes '*'
   ```

   Disable packages until the build succeeds. Then fix the build failures. In
   many cases, this just requires updating to the most recent version of the
   package. If you have trouble, try searching on the package's issue tracker
   for "python 3.12" (or whatever the new version is). It's best to create
   separate PRs for tricky package upgrades.

10. Fix failing package tests.

### Old major Python upgrades

| version | pr         |
| ------- | ---------- |
| 3.12    | {pr}`4435` |
| 3.11    | {pr}`3252` |
| 3.10    | {pr}`2225` |
| 3.9     | {pr}`1637` |
| 3.8     | {pr}`712`  |
| 3.7     | {pr}`77`   |
