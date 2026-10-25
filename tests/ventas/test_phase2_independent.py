"""Independent Phase-2 Sales contract tests. All SQLite and files are synthetic.

Written on audit branch only. Does not touch legacy seed or user profile.
"""
from dataclasses import asdict
from hashlib import sha256
import csv
import json
import sqlite3
from zipfile import ZipFile

import pytest

from core.ventas.application.services import SalesService
from core.ventas.domain.errors import ConflictError, StorageError, ValidationError
from core.ventas.domain.models import Item
from core.ventas.infrastructure.migrations import CHECKSUM, DDL


@pytest.fixture
def service(tmp_path):
    db = tmp_path / "isolated.db"
    sqlite3.connect(db).close()
    return SalesService(db, actor="qa-independent", user_id=42, is_admin=True)


def create_csv(path, rows):
    columns = ("sku", "nombre", "tipo", "unidad", "unidad_fisica",
               "precio", "moneda")
    with path.open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(columns)
        writer.writerows(rows)


def test_csv_preview_does_not_write_and_confirmation_is_single_transaction(service, tmp_path):
    source = tmp_path / "catalog.csv"
    create_csv(source, [["QA-001", "Paint", "PRODUCTO", "und", "und", "20", "PEN"]])
    before = service.items()
    preview = service.preview_catalog_csv(source)
    assert preview["errors"] == []
    assert preview["created"] == 1
    assert service.items() == before
    assert service.movements() == []
    assert service.apply_catalog_import(preview) == {"created": 1, "updated": 0, "skipped": 0}
    assert len(service.items()) == 1
    assert service.items()[0]["sku"] == "QA-001"
    assert service.movements() == []
    with pytest.raises(ConflictError):
        service.apply_catalog_import(preview)


def test_csv_rejects_duplicate_sku_and_disallows_partial_apply(service, tmp_path):
    source = tmp_path / "bad.csv"
    create_csv(source, [
        ["DUP-001", "First", "PRODUCTO", "und", "und", "10", "PEN"],
        ["dup-001", "Second", "PRODUCTO", "und", "und", "10", "PEN"],
    ])
    preview = service.preview_catalog_csv(source)
    assert preview["errors"]
    with pytest.raises(ValidationError):
        service.apply_catalog_import(preview)
    assert service.items() == []


def test_csv_preview_conflicts_after_catalog_change(service, tmp_path):
    source = tmp_path / "catalog.csv"
    create_csv(source, [["Q-C", "New", "PRODUCTO", "und", "und", "1", "PEN"]])
    preview = service.preview_catalog_csv(source)
    service.save_item(asdict(Item(
        sku="OTHER", name="Existing", kind="PRODUCTO",
        unit="und", physical_unit="und", price="2", currency="PEN"
    )))
    with pytest.raises(ConflictError):
        service.apply_catalog_import(preview)
    assert {item["sku"] for item in service.items()} == {"OTHER"}


def test_v1_to_v2_migration_keeps_original_schema_checksum(tmp_path):
    db = tmp_path / "v1-only.db"
    with sqlite3.connect(db) as con:
        for statement in DDL:
            con.execute(statement)
        con.execute(
            "INSERT INTO ventas_schema_migrations VALUES (1, ?, ?)",
            ("2026-10-24T00:00:00Z", CHECKSUM),
        )
    service = SalesService(db, actor="qa")
    with service.store.transaction() as repo:
        versions = [(r["version"], r["hash"]) for r in repo.connection.execute(
            "SELECT version,hash FROM ventas_schema_migrations ORDER BY version"
        )]
        tables = {r[0] for r in repo.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert [v for v, _ in versions] == [1, 2]
    assert versions[0][1] == CHECKSUM
    assert {"ventas_fichas", "ventas_fichas_eventos", "ventas_importaciones"} <= tables
    SalesService(db, actor="qa")  # second initialize idempotent
    with service.store.transaction() as repo:
        assert repo.connection.execute(
            "SELECT COUNT(*) FROM ventas_schema_migrations"
        ).fetchone()[0] == 2


def seed_construction(db):
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE proyectos (id INTEGER PRIMARY KEY, nombre TEXT, moneda TEXT, usuario_id INTEGER)")
        con.execute("CREATE TABLE partidas (id INTEGER PRIMARY KEY, proyecto_id INTEGER, item TEXT, descripcion TEXT, unidad TEXT, metrado REAL, precio_unitario REAL, es_titulo INTEGER, rendimiento REAL)")
        con.execute("CREATE TABLE recursos (id INTEGER PRIMARY KEY, codigo TEXT, descripcion TEXT, tipo TEXT, unidad TEXT, precio REAL)")
        con.execute("CREATE TABLE acu_items (id INTEGER PRIMARY KEY, partida_id INTEGER, recurso_id INTEGER, cantidad REAL, cuadrilla REAL, precio REAL)")
        con.execute("CREATE TABLE configuracion (clave TEXT, valor TEXT)")
        con.executemany("INSERT INTO proyectos VALUES (?,?,?,?)", [
            (17, "Obra QA autorizada", "Soles", 42),
            (18, "Obra ajena QA", "Soles", 99),
        ])
        con.execute("INSERT INTO partidas VALUES (17,17,'01','Pintura','m²',120,8.75,0,1)")
        con.execute("INSERT INTO recursos VALUES (1,'R1','Material QA','MAT','L',20)")
        con.execute("INSERT INTO acu_items VALUES (1,17,1,2,0,18)")


def construction_rows(db):
    with sqlite3.connect(db) as con:
        return {
            table: con.execute(f"SELECT * FROM {table}").fetchall()
            for table in ("proyectos", "partidas", "recursos", "acu_items", "configuracion")
        }


def test_construction_adapter_is_readonly_and_sale_price_explicit(tmp_path):
    db = tmp_path / "legacy.db"
    sqlite3.connect(db).close()
    service = SalesService(db, actor="qa", user_id=42, is_admin=False)
    seed_construction(db)
    before = construction_rows(db)
    projects = service.construction_projects()
    assert [p["id"] for p in projects] == [17]
    with pytest.raises(ValidationError):
        service.preview_construction(18, 17)
    snapshot = service.preview_construction(17, 17)
    assert snapshot["source_partida_id"] == 17
    assert snapshot["cost_basis"] == "8.75"
    line = service.line_from_construction(snapshot, "PEN", "15", "120")
    assert line["price"] == "15.000000"
    assert line["cost"] == "8.750000"
    assert line["provenance"]["snapshot"]["source_hash"] == snapshot["source_hash"]
    assert construction_rows(db) == before


def test_datasheet_copy_hash_history_and_package(service, tmp_path):
    record = service.save_item(asdict(Item(
        sku="DOC-QA", name="Material QA", kind="PRODUCTO",
        unit="und", physical_unit="und", price="10", currency="PEN",
    )))
    src = tmp_path / "source.pdf"
    src.write_bytes(b"%PDF-1.4\n% Synthetic QA document\n%%EOF\n")
    inspection = service.inspect_datasheet(src)
    assert service.datasheets(record["id"]) == []
    attached = service.attach_datasheet(record["id"], inspection, "", "DOCUMENTO_APORTADO", "QA-only PDF")
    assert attached["sha256"] == sha256(src.read_bytes()).hexdigest()
    refs = service.datasheets(record["id"])
    assert len(refs) == 1
    assert service.datasheet_status(refs[0]).startswith("DISPONIBLE")
    pkg = tmp_path / "portable.zip"
    result = service.export_sales_package(pkg)
    assert result["complete"] is True
    with ZipFile(pkg) as z:
        manifest = json.loads(z.read("manifest.json"))
        assert manifest["database"]["path"] == "database/presupuestos.db"
        assert any(name.startswith("fichas/") for name in z.namelist())
        assert manifest["excluded"]  # not a complete Construction-assets backup
    service.retire_datasheet(record["id"], refs[0]["id"])
    assert service.datasheets(record["id"]) == []
    assert len(service.datasheets(record["id"], include_retired=True)) == 1


def test_changed_source_blocks_attachment(service, tmp_path):
    record = service.save_item(asdict(Item(
        sku="DOC-CHANGED", name="Material QA", kind="PRODUCTO",
        unit="und", physical_unit="und", price="10", currency="PEN",
    )))
    src = tmp_path / "source.pdf"
    src.write_bytes(b"%PDF-1.4\nSynthetic first content\n")
    inspection = service.inspect_datasheet(src)
    src.write_bytes(b"%PDF-1.4\nChanged after inspection\n")
    with pytest.raises(ValidationError):
        service.attach_datasheet(record["id"], inspection, "", "DOCUMENTO_APORTADO", "QA")
    assert service.datasheets(record["id"]) == []
