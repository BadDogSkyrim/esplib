"""Game registry -- selects correct record definitions by game."""

from typing import Dict, Optional, List
from .types import EspRecord


class GameRegistry:
    """Registry of record definitions per game."""

    _games: Dict[str, 'GameRegistry'] = {}

    def __init__(self, game_id: str, name: str):
        self.game_id = game_id
        self.name = name
        self._records: Dict[str, EspRecord] = {}

    def register(self, record_def: EspRecord) -> None:
        self._records[record_def.signature] = record_def

    def get(self, signature: str) -> Optional[EspRecord]:
        return self._records.get(signature)

    def signatures(self) -> List[str]:
        return list(self._records.keys())

    @classmethod
    def register_game(cls, registry: 'GameRegistry') -> None:
        cls._games[registry.game_id] = registry

    @classmethod
    def get_game(cls, game_id: str) -> Optional['GameRegistry']:
        return cls._games.get(game_id)

    @classmethod
    def detect_game(cls, header_version: float) -> Optional['GameRegistry']:
        """Auto-detect game from the HEDR version field.

        Skyrim LE (0.94) and SE (1.71) both use 'tes5' -- the record
        definitions are the same (we handle BODT/BOD2 differences).
        """
        # Skyrim SE: 1.70-1.71
        if 1.69 < header_version < 1.72:
            return cls._games.get('tes5')
        # Skyrim LE: 0.94
        if 0.93 < header_version < 0.95:
            return cls._games.get('tes5')
        # Fallout 4: 0.95-1.0
        if 0.94 < header_version < 1.01:
            return cls._games.get('fo4')
        return None

    def __repr__(self) -> str:
        return f"GameRegistry({self.game_id!r}, records={len(self._records)})"
