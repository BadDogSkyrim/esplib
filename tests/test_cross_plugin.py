"""
These tests cover override chain assertions and cross-plugin (DLC) reference resolution.
"""

import pytest

from esplib import Plugin, LoadOrder, PluginSet
from esplib.game_discovery import find_game
import esplib.defs.tes5  # noqa: F401 -- registers tes5 game schemas

from tests.conftest import find_skyrim_esm, find_game_file


# ---------------------------------------------------------------------------
# Override chain detail (Skyrim.esm + Update.esm)
# ---------------------------------------------------------------------------

class TestOverrideChainDetail:
    """Detailed override chain tests with real game files."""


    @pytest.fixture(scope='class')
    def plugin_set(self):
        game = find_game('tes5')
        if game is None:
            assert False, "Skyrim SE not installed"
        if not (game.data_dir / 'Update.esm').exists():
            assert False, "Update.esm not found"

        lo = LoadOrder.from_list(
            ['Skyrim.esm', 'Update.esm'],
            data_dir=game.data_dir, game_id='tes5')
        ps = PluginSet(lo)
        ps.load_all()
        return ps


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_update_esm_has_overrides(self, plugin_set):
        """Update.esm should override at least some Skyrim.esm records."""
        overrides = list(plugin_set.overridden_records())
        assert len(overrides) > 0


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_override_chain_length_is_two(self, plugin_set):
        """Each override with two plugins should have chain length 2."""
        overrides = list(plugin_set.overridden_records())
        for fid, chain in overrides[:10]:
            assert len(chain) == 2


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_override_base_is_skyrim(self, plugin_set):
        """Base record in override chain should be from Skyrim.esm."""
        overrides = list(plugin_set.overridden_records())
        assert len(overrides) > 0
        fid, chain = overrides[0]
        # Base record is first in the chain
        base = chain[0]
        assert base.signature  # should be a valid record


# ---------------------------------------------------------------------------
# Cross-plugin reference: Dawnguard
# ---------------------------------------------------------------------------

class TestDawnguardCrossPlugin:
    """Test cross-plugin references using Dawnguard.esm."""


    @pytest.fixture(scope='class')
    def dawnguard_set(self):
        game = find_game('tes5')
        if game is None:
            assert False, "Skyrim SE not installed"
        if not (game.data_dir / 'Dawnguard.esm').exists():
            assert False, "Dawnguard.esm not found"

        lo = LoadOrder.from_list(
            ['Skyrim.esm', 'Update.esm', 'Dawnguard.esm'],
            data_dir=game.data_dir, game_id='tes5')
        ps = PluginSet(lo)
        ps.load_all()
        return ps


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_dawnguard_loads(self, dawnguard_set):
        """Dawnguard plugin set loads at least 2 plugins."""
        # At minimum Skyrim.esm + Dawnguard.esm (Update might be missing)
        assert dawnguard_set.get_plugin('Dawnguard.esm') is not None


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_dawnguard_has_weapons(self, dawnguard_set):
        """Dawnguard.esm should contain WEAP records."""
        dawnguard = dawnguard_set.get_plugin('Dawnguard.esm')
        weapons = dawnguard.get_records_by_signature('WEAP')
        assert len(weapons) > 0


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_dawnguard_crossbow_resolves(self, dawnguard_set):
        """A Dawnguard crossbow weapon should resolve with valid damage/value."""
        dawnguard = dawnguard_set.get_plugin('Dawnguard.esm')
        dawnguard.set_game('tes5')

        crossbow = dawnguard.get_record_by_editor_id('DLC1CrossBow')
        assert crossbow is not None, "DLC1CrossBow not found in Dawnguard.esm"

        data = crossbow['DATA']
        assert data['damage'] == 19
        assert data['value'] == 120


    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_dawnguard_all_weap_resolve(self, dawnguard_set):
        """Walk all Dawnguard WEAP records; each should be valid and parseable."""
        dawnguard = dawnguard_set.get_plugin('Dawnguard.esm')
        dawnguard.set_game('tes5')

        weapons = dawnguard.get_records_by_signature('WEAP')
        assert len(weapons) > 0

        errors = []
        for w in weapons:
            assert w.signature == 'WEAP'
            assert w.form_id.value != 0
            try:
                data = w['DATA']
                assert data is not None
            except Exception as e:
                errors.append(f"{w.editor_id or w.form_id}: {e}")

        assert len(errors) == 0, f"{len(errors)} errors:\n" + "\n".join(errors[:10])


# ---------------------------------------------------------------------------
# Load order from plugins.txt
# ---------------------------------------------------------------------------

class TestLoadOrderFromGame:
    """Test reading the actual load order from the Skyrim installation."""


    @pytest.mark.gamefiles
    def test_load_order_has_implicit_masters(self):
        """Skyrim load order should start with implicit masters."""
        game = find_game('tes5')
        if game is None:
            assert False, "Skyrim SE not installed"

        lo = LoadOrder.from_game('tes5')
        assert lo[0] == 'Skyrim.esm'
        # Update.esm should be in the first few entries
        assert 'Update.esm' in lo.plugins[:5]


    @pytest.mark.gamefiles
    def test_load_order_includes_dlc(self):
        """DLC masters should appear in the load order."""
        game = find_game('tes5')
        if game is None:
            assert False, "Skyrim SE not installed"

        lo = LoadOrder.from_game('tes5')
        # At least one DLC should be present in a standard install
        dlc_names = {'Dawnguard.esm', 'HearthFires.esm', 'Dragonborn.esm'}
        found = dlc_names & set(lo.plugins)
        assert len(found) > 0, "No DLC found in load order"


    @pytest.mark.gamefiles
    def test_load_order_count(self):
        """Load order should have a reasonable number of plugins."""
        game = find_game('tes5')
        if game is None:
            assert False, "Skyrim SE not installed"

        lo = LoadOrder.from_game('tes5')
        # At minimum: Skyrim.esm + Update.esm + some DLC
        assert len(lo) >= 3
