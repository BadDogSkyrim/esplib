"""esplib - Python library for reading and modifying Bethesda plugin files."""

from .plugin import Plugin, PluginHeader
from .record import Record, SubRecord, GroupInstance, GroupRecord
from .utils import FormID
from .strings import StringTable, StringTableManager
from .load_order import LoadOrder
from .plugin_set import PluginSet, OverrideChain
from .game_discovery import (
    GameInstall, discover_games, find_game,
    find_game_data, find_game_file, find_strings_dir,
)
from .exceptions import PluginError, ParseError, ValidationError, FormIDError
from .helpers import (
    flst_forms, flst_contains, flst_add, flst_remove,
    glob_value, glob_set_value, glob_copy_as,
)
from .vmad import VmadData, VmadScript, VmadProperty, VmadObject

__version__ = "0.2.0"
__all__ = [
    "Plugin", "PluginHeader",
    "Record", "SubRecord", "GroupInstance", "GroupRecord",
    "FormID",
    "StringTable", "StringTableManager",
    "LoadOrder", "PluginSet", "OverrideChain",
    "GameInstall", "discover_games", "find_game",
    "find_game_data", "find_game_file", "find_strings_dir",
    "PluginError", "ParseError", "ValidationError", "FormIDError",
    "flst_forms", "flst_contains", "flst_add", "flst_remove",
    "glob_value", "glob_set_value", "glob_copy_as",
    "VmadData", "VmadScript", "VmadProperty", "VmadObject",
]
