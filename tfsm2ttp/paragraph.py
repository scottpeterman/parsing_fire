"""
Paragraph Parser (Category 2)

Handles single-record data spread across multiple lines.
Examples: show version, show ntp status, show system
"""

import re
from collections import defaultdict
from typing import List, Dict, Tuple

from .core import (
    rows_to_dicts,
    analyze_column_patterns,
    substitute_ttp_vars,
)


def map_values_to_lines(cli_lines: List[str], values: Dict[str, str]) -> Dict[str, List[int]]:
    """
    Map each variable to the line number(s) where its value appears.
    Returns {var_name: [line_indices]}
    """
    value_to_lines = defaultdict(list)

    for var_name, value in values.items():
        if not value or not value.strip():
            continue

        for idx, line in enumerate(cli_lines):
            if value in line:
                value_to_lines[var_name].append(idx)

    return dict(value_to_lines)


def build_paragraph_line_templates(cli_lines: List[str],
                                   value_to_lines: Dict[str, List[int]],
                                   all_values: Dict[str, str],
                                   column_analysis: Dict[str, Dict] = None) -> Dict[int, str]:
    """
    Build TTP template for each line that contains captured values.
    Returns {line_index: ttp_template_line}
    """
    column_analysis = column_analysis or {}

    # Invert mapping: line_index -> {var_name: value}
    line_to_values = defaultdict(dict)

    for var_name, line_indices in value_to_lines.items():
        if line_indices:
            best_idx = line_indices[0]  # Use first occurrence
            line_to_values[best_idx][var_name] = all_values[var_name]

    # Generate template for each line
    line_templates = {}
    for line_idx, values_in_line in sorted(line_to_values.items()):
        source_line = cli_lines[line_idx]
        ttp_line = substitute_ttp_vars(source_line, values_in_line, column_analysis)
        # Clean up excessive spaces but preserve structure
        ttp_line = re.sub(r' {3,}', '  ', ttp_line)
        line_templates[line_idx] = ttp_line

    return line_templates


def generate_paragraph_template(headers: List[str], rows: List[List[str]],
                                cli_content: str, min_values: int = 4) -> Tuple[bool, str]:
    """
    Generate TTP template for paragraph-oriented data (single record, multi-line).
    Returns (success, template_or_error)
    """
    row_dicts = rows_to_dicts(headers, rows)

    if not row_dicts:
        return False, "# ERROR: No parsed data from TextFSM"

    # Merge all rows into single value set
    all_values = {}
    for row in row_dicts:
        all_values.update(row)

    if len(all_values) < min_values:
        return False, f"# No quality data found (need {min_values} or more values, got {len(all_values)})"

    # Analyze column patterns (for paragraph, use row_dicts)
    column_analysis = analyze_column_patterns(row_dicts)

    cli_lines = cli_content.splitlines()

    # Map each value to its source line(s)
    value_to_lines = map_values_to_lines(cli_lines, all_values)

    if not value_to_lines:
        return False, "# ERROR: Could not map any values to source lines"

    # Build line-by-line template
    line_templates = build_paragraph_line_templates(cli_lines, value_to_lines,
                                                    all_values, column_analysis)

    if not line_templates:
        return False, "# ERROR: Could not generate line templates"

    # Assemble final template
    sorted_lines = sorted(line_templates.items())

    # Generate group name from variable names (first 4)
    var_names = '_'.join(sorted(all_values.keys())[:4]).lower()
    group_name = var_names if var_names else "parsed_data"

    ttp_output = f'<group name="{group_name}">\n'
    for line_idx, template_line in sorted_lines:
        ttp_output += template_line + "\n"
    ttp_output += "</group>"

    return True, ttp_output
