"""Tests for string table support."""

import struct
import pytest

from esplib.strings import StringTable, StringTableManager


class TestStringTableSTRINGS:
    """Test .STRINGS format (null-terminated)."""

    def test_roundtrip(self):
        table = StringTable(StringTable.STRINGS)
        table.set(1, "Hello")
        table.set(2, "World")
        table.set(100, "Test String")

        data = table.to_bytes()
        table2 = StringTable.from_bytes(data, StringTable.STRINGS)

        assert len(table2) == 3
        assert table2.get(1) == "Hello"
        assert table2.get(2) == "World"
        assert table2.get(100) == "Test String"

    def test_empty_table(self):
        table = StringTable(StringTable.STRINGS)
        data = table.to_bytes()
        table2 = StringTable.from_bytes(data, StringTable.STRINGS)
        assert len(table2) == 0

    def test_empty_string(self):
        table = StringTable(StringTable.STRINGS)
        table.set(1, "")
        data = table.to_bytes()
        table2 = StringTable.from_bytes(data, StringTable.STRINGS)
        assert table2.get(1) == ""

    def test_special_characters(self):
        table = StringTable(StringTable.STRINGS)
        table.set(1, "Caf\xe9")  # cp1252 character
        data = table.to_bytes()
        table2 = StringTable.from_bytes(data, StringTable.STRINGS)
        assert table2.get(1) == "Caf\xe9"

    def test_byte_perfect_roundtrip(self):
        table = StringTable(StringTable.STRINGS)
        table.set(10, "Alpha")
        table.set(20, "Beta")
        data = table.to_bytes()
        data2 = StringTable.from_bytes(data, StringTable.STRINGS).to_bytes()
        assert data == data2


class TestStringTableDLSTRINGS:
    """Test .DLSTRINGS format (length-prefixed, no null terminator)."""

    def test_roundtrip(self):
        table = StringTable(StringTable.DLSTRINGS)
        table.set(1, "Description one")
        table.set(2, "Description two")

        data = table.to_bytes()
        table2 = StringTable.from_bytes(data, StringTable.DLSTRINGS)

        assert table2.get(1) == "Description one"
        assert table2.get(2) == "Description two"

    def test_byte_perfect_roundtrip(self):
        table = StringTable(StringTable.DLSTRINGS)
        table.set(5, "Hello")
        table.set(10, "World")
        data = table.to_bytes()
        data2 = StringTable.from_bytes(data, StringTable.DLSTRINGS).to_bytes()
        assert data == data2


class TestStringTableILSTRINGS:
    """Test .ILSTRINGS format (length-prefixed with null terminator)."""

    def test_roundtrip(self):
        table = StringTable(StringTable.ILSTRINGS)
        table.set(1, "Response one")
        table.set(2, "Response two")

        data = table.to_bytes()
        table2 = StringTable.from_bytes(data, StringTable.ILSTRINGS)

        assert table2.get(1) == "Response one"
        assert table2.get(2) == "Response two"

    def test_byte_perfect_roundtrip(self):
        table = StringTable(StringTable.ILSTRINGS)
        table.set(7, "Test")
        data = table.to_bytes()
        data2 = StringTable.from_bytes(data, StringTable.ILSTRINGS).to_bytes()
        assert data == data2


class TestStringTableOperations:
    """Test StringTable CRUD operations."""

    def test_set_and_get(self):
        table = StringTable()
        table.set(1, "test")
        assert table.get(1) == "test"
        assert table.get(999) is None

    def test_remove(self):
        table = StringTable()
        table.set(1, "test")
        assert table.remove(1)
        assert table.get(1) is None
        assert not table.remove(1)

    def test_contains(self):
        table = StringTable()
        table.set(1, "test")
        assert 1 in table
        assert 2 not in table

    def test_len(self):
        table = StringTable()
        assert len(table) == 0
        table.set(1, "a")
        table.set(2, "b")
        assert len(table) == 2

    def test_overwrite(self):
        table = StringTable()
        table.set(1, "original")
        table.set(1, "updated")
        assert table.get(1) == "updated"
        assert len(table) == 1


class TestStringTableManager:
    """Test StringTableManager."""

    def test_get_string_across_tables(self):
        mgr = StringTableManager()
        mgr.strings = StringTable(StringTable.STRINGS)
        mgr.dlstrings = StringTable(StringTable.DLSTRINGS)
        mgr.ilstrings = StringTable(StringTable.ILSTRINGS)

        mgr.strings.set(1, "Name")
        mgr.dlstrings.set(2, "Description")
        mgr.ilstrings.set(3, "Response")

        assert mgr.get_string(1) == "Name"
        assert mgr.get_string(2) == "Description"
        assert mgr.get_string(3) == "Response"
        assert mgr.get_string(999) is None

    def test_priority_order(self):
        """STRINGS table is checked first."""
        mgr = StringTableManager()
        mgr.strings = StringTable(StringTable.STRINGS)
        mgr.dlstrings = StringTable(StringTable.DLSTRINGS)

        mgr.strings.set(1, "from_strings")
        mgr.dlstrings.set(1, "from_dlstrings")

        assert mgr.get_string(1) == "from_strings"

    def test_empty_manager(self):
        mgr = StringTableManager()
        assert mgr.get_string(1) is None
