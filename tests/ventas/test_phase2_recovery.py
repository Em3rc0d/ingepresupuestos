"""Independent Fase 2 QA: round-trip recovery and transactional safety.

Only creates temporary synthetic SQLite, PNG/PDF-like references, and ZIPs.
A manual, verified ZIP extraction is simulated in a TEMPORARY directory;
the product does not yet contain a restore implementation.
"""
from dataclasses import asdict
from contextlib import closing
from datetime import date
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile
import csv
import json
import shutil
import sqlite3

import pytest

from core.ventas.application.services import SalesService
from core.ventas.domain.errors import ConflictError, StorageError, ValidationError
from core.ventas.domain.models import Item
from core.ventas.infrastructure.repositories import Repository


def make_service(root, admin=True):
    root.mkdir(parents=True, exist_ok=True)
    db = root / "presupuestos.db"
    sqlite3.connect(db).close()
    return SalesService(db, actor="auditor-f2", user_id=101, is_admin=admin)


def item_payload(sku, **extras):
    base = asdict(Item(sku=sku, name="Artículo sintético " + sku, kind="PRODUCTO",
                       unit="und", physical_unit="und", price="5", currency="PEN",
                       tracks_stock=False))
    base.update(extras)
    return base


def make_quote(service, item):
    doc = service.new_document()
    doc["header"].update(customer={"name": "Cliente temporal"}, title="QA de restauración",
                         issuer="Emisor temporal", date=date.today().isoformat())
    line = service.line_from_item(item["id"], "PEN")
    line["tax"] = {"name": "QA tasa cero", "rate": "0", "mode": "EXCLUSIVE"}
    doc["lines"] = [line]
    saved = service.save_draft(doc)
    return service.save_draft(saved, issue=True)


def manual_verified_restore(zip_path, target):
    """QA ONLY: verify archive membership/hash before extraction to temporary dirs."""
    target.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["format"] == "ingepresupuestos-ventas-package/1"
        assert manifest["complete"] is True
        expected = [manifest["database"]] + manifest["files"]
        for entry in expected:
            source = entry["path"]
            assert not source.startswith("/") and ".." not in Path(source).parts
            payload = archive.read(source)
            assert len(payload) == entry["bytes"]
            assert sha256(payload).hexdigest() == entry["sha256"]
            if source.startswith("database/"):
                destination = target / "presupuestos.db"
            else:
                assert source.startswith("fichas/")
                destination = target / "ventas" / "fichas" / Path(source).name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        assert {x.filename for x in archive.infolist()} == (
            {"manifest.json"} | {entry["path"] for entry in expected}
        )
    return target / "presupuestos.db"


def test_zip_restore_roundtrip_preserves_construction_sales_and_historical_files(tmp_path):
    original = make_service(tmp_path / "original")
    with closing(sqlite3.connect(original.store.path)) as db:
        db.execute("CREATE TABLE proyectos (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL)")
        db.execute("INSERT INTO proyectos VALUES (14, 'Obra sintética: mantener')")
        db.commit()
    item = original.save_item(item_payload("QA-ZIP-1"))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n% Synthetic QA-only portable attachment\n%%EOF\n")
    inspection = original.inspect_datasheet(source)
    original.attach_datasheet(item["id"], inspection, "", "DOCUMENTO_APORTADO",
                              "Documento sintético; sin validar ingeniería")
    issued = make_quote(original, item)
    reference = original.datasheets(item["id"])[0]
    original.retire_datasheet(item["id"], reference["id"])
    archive = tmp_path / "portable.zip"
    info = original.export_sales_package(archive)
    assert info["complete"] and info["files"] == 1

    # Destroy ONLY temporary original source data; the portable ZIP is the oracle.
    original.store.path.unlink()
    shutil.rmtree(tmp_path / "original" / "ventas")
    restored = tmp_path / "restored"
    db_path = manual_verified_restore(archive, restored)
    check = SalesService(db_path, actor="qa-restored", user_id=101, is_admin=True)
    recovered = check.open_document(issued["id"], issued["revision_id"])
    assert recovered["hash"] == issued["hash"]
    assert recovered["lines"] == issued["lines"]
    assert recovered["totals"] == issued["totals"]
    assert len(check.datasheets(item["id"], include_retired=True)) == 1
    old = check.datasheets(item["id"], include_retired=True)[0]
    assert check.datasheet_status(old).startswith("DISPONIBLE")
    with closing(sqlite3.connect(db_path)) as con:
        assert con.execute("SELECT nombre FROM proyectos WHERE id=14").fetchone() == (
            "Obra sintética: mantener",
        )
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    assert "Otros archivos externos de Construcción" in json.loads(
        ZipFile(archive).read("manifest.json")
    )["excluded"][0]


def test_corrupted_archive_member_fails_manual_verified_restore(tmp_path):
    service = make_service(tmp_path / "data")
    archive = tmp_path / "original.zip"
    service.export_sales_package(archive)
    broken = tmp_path / "broken.zip"
    with ZipFile(archive) as good, ZipFile(broken, "w") as damaged:
        for name in good.namelist():
            blob = good.read(name)
            if name == "database/presupuestos.db":
                blob = blob + b"TAMPERED"
            damaged.writestr(name, blob)
    with pytest.raises(AssertionError):
        manual_verified_restore(broken, tmp_path / "restored")


def test_missing_managed_file_blocks_backup_without_replacing_previous_zip(tmp_path):
    service = make_service(tmp_path / "data")
    item = service.save_item(item_payload("QA-ZIP-2"))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n% Synthetic QA second file\n%%EOF\n")
    inspected = service.inspect_datasheet(source)
    reference = service.attach_datasheet(item["id"], inspected, "", "DOCUMENTO_APORTADO", "QA")
    output = tmp_path / "existing.zip"
    output.write_bytes(b"PREVIOUS BACKUP SENTINEL")
    managed = service.datasheet_store().path(reference["sha256"], reference["mime"])
    managed.unlink()
    with pytest.raises(StorageError):
        service.export_sales_package(output)
    assert output.read_bytes() == b"PREVIOUS BACKUP SENTINEL"
    assert service.datasheet_status(reference).startswith("ARCHIVO NO DISPONIBLE")


def test_csv_partial_failure_rolls_back_every_new_article(tmp_path, monkeypatch):
    service = make_service(tmp_path / "data")
    csv_path = tmp_path / "inventory.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["sku", "nombre", "tipo", "unidad", "unidad_fisica", "precio", "moneda"])
        writer.writerow(["ROLL-1", "Tornillo á", "PRODUCTO", "und", "und", "3", "PEN"])
        writer.writerow(["ROLL-2", "Pieza B", "PRODUCTO", "und", "und", "4", "PEN"])
    preview = service.preview_catalog_csv(csv_path)
    assert preview["created"] == 2 and not preview["errors"]
    original_save = Repository.save_item
    called = {"count": 0}

    def save_with_forced_failure(self, item, actor, stamp):
        called["count"] += 1
        if called["count"] == 2:
            raise RuntimeError("QA injected failure after first write")
        return original_save(self, item, actor, stamp)

    monkeypatch.setattr(Repository, "save_item", save_with_forced_failure)
    with pytest.raises(RuntimeError, match="QA injected"):
        service.apply_catalog_import(preview)
    assert service.items() == []
    with service.store.transaction() as repo:
        count = repo.connection.execute("SELECT COUNT(*) FROM ventas_importaciones").fetchone()[0]
        count_prices = repo.connection.execute("SELECT COUNT(*) FROM ventas_precios").fetchone()[0]
    assert count == 0 and count_prices == 0


def test_foreign_key_violation_does_not_partial_mutate_sales_database(tmp_path):
    service = make_service(tmp_path / "data")
    with pytest.raises((ConflictError, StorageError)):
        with service.store.transaction(write=True) as repo:
            repo.connection.execute(
                "INSERT INTO ventas_lineas(id,revision_id,posicion,item_id,data_json,importe_json)"
                " VALUES ('QA', 'UNKNOWN_REVISION', 0, NULL, '{}', '{}')"
            )
    with service.store.transaction() as repo:
        assert repo.connection.execute("SELECT COUNT(*) FROM ventas_lineas").fetchone()[0] == 0
