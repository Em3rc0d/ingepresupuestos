"""Run each inherited test module in a clean Python process.

QA-only utility: never mutates git, writes no production SQLite.
Captures known inherited failures without Qt abort terminating entire sweep.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    root = Path(__file__).resolve().parents[1]
    cases = sorted((root / "tests").glob("test_*.py"))
    results = []
    start = time.monotonic()
    budget = 15 * 60
    for index, case in enumerate(cases, 1):
        if time.monotonic() - start > budget:
            print("TIME BUDGET REACHED: remaining files not executed", flush=True)
            break
        with tempfile.TemporaryDirectory(prefix="inherited-qa-") as temp:
            env = os.environ.copy()
            env["QT_QPA_PLATFORM"] = "offscreen"
            env["MPLBACKEND"] = "Agg"
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["XDG_DATA_HOME"] = str(Path(temp) / "xdg")
            env["APPDATA"] = str(Path(temp) / "appdata")
            cmd = [sys.executable, "-m", "pytest", "-q", "-ra",
                   "--timeout=40", str(case.relative_to(root))]
            print(f"CASE {index}/{len(cases)}: {case.name}", flush=True)
            t0 = time.monotonic()
            try:
                process = subprocess.run(cmd, cwd=root, env=env,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT,
                                         text=True, timeout=80)
                combined = process.stdout
                status = "PASS" if process.returncode == 0 else "FAIL"
                last = combined.splitlines()[-14:]
                result = {"file":case.name,"status":status,"code":process.returncode,
                          "seconds":round(time.monotonic()-t0,1),"summary":last}
            except subprocess.TimeoutExpired as exc:
                combined = (exc.stdout or b"")
                if isinstance(combined, bytes):
                    combined = combined.decode(errors="replace")
                result = {"file":case.name,"status":"TIMEOUT","code":124,
                          "seconds":round(time.monotonic()-t0,1),
                          "summary":combined.splitlines()[-8:]}
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    counts = {kind:sum(r["status"] == kind for r in results)
              for kind in ("PASS","FAIL","TIMEOUT")}
    counts["NOT_EXECUTED"] = len(cases)-len(results)
    counts["TOTAL_FILES"] = len(cases)
    print("REGRESSION_SWEEP_SUMMARY " + json.dumps(counts), flush=True)
    return 0 if counts["FAIL"] == counts["TIMEOUT"] == counts["NOT_EXECUTED"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
