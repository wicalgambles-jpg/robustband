# SPDX-License-Identifier: MIT
"""Validated CSV/JSONL conversion with exact roundtrip and explicit provenance."""
from copy import deepcopy
import csv
from hashlib import sha256
import io
import json
from pathlib import Path

from . import __version__
from .decision import _score_groups
from .domains import get_domain
from .input_utils import MAX_BYTES, read_table
from .matrix import load_long

DOMAINS = ('text', 'scores', 'segmentation', 'matrix')


def _load(text, domain, format, mapping, edition):
    if domain not in DOMAINS:
        raise ValueError('Choose a conversion domain: text, scores, segmentation or matrix.')
    if domain == 'matrix':
        get_domain('text', edition)
        if mapping is not None:
            raise ValueError('Column mapping applies to numeric scores only.')
        return load_long(text, format)[2]
    adapter = get_domain(domain, edition)
    if format not in adapter.formats:
        raise ValueError('This domain requires a supported format; segmentation uses JSONL.')
    if domain == 'scores':
        groups = _score_groups(text, format, mapping)
        cohorts = [{r['sample_id']:r['group'] for r in rows} for rows in groups.values()]
        if any(cohort != cohorts[0] for cohort in cohorts):
            raise ValueError('Converted metrics must have the same sample IDs and group labels.')
        return [row for rows in groups.values() for row in rows]
    if mapping is not None:
        raise ValueError('Column mapping applies to numeric scores only.')
    if domain == 'text':
        # Conversion owns the explicit drop policy and records omitted columns.
        from .workflow import load_paired
        return load_paired(text, format, allow_extra=True)
    return adapter.load(text, format)


def convert_table(text, domain='text', format='csv', output_format='jsonl', mapping=None,
                  edition='generalized', allow_extra=False):
    """Preserve every recognized value; reject ambiguous formats and silent drops."""
    if type(allow_extra) is not bool:
        raise ValueError('allow_extra must be an explicit boolean.')
    rows = _load(text, domain, format, mapping, edition)
    if output_format not in ('csv','jsonl') or (domain == 'segmentation' and output_format != 'jsonl'):
        raise ValueError('Choose CSV or JSONL output; segmentation requires JSONL.')
    source = read_table(text, format, exact_decimals=True)
    original_fields = set().union(*(r.keys() for r in source))
    fields = list(rows[0])
    used = set(fields)
    if mapping is not None:
        used = {mapping['sample_id'], mapping['group']} | {m[k] for m in mapping['metrics'] for k in ('score_a','score_b')}
    dropped = sorted(original_fields - used)
    if dropped and mapping is None and not allow_extra:
        raise ValueError('Unrecognized columns would be omitted: '+', '.join(dropped)+'. Explicitly allow extra columns to continue.')
    if output_format == 'csv':
        buffer = io.StringIO(newline='')
        writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
        output = buffer.getvalue()
    else:
        output = ''.join(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n' for row in rows)
    if len(output.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Normalized output exceeds 4 MiB; split the input to keep the result reloadable.')
    if _load(output, domain, output_format, None, edition) != rows:
        raise ValueError('Conversion roundtrip mismatch; no output was committed.')
    root = Path(__file__).parent
    manifest = {'schema':'robustband.conversion/v1','software_version':__version__, 'domain':domain,
        'input_format':format,'output_format':output_format,'mapping':deepcopy(mapping),
        'source_sha256':sha256(text.encode('utf-8')).hexdigest(), 'output_sha256':sha256(output.encode('utf-8')).hexdigest(),
        'n_records':len(rows),'n_samples':len({r['sample_id'] for r in rows}), 'omitted_columns':dropped,
        'roundtrip_verified':True,
        'source_sha256_lf':{name:sha256((root/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
            for name in ('convert.py','decision.py','domains.py','input_utils.py','matrix.py','scores.py','segmentation.py','workflow.py')},
        'scope':'Recognized fields retain their exact values. Units are declared, never inferred or rescaled. Unused columns are listed; the manifest contains hashes, not original records.'}
    return {'text':output,'manifest':manifest}


def save_conversion(result, source, output, overwrite=False):
    """Validate paths before staging; an input file is never an output target."""
    from .storage import write_text_atomic
    output = Path(output)
    manifest = output.with_name(output.name+'.manifest.json')
    if Path(source).resolve() in (output.resolve(), manifest.resolve()):
        raise ValueError('Conversion output cannot overwrite its source file.')
    if not overwrite and any(path.exists() for path in (output,manifest)):
        raise ValueError('Conversion output already exists; choose another path or explicitly use --overwrite.')
    write_text_atomic(manifest, json.dumps(result['manifest'], ensure_ascii=False, indent=2)+'\n')
    write_text_atomic(output, result['text'])
    return output
