# SPDX-License-Identifier: MIT
"""Measure bounded synthetic audits in fresh processes, including OS peak RSS."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from robustband import __version__, workflow, scores, matrix
from robustband.storage import write_json_atomic


def peak_rss():
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                    "PagefileUsage", "PeakPagefileUsage")]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return counters.PeakWorkingSetSize, "GetProcessMemoryInfo.PeakWorkingSetSize"
    import resource
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value * (1 if sys.platform == "darwin" else 1024)), "getrusage.ru_maxrss"


def worker(kind):
    start = time.perf_counter()
    if kind == "text":
        text = "sample_id,prompt,gold,output_a,output_b\n" + "".join(
            "%d,Question?,42,42,7\n" % i for i in range(5000))
        report = workflow.analyze(workflow.load_paired(text))
        assert workflow.verify_report(report)
        size = {"records": 5000, "models": 2}
    elif kind == "scores":
        text = "sample_id,score_a,score_b,metric,unit,direction\n" + "".join(
            "%d,9,10,latency,ms,lower\n" % i for i in range(5000))
        report = scores.analyze_scores(scores.load_scores(text))
        assert scores.verify_scores_report(report)
        size = {"records": 5000, "models": 2}
    else:
        text = "sample_id,model,gold,output\n" + "".join(
            "%d,m%d,42,%d\n" % (i, j, 42 if (i + j) % 3 else 7)
            for i in range(500) for j in range(8))
        report = matrix.analyze_matrix(matrix.load_long(text)[2])
        assert matrix.verify_matrix_report(report)
        size = {"records": 4000, "paired_samples": 500, "models": 8}
    elapsed = time.perf_counter() - start
    peak, method = peak_rss()
    return {"case": kind, **size, "seconds_load_audit_replay": elapsed,
            "peak_rss_bytes": peak, "peak_method": method, "replay_verified": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("text", "scores", "matrix"))
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker)))
        return
    measurements = []
    for kind in ("text", "scores", "matrix"):
        for trial in range(1, 4):
            process = subprocess.run([sys.executable, "-S", str(Path(__file__)), "--worker", kind],
                                     cwd=ROOT, capture_output=True, text=True, check=True, timeout=60)
            measurements.append({"trial": trial, **json.loads(process.stdout)})
    paths = [Path(__file__)] + sorted((ROOT / "robustband").glob("*.py"))
    receipt = {"schema": "robustband.resource_measurement/v1", "version": __version__,
               "platform": platform.platform(), "python": platform.python_version(),
               "measurements": measurements,
               "scope": "Synthetic default-protocol audits, three fresh processes per case. Timing includes load, audit and replay; excludes process startup. OS peak resident memory includes interpreter, imports and input preparation up to measurement. Not a worst-case bound or a human usability test.",
               "source_sha256_lf": {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in paths}}
    write_json_atomic(ROOT / "results" / ("resource_measurement_%s.json" % __version__), receipt)
    print(json.dumps(measurements, indent=2))


if __name__ == "__main__":
    main()
