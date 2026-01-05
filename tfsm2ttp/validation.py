"""
Validation and Comparison

Validates generated TTP templates by parsing CLI content and comparing
results against TextFSM output.
"""

from typing import List, Dict, Tuple


def validate_ttp_template(ttp_template: str, cli_content: str, timeout: int = 10) -> Tuple[bool, List[Dict], str]:
    """Validate with timeout protection."""
    try:
        from ttp import ttp
    except ImportError:
        return False, [], "TTP library not installed"

    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError("TTP parsing timed out")

    try:
        import warnings
        # Set alarm (Unix only)
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)

        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=SyntaxWarning)
            parser = ttp(data=cli_content, template=ttp_template)
            parser.parse()
            results = parser.result()

        signal.alarm(0)  # Cancel alarm
        signal.signal(signal.SIGALRM, old_handler)

        if results and len(results) > 0:
            return True, results[0], ""
        return True, [], "No results parsed"
    except TimeoutError:
        return False, [], "TTP parsing timed out"
    except Exception as e:
        signal.alarm(0)
        return False, [], f"TTP parse error: {str(e)[:100]}"

def compare_results(textfsm_rows: List[Dict], ttp_results: List) -> Dict:
    """Compare TextFSM and TTP parsing results."""
    comparison = {
        'textfsm_count': len(textfsm_rows),
        'ttp_count': 0,
        'match_rate': 0.0,
        'details': []
    }

    def count_records(obj):
        """Recursively count actual data records in TTP output."""
        count = 0
        if isinstance(obj, dict):
            has_data = any(k for k in obj.keys() if not k.startswith('_') and not isinstance(obj[k], (list, dict)))
            if has_data:
                count += 1
            for v in obj.values():
                count += count_records(v)
        elif isinstance(obj, list):
            for item in obj:
                count += count_records(item)
        return count

    comparison['ttp_count'] = count_records(ttp_results)

    if comparison['textfsm_count'] > 0:
        comparison['match_rate'] = comparison['ttp_count'] / comparison['textfsm_count']

    return comparison
