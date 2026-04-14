"""PluginSet -- loads multiple plugins with master chains and override resolution."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from .plugin import Plugin
from .record import Record
from .utils import FormID, BaseFormID, AbsoluteFormID
from .load_order import LoadOrder
from .exceptions import PluginError


class OverrideChain:
    """Ordered list of records for a single FormID across the load order.

    chain[0]  = base record (from the earliest/master plugin)
    chain[-1] = winning record (last override)
    """

    def __init__(self):
        self._entries: List[Tuple[str, Record]] = []  # (plugin_name, record)

    def add(self, plugin_name: str, record: Record) -> None:
        self._entries.append((plugin_name, record))

    @property
    def records(self) -> List[Record]:
        return [r for _, r in self._entries]

    @property
    def plugin_names(self) -> List[str]:
        return [n for n, _ in self._entries]

    def __getitem__(self, index) -> Record:
        return self._entries[index][1]

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self.records)

    def __repr__(self) -> str:
        names = ', '.join(self.plugin_names)
        return f"OverrideChain([{names}])"


class PluginSet:
    """Manages a set of plugins loaded according to a load order.

    Supports:
    - Lazy loading (header-only by default, full on demand)
    - FormID resolution across master chains
    - Override chain queries
    """

    def __init__(self, load_order: LoadOrder):
        self.load_order = load_order
        self.string_search_dirs: List[str] = []
        self._plugins: Dict[str, Optional[Plugin]] = {}
        self._loaded_full: Dict[str, bool] = {}
        # FormID -> list of (plugin_name, record) in load order
        self._override_index: Optional[Dict[int, OverrideChain]] = None


    @classmethod
    def from_plugin(cls, plugin_path: Union[str, Path],
                    data_dir: Union[str, Path, None] = None,
                    game_id: str = 'tes5') -> 'PluginSet':
        """Load a plugin and all its masters into a PluginSet.

        Reads the plugin's master list from its header, recursively
        gathers transitive masters, builds a load order, and loads
        everything.
        """
        plugin_path = Path(plugin_path)
        if data_dir is None:
            data_dir = plugin_path.parent
        else:
            data_dir = Path(data_dir)

        # Gather all masters recursively
        def _gather_masters(name: str, seen: set, order: list):
            if name.lower() in seen:
                return
            seen.add(name.lower())
            path = data_dir / name
            if not path.exists():
                return
            p = Plugin(path)
            for master in p.header.masters:
                _gather_masters(master, seen, order)
            order.append(name)

        order: list = []
        seen: set = set()
        _gather_masters(plugin_path.name, seen, order)

        lo = LoadOrder.from_list(order, data_dir=data_dir, game_id=game_id)
        ps = cls(lo)
        ps.load_all()
        return ps

    def _resolve_plugin_path(self, name: str) -> Optional[Path]:
        """Find the file path for a plugin name."""
        return self.load_order.plugin_path(name)

    def load_plugin(self, name: str, full: bool = True) -> Optional[Plugin]:
        """Load a single plugin by name.

        Args:
            name: Plugin filename (e.g. 'Skyrim.esm')
            full: If True, load all records. If False, header only.
        """
        if name in self._plugins and self._loaded_full.get(name, False) >= full:
            return self._plugins[name]

        path = self._resolve_plugin_path(name)
        if path is None:
            self._plugins[name] = None
            return None

        try:
            plugin = Plugin()
            plugin.string_search_dirs = list(self.string_search_dirs)
            plugin._load(path)
            plugin.plugin_set = self
            self._plugins[name] = plugin
            self._loaded_full[name] = True
            # Invalidate override index when new plugin loaded
            self._override_index = None
            return plugin
        except Exception:
            self._plugins[name] = None
            return None

    def load_all(self) -> int:
        """Load all plugins in the load order. Returns count of successfully loaded."""
        count = 0
        for name in self.load_order:
            if self.load_plugin(name) is not None:
                count += 1
        return count

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a loaded plugin by name, loading it if not already loaded."""
        if name not in self._plugins:
            self.load_plugin(name)
        return self._plugins.get(name)

    def _build_override_index(self) -> None:
        """Build the FormID -> override chain index."""
        self._override_index = {}

        for plugin_name in self.load_order:
            plugin = self._plugins.get(plugin_name)
            if plugin is None:
                continue

            for record in plugin.records:
                # Resolve the FormID to an absolute form:
                # The file_index byte maps to the plugin's master list.
                abs_fid = self._resolve_absolute_form_id(
                    record.form_id, plugin)
                if abs_fid is None:
                    continue

                fid_val = abs_fid.value

                if fid_val not in self._override_index:
                    self._override_index[fid_val] = OverrideChain()
                self._override_index[fid_val].add(plugin_name, record)

    def _resolve_absolute_form_id(self, form_id: FormID,
                                   plugin: Plugin) -> Optional[AbsoluteFormID]:
        """Resolve a plugin-local FormID to an absolute FormID.

        The file_index byte of a FormID indexes into the plugin's master
        list. Index 0 = first master, index N = the plugin itself (where
        N = number of masters).
        """
        file_idx = form_id.file_index
        masters = plugin.header.masters
        num_masters = len(masters)

        if file_idx < num_masters:
            # References a master -- remap to that master's load order position
            master_name = masters[file_idx]
            lo_idx = self.load_order.index_of(master_name)
            if lo_idx < 0:
                return None
            return AbsoluteFormID((lo_idx << 24) | form_id.object_index)
        elif file_idx == num_masters:
            # This plugin's own record
            plugin_name = None
            if plugin.file_path:
                plugin_name = plugin.file_path.name
            lo_idx = self.load_order.index_of(plugin_name) if plugin_name else -1
            if lo_idx < 0:
                return None
            return AbsoluteFormID((lo_idx << 24) | form_id.object_index)
        else:
            # Invalid file index
            return None

    def get_override_chain(self, form_id: Union[BaseFormID, int]) -> Optional[OverrideChain]:
        """Get the override chain for a FormID.

        Returns an OverrideChain where [0] is the base and [-1] is the winner.
        Returns None if the FormID is not found in any loaded plugin.
        """
        if self._override_index is None:
            self._build_override_index()

        fid_val = form_id.value if isinstance(form_id, BaseFormID) else form_id
        return self._override_index.get(fid_val)

    def overridden_records(self):
        """Iterate all FormIDs that have more than one record (overrides).

        Yields (absolute_form_id: int, chain: OverrideChain) tuples.
        """
        if self._override_index is None:
            self._build_override_index()

        for fid, chain in self._override_index.items():
            if len(chain) > 1:
                yield fid, chain

    def resolve_form_id(self, form_id: BaseFormID,
                        source_plugin: Plugin = None) -> Optional[Record]:
        """Resolve a FormID reference to the winning record.

        AbsoluteFormID: looked up directly (source_plugin not needed).
        LocalFormID: requires source_plugin to normalize first.
        """
        if isinstance(form_id, AbsoluteFormID):
            abs_val = form_id.value
        else:
            if source_plugin is None:
                raise TypeError(
                    "source_plugin is required when resolving a LocalFormID")
            abs_fid = self._resolve_absolute_form_id(form_id, source_plugin)
            if abs_fid is None:
                return None
            abs_val = abs_fid.value

        chain = self.get_override_chain(abs_val)
        if chain and len(chain) > 0:
            return chain[-1]  # Winner
        return None

    def resolve_reference(self, record: Record,
                          subrecord_sig: str) -> Optional[Record]:
        """Resolve a FormID subrecord to the record it references.

        Reads the FormID from the named subrecord on `record`, then
        resolves it through the override chain to the winning record.
        Returns None if the subrecord is missing or the target is not found.
        """
        sr = record.get_subrecord(subrecord_sig)
        if sr is None:
            return None
        form_id = sr.get_form_id()
        source_plugin = record.plugin
        if source_plugin is None:
            return None
        return self.resolve_form_id(form_id, source_plugin)

    def get_record_by_edid(self, signature: str,
                           editor_id: str) -> Optional[Record]:
        """Find the winning override of a record by signature and EditorID.

        Searches all loaded plugins in load order and returns the last
        (winning) copy found.  Returns None if no match exists.
        """
        winner = None
        for plugin in self:
            for record in plugin.get_records_by_signature(signature):
                if record.editor_id == editor_id:
                    winner = record
        return winner


    def __iter__(self):
        """Iterate over loaded plugins in load order."""
        for name in self.load_order:
            plugin = self._plugins.get(name)
            if plugin is not None:
                yield plugin

    def __len__(self) -> int:
        return sum(1 for p in self._plugins.values() if p is not None)

    def __repr__(self) -> str:
        loaded = sum(1 for p in self._plugins.values() if p is not None)
        return f"PluginSet({loaded}/{len(self.load_order)} loaded)"
