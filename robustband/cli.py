# SPDX-License-Identifier: MIT
"""One command surface for interactive use, automation and report replay."""
import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .workflow import DEFAULT_FAMILY, MAX_BYTES
from .report import save_report
from .domains import EDITIONS, domain_options, get_domain, audit_domain, verify_audit


def main(argv=None):
    parser = argparse.ArgumentParser(prog="robustband", description="Audit a declared preference for A on paired archived measurements.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--edition", choices=EDITIONS, default="generalized", help="Professional text evaluation or extensible domain workflows")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Run a hand-checkable example and export its report")
    demo.add_argument("--output", default="robustband-demo")
    demo.add_argument("--domain", default="text")
    template = sub.add_parser("template", help="Write an example paired CSV to adapt to your data")
    template.add_argument("path", type=Path)
    template.add_argument("--domain", default="text")
    sub.add_parser("domains", help="List registered domains, formats and protocol defaults")
    convert = sub.add_parser('convert', help='Validate and convert paired CSV/JSONL without changing values')
    convert.add_argument('input', type=Path)
    convert.add_argument('--domain', choices=('text','scores','segmentation','matrix'), required=True)
    convert.add_argument('--format', choices=('csv','jsonl'), default=None)
    convert.add_argument('--to', choices=('csv','jsonl'), default='jsonl')
    convert.add_argument('--mapping', type=Path)
    convert.add_argument('--output', type=Path, required=True)
    convert.add_argument('--allow-extra-columns', action='store_true')
    convert.add_argument('--overwrite', action='store_true')
    audit = sub.add_parser("audit", help="Validate paired CSV/JSONL, compute and export JSON/HTML")
    audit.add_argument("input", type=Path)
    audit.add_argument("--format", choices=("csv", "jsonl"), default="csv")
    audit.add_argument("--model-a", default="A")
    audit.add_argument("--model-b", default="B")
    for key in DEFAULT_FAMILY:
        audit.add_argument("--" + key, nargs="+", default=DEFAULT_FAMILY[key])
    audit.add_argument("--output", default="robustband-report")
    audit.add_argument("--require-robust", action="store_true", help="Exit 1 if the declared strict claim is not ROBUST")
    segment = sub.add_parser("segment", help="Audit paired segmentation confusion matrices")
    segment.add_argument("input", type=Path)
    segment.add_argument("--classes", nargs="+", type=int, default=None)
    segment.add_argument("--aggregations", nargs="+", default=["pooled", "image_mean"])
    segment.add_argument("--empty-classes", nargs="+", choices=("zero", "omit"), default=["zero"])
    segment.add_argument("--model-a", default="A")
    segment.add_argument("--model-b", default="B")
    segment.add_argument("--output", default="robustband-report")
    segment.add_argument("--require-robust", action="store_true")
    scalar = sub.add_parser("scores", help="Audit recorded paired numeric metrics")
    scalar.add_argument("input", type=Path)
    scalar.add_argument("--format", choices=("csv", "jsonl"), default="csv")
    scalar.add_argument("--aggregations", nargs="+", default=["mean", "median"])
    generic = sub.add_parser("run", help="Run any registered domain using an optional JSON policy file")
    generic.add_argument("input", type=Path)
    generic.add_argument("--domain", required=True)
    generic.add_argument("--format", choices=("csv", "jsonl"), default=None)
    generic.add_argument("--policy", type=Path, help="JSON object declaring a domain's protocol family")
    decision = sub.add_parser("decision", help="Check adoption criteria over separate primary and guardrail targets")
    decision.add_argument("input", type=Path)
    decision.add_argument("--plan", type=Path, required=True)
    decision.add_argument("--mapping", type=Path, help="Optional explicit wide-column score mapping")
    decision.add_argument("--format", choices=("csv", "jsonl"), default="csv")
    decision.add_argument("--require-pass", action="store_true", help="Exit 1 unless all adoption criteria pass")
    decision_template = sub.add_parser("decision-template", help="Write a synthetic paired example, mapping and adoption plan")
    decision_template.add_argument("output", type=Path)
    ranking = sub.add_parser("matrix", help="Rank more than two models under the declared scoring protocols")
    ranking.add_argument("input", type=Path)
    ranking.add_argument("--format", choices=("csv", "jsonl"), default="csv")
    ranking.add_argument("--models", nargs="+", default=None, help="Subset of model names to rank")
    for key in DEFAULT_FAMILY:
        ranking.add_argument("--" + key, nargs="+", default=DEFAULT_FAMILY[key])
    ranking.add_argument("--output", default="robustband-ranking")
    ranking.add_argument("--require-stable", action="store_true", help="Exit 1 unless the ranking is stable under every protocol")
    for command in (scalar, generic, decision):
        command.add_argument("--model-a", default="A")
        command.add_argument("--model-b", default="B")
        command.add_argument("--output", default="robustband-report")
        if command is not decision:
            command.add_argument("--require-robust", action="store_true")
    verify = sub.add_parser("verify", help="Recompute a JSON report with its recorded inputs and protocols")
    verify.add_argument("report", type=Path)
    ui = sub.add_parser("ui", help="Open the local browser interface")
    ui.add_argument("--port", type=int, default=0)
    ui.add_argument("--no-browser", action="store_true")
    ui.add_argument("--edition", dest="ui_edition", choices=EDITIONS, default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == "domains":
            print(json.dumps(domain_options(args.edition), ensure_ascii=False, indent=2))
            return 0
        if args.command == 'convert':
            from .convert import convert_table, save_conversion
            if args.mapping and args.mapping.resolve() in {
                    args.output.resolve(), args.output.with_name(args.output.name + '.manifest.json').resolve()}:
                raise ValueError('Conversion output cannot overwrite a mapping source file; choose a different output path.')
            if args.input.stat().st_size > MAX_BYTES:
                raise ValueError('Input exceeds 4 MiB; split the file or use the Python API.')
            text = args.input.read_text(encoding='utf-8')
            mapping = json.loads(args.mapping.read_text(encoding='utf-8-sig')) if args.mapping else None
            result = convert_table(text, args.domain, args.format or ('jsonl' if args.input.suffix.lower() in ('.jsonl','.ndjson') else 'csv'),
                                   args.to, mapping, args.edition, args.allow_extra_columns)
            save_conversion(result, args.input, args.output, args.overwrite)
            print('CONVERT PASS: %s records, exact roundtrip verified. Output: %s' % (result['manifest']['n_records'], args.output))
            return 0
        if args.command == "ui":
            if not 0 <= args.port <= 65535:
                raise ValueError("Port must be between 0 and 65535; 0 selects a free port.")
            from .local_ui import run_ui
            return run_ui(args.port, not args.no_browser, args.ui_edition or args.edition)
        if args.command == "template":
            args.path.write_text(get_domain(args.domain, args.edition).metadata["example"], encoding="utf-8")
            print("Paired input template: " + str(args.path))
            return 0
        if args.command == "decision-template":
            from .decision import EXAMPLE, EXAMPLE_MAPPING, EXAMPLE_PLAN, validate_plan
            validate_plan(EXAMPLE_PLAN, args.edition)
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "paired.csv").write_text(EXAMPLE, encoding="utf-8")
            for name, value in (("plan", EXAMPLE_PLAN), ("mapping", EXAMPLE_MAPPING)):
                (args.output / (name+".json")).write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")
            print("Decision example, plan and mapping: " + str(args.output))
            return 0
        if args.command == "verify":
            stored = json.loads(args.report.read_text(encoding="utf-8"))
            verify_audit(stored, args.edition)
            print("VERIFY PASS: recomputed inputs, protocols, exact results and source hashes.")
            return 0
        if args.command == "demo":
            domain = get_domain(args.domain, args.edition)
            report = audit_domain(domain.id, domain.metadata["example"], domain.metadata["example_format"])
        else:
            sources = [args.input] + [getattr(args, name) for name in ("plan", "mapping", "policy")
                                      if getattr(args, name, None) is not None]
            targets = {(Path(args.output) / name).resolve() for name in ("report.json", "report.html")}
            if any(source.resolve() in targets for source in sources):
                raise ValueError("Report output cannot overwrite a source file; choose a different output directory.")
            if args.input.stat().st_size > MAX_BYTES:
                raise ValueError("Input exceeds 4 MiB; split the file or use the Python API for larger datasets.")
            raw = args.input.read_bytes()
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ValueError("Input must be UTF-8 text; byte %d is not valid UTF-8. Save the file as UTF-8 and retry."
                                 % exc.start) from exc
            if args.command == "matrix":
                from .matrix import analyze_matrix, load_long
                family = {key: getattr(args, key) for key in DEFAULT_FAMILY}
                report = analyze_matrix(load_long(text, args.format)[2], family, args.models)
                directory = save_report(report, args.output)
                result = report["result"]
                print("%s | models %s | samples %s | flipping pairs %s | report %s" % (
                    result["verdict"], result["n_models"], result["n_items"],
                    result["flipping_pairs"], directory / "report.html"))
                return int(args.require_stable and result["verdict"] != "STABLE")
            if args.command == "decision":
                from .decision import analyze_decision
                report = analyze_decision(text, json.loads(args.plan.read_text(encoding="utf-8-sig")), args.format,
                    json.loads(args.mapping.read_text(encoding="utf-8-sig")) if args.mapping else None,
                    args.model_a, args.model_b, args.edition)
                directory = save_report(report, args.output)
                print("%s | targets %s | pairs %s | report %s" % (report["result"]["status"],
                    report["result"]["n_targets"], report["result"]["n_items"], directory / "report.html"))
                return int(args.require_pass and report["result"]["status"] != "PASS")
            elif args.command == "segment":
                domain, format = "segmentation", "jsonl"
                family = {"classes": args.classes, "aggregations": args.aggregations, "empty_classes": args.empty_classes}
            elif args.command == "scores":
                domain, format, family = "scores", args.format, {"aggregations": args.aggregations}
            elif args.command == "run":
                domain, format = args.domain, args.format
                family = json.loads(args.policy.read_text(encoding="utf-8")) if args.policy else None
            else:
                domain, format, family = "text", args.format, {k: getattr(args, k) for k in DEFAULT_FAMILY}
            get_domain(domain, args.edition)
            report = audit_domain(domain, text, format, family, args.model_a, args.model_b)
        directory = save_report(report, args.output)
        result = report["result"]
        print("%s | band [%s, %s] | support %s/%s | pairs %s" %
              (result["verdict"], *result.get("display_band", result["exact_band"]), result["support_count"], result["n_protocols"], result["n_items"]))
        print("Reports: " + str(directory / "report.html") + " and " + str(directory / "report.json"))
        return int(args.command in ("audit", "segment", "scores", "run") and args.require_robust and result["verdict"] != "ROBUST")
    except (OSError, ValueError) as exc:
        print("Error: " + str(exc), file=sys.stderr)
        return 2
