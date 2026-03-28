"""Phase 1 converted tests: plugin creation, save/reload, and Skyrim.esm stats.

Round-trip tests already live in test_roundtrip.py. These tests cover the
remaining Phase 1 manual-test scenarios: creating plugins from scratch,
saving to disk, reloading, and verifying field integrity.
"""

import struct
import pytest
from pathlib import Path

from esplib import Plugin, Record, SubRecord, FormID

from tests.conftest import find_skyrim_esm


# ---------------------------------------------------------------------------
# Plugin creation from scratch
# ---------------------------------------------------------------------------

class TestPluginCreation:
    """Test creating new plugins, saving, and reloading."""

    def test_create_empty_plugin(self, tmp_path):
        """An empty plugin should save and reload with correct header."""
        plugin = Plugin()
        plugin.header.version = 1.71
        plugin.header.is_esm = False

        path = tmp_path / "empty.esp"
        plugin.save(path)

        loaded = Plugin(path)
        assert loaded.header.version == pytest.approx(1.71, abs=0.01)
        assert not loaded.is_esm
        assert len(loaded.records) == 0

    def test_create_esm_flag(self, tmp_path):
        """ESM flag should survive save/reload."""
        plugin = Plugin()
        plugin.header.is_esm = True
        plugin.header.version = 1.71

        path = tmp_path / "test.esm"
        plugin.save(path)

        loaded = Plugin(path)
        assert loaded.is_esm

    def test_create_plugin_with_masters(self, tmp_path):
        """Master list should survive save/reload."""
        plugin = Plugin()
        plugin.header.version = 1.71
        plugin.header.masters = ['Skyrim.esm', 'Update.esm']
        plugin.header.master_sizes = [0, 0]

        path = tmp_path / "with_masters.esp"
        plugin.save(path)

        loaded = Plugin(path)
        assert loaded.header.masters == ['Skyrim.esm', 'Update.esm']


class TestGMSTOverridePlugin:
    """Test creating a GMST override plugin (from Phase 1 manual test)."""

    def test_gmst_override_save_reload(self, tmp_path):
        """Create a GMST override, save, reload, verify field values."""
        plugin = Plugin()
        plugin.header.is_esm = False
        plugin.header.masters = ['Skyrim.esm']
        plugin.header.master_sizes = [0]
        plugin.header.version = 1.71

        # Override fJumpHeightMin (FormID 0x00066C5B in Skyrim.esm)
        gmst = Record('GMST', FormID(0x00066C5B), 0)
        gmst.timestamp = 0
        gmst.version = 44
        gmst.version_control_info = 0
        gmst.add_subrecord('EDID', b'fJumpHeightMin\x00')
        data_sr = gmst.add_subrecord('DATA')
        data_sr.data = struct.pack('<f', 500.0)

        plugin.add_record(gmst)

        path = tmp_path / 'gmst_test.esp'
        plugin.save(path)

        # Reload and verify
        loaded = Plugin(path)
        assert loaded.header.masters == ['Skyrim.esm']
        assert len(loaded.records) == 1

        rec = loaded.records[0]
        assert rec.signature == 'GMST'
        assert rec.form_id.value == 0x00066C5B
        assert rec.editor_id == 'fJumpHeightMin'

        data = rec.get_subrecord('DATA')
        value = struct.unpack('<f', data.data)[0]
        assert value == pytest.approx(500.0)

    def test_gmst_int_override(self, tmp_path):
        """Integer GMST override round-trips correctly."""
        plugin = Plugin()
        plugin.header.masters = ['Skyrim.esm']
        plugin.header.master_sizes = [0]
        plugin.header.version = 1.71

        gmst = Record('GMST', FormID(0x100), 0)
        gmst.version = 44
        gmst.add_subrecord('EDID', b'iTestSetting\x00')
        gmst.add_subrecord('DATA', struct.pack('<i', 42))
        plugin.add_record(gmst)

        path = tmp_path / 'gmst_int.esp'
        plugin.save(path)

        loaded = Plugin(path)
        rec = loaded.records[0]
        assert rec.editor_id == 'iTestSetting'
        assert struct.unpack('<i', rec.get_subrecord('DATA').data)[0] == 42


class TestMultiRecordPlugin:
    """Test creating plugins with multiple records."""

    def test_multiple_records_same_type(self, tmp_path):
        """Multiple records of the same type group correctly."""
        plugin = Plugin()
        plugin.header.version = 1.71
        plugin.header.masters = ['Skyrim.esm']
        plugin.header.master_sizes = [0]

        for i in range(5):
            rec = Record('GMST', FormID(0x100 + i), 0)
            rec.version = 44
            rec.add_subrecord('EDID', f'fTest{i}\x00'.encode())
            rec.add_subrecord('DATA', struct.pack('<f', float(i)))
            plugin.add_record(rec)

        path = tmp_path / 'multi_gmst.esp'
        plugin.save(path)

        loaded = Plugin(path)
        assert len(loaded.records) == 5
        assert len(loaded.groups) == 1  # All in one GMST group

        for i, rec in enumerate(loaded.records):
            assert rec.editor_id == f'fTest{i}'

    def test_multiple_record_types(self, tmp_path):
        """Records of different types get separate groups."""
        plugin = Plugin()
        plugin.header.version = 1.71

        gmst = Record('GMST', FormID(0x100), 0)
        gmst.version = 44
        gmst.add_subrecord('EDID', b'fTest\x00')
        gmst.add_subrecord('DATA', struct.pack('<f', 1.0))
        plugin.add_record(gmst)

        glob = Record('GLOB', FormID(0x200), 0)
        glob.version = 44
        glob.add_subrecord('EDID', b'TestGlobal\x00')
        glob.add_subrecord('FNAM', bytes([ord('f')]))
        glob.add_subrecord('FLTV', struct.pack('<f', 0.0))
        plugin.add_record(glob)

        path = tmp_path / 'multi_type.esp'
        plugin.save(path)

        loaded = Plugin(path)
        assert len(loaded.records) == 2
        assert len(loaded.groups) == 2
        assert loaded.get_record_by_editor_id('fTest') is not None
        assert loaded.get_record_by_editor_id('TestGlobal') is not None


# ---------------------------------------------------------------------------
# Skyrim.esm statistics / structural validation
# ---------------------------------------------------------------------------

class TestSkyrimStats:
    """Validate structural properties of Skyrim.esm."""

    @pytest.fixture(scope='class')
    def skyrim(self):
        esm_path = find_skyrim_esm()
        if not esm_path:
            pytest.skip("Skyrim.esm not found")
        return Plugin(esm_path)

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_has_many_records(self, skyrim):
        """Skyrim.esm has tens of thousands of records."""
        assert len(skyrim.records) > 50000

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_has_multiple_groups(self, skyrim):
        """Skyrim.esm has many top-level groups."""
        assert len(skyrim.groups) > 20

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_is_localized(self, skyrim):
        """Skyrim.esm is a localized plugin."""
        assert skyrim.is_localized

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_is_esm(self, skyrim):
        """Skyrim.esm has ESM flag set."""
        assert skyrim.is_esm

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_has_compressed_records(self, skyrim):
        """Skyrim.esm contains compressed records (e.g. NAVM)."""
        compressed = [r for r in skyrim.records if r.is_compressed]
        assert len(compressed) > 0

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_statistics_returns_expected_keys(self, skyrim):
        """get_statistics() returns all expected fields."""
        stats = skyrim.get_statistics()
        assert 'total_records' in stats
        assert 'record_types' in stats
        assert 'masters' in stats
        assert 'version' in stats
        assert stats['is_localized'] is True

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_common_record_types_present(self, skyrim):
        """Skyrim.esm contains expected record types."""
        stats = skyrim.get_statistics()
        types = stats['record_types']
        for sig in ['WEAP', 'ARMO', 'NPC_', 'GMST', 'KYWD', 'ALCH']:
            assert sig in types, f"{sig} not found in Skyrim.esm"
            assert types[sig] > 0

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_header_version(self, skyrim):
        """Skyrim SE version is 1.71."""
        assert skyrim.header.version == pytest.approx(1.71, abs=0.01)
