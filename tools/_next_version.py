"""Custom versioningit next-version method.

When the last tag is a pre-release (RC, alpha, beta), returns the base release
version unchanged, so that dev versions stay in the same epoch throughout the
entire RC cycle (e.g. ``4.14.0.dev...``) rather than bumping to the next minor
version (``4.15.0.dev...``).

For production tags, the minor version is bumped as usual.

Example outcomes:
  last tag v4.13.0  -> next_version = 4.14.0  -> dev: 4.14.0.dev20241001...
  last tag v4.14.0rc1 -> next_version = 4.14.0  -> dev: 4.14.0.dev20241015...
  last tag v4.14.0rc2 -> next_version = 4.14.0  -> dev: 4.14.0.dev20241020...
  last tag v4.14.0  -> next_version = 4.15.0  -> dev: 4.15.0.dev20241025...
"""

from packaging.version import Version


def next_version(*, version: str, **_kwargs: object) -> str:
    v = Version(version)
    if v.pre is not None:
        # Pre-release tag (rc/alpha/beta): keep the same base release so dev
        # versions stay as e.g. 4.14.0.dev... across the whole RC cycle.
        return ".".join(str(x) for x in v.release)
    major, minor, *_ = v.release
    return f"{major}.{minor + 1}.0"
