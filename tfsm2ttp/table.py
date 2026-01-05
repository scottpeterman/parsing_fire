"""
Table Parser (Category 1)

Handles simple tabular data with multiple rows of the same structure.
Examples: show ip arp, show cdp neighbors, show interfaces status
"""

from typing import List, Dict, Tuple, Optional

from .core import (
    filter_quality_rows,
    analyze_column_patterns,
    substitute_ttp_vars,
    generalize_pattern,
    pattern_signature,
)


def find_source_line(cli_lines: List[str], row_values: Dict[str, str]) -> Optional[Tuple[int, str]]:
    """
    Find the CLI line that contains all values from this row.
    Returns (line_number, line_content) or None.
    """
    values = [v for v in row_values.values() if v and v.strip()]
    if not values:
        return None

    for idx, line in enumerate(cli_lines):
        if all(val in line for val in values):
            return (idx, line)

    # Fallback: find line with most matches
    best_match = (0, None, "")
    for idx, line in enumerate(cli_lines):
        match_count = sum(1 for val in values if val in line)
        if match_count > best_match[0]:
            best_match = (match_count, idx, line)

    if best_match[1] is not None and best_match[0] >= 2:
        return (best_match[1], best_match[2])

    return None


def generate_table_template(headers: List[str], rows: List[List[str]],
                            cli_content: str, min_cols: int = 3) -> Tuple[bool, str]:
    """
    Generate TTP template for table-oriented data.
    Returns (success, template_or_error)
    """
    quality_rows = filter_quality_rows(headers, rows, min_cols)

    if not quality_rows:
        return False, f"# No quality rows found (need {min_cols} or more columns populated)"

    # Analyze all values per column to detect multi-word patterns
    column_analysis = analyze_column_patterns(quality_rows)

    cli_lines = cli_content.splitlines()
    ttp_patterns = {}
    used_lines = set()

    for row in quality_rows:
        try:
            result = find_source_line(cli_lines, row)
            if result is None:
                continue

            line_num, source_line = result

            if line_num in used_lines:
                continue
            used_lines.add(line_num)

            ttp_line = substitute_ttp_vars(source_line, row, column_analysis)
            ttp_line = generalize_pattern(ttp_line)

            sig = pattern_signature(ttp_line)
            if sig and sig not in ttp_patterns:
                ttp_patterns[sig] = (ttp_line, row)
        except Exception:
            continue

    if not ttp_patterns:
        return False, "# ERROR: Could not generate any TTP patterns from parsed data"

    # Build final template
    ttp_output = ""
    for sig, (pattern, example) in ttp_patterns.items():
        group_name = sig.replace(',', '_').lower()
        ttp_output += f'<group name="{group_name}">\n'
        ttp_output += pattern + "\n"
        ttp_output += "</group>\n"

    return True, ttp_output.rstrip()
