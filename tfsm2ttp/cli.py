#!/usr/bin/env python3
"""
CLI Entry Point

Provides command-line interface for the TextFSM to TTP converter.
Includes built-in examples, database testing, and batch processing.
"""

import os
import time
import multiprocessing
from typing import List, Dict, Tuple

from .core import (
    parse_with_textfsm,
    filter_quality_rows,
    rows_to_dicts,
)
from .converter import generate_ttp_template, safe_generate_ttp_template
from .validation import validate_ttp_template, compare_results
from .multisection import parse_textfsm_filldown_values


# =============================================================================
# WORKER FUNCTION FOR PARALLEL PROCESSING
# =============================================================================

def process_single_template(args: Tuple) -> Dict:
    """
    Worker function to process a single template.
    Takes a tuple to work with ProcessPoolExecutor.
    Returns a dict with results.
    """
    id_, cli_command, cli_content, textfsm_content, source, validate, min_cols = args

    result = {
        'id': id_,
        'command': cli_command,
        'source': source,
        'status': None,
        'ttp_template': None,
        'error': None,
        'textfsm_rows': 0,
        'ttp_rows': 0,
        'match_ratio': None,
        # For JSON export
        'textfsm_parsed': [],
        'ttp_parsed': [],
        'cli_content': cli_content,
        'textfsm_template': textfsm_content
    }

    # Validate inputs
    if not cli_content or not cli_content.strip():
        result['status'] = 'failed_generation'
        result['error'] = "Empty CLI content"
        return result

    if not textfsm_content or not textfsm_content.strip():
        result['status'] = 'failed_generation'
        result['error'] = "Empty TextFSM template"
        return result

    # Try to generate TTP template
    success, ttp_template, error = safe_generate_ttp_template(textfsm_content, cli_content, min_cols)

    if not success:
        if "No quality rows" in error or "No quality data" in error:
            result['status'] = 'no_patterns'
            result['error'] = error
        else:
            result['status'] = 'failed_generation'
            result['error'] = error
        return result

    result['ttp_template'] = ttp_template

    # Validate TTP if requested
    if validate:
        val_success, ttp_results, val_error = validate_ttp_template(ttp_template, cli_content)

        if val_success:
            try:
                headers, fsm_rows = parse_with_textfsm(textfsm_content, cli_content)
                quality_rows = filter_quality_rows(headers, fsm_rows, min_cols=min_cols)
                comparison = compare_results(quality_rows, ttp_results)

                result['textfsm_rows'] = comparison['textfsm_count']
                result['ttp_rows'] = comparison['ttp_count']

                # Store actual parsed data for JSON export
                result['textfsm_parsed'] = quality_rows
                result['ttp_parsed'] = ttp_results

                if comparison['ttp_count'] == 0:
                    result['status'] = 'failed_validation'
                    result['error'] = "TTP template produced 0 rows"
                else:
                    result['status'] = 'success'
                    if comparison['textfsm_count'] > 0:
                        result['match_ratio'] = comparison['ttp_count'] / comparison['textfsm_count']
            except Exception as e:
                result['status'] = 'success'
                result['error'] = f"Comparison error: {str(e)[:50]}"
        else:
            result['status'] = 'failed_validation'
            result['error'] = val_error
    else:
        result['status'] = 'success'

    return result


# =============================================================================
# DEBUG / ANALYSIS FUNCTIONS
# =============================================================================

def analyze_conversion(template_content: str, cli_content: str):
    """Debug/analysis function to show the conversion process."""
    headers, rows = parse_with_textfsm(template_content, cli_content)

    print("=" * 60)
    print("TEXTFSM PARSE RESULTS")
    print("=" * 60)
    print(f"Headers: {headers}")
    print(f"Total rows: {len(rows)}")
    print()

    quality_rows = filter_quality_rows(headers, rows, min_cols=3)
    print(f"Quality rows (≥3 cols): {len(quality_rows)}")
    print()

    for i, row in enumerate(quality_rows):
        print(f"Row {i + 1}: {row}")

    print()
    print("=" * 60)
    print("GENERATED TTP TEMPLATE")
    print("=" * 60)
    ttp = generate_ttp_template(template_content, cli_content)
    print(ttp)

    return ttp


# =============================================================================
# BUILT-IN EXAMPLES
# =============================================================================

def run_multisection_example():
    """Run a multi-section example (Category 3)."""
    textfsm_template = r'''Value Filldown INSTANCE (\d+)
Value Filldown ROUTER_ID (\d+\.\d+\.\d+\.\d+)
Value Filldown VRF (\S+)
Value AREA (\d+\.\d+\.\d+\.\d+)
Value TYPE (\S+)
Value INTERFACES (\d+)
Value NEIGHBORS (\d+)
Value NEIGHBORS_FULL (\d+)
Value ROUTER_LSAS (\d+)
Value NETWORK_LSAS (\d+)
Value SUMMARY_LSAS (\d+)
Value ASBR_LSAS (\d+)
Value NSSA_LSAS (\d+)

Start
  ^OSPF instance ${INSTANCE} with ID ${ROUTER_ID}, VRF ${VRF},.*$$
  ^${AREA}\s+${TYPE}\s+${INTERFACES}\s+${NEIGHBORS}\s+\(${NEIGHBORS_FULL}\s*\)\s+${ROUTER_LSAS}\s+${NETWORK_LSAS}\s+${SUMMARY_LSAS}\s+${ASBR_LSAS}\s+${NSSA_LSAS}\s*$$ -> Record
'''

    cli_output = '''OSPF instance 1 with ID 65.87.229.70, VRF default, ASBR
Time since last SPF: 14 s
Max LSAs: 12000, Total LSAs: 6
Type-5 Ext LSAs: 3
ID               Type   Intf   Nbrs (full) RTR LSA NW LSA  SUM LSA ASBR LSA TYPE-7 LSA
0.0.0.10         normal 6      2    (2   ) 3       0       0       0       0

OSPF instance 2 with ID 192.168.28.193, VRF mgmtVrf, ASBR
Time since last SPF: 1673 s
Max LSAs: 12000, Total LSAs: 357
Type-5 Ext LSAs: 152
ID               Type   Intf   Nbrs (full) RTR LSA NW LSA  SUM LSA ASBR LSA TYPE-7 LSA
0.0.0.0          normal 2      2    (2   ) 113     92      0       0       0'''

    print("\n" + "=" * 60)
    print("MULTI-SECTION EXAMPLE: OSPF Summary (Filldown)")
    print("=" * 60)

    headers, rows = parse_with_textfsm(textfsm_template, cli_output)
    print(f"Headers: {headers}")
    print(f"Rows parsed: {len(rows)}")

    filldown_vars, regular_vars = parse_textfsm_filldown_values(textfsm_template)
    print(f"Filldown vars: {filldown_vars}")
    print(f"Regular vars: {regular_vars}")

    print()
    print("Generated TTP Template:")
    ttp = generate_ttp_template(textfsm_template, cli_output)
    print(ttp)


def run_example():
    """Run the built-in table example."""
    textfsm_template = r'''Value PORT ([0-9/]+)
Value NAME (\S+)
Value SN (\S+)
Value DESCR (.+)
Value VID (\d+\.\d+|\d+)

Start
  ^\s*System\s+\S+?$$ -> Chassis

Chassis
  ^\s+Model
  ^\s+-
  ^\s+HW
  ^\s+${VID}\s+${SN}\s+\d+-\d+-\d+ -> Record
  ^\s+${NAME}?\s+${DESCR}$$
  ^\s*System.+(power supply|power-supply) -> Power_Supply

Power_Supply
  ^\s+Slot
  ^\s+-
  ^\s+${PORT}\s+${NAME}\s+${SN} -> Record
  ^\s*System.+(fan) -> Fan

Fan
  ^\s+Module
  ^\s+-
  ^\s+${PORT}?\s+\d+?\s+${NAME}?\s+${SN} -> Record
  ^\s*System.+ports -> Ports

Ports
  ^\s+${DESCR}\s+${PORT} -> Record
  ^\s*System.+transceiver -> Transceiver

Transceiver
  ^\s+${PORT}\s+${DESCR}\s+${NAME}\s+${SN}\s+${VID} -> Record
'''

    cli_output = '''System information
  DCS-7150S-52-CL 52-port SFP+ 10GigE 1RU + Clock
  02.00 JPE13120702 2013-03-27

System has 2 power supply slots
  Slot Model            Serial Number
  ---- ---------------- ----------------
  1    PWR-460AC-F      K192KU00241CZ
  2    PWR-460AC-F      K192L200751CZ

System has 4 fan modules
  Module Number of Fans Model            Serial Number
  ------- --------------- ---------------- ----------------
  1       1               FAN-7000-F       N/A
  2       1               FAN-7000-F       N/A
  3       1               FAN-7000-F       N/A
  4       1               FAN-7000-F       N/A

System has 53 ports
  Type             Count
  ---------------- ----
  Management       1
  Switched         52

System has 52 transceiver slots
  Port Manufacturer      Model            Serial Number    Rev
  ---- ---------------- ---------------- ---------------- ----
  1    Arista Networks  SFP-10G-SR       XCW1225FD753     0002
  2    Arista Networks  SFP-10G-SR       XCW1225FD753     0002
  51   Arista Networks  SFP-10G-SR       XCW1225FD753     0002
  52   Arista Networks  SFP-10G-SR       XCW1225FD753     0002
'''

    print("=" * 60)
    print("TABLE EXAMPLE: Arista show inventory")
    print("=" * 60)
    analyze_conversion(textfsm_template, cli_output)


def run_paragraph_example():
    """Run a paragraph-format example."""
    textfsm_template = r'''Value VERSION (\S+)
Value HOSTNAME (\S+)
Value UPTIME (.+)
Value IMAGE (\S+)
Value SERIAL (\S+)
Value MODEL (\S+)

Start
  ^.*Software.*Version ${VERSION}
  ^${HOSTNAME} uptime is ${UPTIME}
  ^System image file is "${IMAGE}"
  ^[Pp]rocessor board ID ${SERIAL}
  ^[Cc]isco ${MODEL} -> Record
'''

    cli_output = '''Cisco IOS Software, C2900 Software (C2900-UNIVERSALK9-M), Version 15.1(4)M4
Technical Support: http://www.cisco.com/techsupport
Copyright (c) 1986-2012 by Cisco Systems, Inc.

ROM: System Bootstrap, Version 15.0(1r)M15

router01 uptime is 2 weeks, 3 days, 14 hours, 22 minutes
System returned to ROM by power-on
System image file is "flash:c2900-universalk9-mz.SPA.151-4.M4.bin"

Cisco CISCO2911/K9 (revision 1.0) with 483328K/40960K bytes of memory.
Processor board ID FTX1234A5BC
3 Gigabit Ethernet interfaces
DRAM configuration is 64 bits wide with parity enabled.
255K bytes of non-volatile configuration memory.
'''

    print("\n" + "=" * 60)
    print("PARAGRAPH EXAMPLE: Cisco show version")
    print("=" * 60)

    headers, rows = parse_with_textfsm(textfsm_template, cli_output)
    print(f"Headers: {headers}")
    print(f"Rows parsed: {len(rows)}")

    if rows:
        print("Captured values:")
        for h, v in zip(headers, rows[0]):
            if v:
                print(f"  {h}: {v}")

    print()
    print("Generated TTP Template:")
    ttp = generate_ttp_template(textfsm_template, cli_output)
    print(ttp)


def run_ntp_example():
    """Another paragraph example: show ntp status."""
    textfsm_template = r'''Value CLOCK_STATE (\S+)
Value STRATUM (\d+)
Value REFERENCE (\d+\.\d+\.\d+\.\d+)
Value ACTUAL_FREQ ([\d\.]+)
Value OFFSET ([\d\.\-]+)
Value ROOT_DELAY ([\d\.]+)

Start
  ^Clock is ${CLOCK_STATE}, stratum ${STRATUM}, reference is ${REFERENCE}
  ^nominal freq is .*, actual freq is ${ACTUAL_FREQ} Hz
  ^clock offset is ${OFFSET} msec, root delay is ${ROOT_DELAY} msec -> Record
'''

    cli_output = '''Clock is synchronized, stratum 3, reference is 10.1.1.1
nominal freq is 250.0000 Hz, actual freq is 249.9987 Hz, precision is 2**18
reference time is E4A2B3C4.5678ABCD (14:32:44.123 UTC Mon Jan 6 2025)
clock offset is 1.2345 msec, root delay is 12.34 msec
root dispersion is 56.78 msec, peer dispersion is 0.12 msec
loopfilter state is 'CTRL' (Normal Controlled Loop)
'''

    print("\n" + "=" * 60)
    print("PARAGRAPH EXAMPLE: Cisco show ntp status")
    print("=" * 60)

    headers, rows = parse_with_textfsm(textfsm_template, cli_output)
    print(f"Headers: {headers}")
    print(f"Rows parsed: {len(rows)}")

    if rows:
        print("Captured values:")
        for h, v in zip(headers, rows[0]):
            if v:
                print(f"  {h}: {v}")

    print()
    print("Generated TTP Template:")
    ttp = generate_ttp_template(textfsm_template, cli_output)
    print(ttp)


# =============================================================================
# JSON EXPORT FOR REVIEW
# =============================================================================

def sanitize_filename(name: str) -> str:
    """
    Sanitize a string for use as a filename.
    Replaces invalid characters with underscores.
    """
    # Replace common problematic characters
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', ' ']
    result = name
    for char in invalid_chars:
        result = result.replace(char, '_')
    # Remove any leading/trailing underscores or dots
    result = result.strip('_.')
    # Collapse multiple underscores
    while '__' in result:
        result = result.replace('__', '_')
    return result if result else 'unnamed'


def export_json_results(filepath: str, result: Dict):
    """
    Export parsed results to JSON for review.
    Includes TextFSM results, TTP results, CLI content, and template.
    """
    import json

    export_data = {
        'command': result.get('command'),
        'source': result.get('source'),
        'status': result.get('status'),
        'match_ratio': result.get('match_ratio'),
        'textfsm_rows': result.get('textfsm_rows'),
        'ttp_rows': result.get('ttp_rows'),
        'ttp_template': result.get('ttp_template'),
        'error': result.get('error'),
        # These will be populated if we have the raw data
        'textfsm_parsed': result.get('textfsm_parsed', []),
        'ttp_parsed': result.get('ttp_parsed', []),
        'cli_content': result.get('cli_content', ''),
        'textfsm_template': result.get('textfsm_template', '')
    }

    with open(filepath, 'w') as f:
        json.dump(export_data, f, indent=2, default=str)


# =============================================================================
# DATABASE TESTING
# =============================================================================

def test_from_database(db_path: str, limit: int = 5, validate: bool = True, verbose: bool = False, workers: int = 1,
                       min_cols: int = 3, export_dir: str = None, min_ratio: float = 0.0,
                       vendors: List[str] = None, timeout: int = 30, batch_size: int = 50):
    """Test the converter against templates from the database.

    Args:
        db_path: Path to SQLite database
        limit: Maximum number of templates to process
        validate: Whether to validate TTP output against CLI content
        verbose: Print detailed output for each template
        workers: Number of parallel workers
        min_cols: Minimum columns for quality row detection
        export_dir: Directory to export successful TTP templates
        min_ratio: Minimum TTP/TextFSM ratio for export
        vendors: List of vendor names to filter (e.g., ['cisco', 'arista'])
        timeout: Timeout in seconds per template (default: 30)
        batch_size: Process templates in batches of this size (default: 50)
    """
    import sqlite3

    start_time = time.time()

    # Setup export directory if specified
    if export_dir:
        os.makedirs(export_dir, exist_ok=True)
        print(f"Exporting successful templates to: {export_dir}")
        if min_ratio > 0:
            print(f"Minimum match ratio for export: {min_ratio}")

    # Verify database exists
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
    except sqlite3.Error as e:
        print(f"ERROR: Cannot open database '{db_path}': {e}")
        return

    # Check if vendor column exists
    cursor.execute("PRAGMA table_info(templates)")
    columns = [col[1] for col in cursor.fetchall()]
    has_vendor_column = 'vendor' in columns

    # Build query with optional vendor filter
    base_query = """
        SELECT id, cli_command, cli_content, textfsm_content, source 
        FROM templates 
        WHERE cli_content IS NOT NULL 
          AND cli_content != ''
          AND textfsm_content IS NOT NULL 
          AND textfsm_content != ''
    """

    params = []

    if vendors:
        # Normalize vendor names to lowercase
        vendors = [v.lower().strip() for v in vendors]

        if has_vendor_column:
            # Use vendor column directly
            placeholders = ','.join(['?' for _ in vendors])
            base_query += f" AND LOWER(vendor) IN ({placeholders})"
            params.extend(vendors)
        else:
            # Filter by cli_command prefix (e.g., cisco_ios_show_version)
            vendor_conditions = []
            for vendor in vendors:
                vendor_conditions.append("LOWER(cli_command) LIKE ?")
                params.append(f"{vendor}%")
            base_query += f" AND ({' OR '.join(vendor_conditions)})"

        print(f"Filtering by vendor(s): {', '.join(vendors)}")

    base_query += " LIMIT ?"
    params.append(limit)

    # Get templates that have both cli_content and textfsm_content
    try:
        cursor.execute(base_query, params)
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"ERROR: Database query failed: {e}")
        conn.close()
        return

    conn.close()

    if not rows:
        if vendors:
            print(f"No templates found for vendor(s): {', '.join(vendors)}")
        else:
            print(f"No templates with CLI content found in {db_path}")
        return

    print(f"Testing {len(rows)} templates from {db_path}")
    if workers > 1:
        print(f"Using {workers} workers")
    print("=" * 80)

    # Prepare work items
    work_items = [
        (id_, cli_command, cli_content, textfsm_content, source, validate, min_cols)
        for id_, cli_command, cli_content, textfsm_content, source in rows
    ]

    stats = {
        'success': 0,
        'failed_generation': 0,
        'failed_validation': 0,
        'no_patterns': 0,
        'timeouts': 0,
        'errors': []
    }
    match_ratios = []
    results = []
    over_matched = []  # Templates where TTP found more than TextFSM
    export_errors = 0  # Count of failed exports

    if workers > 1:
        # Parallel processing with proper timeout and process termination
        from multiprocessing import Pool, TimeoutError as MPTimeoutError

        # Process in batches to avoid resource exhaustion
        actual_batch_size = min(batch_size, len(work_items))

        completed = 0
        for batch_start in range(0, len(work_items), actual_batch_size):
            batch = work_items[batch_start:batch_start + actual_batch_size]

            with Pool(processes=workers) as pool:
                async_results = []
                for item in batch:
                    ar = pool.apply_async(process_single_template, (item,))
                    async_results.append((item[0], ar))  # (template_id, async_result)

                for template_id, ar in async_results:
                    completed += 1
                    if not verbose:
                        print(f"\rProcessing: {completed}/{len(work_items)}", end="", flush=True)

                    try:
                        result = ar.get(timeout=timeout)
                        results.append(result)
                    except MPTimeoutError:
                        results.append({
                            'id': template_id,
                            'status': 'failed_generation',
                            'error': f"Timeout (>{timeout}s)"
                        })
                    except Exception as e:
                        results.append({
                            'id': template_id,
                            'status': 'failed_generation',
                            'error': f"Worker exception: {str(e)[:80]}"
                        })

                # Force terminate any hung workers before next batch
                pool.terminate()
                pool.join()

        if not verbose:
            print()
    else:
        # Sequential processing
        for i, item in enumerate(work_items):
            if not verbose:
                print(f"\rProcessing: {i + 1}/{len(work_items)}", end="", flush=True)
            result = process_single_template(item)
            results.append(result)

        if not verbose:
            print()

    # Process results
    exported_count = 0
    for result in results:
        status = result.get('status', 'failed_generation')

        if status == 'success':
            stats['success'] += 1
            if result.get('match_ratio') is not None:
                match_ratios.append(result['match_ratio'])

                # Track over-matched templates (TTP found more than TextFSM)
                if result['match_ratio'] > 1.0:
                    over_matched.append({
                        'command': result.get('command', '?'),
                        'ratio': result['match_ratio'],
                        'textfsm_rows': result.get('textfsm_rows', 0),
                        'ttp_rows': result.get('ttp_rows', 0)
                    })

                    # Export over-matched to separate folder for review
                    if export_dir and result.get('ttp_template') and result.get('command'):
                        try:
                            om_dir = os.path.join(export_dir, '_over_matched')
                            os.makedirs(om_dir, exist_ok=True)
                            cmd = result['command']
                            safe_cmd = sanitize_filename(cmd)
                            json_filepath = os.path.join(om_dir, f"{safe_cmd}.json")
                            export_json_results(json_filepath, result)
                        except Exception:
                            pass

            # Export successful template if export_dir specified
            if export_dir and result.get('ttp_template') and result.get('command'):
                ratio = result.get('match_ratio', 0) or 0
                if ratio >= min_ratio:
                    try:
                        cmd = result['command']
                        safe_cmd = sanitize_filename(cmd)
                        filename = f"{safe_cmd}.ttp"
                        filepath = os.path.join(export_dir, filename)

                        header = f'''# TTP Template auto-generated from TextFSM
# Original command: {cmd}
# Source: {result.get('source', 'unknown')}
# TextFSM rows: {result.get('textfsm_rows', 'N/A')}
# TTP rows: {result.get('ttp_rows', 'N/A')}
# Match ratio: {result.get('match_ratio', 0):.2f}

'''
                        with open(filepath, 'w') as f:
                            f.write(header + result['ttp_template'])

                        # Export JSON sidecar with parsed results
                        json_filepath = os.path.join(export_dir, f"{safe_cmd}.json")
                        export_json_results(json_filepath, result)

                        exported_count += 1
                    except Exception as e:
                        export_errors += 1
                        if verbose:
                            print(f"  Export error for {result.get('command')}: {e}")

        elif status == 'no_patterns':
            stats['no_patterns'] += 1
        elif status == 'failed_validation':
            stats['failed_validation'] += 1
            if result.get('error'):
                stats['errors'].append((result['id'], result.get('command', '?'), result['error']))

            # Export failed validations for review if export_dir specified
            if export_dir and result.get('ttp_template') and result.get('command'):
                try:
                    failed_dir = os.path.join(export_dir, '_failed_validation')
                    os.makedirs(failed_dir, exist_ok=True)

                    cmd = result['command']
                    safe_cmd = sanitize_filename(cmd)

                    # Export the template
                    filepath = os.path.join(failed_dir, f"{safe_cmd}.ttp")
                    header = f'''# TTP Template - FAILED VALIDATION
# Original command: {cmd}
# Source: {result.get('source', 'unknown')}
# Error: {result.get('error', 'unknown')}

'''
                    with open(filepath, 'w') as f:
                        f.write(header + result['ttp_template'])

                    # Export JSON for review
                    json_filepath = os.path.join(failed_dir, f"{safe_cmd}.json")
                    export_json_results(json_filepath, result)
                except Exception:
                    pass  # Don't fail on export errors
        else:
            # Check if it was a timeout
            error_msg = result.get('error', '')
            if 'Timeout' in error_msg:
                stats['timeouts'] += 1
            else:
                stats['failed_generation'] += 1
            if error_msg:
                stats['errors'].append((result['id'], result.get('command', '?'), error_msg))

        # Verbose output
        if verbose:
            print(f"\n{'=' * 80}")
            print(f"Template ID: {result['id']}")
            print(f"Command: {result.get('command', 'N/A')}")
            print(f"Source: {result.get('source', 'N/A')}")
            print("-" * 40)

            if result.get('ttp_template'):
                print("Generated TTP Template:")
                print(result['ttp_template'])

            if status == 'success':
                print(f"\n✓ Success")
                if result.get('textfsm_rows'):
                    print(f"  TextFSM rows: {result['textfsm_rows']}")
                    print(f"  TTP rows: {result['ttp_rows']}")
                    if result.get('match_ratio') is not None:
                        print(f"  Match ratio: {result['match_ratio']:.2f}")
            elif status == 'no_patterns':
                print(f"NO PATTERNS: {result.get('error', 'Unknown')}")
            else:
                print(f"✗ {status.upper()}: {result.get('error', 'Unknown error')}")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total = stats['success'] + stats['failed_generation'] + stats['failed_validation'] + stats['no_patterns'] + stats[
        'timeouts']
    print(f"Total processed: {total}")
    print(f"  Successful:         {stats['success']}")
    print(f"  Failed generation:  {stats['failed_generation']}")
    print(f"  Failed validation:  {stats['failed_validation']}")
    print(f"  No quality patterns:{stats['no_patterns']}")
    if stats['timeouts'] > 0:
        print(f"  Timeouts:           {stats['timeouts']}")

    if export_dir:
        print(f"\nExported templates: {exported_count}")
        if export_errors > 0:
            print(f"Export errors: {export_errors}")

    if total > 0:
        success_rate = (stats['success'] / total) * 100
        print(f"\nSuccess rate: {success_rate:.1f}%")

    if match_ratios:
        avg_ratio = sum(match_ratios) / len(match_ratios)
        min_r = min(match_ratios)
        max_r = max(match_ratios)
        print(f"TTP/TextFSM row ratio: avg={avg_ratio:.2f}, min={min_r:.2f}, max={max_r:.2f}")

    if stats['errors'] and verbose:
        print(f"\nFirst {min(5, len(stats['errors']))} errors:")
        for id_, cmd, err in stats['errors'][:5]:
            err_short = err[:80] + "..." if len(err) > 80 else err
            print(f"  ID {id_} ({cmd}): {err_short}")

    # Report over-matched templates (potential over-matching issues)
    if over_matched:
        print(f"\n⚠ OVER-MATCHED TEMPLATES ({len(over_matched)} templates where TTP > TextFSM):")
        # Sort by ratio descending
        over_matched.sort(key=lambda x: x['ratio'], reverse=True)
        for item in over_matched[:15]:  # Show top 15
            print(
                f"  {item['command']}: ratio={item['ratio']:.2f} (TextFSM={item['textfsm_rows']}, TTP={item['ttp_rows']})")
        if len(over_matched) > 15:
            print(f"  ... and {len(over_matched) - 15} more")

        # Export over-matched list if export_dir specified
        if export_dir:
            try:
                import json
                overmatched_path = os.path.join(export_dir, '_over_matched.json')
                with open(overmatched_path, 'w') as f:
                    json.dump(over_matched, f, indent=2)
                print(f"  Full list exported to: {overmatched_path}")
            except Exception:
                pass

    # Timing
    elapsed = time.time() - start_time
    print(f"\nElapsed time: {elapsed:.2f}s ({total / elapsed:.1f} templates/sec)" if elapsed > 0 else "")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Entry point for console script."""
    import argparse

    default_workers = max(1, multiprocessing.cpu_count() - 1)

    parser = argparse.ArgumentParser(
        description='Convert TextFSM templates to TTP format using CLI output as reference',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''
Examples:
  python -m tfsm2ttp                        # Run built-in examples
  python -m tfsm2ttp --table                # Run table example only
  python -m tfsm2ttp --paragraph            # Run paragraph examples only
  python -m tfsm2ttp tfsm_template.db       # Test 5 templates from DB
  python -m tfsm2ttp tfsm_template.db -n 20 # Test 20 templates
  python -m tfsm2ttp tfsm_template.db -n 100 -w 8  # Fast batch with 8 workers
  python -m tfsm2ttp tfsm_template.db --no-validate   # Skip TTP validation
  python -m tfsm2ttp tfsm_template.db --min-cols 2    # Lower quality threshold

  # Filter by vendor:
  python -m tfsm2ttp tfsm_template.db -n 50 --vendor cisco
  python -m tfsm2ttp tfsm_template.db -n 100 --vendor cisco arista juniper

  # Export successful templates to directory:
  python -m tfsm2ttp tfsm_template.db -n 1000 -w 8 --export ./ttp_templates

  # Verbose output for debugging:
  python -m tfsm2ttp tfsm_template.db -n 10 -v

  # Adjust timeout and batch size for problematic templates:
  python -m tfsm2ttp tfsm_template.db -n 500 -w 8 --timeout 60 --batch-size 25

Your system has {multiprocessing.cpu_count()} CPU cores available.

Note: The converter tries table parsing first, then falls back to paragraph
parsing for single-record, multi-line data (like "show version").
        '''
    )
    parser.add_argument('database', nargs='?', help='Path to tfsm_template.db')
    parser.add_argument('-n', '--limit', type=int, default=5, help='Number of templates to test (default: 5)')
    parser.add_argument('-w', '--workers', type=int, default=1,
                        help=f'Number of parallel workers (default: 1, max recommended: {default_workers})')
    parser.add_argument('--no-validate', action='store_true', help='Skip TTP validation')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output (show each template details)')
    parser.add_argument('-q', '--quiet', action='store_true', help='Minimal output (summary only, overrides -v)')
    parser.add_argument('--min-cols', type=int, default=3, help='Minimum columns for quality row (default: 3)')
    parser.add_argument('--export', metavar='DIR', help='Export successful TTP templates to directory')
    parser.add_argument('--min-ratio', type=float, default=0.0,
                        help='Minimum TTP/TextFSM row ratio for export (default: 0.0, recommended: 0.5)')
    parser.add_argument('--timeout', type=int, default=30,
                        help='Timeout in seconds per template (default: 30)')
    parser.add_argument('--batch-size', type=int, default=50,
                        help='Process templates in batches of this size (default: 50)')
    parser.add_argument('--vendor', nargs='+', metavar='VENDOR',
                        help='Filter by vendor(s): cisco, arista, juniper, etc. (matches cli_command prefix)')
    parser.add_argument('--table', action='store_true', help='Run table example only')
    parser.add_argument('--paragraph', action='store_true', help='Run paragraph examples only')
    parser.add_argument('--multisection', action='store_true', help='Run multi-section example only')

    args = parser.parse_args()

    # Validate workers
    if args.workers < 1:
        args.workers = 1
    elif args.workers > multiprocessing.cpu_count() * 2:
        print(f"Warning: {args.workers} workers exceeds 2x CPU count, capping at {multiprocessing.cpu_count() * 2}")
        args.workers = multiprocessing.cpu_count() * 2

    # Determine verbosity: quiet overrides verbose
    if args.quiet:
        verbose = False
    else:
        verbose = args.verbose

    if args.database and args.database.endswith('.db'):
        test_from_database(
            args.database,
            limit=args.limit,
            validate=not args.no_validate,
            verbose=verbose,
            workers=args.workers,
            min_cols=args.min_cols,
            export_dir=args.export,
            min_ratio=args.min_ratio,
            vendors=args.vendor,
            timeout=args.timeout,
            batch_size=args.batch_size
        )
    elif args.table:
        run_example()
    elif args.paragraph:
        run_paragraph_example()
        run_ntp_example()
    elif args.multisection:
        run_multisection_example()
    else:
        # Run all examples
        run_example()
        run_paragraph_example()
        run_ntp_example()
        run_multisection_example()


if __name__ == "__main__":
    main()
