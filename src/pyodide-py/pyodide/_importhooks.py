# mypy gets angry about PathFinder._path_importer_cache.
# mypy: ignore-errors
import os
import inspect
from textwrap import dedent
from importlib.machinery import PathFinder


def _monkeypatch_path_importer_cache():
    """ Get rid of _path_importer_cache, which causes trouble for us. """
    # Future proofing: Double check that the original source of _path_importer_cache
    # is what we expect. (TODO: do we want this?)
    #
    # inspect.getsourcefile returns the wrong thing on PathFinder._path_importer_cache
    # but it behaves correctly on PathFinder. Temporarily monkey patch getsourcefile
    sourcefile = inspect.getsourcefile(PathFinder)
    save_inspect_getsourcefile = inspect.getsourcefile

    def temp_inspect_getsourcefile(object):
        return sourcefile

    inspect.getsourcefile = temp_inspect_getsourcefile
    orig_source = inspect.getsource(PathFinder._path_importer_cache)
    # Restore getsourcefile
    inspect.getsourcefile = save_inspect_getsourcefile

    supposed_orig_source = '''\
    @classmethod
    def _path_importer_cache(cls, path):
        """Get the finder for the path entry from sys.path_importer_cache.

        If the path entry is not in the cache, find the appropriate finder
        and cache it. If no finder is available, store None.

        """
        if path == '':
            try:
                path = _os.getcwd()
            except FileNotFoundError:
                # Don't cache the failure as the cwd can easily change to
                # a valid directory later on.
                return None
        try:
            finder = sys.path_importer_cache[path]
        except KeyError:
            finder = cls._path_hooks(path)
            sys.path_importer_cache[path] = finder
        return finder
    '''

    if dedent(orig_source) != dedent(supposed_orig_source):
        raise RuntimeWarning(
            "Unexpected definition of _path_importer_cache, skipping monkey patch."
        )

    @classmethod
    def _path_importer_cache(cls, path):
        """
        Monkey path for PathFinder._path_importer_cache.
        The import cache has given us various troubles over time. End these problems once
        and for all by never using it!
        """
        if path == "":
            try:
                path = os.getcwd()
            except FileNotFoundError:
                return None
        # Jinx: don't cache anything!
        return cls._path_hooks(path)

    PathFinder._path_importer_cache = _path_importer_cache


_monkeypatch_path_importer_cache()
del _monkeypatch_path_importer_cache
