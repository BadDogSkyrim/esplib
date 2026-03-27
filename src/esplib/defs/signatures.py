"""Shared signature constants for Bethesda plugin record and subrecord types.

These are the most commonly used signatures. Game-specific signatures
are defined in their respective definition modules (tes5.py, fo4.py, sf1.py).
"""

# --- Common subrecord signatures ---
EDID = 'EDID'  # Editor ID
FULL = 'FULL'  # Full name (localized)
DESC = 'DESC'  # Description (localized)
MODL = 'MODL'  # Model filename
MODT = 'MODT'  # Model texture data
MODS = 'MODS'  # Model alternate textures
OBND = 'OBND'  # Object bounds
KWDA = 'KWDA'  # Keywords (FormID array)
KSIZ = 'KSIZ'  # Keyword count
DATA = 'DATA'  # Generic data
HEDR = 'HEDR'  # Header data
CNAM = 'CNAM'  # Author / color
SNAM = 'SNAM'  # Description / sound
MAST = 'MAST'  # Master file
ONAM = 'ONAM'  # Override records
INTV = 'INTV'  # Internal version
INCC = 'INCC'  # Internal cell count

# --- Common record signatures ---
TES4 = 'TES4'  # Plugin header
GRUP = 'GRUP'  # Group
GMST = 'GMST'  # Game Setting
GLOB = 'GLOB'  # Global Variable
KYWD = 'KYWD'  # Keyword
FLST = 'FLST'  # Form List
WEAP = 'WEAP'  # Weapon
ARMO = 'ARMO'  # Armor
NPC_ = 'NPC_'  # Non-Player Character
ALCH = 'ALCH'  # Ingestible (Potion)
AMMO = 'AMMO'  # Ammunition
BOOK = 'BOOK'  # Book
INGR = 'INGR'  # Ingredient
MISC = 'MISC'  # Misc Item
KEYM = 'KEYM'  # Key
SCRL = 'SCRL'  # Scroll
CONT = 'CONT'  # Container
DOOR = 'DOOR'  # Door
LIGH = 'LIGH'  # Light
FURN = 'FURN'  # Furniture
ACTI = 'ACTI'  # Activator
FLOR = 'FLOR'  # Flora
TREE = 'TREE'  # Tree
STAT = 'STAT'  # Static
TXST = 'TXST'  # Texture Set
SPEL = 'SPEL'  # Spell
ENCH = 'ENCH'  # Enchantment
MGEF = 'MGEF'  # Magic Effect
PERK = 'PERK'  # Perk
RACE = 'RACE'  # Race
FACT = 'FACT'  # Faction
LVLI = 'LVLI'  # Leveled Item
LVLN = 'LVLN'  # Leveled NPC
LVSP = 'LVSP'  # Leveled Spell
COBJ = 'COBJ'  # Constructible Object
SNDR = 'SNDR'  # Sound Descriptor
SOUN = 'SOUN'  # Sound Marker
ADDN = 'ADDN'  # Addon Node
QUST = 'QUST'  # Quest
PACK = 'PACK'  # Package (AI)
IDLE = 'IDLE'  # Idle Animation
DIAL = 'DIAL'  # Dialog Topic
INFO = 'INFO'  # Dialog Response
LCTN = 'LCTN'  # Location
SMQN = 'SMQN'  # Story Manager Quest Node
SCEN = 'SCEN'  # Scene
CELL = 'CELL'  # Cell
WRLD = 'WRLD'  # Worldspace
REFR = 'REFR'  # Placed Object
ACHR = 'ACHR'  # Placed NPC
NAVM = 'NAVM'  # Navigation Mesh
LAND = 'LAND'  # Landscape
