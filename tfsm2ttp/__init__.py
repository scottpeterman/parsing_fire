"""
TextFSM to TTP Converter

Converts TextFSM templates to TTP format using CLI output as a reference.
Uses TextFSM as an "oracle" to identify captured values, then reverse-engineers
a TTP template by substituting those values back into the original CLI output.

Supports three parsing strategies:
- Table: Multiple rows, same structure (show interfaces status, show cdp neighbors)
- Paragraph: Single record, values across many lines (show version, show ntp status)
- Multi-section: Repeating blocks with headers (show interfaces, show cdp detail)
"""

__version__ = "1.0.0"

from .core import (
    parse_with_textfsm,
    rows_to_dicts,
    filter_quality_rows,
    analyze_column_patterns,
    infer_variable_type,
    substitute_ttp_vars,
    generalize_pattern,
    pattern_signature,
)

from .table import (
    find_source_line,
    generate_table_template,
)

from .paragraph import (
    map_values_to_lines,
    build_paragraph_line_templates,
    generate_paragraph_template,
)

from .multisection import (
    parse_textfsm_filldown_values,
    generate_multisection_template,
)

from .validation import (
    validate_ttp_template,
    compare_results,
)

from .converter import (
    generate_ttp_template,
    safe_generate_ttp_template,
)

__all__ = [
    # Core utilities
    "parse_with_textfsm",
    "rows_to_dicts",
    "filter_quality_rows",
    "analyze_column_patterns",
    "infer_variable_type",
    "substitute_ttp_vars",
    "generalize_pattern",
    "pattern_signature",
    # Table parsing
    "find_source_line",
    "generate_table_template",
    # Paragraph parsing
    "map_values_to_lines",
    "build_paragraph_line_templates",
    "generate_paragraph_template",
    # Multi-section parsing
    "parse_textfsm_filldown_values",
    "generate_multisection_template",
    # Validation
    "validate_ttp_template",
    "compare_results",
    # Main converter
    "generate_ttp_template",
    "safe_generate_ttp_template",
]
