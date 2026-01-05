"""
Multi-section Parser (Category 3)

Handles repeating blocks with section headers (Filldown patterns).
Examples: show interfaces, show cdp detail, show ospf neighbor detail
"""

import re
from typing import List, Dict, Tuple

from .core import (
    rows_to_dicts,
    analyze_column_patterns,
    substitute_ttp_vars,
    generalize_pattern,
)


def parse_textfsm_filldown_values(textfsm_template: str) -> Tuple[List[str], List[str]]:
    """
    Parse TextFSM template to identify Filldown vs regular values.
    Returns (filldown_vars, regular_vars)
    """
    filldown_vars = []
    regular_vars = []

    for line in textfsm_template.splitlines():
        line = line.strip()
        if line.startswith('Value'):
            # Parse: Value [Filldown] [Required] NAME (regex)
            parts = line.split()
            if len(parts) >= 3:
                # Find the variable name (first part that starts with uppercase after Value)
                is_filldown = 'Filldown' in parts

                # Variable name is typically after Value/Filldown/Required keywords
                for i, part in enumerate(parts[1:], 1):
                    if part not in ('Filldown', 'Required', 'List', 'Fillup') and not part.startswith('('):
                        var_name = part
                        if is_filldown:
                            filldown_vars.append(var_name)
                        else:
                            regular_vars.append(var_name)
                        break

    return filldown_vars, regular_vars


def generate_multisection_template(headers: List[str], rows: List[List[str]],
                                   cli_content: str, textfsm_template: str,
                                   min_cols: int = 3) -> Tuple[bool, str]:
    """
    Generate TTP template for multi-section data (repeating blocks).
    Uses nested groups: outer for section header, inner for data rows.
    Returns (success, template_or_error)
    """
    # Parse TextFSM to identify filldown values
    filldown_vars, regular_vars = parse_textfsm_filldown_values(textfsm_template)

    if not filldown_vars:
        return False, "# No Filldown values found - not multi-section data"

    row_dicts = rows_to_dicts(headers, rows)

    if not row_dicts:
        return False, "# ERROR: No parsed data from TextFSM"

    # Find a row with both filldown and regular values
    filldown_values = {}
    regular_values = {}

    for row in row_dicts:
        # Get filldown values from this row
        row_filldown = {var: row[var] for var in filldown_vars if var in row and row[var]}
        row_regular = {var: row[var] for var in regular_vars if var in row and row[var]}

        # We want a row that has both filldown and regular values (a complete record)
        if row_filldown and row_regular and len(row_regular) >= min_cols:
            filldown_values = row_filldown
            regular_values = row_regular
            break

    if not filldown_values:
        return False, "# No filldown values captured - not multi-section data"

    if len(regular_values) < min_cols:
        return False, f"# Insufficient regular values (need {min_cols}, got {len(regular_values)})"

    cli_lines = cli_content.splitlines()

    # Find the header line - contains filldown values but few/no regular values
    header_line = None
    for idx, line in enumerate(cli_lines):
        filldown_in_line = sum(1 for v in filldown_values.values() if v and len(v) > 1 and v in line)
        regular_in_line = sum(1 for v in regular_values.values() if v and len(v) > 1 and v in line)

        # Header line: has filldown values, minimal regular values
        if filldown_in_line >= 1 and regular_in_line <= 1:
            header_vars_in_line = {k: v for k, v in filldown_values.items() if v and v in line}
            if header_vars_in_line:
                header_line = (idx, line, header_vars_in_line)
                break

    if not header_line:
        return False, "# Could not identify section header line"

    header_idx = header_line[0]

    # Find the data line - contains regular values, NOT the header line
    data_line = None
    for idx, line in enumerate(cli_lines):
        if idx == header_idx:
            continue

        # Count regular values in this line (only count values > 1 char to avoid false matches)
        values_in_line = {}
        for k, v in regular_values.items():
            if v and len(v) > 1 and v in line:
                values_in_line[k] = v
            elif v and len(v) == 1:
                # For single-char values, require word boundary match
                if re.search(r'\b' + re.escape(v) + r'\b', line):
                    values_in_line[k] = v

        if len(values_in_line) >= min_cols:
            data_line = (idx, line, values_in_line)
            break

    if not data_line:
        return False, "# Could not identify data row line"

    # Analyze column patterns for both filldown and regular values
    column_analysis = analyze_column_patterns(row_dicts)

    # Generate header template
    header_source = header_line[1]
    header_vars = header_line[2]
    header_ttp = substitute_ttp_vars(header_source, header_vars, column_analysis)

    # Generate data row template
    data_source = data_line[1]
    data_vars = data_line[2]
    data_ttp = substitute_ttp_vars(data_source, data_vars, column_analysis)
    data_ttp = generalize_pattern(data_ttp)

    # Generate group names
    header_group = '_'.join(sorted(filldown_vars)[:3]).lower()
    data_group = '_'.join(sorted(data_vars.keys())[:3]).lower()

    # Build nested TTP template
    ttp_output = f'<group name="{header_group}">\n'
    ttp_output += header_ttp + "\n"
    ttp_output += f'<group name="{data_group}">\n'
    ttp_output += data_ttp + "\n"
    ttp_output += "</group>\n"
    ttp_output += "</group>"

    return True, ttp_output
