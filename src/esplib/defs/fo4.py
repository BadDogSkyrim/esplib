"""Fallout 4 record definitions.

Ported from wbDefinitionsFO4.pas and wbDefinitionsCommon.pas, mirroring the
structure of tes5.py. Only the record types the FO4 furrifier needs are
defined; unported types fall back to generic raw-bytes round-trip.

Key FO4 differences from Skyrim that drive the design here:
  - Face tint layers use TETI (type+index) + TEND (value+RGBA+template) pairs,
    replacing Skyrim's TINI/TINC/TINV/TIAS.
  - Face morphs use MSDK/MSDV (keys/values) and FMRI/FMRS, replacing NAM9.
  - NPC_ weight is an MWGT struct (thin/muscular/fat), not a single float.
  - ARMA/ARMO/RACE BOD2 is a single u32 (First Person Flags), not the Skyrim
    32-bit flags + armor-type pair.
  - CLFM (Color) is a first-class record with no Skyrim equivalent.

Header version: 0.95 (and 1.0). Form version: 131.
"""

from .types import (
    IntType, EspFlags, EspEnum,
    EspInteger, EspFloat, EspString, EspFormID, EspByteArray,
    EspGmstValue, EspAlternateTextures,
    EspStruct, EspArray, EspUnion, EspSubRecord, EspGroup, EspRecord,
)
from . import common
from .game import GameRegistry


# ---------------------------------------------------------------------------
# FO4-shared building blocks
# ---------------------------------------------------------------------------

# FO4 model block trailing fields recur per slot (MODC/MO2C.., MODS/MO2S..,
# MODF/MO2F..) with consistent types:
#   *C = Color Remapping Index (float32)
#   *S = Material Swap (FormID -> MSWP) — typed so copy_record remaps it
#   *F = Model Flags (u8 bitfield: Head/Torso/Right Hand/Left Hand)
ModelFlags = EspFlags.new({
    0: 'Head', 1: 'Torso', 2: 'Right Hand', 3: 'Left Hand',
})


def _model_color(sig):
    return EspSubRecord.new(sig, 'Color Remapping Index', EspFloat.new('color'))


def _model_swap(sig):
    return EspSubRecord.new(sig, 'Material Swap',
                            EspFormID.new('material_swap', ['MSWP']))


def _model_flags(sig):
    return EspSubRecord.new(sig, 'Model Flags',
                            EspInteger.new('flags', IntType.U8,
                                           formatter=ModelFlags))


MODC = _model_color('MODC')
MODS = _model_swap('MODS')
MODF = _model_flags('MODF')

# Conditions block — CTDA is a fixed struct in FO4 but we don't decode it;
# raw bytes round-trip fine and the furrifier never edits conditions.
CTDA = EspSubRecord.new('CTDA', 'Condition', EspByteArray.new('data'))

# Object bounds (FO4 OBND is the same 6×int16 as Skyrim).
OBND = common.OBND


# ===== Tier 0: Infrastructure =====

GMST = EspRecord.new('GMST', 'Game Setting', [
    common.EDID,
    # DATA type is determined by the first character of the EDID:
    # f=float, i=int32, s=string, b=bool — same scheme as Skyrim.
    EspSubRecord.new('DATA', 'Value', EspGmstValue.new('value')),
])

GLOB = EspRecord.new('GLOB', 'Global Variable', [
    common.EDID,
    EspSubRecord.new('FNAM', 'Type', EspInteger.new('type', IntType.U8,
        formatter=EspEnum.new({
            0: 'Unknown',
            ord('s'): 'Short',
            ord('l'): 'Long',
            ord('f'): 'Float',
            ord('b'): 'Boolean',
        }))),
    EspSubRecord.new('FLTV', 'Value', EspFloat.new('value')),
])

KeywordTypeEnum = EspEnum.new({
    0: 'None', 1: 'Component Tech Level', 2: 'Attach Point',
    3: 'Component Property', 4: 'Instantiation Filter', 5: 'Mod Association',
    6: 'Sound', 7: 'Anim Archetype', 8: 'Function Call', 9: 'Recipe Filter',
    10: 'Attraction Type', 11: 'Dialogue Subtype', 12: 'Quest Target',
    13: 'Anim Flavor', 14: 'Anim Gender', 15: 'Anim Face', 16: 'Quest Group',
    17: 'Anim Injured', 18: 'Dispel Effect',
})

KYWD = EspRecord.new('KYWD', 'Keyword', [
    common.EDID,
    EspSubRecord.new('CNAM', 'Color', EspStruct.new('color', [
        EspInteger.new('red', IntType.U8),
        EspInteger.new('green', IntType.U8),
        EspInteger.new('blue', IntType.U8),
        EspInteger.new('alpha', IntType.U8),
    ])),
    EspSubRecord.new('DNAM', 'Notes', EspString.new('notes', 'zstring')),
    EspSubRecord.new('TNAM', 'Type', EspInteger.new('type', IntType.U32,
                                                    formatter=KeywordTypeEnum)),
    EspSubRecord.new('DATA', 'Attraction Rule',
                     EspFormID.new('attraction_rule', ['AORU'])),
    common.FULL,
    EspSubRecord.new('NNAM', 'Display Name', EspString.new('name', 'zstring')),
])

FLST = EspRecord.new('FLST', 'Form List', [
    common.EDID,
    common.FULL,
    EspSubRecord.new('LNAM', 'Form', EspFormID.new('form')),
])


# ===== Moderate: TXST, CLFM, HDPT, ARMA, ARMO =====

# FO4 texture slot order in the file is TX00, TX01, TX03, TX04, TX05, TX02,
# TX06, TX07 (note 02 sits between 05 and 06 — matches xEdit's struct order).
TXST = EspRecord.new('TXST', 'Texture Set', [
    common.EDID,
    OBND,
    EspSubRecord.new('TX00', 'Diffuse', EspString.new('texture', 'zstring')),
    EspSubRecord.new('TX01', 'Normal/Gloss',
                     EspString.new('texture', 'zstring')),
    EspSubRecord.new('TX03', 'Glow', EspString.new('texture', 'zstring')),
    EspSubRecord.new('TX04', 'Height', EspString.new('texture', 'zstring')),
    EspSubRecord.new('TX05', 'Environment',
                     EspString.new('texture', 'zstring')),
    EspSubRecord.new('TX02', 'Wrinkles', EspString.new('texture', 'zstring')),
    EspSubRecord.new('TX06', 'Multilayer',
                     EspString.new('texture', 'zstring')),
    EspSubRecord.new('TX07', 'Smooth Spec',
                     EspString.new('texture', 'zstring')),
    EspSubRecord.new('DODT', 'Decal Data', EspByteArray.new('dodt')),
    EspSubRecord.new('DNAM', 'Flags', EspInteger.new('flags', IntType.U16,
        formatter=EspFlags.new({
            0: 'No Specular Map',
            1: 'FaceGen Textures',
            2: 'Has Model Space Normal Map',
        }))),
    EspSubRecord.new('MNAM', 'Material', EspString.new('material', 'zstring')),
])

# CLFM — Color record. CNAM is a union (RGBA bytes OR a float remapping index)
# decided by FNAM bit 1, but FNAM follows CNAM so xEdit reads it as a plain
# u32 with a formatter. We do the same: raw u32, interpreted by the consumer.
CLFM = EspRecord.new('CLFM', 'Color', [
    common.EDID,
    common.FULL,
    EspSubRecord.new('CNAM', 'Color/Index',
                     EspInteger.new('color', IntType.U32)),
    EspSubRecord.new('FNAM', 'Flags', EspInteger.new('flags', IntType.U32,
        formatter=EspFlags.new({
            0: 'Playable',
            1: 'Remapping Index',
            2: 'Extended LUT',
        }))),
    CTDA,
])

HeadpartTypeEnum = EspEnum.new({
    0: 'Misc', 1: 'Face', 2: 'Eyes', 3: 'Hair', 4: 'Facial Hair',
    5: 'Scar', 6: 'Eyebrows', 7: 'Meatcaps', 8: 'Teeth', 9: 'Head Rear',
})

HDPT = EspRecord.new('HDPT', 'Head Part', [
    common.EDID,
    common.FULL,
    common.MODL,
    common.MODT,
    MODC,
    MODS,
    MODF,
    EspSubRecord.new('DATA', 'Flags', EspInteger.new('flags', IntType.U8,
        formatter=EspFlags.new({
            0: 'Playable', 1: 'Male', 2: 'Female',
            4: 'Is Extra Part', 5: 'Use Solid Tint', 6: 'Uses Body Texture',
        }))),
    EspSubRecord.new('PNAM', 'Type',
                     EspInteger.new('type', IntType.U32,
                                    formatter=HeadpartTypeEnum)),
    EspSubRecord.new('HNAM', 'Extra Parts',
                     EspArray.new('extra_parts', EspFormID.new('part', ['HDPT']))),
    EspGroup.new('Part', [
        EspSubRecord.new('NAM0', 'Part Type',
                         EspInteger.new('type', IntType.U32,
                                        formatter=EspEnum.new({
                                            0: 'Race Morph',
                                            1: 'Tri',
                                            2: 'Chargen Morph',
                                        }))),
        EspSubRecord.new('NAM1', 'FileName',
                         EspString.new('filename', 'zstring')),
    ]),
    EspSubRecord.new('TNAM', 'Texture Set',
                     EspFormID.new('texture_set', ['TXST'])),
    EspSubRecord.new('CNAM', 'Color', EspFormID.new('color', ['CLFM'])),
    EspSubRecord.new('RNAM', 'Valid Races', EspFormID.new('valid_races', ['FLST'])),
    CTDA,
])

# BOD2 in FO4 is a single u32 (First Person Flags / biped object slots).
BOD2_FO4 = EspSubRecord.new('BOD2', 'Biped Body Template',
                            EspInteger.new('first_person_flags', IntType.U32))

ARMA = EspRecord.new('ARMA', 'Armor Addon', [
    common.EDID,
    BOD2_FO4,
    EspSubRecord.new('RNAM', 'Race', EspFormID.new('race', ['RACE'])),
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
    # Biped (world) models — male MOD2.., female MOD3..
    EspGroup.new('Male Biped Model', [
        EspSubRecord.new('MOD2', 'Male Model', EspString.new('model', 'zstring')),
        EspSubRecord.new('MO2T', 'Male Model Texture Data',
                         EspByteArray.new('data')),
        _model_color('MO2C'),
        _model_swap('MO2S'),
        _model_flags('MO2F'),
    ]),
    EspGroup.new('Female Biped Model', [
        EspSubRecord.new('MOD3', 'Female Model',
                         EspString.new('model', 'zstring')),
        EspSubRecord.new('MO3T', 'Female Model Texture Data',
                         EspByteArray.new('data')),
        _model_color('MO3C'),
        _model_swap('MO3S'),
        _model_flags('MO3F'),
    ]),
    # 1st person models — male MOD4.., female MOD5..
    EspGroup.new('Male 1st Person', [
        EspSubRecord.new('MOD4', 'Male 1st Person Model',
                         EspString.new('model', 'zstring')),
        EspSubRecord.new('MO4T', 'Male 1st Person Texture Data',
                         EspByteArray.new('data')),
        _model_color('MO4C'),
        _model_swap('MO4S'),
        _model_flags('MO4F'),
    ]),
    EspGroup.new('Female 1st Person', [
        EspSubRecord.new('MOD5', 'Female 1st Person Model',
                         EspString.new('model', 'zstring')),
        EspSubRecord.new('MO5T', 'Female 1st Person Texture Data',
                         EspByteArray.new('data')),
        _model_color('MO5C'),
        _model_swap('MO5S'),
        _model_flags('MO5F'),
    ]),
    EspSubRecord.new('NAM0', 'Male Skin Texture',
                     EspFormID.new('male_skin', ['TXST'])),
    EspSubRecord.new('NAM1', 'Female Skin Texture',
                     EspFormID.new('female_skin', ['TXST'])),
    EspSubRecord.new('NAM2', 'Male Skin Texture Swap List',
                     EspFormID.new('male_swap', ['FLST'])),
    EspSubRecord.new('NAM3', 'Female Skin Texture Swap List',
                     EspFormID.new('female_swap', ['FLST'])),
    EspSubRecord.new('MODL', 'Additional Races',
                     EspFormID.new('race', ['RACE'])),
    EspSubRecord.new('SNDD', 'Footstep Sound',
                     EspFormID.new('footstep_sound', ['FSTS'])),
    EspSubRecord.new('ONAM', 'Art Object', EspFormID.new('art_object', ['ARTO'])),
])

ARMO = EspRecord.new('ARMO', 'Armor', [
    common.EDID,
    common.VMAD,
    OBND,
    EspSubRecord.new('PTRN', 'Preview Transform',
                     EspFormID.new('transform', ['TRNS'])),
    common.FULL,
    common.EITM,
    EspSubRecord.new('EAMT', 'Enchantment Amount',
                     EspInteger.new('amount', IntType.U16)),
    # Male world model. ARMO world models carry MODC + MODS (no MODF flags).
    EspGroup.new('Male World Model', [
        EspSubRecord.new('MOD2', 'Male Model', EspString.new('model', 'zstring')),
        EspSubRecord.new('MO2T', 'Male Model Texture Data',
                         EspByteArray.new('data')),
        _model_color('MO2C'),
        _model_swap('MO2S'),
        EspSubRecord.new('ICON', 'Icon Image', EspString.new('icon', 'zstring')),
        EspSubRecord.new('MICO', 'Message Icon',
                         EspString.new('message_icon', 'zstring')),
    ]),
    EspGroup.new('Female World Model', [
        EspSubRecord.new('MOD4', 'Female Model',
                         EspString.new('model', 'zstring')),
        EspSubRecord.new('MO4T', 'Female Model Texture Data',
                         EspByteArray.new('data')),
        _model_color('MO4C'),
        _model_swap('MO4S'),
        EspSubRecord.new('ICO2', 'Icon Image 2', EspString.new('icon', 'zstring')),
        EspSubRecord.new('MIC2', 'Message Icon 2',
                         EspString.new('message_icon', 'zstring')),
    ]),
    BOD2_FO4,
    common.DEST,
    common.YNAM,
    common.ZNAM,
    common.ETYP,
    EspSubRecord.new('BIDS', 'Block Bash Impact Data Set',
                     EspFormID.new('bash_impact', ['IPDS'])),
    EspSubRecord.new('BAMT', 'Alternate Block Material',
                     EspFormID.new('block_material', ['MATT'])),
    EspSubRecord.new('RNAM', 'Race', EspFormID.new('race', ['RACE'])),
    common.KSIZ,
    common.KWDA,
    common.DESC,
    EspSubRecord.new('INRD', 'Instance Naming', EspByteArray.new('data')),
    # Addon models: repeating INDX + MODL pairs
    EspGroup.new('Model', [
        EspSubRecord.new('INDX', 'Addon Index',
                         EspInteger.new('index', IntType.U16)),
        EspSubRecord.new('MODL', 'Armor Addon', EspFormID.new('addon', ['ARMA'])),
    ]),
    EspSubRecord.new('DATA', 'Data', EspStruct.new('data', [
        EspInteger.new('value', IntType.S32),
        EspFloat.new('weight'),
        EspInteger.new('health', IntType.U32),
    ])),
    EspSubRecord.new('FNAM', 'Armor Rating Data', EspStruct.new('fnam', [
        EspInteger.new('armor_rating', IntType.U16),
        EspInteger.new('base_addon_index', IntType.U16),
        EspInteger.new('stagger_rating', IntType.U8),
        EspByteArray.new('unused', size=3),
    ])),
    EspSubRecord.new('TNAM', 'Template Armor',
                     EspFormID.new('template', ['ARMO'])),
])


# ===== Appearance core: RACE, NPC_ =====

# -- RACE flags (FO4 layout) --
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

# Race head data is shared between Male/Female sections. Each section is a run
# of head-part entries (INDX + HEAD), presets (RPRM/RPRF), hair colors
# (AHCM/AHCF), face details (FTSM/FTSF), default face texture (DFTM/DFTF), then
# the tint-template groups (TTGP/TETI/TTEF/CTDA/TTET/TTEB/TTEC/TTED) and morph
# groups. The tint/morph group internals are complex and version-dependent;
# the furrifier copies them wholesale, so we keep the FormID-bearing leaders
# typed and let the rest round-trip as raw bytes.
_race_head_part = EspGroup.new('Head Part', [
    EspSubRecord.new('INDX', 'Head Part Number',
                     EspInteger.new('index', IntType.U32)),
    EspSubRecord.new('HEAD', 'Head Part', EspFormID.new('head_part', ['HDPT'])),
])

RACE = EspRecord.new('RACE', 'Race', [
    common.EDID,
    EspSubRecord.new('STCP', 'Animation Sound', EspFormID.new('sound', ['STAG'])),
    common.FULL,
    common.DESC,
    EspSubRecord.new('SPCT', 'Spell Count',
                     EspInteger.new('count', IntType.U32)),
    EspSubRecord.new('SPLO', 'Spell', EspFormID.new('spell', ['SPEL'])),
    EspSubRecord.new('WNAM', 'Skin', EspFormID.new('skin', ['ARMO'])),
    BOD2_FO4,
    common.KSIZ,
    common.KWDA,
    EspSubRecord.new('PRPS', 'Properties', EspByteArray.new('data')),
    EspSubRecord.new('APPR', 'Attach Parent Slots', EspByteArray.new('data')),
    # DATA is a large version-dependent struct; opaque round-trip.
    EspSubRecord.new('DATA', 'Data', EspByteArray.new('data')),
    EspSubRecord.new('MNAM', 'Male Marker', EspByteArray.new('data')),
    EspSubRecord.new('ANAM', 'Skeletal Model', EspString.new('skeleton', 'zstring')),
    common.MODT,
    EspSubRecord.new('FNAM', 'Female Marker', EspByteArray.new('data')),
    EspSubRecord.new('NAM2', 'Marker NAM2', EspByteArray.new('data')),
    EspSubRecord.new('MTNM', 'Movement Type Name',
                     EspString.new('name', 'zstring')),
    EspSubRecord.new('VTCK', 'Voices', EspArray.new('voices',
                     EspFormID.new('voice', ['VTYP']))),
    EspSubRecord.new('HCLF', 'Default Hair Colors', EspArray.new('hair_colors',
                     EspFormID.new('color', ['CLFM']))),
    EspSubRecord.new('TINL', 'Total Tints In List',
                     EspInteger.new('count', IntType.U16)),
    EspSubRecord.new('PNAM', 'FaceGen Main Clamp', EspFloat.new('clamp')),
    EspSubRecord.new('UNAM', 'FaceGen Face Clamp', EspFloat.new('clamp')),
    EspSubRecord.new('ATKR', 'Attack Race', EspFormID.new('attack_race', ['RACE'])),
    EspGroup.new('Attack', [
        EspSubRecord.new('ATKD', 'Attack Data', EspByteArray.new('data')),
        EspSubRecord.new('ATKE', 'Attack Event', EspString.new('event', 'zstring')),
    ]),
    EspSubRecord.new('GNAM', 'Body Part Data',
                     EspFormID.new('body_part_data', ['BPTD'])),
    EspSubRecord.new('NAM3', 'Marker NAM3', EspByteArray.new('data')),
    EspSubRecord.new('NAM4', 'Impact Material Type',
                     EspFormID.new('material', ['MATT'])),
    EspSubRecord.new('NAM5', 'Impact Data Set', EspFormID.new('impact', ['IPDS'])),
    EspSubRecord.new('NAM7', 'Dismember Blood Art',
                     EspFormID.new('blood_art', ['ARTO'])),
    EspSubRecord.new('CNAM', 'Meat Cap Texture Set',
                     EspFormID.new('texture', ['TXST'])),
    EspSubRecord.new('ONAM', 'Sound - Open Corpse',
                     EspFormID.new('open_sound', ['SNDR'])),
    EspSubRecord.new('LNAM', 'Sound - Close Corpse',
                     EspFormID.new('close_sound', ['SNDR'])),
    EspSubRecord.new('NAME', 'Biped Object Name',
                     EspString.new('name', 'zstring')),
    # Head data — male then female. We type the FormID-bearing leaders;
    # tint/morph group internals round-trip as raw subrecords.
    EspGroup.new('Head Data', [
        EspSubRecord.new('NAM0', 'Head Data Marker', EspByteArray.new('data')),
        _race_head_part,
        EspSubRecord.new('RPRM', 'Race Preset Male',
                         EspFormID.new('preset', ['NPC_'])),
        EspSubRecord.new('RPRF', 'Race Preset Female',
                         EspFormID.new('preset', ['NPC_'])),
        EspSubRecord.new('AHCM', 'Hair Color Male',
                         EspFormID.new('color', ['CLFM'])),
        EspSubRecord.new('AHCF', 'Hair Color Female',
                         EspFormID.new('color', ['CLFM'])),
        EspSubRecord.new('FTSM', 'Face Details Texture Set Male',
                         EspFormID.new('texture', ['TXST'])),
        EspSubRecord.new('FTSF', 'Face Details Texture Set Female',
                         EspFormID.new('texture', ['TXST'])),
        EspSubRecord.new('DFTM', 'Default Face Texture Male',
                         EspFormID.new('texture', ['TXST'])),
        EspSubRecord.new('DFTF', 'Default Face Texture Female',
                         EspFormID.new('texture', ['TXST'])),
    ]),
    EspSubRecord.new('NAM8', 'Morph Race', EspFormID.new('morph_race', ['RACE'])),
    EspSubRecord.new('RNAM', 'Armor Race', EspFormID.new('armor_race', ['RACE'])),
])


# -- NPC_ ACBS flags (FO4 layout) --
NpcAcbsFlags = EspFlags.new({
    0: 'Female', 1: 'Essential', 2: 'Is CharGen Face Preset', 3: 'Respawn',
    4: 'Auto-calc stats', 5: 'Unique', 6: "Doesn't affect stealth meter",
    7: 'PC Level Mult', 9: 'Calc For Each Template', 11: 'Protected',
    14: 'Summonable', 16: "Doesn't bleed", 18: 'Bleedout Override',
    19: 'Opposite Gender Anims', 20: 'Simple Actor', 23: 'No Activation/Hellos',
    24: 'Diffuse Alpha Test', 29: 'Is Ghost', 31: 'Invulnerable',
})

# FO4 face tint layer: TETI (data type + index) followed by TEND
# (value + RGBA + template color index). Pairs repeat per layer.
_npc_face_tint = EspGroup.new('Face Tint Layer', [
    EspSubRecord.new('TETI', 'Index', EspStruct.new('teti', [
        EspInteger.new('data_type', IntType.U16),
        EspInteger.new('index', IntType.U16),
    ])),
    # TEND layout: Value(u8) then OPTIONAL [RGBA(4) + Template Color Index(s16)].
    # xEdit marks everything past Value optional, so vanilla records appear at
    # size 1 (value only) or 7 (value + color + index). A fixed struct can't
    # express "optional from index 1", and the furrifier writes its own TEND,
    # so keep it raw for robust round-trip; consumers parse the bytes directly.
    EspSubRecord.new('TEND', 'Data', EspByteArray.new('data')),
])

# FO4 face morph: FMRI (index) + FMRS (7 floats + trailing bytes).
_npc_face_morph = EspGroup.new('Face Morph', [
    EspSubRecord.new('FMRI', 'Index', EspInteger.new('index', IntType.U32)),
    EspSubRecord.new('FMRS', 'Values', EspByteArray.new('data')),
])

NPC_ = EspRecord.new('NPC_', 'Non-Player Character', [
    common.EDID,
    common.VMAD,
    OBND,
    EspSubRecord.new('PTRN', 'Preview Transform',
                     EspFormID.new('transform', ['TRNS'])),
    EspSubRecord.new('STCP', 'Animation Sound', EspFormID.new('sound', ['STAG'])),
    EspSubRecord.new('ACBS', 'Configuration', EspStruct.new('acbs', [
        EspInteger.new('flags', IntType.U32, formatter=NpcAcbsFlags),
        EspInteger.new('xp_value_offset', IntType.S16),
        EspInteger.new('level', IntType.U16),
        EspInteger.new('calc_min_level', IntType.U16),
        EspInteger.new('calc_max_level', IntType.U16),
        EspInteger.new('disposition_base', IntType.S16),
        EspInteger.new('template_flags', IntType.U16),
        EspInteger.new('bleedout_override', IntType.U16),
        EspByteArray.new('unknown', size=2),
    ])),
    # Faction: FormID(FACT) + Rank(s8). MUST be modeled (not raw bytes) so
    # copy_record remaps the faction FormID into a patch's master list — a raw
    # ByteArray leaves the file_index byte unremapped, so a DLC NPC copied into a
    # patch ends up pointing the faction at the wrong master (invalid faction).
    # FO4 has no trailing unused bytes here (those are pre-FO4 only) -> 5 bytes.
    EspSubRecord.new('SNAM', 'Faction', EspStruct.new('faction', [
        EspFormID.new('faction', ['FACT']),
        EspInteger.new('rank', IntType.S8),
    ])),
    EspSubRecord.new('INAM', 'Death Item', EspFormID.new('death_item', ['LVLI'])),
    EspSubRecord.new('VTCK', 'Voice', EspFormID.new('voice', ['VTYP'])),
    EspSubRecord.new('TPLT', 'Default Template',
                     EspFormID.new('template', ['LVLN', 'NPC_'])),
    EspSubRecord.new('LTPT', 'Legendary Template',
                     EspFormID.new('template', ['LVLN', 'NPC_'])),
    EspSubRecord.new('LTPC', 'Legendary Chance',
                     EspFormID.new('chance', ['GLOB'])),
    # Template Actors: 13 FormIDs (NPC_/LVLN/null), one per template-use
    # category, in xEdit's fixed order. Each names the actor that supplies that
    # category when the corresponding template flag is set. Modeled (not raw
    # bytes) so copy_record remaps every entry's master index. 13 * 4 = 52 bytes.
    EspSubRecord.new('TPTA', 'Template Actors', EspStruct.new('tpta', [
        EspFormID.new('traits', ['NPC_', 'LVLN']),
        EspFormID.new('stats', ['NPC_', 'LVLN']),
        EspFormID.new('factions', ['NPC_', 'LVLN']),
        EspFormID.new('spell_list', ['NPC_', 'LVLN']),
        EspFormID.new('ai_data', ['NPC_', 'LVLN']),
        EspFormID.new('ai_packages', ['NPC_', 'LVLN']),
        EspFormID.new('model_animation', ['NPC_', 'LVLN']),
        EspFormID.new('base_data', ['NPC_', 'LVLN']),
        EspFormID.new('inventory', ['NPC_', 'LVLN']),
        EspFormID.new('script', ['NPC_', 'LVLN']),
        EspFormID.new('def_package_list', ['NPC_', 'LVLN']),
        EspFormID.new('attack_data', ['NPC_', 'LVLN']),
        EspFormID.new('keywords', ['NPC_', 'LVLN']),
    ])),
    EspSubRecord.new('RNAM', 'Race', EspFormID.new('race', ['RACE'])),
    EspSubRecord.new('SPCT', 'Spell Count',
                     EspInteger.new('count', IntType.U32)),
    EspSubRecord.new('SPLO', 'Spell', EspFormID.new('spell', ['SPEL'])),
    # Destructible: DEST header + repeating stages (DSTD/DSTF). Modeled as a
    # group so the stage subrecords keep their position on modify+save instead
    # of being dumped to the end as unknowns. Contents stay opaque — the
    # furrifier never edits destruction data.
    EspGroup.new('Destructible', [
        EspSubRecord.new('DEST', 'Header', EspByteArray.new('data')),
        EspGroup.new('Stage', [
            EspSubRecord.new('DSTD', 'Stage Data', EspByteArray.new('data')),
            EspSubRecord.new('DSTF', 'Stage End', EspByteArray.new('data')),
        ]),
    ]),
    EspSubRecord.new('WNAM', 'Skin', EspFormID.new('skin', ['ARMO'])),
    EspSubRecord.new('ANAM', 'Far Away Model', EspFormID.new('model', ['ARMO'])),
    EspSubRecord.new('ATKR', 'Attack Race', EspFormID.new('attack_race', ['RACE'])),
    EspGroup.new('Attack', [
        EspSubRecord.new('ATKD', 'Attack Data', EspByteArray.new('data')),
        EspSubRecord.new('ATKE', 'Attack Event', EspString.new('event', 'zstring')),
    ]),
    EspSubRecord.new('SPOR', 'Spectator Override',
                     EspFormID.new('list', ['FLST'])),
    EspSubRecord.new('OCOR', 'Observe Dead Body Override',
                     EspFormID.new('list', ['FLST'])),
    EspSubRecord.new('GWOR', 'Guard Warn Override',
                     EspFormID.new('list', ['FLST'])),
    EspSubRecord.new('ECOR', 'Combat Override', EspFormID.new('list', ['FLST'])),
    EspSubRecord.new('FCPL', 'Follower Command', EspFormID.new('list', ['FLST'])),
    EspSubRecord.new('RCLR', 'Follower Elevator',
                     EspFormID.new('list', ['FLST'])),
    EspSubRecord.new('PRKZ', 'Perk Count', EspInteger.new('count', IntType.U32)),
    EspGroup.new('Perk', [
        EspSubRecord.new('PRKR', 'Perk', EspStruct.new('prkr', [
            EspFormID.new('perk', ['PERK']),
            EspInteger.new('rank', IntType.U8),
        ])),
    ]),
    EspSubRecord.new('PRPS', 'Properties', EspByteArray.new('data')),
    EspSubRecord.new('FTYP', 'Force Keyword', EspFormID.new('keyword', ['KYWD'])),
    EspSubRecord.new('NTRM', 'Native Terminal',
                     EspFormID.new('terminal', ['TERM'])),
    EspSubRecord.new('COCT', 'Item Count', EspInteger.new('count', IntType.U32)),
    EspGroup.new('Item', [
        EspSubRecord.new('CNTO', 'Item', EspStruct.new('cnto', [
            EspFormID.new('item'),
            EspInteger.new('count', IntType.S32),
        ])),
        EspSubRecord.new('COED', 'Extra Data', EspByteArray.new('data')),
    ]),
    EspSubRecord.new('AIDT', 'AI Data', EspByteArray.new('data')),
    EspSubRecord.new('PKID', 'Package', EspFormID.new('package', ['PACK'])),
    common.KSIZ,
    common.KWDA,
    EspSubRecord.new('APPR', 'Attach Parent Slots', EspByteArray.new('data')),
    # Object Template: OBTE count + repeating Combination + STOP marker. The
    # combination carries its OWN FULL (the combo's display name) — this MUST be
    # nested in a group, or auto-sort hoists those FULLs into the record-level
    # FULL slot and shreds the block. Contents stay opaque (furrifier doesn't
    # touch object templates); the group exists purely to preserve structure.
    EspGroup.new('Object Template', [
        EspSubRecord.new('OBTE', 'Count', EspByteArray.new('data')),
        EspGroup.new('Combination', [
            EspSubRecord.new('OBTF', 'Editor Marker', EspByteArray.new('data')),
            EspSubRecord.new('FULL', 'Combination Name', EspByteArray.new('data')),
            EspSubRecord.new('OBTS', 'Combination Data', EspByteArray.new('data')),
        ]),
        EspSubRecord.new('STOP', 'Marker', EspByteArray.new('data')),
    ]),
    EspSubRecord.new('CNAM', 'Class', EspFormID.new('class', ['CLAS'])),
    common.FULL,
    EspSubRecord.new('SHRT', 'Short Name', EspUnion.new(
        'short_name',
        decider=lambda ctx: 0 if ctx.extra.get('subrecord_size', 0) == 4 else 1,
        members=[
            EspInteger.new('string_id', IntType.U32),
            EspString.new('short_name', 'zstring'),
        ],
    )),
    EspSubRecord.new('DATA', 'Marker', EspByteArray.new('data')),
    EspSubRecord.new('DNAM', 'Data', EspStruct.new('dnam', [
        EspInteger.new('calculated_health', IntType.U16),
        EspInteger.new('calculated_action_points', IntType.U16),
        EspInteger.new('far_away_model_distance', IntType.U16),
        EspInteger.new('geared_up_weapons', IntType.U8),
        EspByteArray.new('unused', size=1),
    ])),
    EspSubRecord.new('PNAM', 'Head Part', EspFormID.new('head_part', ['HDPT'])),
    EspSubRecord.new('HCLF', 'Hair Color', EspFormID.new('color', ['CLFM'])),
    EspSubRecord.new('BCLF', 'Facial Hair Color', EspFormID.new('color', ['CLFM'])),
    EspSubRecord.new('ZNAM', 'Combat Style', EspFormID.new('style', ['CSTY'])),
    EspSubRecord.new('GNAM', 'Gift Filter', EspFormID.new('filter', ['FLST'])),
    EspSubRecord.new('NAM5', 'Unknown', EspByteArray.new('data')),
    EspSubRecord.new('NAM6', 'Height Min', EspFloat.new('height')),
    EspSubRecord.new('NAM7', 'Unused', EspFloat.new('value')),
    EspSubRecord.new('NAM4', 'Height Max', EspFloat.new('height')),
    EspSubRecord.new('MWGT', 'Weight', EspStruct.new('mwgt', [
        EspFloat.new('thin'),
        EspFloat.new('muscular'),
        EspFloat.new('fat'),
    ])),
    EspSubRecord.new('NAM8', 'Sound Level', EspInteger.new('level', IntType.U32)),
    # Actor sounds: CS2H count, then a repeating Sound entry of [CS2K optional
    # keyword + CS2D sound], then CS2E marker + CS2F byte. The Sound entry is
    # its own nested group so multiple entries keep their interleaved
    # CS2K/CS2D pairing instead of collapsing into all-CS2K-then-all-CS2D.
    EspGroup.new('Actor Sounds', [
        EspSubRecord.new('CS2H', 'Count', EspInteger.new('count', IntType.U32)),
        EspGroup.new('Sound', [
            EspSubRecord.new('CS2K', 'Sound Keyword',
                             EspFormID.new('keyword', ['KYWD'])),
            EspSubRecord.new('CS2D', 'Sound Type', EspByteArray.new('data')),
        ]),
        EspSubRecord.new('CS2E', 'End Marker', EspByteArray.new('data')),
        EspSubRecord.new('CS2F', 'Finalize', EspByteArray.new('data')),
    ]),
    EspSubRecord.new('CSCR', 'Inherits Sounds From',
                     EspFormID.new('npc', ['NPC_'])),
    EspSubRecord.new('PFRN', 'Power Armor Stand',
                     EspFormID.new('furniture', ['FURN'])),
    EspSubRecord.new('DOFT', 'Default Outfit', EspFormID.new('outfit', ['OTFT'])),
    EspSubRecord.new('SOFT', 'Sleeping Outfit', EspFormID.new('outfit', ['OTFT'])),
    EspSubRecord.new('DPLT', 'Default Package List',
                     EspFormID.new('list', ['FLST'])),
    EspSubRecord.new('CRIF', 'Crime Faction', EspFormID.new('faction', ['FACT'])),
    EspSubRecord.new('FTST', 'Head Texture', EspFormID.new('texture', ['TXST'])),
    EspSubRecord.new('QNAM', 'Texture Lighting', EspStruct.new('qnam', [
        EspFloat.new('red'),
        EspFloat.new('green'),
        EspFloat.new('blue'),
        EspFloat.new('alpha'),
    ])),
    EspSubRecord.new('MSDK', 'Morph Keys',
                     EspArray.new('keys', EspInteger.new('key', IntType.U32))),
    EspSubRecord.new('MSDV', 'Morph Values',
                     EspArray.new('values', EspFloat.new('value'))),
    _npc_face_tint,
    EspSubRecord.new('MRSV', 'Body Morph Region Values', EspStruct.new('mrsv', [
        EspFloat.new('head'),
        EspFloat.new('upper_torso'),
        EspFloat.new('arms'),
        EspFloat.new('lower_torso'),
        EspFloat.new('legs'),
    ])),
    _npc_face_morph,
    EspSubRecord.new('FMIN', 'Facial Morph Intensity', EspFloat.new('intensity')),
    EspSubRecord.new('ATTX', 'Activate Text Override',
                     EspString.new('text', 'zstring')),
])


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_registry = GameRegistry('fo4', 'Fallout 4')
for _rec in (GMST, GLOB, KYWD, FLST, TXST, CLFM, HDPT, ARMA, ARMO, RACE, NPC_):
    _registry.register(_rec)
GameRegistry.register_game(_registry)
