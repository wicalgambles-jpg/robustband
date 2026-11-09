# SPDX-License-Identifier: MIT
"""Shared bounded table ingestion; semantic validation belongs to each adapter."""
import csv
from decimal import Decimal, InvalidOperation
import io
import json

MAX_BYTES = 4 * 1024 * 1024
MAX_ROWS = 5000


def _json_constant(value):
    raise ValueError("Nonstandard JSON numeric constant: " + value)


def _json_object(pairs):
    if len(dict(pairs)) != len(pairs):
        raise ValueError("Duplicate JSON field name.")
    return dict(pairs)


def _json_depth(text):
    """Bound nesting independently of Python's platform-specific JSON decoder."""
    depth, quoted, escaped = 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            if depth > 64:
                raise ValueError('JSON nesting exceeds 64 levels.')
        elif char in ']}':
            depth -= 1


def read_table(text, format, required=(), max_bytes=MAX_BYTES, max_rows=MAX_ROWS, exact_decimals=False):
    """Reject ambiguous headers, duplicate JSON keys and nonstandard numbers."""
    if not isinstance(text, str) or len(text.encode("utf-8")) > max_bytes:
        raise ValueError("Input must be UTF-8 text of at most 4 MiB; split the file or use the Python API for larger inputs.")
    if "\ufffd" in text:
        raise ValueError("Input contains replacement characters (U+FFFD), so it was not valid UTF-8. "
                         "Save the file as UTF-8 and retry.")
    text = text.lstrip("\ufeff")
    rows = []
    if format == "csv":
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        try:
            reader.fieldnames
        except csv.Error as exc:
            raise ValueError('Invalid CSV header near line 1: '+str(exc)) from exc
        if not reader.fieldnames or not set(required) <= set(reader.fieldnames):
            raise ValueError("CSV header needs: " + ", ".join(required))
        if len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("CSV header has duplicate column names.")
        try:
            for number, row in enumerate(reader, 1):
                if None in row or any(v is None for v in row.values()):
                    raise ValueError("CSV record %d has a different number of fields than the header." % number)
                rows.append(row)
                if len(rows) > max_rows:
                    raise ValueError("Use at most %d paired records per audit; split the file or use the Python API."
                                     % max_rows)
        except csv.Error as exc:
            raise ValueError("Invalid CSV near line %d: %s" % (getattr(reader, "line_num", 0), exc)) from exc
    elif format == "jsonl":
        # JSON Lines uses LF/CRLF. U+0085/U+2028/U+2029 are valid string
        # content, so str.splitlines() would split and corrupt valid records.
        for number, line in enumerate(text.split("\n"), 1):
            if line.strip():
                try:
                    _json_depth(line)
                    rows.append(json.loads(line, parse_float=Decimal if exact_decimals else float,
                                           parse_constant=_json_constant, object_pairs_hook=_json_object))
                except (ValueError, RecursionError, InvalidOperation) as exc:
                    raise ValueError("JSONL line %d: %s" % (number, exc)) from exc
                if len(rows) > max_rows:
                    raise ValueError("Use at most %d paired records per audit; split the file or use the Python API."
                                     % max_rows)
    else:
        raise ValueError("Choose input format csv or jsonl.")
    return rows
