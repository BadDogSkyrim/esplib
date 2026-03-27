"""Context object passed during schema resolution."""

from dataclasses import dataclass, field
from typing import List, Optional, Any


@dataclass
class EspContext:
    """Carries record-level context needed by schema resolution.

    Passed to from_bytes() methods so that conditional definitions
    (EspUnion deciders) can inspect record state.
    """
    # Record flags (e.g. compressed flag, etc.)
    flags: int = 0
    # Record's form version (from the version field in the record header)
    form_version: int = 0
    # Plugin master list (for FormID resolution display)
    masters: List[str] = field(default_factory=list)
    # Game identifier ('tes5', 'fo4', 'sf1')
    game: str = ''
    # Parent record signature (e.g. 'WEAP', 'NPC_')
    record_signature: str = ''
    # Arbitrary extra data that deciders can use
    extra: dict = field(default_factory=dict)
