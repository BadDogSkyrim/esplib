"""Convenience helpers for common record operations.

FormList (FLST) and Global Variable (GLOB) helpers used by the Furrifier
and other automation tools.
"""

import struct
from typing import List, Optional, Union
from .record import Record, SubRecord
from .utils import FormID, BaseFormID


# ---------------------------------------------------------------------------
# FormList (FLST) helpers
# ---------------------------------------------------------------------------

def flst_forms(record: Record) -> List[FormID]:
    """Get all FormIDs in a FormList record.

    If the record's plugin is part of a PluginSet, FormIDs are
    normalized to load-order space so callers don't need to know
    which plugin's master-list they came from.
    """
    plugin = record.plugin
    normalize = (plugin is not None and plugin.plugin_set is not None)
    result = []
    for sr in record.subrecords:
        if sr.signature == 'LNAM':
            fid = FormID(sr.get_uint32())
            if normalize:
                fid = plugin.normalize_form_id(fid)
            result.append(fid)
    return result


def flst_contains(record: Record, form_id: Union[BaseFormID, int]) -> bool:
    """Check if a FormList contains a specific FormID."""
    target = form_id.value if isinstance(form_id, BaseFormID) else form_id
    return any(sr.get_uint32() == target for sr in record.subrecords
               if sr.signature == 'LNAM')


def flst_add(record: Record, form_id: Union[BaseFormID, int]) -> None:
    """Append a FormID to a FormList (no dedup -- caller checks if needed)."""
    fid = form_id if isinstance(form_id, BaseFormID) else FormID(form_id)
    record.add_subrecord('LNAM', struct.pack('<I', fid.value))


def flst_remove(record: Record, form_id: Union[BaseFormID, int]) -> bool:
    """Remove the first occurrence of a FormID from a FormList.

    Returns True if found and removed, False otherwise.
    """
    target = form_id.value if isinstance(form_id, BaseFormID) else form_id
    for sr in record.subrecords:
        if sr.signature == 'LNAM' and sr.get_uint32() == target:
            record.remove_subrecord(sr)
            return True
    return False


# ---------------------------------------------------------------------------
# Global Variable (GLOB) helpers
# ---------------------------------------------------------------------------

def glob_value(record: Record) -> float:
    """Read a GLOB record's value (FLTV subrecord)."""
    fltv = record.get_subrecord('FLTV')
    if fltv is None:
        return 0.0
    return struct.unpack('<f', fltv.data)[0]


def glob_set_value(record: Record, value: float) -> None:
    """Set a GLOB record's value (FLTV subrecord)."""
    fltv = record.get_subrecord('FLTV')
    data = struct.pack('<f', value)
    if fltv is not None:
        fltv.data = data
    else:
        record.add_subrecord('FLTV', data)
    record.modified = True


def glob_copy_as(record: Record, new_editor_id: str,
                 new_form_id: Union[BaseFormID, int]) -> Record:
    """Copy a GLOB record with a new EditorID and FormID."""
    new = record.copy()
    new.form_id = FormID(new_form_id) if isinstance(new_form_id, int) else new_form_id
    new.editor_id = new_editor_id
    return new


# ---------------------------------------------------------------------------
# Race (RACE) helpers
# ---------------------------------------------------------------------------

def race_height(record: Record, female: bool = False) -> float:
    """Read a RACE record's height multiplier (Fallout 4).

    FO4 RACE ``DATA`` begins with two float32s -- male height (offset 0) and
    female height (offset 4). The rest of DATA is a large, version-dependent
    struct that esplib keeps opaque, so this reads just the two leading floats.

    The Creation Kit scales an actor's baked FaceGen skeleton by this factor, so
    facegen tools need it to place nif-local bones (e.g. cloth-physics hair bones
    that aren't in the actor skeleton) in the scaled actor frame.

    Only FO4's layout is supported -- Skyrim stores height elsewhere in DATA --
    so this returns 1.0 for a non-FO4 record (or when DATA is absent/too short).
    """
    if record is None:
        return 1.0
    plugin = record.plugin
    registry = getattr(plugin, '_game_registry', None) if plugin else None
    if registry is not None and getattr(registry, 'game_id', None) != 'fo4':
        return 1.0
    data = record.get_subrecord('DATA')
    if data is None or data.size < 8:
        return 1.0
    return data.get_float(4 if female else 0)
