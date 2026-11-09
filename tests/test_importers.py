# SPDX-License-Identifier: MIT
"""File imports preserve exact measurements, pairing, provenance and bounded parsing."""
from copy import deepcopy
import csv
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import io
import json
import stat
import struct
import zipfile
from xml.sax.saxutils import escape

import pytest

from robustband import importers as imp, domains, workflow, matrix, segmentation


def record(**changes):
    return {**dict(sample_id="s1", prompt="What is six times seven?", gold="42", output_a="42", output_b="7"), **changes}


def file(name, value):
    return {"name": name, "data": value if isinstance(value, bytes) else json.dumps(value).encode("utf-8")}


def table_bytes(rows, delimiter=","):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter=delimiter, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def zipped(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, value in entries:
            archive.writestr(name, value)
    return stream.getvalue()


def mmlu(identity=1, **changes):
    return {**dict(question_id=identity, question="Which letter is requested?", options=["First", "Second"],
                answer="A", answer_index=0, pred="A", category="computer science", generated_text="Archived response."), **changes}


def xlsx(rows, extras=(), shared=None, sheet_xml=None, workbook=None, rels=None):
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    sheet_rows = []
    for row_number, values in enumerate(rows, 1):
        cells = []
        for column, value in enumerate(values):
            reference = chr(65 + column) + str(row_number)
            if isinstance(value, tuple):
                kind, value = value
                cells.append('<c r="%s" t="%s"><v>%s</v></c>' % (reference, kind, escape(str(value))))
            else:
                cells.append('<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' % (reference, escape(str(value))))
        sheet_rows.append('<row r="%d">%s</row>' % (row_number, "".join(cells)))
    sheet_xml = sheet_xml if sheet_xml is not None else '<worksheet %s><sheetData>%s</sheetData></worksheet>' % (ns, "".join(sheet_rows))
    workbook = workbook if workbook is not None else ('<workbook %s xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Results" sheetId="1" r:id="rId1"/><sheet name="Notes" sheetId="2" r:id="rId2"/></sheets></workbook>' % ns)
    rels = rels if rels is not None else ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>')
    entries = [("xl/workbook.xml", workbook), ("xl/_rels/workbook.xml.rels", rels), ("xl/worksheets/sheet1.xml", sheet_xml)]
    if shared is not None:
        entries.append(("xl/sharedStrings.xml", '<sst %s>%s</sst>' % (ns, "".join('<si><t>%s</t></si>' % escape(v) for v in shared))))
    return zipped(entries + list(extras))


def assert_text_margin(result, expected="1"):
    assert result["mode"] == "text" and result["format"] == "jsonl"
    report = domains.audit_domain("text", result["text"], "jsonl", result["family"])
    assert report["result"]["exact_band"] == [expected, expected]
    assert domains.verify_audit(report)


@pytest.mark.parametrize("suffix", ["csv", "tsv", "json", "jsonl", "ndjson", "xlsx"])
def test_standard_formats_produce_same_hand_checked_audit(suffix):
    row = record()
    raw = table_bytes([row], "\t" if suffix == "tsv" else ",") if suffix in ("csv", "tsv") else (
        xlsx([list(row), list(row.values())]) if suffix == "xlsx" else json.dumps(row).encode())
    result = imp.import_files([file("paired." + suffix, b"\xef\xbb\xbf" + raw if suffix == "csv" else raw)])
    assert_text_margin(result)
    source = result["manifest"]["sources"][0]
    assert source["sha256"] == sha256(b"\xef\xbb\xbf" + raw if suffix == "csv" else raw).hexdigest()
    assert source["fields"] == sorted(row) and result["manifest"]["normalized_records"] == 1
    if suffix == "xlsx":
        assert source["omitted_worksheets"] == ["Notes"] and result["manifest"]["warnings"]


@pytest.mark.parametrize("container", [lambda r:r, lambda r:[r], lambda r:{"records":[r]}])
def test_json_record_array_and_explicit_wrapper(container):
    assert_text_margin(imp.import_files([file("paired.json", container(record()))]))


def test_decimal_scores_and_numeric_metadata_are_not_coerced():
    raw = b'{"sample_id":"s","score_a":1.000000000000000000000001,"score_b":1,"metric":"quality","unit":"fraction","direction":"higher"}'
    result = imp.import_files([file("scores.json", raw)])
    assert result["mode"] == "scores" and result["family"] is None
    report = domains.audit_domain("scores", result["text"], "jsonl")
    assert Fraction(report["result"]["exact_band"][0]) == Fraction(1, 10**24)
    assert '1.000000000000000000000001' in result["text"]
    for column in ("sample_id", "metric", "unit", "group"):
        row = dict(sample_id="s",score_a=2,score_b=1,metric="quality",unit="fraction",direction="higher",group="g")
        row[column] = 1.5
        with pytest.raises(ValueError):
            imp.import_files([file("scores.json",row)])


def test_xlsx_shared_inline_and_numeric_cells_keep_precision():
    fields = ["sample_id","score_a","score_b","metric","unit","direction"]
    data = xlsx([fields, [("s",0),("n","1.000000000000000000000001"),("n","1"),"quality","fraction","higher"]], shared=["sample"])
    result = imp.import_files([file("scores.xlsx", data)])
    report = domains.audit_domain("scores", result["text"], "jsonl")
    assert Fraction(report["result"]["exact_band"][0]) == Fraction(1,10**24)
    assert report["inputs"][0]["sample_id"] == "sample"


@pytest.mark.parametrize("shared", [False, True])
def test_xlsx_phonetic_hints_do_not_modify_ids_or_block_pairing(shared):
    # OOXML rPh supplies a pronunciation hint. The actual value consists of
    # ordinary t/r text, so both workbooks identify exactly the same sample.
    fields = ["sample_id", "prompt", "gold", "output"]
    plain = xlsx([fields, ["東京", "Question", "42", "42"]])
    annotated = xlsx([fields, [("s", 0) if shared else "東京", "Question", "42", "42"]],
                     shared=["東京"] if shared else None)
    rich = '<r><t>東</t></r><r><t>京</t></r><rPh sb="0" eb="2"><t>とうきょう</t></rPh>'
    with zipfile.ZipFile(io.BytesIO(annotated)) as archive:
        parts = [(name, archive.read(name)) for name in archive.namelist()]
    member = "xl/sharedStrings.xml" if shared else "xl/worksheets/sheet1.xml"
    annotated = zipped([(name, content.replace('<t>東京</t>'.encode(), rich.encode()) if name == member else content)
                        for name, content in parts])
    result = imp.import_files([file("candidate.xlsx", annotated), file("baseline.xlsx", plain)])
    rows = workflow.load_paired(result["text"], "jsonl")
    assert rows[0]["sample_id"] == "東京" and len(rows) == 1
    assert "とうきょう" not in result["text"]
    assert result["manifest"]["pairing"]["same_ids"] is True
    assert_text_margin(result, "0")


@pytest.mark.parametrize("suffix", ["json", "csv", "xlsx"])
def test_segmentation_counts_are_explicitly_decoded(suffix):
    row = dict(sample_id="image",confusion_a=[[1,0],[0,1]],confusion_b=[[1,0],[1,0]])
    serialized = {key:json.dumps(value) if isinstance(value,list) else value for key,value in row.items()}
    raw = table_bytes([serialized]) if suffix == "csv" else xlsx([list(serialized),list(serialized.values())]) if suffix == "xlsx" else json.dumps(row).encode()
    result = imp.import_files([file("counts."+suffix,raw)])
    assert result["mode"] == "segmentation"
    report = domains.audit_domain("segmentation",result["text"],"jsonl",{"classes":[1],"aggregations":["pooled"],"empty_classes":["zero"]})
    assert report["result"]["exact_band"] == ["1","1"]
    assert result["manifest"]["sources"][0]["decoded_json_fields"] == ([] if suffix == "json" else ["confusion_a","confusion_b"])


def test_matrix_uses_all_models_and_canonical_fields():
    rows = [dict(sample_id="s",model=model,gold="42",output=output) for model,output in (("first","42"),("second","7"),("third","42"))]
    result = imp.import_files([file("models.json",rows)])
    assert result["mode"] == "matrix" and result["model_a"] == "first" and result["model_b"] == "second"
    report = matrix.analyze_matrix(matrix.load_long(result["text"],"jsonl")[2])
    assert report["result"]["n_models"] == 3 and report["pairs"][0]["exact_band"] == ["1","1"]


def test_registered_extension_can_keep_its_numeric_contract(monkeypatch):
    from examples import measurement_lab as lab
    monkeypatch.setattr(domains,"_DOMAINS",dict(domains._DOMAINS))
    lab.register()
    result = imp.import_files([file("measurements.csv",lab.DEMO_CSV.encode())],preferred_domain="measurement_lab")
    assert result["mode"] == "measurement_lab" and result["family"] is None
    assert domains.audit_domain(result["mode"],result["text"],"jsonl")["result"]["exact_band"] == ["-8/3","1"]
    original = domains.get_domain("measurement_lab")
    monkeypatch.setitem(domains._DOMAINS,"measurement_lab",domains.replace(original,formats=("csv",)))
    with pytest.raises(ValueError,match="support JSONL"):
        imp.import_files([file("measurements.csv",lab.DEMO_CSV.encode())],preferred_domain="measurement_lab")


def test_unknown_schema_and_unknown_text_fields_are_rejected():
    with pytest.raises(ValueError,match="needs fields"):
        imp.import_files([file("unknown.json",{"unknown":1})])
    with pytest.raises(ValueError,match="unrecognized fields"):
        imp.import_files([file("paired.json",record(extra="private"))])
    with pytest.raises(ValueError,match="professional"):
        imp.import_files([file("scores.csv",imp.scores.DEMO_CSV.encode())],edition="professional")


def test_two_single_model_tables_pair_by_id_and_preserve_input_order():
    a = [dict(sample_id="s1",prompt="Q1",gold="42",output="42"),dict(sample_id="s2",prompt="Q2",gold="42",output="42")]
    b = [{**row,"output":"7"} for row in reversed(a)]
    result = imp.import_files([file("candidate.csv",table_bytes(a)),file("baseline.json",b)])
    assert (result["model_a"],result["model_b"]) == ("candidate","baseline")
    assert [row["sample_id"] for row in workflow.load_paired(result["text"],"jsonl")] == ["s1","s2"]
    assert_text_margin(result)
    assert result["manifest"]["pairing"]["inner_join"] is False


@pytest.mark.parametrize("change,match", [
    (lambda rows:rows[0].update(sample_id="other"),"IDs differ"),
    (lambda rows:rows[0].update(prompt="different"),"different prompt"),
    (lambda rows:rows[0].update(gold="43"),"different prompt"),
    (lambda rows:rows[0].update(**{"class":"different"}),"different prompt"),
    (lambda rows:rows[0].update(extra="hidden"),"only optional"),
    (lambda rows:rows.append(deepcopy(rows[0])),"duplicate sample_id"),
])
def test_two_single_model_files_reject_unpaired_context(change,match):
    a = [dict(sample_id="s",prompt="Q",gold="42",output="42")]
    b = deepcopy(a)
    change(b)
    with pytest.raises(ValueError,match=match):
        imp.import_files([file("a.json",a),file("b.json",b)])


@pytest.mark.parametrize("suffix",["zip","json","jsonl","csv"])
def test_mmlu_all_formats_preserve_complete_category_and_missing_predictions(suffix):
    a = [mmlu(1),mmlu(2),mmlu(3)]
    a[0]["category"]="math"
    b = deepcopy(list(reversed(a)))
    a[1]["pred"]=None
    b[0]["pred"]="This is not a letter"
    def raw(rows):
        if suffix == "zip":
            return zipped([("archive.json",json.dumps(rows))])
        if suffix == "jsonl":
            return b"\n".join(json.dumps(row).encode() for row in rows)
        if suffix == "csv":
            return table_bytes([{**row,"options":json.dumps(row["options"])} for row in rows])
        return json.dumps(rows).encode()
    # CSV has no typed null; an empty cell is its explicit missing-pred spelling.
    if suffix == "csv":
        a[1]["pred"]=""
    result = imp.import_files([file("model_outputs_A_5shots."+suffix,raw(a)),file("model_outputs_B_5shots."+suffix,raw(b))])
    assert result["categories"] == ["computer science","math"] and result["selected_category"] == "computer science"
    assert result["family"] == imp.STRICT_LETTERS and (result["model_a"],result["model_b"]) == ("A","B")
    rows = workflow.load_paired(result["text"],"jsonl")
    assert len(rows)==2 and rows[0]["output_a"]=="" and rows[1]["output_b"]==""
    assert "A. First" in rows[0]["prompt"] and result["manifest"]["pairing"]["n_items"] == 2
    assert result["manifest"]["sources"][0]["missing_predictions"] == 1
    assert result["manifest"]["sources"][1]["invalid_predictions"] == 1
    assert result["manifest"]["sources"][0]["omitted_fields"] == ["answer_index","generated_text"]
    assert_text_margin(result,"0")
    selected = imp.import_files([file("A.json",a),file("B.json",b)],category="math")
    assert selected["manifest"]["normalized_records"] == 1


def test_mmlu_first_common_category_missing_pred_and_model_json_zip_name():
    a,b = [mmlu(1)],[mmlu(1)]
    a[0]["category"]=b[0]["category"]="biology"
    a[0].pop("pred")
    result = imp.import_files([file("model_outputs_A_5shots.json.zip",zipped([("a.json",json.dumps(a))])),file("B.json",b)])
    assert result["selected_category"]=="biology" and result["model_a"]=="A"
    assert_text_margin(result,"-1")


@pytest.mark.parametrize("change,match", [
    (lambda r:r[0].update(question_id=2),"IDs differ"),
    (lambda r:r[0].update(question="different"),"different question"),
    (lambda r:r[0].update(options=["changed","Second"]),"different question"),
    (lambda r:r[0].update(answer="B",answer_index=1),"different question"),
    (lambda r:r[0].update(category="other"),"no common category"),
    (lambda r:r[0].update(answer_index=1),"answer_index"),
    (lambda r:r[0].update(answer_index=True),"answer_index"),
    (lambda r:r[0].update(options=[]),"1–16"),
    (lambda r:r[0].update(question_id=1.5),"Sample IDs"),
    (lambda r:r[0].update(extra="unknown"),"unrecognized extra"),
    (lambda r:r[0].pop("options"),"matching MMLU"),
    (lambda r:r.append(deepcopy(r[0])),"Duplicate MMLU"),
])
def test_mmlu_rejects_inconsistent_sources(change,match):
    a,b=[mmlu()],[mmlu()]
    change(b)
    with pytest.raises(ValueError,match=match):
        imp.import_files([file("a.json",a),file("b.json",b)])


def test_category_and_same_model_errors():
    pair=[file("a.json",[mmlu()]),file("b.json",[mmlu()])]
    with pytest.raises(ValueError,match="present in both"):
        imp.import_files(pair,category="absent")
    with pytest.raises(ValueError,match="distinct model"):
        imp.import_files([pair[0],file("a.csv",table_bytes([mmlu(options='["one","two"]')]))])
    with pytest.raises(ValueError,match="nonempty model"):
        imp.import_files([file(".json",[mmlu()]),pair[1]])
    single=file("a.json",[dict(sample_id="s",prompt="Q",gold="A",output="A")])
    with pytest.raises(ValueError,match="applies only"):
        imp.import_files([single,file("b.json",[dict(sample_id="s",prompt="Q",gold="A",output="A")])],category="cs")
    with pytest.raises(ValueError,match="requires two"):
        imp.import_files([file("paired.json",record())],category="cs")
    for value in (single,pair[0]):
        with pytest.raises(ValueError,match="second model"):
            imp.import_files([value])


def test_mmlu_single_option_archives_are_preserved_and_disclosed():
    rows = [mmlu(options=["only"])]
    result = imp.import_files([file("a.json",rows),file("b.json",rows)])
    assert result["manifest"]["sources"][0]["single_option_records"] == 1
    assert any("only one option" in warning for warning in result["manifest"]["warnings"])
    assert result["manifest"]["normalized_records"] == 1
    assert_text_margin(result,"0")


@pytest.mark.parametrize("files,match", [
    ([],"one paired"),([{}, {}, {}],"one paired"),([{}],"original bytes"),
    ([{"name":"x.json","data":"text"}],"original bytes"),
    ([{"name":"","data":b""}],"original bytes"),
    ([file("x.exe",b"data")],"Choose CSV"),([file("x.json",b"\xff")],"UTF-8"),
    ([file("x.zip",b"broken")],"readable ZIP"),
    ([file("x.json",b"[]")],"nonempty record"),
    ([file("x.json",b'{"records":[],"extra":1}')],"wrapper"),
    ([file("x.json",b'{"x":1,"x":2}')],"Duplicate JSON"),
    ([file("x.json",b'{"x":NaN}')],"constant"),
    ([file("x.json",b'['*65+b']'*65)],"nesting"),
    ([file("x.jsonl",b'[]')],"nonempty record"),
    ([file("x.csv",b'a,a\n1,2')],"distinct"),
    ([file("x.csv",b'a,b\n1')],"same number"),
    ([file("x.csv",b'a\n"unterminated')],"Invalid delimited"),
])
def test_malformed_sources_fail_actionably(files,match):
    with pytest.raises(ValueError,match=match):
        imp.import_files(files)


@pytest.mark.parametrize("entries", [
    [("../a.json","[]")],[("/a.json","[]")],[("C:/a.json","[]")],[("a\\b.json","[]")],
    [("a.json","[]"),("evil.py","print(1)")],[("a.txt","[]")],
    [("a.json","{}")],[("a.json",json.dumps([record()]))],
])
def test_zip_rejects_unsafe_and_non_mmlu_contents(entries):
    with pytest.raises(ValueError):
        imp.import_files([file("x.zip",zipped(entries))])


def test_archive_symlinks_duplicates_encryption_and_corruption():
    link=zipfile.ZipInfo("link.json")
    link.create_system=3
    link.external_attr=(stat.S_IFLNK|0o777)<<16
    with pytest.raises(ValueError,match="symbolic"):
        imp.import_files([file("x.zip",zipped([(link,"target")]))])
    with pytest.warns(UserWarning):
        duplicate=zipped([("x.json","[]"),("x.json","[]")])
    with pytest.raises(ValueError,match="Duplicate"):
        imp.import_files([file("x.zip",duplicate)])
    raw=bytearray(zipped([("x.json",json.dumps([mmlu()]))]))
    for signature,offset in ((b'PK\x03\x04',6),(b'PK\x01\x02',8)):
        index=raw.index(signature)+offset
        raw[index:index+2]=struct.pack('<H',struct.unpack('<H',raw[index:index+2])[0]|1)
    with pytest.raises(ValueError,match="encrypted"):
        imp.import_files([file("x.zip",bytes(raw))])
    corrupt=bytearray(zipped([("x.json",json.dumps([mmlu()]))]))
    corrupt[30+len("x.json")]=ord("!")
    with pytest.raises(ValueError,match="Cannot read"):
        imp.import_files([file("x.zip",bytes(corrupt))])


def test_size_and_row_budgets_are_enforced_before_audit(monkeypatch):
    sample=file("paired.json",record())
    monkeypatch.setattr(imp,"MAX_FILE_BYTES",len(sample["data"])-1)
    with pytest.raises(ValueError,match="24 MiB"):
        imp.import_files([sample])
    monkeypatch.setattr(imp,"MAX_FILE_BYTES",10000)
    monkeypatch.setattr(imp,"MAX_TOTAL_BYTES",len(sample["data"]))
    with pytest.raises(ValueError,match="48 MiB"):
        imp.import_files([sample,sample])
    monkeypatch.setattr(imp,"MAX_TOTAL_BYTES",20000)
    monkeypatch.setattr(imp,"MAX_MEMBERS",0)
    with pytest.raises(ValueError,match="256 members"):
        imp.import_files([file("x.zip",zipped([("x.json","[]")]))])
    monkeypatch.setattr(imp,"MAX_MEMBERS",256)
    monkeypatch.setattr(imp,"MAX_EXPANDED_BYTES",1)
    with pytest.raises(ValueError,match="32 MiB"):
        imp.import_files([file("x.zip",zipped([("x.json","[]")]))])
    monkeypatch.setattr(imp,"MAX_RAW_ROWS",1)
    for suffix,raw in (("json",json.dumps([record(),record()]).encode()),("csv",table_bytes([record(),record()])),("jsonl",b'{}\n{}')):
        with pytest.raises(ValueError,match="at most 1"):
            imp.import_files([file("x."+suffix,raw)])
    monkeypatch.setattr(imp,"MAX_RAW_ROWS",20000)
    monkeypatch.setattr(imp,"MAX_ROWS",0)
    with pytest.raises(ValueError,match="normalized audit rows"):
        imp.import_files([sample])
    monkeypatch.setattr(imp,"MAX_ROWS",5000)
    monkeypatch.setattr(imp,"MAX_BYTES",1)
    with pytest.raises(ValueError,match="4 MiB"):
        imp.import_files([sample])


@pytest.mark.parametrize("category",["",1,[]])
def test_invalid_category_type(category):
    with pytest.raises(ValueError,match="Category must"):
        imp.import_files([file("paired.json",record())],category=category)


def test_xlsx_formulas_dtd_and_entity_are_rejected():
    ns='xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    formula='<worksheet %s><sheetData><row><c><f>WEBSERVICE("https://example.invalid")</f><v>42</v></c></row></sheetData></worksheet>'%ns
    with pytest.raises(ValueError,match="Paste values"):
        imp.import_files([file("x.xlsx",xlsx([],sheet_xml=formula))])
    for xml in ('<!DOCTYPE x><workbook/>','<!DOCTYPE x [<!ENTITY data "bomb">]><workbook/>'):
        for encoded in (xml.encode(),xml.encode('utf-16')):
            with pytest.raises(ValueError,match="DTD or ENTITY"):
                imp.import_files([file("x.xlsx",xlsx([],workbook=encoded))])


@pytest.mark.parametrize("options,match", [
    ({"workbook":"<broken"},"Invalid workbook XML"),
    ({"workbook":"<workbook/>"},"readable first"),
    ({"rels":'<Relationships><Relationship Id="rId1" TargetMode="External" Target="https://example.invalid"/></Relationships>'},"internal references"),
    ({"rels":'<Relationships><Relationship Id="rId1" Target="missing.xml"/></Relationships>'},"Cannot read"),
    ({"sheet_xml":'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="bad"/></row></sheetData></worksheet>'},"cell reference"),
    ({"sheet_xml":'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="ZZ1"/></row></sheetData></worksheet>'},"256 distinct"),
    ({"sheet_xml":'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c t="s"><v>0</v></c></row></sheetData></worksheet>'},"shared-string"),
    ({"sheet_xml":'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c t="e"><v>#DIV/0!</v></c></row></sheetData></worksheet>'},"error-valued"),
])
def test_xlsx_malformed_structure_errors(options,match):
    with pytest.raises(ValueError,match=match):
        imp.import_files([file("x.xlsx",xlsx([],**options))])


def test_xlsx_sparse_and_header_boundaries(monkeypatch):
    for rows in ([],[["a","a"]],[["a",""]],[["a"],["x","y"]]):
        with pytest.raises(ValueError):
            imp.import_files([file("x.xlsx",xlsx(rows))])
    monkeypatch.setattr(imp,"MAX_RAW_ROWS",1)
    with pytest.raises(ValueError,match="at most 1"):
        imp.import_files([file("x.xlsx",xlsx([["a"],["1"],["2"]]))])
    # Empty inline strings and blank cells stay empty; a valid declared empty output
    # is retained and scored as incorrect, rather than dropping the record.
    row=record()
    ns='xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    header=''.join('<c t="inlineStr"><is><t>%s</t></is></c>'%key for key in row)
    values=''.join('<c t="inlineStr"><is><t>%s</t></is></c>'%escape(value) for value in list(row.values())[:3])+'<c t="inlineStr"/><c t="inlineStr"><is><t>7</t></is></c>'
    sheet='<worksheet %s><sheetData><row>%s</row><row>%s</row><row><c/></row></sheetData></worksheet>'%(ns,header,values)
    result=imp.import_files([file("x.xlsx",xlsx([],sheet_xml=sheet))])
    assert_text_margin(result,"0")
