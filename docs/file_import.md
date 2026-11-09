# Drop files and compare results

Start the local app with `start_generalized.cmd`, `start_professional.cmd`, or
`python -m robustband ui`. Drop files anywhere on the page, or use **Select files**.
The app imports, validates and analyzes recognized data automatically. Files stay
on this machine. Opening `WELCOME.html` alone provides saved examples; start the
local app to analyze your own files.

## Supported inputs

| Format | What to supply |
|---|---|
| CSV / TSV | UTF-8 table with a header row |
| JSON | One record, an array of records, or `{"records": [...]}` |
| JSONL / NDJSON | One JSON record per LF/CRLF-delimited line |
| Excel `.xlsx` | First worksheet, with column names in the first row; other sheets are listed as omitted |
| Official MMLU-Pro result ZIP | Two model archives, each containing one JSON record file |

Legacy `.xls`, macro workbooks, workbook formulas, PDFs and arbitrary ZIP layouts
need conversion to a supported data table first. A file extension alone does not
establish that its records have the required meaning.

**One paired file:** use the selected domain's template. AI text uses
`sample_id,prompt,gold,output_a,output_b`; numeric scores use the score template;
segmentation uses the confusion-matrix template. Structured confusion matrices in
CSV, TSV or Excel cells must contain JSON arrays. A long table with
`sample_id,model,gold,output` is recognized as a multi-model ranking input.

**Two single-model files:** each must contain `sample_id,prompt,gold,output`.
Select both files together. The first file is A, the second B; source names appear
in the import details. IDs and reference context must match exactly. Missing IDs,
conflicting references and duplicate IDs produce errors; no inner join removes
unmatched samples. Declare optional grouping columns consistently in both files.

**Two official MMLU-Pro archives:** select them together, or drop the first and
then the second. The app selects the complete common computer-science subject
when available; otherwise it starts with the first common subject. The subject
selector reruns the complete selected subject. This is a subject comparison,
not an all-subject benchmark score. IDs, questions, options and answers must match.
Archived prediction letters are scored with strict extraction, exact match and
micro averaging. Missing or out-of-options predictions count as incorrect and
their counts appear in the import details. These deterministic results can differ
from upstream scores that use random guessing for missing predictions.

## Read and save the result

Review the file names, number of paired samples, selected subject, scoring rules
and warnings before interpreting the band. **Save complete results (ZIP)** contains:

- `report.html`: readable report with import details;
- `report.json`: exact replay data;
- `paired.jsonl`: normalized input used in the calculation;
- `import_manifest.json`: source hashes, scope, conversions, omissions and rules.

Original archives and workbooks are not copied into this result bundle. Keep them
if you need to inspect original generated answers or worksheets later. Source
hashes identify those files; they do not establish reference-answer correctness.
Changing comparison settings hides the previous import bundle. Recalculate and
use the ordinary HTML/JSON export controls for the edited comparison.

## Input contract change

Direct audit inputs reject unknown fields. The import adapters perform explicit
mapping and record omitted source fields in the manifest. They do not silently
guess arbitrary column aliases. Use the existing conversion workflow with an
explicit mapping for other schemas, then import its normalized output.

Limits are 24 MiB per source, 48 MiB combined, 32 MiB expanded per archive,
256 archive members and 20,000 raw records per source. Normalized audit inputs
retain the engine's 4 MiB / 5,000-row limits. Only one large import runs at a time.
Malformed archives, unsafe member paths, encrypted archives, XML entities and
workbook formulas are rejected. Data is read in memory; archive members are not
extracted to the filesystem.

## 中文操作速查

启动本地软件后，拖入一个配对表，或同时选择两份单模型结果，软件会自动识别、校验并分析。
支持 CSV、TSV、JSON、JSONL、NDJSON、XLSX，以及官方 MMLU-Pro 模型结果 ZIP。
Excel 读取第一张工作表；省略的工作表与字段会列入导入说明。两份结果必须具有完整一致的
样本与参考答案，不会偷偷取交集。MMLU-Pro 默认分析一个完整公共科目，可切换科目，
缺失或无效预测按错误计入。请先检查样本数、科目和规则，再下载含报告、配对数据与来源说明
的完整结果包。其他列名需先做显式映射转换。
