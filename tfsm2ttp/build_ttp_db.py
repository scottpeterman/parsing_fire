#!/usr/bin/env python3
"""
Build TTP Templates Database

Reads the JSON sidecar files from textfsm_to_ttp export and creates
a ttp_templates.db SQLite database for use with ttp_fire.py.

Usage:
    python build_ttp_db.py ./ttp_templates
    python build_ttp_db.py ./ttp_templates --output ttp_templates.db
"""

import sqlite3
import json
import os
import sys
import argparse
from pathlib import Path


def create_database(db_path: str) -> sqlite3.Connection:
    """Create the TTP templates database with schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cli_command TEXT UNIQUE NOT NULL,
            ttp_content TEXT NOT NULL,
            cli_content TEXT,
            textfsm_rows INTEGER,
            ttp_rows INTEGER,
            match_ratio REAL,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_cli_command ON templates(cli_command)
    ''')

    conn.commit()
    return conn


def load_json_file(json_path: str) -> dict:
    """Load and parse a JSON sidecar file."""
    with open(json_path, 'r') as f:
        return json.load(f)


def load_ttp_file(ttp_path: str) -> str:
    """Load TTP template content, stripping header comments."""
    with open(ttp_path, 'r') as f:
        content = f.read()

    # Strip header comments (lines starting with #)
    lines = content.splitlines()
    template_lines = []
    in_header = True

    for line in lines:
        if in_header and line.startswith('#'):
            continue
        elif in_header and line.strip() == '':
            continue
        else:
            in_header = False
            template_lines.append(line)

    return '\n'.join(template_lines).strip()


def import_templates(conn: sqlite3.Connection, export_dir: str, verbose: bool = False) -> dict:
    """Import templates from export directory."""
    stats = {
        'imported': 0,
        'skipped': 0,
        'errors': 0,
        'error_list': []
    }

    export_path = Path(export_dir)

    # Find all JSON files (excluding special directories)
    json_files = [f for f in export_path.glob('*.json')
                  if not f.name.startswith('_')]

    if verbose:
        print(f"Found {len(json_files)} JSON files in {export_dir}")

    cursor = conn.cursor()

    for json_file in json_files:
        try:
            # Load JSON data
            data = load_json_file(json_file)
            command = data.get('command')

            if not command:
                stats['skipped'] += 1
                continue

            # Try to load corresponding .ttp file
            ttp_file = json_file.with_suffix('.ttp')
            if ttp_file.exists():
                ttp_content = load_ttp_file(ttp_file)
            else:
                # Fall back to ttp_template in JSON
                ttp_content = data.get('ttp_template', '')

            if not ttp_content:
                stats['skipped'] += 1
                if verbose:
                    print(f"  Skipped {command}: no TTP content")
                continue

            # Insert into database
            cursor.execute('''
                INSERT OR REPLACE INTO templates 
                (cli_command, ttp_content, cli_content, textfsm_rows, ttp_rows, match_ratio, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                command,
                ttp_content,
                data.get('cli_content', ''),
                data.get('textfsm_rows'),
                data.get('ttp_rows'),
                data.get('match_ratio'),
                data.get('source', 'converted')
            ))

            stats['imported'] += 1
            if verbose:
                print(f"  Imported: {command}")

        except Exception as e:
            stats['errors'] += 1
            stats['error_list'].append((json_file.name, str(e)))
            if verbose:
                print(f"  Error {json_file.name}: {e}")

    conn.commit()
    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Build TTP templates database from JSON exports',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    python build_ttp_db.py ./ttp_templates
    python build_ttp_db.py ./ttp_templates --output my_templates.db
    python build_ttp_db.py ./ttp_templates -v
        '''
    )
    parser.add_argument('export_dir', help='Directory containing JSON/TTP exports')
    parser.add_argument('--output', '-o', default='ttp_templates.db',
                        help='Output database path (default: ttp_templates.db)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    if not os.path.isdir(args.export_dir):
        print(f"Error: {args.export_dir} is not a directory")
        sys.exit(1)

    print(f"Building TTP database from: {args.export_dir}")
    print(f"Output: {args.output}")
    print()

    # Create database
    conn = create_database(args.output)

    # Import templates
    stats = import_templates(conn, args.export_dir, args.verbose)

    conn.close()

    # Print summary
    print()
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Templates imported: {stats['imported']}")
    print(f"Templates skipped:  {stats['skipped']}")
    print(f"Errors:             {stats['errors']}")

    if stats['error_list']:
        print(f"\nFirst {min(5, len(stats['error_list']))} errors:")
        for name, err in stats['error_list'][:5]:
            print(f"  {name}: {err[:60]}")

    print(f"\nDatabase created: {args.output}")


if __name__ == '__main__':
    main()