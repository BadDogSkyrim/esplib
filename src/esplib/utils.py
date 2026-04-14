"""Utility classes and functions for esplib."""

import struct
import zlib
from typing import Union, List, Optional
from .exceptions import FormIDError, ParseError


class BaseFormID:
    """Common base for all FormID types.

    Use for isinstance checks when either LocalFormID or AbsoluteFormID
    is acceptable.
    """

    __slots__ = ('_value',)

    def __init__(self, value: int):
        if not isinstance(value, int):
            raise FormIDError(f"FormID must be an integer, got {type(value)}")
        if value < 0 or value > 0xFFFFFFFF:
            raise FormIDError(f"FormID out of range: 0x{value:08X}")
        self._value = value

    @property
    def value(self) -> int:
        return self._value

    @property
    def object_index(self) -> int:
        return self._value & 0x00FFFFFF

    def __str__(self) -> str:
        fi = (self._value >> 24) & 0xFF
        if fi == 0xFE:
            esl_index = (self._value >> 12) & 0xFFF
            object_index = self._value & 0xFFF
            return f"[FE:{esl_index:03X}] {object_index:06X}"
        else:
            return f"[{fi:02X}] {self.object_index:06X}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}(0x{self._value:08X})"

    def __eq__(self, other) -> bool:
        if type(self) is type(other):
            return self._value == other._value
        if isinstance(other, BaseFormID):
            return False  # cross-type: never equal
        if isinstance(other, int):
            return self._value == other
        return False

    def __hash__(self) -> int:
        return hash(self._value)

    def __int__(self) -> int:
        return self._value


class LocalFormID(BaseFormID):
    """FormID as stored on disk — file_index indexes into a plugin's master list.

    Meaningless without knowing which plugin it belongs to.
    """

    __slots__ = ()

    @property
    def file_index(self) -> int:
        return (self._value >> 24) & 0xFF

    @classmethod
    def from_string(cls, s: str) -> 'LocalFormID':
        s = s.strip()
        if s.startswith('[') and '] ' in s:
            bracket_part, object_part = s.split('] ', 1)
            bracket_content = bracket_part[1:]
            if ':' in bracket_content:
                file_part, esl_part = bracket_content.split(':', 1)
                file_index = int(file_part, 16)
                esl_index = int(esl_part, 16)
                object_index = int(object_part, 16)
                if file_index == 0xFE:
                    value = (0xFE << 24) | ((esl_index & 0xFFF) << 12) | (object_index & 0xFFF)
                else:
                    raise FormIDError(f"Invalid ESL FormID format: {s}")
            else:
                file_index = int(bracket_content, 16)
                object_index = int(object_part, 16)
                value = (file_index << 24) | object_index
        else:
            if s.startswith(('0x', '0X')):
                s = s[2:]
            elif s.startswith('$'):
                s = s[1:]
            value = int(s, 16)
        return cls(value)

    def to_load_order_form_id(self, load_order_index: int) -> 'AbsoluteFormID':
        if load_order_index < 0 or load_order_index > 0xFF:
            raise FormIDError(f"Load order index out of range: {load_order_index}")
        return AbsoluteFormID((load_order_index << 24) | self.object_index)

    def is_esl_form_id(self) -> bool:
        return self.file_index == 0xFE

    def get_esl_index(self) -> Optional[int]:
        if self.is_esl_form_id():
            return (self._value >> 12) & 0xFFF
        return None


# Backward compatibility alias
FormID = LocalFormID


class AbsoluteFormID(BaseFormID):
    """FormID resolved to load-order space — load_index is the plugin's
    position in the load order.

    Self-contained.  Can be used directly as a key in PluginSet's override
    index without needing to know the source plugin.
    """

    __slots__ = ()

    @property
    def load_index(self) -> int:
        return (self._value >> 24) & 0xFF


class BinaryReader:
    """Sequential binary data reader."""

    def __init__(self, data: bytes):
        self.data = data
        self.position = 0

    def read_bytes(self, count: int) -> bytes:
        if self.position + count > len(self.data):
            raise ParseError(f"Attempted to read {count} bytes at position {self.position}, "
                             f"but only {len(self.data) - self.position} bytes available")
        result = self.data[self.position:self.position + count]
        self.position += count
        return result

    def read_uint8(self) -> int:
        return struct.unpack('<B', self.read_bytes(1))[0]

    def read_uint16(self) -> int:
        return struct.unpack('<H', self.read_bytes(2))[0]

    def read_uint32(self) -> int:
        return struct.unpack('<I', self.read_bytes(4))[0]

    def read_int32(self) -> int:
        return struct.unpack('<i', self.read_bytes(4))[0]

    def read_float(self) -> float:
        return struct.unpack('<f', self.read_bytes(4))[0]

    def read_string(self, length: Optional[int] = None, encoding: str = 'cp1252') -> str:
        if length is not None:
            data = self.read_bytes(length)
            null_pos = data.find(b'\x00')
            if null_pos >= 0:
                data = data[:null_pos]
        else:
            start_pos = self.position
            while self.position < len(self.data) and self.data[self.position] != 0:
                self.position += 1
            data = self.data[start_pos:self.position]
            if self.position < len(self.data):
                self.position += 1
        return data.decode(encoding, errors='replace')

    def read_lstring(self, encoding: str = 'cp1252') -> str:
        length = self.read_uint16()
        if length == 0:
            return ""
        data = self.read_bytes(length)
        return data.decode(encoding, errors='replace')

    def read_form_id(self) -> 'FormID':
        return FormID(self.read_uint32())

    def seek(self, position: int) -> None:
        if position < 0 or position > len(self.data):
            raise ValueError(f"Position {position} out of range")
        self.position = position

    def tell(self) -> int:
        return self.position

    def remaining(self) -> int:
        return len(self.data) - self.position

    def at_end(self) -> bool:
        return self.position >= len(self.data)


class BinaryWriter:
    """Sequential binary data writer."""

    def __init__(self):
        self.data = bytearray()

    def write_bytes(self, data: bytes) -> None:
        self.data.extend(data)

    def write_uint8(self, value: int) -> None:
        self.data.extend(struct.pack('<B', value))

    def write_uint16(self, value: int) -> None:
        self.data.extend(struct.pack('<H', value))

    def write_uint32(self, value: int) -> None:
        self.data.extend(struct.pack('<I', value))

    def write_int32(self, value: int) -> None:
        self.data.extend(struct.pack('<i', value))

    def write_float(self, value: float) -> None:
        self.data.extend(struct.pack('<f', value))

    def write_string(self, value: str, encoding: str = 'cp1252',
                     null_terminate: bool = True) -> None:
        encoded = value.encode(encoding, errors='replace')
        self.data.extend(encoded)
        if null_terminate:
            self.data.append(0)

    def write_lstring(self, value: str, encoding: str = 'cp1252') -> None:
        encoded = value.encode(encoding, errors='replace')
        self.write_uint16(len(encoded))
        self.data.extend(encoded)

    def write_form_id(self, form_id: Union[BaseFormID, int]) -> None:
        if isinstance(form_id, BaseFormID):
            self.write_uint32(form_id.value)
        else:
            self.write_uint32(form_id)

    def get_bytes(self) -> bytes:
        return bytes(self.data)

    def size(self) -> int:
        return len(self.data)


def calculate_crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def decompress_zlib(data: bytes) -> bytes:
    try:
        return zlib.decompress(data)
    except zlib.error as e:
        raise ParseError(f"Failed to decompress zlib data: {e}")


def compress_zlib(data: bytes, level: int = 6) -> bytes:
    return zlib.compress(data, level)
