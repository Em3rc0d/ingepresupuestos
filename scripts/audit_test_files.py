#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Ejecuta cada archivo de tests en proceso y datos de usuario aislados.

Los tests heredados cambian core.database.DB_PATH y core.config.DB_PATH durante
la importación. Un único proceso Pytest mezcla esas copias del seed. Este runner
NO omite errores: un resultado no-cero, timeout o segfault bloquea el gate.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="*", default=None, help="Archivo(s) tests/test_*.py")
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--output", default="audit-test-results.json")
    opts = p.parse_args()
    files = [Path(s) for s in opts.only] if opts.only else sorted(Path("tests").glob("test_*.py"))
    if opts.timeout < 10 or not files:
        p.error("Se requiere uno o más archivos y timeout >=10")
    results = []
    for file in files:
        target = (ROOT / file).resolve()
        if not target.is_relative_to(ROOT / "tests") or not target.is_file():
            p.error(f"Ruta de prueba no válida: {file}")
        print(f"--- TEST MODULE {file} ---", flush=True)
        with tempfile.TemporaryDirectory(prefix="ip_audit_") as temp:
            env = os.environ.copy()
            env["QT_QPA_PLATFORM"] = os.environ.get("QT_QPA_PLATFORM", "offscreen")
            env["MPLBACKEND"] = "Agg"
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["XDG_DATA_HOME"] = temp
            env["APPDATA"] = temp
            env["HOME"] = temp
            cmd = [sys.executable, "-m", "pytest", "-q", str(target.relative_to(ROOT)), 
                   "--tb=short", "--maxfail=5"]
            try:
                run = subprocess.run(cmd, cwd=ROOT, env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, errors="replace", timeout=opts.timeout,
                                     check=False)
                rc, output = run.returncode, run.stdout
            except subprocess.TimeoutExpired as exc:
                rc = 124
                output = (exc.stdout or b"")
                if isinstance(output, bytes):
                    output = output.decode("utf-8", "replace")
                output += "\nERROR: timeout del módulo."
            tail = output[-14000:]
            print(tail, flush=True)
            counts = {}
            for k in ("passed", "failed", "skipped", "error"):
                m = re.findall(rf"(\d+) {k}", output)
                counts[k] = int(m[-1]) if m else 0
            results.append({"file":file.as_posix(),"returncode":rc,
                            "counts":counts,"output_tail":tail})
            print(f"--- END MODULE {file}: rc={rc} ---", flush=True)
    summary = {"modules": len(results), "modules_failed":sum(x["returncode"] != 0 for x in results),
               "results":results}
    out = Path(opts.output)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"SUMMARY: {summary['modules']} modules; {summary['modules_failed']} failing modules",flush=True)
    return 1 if summary["modules_failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
