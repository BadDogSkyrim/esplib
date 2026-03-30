"""Game discovery -- finds installed Bethesda games on disk.

Uses the Windows registry to find Steam, then parses Steam's library
folders and app manifests to locate game installs. Falls back to
scanning common paths on non-Windows or if the registry isn't available.
"""

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


# Game definitions: (game_id, name, steam_appid, steam_folder_name,
#                    exe_name, appdata_folder_name)
_GAME_DEFS = [
    ('tes5', 'Skyrim Special Edition', '489830',
     'Skyrim Special Edition', 'SkyrimSE.exe', 'Skyrim Special Edition'),
    ('tes5le', 'Skyrim', '72850',
     'Skyrim', 'TESV.exe', 'Skyrim'),
    ('fo4', 'Fallout 4', '377160',
     'Fallout 4', 'Fallout4.exe', 'Fallout4'),
    ('sf1', 'Starfield', '1716740',
     'Starfield', 'Starfield.exe', 'Starfield'),
]

# Bethesda Launcher registry paths (game_id -> registry key)
_BETHESDA_REGISTRY = {
    'tes5': r'SOFTWARE\Bethesda Softworks\Skyrim Special Edition',
    'fo4': r'SOFTWARE\Bethesda Softworks\Fallout4',
}


def _find_steam_path() -> Optional[Path]:
    """Find Steam installation path from the Windows registry."""
    if platform.system() != 'Windows':
        return None

    try:
        import winreg
    except ImportError:
        return None

    for hive, key_path, value_name in [
        (winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
        (winreg.HKEY_CURRENT_USER, r'Software\WOW6432Node\Valve\Steam', 'SteamPath'),
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath'),
        (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Valve\Steam', 'InstallPath'),
    ]:
        try:
            with winreg.OpenKey(hive, key_path) as k:
                return Path(winreg.QueryValueEx(k, value_name)[0])
        except OSError:
            continue

    return None


def _parse_steam_libraries(steam_path: Path) -> List[Path]:
    """Parse libraryfolders.vdf to find all Steam library paths."""
    libraries = []
    vdf = steam_path / 'steamapps' / 'libraryfolders.vdf'

    if vdf.exists():
        try:
            text = vdf.read_text(encoding='utf-8', errors='replace')
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

    # Always include the Steam dir itself
    if steam_path not in libraries:
        libraries.append(steam_path)

    return libraries


def _find_game_in_manifest(library: Path, appid: str) -> Optional[Path]:
    """Check a Steam library for a game by parsing its app manifest."""
    manifest = library / 'steamapps' / f'appmanifest_{appid}.acf'
    if not manifest.exists():
        return None

    try:
        with open(manifest, encoding='utf-8', errors='ignore') as f:
            for line in f:
                if '"installdir"' in line:
                    installdir = line.split('"')[-2]
                    game_path = library / 'steamapps' / 'common' / installdir
                    if game_path.exists():
                        return game_path
    except OSError:
        pass

    return None


def _find_steam_libraries_fallback() -> List[Path]:
    """Find Steam libraries by scanning common filesystem paths.

    Used when the registry is unavailable (non-Windows, or registry
    access fails).
    """
    libraries = []

    if platform.system() == 'Windows':
        for drive in 'CDEFGH':
            for subdir in ['Steam', 'Program Files (x86)/Steam',
                           'Program Files/Steam', 'SteamLibrary']:
                candidate = Path(f'{drive}:/{subdir}')
                if (candidate / 'steamapps').exists():
                    libraries.append(candidate)
    else:
        home = Path.home()
        for candidate in [
            home / '.steam' / 'steam',
            home / '.local' / 'share' / 'Steam',
        ]:
            if (candidate / 'steamapps').exists():
                libraries.append(candidate)

    return libraries


def _find_bethesda_launcher_install(game_id: str) -> Optional[Path]:
    """Check Bethesda Launcher registry for a game install path."""
    if platform.system() != 'Windows':
        return None

    try:
        import winreg
    except ImportError:
        return None

    key_path = _BETHESDA_REGISTRY.get(game_id)
    if not key_path:
        return None

    for prefix in [r'SOFTWARE\WOW6432Node\Bethesda Softworks',
                   r'SOFTWARE\Bethesda Softworks']:
        # Extract the game-specific part after "Bethesda Softworks\"
        game_key = key_path.split('Bethesda Softworks\\')[-1]
        full_key = prefix + '\\' + game_key
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, full_key) as key:
                path = Path(winreg.QueryValueEx(key, 'Installed Path')[0])
                if path.is_dir():
                    return path
        except OSError:
            continue

    return None


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

    Search order:
    1. Windows registry → Steam path → library folders → app manifests
    2. Bethesda Launcher registry entries
    3. Fallback: scan common filesystem paths for Steam libraries
    """
    found = []
    found_ids = set()

    # Try registry-based Steam discovery first
    steam_path = _find_steam_path()
    if steam_path:
        libraries = _parse_steam_libraries(steam_path)
    else:
        libraries = _find_steam_libraries_fallback()

    for game_id, name, appid, steam_folder, exe_name, appdata_name in _GAME_DEFS:
        # Try app manifest lookup (most reliable)
        for lib in libraries:
            game_dir = _find_game_in_manifest(lib, appid)
            if game_dir:
                data_dir = game_dir / 'Data'
                if data_dir.exists():
                    exe_path = game_dir / exe_name
                    found.append(GameInstall(
                        game_id=game_id,
                        name=name,
                        data_dir=data_dir,
                        exe_path=exe_path if exe_path.exists() else None,
                        app_data_dir=_find_appdata_dir(appdata_name),
                    ))
                    found_ids.add(game_id)
                    break

        if game_id in found_ids:
            continue

        # Fallback: scan library common folders by name
        for lib in libraries:
            game_dir = lib / 'steamapps' / 'common' / steam_folder
            data_dir = game_dir / 'Data'
            if data_dir.exists():
                exe_path = game_dir / exe_name
                found.append(GameInstall(
                    game_id=game_id,
                    name=name,
                    data_dir=data_dir,
                    exe_path=exe_path if exe_path.exists() else None,
                    app_data_dir=_find_appdata_dir(appdata_name),
                ))
                found_ids.add(game_id)
                break

        if game_id in found_ids:
            continue

        # Bethesda Launcher
        game_dir = _find_bethesda_launcher_install(game_id)
        if game_dir:
            data_dir = game_dir / 'Data'
            if data_dir.exists():
                found.append(GameInstall(
                    game_id=game_id,
                    name=name,
                    data_dir=data_dir,
                    exe_path=None,
                    app_data_dir=_find_appdata_dir(appdata_name),
                ))
                found_ids.add(game_id)

    return found


def find_game(game_id: str) -> Optional[GameInstall]:
    """Find a specific game by ID ('tes5', 'fo4', 'sf1')."""
    for game in discover_games():
        if game.game_id == game_id:
            return game
    return None


# -- Convenience functions for common lookups --


def find_game_data(game_id: str = 'tes5') -> Optional[Path]:
    """Find a game's Data directory."""
    game = find_game(game_id)
    return game.data_dir if game else None


def find_game_file(name: str, game_id: str = 'tes5') -> Optional[Path]:
    """Find a file in a game's Data directory (e.g. 'Dawnguard.esm')."""
    data = find_game_data(game_id)
    if data:
        path = data / name
        if path.exists():
            return path
    return None


# Additional paths to search for string tables extracted from BSAs
STRING_TABLE_SEARCH_PATHS = [
    Path(r"C:\Modding\SkyrimSEAssets\00 Vanilla Assets\strings"),
]


def find_strings_dir(game_id: str = 'tes5') -> Optional[Path]:
    """Find directory containing string tables for a game.

    Checks the game's Data/Strings/ first, then falls back to
    STRING_TABLE_SEARCH_PATHS for extracted BSA strings.
    """
    data = find_game_data(game_id)
    game = find_game(game_id)
    plugin_name = {
        'tes5': 'Skyrim', 'tes5le': 'Skyrim',
        'fo4': 'Fallout4', 'sf1': 'Starfield',
    }.get(game_id, '')

    strings_filename = f'{plugin_name}_english.STRINGS'.lower()

    # Check Data/Strings/
    if data:
        d = data / 'Strings'
        if d.exists():
            for f in d.iterdir():
                if f.name.lower() == strings_filename:
                    return d

    # Check additional search paths
    for p in STRING_TABLE_SEARCH_PATHS:
        if p.exists():
            for f in p.iterdir():
                if f.name.lower() == strings_filename:
                    return p

    return None
