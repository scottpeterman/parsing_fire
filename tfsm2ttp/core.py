"""
Core utilities for TextFSM to TTP conversion.

Contains shared functions for parsing, type inference, and variable substitution.
"""

import textfsm
import re
from io import StringIO
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


def parse_with_textfsm(template_content: str, cli_content: str) -> Tuple[List[str], List[List[str]]]:
    """Parse CLI output with TextFSM template, return headers and rows."""
    try:
        template_file = StringIO(template_content)
        fsm = textfsm.TextFSM(template_file)
        parsed = fsm.ParseText(cli_content)
        return fsm.header, parsed
    except textfsm.TextFSMTemplateError as e:
        raise ValueError(f"Invalid TextFSM template: {e}")
    except Exception as e:
        raise ValueError(f"TextFSM parsing failed: {e}")


def rows_to_dicts(headers: List[str], rows: List[List[str]]) -> List[Dict[str, str]]:
    """Convert TextFSM rows to list of dicts, handling list values."""
    result = []
    for row in rows:
        if not row:
            continue
        row_dict = {}
        for h, v in zip(headers, row):
            try:
                if isinstance(v, list):
                    v = ', '.join(str(x) for x in v if x) if v else ''
                if v and isinstance(v, str) and v.strip():
                    row_dict[h] = v.strip()
            except (TypeError, AttributeError):
                continue
        if row_dict:
            result.append(row_dict)
    return result


def filter_quality_rows(headers: List[str], rows: List[List[str]], min_cols: int = 3) -> List[Dict[str, str]]:
    """Filter to rows with at least min_cols populated columns."""
    if not headers or not rows:
        return []

    quality_rows = []
    for row in rows:
        if not row:
            continue
        row_dict = {}
        for h, v in zip(headers, row):
            try:
                if isinstance(v, list):
                    v = ', '.join(str(x) for x in v if x) if v else ''
                if v and isinstance(v, str) and v.strip():
                    row_dict[h] = v.strip()
            except (TypeError, AttributeError):
                continue
        if len(row_dict) >= min_cols:
            quality_rows.append(row_dict)
    return quality_rows


def analyze_column_patterns(quality_rows: List[Dict[str, str]]) -> Dict[str, Dict]:
    """
    Analyze all values for each column across all rows.
    Returns {column_name: {'has_spaces': bool, 'all_values': [...]}}
    """
    column_analysis = defaultdict(lambda: {'has_spaces': False, 'all_values': []})

    for row in quality_rows:
        for col_name, value in row.items():
            column_analysis[col_name]['all_values'].append(value)
            if ' ' in value:
                column_analysis[col_name]['has_spaces'] = True

    return dict(column_analysis)


def infer_variable_type(var_name: str, sample_value: str,
                        column_has_spaces: bool = False,
                        is_last_field: bool = False) -> str:
    """
    Infer TTP regex constraint based on variable name and sample value.
    Returns TTP variable with appropriate filter.

    Args:
        var_name: Variable name
        sample_value: Sample value from one row
        column_has_spaces: True if ANY value in this column has spaces
        is_last_field: True if this is the last field on the line
    """
    var_name_lower = var_name.lower()

    # If column has spaces in any row, use ORPHRASE
    if column_has_spaces:
        return '{{' + var_name + ' | ORPHRASE}}'

    # If last field on line, use ORPHRASE (captures remainder including commas)
    if is_last_field:
        return '{{' + var_name + ' | ORPHRASE}}'

    # Status fields often have multi-word values like "Power Loss", "Not Installed"
    if any(x in var_name_lower for x in ['status', 'state']):
        return '{{' + var_name + ' | ORPHRASE}}'

    # Numeric patterns - reject header separators
    if any(x in var_name_lower for x in ['port', 'vlan', 'id', 'count', 'slot', 'module', 'vid', 'rev', 'stratum']):
        if sample_value.isdigit():
            return '{{' + var_name + r' | re("\\d+")}}'

    # IP addresses
    if any(x in var_name_lower for x in ['ip', 'addr', 'address', 'reference']):
        if re.match(r'\d+\.\d+\.\d+\.\d+', sample_value):
            return '{{' + var_name + r' | re("\\d+\\.\\d+\\.\\d+\\.\\d+")}}'

    # MAC addresses
    if 'mac' in var_name_lower:
        return '{{' + var_name + r' | re("[0-9a-fA-F:.-]+")}}'

    # Serial numbers - alphanumeric
    if any(x in var_name_lower for x in ['sn', 'serial']):
        return '{{' + var_name + r' | re("\\w+")}}'

    # Version strings (common in show version)
    if any(x in var_name_lower for x in ['version', 'ver']):
        return '{{' + var_name + r' | re("[\\d\\.\\(\\)A-Za-z]+")}}'

    # Uptime patterns (e.g., "2 weeks, 3 days")
    if 'uptime' in var_name_lower:
        return '{{' + var_name + ' | ORPHRASE}}'

    # Hostname
    if any(x in var_name_lower for x in ['hostname', 'host']):
        return '{{' + var_name + r' | re("\\S+")}}'

    # Image/filename patterns
    if any(x in var_name_lower for x in ['image', 'file', 'flash']):
        return '{{' + var_name + '}}'

    # Default: require at least one alphanumeric (reject pure separators)
    if sample_value and not any(c.isalnum() for c in sample_value):
        return '{{' + var_name + r' | re(".*\\w.*")}}'

    return '{{' + var_name + '}}'


def substitute_ttp_vars(line: str, row_values: Dict[str, str],
                        column_analysis: Dict[str, Dict] = None) -> str:
    """
    Replace captured values with TTP {{VAR_NAME}} syntax.
    Process longest values first to avoid partial substitution issues.
    Adds type-based regex constraints.

    Args:
        line: Source CLI line
        row_values: {var_name: value} for this row
        column_analysis: {col_name: {'has_spaces': bool}} from analyze_column_patterns
    """
    ttp_line = line
    column_analysis = column_analysis or {}

    # Sort by value length descending to avoid partial matches
    sorted_items = sorted(row_values.items(), key=lambda x: len(x[1]), reverse=True)

    # Determine which variable is last on the line (rightmost position)
    var_positions = {}
    for var_name, value in row_values.items():
        pos = line.find(value)
        if pos >= 0:
            var_positions[var_name] = pos + len(value)  # End position

    last_var = max(var_positions, key=var_positions.get) if var_positions else None

    for var_name, value in sorted_items:
        if not value or not value.strip():
            continue

        pos = ttp_line.find(value)
        if pos == -1:
            continue

        # Get column info
        col_info = column_analysis.get(var_name, {})
        has_spaces = col_info.get('has_spaces', False)
        is_last = (var_name == last_var)

        new_var = infer_variable_type(var_name, value,
                                      column_has_spaces=has_spaces,
                                      is_last_field=is_last)
        ttp_line = ttp_line.replace(value, new_var, 1)

    return ttp_line


def generalize_pattern(ttp_line: str) -> str:
    """
    Generalize a TTP pattern by normalizing whitespace.
    """
    stripped = ttp_line.lstrip()
    leading = ttp_line[:len(ttp_line) - len(stripped)]
    normalized = re.sub(r' {2,}', ' ', stripped)
    return leading + normalized


def pattern_signature(ttp_line: str) -> str:
    """
    Generate a signature for deduplication.
    Two lines with same variables in same order = same pattern.
    """
    vars_found = re.findall(r'\{\{(\w+)(?:\s*\|[^}]*)?\}\}', ttp_line)
    return ','.join(vars_found)
