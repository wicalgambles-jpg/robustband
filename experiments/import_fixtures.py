# SPDX-License-Identifier: MIT
"""Small offline, hand-checkable files for the browser import workflow."""
import csv
import io
import json
from pathlib import Path
import sys
from xml.sax.saxutils import escape
import zipfile


def workbook(rows):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="xl/workbook.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/></Relationships>')
        archive.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Results" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/></Relationships>')
        sheet = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        for number, row in enumerate(rows, 1):
            sheet += '<row r="%d">' % number
            for column, value in enumerate(row):
                sheet += '<c r="%s%d" t="inlineStr"><is><t>%s</t></is></c>' % (chr(65 + column), number, escape(str(value)))
            sheet += '</row>'
        archive.writestr("xl/worksheets/sheet1.xml", sheet + '</sheetData></worksheet>')
    return buffer.getvalue()


def main():
    root = Path(sys.argv[1]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    row = dict(sample_id="q1", prompt="What is six times seven?", gold="42", output_a="42", output_b="7")
    cases = []
    for suffix in ("csv", "tsv", "json", "jsonl", "ndjson", "xlsx"):
        path = root / ("paired." + suffix)
        if suffix == "xlsx":
            data = workbook([list(row), list(row.values())])
        elif suffix in ("csv", "tsv"):
            buffer = io.StringIO(newline="")
            writer = csv.DictWriter(buffer, list(row), delimiter="\t" if suffix == "tsv" else ",", lineterminator="\n")
            writer.writeheader()
            writer.writerow(row)
            data = buffer.getvalue().encode()
        else:
            data = (json.dumps([row] if suffix == "json" else row) + "\n").encode()
        path.write_bytes(data)
        cases.append(dict(name=suffix, files=[str(path)], n=1, band=["1", "1"]))
    paths = []
    for name, answer in (("first-model", "42"), ("second-model", "7")):
        path = root / (name + ".json")
        path.write_text(json.dumps([{k: v for k, v in row.items() if not k.startswith("output_")} | {"output": answer}]), encoding="utf-8")
        paths.append(str(path))
    cases.append(dict(name="two independent model files", files=paths, n=1, band=["1", "1"]))
    paths = []
    for name, pred in (("fixture-base", "A"), ("fixture-instruct", "B")):
        path = root / ("model_outputs_" + name + "_5shots.zip")
        value = [dict(question_id=1, question="Choose the first letter", options=["first", "second"],
                      answer="A", answer_index=0, category="computer science", pred=pred)]
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(path.stem + ".json", json.dumps(value))
        paths.append(str(path))
    cases.append(dict(name="MMLU-Pro ZIP", files=paths, n=1, band=["1", "1"]))
    path = root / "ranking.tsv"
    path.write_text("sample_id\tmodel\tgold\toutput\nq1\tA\t42\t42\nq1\tB\t42\t7\n", encoding="utf-8")
    cases.append(dict(name="ranking long table", files=[str(path)], n=1, band=["1", "1"], matrix=True))
    (root / "cases.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")
    print(str(root))


if __name__ == "__main__":
    main()
