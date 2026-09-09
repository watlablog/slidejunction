"""Shared canonical reference syntax for parsing and source-anchor validation."""

import re

_CONFIG_REF_PREFIX = "<!-- sj:ref="
_CONFIG_REF_SUFFIX = " -->"
_VALID_CONFIG_REF = re.compile(
    rf"^{re.escape(_CONFIG_REF_PREFIX)}([1-9][0-9]*){re.escape(_CONFIG_REF_SUFFIX)}$"
)
_INLINE_FORMAT_OPEN = re.compile(r"<sj-format ref[ \t]*=[ \t]*([1-9][0-9]*)>")
_INLINE_FORMAT_CLOSE = "</sj-format>"


def _format_config_ref_marker(ref_id: int) -> str:
    """Format an already validated positive ID as a canonical block marker."""
    return f"{_CONFIG_REF_PREFIX}{ref_id}{_CONFIG_REF_SUFFIX}"
