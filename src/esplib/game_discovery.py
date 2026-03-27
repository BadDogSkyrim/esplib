"""Game discovery -- finds installed Bethesda games on disk."""

import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class GameInstall:
    """Information about an installed Bethesda game."""
    game_id: str        # 'tes5', 'fo4', 'sf1'
    name: str           # 'Skyrim Special Edition'
    data_dir: Path      # Path to the Data/ directory
    exe_path: Optional[Path] = None
    app_data_dir: Optional[Path] = None  # Local AppData dir for plugins.txt

    def plugins_txt(self) -> Optional[Path]:
        """Path to plugins.txt for this game."""
        if self.app_data_dir:
            p = self.app_data_dir / 'plugins.txt'
            if p.exists():
                return p
        return None

    def loadorder_txt(self) -> Optional[Path]:
        """Path to loadorder.txt for this game."""
        if self.app_data_dir:
            p = self.app_data_dir / 'loadorder.txt'
            if p.exists():
                return p
        return None


# Game definitions: (game_id, name, steam_folder_name, exe_name, appdata_folder_name)
_GAME_DEFS = [
    ('tes5', 'Skyrim Special Edition', 'Skyrim Special Edition',
     'SkyrimSE.exe', 'Skyrim Special Edition'),
    ('fo4', 'Fallout 4', 'Fallout 4',
     'Fallout4.exe', 'Fallout4'),
    ('sf1', 'Starfield', 'Starfield',
     'Starfield.exe', 'Starfield'),
]


def _find_steam_libraries() -> List[Path]:
    """Find all Steam library folders by parsing libraryfolders.vdf."""
    libraries = []

    # Common Steam install locations
    candidates = []
    if platform.system() == 'Windows':
        for drive in 'CDEFGH':
            candidates.append(Path(f'{drive}:/Steam'))
            candidates.append(Path(f'{drive}:/Program Files (x86)/Steam'))
            candidates.append(Path(f'{drive}:/Program Files/Steam'))
            candidates.append(Path(f'{drive}:/SteamLibrary'))
    else:
        home = Path.home()
        candidates.append(home / '.steam' / 'steam')
        candidates.append(home / '.local' / 'share' / 'Steam')

    for steam_dir in candidates:
        vdf = steam_dir / 'steamapps' / 'libraryfolders.vdf'
        if vdf.exists():
            try:
                text = vdf.read_text(encoding='utf-8', errors='replace')
                # Simple VDF parser: look for "path" values
                for line in text.splitlines():
                    line = line.strip()
                    if line.startswith('"path"'):
                        parts = line.split('"')
                        if len(parts) >= 4:
                            lib_path = Path(parts[3].replace('\\\\', '\\'))
                            if lib_path.exists():
                                libraries.append(lib_path)
            except OSError:
                pass

        # Also add the Steam dir itself as a library
        if (steam_dir / 'steamapps' / 'common').exists():
            if steam_dir not in libraries:
                libraries.append(steam_dir)

    return libraries


def _find_appdata_dir(appdata_folder_name: str) -> Optional[Path]:
    """Find the Local AppData directory for a game."""
    if platform.system() == 'Windows':
        local = os.environ.get('LOCALAPPDATA')
        if local:
            d = Path(local) / appdata_folder_name
            if d.exists():
                return d
    return None


def discover_games() -> List[GameInstall]:
    """Discover all installed Bethesda games.

    Scans Steam library folders for known game directories.
    """
    libraries = _find_steam_libraries()
    found = []

    for game_id, name, steam_folder, exe_name, appdata_name in _GAME_DEFS:
        for lib in libraries:
            game_dir = lib / 'steamapps' / 'common' / steam_folder
            data_dir = game_dir / 'Data'
            if data_dir.exists():
                exe_path = game_dir / exe_name
                if not exe_path.exists():
                    exe_path = None

                appdata = _find_appdata_dir(appdata_name)

                found.append(GameInstall(
                    game_id=game_id,
                    name=name,
                    data_dir=data_dir,
                    exe_path=exe_path,
                    app_data_dir=appdata,
                ))
                break  # Found this game, move to next

    return found


def find_game(game_id: str) -> Optional[GameInstall]:
    """Find a specific game by ID ('tes5', 'fo4', 'sf1')."""
    for game in discover_games():
        if game.game_id == game_id:
            return game
    return None
