"""Skyrim SE record definitions.

Ported from wbDefinitionsTES5.pas and wbDefinitionsCommon.pas.
"""

from .types import (
    IntType, EspFlags, EspEnum,
    EspInteger, EspFloat, EspString, EspFormID, EspByteArray,
    EspGmstValue, EspAlternateTextures,
    EspStruct, EspArray, EspSubRecord, EspGroup, EspRecord,
)
from . import common
from .game import GameRegistry


# ===== Tier 0: Infrastructure =====

GMST = EspRecord.new('GMST', 'Game Setting', [
    common.EDID,
    # DATA type is determined by the first character of the EDID:
    # f=float, i=int32, s=string, b=bool
    EspSubRecord.new('DATA', 'Value', EspGmstValue.new('value')),
])

GLOB = EspRecord.new('GLOB', 'Global Variable', [
    common.EDID,
    EspSubRecord.new('FNAM', 'Type', EspInteger.new('type', IntType.U8,
        formatter=EspEnum.new({
            ord('s'): 'Short',
            ord('l'): 'Long',
            ord('f'): 'Float',
        }))),
    EspSubRecord.new('FLTV', 'Value', EspFloat.new('value')),
])

KYWD = EspRecord.new('KYWD', 'Keyword', [
    common.EDID,
    EspSubRecord.new('CNAM', 'Color', EspStruct.new('color', [
        EspInteger.new('red', IntType.U8),
        EspInteger.new('green', IntType.U8),
        EspInteger.new('blue', IntType.U8),
        EspInteger.new('alpha', IntType.U8),
    ])),
])

FLST = EspRecord.new('FLST', 'Form List', [
    common.EDID,
    EspSubRecord.new('LNAM', 'Form', EspFormID.new('form')),
])


# ===== Tier 1: Game Things =====

WEAP = EspRecord.new('WEAP', 'Weapon', [
    common.EDID,
    common.VMAD,
    common.OBND,
    common.FULL,
    common.MODL,
    common.MODT,
    common.ICON,
    common.EITM,
    EspSubRecord.new('EAMT', 'Enchantment Amount',
                     EspInteger.new('amount', IntType.U16)),
    EspSubRecord.new('DEST', 'Destructible Header',
                     EspByteArray.new('data')),
    common.ETYP,
    EspSubRecord.new('BIDS', 'Block Bash Impact Data Set',
                     EspFormID.new('bash_impact', ['IPDS'])),
    EspSubRecord.new('BAMT', 'Alternate Block Material',
                     EspFormID.new('block_material', ['MATT'])),
    common.YNAM,
    common.ZNAM,
    common.KSIZ,
    common.KWDA,
    common.DESC,
    # Scope model (wbTexturedModel 'Has Scope')
    EspSubRecord.new('MOD3', 'Scope Model',
                     EspString.new('model', 'zstring')),
    EspSubRecord.new('MO3T', 'Scope Model Texture Data',
                     EspByteArray.new('data')),
    EspSubRecord.new('EFSD', 'Scope Effect',
                     EspFormID.new('scope_effect', ['EFSH'])),
    EspSubRecord.new('NNAM', 'Unused',
                     EspByteArray.new('data')),
    EspSubRecord.new('INAM', 'Impact Data Set',
                     EspFormID.new('impact_data', ['IPDS'])),
    EspSubRecord.new('WNAM', '1st Person Model Object',
                     EspFormID.new('first_person_model', ['STAT'])),
    EspSubRecord.new('SNAM', 'Attack Sound',
                     EspFormID.new('attack_sound', ['SNDR'])),
    EspSubRecord.new('XNAM', 'Attack Sound 2D',
                     EspFormID.new('attack_sound_2d', ['SNDR'])),
    EspSubRecord.new('NAM7', 'Attack Loop Sound',
                     EspFormID.new('attack_loop_sound', ['SNDR'])),
    EspSubRecord.new('TNAM', 'Attack Fail Sound',
                     EspFormID.new('attack_fail_sound', ['SNDR'])),
    EspSubRecord.new('UNAM', 'Idle Sound',
                     EspFormID.new('idle_sound', ['SNDR'])),
    EspSubRecord.new('NAM9', 'Equip Sound',
                     EspFormID.new('equip_sound', ['SNDR'])),
    EspSubRecord.new('NAM8', 'Unequip Sound',
                     EspFormID.new('unequip_sound', ['SNDR'])),
    EspSubRecord.new('DATA', 'Game Data', EspStruct.new('data', [
        EspInteger.new('value', IntType.U32),
        EspFloat.new('weight'),
        EspInteger.new('damage', IntType.U16),
    ])),
    EspSubRecord.new('DNAM', 'Weapon Data', EspStruct.new('dnam', [
        EspInteger.new('animation_type', IntType.U8,
                       formatter=common.WeaponAnimTypeEnum),
        EspByteArray.new('padding1', size=3),
        EspFloat.new('speed'),
        EspFloat.new('reach'),
        EspInteger.new('flags', IntType.U16, formatter=common.WeaponFlags),
        EspByteArray.new('padding2', size=2),
        EspFloat.new('sight_fov'),
        EspByteArray.new('unknown1', size=4),
        EspInteger.new('base_vats_hit_chance', IntType.U8),
        EspInteger.new('attack_animation', IntType.U8),
        EspInteger.new('num_projectiles', IntType.U8),
        EspInteger.new('embedded_weapon_av', IntType.U8),
        EspFloat.new('range_min'),
        EspFloat.new('range_max'),
        EspInteger.new('on_hit', IntType.U32),
        EspInteger.new('flags2', IntType.U32, formatter=common.WeaponFlags2),
        EspFloat.new('animation_attack_mult'),
        EspFloat.new('fire_rate'),
        EspFloat.new('rumble_left'),
        EspFloat.new('rumble_right'),
        EspFloat.new('rumble_duration'),
        EspFloat.new('override_damage_mult'),
        EspFloat.new('attack_shots_per_sec'),
        EspByteArray.new('unknown2', size=4),
        EspInteger.new('skill', IntType.S32, formatter=common.ActorValueEnum),
        EspByteArray.new('unknown3', size=8),
        EspInteger.new('resist', IntType.S32, formatter=common.ActorValueEnum),
        EspByteArray.new('unknown4', size=4),
        EspFloat.new('stagger'),
    ])),
    EspSubRecord.new('CRDT', 'Critical Data', EspStruct.new('crdt', [
        EspInteger.new('damage', IntType.U16),
        EspByteArray.new('padding1', size=2),
        EspFloat.new('percent_mult'),
        EspInteger.new('on_death', IntType.U8),
        EspByteArray.new('padding2', size=7),
        EspFormID.new('effect', ['SPEL']),
        EspByteArray.new('padding3', size=4),
    ])),
    EspSubRecord.new('VNAM', 'Detection Sound Level',
                     EspInteger.new('level', IntType.U32,
                                    formatter=common.SoundLevelEnum)),
    EspSubRecord.new('CNAM', 'Template',
                     EspFormID.new('template', ['WEAP'])),
])

# -- Bodypart flags for BOD2/ARMA --
BodypartFlags = EspFlags.new({
    0: 'Head', 1: 'Hair', 2: 'Body', 3: 'Hands',
    4: 'Forearms', 5: 'Amulet', 6: 'Ring', 7: 'Feet',
    8: 'Calves', 9: 'Shield', 10: 'Tail',
    11: 'Long Hair', 12: 'Circlet', 13: 'Ears',
    20: 'Decapitate Head', 21: 'Decapitate',
    30: 'FX01',
})

ARMO = EspRecord.new('ARMO', 'Armor', [
    common.EDID,
    common.VMAD,
    common.OBND,
    common.FULL,
    common.EITM,
    EspSubRecord.new('EAMT', 'Enchantment Amount',
                     EspInteger.new('amount', IntType.U16)),
    # Male world model
    EspGroup.new('Male World Model', [
        EspSubRecord.new('MOD2', 'Male Model Filename',
                         EspString.new('male_model', 'zstring')),
        EspSubRecord.new('MO2T', 'Male Model Texture Data',
                         EspByteArray.new('data')),
        EspSubRecord.new('MO2S', 'Male Model Alternate Textures',
                         EspAlternateTextures.new('data')),
        EspSubRecord.new('ICON', 'Icon Image',
                         EspString.new('icon', 'zstring')),
        EspSubRecord.new('MICO', 'Message Icon',
                         EspString.new('message_icon', 'zstring')),
    ]),
    # Female world model
    EspGroup.new('Female World Model', [
        EspSubRecord.new('MOD4', 'Female Model Filename',
                         EspString.new('female_model', 'zstring')),
        EspSubRecord.new('MO4T', 'Female Model Texture Data',
                         EspByteArray.new('data')),
        EspSubRecord.new('MO4S', 'Female Model Alternate Textures',
                         EspAlternateTextures.new('data')),
        EspSubRecord.new('ICO2', 'Icon Image 2',
                         EspString.new('icon', 'zstring')),
        EspSubRecord.new('MIC2', 'Message Icon 2',
                         EspString.new('message_icon', 'zstring')),
    ]),
    EspSubRecord.new('BODT', 'Body Template (Old)', EspByteArray.new('bodt')),
    EspSubRecord.new('BOD2', 'Body Template', EspStruct.new('bod2', [
        EspInteger.new('first_person_flags', IntType.U32, formatter=BodypartFlags),
        EspInteger.new('armor_type', IntType.U32,
                       formatter=common.ArmorTypeEnum),
    ])),
    common.YNAM,
    common.ZNAM,
    EspSubRecord.new('BMCT', 'Ragdoll Constraint Template',
                     EspString.new('template', 'zstring')),
    common.ETYP,
    EspSubRecord.new('BIDS', 'Bash Impact Data Set',
                     EspFormID.new('bash_impact', ['IPDS'])),
    EspSubRecord.new('BAMT', 'Alternate Block Material',
                     EspFormID.new('block_material', ['MATT'])),
    EspSubRecord.new('RNAM', 'Race',
                     EspFormID.new('race', ['RACE'])),
    common.KSIZ,
    common.KWDA,
    common.DESC,
    EspSubRecord.new('MODL', 'Armature',
                     EspFormID.new('armature', ['ARMA'])),
    EspSubRecord.new('DATA', 'Data', EspStruct.new('data', [
        EspInteger.new('value', IntType.S32),
        EspFloat.new('weight'),
    ])),
    EspSubRecord.new('DNAM', 'Armor Rating',
                     EspInteger.new('rating', IntType.S32)),
    EspSubRecord.new('TNAM', 'Template Armor',
                     EspFormID.new('template', ['ARMO'])),
])

ALCH = EspRecord.new('ALCH', 'Ingestible', [
    common.EDID,
    common.OBND,
    common.FULL,
    common.KSIZ,
    common.KWDA,
    common.DESC,
    common.MODL,
    common.MODT,
    common.ICON,
    common.YNAM,
    common.ZNAM,
    common.ETYP,
    EspSubRecord.new('DATA', 'Weight', EspFloat.new('weight')),
    EspSubRecord.new('ENIT', 'Effect Data', EspStruct.new('enit', [
        EspInteger.new('value', IntType.S32),
        EspInteger.new('flags', IntType.U32, formatter=EspFlags.new({
            0: 'No Auto-Calc',
            1: 'Food Item',
            16: 'Medicine',
            17: 'Poison',
        })),
        EspFormID.new('addiction'),
        EspFloat.new('addiction_chance'),
        EspFormID.new('sound_consume', ['SNDR']),
    ])),
    # Effects (repeating EFID + EFIT pairs)
    EspGroup.new('Effect', [
        EspSubRecord.new('EFID', 'Effect',
                         EspFormID.new('base_effect', ['MGEF'])),
        EspSubRecord.new('EFIT', 'Effect Data', EspStruct.new('efit', [
            EspFloat.new('magnitude'),
            EspInteger.new('area', IntType.U32),
            EspInteger.new('duration', IntType.U32),
        ])),
        EspSubRecord.new('CTDA', 'Condition',
                         EspByteArray.new('data')),
    ]),
])

AMMO = EspRecord.new('AMMO', 'Ammunition', [
    common.EDID,
    common.OBND,
    common.FULL,
    common.MODL,
    common.MODT,
    common.ICON,
    common.YNAM,
    common.ZNAM,
    common.DESC,
    common.KSIZ,
    common.KWDA,
    EspSubRecord.new('DATA', 'Data', EspStruct.new('data', [
        EspFormID.new('projectile', ['PROJ']),
        EspInteger.new('flags', IntType.U32, formatter=EspFlags.new({
            0: 'Ignores Normal Weapon Resistance',
            1: 'Non-Playable',
            2: 'Non-Bolt',
        })),
        EspFloat.new('damage'),
        EspInteger.new('value', IntType.U32),
        EspFloat.new('weight'),
    ])),
    EspSubRecord.new('ONAM', 'Short Name',
                     EspString.new('short_name', 'zstring')),
])

BOOK = EspRecord.new('BOOK', 'Book', [
    common.EDID,
    common.VMAD,
    common.OBND,
    common.FULL,
    common.MODL,
    common.MODT,
    common.ICON,
    common.DESC,
    common.YNAM,
    common.ZNAM,
    common.KSIZ,
    common.KWDA,
    EspSubRecord.new('DATA', 'Data', EspStruct.new('data', [
        EspInteger.new('flags', IntType.U8, formatter=EspFlags.new({
            0: 'Teaches Skill',
            1: "Can't Be Taken",
            2: 'Teaches Spell',
        })),
        EspInteger.new('type', IntType.U8, formatter=EspEnum.new({
            0: 'Book/Tome',
            255: 'Note/Scroll',
        })),
        EspByteArray.new('padding', size=2),
        # Teaches field is a union: skill enum (int32) or spell FormID
        # Simplified as int32 for now
        EspInteger.new('teaches', IntType.S32),
        EspInteger.new('value', IntType.U32),
        EspFloat.new('weight'),
    ])),
    EspSubRecord.new('INAM', 'Inventory Art',
                     EspFormID.new('inventory_art', ['STAT'])),
    EspSubRecord.new('CNAM', 'Description',
                     EspString.new('description', 'lstring')),
])

MISC = EspRecord.new('MISC', 'Misc Item', [
    common.EDID,
    common.VMAD,
    common.OBND,
    common.FULL,
    common.MODL,
    common.MODT,
    common.ICON,
    common.YNAM,
    common.ZNAM,
    common.KSIZ,
    common.KWDA,
    EspSubRecord.new('DATA', 'Data', EspStruct.new('data', [
        EspInteger.new('value', IntType.S32),
        EspFloat.new('weight'),
    ])),
])

_LEVELED_ENTRY_STRUCT = EspStruct.new('entry', [
    EspInteger.new('level', IntType.U16),
    EspByteArray.new('padding', size=2),
    EspFormID.new('reference'),
    EspInteger.new('count', IntType.U16),
    EspByteArray.new('padding2', size=2),
])


LVLI = EspRecord.new('LVLI', 'Leveled Item', [
    common.EDID,
    common.OBND,
    EspSubRecord.new('LVLD', 'Chance None',
                     EspInteger.new('chance_none', IntType.U8)),
    EspSubRecord.new('LVLF', 'Flags',
                     EspInteger.new('flags', IntType.U8,
                                    formatter=common.LeveledItemFlags)),
    EspSubRecord.new('LVLG', 'Global',
                     EspFormID.new('global', ['GLOB'])),
    EspSubRecord.new('LLCT', 'Entry Count',
                     EspInteger.new('count', IntType.U8)),
    EspSubRecord.new('LVLO', 'Leveled List Entry', _LEVELED_ENTRY_STRUCT),
])

LVLN = EspRecord.new('LVLN', 'Leveled NPC', [
    common.EDID,
    common.OBND,
    EspSubRecord.new('LVLD', 'Chance None',
                     EspInteger.new('chance_none', IntType.U8)),
    EspSubRecord.new('LVLF', 'Flags',
                     EspInteger.new('flags', IntType.U8,
                                    formatter=common.LeveledItemFlags)),
    EspSubRecord.new('LVLG', 'Global',
                     EspFormID.new('global', ['GLOB'])),
    EspSubRecord.new('LLCT', 'Entry Count',
                     EspInteger.new('count', IntType.U8)),
    EspSubRecord.new('LVLO', 'Leveled List Entry', _LEVELED_ENTRY_STRUCT),
    EspSubRecord.new('MODL', 'Model File',
                     EspString.new('model', 'zstring', encoding='cp1252')),
    EspSubRecord.new('MODT', 'Model Texture Data',
                     EspByteArray.new('modt')),
])

COBJ = EspRecord.new('COBJ', 'Constructible Object', [
    common.EDID,
    EspSubRecord.new('COCT', 'Ingredient Count',
                     EspInteger.new('count', IntType.U32)),
    EspSubRecord.new('CNTO', 'Ingredient', EspStruct.new('ingredient', [
        EspFormID.new('item'),
        EspInteger.new('count', IntType.S32),
    ])),
    EspSubRecord.new('CITC', 'Condition Count',
                     EspInteger.new('count', IntType.U32)),
    EspSubRecord.new('CTDA', 'Condition',
                     EspByteArray.new('data')),
    EspSubRecord.new('CNAM', 'Created Object',
                     EspFormID.new('created_object')),
    EspSubRecord.new('BNAM', 'Workbench Keyword',
                     EspFormID.new('workbench', ['KYWD'])),
    EspSubRecord.new('NAM1', 'Created Object Count',
                     EspInteger.new('count', IntType.U16)),
])

FACT = EspRecord.new('FACT', 'Faction', [
    common.EDID,
    common.FULL,
    EspSubRecord.new('XNAM', 'Relation', EspStruct.new('relation', [
        EspFormID.new('faction', ['FACT', 'RACE']),
        EspInteger.new('modifier', IntType.S32),
        EspInteger.new('group_combat_reaction', IntType.U32, formatter=EspEnum.new({
            0: 'Neutral',
            1: 'Enemy',
            2: 'Ally',
            3: 'Friend',
        })),
    ])),
    EspSubRecord.new('DATA', 'Flags',
                     EspInteger.new('flags', IntType.U32,
                                    formatter=common.FactionFlags)),
    EspSubRecord.new('JAIL', 'Exterior Jail Marker',
                     EspFormID.new('jail', ['REFR'])),
    EspSubRecord.new('WAIT', 'Follower Wait Marker',
                     EspFormID.new('wait', ['REFR'])),
    EspSubRecord.new('STOL', 'Stolen Goods Container',
                     EspFormID.new('stolen_goods', ['REFR'])),
    EspSubRecord.new('PLCN', 'Player Inventory Container',
                     EspFormID.new('player_container', ['REFR'])),
    EspSubRecord.new('CRGR', 'Shared Crime Faction List',
                     EspFormID.new('crime_faction_list', ['FLST'])),
    EspSubRecord.new('JOUT', 'Jail Outfit',
                     EspFormID.new('jail_outfit', ['OTFT'])),
    EspSubRecord.new('CRVA', 'Crime Values', EspStruct.new('crime_values', [
        EspInteger.new('arrest', IntType.U8),
        EspInteger.new('attack_on_sight', IntType.U8),
        EspInteger.new('murder', IntType.U16),
        EspInteger.new('assault', IntType.U16),
        EspInteger.new('trespass', IntType.U16),
        EspInteger.new('pickpocket', IntType.U16),
        EspInteger.new('unknown', IntType.U16),
        EspFloat.new('steal_multiplier'),
        EspInteger.new('escape', IntType.U16),
        EspInteger.new('werewolf', IntType.U16),
    ])),
    # Ranks (repeating group: RNAM, MNAM, FNAM, INAM)
    EspSubRecord.new('RNAM', 'Rank Number',
                     EspInteger.new('rank', IntType.U32)),
    EspSubRecord.new('MNAM', 'Male Title',
                     EspString.new('male_title')),
    EspSubRecord.new('FNAM', 'Female Title',
                     EspString.new('female_title')),
    EspSubRecord.new('INAM', 'Insignia Unused',
                     EspString.new('insignia')),
    EspSubRecord.new('VEND', 'Vendor Buy/Sell List',
                     EspFormID.new('vendor_list', ['FLST'])),
    EspSubRecord.new('VENC', 'Merchant Container',
                     EspFormID.new('merchant_container', ['REFR'])),
    EspSubRecord.new('VENV', 'Vendor Values', EspStruct.new('vendor_values', [
        EspInteger.new('start_hour', IntType.U16),
        EspInteger.new('end_hour', IntType.U16),
        EspInteger.new('radius', IntType.U16),
        EspByteArray.new('unknown1', size=2),
        EspInteger.new('only_buys_stolen', IntType.U8),
        EspInteger.new('not_sell_buy', IntType.U8),
        EspByteArray.new('unknown2', size=2),
    ])),
    EspSubRecord.new('PLVD', 'Vendor Location', EspStruct.new('vendor_location', [
        EspInteger.new('type', IntType.U32),
        EspFormID.new('location', []),
        EspInteger.new('radius', IntType.U32),
    ])),
    EspSubRecord.new('CITC', 'Condition Count',
                     EspInteger.new('count', IntType.U32)),
    EspSubRecord.new('CTDA', 'Condition',
                     EspByteArray.new('data')),
])

# ===== Phase A: Additional definitions for Furrifier =====

# -- Headpart Type enum (used by HDPT PNAM) --
HeadpartTypeEnum = EspEnum.new({
    0: 'Misc',
    1: 'Face',
    2: 'Eyes',
    3: 'Hair',
    4: 'Facial Hair',
    5: 'Scar',
    6: 'Eyebrows',
})

# -- RACE flags --
RaceFlags = EspFlags.new({
    0: 'Playable', 1: 'FaceGen Head', 2: 'Child',
    3: 'Tilt Front/Back', 4: 'Tilt Left/Right', 5: 'No Shadow',
    6: 'Swims', 7: 'Flies', 8: 'Walks', 9: 'Immobile',
    10: 'Not Pushable', 11: 'No Combat In Water',
    12: 'No Rotating to Head-Track', 15: 'Uses Head Track Anims',
    20: "Can't Open Doors", 21: 'Allow PC Dialogue',
    22: 'No Knockdowns', 23: 'Allow Pickpocket',
    28: 'Can Pickup Items', 30: 'Can Dual Wield',
    31: 'Avoids Roads',
})

TXST = EspRecord.new('TXST', 'Texture Set', [
    common.EDID,
    common.OBND,
    # TX00..TX07 are the eight texture slots referenced by the
    # TXST. They're all zstring file paths under `Data\textures\`.
    # All share `name='texture'` so consumers can detect "this
    # field is a file path" via a single value_def name; the
    # subrecord descriptions carry the per-slot semantics for
    # to_dict output / docs.
    EspSubRecord.new('TX00', 'Color Map',
                     EspString.new('texture', 'zstring')),
    EspSubRecord.new('TX01', 'Normal/Gloss Map',
                     EspString.new('texture', 'zstring')),
    EspSubRecord.new('TX02', 'Environment Mask / Subsurface Tint',
                     EspString.new('texture', 'zstring')),
    EspSubRecord.new('TX03', 'Glow / Detail Map',
                     EspString.new('texture', 'zstring')),
    EspSubRecord.new('TX04', 'Height Map',
                     EspString.new('texture', 'zstring')),
    EspSubRecord.new('TX05', 'Environment Map',
                     EspString.new('texture', 'zstring')),
    EspSubRecord.new('TX06', 'Multilayer Mask',
                     EspString.new('texture', 'zstring')),
    EspSubRecord.new('TX07', 'Backlight Mask / Specular',
                     EspString.new('texture', 'zstring')),
    # DODT is decal data (24-byte struct in vanilla, ~52 in some
    # SE plugins). Contents aren't useful to us; pass through as
    # raw bytes so round-trip is preserved.
    EspSubRecord.new('DODT', 'Decal Data',
                     EspByteArray.new('dodt')),
    # DNAM is a uint16 flag word: 0=NoSpecular, 1=FacegenTextures,
    # 2=HasModelSpaceNormalMap (rest unknown / unused).
    EspSubRecord.new('DNAM', 'Flags',
                     EspInteger.new('flags', IntType.U16,
                                    formatter=EspFlags.new({
                                        0: 'No Specular',
                                        1: 'FaceGen Textures',
                                        2: 'Has Model Space Normal Map',
                                    }))),
])

HDPT = EspRecord.new('HDPT', 'Head Part', [
    common.EDID,
    common.FULL,
    common.MODL,
    common.MODT,
    EspSubRecord.new('DATA', 'Flags',
                     EspInteger.new('flags', IntType.U8, formatter=EspFlags.new({
                         0: 'Playable', 1: 'Male', 2: 'Female',
                         4: 'Is Extra Part', 5: 'Use Solid Tint',
                     }))),
    EspSubRecord.new('PNAM', 'Type',
                     EspInteger.new('type', IntType.U32,
                                    formatter=HeadpartTypeEnum)),
    EspSubRecord.new('HNAM', 'Extra Parts',
                     EspArray.new('extra_parts', EspFormID.new('part', ['HDPT']))),
    EspGroup.new('Part', [
        EspSubRecord.new('NAM0', 'Part Type',
                         EspInteger.new('type', IntType.U32)),
        EspSubRecord.new('NAM1', 'FileName',
                         EspString.new('filename', 'zstring')),
    ]),
    EspSubRecord.new('TNAM', 'Texture Set',
                     EspFormID.new('texture_set', ['TXST'])),
    EspSubRecord.new('CNAM', 'Color',
                     EspFormID.new('color', ['CLFM'])),
    EspSubRecord.new('RNAM', 'Valid Races',
                     EspFormID.new('valid_races', ['FLST'])),
])

ARMA = EspRecord.new('ARMA', 'Armor Addon', [
    common.EDID,
    EspSubRecord.new('BODT', 'Body Template (Old)', EspStruct.new('bodt', [
        EspInteger.new('first_person_flags', IntType.U32, formatter=BodypartFlags),
        EspInteger.new('general_flags', IntType.U32),
        EspInteger.new('armor_type', IntType.U32,
                       formatter=common.ArmorTypeEnum),
    ])),
    EspSubRecord.new('BOD2', 'Body Template', EspStruct.new('bod2', [
        EspInteger.new('first_person_flags', IntType.U32, formatter=BodypartFlags),
        EspInteger.new('armor_type', IntType.U32,
                       formatter=common.ArmorTypeEnum),
    ])),
    EspSubRecord.new('RNAM', 'Race',
                     EspFormID.new('race', ['RACE'])),
    EspSubRecord.new('DNAM', 'Data', EspStruct.new('dnam', [
        EspInteger.new('male_priority', IntType.U8),
        EspInteger.new('female_priority', IntType.U8),
        EspInteger.new('weight_slider_male', IntType.U8),
        EspInteger.new('weight_slider_female', IntType.U8),
        EspByteArray.new('unknown1', size=2),
        EspInteger.new('detection_sound_value', IntType.U8),
        EspByteArray.new('unknown2', size=1),
        EspFloat.new('weapon_adjust'),
    ])),
    # Biped Model (Male + Female world models)
    EspGroup.new('Male World Model', [
        EspSubRecord.new('MOD2', 'Male World Model',
                         EspString.new('model', 'zstring')),
        EspSubRecord.new('MO2T', 'Male Model Texture Data',
                         EspByteArray.new('data')),
        EspSubRecord.new('MO2S', 'Male Model Alternate Textures',
                         EspAlternateTextures.new('data')),
    ]),
    EspGroup.new('Female World Model', [
        EspSubRecord.new('MOD3', 'Female World Model',
                         EspString.new('model', 'zstring')),
        EspSubRecord.new('MO3T', 'Female Model Texture Data',
                         EspByteArray.new('data')),
        EspSubRecord.new('MO3S', 'Female Model Alternate Textures',
                         EspAlternateTextures.new('data')),
    ]),
    # 1st Person Model (Male + Female)
    EspGroup.new('Male 1st Person', [
        EspSubRecord.new('MOD4', 'Male 1st Person Model',
                         EspString.new('model', 'zstring')),
        EspSubRecord.new('MO4T', 'Male 1st Person Texture Data',
                         EspByteArray.new('data')),
        EspSubRecord.new('MO4S', 'Male 1st Person Alternate Textures',
                         EspAlternateTextures.new('data')),
    ]),
    EspGroup.new('Female 1st Person', [
        EspSubRecord.new('MOD5', 'Female 1st Person Model',
                         EspString.new('model', 'zstring')),
        EspSubRecord.new('MO5T', 'Female 1st Person Texture Data',
                         EspByteArray.new('data')),
        EspSubRecord.new('MO5S', 'Female 1st Person Alternate Textures',
                         EspAlternateTextures.new('data')),
    ]),
    # Skin textures
    EspSubRecord.new('NAM0', 'Male Skin Texture',
                     EspFormID.new('male_skin', ['TXST'])),
    EspSubRecord.new('NAM1', 'Female Skin Texture',
                     EspFormID.new('female_skin', ['TXST'])),
    EspSubRecord.new('NAM2', 'Male Skin Texture Swap List',
                     EspFormID.new('male_swap', ['FLST'])),
    EspSubRecord.new('NAM3', 'Female Skin Texture Swap List',
                     EspFormID.new('female_swap', ['FLST'])),
    # Additional races
    EspSubRecord.new('MODL', 'Additional Races',
                     EspFormID.new('race', ['RACE'])),
    # Footstep sound
    EspSubRecord.new('SNDD', 'Footstep Sound',
                     EspFormID.new('footstep_sound', ['FSTS'])),
    EspSubRecord.new('ONAM', 'Art Object',
                     EspFormID.new('art_object', ['ARTO'])),
])

# -- Shared sub-definitions for RACE tint entries and head part groups --
_race_tint_preset = EspGroup.new('Tint Preset', [
    EspSubRecord.new('TINC', 'Tint Preset Color',
                     EspFormID.new('color', ['CLFM'])),
    EspSubRecord.new('TINV', 'Tint Preset Default Value',
                     EspFloat.new('value')),
    EspSubRecord.new('TIRS', 'Tint Preset Index',
                     EspInteger.new('index', IntType.U16)),
])

_race_tint_entry = EspGroup.new('Tint Entry', [
    EspSubRecord.new('TINI', 'Tint Index',
                     EspInteger.new('index', IntType.U16)),
    EspSubRecord.new('TINT', 'Tint File',
                     EspString.new('file', 'zstring')),
    EspSubRecord.new('TINP', 'Tint Mask Type',
                     EspInteger.new('type', IntType.U16)),
    EspSubRecord.new('TIND', 'Tint Preset Default',
                     EspFormID.new('default_color', ['CLFM'])),
    _race_tint_preset,
])

_race_head_part = EspGroup.new('Head Part', [
    EspSubRecord.new('INDX', 'Head Part Number',
                     EspInteger.new('index', IntType.U32)),
    EspSubRecord.new('HEAD', 'Head Part',
                     EspFormID.new('head_part', ['HDPT'])),
])

_race_morph = EspGroup.new('Morph', [
    EspSubRecord.new('MPAI', 'Morph Preset Flags',
                     EspByteArray.new('data')),
    EspSubRecord.new('MPAV', 'Morph Preset Values',
                     EspByteArray.new('data')),
])

RACE = EspRecord.new('RACE', 'Race', [
    common.EDID,
    common.FULL,
    common.DESC,
    # Spells
    EspSubRecord.new('SPCT', 'Spell Count',
                     EspInteger.new('count', IntType.U32)),
    EspSubRecord.new('SPLO', 'Spell',
                     EspFormID.new('spell', ['SPEL'])),
    # Skin armor
    EspSubRecord.new('WNAM', 'Skin',
                     EspFormID.new('skin', ['ARMO'])),
    # Body template
    EspSubRecord.new('BOD2', 'Body Template', EspStruct.new('bod2', [
        EspInteger.new('first_person_flags', IntType.U32, formatter=BodypartFlags),
        EspInteger.new('armor_type', IntType.U32,
                       formatter=common.ArmorTypeEnum),
    ])),
    common.KSIZ,
    common.KWDA,
    EspSubRecord.new('DATA', 'Race Data', EspByteArray.new('data')),
    # Male skeletal model
    EspGroup.new('Male Skeletal Model', [
        EspSubRecord.new('MNAM', 'Male Marker',
                         EspByteArray.new('data')),
        EspSubRecord.new('ANAM', 'Male Skeletal Model',
                         EspString.new('skeleton', 'zstring')),
        common.MODT,
    ]),
    # Female skeletal model
    EspGroup.new('Female Skeletal Model', [
        EspSubRecord.new('FNAM', 'Female Marker',
                         EspByteArray.new('data')),
        EspSubRecord.new('ANAM', 'Female Skeletal Model',
                         EspString.new('skeleton', 'zstring')),
        common.MODT,
    ]),
    EspSubRecord.new('NAM2', 'Marker NAM2 #1',
                     EspByteArray.new('data')),
    EspSubRecord.new('MTNM', 'Movement Type Name',
                     EspString.new('name', 'zstring')),
    EspSubRecord.new('VTCK', 'Voices', EspStruct.new('voices', [
        EspFormID.new('male', ['VTYP']),
        EspFormID.new('female', ['VTYP']),
    ])),
    EspSubRecord.new('DNAM', 'Decapitate Armors', EspStruct.new('decap', [
        EspFormID.new('male', ['ARMO']),
        EspFormID.new('female', ['ARMO']),
    ])),
    EspSubRecord.new('HCLF', 'Default Hair Colors', EspStruct.new('hair_colors', [
        EspFormID.new('male', ['CLFM']),
        EspFormID.new('female', ['CLFM']),
    ])),
    EspSubRecord.new('TINL', 'Total Tints In List',
                     EspInteger.new('count', IntType.U16)),
    EspSubRecord.new('PNAM', 'FaceGen Main Clamp',
                     EspFloat.new('clamp')),
    EspSubRecord.new('UNAM', 'FaceGen Face Clamp',
                     EspFloat.new('clamp')),
    EspSubRecord.new('ATKR', 'Attack Race',
                     EspFormID.new('attack_race', ['RACE'])),
    # Attacks (repeating ATKD+ATKE pairs)
    EspGroup.new('Attack', [
        EspSubRecord.new('ATKD', 'Attack Data',
                         EspByteArray.new('data')),
        EspSubRecord.new('ATKE', 'Attack Event',
                         EspString.new('event', 'zstring')),
    ]),
    # Body Data section
    EspGroup.new('Body Data', [
        EspSubRecord.new('NAM1', 'Body Data Marker',
                         EspByteArray.new('data')),
        EspGroup.new('Male Body Data', [
            EspSubRecord.new('MNAM', 'Male Data Marker',
                             EspByteArray.new('data')),
            EspSubRecord.new('INDX', 'Body Part Number',
                             EspInteger.new('index', IntType.U32)),
            common.MODL,
            common.MODT,
        ]),
        EspGroup.new('Female Body Data', [
            EspSubRecord.new('FNAM', 'Female Data Marker',
                             EspByteArray.new('data')),
            EspSubRecord.new('INDX', 'Body Part Number',
                             EspInteger.new('index', IntType.U32)),
            common.MODL,
            common.MODT,
        ]),
    ]),
    EspSubRecord.new('HNAM', 'Hairs',
                     EspFormID.new('hair', ['HDPT'])),
    EspSubRecord.new('ENAM', 'Eyes',
                     EspFormID.new('eyes', ['EYES'])),
    EspSubRecord.new('GNAM', 'Body Part Data',
                     EspFormID.new('body_part_data', ['BPTD'])),
    EspSubRecord.new('NAM2', 'Marker NAM2 #2',
                     EspByteArray.new('data')),
    EspSubRecord.new('NAM3', 'Marker NAM3 #3',
                     EspByteArray.new('data')),
    # Male Behavior Graph
    EspGroup.new('Male Behavior Graph', [
        EspSubRecord.new('MNAM', 'Male Data Marker',
                         EspByteArray.new('data')),
        common.MODL,
        common.MODT,
    ]),
    # Female Behavior Graph
    EspGroup.new('Female Behavior Graph', [
        EspSubRecord.new('FNAM', 'Female Data Marker',
                         EspByteArray.new('data')),
        common.MODL,
        common.MODT,
    ]),
    EspSubRecord.new('NAM4', 'Material Type',
                     EspFormID.new('material', ['MATT'])),
    EspSubRecord.new('NAM5', 'Impact Data Set',
                     EspFormID.new('impact', ['IPDS'])),
    EspSubRecord.new('NAM7', 'Decapitation FX',
                     EspFormID.new('decap_fx', ['ARTO'])),
    EspSubRecord.new('ONAM', 'Open Loot Sound',
                     EspFormID.new('open_sound', ['SNDR'])),
    EspSubRecord.new('LNAM', 'Close Loot Sound',
                     EspFormID.new('close_sound', ['SNDR'])),
    EspSubRecord.new('NAME', 'Biped Object Name',
                     EspString.new('name', 'zstring')),
    # Movement Types (repeating MTYP+SPED pairs)
    EspGroup.new('Movement Type', [
        EspSubRecord.new('MTYP', 'Movement Type',
                         EspFormID.new('type', ['MOVT'])),
        EspSubRecord.new('SPED', 'Override Values',
                         EspByteArray.new('data')),
    ]),
    EspSubRecord.new('VNAM', 'Equipment Flags',
                     EspInteger.new('flags', IntType.U32)),
    EspSubRecord.new('QNAM', 'Equip Slot',
                     EspFormID.new('slot', ['EQUP'])),
    EspSubRecord.new('UNES', 'Unarmed Equip Slot',
                     EspFormID.new('slot', ['EQUP'])),
    EspSubRecord.new('PHTN', 'Phoneme Target Name',
                     EspString.new('name', 'zstring')),
    EspSubRecord.new('PHWT', 'Phoneme Weights',
                     EspByteArray.new('data')),
    EspSubRecord.new('WKMV', 'Base Movement Default - Walk',
                     EspFormID.new('type', ['MOVT'])),
    EspSubRecord.new('RNMV', 'Base Movement Default - Run',
                     EspFormID.new('type', ['MOVT'])),
    EspSubRecord.new('SWMV', 'Base Movement Default - Swim',
                     EspFormID.new('type', ['MOVT'])),
    EspSubRecord.new('FLMV', 'Base Movement Default - Fly',
                     EspFormID.new('type', ['MOVT'])),
    EspSubRecord.new('SNMV', 'Base Movement Default - Sneak',
                     EspFormID.new('type', ['MOVT'])),
    EspSubRecord.new('SPMV', 'Base Movement Default - Sprint',
                     EspFormID.new('type', ['MOVT'])),
    # Head Data section
    EspGroup.new('Head Data', [
        EspSubRecord.new('NAM0', 'Head Data Marker',
                         EspByteArray.new('data')),
        EspGroup.new('Male Head Data', [
            EspSubRecord.new('MNAM', 'Male Data Marker',
                             EspByteArray.new('data')),
            _race_head_part,
            _race_morph,
            EspSubRecord.new('RPRM', 'Race Preset Male',
                             EspFormID.new('preset', ['NPC_'])),
            EspSubRecord.new('AHCM', 'Available Hair Colors Male',
                             EspFormID.new('color', ['CLFM'])),
            EspSubRecord.new('FTSM', 'Face Details Texture Set Male',
                             EspFormID.new('texture', ['TXST'])),
            EspSubRecord.new('DFTM', 'Default Face Texture Male',
                             EspFormID.new('texture', ['TXST'])),
            _race_tint_entry,
            common.MODL,
            common.MODT,
        ]),
        EspGroup.new('Female Head Data', [
            EspSubRecord.new('NAM0', 'Female Head Data Marker',
                             EspByteArray.new('data')),
            EspSubRecord.new('FNAM', 'Female Data Marker',
                             EspByteArray.new('data')),
            _race_head_part,
            _race_morph,
            EspSubRecord.new('RPRF', 'Race Preset Female',
                             EspFormID.new('preset', ['NPC_'])),
            EspSubRecord.new('AHCF', 'Available Hair Colors Female',
                             EspFormID.new('color', ['CLFM'])),
            EspSubRecord.new('FTSF', 'Face Details Texture Set Female',
                             EspFormID.new('texture', ['TXST'])),
            EspSubRecord.new('DFTF', 'Default Face Texture Female',
                             EspFormID.new('texture', ['TXST'])),
            _race_tint_entry,
            common.MODL,
            common.MODT,
        ]),
    ]),
    # Morph race and Armor race (after Head Data)
    EspSubRecord.new('NAM8', 'Morph Race',
                     EspFormID.new('morph_race', ['RACE'])),
    EspSubRecord.new('RNAM', 'Armor Race',
                     EspFormID.new('armor_race', ['RACE'])),
])

QUST = EspRecord.new('QUST', 'Quest', [
    common.EDID,
    common.VMAD,
    common.FULL,
    EspSubRecord.new('DNAM', 'Data', EspByteArray.new('data')),
    EspSubRecord.new('ENAM', 'Event', EspString.new('event', 'zstring')),
    EspSubRecord.new('FLTR', 'Object Window Filter',
                     EspString.new('filter', 'zstring')),
    # Quest Dialogue/Story Manager Conditions (before NEXT marker)
    EspGroup.new('Quest Conditions', [
        EspSubRecord.new('CTDA', 'Condition', EspByteArray.new('data')),
        EspSubRecord.new('CIS2', 'Condition String', EspString.new('str', 'zstring')),
    ]),
    EspSubRecord.new('NEXT', 'Marker', EspByteArray.new('data')),
    # Stages (repeating INDX + QSDT + conditions)
    EspGroup.new('Stage', [
        EspSubRecord.new('INDX', 'Stage Index', EspByteArray.new('data')),
        EspSubRecord.new('QSDT', 'Stage Flags', EspByteArray.new('data')),
        EspSubRecord.new('CNAM', 'Log Entry', EspByteArray.new('data')),
        EspSubRecord.new('CITC', 'Condition Count',
                         EspInteger.new('count', IntType.U32)),
        EspSubRecord.new('CTDA', 'Condition', EspByteArray.new('data')),
        EspSubRecord.new('CIS2', 'Condition String', EspString.new('str', 'zstring')),
        EspSubRecord.new('NAM0', 'Stage Index Unused', EspByteArray.new('data')),
    ]),
    # Objectives
    EspGroup.new('Objective', [
        EspSubRecord.new('QOBJ', 'Objective Index',
                         EspInteger.new('index', IntType.U16)),
        EspSubRecord.new('FNAM', 'Flags', EspByteArray.new('data')),
        EspSubRecord.new('NNAM', 'Display Text', EspString.new('text', 'zstring')),
        EspGroup.new('Target', [
            EspSubRecord.new('QSTA', 'Target', EspByteArray.new('data')),
            EspSubRecord.new('CITC', 'Condition Count',
                             EspInteger.new('count', IntType.U32)),
            EspSubRecord.new('CTDA', 'Condition', EspByteArray.new('data')),
            EspSubRecord.new('CIS2', 'Condition String', EspString.new('str', 'zstring')),
        ]),
    ]),
    EspSubRecord.new('ANAM', 'Next Alias ID',
                     EspInteger.new('next_alias', IntType.U32)),
    # Aliases -- two types with same internal structure but different leaders
    EspGroup.new('Reference Alias', [
        EspSubRecord.new('ALST', 'Reference Alias ID',
                         EspInteger.new('id', IntType.U32)),
        EspSubRecord.new('ALID', 'Alias Name', EspString.new('name', 'zstring')),
        EspSubRecord.new('FNAM', 'Alias Flags', EspByteArray.new('data')),
        EspSubRecord.new('ALFI', 'Force Into Alias When Filled',
                         EspByteArray.new('data')),
        EspSubRecord.new('ALFL', 'Specific Location',
                         EspFormID.new('location', [])),
        EspSubRecord.new('ALFR', 'Forced Reference',
                         EspFormID.new('ref', ['REFR'])),
        EspSubRecord.new('ALFE', 'From Event', EspString.new('event', 'zstring')),
        EspSubRecord.new('ALEA', 'Alias Reference',
                         EspFormID.new('alias', [])),
        EspSubRecord.new('ALEQ', 'External Alias Reference',
                         EspByteArray.new('data')),
        EspSubRecord.new('ALFA', 'Alias Forced',
                         EspByteArray.new('data')),
        EspSubRecord.new('KNAM', 'Keyword',
                         EspFormID.new('keyword', ['KYWD'])),
        EspSubRecord.new('ALRT', 'Alias Reference Type',
                         EspByteArray.new('data')),
        EspSubRecord.new('ALUA', 'Unique Actor',
                         EspFormID.new('actor', ['NPC_'])),
        EspSubRecord.new('ALDN', 'Display Name',
                         EspFormID.new('name', [])),
        EspSubRecord.new('ALSP', 'Alias Spells',
                         EspFormID.new('spell', ['SPEL'])),
        EspSubRecord.new('ALFC', 'Alias Factions',
                         EspFormID.new('faction', ['FACT'])),
        EspSubRecord.new('ALPC', 'Alias Package Data',
                         EspFormID.new('package', ['PACK'])),
        EspSubRecord.new('ALFD', 'Alias Force Data',
                         EspByteArray.new('data')),
        EspSubRecord.new('KSIZ', 'Keyword Count',
                         EspInteger.new('count', IntType.U32)),
        EspSubRecord.new('KWDA', 'Keywords',
                         EspByteArray.new('data')),
        EspSubRecord.new('COCT', 'Item Count',
                         EspInteger.new('count', IntType.U32)),
        EspSubRecord.new('CNTO', 'Item', EspStruct.new('item', [
            EspFormID.new('item'),
            EspInteger.new('count', IntType.S32),
        ])),
        EspSubRecord.new('ECOR', 'Alias ECor',
                         EspFormID.new('ecor', [])),
        EspSubRecord.new('ALCO', 'Alias Create Object',
                         EspByteArray.new('data')),
        EspSubRecord.new('ALCA', 'Alias Create At',
                         EspByteArray.new('data')),
        EspSubRecord.new('ALCL', 'Alias Create Level',
                         EspByteArray.new('data')),
        EspSubRecord.new('ALNA', 'Alias Near', EspByteArray.new('data')),
        EspSubRecord.new('ALNT', 'Alias Near Type',
                         EspByteArray.new('data')),
        EspSubRecord.new('VTCK', 'Voice Types',
                         EspFormID.new('voice', ['VTYP', 'FLST'])),
        EspSubRecord.new('CITC', 'Condition Count',
                         EspInteger.new('count', IntType.U32)),
        EspSubRecord.new('CTDA', 'Condition', EspByteArray.new('data')),
        EspSubRecord.new('CIS2', 'Condition String', EspString.new('str', 'zstring')),
        EspSubRecord.new('ALED', 'Alias End',
                         EspByteArray.new('data')),
    ]),
    EspGroup.new('Location Alias', [
        EspSubRecord.new('ALLS', 'Location Alias ID',
                         EspInteger.new('id', IntType.U32)),
        EspSubRecord.new('ALID', 'Alias Name', EspString.new('name', 'zstring')),
        EspSubRecord.new('FNAM', 'Alias Flags', EspByteArray.new('data')),
        EspSubRecord.new('ALFL', 'Specific Location',
                         EspFormID.new('location', [])),
        EspSubRecord.new('ALFE', 'From Event', EspString.new('event', 'zstring')),
        EspSubRecord.new('ALEQ', 'External Alias Reference',
                         EspByteArray.new('data')),
        EspSubRecord.new('ALFA', 'Alias Forced',
                         EspByteArray.new('data')),
        EspSubRecord.new('KNAM', 'Keyword',
                         EspFormID.new('keyword', ['KYWD'])),
        EspSubRecord.new('ALDN', 'Display Name',
                         EspFormID.new('name', [])),
        EspSubRecord.new('CITC', 'Condition Count',
                         EspInteger.new('count', IntType.U32)),
        EspSubRecord.new('CTDA', 'Condition', EspByteArray.new('data')),
        EspSubRecord.new('CIS2', 'Condition String', EspString.new('str', 'zstring')),
        EspSubRecord.new('ALED', 'Alias End',
                         EspByteArray.new('data')),
    ]),
    # Quest globals
    EspSubRecord.new('QTGL', 'Quest Toggle',
                     EspByteArray.new('data')),
])


_ACBS_FLAGS = EspFlags.new({
    0: 'Female', 1: 'Essential', 2: 'Is CharGen Face Preset',
    3: 'Respawn', 4: 'Auto-calc Stats', 5: 'Unique',
    6: "Doesn't Affect Stealth Meter", 7: 'PC Level Mult',
    8: 'Use Template', 11: 'Protected', 14: 'Summonable',
    16: "Doesn't Bleed", 18: 'Bleedout Override',
    19: 'Opposite Gender Anims', 20: 'Simple Actor',
    23: 'Is Ghost', 28: 'Invulnerable',
})
ACBS = _ACBS_FLAGS.constants()

NPC_ = EspRecord.new('NPC_', 'Non-Player Character', [
    common.EDID,
    common.VMAD,
    common.OBND,
    EspSubRecord.new('ACBS', 'Configuration', EspStruct.new('acbs', [
        EspInteger.new('flags', IntType.U32, formatter=_ACBS_FLAGS),
        EspInteger.new('magicka_offset', IntType.S16),
        EspInteger.new('stamina_offset', IntType.S16),
        EspInteger.new('level', IntType.U16),
        EspInteger.new('calc_min_level', IntType.U16),
        EspInteger.new('calc_max_level', IntType.U16),
        EspInteger.new('speed_multiplier', IntType.U16),
        EspInteger.new('disposition_base', IntType.S16),
        EspInteger.new('template_flags', IntType.U16, formatter=EspFlags.new({
            0: 'Traits', 1: 'Stats', 2: 'Factions', 3: 'Spell List',
            4: 'AI Data', 5: 'AI Packages', 6: 'Model/Animation',
            7: 'Base Data', 8: 'Inventory', 9: 'Script',
            10: 'Def Pack List', 11: 'Attack Data', 12: 'Keywords',
        })),
        EspInteger.new('health_offset', IntType.S16),
        EspInteger.new('bleedout_override', IntType.U16),
    ])),
    # Factions (repeating)
    EspSubRecord.new('SNAM', 'Faction', EspStruct.new('faction', [
        EspFormID.new('faction', ['FACT']),
        EspInteger.new('rank', IntType.S8),
        EspByteArray.new('unused', size=3),
    ])),
    # Death item
    EspSubRecord.new('INAM', 'Death Item',
                     EspFormID.new('death_item', ['LVLI'])),
    EspSubRecord.new('VTCK', 'Voice Type',
                     EspFormID.new('voice_type', ['VTYP'])),
    EspSubRecord.new('TPLT', 'Template',
                     EspFormID.new('template', ['LVLN', 'NPC_'])),
    EspSubRecord.new('RNAM', 'Race',
                     EspFormID.new('race', ['RACE'])),
    # Spells
    EspSubRecord.new('SPCT', 'Spell Count',
                     EspInteger.new('count', IntType.U32)),
    EspSubRecord.new('SPLO', 'Actor Effect',
                     EspFormID.new('spell', ['SPEL', 'SHOU', 'LVSP'])),
    # Destruction data
    # EspSubRecord.new('DEST', ...) -- not yet implemented
    EspSubRecord.new('WNAM', 'Worn Armor',
                     EspFormID.new('worn_armor', ['ARMO'])),
    EspSubRecord.new('ANAM', 'Far Away Model',
                     EspFormID.new('far_model', ['ARMO'])),
    # Attack data
    EspSubRecord.new('ATKR', 'Attack Race',
                     EspFormID.new('attack_race', ['RACE'])),
    EspGroup.new('Attack', [
        EspSubRecord.new('ATKD', 'Attack Data',
                         EspByteArray.new('data')),
        EspSubRecord.new('ATKE', 'Attack Event',
                         EspString.new('event', 'zstring')),
    ]),
    EspSubRecord.new('SPOR', 'Spectator Override Package List',
                     EspFormID.new('spectator_override', ['FLST'])),
    EspSubRecord.new('OCOR', 'Observe Dead Body Override Package List',
                     EspFormID.new('observe_dead_override', ['FLST'])),
    EspSubRecord.new('GWOR', 'Guard Warn Override Package List',
                     EspFormID.new('guard_warn_override', ['FLST'])),
    EspSubRecord.new('ECOR', 'Race Override',
                     EspFormID.new('ecor', ['RACE'])),
    # Perks
    EspSubRecord.new('PRKZ', 'Perk Count',
                     EspInteger.new('count', IntType.U32)),
    EspSubRecord.new('PRKR', 'Perk', EspStruct.new('perk', [
        EspFormID.new('perk', ['PERK']),
        EspInteger.new('rank', IntType.U8),
        EspByteArray.new('unused', size=3),
    ])),
    # Inventory (repeating CNTO + optional COED pairs)
    EspSubRecord.new('COCT', 'Item Count',
                     EspInteger.new('count', IntType.U32)),
    EspGroup.new('Item', [
        EspSubRecord.new('CNTO', 'Item', EspStruct.new('item', [
            EspFormID.new('item'),
            EspInteger.new('count', IntType.S32),
        ])),
        EspSubRecord.new('COED', 'Extra Data', EspStruct.new('extra_data', [
            EspFormID.new('owner'),
            EspInteger.new('global_or_rank', IntType.U32),
            EspFloat.new('item_condition'),
        ])),
    ]),
    # AI data
    EspSubRecord.new('AIDT', 'AI Data', EspByteArray.new('ai_data')),
    # Packages (repeating)
    EspSubRecord.new('PKID', 'Package',
                     EspFormID.new('package', ['PACK'])),
    common.KSIZ,
    common.KWDA,
    EspSubRecord.new('CNAM', 'Class',
                     EspFormID.new('class_', ['CLAS'])),
    common.FULL,
    EspSubRecord.new('SHRT', 'Short Name', EspByteArray.new('short_name')),
    EspSubRecord.new('DATA', 'Marker', EspByteArray.new('data_marker')),
    EspSubRecord.new('DNAM', 'Player Skills', EspStruct.new('skills', [
        EspInteger.new('one_handed_value', IntType.U8),
        EspInteger.new('two_handed_value', IntType.U8),
        EspInteger.new('archery_value', IntType.U8),
        EspInteger.new('block_value', IntType.U8),
        EspInteger.new('smithing_value', IntType.U8),
        EspInteger.new('heavy_armor_value', IntType.U8),
        EspInteger.new('light_armor_value', IntType.U8),
        EspInteger.new('pickpocket_value', IntType.U8),
        EspInteger.new('lockpicking_value', IntType.U8),
        EspInteger.new('sneak_value', IntType.U8),
        EspInteger.new('alchemy_value', IntType.U8),
        EspInteger.new('speech_value', IntType.U8),
        EspInteger.new('alteration_value', IntType.U8),
        EspInteger.new('conjuration_value', IntType.U8),
        EspInteger.new('destruction_value', IntType.U8),
        EspInteger.new('illusion_value', IntType.U8),
        EspInteger.new('restoration_value', IntType.U8),
        EspInteger.new('enchanting_value', IntType.U8),
        EspInteger.new('one_handed_offset', IntType.U8),
        EspInteger.new('two_handed_offset', IntType.U8),
        EspInteger.new('archery_offset', IntType.U8),
        EspInteger.new('block_offset', IntType.U8),
        EspInteger.new('smithing_offset', IntType.U8),
        EspInteger.new('heavy_armor_offset', IntType.U8),
        EspInteger.new('light_armor_offset', IntType.U8),
        EspInteger.new('pickpocket_offset', IntType.U8),
        EspInteger.new('lockpicking_offset', IntType.U8),
        EspInteger.new('sneak_offset', IntType.U8),
        EspInteger.new('alchemy_offset', IntType.U8),
        EspInteger.new('speech_offset', IntType.U8),
        EspInteger.new('alteration_offset', IntType.U8),
        EspInteger.new('conjuration_offset', IntType.U8),
        EspInteger.new('destruction_offset', IntType.U8),
        EspInteger.new('illusion_offset', IntType.U8),
        EspInteger.new('restoration_offset', IntType.U8),
        EspInteger.new('enchanting_offset', IntType.U8),
        EspInteger.new('health', IntType.U16),
        EspInteger.new('magicka', IntType.U16),
        EspInteger.new('stamina', IntType.U16),
    ])),
    # Head parts (repeating)
    EspSubRecord.new('PNAM', 'Head Part',
                     EspFormID.new('head_part', ['HDPT'])),
    EspSubRecord.new('HCLF', 'Hair Color',
                     EspFormID.new('hair_color', ['CLFM'])),
    EspSubRecord.new('ZNAM', 'Combat Style',
                     EspFormID.new('combat_style', ['CSTY'])),
    EspSubRecord.new('GNAM', 'Gifts',
                     EspFormID.new('gift_filter', ['FLST'])),
    EspSubRecord.new('NAM5', 'Unknown', EspByteArray.new('nam5')),
    EspSubRecord.new('NAM6', 'Height', EspFloat.new('height')),
    EspSubRecord.new('NAM7', 'Weight', EspFloat.new('weight')),
    EspSubRecord.new('NAM8', 'Sound Level',
                     EspInteger.new('sound_level', IntType.U32)),
    # Sound overrides: CSDT header, then repeating CSDI+CSDC pairs
    EspGroup.new('Sound Type', [
        EspSubRecord.new('CSDT', 'Sound Type',
                         EspInteger.new('type', IntType.U32)),
        EspGroup.new('Sound', [
            EspSubRecord.new('CSDI', 'Sound',
                             EspFormID.new('sound', ['SNDR'])),
            EspSubRecord.new('CSDC', 'Sound Chance',
                             EspInteger.new('chance', IntType.U8)),
        ]),
    ]),
    EspSubRecord.new('CSCR', 'Inherits Sound From',
                     EspFormID.new('sound_source', ['NPC_'])),
    # Sound overrides: CSDT header, then repeating CSDI+CSDC pairs
    EspGroup.new('Sound Type', [
        EspSubRecord.new('CSDT', 'Sound Type',
                         EspInteger.new('type', IntType.U32)),
        EspGroup.new('Sound', [
            EspSubRecord.new('CSDI', 'Sound',
                             EspFormID.new('sound', ['SNDR'])),
            EspSubRecord.new('CSDC', 'Sound Chance',
                             EspInteger.new('chance', IntType.U8)),
        ]),
    ]),
    # Outfits
    EspSubRecord.new('DOFT', 'Default Outfit',
                     EspFormID.new('default_outfit', ['OTFT'])),
    EspSubRecord.new('SOFT', 'Sleep Outfit',
                     EspFormID.new('sleep_outfit', ['OTFT'])),
    EspSubRecord.new('DPLT', 'Default Package List',
                     EspFormID.new('default_package_list', ['FLST'])),
    EspSubRecord.new('CRIF', 'Crime Faction',
                     EspFormID.new('crime_faction', ['FACT'])),
    EspSubRecord.new('FTST', 'Head Texture',
                     EspFormID.new('head_texture', ['TXST'])),
    # Texture lighting color
    EspSubRecord.new('QNAM', 'Texture Lighting', EspStruct.new('qnam', [
        EspFloat.new('red'),
        EspFloat.new('green'),
        EspFloat.new('blue'),
    ])),
    # Face morph
    EspSubRecord.new('NAM9', 'Face Morph', EspByteArray.new('face_morph')),
    # Face parts
    EspSubRecord.new('NAMA', 'Face Parts', EspStruct.new('face_parts', [
        EspInteger.new('nose', IntType.U32),
        EspInteger.new('unknown', IntType.U32),
        EspInteger.new('eyes', IntType.U32),
        EspInteger.new('mouth', IntType.U32),
    ])),
    # Tint layers — repeating group. Each instance is TINI+TINC+TINV+TIAS.
    # TINI is the group leader: auto-sort collects each TINI and its
    # following TINC/TINV/TIAS into a GroupInstance, preserving the
    # interleaved order across instances.
    EspGroup.new('Tint Layer', [
        EspSubRecord.new('TINI', 'Tint Index',
                         EspInteger.new('index', IntType.U16)),
        EspSubRecord.new('TINC', 'Tint Color', EspStruct.new('color', [
            EspInteger.new('red', IntType.U8),
            EspInteger.new('green', IntType.U8),
            EspInteger.new('blue', IntType.U8),
            EspInteger.new('alpha', IntType.U8),
        ])),
        EspSubRecord.new('TINV', 'Tint Interpolation Value',
                         EspInteger.new('value', IntType.S32)),
        EspSubRecord.new('TIAS', 'Tint Preset',
                         EspInteger.new('preset', IntType.S16)),
    ]),
])


# ---------------------------------------------------------------------------
# Register all definitions
# ---------------------------------------------------------------------------

def register():
    """Register Skyrim SE definitions with the game registry."""
    registry = GameRegistry('tes5', 'Skyrim Special Edition')

    for record_def in [
        GMST, GLOB, KYWD, FLST,
        WEAP, ARMO, ALCH, AMMO, BOOK, MISC,
        LVLI, LVLN, COBJ, FACT, NPC_,
        HDPT, ARMA, RACE, TXST,
    ]:
        registry.register(record_def)

    GameRegistry.register_game(registry)
    return registry


# Auto-register on import
_registry = register()
