#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Auditoría de METADATOS de presupuestos_seed.db: no imprime datos de clientes.

El archivo se abre con SQLite URI read-only immutable; no altera el seed.
Los contadores sirven como indicadores de revisión, no certifican anonimato.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path

SENSITIVE = re.compile(
    r"(?:email|correo|celular|telefono|teléfono|direccion|dirección|"
    r"password|clave|token|cliente|nombre|contacto|documento|ruc|dni|"
    r"cuenta|representante|usuario)",
    re.IGNORECASE,
)


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def audit(path: Path) -> dict:
    path = path.resolve(strict=True)
    if path.suffix.lower() not in (".db", ".sqlite", ".sqlite3"):
        raise ValueError("Se esperaba un archivo de base de datos SQLite")
    conn = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        violations = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        flagged = []
        for table in tables:
            cols = [row[1] for row in conn.execute(
                f"PRAGMA table_info({quote_identifier(table)})")]
            for column in cols:
                if not SENSITIVE.search(column):
                    continue
                n = conn.execute(
                    f"SELECT COUNT(*) FROM {quote_identifier(table)} WHERE "
                    f"{quote_identifier(column)} IS NOT NULL AND "
                    f"LENGTH(TRIM(CAST({quote_identifier(column)} AS TEXT))) > 0"
                ).fetchone()[0]
                if n:
                    flagged.append({"table": table, "column": column, "populated_rows": n})
        return {
            "seed_file": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "sqlite_integrity": integrity,
            "foreign_key_violations": violations,
            "table_count": len(tables),
            "potentially_sensitive_fields": flagged,
            "caveat": "Indicadores por nombre de columna: no demuestra ni descarta PII; "
                      "ningún valor de fila fue extraído o impreso.",
        }
    finally:
        conn.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("seed", nargs="?", default="presupuestos_seed.db")
    p.add_argument("--output", default="audit-seed-metadata.json")
    a = p.parse_args()
    result = audit(Path(a.seed))
    Path(a.output).write_text(json.dumps(result, indent=2, ensure_ascii=False),
                              encoding="utf-8")
    # No publicar valores; solo nombres de campos y conteos en CI.
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["sqlite_integrity"] != "ok" or result["foreign_key_violations"]:
        raise SystemExit(1)
