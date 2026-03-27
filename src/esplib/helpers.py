"""Convenience helpers for common record operations.

FormList (FLST) and Global Variable (GLOB) helpers used by the Furrifier
and other automation tools.
"""

import struct
from typing import List, Optional, Union
from .record import Record, SubRecord
from .utils import FormID


# ---------------------------------------------------------------------------
# FormList (FLST) helpers
# ---------------------------------------------------------------------------

def flst_forms(record: Record) -> List[FormID]:
    """Get all FormIDs in a FormList record."""
    return [FormID(sr.get_uint32()) for sr in record.subrecords
            if sr.signature == 'LNAM']


def flst_contains(record: Record, form_id: Union[FormID, int]) -> bool:
    """Check if a FormList contains a specific FormID."""
    target = form_id.value if isinstance(form_id, FormID) else form_id
    return any(sr.get_uint32() == target for sr in record.subrecords
               if sr.signature == 'LNAM')


def flst_add(record: Record, form_id: Union[FormID, int]) -> None:
    """Append a FormID to a FormList (no dedup -- caller checks if needed)."""
    fid = form_id if isinstance(form_id, FormID) else FormID(form_id)
    record.add_subrecord('LNAM', struct.pack('<I', fid.value))


def flst_remove(record: Record, form_id: Union[FormID, int]) -> bool:
    """Remove the first occurrence of a FormID from a FormList.

    Returns True if found and removed, False otherwise.
    """
    target = form_id.value if isinstance(form_id, FormID) else form_id
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
                 new_form_id: Union[FormID, int]) -> Record:
    """Copy a GLOB record with a new EditorID and FormID."""
    new = record.copy()
    new.form_id = FormID(new_form_id) if isinstance(new_form_id, int) else new_form_id
    new.editor_id = new_editor_id
    return new
