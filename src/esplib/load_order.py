"""Load order management for Bethesda plugins."""

from pathlib import Path
from typing import List, Optional, Union
from .game_discovery import find_game, GameInstall


class LoadOrder:
    """Represents an ordered list of plugins to load.

    Each entry is a (plugin_name, active) tuple. Active plugins have '*'
    prefix in plugins.txt. The implicit masters (game ESM files) are
    always loaded first even if not listed.
    """

    # Implicit masters per game that are always loaded first
    _IMPLICIT_MASTERS = {
        'tes5': [
            'Skyrim.esm', 'Update.esm', 'Dawnguard.esm',
            'HearthFires.esm', 'Dragonborn.esm',
        ],
        'fo4': [
            'Fallout4.esm', 'DLCRobot.esm', 'DLCworkshop01.esm',
            'DLCCoast.esm', 'DLCworkshop02.esm', 'DLCworkshop03.esm',
            'DLCNukaWorld.esm',
        ],
        'sf1': [
            'Starfield.esm',
        ],
    }

    def __init__(self, plugins: List[str], data_dir: Optional[Path] = None,
                 game_id: str = ''):
        self.plugins = plugins
        self.data_dir = data_dir
        self.game_id = game_id

    @classmethod
    def from_game(cls, game_id: str,
                  active_only: bool = False) -> 'LoadOrder':
        """Load the load order from the game's plugins.txt.

        If active_only is True, only include plugins marked active
        (prefixed with '*') and implicit masters.

        Creation Club plugins listed in the game's .ccc file are
        inserted after the implicit masters, matching the game engine's
        load order.
        """
        game = find_game(game_id)
        if game is None:
            raise FileNotFoundError(f"Game not found: {game_id}")

        plugins_txt = game.plugins_txt()
        if plugins_txt is None:
            raise FileNotFoundError(
                f"plugins.txt not found for {game.name}")

        plugins = cls._parse_plugins_txt(
            plugins_txt, game_id, active_only=active_only,
            ccc_file=game.ccc_file(), data_dir=game.data_dir)
        return cls(plugins=plugins, data_dir=game.data_dir, game_id=game_id)

    @classmethod
    def from_list(cls, plugin_names: List[str],
                  data_dir: Union[str, Path, None] = None,
                  game_id: str = '') -> 'LoadOrder':
        """Create a load order from an explicit list of plugin filenames."""
        data_path = Path(data_dir) if data_dir else None
        return cls(plugins=list(plugin_names), data_dir=data_path,
                   game_id=game_id)

    @classmethod
    def _parse_plugins_txt(cls, path: Path, game_id: str,
                           active_only: bool = False,
                           ccc_file: Optional[Path] = None,
                           data_dir: Optional[Path] = None) -> List[str]:
        """Parse plugins.txt into an ordered list of plugin names.

        Format:
          # comments
          *active_plugin.esp     (active, loaded by game)
          inactive_plugin.esp    (inactive, not loaded)

        If active_only is True, only plugins prefixed with '*' are
        included (plus implicit masters which are always active).

        If ccc_file is provided, Creation Club plugins are inserted
        after implicit masters (only those that exist in data_dir).
        """
        plugins = []

        # Add implicit masters first
        implicits = cls._IMPLICIT_MASTERS.get(game_id, [])
        plugins.extend(implicits)

        # Add Creation Club plugins from .ccc file
        if ccc_file is not None:
            cc_text = ccc_file.read_text(encoding='utf-8', errors='replace')
            for line in cc_text.splitlines():
                name = line.strip()
                if not name:
                    continue
                # Only include CC plugins that exist on disk
                if data_dir and not (data_dir / name).exists():
                    continue
                if name.lower() not in [p.lower() for p in plugins]:
                    plugins.append(name)

        text = path.read_text(encoding='utf-8', errors='replace')
        already = {p.lower() for p in plugins}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            active = line.startswith('*')
            name = line.lstrip('*').strip()

            # Skip if already added (implicit master or CC plugin)
            if name.lower() in already:
                continue

            if active_only and not active:
                continue

            plugins.append(name)
            already.add(name.lower())

        return plugins

    def plugin_path(self, name: str) -> Optional[Path]:
        """Get the full path to a plugin file."""
        if self.data_dir:
            p = self.data_dir / name
            if p.exists():
                return p
        return None

    def index_of(self, name: str) -> int:
        """Get the load order index of a plugin (-1 if not found)."""
        name_lower = name.lower()
        for i, p in enumerate(self.plugins):
            if p.lower() == name_lower:
                return i
        return -1

    def __len__(self) -> int:
        return len(self.plugins)

    def __iter__(self):
        return iter(self.plugins)

    def __getitem__(self, index):
        return self.plugins[index]

    def __repr__(self) -> str:
        return f"LoadOrder({len(self.plugins)} plugins, game={self.game_id!r})"
