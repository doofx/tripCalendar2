"""Application version and build stamp.

The version number and the timestamp of every change are recorded in three
places so they survive independently of each other:

* here, as the version the running code was built from;
* in ``CHANGELOG.md``, as the human-readable history of releases;
* in the saved XML document, as ``appVersion`` / ``savedAt`` / ``revision``
  plus a rolling ``<history>`` of the changes made to that document.
"""

from __future__ import annotations

from datetime import datetime, timezone

__version__ = "1.0.0"

#: When this version of the application was cut (UTC, ISO-8601).
BUILD_TIMESTAMP = "2026-09-06T00:00:00+00:00"

#: Version of the on-disk XML layout. Bump when the schema changes shape.
SCHEMA_VERSION = 1


def utc_now() -> datetime:
    """Current time as an aware UTC datetime (seconds resolution)."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_now_iso() -> str:
    """Current time as an ISO-8601 string, used for change timestamps."""
    return utc_now().isoformat()


def version_banner() -> str:
    return f"v{__version__} (built {BUILD_TIMESTAMP[:10]})"
