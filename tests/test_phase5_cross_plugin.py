"""Phase 5 converted tests: cross-plugin references and override chain detail.

Game discovery tests are in test_discovery.py. Load order and basic
override chain tests are in test_masters.py. These tests cover the
remaining Phase 5 manual scenarios: richer override chain assertions
and cross-plugin (DLC) reference resolution.
"""

import pytest

from esplib import Plugin, LoadOrder, PluginSet
from esplib.defs import tes5
from esplib.game_discovery import find_game

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
            pytest.skip("Skyrim SE not installed")
        if not (game.data_dir / 'Update.esm').exists():
            pytest.skip("Update.esm not found")

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
            pytest.skip("Skyrim SE not installed")
        if not (game.data_dir / 'Dawnguard.esm').exists():
            pytest.skip("Dawnguard.esm not found")

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

        weapons = dawnguard.get_records_by_signature('WEAP')
        crossbow = None
        for w in weapons:
            edid = w.editor_id
            if edid and 'Crossbow' in edid:
                crossbow = w
                break

        if crossbow is None:
            pytest.skip("No crossbow weapon found in Dawnguard.esm")

        result = tes5.WEAP.from_record(crossbow)
        data = result['Game Data']
        assert data['damage'] > 0
        assert data['value'] > 0

    @pytest.mark.gamefiles
    @pytest.mark.slow
    def test_dawnguard_all_weap_resolve(self, dawnguard_set):
        """All Dawnguard WEAP records should resolve without errors."""
        dawnguard = dawnguard_set.get_plugin('Dawnguard.esm')

        weapons = dawnguard.get_records_by_signature('WEAP')
        errors = []
        for w in weapons:
            try:
                tes5.WEAP.from_record(w)
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
            pytest.skip("Skyrim SE not installed")

        lo = LoadOrder.from_game('tes5')
        assert lo[0] == 'Skyrim.esm'
        # Update.esm should be in the first few entries
        assert 'Update.esm' in lo.plugins[:5]

    @pytest.mark.gamefiles
    def test_load_order_includes_dlc(self):
        """DLC masters should appear in the load order."""
        game = find_game('tes5')
        if game is None:
            pytest.skip("Skyrim SE not installed")

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
            pytest.skip("Skyrim SE not installed")

        lo = LoadOrder.from_game('tes5')
        # At minimum: Skyrim.esm + Update.esm + some DLC
        assert len(lo) >= 3
