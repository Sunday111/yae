from __future__ import annotations


class YaeError(Exception):
    """Base class for expected, user-facing failures.

    These are reported by the CLI as a single clean message (no traceback);
    anything that is not a YaeError is treated as an unexpected bug and printed
    with a full traceback.
    """


class ProjectError(YaeError):
    """A project could not be located, or a requested target is missing/invalid."""


class FetchError(YaeError):
    """A dependency could not be fetched or an existing checkout could not be adopted."""


class ModuleGraphError(YaeError):
    """The resolved set of packages/modules is invalid (duplicates, cycles, missing deps)."""
