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
    def from_game(cls, game_id: str) -> 'LoadOrder':
        """Load the active load order from the game's plugins.txt."""
        game = find_game(game_id)
        if game is None:
            raise FileNotFoundError(f"Game not found: {game_id}")

        plugins_txt = game.plugins_txt()
        if plugins_txt is None:
            raise FileNotFoundError(
                f"plugins.txt not found for {game.name}")

        plugins = cls._parse_plugins_txt(plugins_txt, game_id)
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
    def _parse_plugins_txt(cls, path: Path, game_id: str) -> List[str]:
        """Parse plugins.txt into an ordered list of active plugin names.

        Format:
          # comments
          *active_plugin.esp     (active, loaded by game)
          inactive_plugin.esp    (inactive, not loaded)

        We include inactive plugins too -- caller can filter if needed.
        Implicit masters are prepended.
        """
        plugins = []

        # Add implicit masters first
        implicits = cls._IMPLICIT_MASTERS.get(game_id, [])
        plugins.extend(implicits)

        text = path.read_text(encoding='utf-8', errors='replace')
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Strip active marker
            name = line.lstrip('*').strip()

            # Skip if it's an implicit master (already added)
            if name.lower() in [m.lower() for m in implicits]:
                continue

            plugins.append(name)

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
