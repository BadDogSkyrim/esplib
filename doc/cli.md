# esplib CLI Reference

Command-line tool for inspecting and modifying Bethesda plugin files.

## Usage

```
esplib <command> [options]
```

## Commands

### info

Show plugin header information and record statistics.

```
esplib info <plugin> [--format {text,json}] [-o OUTPUT]
```

**Example:**
```
$ esplib info Skyrim.esm

File: Skyrim.esm
Type: ESM
Version: 1.71
Records: 432,175
Groups: 105
Author: bnesmith
Masters: (none)

Record types:
  WEAP: 378
  ARMO: 2345
  NPC_: 5124
  ...
```

**JSON output:**
```
$ esplib info Skyrim.esm --format json
```

---

### dump

Dump records with typed field values.

```
esplib dump <plugin> [--type TYPE] [--form-id FORMID] [--editor-id EDITORID]
            [--game {tes5,fo4,sf1}] [--format {text,json,csv}]
            [--limit LIMIT] [-o OUTPUT]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--type TYPE` | Filter by record signature (e.g. WEAP, NPC_) |
| `--form-id FORMID` | Filter by FormID (hex) |
| `--editor-id EDITORID` | Filter by Editor ID |
| `--game GAME` | Game for schema-aware parsing (auto-detected if omitted) |
| `--format FORMAT` | Output format: text (default), json, csv |
| `--limit N` | Max records to output (0 = all) |
| `-o FILE` | Write to file instead of stdout |

**Examples:**
```
# All weapons with parsed fields
esplib dump Skyrim.esm --type WEAP --game tes5 --limit 10

# Single record by Editor ID
esplib dump MyMod.esp --editor-id IronSword --game tes5

# Export to CSV
esplib dump Skyrim.esm --type ARMO --game tes5 --format csv -o armors.csv
```

---

### diff

Compare two plugin files.

```
esplib diff <plugin1> <plugin2> [--field-level] [--game {tes5,fo4,sf1}]
            [--format {text,json}] [-o OUTPUT]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--field-level` | Show field-level differences (requires --game) |
| `--game GAME` | Game for field-level parsing |
| `--format FORMAT` | Output format: text (default), json |
| `-o FILE` | Write to file |

**Example:**
```
$ esplib diff Original.esp Modified.esp

Comparing: Original.esp <-> Modified.esp

Summary:
  Added:     3
  Removed:   1
  Changed:   12
  Identical: 245

Changed:
  WEAP [00] 012EB7 IronSword
  ARMO [00] 013952 IronArmor
  ...
```

---

### validate

Check plugin for structural issues.

```
esplib validate <plugin> [--game {tes5,fo4,sf1}]
                [--format {text,json}] [-o OUTPUT]
```

**Checks performed:**
- Duplicate FormIDs
- ESL FormID range violations (max 2048 records, IDs must be < 0x1000)
- References to missing masters

**Example:**
```
$ esplib validate MyMod.esp
OK -- no issues found

$ esplib validate Broken.esp
Issues found:
  Duplicate FormID: 0x00000800 (WEAP, ARMO)
```

**Exit code:** 0 if valid, 1 if issues found.

---

### rename-master

Rename a master dependency in a plugin.

```
esplib rename-master <plugin> <old_name> <new_name>
```

**Example:**
```
$ esplib rename-master MyMod.esp "OldMaster.esm" "NewMaster.esm"
Renamed master: 'OldMaster.esm' -> 'NewMaster.esm' in MyMod.esp
```

Creates a backup (.bak) before saving.

---

## Common Options

All commands support:

| Option | Description |
|--------|-------------|
| `-o, --output FILE` | Write output to file instead of stdout |
| `--format FORMAT` | Output format (text, json, or csv where supported) |

## Supported Games

| ID | Game |
|----|------|
| `tes5` | Skyrim Special Edition |
| `fo4` | Fallout 4 |
| `sf1` | Starfield |

Game is auto-detected from header version when possible. Use `--game` to override.
