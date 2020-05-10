try:
    from js import Promise, XMLHttpRequest
except ImportError:
    XMLHttpRequest = None

try:
    from js import pyodide as js_pyodide
except ImportError:

    class js_pyodide:  # type: ignore
        """A mock object to allow import of this package outside pyodide"""
        class _module:
            class packages:
                dependencies = []  # type: ignore


import hashlib
import importlib
import io
import json
from pathlib import Path
import zipfile
from typing import Dict, Any, Union, List, Tuple

from distlib import markers, util, version


def _nullop(*args):
    return


# Provide implementations of HTTP fetching for in-browser and out-of-browser to
# make testing easier
if XMLHttpRequest is not None:
    import pyodide

    def _get_url(url):
        req = XMLHttpRequest.new()
        req.open('GET', url, False)
        req.send(None)
        return io.StringIO(req.response)

    def _get_url_async(url, cb):
        req = XMLHttpRequest.new()
        req.open('GET', url, True)
        req.responseType = 'arraybuffer'

        def callback(e):
            if req.readyState == 4:
                cb(io.BytesIO(req.response))

        req.onreadystatechange = callback
        req.send(None)

    # In practice, this is the `site-packages` directory.
    WHEEL_BASE = Path(__file__).parent
else:
    # Outside the browser
    from urllib.request import urlopen

    def _get_url(url):
        with urlopen(url) as fd:
            content = fd.read()
        return io.BytesIO(content)

    def _get_url_async(url, cb):
        cb(_get_url(url))

    WHEEL_BASE = Path('.') / 'wheels'


def _get_pypi_json(pkgname):
    url = f'https://pypi.org/pypi/{pkgname}/json'
    fd = _get_url(url)
    return json.load(fd)


def _parse_wheel_url(url: str) -> Tuple[str, Dict[str, Any], str]:
    """Parse wheels url and extract available metadata

    See https://www.python.org/dev/peps/pep-0427/#file-name-convention
    """
    file_name = Path(url).name
    # also strip '.whl' extension.
    wheel_name = Path(url).stem
    tokens = wheel_name.split('-')
    # TODO: support optional build tags in the filename (cf PEP 427)
    if len(tokens) < 5:
        raise ValueError(f'{file_name} is not a valid wheel file name.')
    version, python_tag, abi_tag, platform = tokens[-4:]
    name = '-'.join(tokens[:-4])
    wheel = {
        'digests': None,  # checksums not available
        'filename': file_name,
        'packagetype': 'bdist_wheel',
        'python_version': python_tag,
        'abi_tag': abi_tag,
        'platform': platform,
        'url': url,
    }

    return name, wheel, version


class _WheelInstaller:
    def extract_wheel(self, fd):
        with zipfile.ZipFile(fd) as zf:
            zf.extractall(WHEEL_BASE)

    def validate_wheel(self, data, fileinfo):
        if fileinfo.get('digests') is None:
            # No checksums available, e.g. because installing
            # from a different location than PyPi.
            return
        sha256 = fileinfo['digests']['sha256']
        m = hashlib.sha256()
        m.update(data.getvalue())
        if m.hexdigest() != sha256:
            raise ValueError("Contents don't match hash")

    def __call__(self, name, fileinfo, resolve, reject):
        url = self.fetch_wheel(name, fileinfo)

        def callback(wheel):
            try:
                self.validate_wheel(wheel, fileinfo)
                self.extract_wheel(wheel)
            except Exception as e:
                reject(str(e))
            else:
                resolve()

        _get_url_async(url, callback)


class _RawWheelInstaller(_WheelInstaller):
    def fetch_wheel(self, name, fileinfo):
        return fileinfo['url']


class _PackageManager:
    version_scheme = version.get_scheme('normalized')

    def __init__(self):
        self.builtin_packages = {}
        self.builtin_packages.update(
            js_pyodide._module.packages.dependencies
        )
        self.installed_packages = {}

    def install(
            self,
            requirements: Union[str, List[str]],
            ctx=None,
            wheel_installer=None,
            resolve=_nullop,
            reject=_nullop
    ):
        try:
            if ctx is None:
                ctx = {'extra': None}

            if wheel_installer is None:
                wheel_installer = _RawWheelInstaller()

            complete_ctx = dict(markers.DEFAULT_CONTEXT)
            complete_ctx.update(ctx)

            if isinstance(requirements, str):
                requirements = [requirements]

            transaction: Dict[str, Any] = {
                'wheels': [],
                'pyodide_packages': set(),
                'locked': dict(self.installed_packages)
            }
            for requirement in requirements:
                self.add_requirement(requirement, complete_ctx, transaction)
        except Exception as e:
            reject(str(e))

        resolve_count = [len(transaction['wheels'])]

        def do_resolve(*args):
            resolve_count[0] -= 1
            if resolve_count[0] == 0:
                resolve(
                    f'Installed {", ".join(self.installed_packages.keys())}'
                )

        # Install built-in packages
        pyodide_packages = transaction['pyodide_packages']
        if len(pyodide_packages):
            resolve_count[0] += 1
            self.installed_packages.update(
                dict((k, None) for k in pyodide_packages)
            )
            js_pyodide.loadPackage(
                list(pyodide_packages)
            ).then(do_resolve)

        # Now install PyPI packages
        for name, wheel, ver in transaction['wheels']:
            wheel_installer(name, wheel, do_resolve, reject)
            self.installed_packages[name] = ver

    def add_requirement(self, requirement: str, ctx, transaction):
        if requirement.startswith(('http://', 'https://')):
            # custom download location
            name, wheel, version = _parse_wheel_url(requirement)
            transaction['wheels'].append((name, wheel, version))
            return

        req = util.parse_requirement(requirement)

        # If it's a Pyodide package, use that instead of the one on PyPI
        if req.name in self.builtin_packages:
            transaction['pyodide_packages'].add(req.name)
            return

        if req.marker:
            if not markers.evaluator.evaluate(
                    req.marker, ctx):
                return

        matcher = self.version_scheme.matcher(req.requirement)

        # If we already have something that will work, don't
        # fetch again
        for name, ver in transaction['locked'].items():
            if name == req.name:
                if matcher.match(ver):
                    break
                else:
                    raise ValueError(
                        f"Requested '{requirement}', "
                        f"but {name}=={ver} is already installed"
                    )
        else:
            metadata = _get_pypi_json(req.name)
            wheel, ver = self.find_wheel(metadata, req)
            transaction['locked'][req.name] = ver

            recurs_reqs = metadata.get('info', {}).get('requires_dist') or []
            for recurs_req in recurs_reqs:
                self.add_requirement(recurs_req, ctx, transaction)

            transaction['wheels'].append((req.name, wheel, ver))

    def find_wheel(self, metadata, req):
        releases = []
        for ver, files in metadata.get('releases', {}).items():
            ver = self.version_scheme.suggest(ver)
            if ver is not None:
                releases.append((ver, files))
        releases = sorted(releases, reverse=True)
        matcher = self.version_scheme.matcher(req.requirement)
        for ver, meta in releases:
            if matcher.match(ver):
                for fileinfo in meta:
                    if fileinfo['filename'].endswith('py3-none-any.whl'):
                        return fileinfo, ver

        raise ValueError(
            f"Couldn't find a pure Python 3 wheel for '{req.requirement}'"
        )


# Make PACKAGE_MANAGER singleton
PACKAGE_MANAGER = _PackageManager()
del _PackageManager


def install(requirements: Union[str, List[str]]):
    """
    Install the given package and all of its dependencies.

    Returns a Promise that resolves when all packages have downloaded and
    installed.
    """
    def do_install(resolve, reject):
        PACKAGE_MANAGER.install(
            requirements, resolve=resolve, reject=reject
        )
        importlib.invalidate_caches()

    return Promise.new(do_install)


__all__ = ['install']


if __name__ == '__main__':
    install('snowballstemmer')
