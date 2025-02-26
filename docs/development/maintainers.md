(maintainer-information)=

# Maintainer information

## Making a release

For branch organization we use a variation of the [GitHub
Flow](https://guides.github.com/introduction/flow/) with
the latest release branch named `stable` (due to ReadTheDocs constraints).

### Making a major release

Assume for concreteness that we are releasing version 0.20.0.

#### Preparation

1. Make a tracking issue with a title like "0.20.0 release planning". Add the
   checklist:

   - [ ] Update packages
   - [ ] Look for open PRs to add to the release milestone
   - [ ] Make sure all PRs in the release milestone are merged
   - [ ] Write release notes
   - [ ] Tidy changelog

2. Make a release notes blog post at pyodide-blog:
   https://github.com/pyodide/pyodide-blog

3. Generate the list of contributors for the release at the end of the release
   notes blog post with:

   ```sh
   git shortlog -s 0.19.0.. | cut -f2- | grep -v '\[bot\]' | sort --ignore-case | tr '\n' ';' | sed 's/;/, /g;s/, $//' | fold -s
   ```

   where `0.19.0` is the tag for the last major release.

4. Read the changelog and tidy it up by adding subsections, organizing, and proof
   reading it. Make a pull request with these changes titled "Rearrange changelog
   for 0.20.0 release" and merge it.

5. Make sure all the PRs that we want to release are merged and that the release notes are ready.

#### Releasing

1. Switch to the main branch
2. Replace the `## Unreleased` heading in the changelog with `## Version 0.20.0`
   and add the date underneath it. Commit this.
3. From the root of the repository run:
   ```
   ./tools/bump_version.py 0.20.0 --tag
   ```
   This makes a release commit and tags it.
4. Push the release commit and tag to upstream. This triggers the release CI.
   ```
   git push upstream main 0.20.0
   ```
5. Wait for CI to pass and release to be created.
6. Rename the `stable` branch to a release branch for the previous major
   version. For instance if last release was, `0.20.0`, the corresponding
   release branch would be `0.20.X`:

   ```sh
   git fetch upstream stable:stable
   git branch 0.20.X stable
   git push -u upstream 0.20.X
   ```

7. Create a new `stable` branch:

   ```sh
   git switch main
   git switch -C stable
   git push upstream stable --force
   ```

8. Set the version back to next development version with:
   ```sh
   git switch main
   ./tools/bump_version.py 0.21.0 --dev
   git push upstream main
   ```

### Making a minor release

Assume for concreteness that we are releasing version 0.27.2.

#### Preparation

1. Go through the commits on the main branch since the last release, find ones
   you want to backport and add the "needs backport" label to the pull requests.
   You can do this manually in the web interface on the github PR or you can use

   ```sh
   ./tools/backports.py add-backport-pr <pr-number>
   ```

2. List out the `needs backport` PRs that are missing changelog entries with

   ```sh
   ./tools/backports.py missing-changelogs
   ```

   and double check that every PR that should have a changelog does have one.

3. Read the changelog and tidy it up by adding subsections, organizing, and
   proof reading it. Make a pull request with these changes titled e.g.,
   "Rearrange changelog for 0.27.2 release" and merge it.

4. Make the backport branch (on top of stable):

   ```
   ./tools/backports.py backport-branch 0.27.2
   ```

5. Make the update-changelog branch (on top of main) with:

   ```
   ./tools/backports.py changelog-branch 0.27.2
   ```

6. Open PRs for these two branches with:

   ```
   ./tools/backports.py open-release-prs 0.27.2
   ```

7. Use the backport branch PR as the release tracker.

8. Make sure that the CI passes on the backports branch and it is approved. When
   it does pass, set the date for the release in the changelog with:
   ```
   ./tools/backports.py changelog-branch 0.27.2 --today
   git push -f
   ./tools/backports.py backport-branch 0.27.2 --today
   git push -f
   ```
   Then merge the two PRs.

#### Releasing

1. Switch to the stable branch and `git pull`.
2. From the root of the repository run:
   ```
   ./tools/bump_version.py 0.27.2 --tag
   ```
   This makes a release commit and tags it.
3. Push the release commit and tag to `upstream/stable`. This triggers the release
   CI.
   ```
   git push upstream stable 0.27.2
   ```
4. Wait for CI to pass and the release to be created.

### Making an alpha release

Assume for concreteness that we are releasing 0.28.0a1.

#### Preparation

Any single maintainer can decide on their own to make an alpha release, it is
not required to discuss it with other maintainers.

Name the first alpha release `x.x.xa1` and in subsequent alphas increment the
final number. No preparation is necessary. Do not make any changes to the
changelog.

#### Release instructions

1. Switch to the main branch and `git pull`.
2. From the root of the repository run:
   ```
   ./tools/bump_version.py 0.28.0a1 --tag
   ```
   This makes a release commit and tags it.
3. Push the release commit and tag to `upstream/main`. This triggers the release
   CI.
   ```
   git push upstream main 0.28.0a1
   ```
4. Put the version back with:
   ```
   git revert 0.28.0a1 -n && git commit -m "Back to development version"
   git push upstream main
   ```
5. Wait for CI to pass and the release to be created.

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

## Updating the Emscripten version

To update Emscripten requires the following three steps:

1. Rebase the patches in `emsdk/patches` onto the new Emscripten version.
2. Update the Emscripten version in `Makefile.envs`
3. Update the `struct_info` json file in `src/js/` to match the version of the
   file in Emscripten.

All three of these steps are automated by `tools/update_emscripten.py`. To
update, you can say: `./tools/update_emscripten.py new_version`. If there are
rebase conflicts, you will have to manually finish the rebase. Once the rebase
is completed, you can rerun `update_emscripten.py`. It will start over the
rebase from scratch but reuse your conflict resolutions using the git rerere
feature.

Updating Emscripten is an ABI break so all platformed wheels that are downloaded
from an external URL need to be disabled until they are rebuilt.

After this is done, commit all the changes and open a PR. There are frequently
complicated CI failures.

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
