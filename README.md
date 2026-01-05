# Parsing Fire 🔥

**Unified Network CLI Parsing Toolkit - TextFSM & TTP engines with auto-matching, template testing, and automated conversion.**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Parsing Fire is a comprehensive toolkit for parsing network device CLI output. It provides:

- **Auto-matching engines** - Automatically find the best template for unknown CLI output
- **Template testers** - PyQt6 GUIs for debugging and validating templates
- **TextFSM → TTP converter** - Generate 800+ TTP templates from NTC-Templates
- **Database-driven workflow** - SQLite template libraries with scoring and validation

### The Problem

Network engineers face a fragmented parsing landscape:
- **TextFSM** has 1,000+ community templates (NTC-Templates) but verbose syntax
- **TTP** has cleaner syntax but limited template library
- Neither has good tooling for auto-detecting which template fits unknown output
- Testing templates requires manual trial and error

### The Solution

Parsing Fire unifies both ecosystems with shared tooling:

| Component | TextFSM | TTP |
|-----------|---------|-----|
| Auto-match engine | `tfsm_fire.py` | `ttp_fire.py` |
| GUI tester | `tfsm_fire_tester.py` | `ttp_fire_tester.py` |
| Template database | `tfsm_templates.db` | `ttp_templates.db` |
| Templates available | ~1,000 (NTC) | 828 (converted) |

Plus: **`textfsm_to_ttp.py`** - Automated converter with 83% success rate.

## Installation

```bash
# Clone the repository
git clone https://github.com/scottpeterman/parsing_fire.git
cd parsing_fire

# Install dependencies
pip install -r requirements.txt

# Or install as package
pip install -e .
```

### Requirements

```
textfsm>=1.1.0
ttp>=0.9.0
click>=8.0
PyQt6>=6.4.0      # For GUI testers
requests>=2.28    # For NTC download
```

## Quick Start

### Auto-Match Unknown CLI Output

```bash
# TextFSM - find best template for CLI output
cat switch_output.txt | python -m parsing_fire.tfsm_fire tfsm_templates.db "show"

# TTP - same workflow, different engine
cat switch_output.txt | python -m parsing_fire.ttp_fire ttp_templates.db "cisco_ios"

# With verbose scoring
python -m parsing_fire.tfsm_fire tfsm_templates.db "show version" -v < output.txt
```

### GUI Template Testers

```bash
# TextFSM tester
python -m parsing_fire.tfsm_fire_tester

# TTP tester  
python -m parsing_fire.ttp_fire_tester

# With specific database
python -m parsing_fire.ttp_fire_tester /path/to/ttp_templates.db
```

### Convert TextFSM → TTP

```bash
# Convert templates and export
python -m parsing_fire.tfsm2ttp tfsm_templates.db -n 1000 --export ./ttp_templates

# Build TTP database from exports
python -m parsing_fire.build_ttp_db ./ttp_templates -o ttp_templates.db
```

## Architecture

```
parsing_fire/
├── __init__.py
├── __main__.py
│
├── # TextFSM Tools
├── tfsm_fire.py              # Auto-matching engine
├── tfsm_fire_tester.py       # PyQt6 GUI tester
│
├── # TTP Tools  
├── ttp_fire.py               # Auto-matching engine
├── ttp_fire_tester.py        # PyQt6 GUI tester
├── build_ttp_db.py           # Build database from exports
│
├── # Converter
├── tfsm2ttp/
│   ├── __init__.py
│   ├── __main__.py           # CLI entry point
│   ├── converter.py          # Strategy router
│   ├── core.py               # Shared utilities
│   ├── table.py              # Tabular data parser
│   ├── paragraph.py          # Single-record parser
│   ├── multisection.py       # Repeating blocks parser
│   └── validation.py         # TTP validation
│
└── # Data
    ├── tfsm_templates.db     # TextFSM template library
    └── ttp_templates.db      # TTP template library (generated)
```

## Auto-Match Engines

Both engines use identical 4-factor scoring (0-100 scale):

| Factor | Points | Description |
|--------|--------|-------------|
| Record Count | 0-30 | Did the template find data? |
| Field Richness | 0-30 | How many fields per record? |
| Population Rate | 0-25 | Are fields actually filled? |
| Consistency | 0-15 | Uniform data across records? |

### CLI Usage

```bash
# Basic usage
cat output.txt | python -m parsing_fire.tfsm_fire db.db "filter"

# Options
-v, --verbose      Show detailed scoring
-t, --top N        Show top N matches (default: 5)
-j, --json         Output as JSON
-l, --list         List available templates
```

### Programmatic Usage

```python
from parsing_fire import TFSMAutoEngine, TTPAutoEngine

# TextFSM
tfsm = TFSMAutoEngine("tfsm_templates.db")
template, parsed, score, all_scores = tfsm.find_best_template(cli_output, "show version")

# TTP  
ttp = TTPAutoEngine("ttp_templates.db")
template, parsed, score, all_scores = ttp.find_best_template(cli_output, "cisco_ios")

# Direct parsing with known template
data = tfsm.parse(cli_output, "cisco_ios_show_version")
```

## GUI Testers

Both testers provide three tabs:

### Auto Test Tab
- Paste CLI output, set filter, click "Find Best Template"
- See all matching templates ranked by score
- Best match highlighted, parsed data displayed
- Double-click to load template into Manual Test

### Manual Test Tab
- Direct template testing without database
- Side-by-side template and CLI input
- Parsed results as table + raw JSON
- Perfect for template development

### Template Manager Tab
- Browse all templates with search/filter
- Full CRUD operations
- Import from directory or NTC GitHub
- Export templates to files

### Themes
- **Dark** (default) - Easy on the eyes
- **Light** - High contrast
- **Cyber** - Green on black terminal aesthetic

## TextFSM → TTP Converter

### How It Works

```
TextFSM Template + CLI Output
         │
         ▼
┌─────────────────────────┐
│ 1. Parse with TextFSM   │  ← Use TextFSM as "oracle"
│    to get values        │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 2. Find values in       │  ← Locate captured text
│    original CLI text    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 3. Replace with TTP     │  ← {{VARIABLE}} placeholders
│    syntax + types       │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 4. Validate TTP output  │  ← Verify same data captured
│    matches TextFSM      │
└─────────────────────────┘
```

### Three Parsing Strategies

| Strategy | Detection | Use Case |
|----------|-----------|----------|
| Multi-section | `Filldown` in TextFSM | `show interfaces`, `show cdp detail` |
| Table | Multiple rows, consistent columns | `show ip arp`, `show vlan` |
| Paragraph | Few rows, values across lines | `show version`, `show ntp status` |

### Results

| Metric | Value |
|--------|-------|
| Success Rate | 82.9% |
| Templates Generated | 828 |
| Processing Speed | 26+ templates/sec |

### Usage

```bash
# Test conversion
python -m parsing_fire.tfsm2ttp tfsm_templates.db -n 10 -v

# Batch convert with parallel processing
python -m parsing_fire.tfsm2ttp tfsm_templates.db -n 1000 -w 8 --export ./ttp_templates

# Filter by vendor
python -m parsing_fire.tfsm2ttp tfsm_templates.db -n 500 --vendor cisco arista

# Build database
python -m parsing_fire.build_ttp_db ./ttp_templates -o ttp_templates.db
```

## Database Schema

### TextFSM Database (`tfsm_templates.db`)

```sql
CREATE TABLE templates (
    id INTEGER PRIMARY KEY,
    cli_command TEXT UNIQUE,     -- "cisco_ios_show_version"
    cli_content TEXT,            -- Sample CLI output
    textfsm_content TEXT,        -- TextFSM template
    textfsm_hash TEXT,           -- MD5 for deduplication
    source TEXT,                 -- "ntc-templates"
    created TEXT                 -- ISO timestamp
);
```

### TTP Database (`ttp_templates.db`)

```sql
CREATE TABLE templates (
    id INTEGER PRIMARY KEY,
    cli_command TEXT UNIQUE,     -- "cisco_ios_show_version"
    ttp_content TEXT,            -- TTP template
    cli_content TEXT,            -- Sample CLI output
    textfsm_rows INTEGER,        -- Original TextFSM count
    ttp_rows INTEGER,            -- TTP parsed count
    match_ratio REAL,            -- Validation ratio
    source TEXT,                 -- "converted"
    created_at TIMESTAMP
);
```

## Complete Workflow Example

```bash
# 1. Start with NTC-Templates database
#    (or download via GUI: Template Manager → Download from NTC)

# 2. Convert TextFSM → TTP
python -m parsing_fire.tfsm2ttp tfsm_templates.db -n 1000 -w 8 --export ./ttp_templates
# Output: 828 templates exported

# 3. Build TTP database
python -m parsing_fire.build_ttp_db ./ttp_templates -o ttp_templates.db
# Output: ttp_templates.db created

# 4. Use auto-matching on unknown output
ssh router "show ip route" | python -m parsing_fire.ttp_fire ttp_templates.db "cisco"
# Output: Best match: cisco_ios_show_ip_route (score: 92.50)

# 5. Or use the GUI for interactive testing
python -m parsing_fire.ttp_fire_tester ttp_templates.db
```

## Why Both Engines?

| Aspect | TextFSM | TTP |
|--------|---------|-----|
| Syntax | Verbose, regex-heavy | Clean, Pythonic |
| Learning curve | Steeper | Gentler |
| Community templates | 1,000+ (NTC) | Limited |
| Nested data | Difficult | Native support |
| Performance | Fast | Fast |

**Use TextFSM when:** You need NTC-Templates compatibility, existing tooling.

**Use TTP when:** Starting fresh, prefer cleaner syntax, need nested output.

**Use Parsing Fire when:** You want the best of both, with auto-matching and easy testing.

## Contributing

Areas that need work:

1. **Reduce over-matching** in converter - Better pattern anchoring
2. **Improve multi-section detection** - Beyond Filldown heuristics  
3. **Add more NTC templates** to database - Expand sample CLI coverage
4. **Unit tests** - Comprehensive test coverage
5. **Documentation** - More examples, edge cases

### Development Setup

```bash
git clone https://github.com/scottpeterman/parsing_fire.git
cd parsing_fire
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Related Projects

- **[NTC-Templates](https://github.com/networktocode/ntc-templates)** - 1,000+ TextFSM templates
- **[TextFSM](https://github.com/google/textfsm)** - Google's template parser
- **[TTP](https://github.com/dmulyalin/ttp)** - Denis Mulyalin's Template Text Parser
- **[Netmiko](https://github.com/ktbyers/netmiko)** - Multi-vendor SSH library
- **[NAPALM](https://github.com/napalm-automation/napalm)** - Network automation abstraction

## License

MIT License - See [LICENSE](LICENSE) for details.

## Author

**Scott Peterman** - Network automation engineer, 30+ years in the field.

- GitHub: [@scottpeterman](https://github.com/scottpeterman)
- LinkedIn: [Scott Peterman](https://linkedin.com/in/yourprofile)

---

*"Use the tools you have to solve real problems."* - The 100-year-old hammer philosophy.