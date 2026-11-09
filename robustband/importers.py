# SPDX-License-Identifier: MIT
"""Bounded, in-memory file adapters for archived evaluations.

These adapters inspect data, never execute workbook formulas or upstream code.
Measurement and scoring remain the responsibility of the registered domains.
"""
import csv
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import io
import json
import posixpath
import re
import stat
import xml.etree.ElementTree as ET
import zipfile
import zlib

from .domains import get_domain
from .input_utils import MAX_BYTES, MAX_ROWS, _json_constant, _json_depth, _json_object, read_table
from . import matrix, scores, workflow

MAX_FILE_BYTES = 24 * 1024 * 1024
MAX_TOTAL_BYTES = 48 * 1024 * 1024
MAX_EXPANDED_BYTES = 32 * 1024 * 1024
MAX_MEMBERS = 256
MAX_RAW_ROWS = 20000
MAX_COLUMNS = 256
STRICT_LETTERS = {"parses": ["strict_exact"], "metrics": ["exact_match"], "aggs": ["micro"]}
_MMLU = {"question_id", "question", "options", "answer", "category"}
_MMLU_EXTRA = {"pred", "answer_index", "cot_content", "src", "generated_text", "model_outputs"}
_SINGLE = {"sample_id", "prompt", "gold", "output"}
_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _decode(data):
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Save the input as UTF-8 before importing it.") from exc


def _json(text):
    try:
        _json_depth(text)
        return json.loads(text, parse_float=Decimal, parse_constant=_json_constant, object_pairs_hook=_json_object)
    except (ValueError, RecursionError, InvalidOperation) as exc:
        raise ValueError("Invalid JSON: " + str(exc)) from exc


def _records(value):
    if isinstance(value, dict):
        if "records" in value:
            if set(value) != {"records"} or not isinstance(value["records"], list):
                raise ValueError("A records wrapper must contain only a records array; remove ambiguous metadata.")
            value = value["records"]
        else:
            value = [value]
    if not isinstance(value, list) or not value or any(not isinstance(row, dict) for row in value):
        raise ValueError("Import a nonempty record, record array or records wrapper.")
    if len(value) > MAX_RAW_ROWS:
        raise ValueError("Use at most %d raw records per source." % MAX_RAW_ROWS)
    return value


def _table(text, delimiter):
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
        fields = reader.fieldnames
        if not fields or any(not field for field in fields) or len(set(fields)) != len(fields):
            raise ValueError("Table headers must be distinct, nonempty column names.")
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Table rows must have the same number of fields as the header.")
            rows.append(row)
            if len(rows) > MAX_RAW_ROWS:
                raise ValueError("Use at most %d raw records per source." % MAX_RAW_ROWS)
    except csv.Error as exc:
        raise ValueError("Invalid delimited table: " + str(exc)) from exc
    return _records(rows)


def _safe_path(name):
    if (not name or "\\" in name or name.startswith("/") or re.match(r"^[A-Za-z]:", name)
            or ".." in name.split("/")):
        raise ValueError("Archive members must not use absolute or parent-traversal paths.")
    return name


def _archive(data):
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("The file is not a readable ZIP archive.") from exc
    try:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS or sum(member.file_size for member in members) > MAX_EXPANDED_BYTES:
            raise ValueError("An archive may contain at most 256 members and 32 MiB of expanded data.")
        names = set()
        for member in members:
            _safe_path(member.filename)
            if member.filename in names or member.flag_bits & 1 or stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError("Duplicate, encrypted or symbolic-link archive members are not supported.")
            names.add(member.filename)
    except ValueError:
        archive.close()
        raise
    return archive


def _member(archive, name):
    try:
        return archive.read(name)
    except (KeyError, zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, EOFError, zlib.error) as exc:
        raise ValueError("Cannot read archive member: " + name) from exc


def _xml(archive, name):
    data = _member(archive, name)
    markup = data.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in markup or b"<!ENTITY" in markup:
        raise ValueError("Workbook XML must not contain DTD or ENTITY declarations.")
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("Invalid workbook XML: " + name) from exc


def _rich_text(node):
    # rPh contains pronunciation hints, not the string's value (OOXML 18.4.6).
    # Read only direct text and ordinary rich-text runs in their original order.
    parts = []
    if node is not None:
        for child in node:
            if child.tag == _MAIN + "t":
                parts.append(child.text or "")
            elif child.tag == _MAIN + "r":
                parts.extend(item.text or "" for item in child.findall(_MAIN + "t"))
    return "".join(parts)


def _xlsx(data):
    with _archive(data) as archive:
        workbook = _xml(archive, "xl/workbook.xml")
        rels = _xml(archive, "xl/_rels/workbook.xml.rels")
        relationships = {}
        for relationship in rels:
            identity, target = relationship.get("Id"), relationship.get("Target", "")
            if identity in relationships or relationship.get("TargetMode") == "External":
                raise ValueError("Workbook relationships must be distinct internal references.")
            _safe_path(target.lstrip("/"))
            relationships[identity] = target.lstrip("/") if target.startswith("/") else posixpath.join("xl", target)
        sheets = workbook.findall(_MAIN + "sheets/" + _MAIN + "sheet")
        if not sheets or sheets[0].get(_REL) not in relationships:
            raise ValueError("The workbook must contain a readable first worksheet.")
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = [_rich_text(item) for item in _xml(archive, "xl/sharedStrings.xml").findall(_MAIN + "si")]
        sheet = _xml(archive, relationships[sheets[0].get(_REL)])
        grid = []
        for row in sheet.findall(_MAIN + "sheetData/" + _MAIN + "row"):
            cells, previous = {}, -1
            for cell in row.findall(_MAIN + "c"):
                if cell.find(_MAIN + "f") is not None:
                    raise ValueError("Workbook formulas are not imported. Paste values into a new sheet first.")
                reference = cell.get("r")
                column = previous + 1
                if reference is not None:
                    match = re.fullmatch(r"([A-Z]{1,3})[1-9][0-9]*", reference)
                    if not match:
                        raise ValueError("Invalid worksheet cell reference.")
                    column = 0
                    for char in match[1]:
                        column = column * 26 + ord(char) - 64
                    column -= 1
                if column >= MAX_COLUMNS or column in cells:
                    raise ValueError("Use at most 256 distinct columns per worksheet row.")
                previous = column
                kind = cell.get("t", "n")
                value = cell.findtext(_MAIN + "v", "")
                if kind == "s":
                    if not value.isdigit() or int(value) >= len(shared):
                        raise ValueError("Invalid workbook shared-string reference.")
                    value = shared[int(value)]
                elif kind == "inlineStr":
                    value = _rich_text(cell.find(_MAIN + "is"))
                elif kind not in ("n", "str", "b", "d"):
                    raise ValueError("Unsupported or error-valued workbook cell; paste plain values first.")
                cells[column] = value
            if cells and any(cells.values()):
                grid.append([cells.get(index, "") for index in range(max(cells) + 1)])
                if len(grid) > MAX_RAW_ROWS + 1:
                    raise ValueError("Use at most %d raw records per source." % MAX_RAW_ROWS)
        if not grid or any(not field for field in grid[0]) or len(set(grid[0])) != len(grid[0]):
            raise ValueError("The first worksheet needs distinct nonempty headers and data rows.")
        header = grid[0]
        rows = []
        for row in grid[1:]:
            if len(row) > len(header):
                raise ValueError("Worksheet data extends beyond its declared headers.")
            rows.append(dict(zip(header, row + [""] * (len(header) - len(row)))))
    return _records(rows), {"worksheet": sheets[0].get("name", "Sheet 1"),
                            "omitted_worksheets": [sheet.get("name", "") for sheet in sheets[1:]]}


def _kind(rows):
    fields = set(rows[0])
    if _MMLU <= fields:
        return "mmlu_pro"
    if set(matrix.REQUIRED) <= fields:
        return "matrix"
    if _SINGLE <= fields:
        return "single_model"
    if set(workflow.REQUIRED) <= fields:
        return "text"
    if set(scores.REQUIRED) <= fields:
        return "scores"
    if {"sample_id", "confusion_a", "confusion_b"} <= fields:
        return "segmentation"
    return None


def _load(file):
    name, data = file["name"], file["data"]
    suffix = name.rsplit(".", 1)[-1].lower()
    details = {}
    if suffix == "xlsx":
        rows, details = _xlsx(data)
    elif suffix == "zip":
        with _archive(data) as archive:
            members = [member for member in archive.infolist() if not member.is_dir()]
            if len(members) != 1 or not members[0].filename.lower().endswith(".json"):
                raise ValueError("ZIP imports require one MMLU-Pro JSON array and no other files.")
            value = _json(_decode(_member(archive, members[0].filename)))
            if not isinstance(value, list):
                raise ValueError("An MMLU-Pro ZIP member must be a JSON record array.")
            rows = _records(value)
            details["archive_member"] = members[0].filename
        if _kind(rows) != "mmlu_pro":
            raise ValueError("ZIP imports require the MMLU-Pro question/options/answer/pred schema.")
    elif suffix == "json":
        rows = _records(_json(_decode(data)))
    elif suffix in ("jsonl", "ndjson"):
        rows = _records(read_table(_decode(data), "jsonl", max_bytes=MAX_FILE_BYTES, max_rows=MAX_RAW_ROWS, exact_decimals=True))
    elif suffix in ("csv", "tsv"):
        rows = _table(_decode(data), "\t" if suffix == "tsv" else ",")
    else:
        raise ValueError("Choose CSV, TSV, JSON, JSONL, NDJSON, XLSX or an MMLU-Pro ZIP.")
    decoded = []
    if _kind(rows) == "segmentation":
        for row in rows:
            for column in ("confusion_a", "confusion_b"):
                if isinstance(row.get(column), str):
                    row[column] = _json(row[column])
                    if column not in decoded:
                        decoded.append(column)
        details["decoded_json_fields"] = decoded
    details.update(name=name, sha256=sha256(data).hexdigest(), bytes=len(data), source_format=suffix,
                   raw_records=len(rows), fields=sorted(set().union(*(row.keys() for row in rows))), omitted_fields=[])
    details["mapping"] = {field:field for field in details["fields"]}
    return rows, details


def _encode(value):
    # Decimal values remain JSON numbers, including in metadata, so the domain
    # validators can reject numeric labels rather than silently making strings.
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(key, ensure_ascii=False) + ":" + _encode(item) for key, item in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _jsonl(rows):
    if len(rows) > MAX_ROWS:
        raise ValueError("Use at most %d normalized audit rows; select a smaller complete category." % MAX_ROWS)
    text = "".join(_encode(row) + "\n" for row in rows)
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Normalized audit input exceeds 4 MiB; split the source or choose a smaller category.")
    return text


def _model(name):
    value = name.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if value.lower().endswith(".json"):
        value = value[:-5]
    value = re.sub(r"^model_outputs_", "", value)
    value = re.sub(r"_\d+[-_]?shots?$", "", value)
    if not value.strip():
        raise ValueError("Use a nonempty model filename.")
    return value


def _identity(value):
    if type(value) not in (str, int) or not str(value).strip():
        raise ValueError("Sample IDs must be nonempty strings or integers.")
    return str(value)


def _mmlu_rows(rows):
    result = {}
    for row in rows:
        if not _MMLU <= row.keys() or set(row) - _MMLU - _MMLU_EXTRA:
            raise ValueError("MMLU-Pro records need consistent question fields and no unrecognized extra columns.")
        identity = _identity(row["question_id"])
        if identity in result:
            raise ValueError("Duplicate MMLU-Pro question_id: " + identity)
        question, category, options, answer = (row[key] for key in ("question", "category", "options", "answer"))
        if isinstance(options, str):
            options = _json(options)
        if (not isinstance(question, str) or not question.strip() or not isinstance(category, str) or not category.strip()
                or not isinstance(options, list) or not 1 <= len(options) <= 16
                or any(not isinstance(option, str) or not option.strip() for option in options)
                or not isinstance(answer, str) or len(answer) != 1 or answer not in "ABCDEFGHIJKLMNOP"[:len(options)]):
            raise ValueError("MMLU-Pro needs a question, category, 1–16 text options and one valid uppercase answer letter.")
        if "answer_index" in row:
            index = row["answer_index"]
            if isinstance(index, str) and index.isascii() and index.isdigit():
                index = int(index)
            if type(index) is not int or index != ord(answer) - ord("A"):
                raise ValueError("MMLU-Pro answer_index disagrees with its answer letter.")
        pred = row.get("pred")
        valid = isinstance(pred, str) and len(pred) == 1 and pred in "ABCDEFGHIJKLMNOP"[:len(options)]
        result[identity] = dict(question=question, options=options, answer=answer, category=category,
                                output=pred if valid else "", missing=pred is None or pred == "", invalid=not valid)
    return result


def _pair_mmlu(tables, category, sources, manifest):
    indexes = [_mmlu_rows(rows) for rows in tables]
    common = sorted(set(row["category"] for row in indexes[0].values()) & set(row["category"] for row in indexes[1].values()))
    if not common:
        raise ValueError("The two MMLU-Pro files have no common category.")
    selected = category if category is not None else "computer science" if "computer science" in common else common[0]
    if selected not in common:
        raise ValueError("Choose a category present in both files: " + ", ".join(common))
    indexes = [{identity:row for identity, row in index.items() if row["category"] == selected} for index in indexes]
    if set(indexes[0]) != set(indexes[1]):
        raise ValueError("Selected category sample IDs differ; no implicit inner join is performed.")
    rows = []
    for identity, a in indexes[0].items():
        b = indexes[1][identity]
        if any(a[key] != b[key] for key in ("question", "options", "answer")):
            raise ValueError("The same MMLU-Pro ID has different question/options/gold: " + identity)
        prompt = a["question"] + "\n" + "\n".join(chr(65 + index) + ". " + option for index, option in enumerate(a["options"]))
        rows.append(dict(sample_id=identity, prompt=prompt, gold=a["answer"], output_a=a["output"], output_b=b["output"], **{"class": selected}))
    for side, (source, index) in enumerate(zip(sources, indexes)):
        source["omitted_fields"] = sorted(set(source["fields"]) - _MMLU - {"pred"})
        source["selected_records"] = len(index)
        source["missing_predictions"] = sum(row["missing"] for row in index.values())
        source["invalid_predictions"] = sum(row["invalid"] and not row["missing"] for row in index.values())
        source["single_option_records"] = sum(len(row["options"]) == 1 for row in index.values())
        source["mapping"] = {"sample_id": "question_id", "prompt": ["question", "options"], "gold": "answer", "output_a" if side == 0 else "output_b": "pred", "class": "category"}
        if source["missing_predictions"] or source["invalid_predictions"]:
            manifest["warnings"].append(source["name"] + ": missing or invalid predictions remain as empty, incorrect outputs.")
        if source["single_option_records"]:
            manifest["warnings"].append(source["name"] + ": the selected category includes archived questions with only one option; they remain in the audit.")
    manifest["missing_prediction_policy"] = "Keep every selected question. Missing/invalid pred becomes empty output and scores 0; no random guessing or re-extraction."
    manifest["pairing"] = {"same_ids": True, "same_context": True, "context_fields": ["question", "options", "answer"], "inner_join": False, "n_items": len(rows)}
    return rows, common, selected


def _pair_text(tables, manifest):
    indexes = []
    for table in tables:
        paired = []
        for row in table:
            if not _SINGLE <= row.keys() or set(row) - _SINGLE - set(workflow.GROUPS.values()):
                raise ValueError("Single-model tables need sample_id,prompt,gold,output and only optional class/len_bucket.")
            paired.append({**{key:value for key, value in row.items() if key != "output"}, "output_a": row["output"], "output_b": ""})
        normalized = workflow.load_paired(_jsonl(paired), "jsonl")
        indexes.append({row["sample_id"]:row for row in normalized})
    if set(indexes[0]) != set(indexes[1]):
        raise ValueError("Single-model sample IDs differ; no implicit inner join is performed.")
    rows = []
    for identity, a in indexes[0].items():
        b = indexes[1][identity]
        if any(a[key] != b[key] for key in ("prompt", "gold", "class", "len_bucket")):
            raise ValueError("The same sample ID has different prompt/gold/group context: " + identity)
        rows.append({**a, "output_b": b["output_a"]})
    manifest["pairing"] = {"same_ids": True, "same_context": True, "inner_join": False, "n_items": len(rows)}
    return rows


def import_files(files, category=None, edition="generalized", preferred_domain="text"):
    """Inspect one paired table or strictly pair two archived model result files.

    Return canonical JSONL plus explicit policies/provenance, without reports or
    disk writes. The first input is A and the second input is B, without sorting.
    """
    if not isinstance(files, (list, tuple)) or not 1 <= len(files) <= 2:
        raise ValueError("Import one paired table or two single-model files.")
    total = 0
    for file in files:
        if (not isinstance(file, dict) or set(file) != {"name", "data"} or not isinstance(file["name"], str)
                or not file["name"].strip() or len(file["name"]) > 512 or type(file["data"]) is not bytes):
            raise ValueError("Each file needs a nonempty name and original bytes.")
        if len(file["data"]) > MAX_FILE_BYTES:
            raise ValueError("Each source must be at most 24 MiB.")
        total += len(file["data"])
    if total > MAX_TOTAL_BYTES:
        raise ValueError("Combined source files must be at most 48 MiB.")
    if category is not None and (not isinstance(category, str) or not category.strip()):
        raise ValueError("Category must be a nonempty category label.")
    # Validate edition and explicit extension selection before parsing large files.
    get_domain(preferred_domain, edition)
    parsed = [_load(file) for file in files]
    tables, sources = [part[0] for part in parsed], [part[1] for part in parsed]
    manifest = {"schema": "robustband.file_import/v1", "sources": sources, "warnings": [],
                "input_order": "First source is A; second source is B.", "missing_prediction_policy": None,
                "pairing": None}
    for source in sources:
        if source.get("omitted_worksheets"):
            manifest["warnings"].append(source["name"] + ": only the first worksheet is imported; other sheets are listed in the manifest.")
    kinds = [_kind(table) for table in tables]
    categories, selected, family, model_a, model_b = [], None, None, "A", "B"
    if len(files) == 2:
        model_a, model_b = (_model(file["name"]) for file in files)
        if model_a == model_b:
            raise ValueError("The two source files must identify distinct model names.")
        if kinds[0] != kinds[1] or kinds[0] not in ("mmlu_pro", "single_model"):
            raise ValueError("Two-file imports require matching MMLU-Pro archives or matching single-model tables.")
        if kinds[0] == "mmlu_pro":
            rows, categories, selected = _pair_mmlu(tables, category, sources, manifest)
            family = {key:list(value) for key, value in STRICT_LETTERS.items()}
        else:
            if category is not None:
                raise ValueError("Category selection applies only to MMLU-Pro archives.")
            rows = _pair_text(tables, manifest)
            for side, source in enumerate(sources):
                source["mapping"].pop("output")
                source["mapping"]["output_a" if side == 0 else "output_b"] = "output"
        mode = "text"
    else:
        if category is not None:
            raise ValueError("Category selection requires two MMLU-Pro archives.")
        if kinds[0] in ("mmlu_pro", "single_model"):
            raise ValueError("Add a second model file to compare these single-model results.")
        mode = preferred_domain if preferred_domain not in ("text", "scores", "segmentation") else kinds[0] or preferred_domain
        rows = tables[0]
    text = _jsonl(rows)
    if mode == "matrix":
        get_domain("text", edition)
        models = matrix.load_long(text, "jsonl")[0]
        model_a, model_b = models[:2]
    else:
        adapter = get_domain(mode, edition)
        if "jsonl" not in adapter.formats:
            raise ValueError("This adapter must support JSONL to import these file formats.")
        adapter.load(text, "jsonl")
    manifest["normalized_sha256"] = sha256(text.encode("utf-8")).hexdigest()
    manifest["normalized_records"] = len(rows)
    manifest.update(mode=mode, family=family, model_a=model_a, model_b=model_b, selected_category=selected)
    return {"mode": mode, "text": text, "format": "jsonl", "family": family,
            "model_a": model_a, "model_b": model_b, "categories": categories,
            "selected_category": selected, "manifest": manifest}
