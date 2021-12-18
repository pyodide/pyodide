# coding: utf-8
"""
Package resource API
--------------------

A resource is a logical file contained within a package, or a logical
subdirectory thereof.  The package resource API expects resource names
to have their path parts separated with ``/``, *not* whatever the local
path separator is.  Do not use os.path operations to manipulate resource
names being passed into the API.

The package resource API is designed to work with normal filesystem packages,
.egg files, and unpacked .egg files.  It can also work in a limited way with
.zip files and with custom PEP 302 loaders that support the ``get_data()``
method.
"""

from __future__ import absolute_import

import sys
import re
import warnings
import email.parser
import urllib

try:
    FileExistsError
except NameError:
    FileExistsError = OSError

import packaging.version
import packaging.specifiers
import packaging.requirements
import packaging.markers


__metaclass__ = type


class PEP440Warning(RuntimeWarning):
    """
    Used when there is an issue with a version or specifier not complying with
    PEP 440.
    """


def parse_version(v):
    try:
        return packaging.version.Version(v)
    except packaging.version.InvalidVersion:
        return packaging.version.LegacyVersion(v)


__all__ = [
    "DistInfoDistribution",
    "Distribution",
    "DictMetadata",
]


class ResolutionError(Exception):
    """Abstract base for dependency resolution errors"""

    def __repr__(self):
        return self.__class__.__name__ + repr(self.args)


class UnknownExtra(ResolutionError):
    """Distribution doesn't have an "extra feature" of the given name"""


PY_MAJOR = "{}.{}".format(*sys.version_info)
EGG_DIST = 3


def safe_name(name):
    """Convert an arbitrary string to a standard distribution name

    Any runs of non-alphanumeric/. characters are replaced with a single '-'.
    """
    return re.sub("[^A-Za-z0-9.]+", "-", name)


def safe_version(version):
    """
    Convert an arbitrary string to a standard version string
    """
    try:
        # normalize the version
        return str(packaging.version.Version(version))
    except packaging.version.InvalidVersion:
        version = version.replace(" ", ".")
        return re.sub("[^A-Za-z0-9.]+", "-", version)


def safe_extra(extra):
    """Convert an arbitrary string to a standard 'extra' name

    Any runs of non-alphanumeric characters are replaced with a single '_',
    and the result is always lowercased.
    """
    return re.sub("[^A-Za-z0-9.-]+", "_", extra).lower()


def invalid_marker(text):
    """
    Validate text as a PEP 508 environment marker; return an exception
    if invalid or False otherwise.
    """
    try:
        evaluate_marker(text)
    except SyntaxError as e:
        e.filename = None
        e.lineno = None
        return e
    return False


def evaluate_marker(text, extra=None):
    """
    Evaluate a PEP 508 environment marker.
    Return a boolean indicating the marker result in this environment.
    Raise SyntaxError if marker is invalid.

    This implementation uses the 'pyparsing' module.
    """
    try:
        marker = packaging.markers.Marker(text)
        return marker.evaluate()
    except packaging.markers.InvalidMarker as e:
        raise SyntaxError(e)


def yield_lines(strs):
    """Yield non-empty/non-comment lines of a string or sequence"""
    if isinstance(strs, str):
        for s in strs.splitlines():
            s = s.strip()
            # skip blank lines/comments
            if s and not s.startswith("#"):
                yield s
    else:
        for ss in strs:
            for s in yield_lines(ss):
                yield s


def _remove_md5_fragment(location):
    if not location:
        return ""
    parsed = urllib.parse.urlparse(location)
    if parsed[-1].startswith("md5="):
        return urllib.parse.urlunparse(parsed[:-1] + ("",))
    return location


def _version_from_file(lines):
    """
    Given an iterable of lines from a Metadata file, return
    the value of the Version field, if present, or None otherwise.
    """

    def is_version_line(line):
        return line.lower().startswith("version:")

    version_lines = filter(is_version_line, lines)
    line = next(iter(version_lines), "")
    _, _, value = line.partition(":")
    return safe_version(value.strip()) or None


class Distribution:
    """Wrap an actual or potential sys.path entry w/metadata"""

    PKG_INFO = "PKG-INFO"

    def __init__(
        self,
        location=None,
        metadata=None,
        project_name=None,
        version=None,
        py_version=PY_MAJOR,
        platform=None,
        precedence=EGG_DIST,
    ):
        self.project_name = safe_name(project_name or "Unknown")
        if version is not None:
            self._version = safe_version(version)
        self.py_version = py_version
        self.platform = platform
        self.location = location
        self.precedence = precedence
        self._provider = metadata

    @property
    def hashcmp(self):
        return (
            self.parsed_version,
            self.precedence,
            self.key,
            _remove_md5_fragment(self.location),
            self.py_version or "",
            self.platform or "",
        )

    def __hash__(self):
        return hash(self.hashcmp)

    def __lt__(self, other):
        return self.hashcmp < other.hashcmp

    def __le__(self, other):
        return self.hashcmp <= other.hashcmp

    def __gt__(self, other):
        return self.hashcmp > other.hashcmp

    def __ge__(self, other):
        return self.hashcmp >= other.hashcmp

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            # It's not a Distribution, so they are not equal
            return False
        return self.hashcmp == other.hashcmp

    def __ne__(self, other):
        return not self == other

    # These properties have to be lazy so that we don't have to load any
    # metadata until/unless it's actually needed.  (i.e., some distributions
    # may not know their name or version without loading PKG-INFO)

    @property
    def key(self):
        try:
            return self._key
        except AttributeError:
            self._key = key = self.project_name.lower()
            return key

    @property
    def parsed_version(self):
        if not hasattr(self, "_parsed_version"):
            self._parsed_version = parse_version(self.version)

        return self._parsed_version

    @property
    def version(self):
        try:
            return self._version
        except AttributeError:
            version = self._get_version()
            if version is None:
                path = self._get_metadata_path_for_display(self.PKG_INFO)
                msg = ("Missing 'Version:' header and/or {} file at path: {}").format(
                    self.PKG_INFO, path
                )
                raise ValueError(msg, self)

            return version

    @property
    def _dep_map(self):
        """
        A map of extra to its list of (direct) requirements
        for this distribution, including the null extra.
        """
        try:
            return self.__dep_map
        except AttributeError:
            self.__dep_map = self._filter_extras(self._build_dep_map())
        return self.__dep_map

    @staticmethod
    def _filter_extras(dm):
        """
        Given a mapping of extras to dependencies, strip off
        environment markers and filter out any dependencies
        not matching the markers.
        """
        for extra in list(filter(None, dm)):
            new_extra = extra
            reqs = dm.pop(extra)
            new_extra, _, marker = extra.partition(":")
            fails_marker = marker and (
                invalid_marker(marker) or not evaluate_marker(marker)
            )
            if fails_marker:
                reqs = []
            new_extra = safe_extra(new_extra) or None

            dm.setdefault(new_extra, []).extend(reqs)
        return dm

    def _build_dep_map(self):
        dm = {}
        for name in "requires.txt", "depends.txt":
            for extra, reqs in split_sections(self._get_metadata(name)):
                dm.setdefault(extra, []).extend(parse_requirements(reqs))
        return dm

    def requires(self, extras=()):
        """List of Requirements needed for this distro if `extras` are used"""
        dm = self._dep_map
        deps = []
        deps.extend(dm.get(None, ()))
        for ext in extras:
            try:
                deps.extend(dm[safe_extra(ext)])
            except KeyError:
                raise UnknownExtra("%s has no such extra feature %r" % (self, ext))
        return deps

    def _get_metadata_path_for_display(self, name):
        """
        Return the path to the given metadata file, if available.
        """
        try:
            # We need to access _get_metadata_path() on the provider object
            # directly rather than through this class's __getattr__()
            # since _get_metadata_path() is marked private.
            path = self._provider._get_metadata_path(name)

        # Handle exceptions e.g. in case the distribution's metadata
        # provider doesn't support _get_metadata_path().
        except Exception:
            return "[could not detect]"

        return path

    def _get_metadata(self, name):
        if self.has_metadata(name):
            for line in self.get_metadata_lines(name):
                yield line

    def _get_version(self):
        lines = self._get_metadata(self.PKG_INFO)
        version = _version_from_file(lines)

        return version

    def __repr__(self):
        if self.location:
            return "%s (%s)" % (self, self.location)
        else:
            return str(self)

    def __str__(self):
        try:
            version = getattr(self, "version", None)
        except ValueError:
            version = None
        version = version or "[unknown version]"
        return "%s %s" % (self.project_name, version)

    def __getattr__(self, attr):
        """Delegate all unrecognized public attributes to .metadata provider"""
        if attr.startswith("_"):
            raise AttributeError(attr)
        return getattr(self._provider, attr)

    def __dir__(self):
        return list(
            set(super(Distribution, self).__dir__())
            | set(attr for attr in self._provider.__dir__() if not attr.startswith("_"))
        )

    if not hasattr(object, "__dir__"):
        # python 2.7 not supported
        del __dir__

    @property
    def extras(self):
        return [dep for dep in self._dep_map if dep]


class DistInfoDistribution(Distribution):
    """
    Wrap an actual or potential sys.path entry
    w/metadata, .dist-info style.
    """

    PKG_INFO = "METADATA"

    @property
    def _parsed_pkg_info(self):
        """Parse and cache metadata"""
        try:
            return self._pkg_info
        except AttributeError:
            metadata = self.get_metadata(self.PKG_INFO)
            self._pkg_info = email.parser.Parser().parsestr(metadata)
            return self._pkg_info

    @property
    def _dep_map(self):
        try:
            return self.__dep_map
        except AttributeError:
            self.__dep_map = self._compute_dependencies()
            return self.__dep_map

    def _compute_dependencies(self):
        """Recompute this distribution's dependencies."""
        dm = self.__dep_map = {None: []}

        reqs = []
        # Including any condition expressions
        for req in self._parsed_pkg_info.get_all("Requires-Dist") or []:
            reqs.extend(parse_requirements(req))

        def reqs_for_extra(extra):
            for req in reqs:
                if not req.marker or req.marker.evaluate({"extra": extra}):
                    yield req

        common = frozenset(reqs_for_extra(None))
        dm[None].extend(common)

        for extra in self._parsed_pkg_info.get_all("Provides-Extra") or []:
            s_extra = safe_extra(extra.strip())
            dm[s_extra] = list(frozenset(reqs_for_extra(extra)) - common)

        return dm


class RequirementParseError(ValueError):
    def __str__(self):
        return " ".join(self.args)


def parse_requirements(strs):
    """Yield ``Requirement`` objects for each specification in `strs`

    `strs` must be a string, or a (possibly-nested) iterable thereof.
    """
    # create a steppable iterator, so we can handle \-continuations
    lines = iter(yield_lines(strs))

    for line in lines:
        # Drop comments -- a hash without a space may be in a URL.
        if " #" in line:
            line = line[: line.find(" #")]
        # If there is a line continuation, drop it, and append the next line.
        if line.endswith("\\"):
            line = line[:-2].strip()
            try:
                line += next(lines)
            except StopIteration:
                return
        yield Requirement(line)


class Requirement(packaging.requirements.Requirement):
    def __init__(self, requirement_string):
        """DO NOT CALL THIS UNDOCUMENTED METHOD; use Requirement.parse()!"""
        try:
            super(Requirement, self).__init__(requirement_string)
        except packaging.requirements.InvalidRequirement as e:
            raise RequirementParseError(str(e))
        self.unsafe_name = self.name
        project_name = safe_name(self.name)
        self.project_name, self.key = project_name, project_name.lower()
        self.extras = tuple(map(safe_extra, self.extras))
        self.hashCmp = (
            self.key,
            self.url,
            self.specifier,
            frozenset(self.extras),
            str(self.marker) if self.marker else None,
        )
        self.__hash = hash(self.hashCmp)

    def __eq__(self, other):
        return isinstance(other, Requirement) and self.hashCmp == other.hashCmp

    def __ne__(self, other):
        return not self == other

    def __contains__(self, item):
        if isinstance(item, Distribution):
            if item.key != self.key:
                return False

            item = item.version

        # Allow prereleases always in order to match the previous behavior of
        # this method. In the future this should be smarter and follow PEP 440
        # more accurately.
        return self.specifier.contains(item, prereleases=True)

    def __hash__(self):
        return self.__hash

    def __repr__(self):
        return "Requirement.parse(%r)" % str(self)

    @staticmethod
    def parse(s):
        (req,) = parse_requirements(s)
        return req


def split_sections(s):
    """Split a string or iterable thereof into (section, content) pairs

    Each ``section`` is a stripped version of the section header ("[section]")
    and each ``content`` is a list of stripped lines excluding blank lines and
    comment-only lines.  If there are any such lines before the first section
    header, they're returned in a first ``section`` of ``None``.
    """
    section = None
    content = []
    for line in yield_lines(s):
        if line.startswith("["):
            if line.endswith("]"):
                if section or content:
                    yield section, content
                section = line[1:-1].strip()
                content = []
            else:
                raise ValueError("Invalid section heading", line)
        else:
            content.append(line)

    # wrap up last segment
    yield section, content


# Silence the PEP440Warning by default, so that end users don't get hit by it
# randomly just because they use pkg_resources. We want to append the rule
# because we want earlier uses of filterwarnings to take precedence over this
# one.
warnings.filterwarnings("ignore", category=PEP440Warning, append=True)
