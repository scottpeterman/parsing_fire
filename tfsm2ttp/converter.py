"""
Main Converter

Routes to the appropriate parser based on data characteristics:
1. Multi-section (Filldown) -> multisection.py
2. Table (multiple rows, same structure) -> table.py
3. Paragraph (single record, multi-line) -> paragraph.py
"""

from typing import Tuple

from .core import parse_with_textfsm, rows_to_dicts
from .table import generate_table_template
from .paragraph import generate_paragraph_template
from .multisection import parse_textfsm_filldown_values, generate_multisection_template


def generate_ttp_template(template_content: str, cli_content: str, min_cols: int = 3) -> str:
    """
    Main function: Generate TTP template from TextFSM template + CLI output.

    Strategy (in order):
    1. Multi-section (Category 3): Repeating blocks like show interfaces, show cdp detail
       - Detected by Filldown values in TextFSM template
    2. Table (Category 1): Simple tabular data like show ip arp, show cdp neighbors
       - Multiple rows with same column structure
    3. Paragraph (Category 2): Single record across multiple lines like show version
       - 1-2 rows with many values spread across lines
    """
    # Parse with TextFSM
    headers, rows = parse_with_textfsm(template_content, cli_content)

    if not headers:
        return "# ERROR: No headers found in TextFSM template"

    if not rows:
        return "# ERROR: TextFSM produced no parsed rows"

    # Category 3: Try multi-section first (if TextFSM has Filldown values)
    filldown_vars, regular_vars = parse_textfsm_filldown_values(template_content)

    if filldown_vars:
        ms_success, ms_result = generate_multisection_template(
            headers, rows, cli_content, template_content, min_cols
        )
        if ms_success:
            return ms_result

    # Category 1: Try table parsing
    row_dicts = rows_to_dicts(headers, rows)
    num_rows = len(row_dicts)

    # Collect all unique values
    all_values = {}
    for row in row_dicts:
        all_values.update(row)
    total_values = len(all_values)

    # If few rows with many values spread across lines, skip to paragraph
    if num_rows <= 2 and total_values >= 4:
        cli_lines = cli_content.splitlines()
        lines_with_values = set()
        for val in all_values.values():
            for idx, line in enumerate(cli_lines):
                if val in line:
                    lines_with_values.add(idx)
                    break

        if len(lines_with_values) >= total_values * 0.5:
            # Skip table, go straight to paragraph
            para_success, para_result = generate_paragraph_template(
                headers, rows, cli_content, min_values=max(3, min_cols)
            )
            if para_success:
                return para_result

    # Try table parsing
    success, result = generate_table_template(headers, rows, cli_content, min_cols)

    if success:
        return result

    # Category 2: Table failed - try paragraph parsing as fallback
    para_success, para_result = generate_paragraph_template(
        headers, rows, cli_content, min_values=max(3, min_cols)
    )

    if para_success:
        return para_result

    # All failed - return the table error
    return result


def safe_generate_ttp_template(template_content: str, cli_content: str, min_cols: int = 3) -> Tuple[bool, str, str]:
    """
    Safe wrapper around generate_ttp_template.
    Returns (success, ttp_template_or_empty, error_message_or_empty)
    """
    try:
        result = generate_ttp_template(template_content, cli_content, min_cols)
        if result.startswith("# ERROR:") or result.startswith("# No quality"):
            return False, "", result
        return True, result, ""
    except ValueError as e:
        return False, "", str(e)
    except Exception as e:
        return False, "", f"Unexpected error: {type(e).__name__}: {str(e)[:100]}"
