#!/usr/bin/env python3
"""
TTP Auto-Match Engine (ttp_fire.py)

Automatically finds the best TTP template for unknown CLI output.
TTP equivalent of tfsm_fire.py.

Usage:
    # Find best template for CLI output
    engine = TTPAutoEngine("ttp_templates.db")
    template, parsed, score, all_scores = engine.find_best_template(cli_output, "show version")

    # CLI usage
    python ttp_fire.py ttp_templates.db "show interfaces" < cli_output.txt
    python ttp_fire.py ttp_templates.db --filter "cisco_ios" < cli_output.txt
"""

import sqlite3
from typing import Dict, List, Tuple, Optional
import time
import click
import threading
from contextlib import contextmanager
import warnings


class ThreadSafeConnection:
    """Thread-local storage for SQLite connections"""

    def __init__(self, db_path: str, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self._local = threading.local()

    @contextmanager
    def get_connection(self):
        """Get a thread-local connection"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(self.db_path)
            self._local.connection.row_factory = sqlite3.Row
            if self.verbose:
                click.echo(f"Created new connection in thread {threading.get_ident()}")

        try:
            yield self._local.connection
        except Exception as e:
            if hasattr(self._local, 'connection'):
                self._local.connection.close()
                delattr(self._local, 'connection')
            raise e

    def close_all(self):
        """Close connection if it exists for current thread"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            delattr(self._local, 'connection')


class TTPAutoEngine:
    """
    Automatic TTP template matching engine.

    Tries multiple TTP templates against CLI output and scores
    each match to find the best template.
    """

    def __init__(self, db_path: str, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self.connection_manager = ThreadSafeConnection(db_path, verbose)
        self._ttp = None  # Lazy load

    def _get_ttp(self):
        """Lazy load TTP module."""
        if self._ttp is None:
            from ttp import ttp
            self._ttp = ttp
        return self._ttp

    def _parse_with_ttp(self, template_content: str, cli_content: str) -> List[Dict]:
        """Parse CLI output with TTP template, return list of dicts."""
        ttp_class = self._get_ttp()

        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=SyntaxWarning)
            parser = ttp_class(data=cli_content, template=template_content)
            parser.parse()
            results = parser.result()

        # Flatten TTP results into list of dicts
        parsed_dicts = []

        def extract_records(obj):
            """Recursively extract records from TTP nested structure."""
            if isinstance(obj, dict):
                # Check if this dict has actual data (non-nested values)
                has_data = any(
                    not isinstance(v, (list, dict))
                    for v in obj.values()
                )
                if has_data:
                    # Filter out nested structures for the record
                    record = {k: v for k, v in obj.items()
                              if not isinstance(v, (list, dict))}
                    if record:
                        parsed_dicts.append(record)

                # Recurse into nested structures
                for v in obj.values():
                    extract_records(v)

            elif isinstance(obj, list):
                for item in obj:
                    extract_records(item)

        if results and len(results) > 0:
            extract_records(results[0])

        return parsed_dicts

    def _calculate_template_score(
            self,
            parsed_data: List[Dict],
            template: sqlite3.Row,
            raw_output: str
    ) -> float:
        """
        Score template match quality (0-100 scale).

        Factors:
        - Record count (0-30 pts): Did the template find data?
        - Field richness (0-30 pts): How many fields per record?
        - Population rate (0-25 pts): Are fields actually filled?
        - Consistency (0-15 pts): Uniform data across records?
        """
        if not parsed_data:
            return 0.0

        num_records = len(parsed_data)
        num_fields = len(parsed_data[0].keys()) if parsed_data else 0
        is_version_cmd = 'version' in template['cli_command'].lower()

        # === Factor 1: Record Count (0-30 points) ===
        if is_version_cmd:
            # Version commands: expect exactly 1 record
            record_score = 30.0 if num_records == 1 else max(0, 15 - (num_records - 1) * 5)
        else:
            # Diminishing returns: log scale capped at 30
            # 1 rec = 10, 3 rec = 20, 10+ rec = 30
            if num_records >= 10:
                record_score = 30.0
            elif num_records >= 3:
                record_score = 20.0 + (num_records - 3) * (10.0 / 7.0)
            else:
                record_score = num_records * 10.0

        # === Factor 2: Field Richness (0-30 points) ===
        # More fields = richer data extraction
        # 1-2 fields = weak, 3-5 = decent, 6-10 = good, 10+ = excellent
        if num_fields >= 10:
            field_score = 30.0
        elif num_fields >= 6:
            field_score = 20.0 + (num_fields - 6) * 2.5
        elif num_fields >= 3:
            field_score = 10.0 + (num_fields - 3) * (10.0 / 3.0)
        else:
            field_score = num_fields * 5.0

        # === Factor 3: Population Rate (0-25 points) ===
        # What percentage of cells have actual data?
        total_cells = num_records * num_fields
        populated_cells = 0

        for record in parsed_data:
            for value in record.values():
                if value is not None and str(value).strip():
                    populated_cells += 1

        population_rate = populated_cells / total_cells if total_cells > 0 else 0
        population_score = population_rate * 25.0

        # === Factor 4: Consistency (0-15 points) ===
        # Are the same fields populated across all records?
        if num_records > 1:
            # Check which fields are populated in each record
            field_fill_counts = {key: 0 for key in parsed_data[0].keys()}

            for record in parsed_data:
                for key, value in record.items():
                    if key in field_fill_counts and value is not None and str(value).strip():
                        field_fill_counts[key] += 1

            # Consistency = fields that are either always filled or never filled
            consistent_fields = sum(
                1 for count in field_fill_counts.values()
                if count == 0 or count == num_records
            )
            consistency_rate = consistent_fields / num_fields if num_fields > 0 else 0
            consistency_score = consistency_rate * 15.0
        else:
            # Single record = perfectly consistent
            consistency_score = 15.0

        total_score = record_score + field_score + population_score + consistency_score

        if self.verbose:
            click.echo(f"    Scoring: records={record_score:.1f}, fields={field_score:.1f}, "
                       f"population={population_score:.1f}, consistency={consistency_score:.1f} "
                       f"-> {total_score:.1f}")

        return total_score

    def find_best_template(
            self,
            device_output: str,
            filter_string: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[List[Dict]], float, List[Tuple[str, float, int]]]:
        """
        Try filtered templates against the output and return the best match.

        Args:
            device_output: Raw CLI output to parse
            filter_string: Optional filter (e.g., "cisco_ios", "show version")

        Returns:
            Tuple of (best_template_name, parsed_data, score, all_scores)
            all_scores is List of (template_name, score, record_count)
        """
        best_template = None
        best_parsed_output = None
        best_score = 0
        all_scores = []

        with self.connection_manager.get_connection() as conn:
            templates = self._get_filtered_templates(conn, filter_string)
            total_templates = len(templates)

            if self.verbose:
                click.echo(f"Found {total_templates} matching templates for filter: {filter_string}")

            for idx, template in enumerate(templates, 1):
                if self.verbose:
                    percentage = (idx / total_templates) * 100
                    click.echo(f"\nTemplate {idx}/{total_templates} ({percentage:.1f}%): {template['cli_command']}")

                try:
                    parsed_dicts = self._parse_with_ttp(
                        template['ttp_content'],
                        device_output
                    )
                    score = self._calculate_template_score(parsed_dicts, template, device_output)

                    if self.verbose:
                        click.echo(f" -> Score={score:.2f}, Records={len(parsed_dicts)}")

                    # Track all non-zero scores
                    if score > 0:
                        all_scores.append((template['cli_command'], score, len(parsed_dicts)))

                    if score > best_score:
                        best_score = score
                        best_template = template['cli_command']
                        best_parsed_output = parsed_dicts
                        if self.verbose:
                            click.echo(click.style("  New best match!", fg='green'))

                except Exception as e:
                    if self.verbose:
                        click.echo(f" -> Failed to parse: {str(e)[:80]}")
                    continue

        # Sort all_scores by score descending
        all_scores.sort(key=lambda x: x[1], reverse=True)

        return best_template, best_parsed_output, best_score, all_scores

    def _get_filtered_templates(
            self,
            connection: sqlite3.Connection,
            filter_string: Optional[str] = None
    ) -> List[sqlite3.Row]:
        """Get filtered templates from database."""
        cursor = connection.cursor()

        if filter_string:
            # Split on _ or - and require all terms to match
            filter_terms = filter_string.replace('-', '_').split('_')
            query = "SELECT * FROM templates WHERE 1=1"
            params = []

            for term in filter_terms:
                if term and len(term) > 2:
                    query += " AND cli_command LIKE ?"
                    params.append(f"%{term}%")

            cursor.execute(query, params)
        else:
            cursor.execute("SELECT * FROM templates")

        return cursor.fetchall()

    def get_template(self, command: str) -> Optional[str]:
        """Get a specific template by command name."""
        with self.connection_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ttp_content FROM templates WHERE cli_command = ?",
                (command,)
            )
            row = cursor.fetchone()
            return row['ttp_content'] if row else None

    def list_templates(self, filter_string: Optional[str] = None) -> List[str]:
        """List available template names."""
        with self.connection_manager.get_connection() as conn:
            templates = self._get_filtered_templates(conn, filter_string)
            return [t['cli_command'] for t in templates]

    def parse(self, device_output: str, command: str) -> List[Dict]:
        """Parse output using a specific template by name."""
        template_content = self.get_template(command)
        if not template_content:
            raise ValueError(f"Template not found: {command}")
        return self._parse_with_ttp(template_content, device_output)

    def __del__(self):
        """Clean up connections on deletion"""
        self.connection_manager.close_all()


# =============================================================================
# CLI Interface
# =============================================================================

@click.command()
@click.argument('database', type=click.Path(exists=True))
@click.argument('filter', required=False)
@click.option('--input', '-i', type=click.File('r'), default='-',
              help='Input file (default: stdin)')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--list', '-l', 'list_templates', is_flag=True,
              help='List available templates')
@click.option('--top', '-t', type=int, default=5,
              help='Show top N matches (default: 5)')
@click.option('--json', '-j', 'output_json', is_flag=True,
              help='Output results as JSON')
def main(database, filter, input, verbose, list_templates, top, output_json):
    """
    TTP Auto-Match Engine - Find the best TTP template for CLI output.

    DATABASE: Path to ttp_templates.db
    FILTER: Optional filter string (e.g., "cisco_ios", "show_version")

    Examples:

        # Find best template for piped input
        cat output.txt | python ttp_fire.py ttp_templates.db "show version"

        # Find best template with verbose scoring
        python ttp_fire.py ttp_templates.db "cisco" -v < output.txt

        # List available templates
        python ttp_fire.py ttp_templates.db --list
        python ttp_fire.py ttp_templates.db --list "cisco_ios"
    """
    engine = TTPAutoEngine(database, verbose=verbose)

    if list_templates:
        templates = engine.list_templates(filter)
        click.echo(f"Found {len(templates)} templates:")
        for t in templates:
            click.echo(f"  {t}")
        return

    # Read input
    cli_output = input.read()

    if not cli_output.strip():
        click.echo("Error: No input provided", err=True)
        raise SystemExit(1)

    # Find best template
    start_time = time.time()
    best_template, parsed_data, score, all_scores = engine.find_best_template(
        cli_output, filter
    )
    elapsed = time.time() - start_time

    if output_json:
        import json
        result = {
            'best_template': best_template,
            'score': score,
            'records': len(parsed_data) if parsed_data else 0,
            'parsed_data': parsed_data,
            'top_matches': [
                {'template': t, 'score': s, 'records': r}
                for t, s, r in all_scores[:top]
            ],
            'elapsed_seconds': elapsed
        }
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo()
        click.echo("=" * 60)
        click.echo("RESULTS")
        click.echo("=" * 60)

        if best_template:
            click.echo(f"Best template: {click.style(best_template, fg='green', bold=True)}")
            click.echo(f"Score: {score:.2f}")
            click.echo(f"Records parsed: {len(parsed_data) if parsed_data else 0}")
        else:
            click.echo(click.style("No matching template found", fg='red'))

        if all_scores and top > 1:
            click.echo(f"\nTop {min(top, len(all_scores))} matches:")
            for i, (template, score, records) in enumerate(all_scores[:top], 1):
                marker = " <--" if template == best_template else ""
                click.echo(f"  {i}. {template}: score={score:.2f}, records={records}{marker}")

        click.echo(f"\nElapsed: {elapsed:.2f}s")

        if parsed_data and verbose:
            click.echo("\nParsed data (first 3 records):")
            for i, record in enumerate(parsed_data[:3], 1):
                click.echo(f"  Record {i}: {record}")


if __name__ == '__main__':
    main()