"""Tests for game discovery."""

import pytest
from esplib.game_discovery import discover_games, find_game


class TestGameDiscovery:
    def test_discover_finds_games(self):
        """Should find at least one game on this machine."""
        games = discover_games()
        assert len(games) > 0, "No games found -- is Steam installed?"

    def test_find_skyrim(self):
        game = find_game('tes5')
        if game is None:
            pytest.skip("Skyrim SE not installed")
        assert game.data_dir.exists()
        assert (game.data_dir / 'Skyrim.esm').exists()
        assert game.app_data_dir is not None

    def test_find_fo4(self):
        game = find_game('fo4')
        if game is None:
            pytest.skip("Fallout 4 not installed")
        assert game.data_dir.exists()
        assert (game.data_dir / 'Fallout4.esm').exists()

    def test_find_nonexistent_game(self):
        assert find_game('morrowind_2077') is None

    def test_game_install_plugins_txt(self):
        game = find_game('tes5')
        if game is None:
            pytest.skip("Skyrim SE not installed")
        ptxt = game.plugins_txt()
        assert ptxt is not None
        assert ptxt.exists()
