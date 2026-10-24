"""Independent QA of Astra's sales branch. Synthetic temporary data only.

This file is deliberately NOT committed to Astra's implementation branch.
"""
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3

import pytest

from core.ventas.application.services import SalesService
from core.ventas.domain.errors import ConflictError, ValidationError
from core.ventas.domain.formulas import calculate as quantity
from core.ventas.domain.models import Item, QuoteLine
from core.ventas.domain.money import Money, rounded
from core.ventas.domain.pricing import calculate as pricing
from core.ventas.domain.quantity import UnitRegistry


@pytest.fixture()
def service():
    with TemporaryDirectory(prefix="sales-qa-") as temp:
        db = Path(temp) / "synthetic-sales.db"
        sqlite3.connect(db).close()
        yield SalesService(db, actor="qa-independent")


def quote_document(service, lines):
    doc = service.new_document()
    doc["header"].update({
        "customer": {"name": "Cliente sintético QA"},
        "title": "Cotización QA",
        "issuer": "Emisor sintético QA",
        "date": date.today().isoformat(),
    })
    doc["lines"] = lines
    return doc


def taxable_line(price="10", qty="3"):
    return asdict(QuoteLine(
        description="Artículo de prueba", quantity=qty, unit="und", price=price,
        tax={"name": "Cero explícito QA", "rate": "0", "mode": "EXCLUSIVE"},
    ))


def test_decimal_rejects_float_and_rounds():
    with pytest.raises(ValidationError):
        Money(10.2, "PEN")
    assert str(rounded(Decimal("2.345"), "PEN")) == "2.35"


def test_quantity_conversion_rejects_dimension_mismatch():
    assert UnitRegistry.convert("100", "cm", "m") == Decimal("1.000000")
    with pytest.raises(ValidationError):
        UnitRegistry.convert("5", "kg", "L")


def test_coverage_to_closed_packaging():
    result = quantity("COBERTURA", {
        "area": "120", "area_unit": "m2", "coats": "2",
        "coverage": "8", "extra_percent": "10",
        "presentation_size": "4", "presentation_unit": "L",
        "closed_presentation": True, "source": "Synthetic QA input",
    }, "envase")
    assert Decimal(result["required"]) == 33
    assert Decimal(result["quantity"]) == 9
    assert Decimal(result["sold_physical"]) == 36
    assert Decimal(result["remainder"]) == 3


def test_money_quotations_have_explicit_tax():
    result = pricing([QuoteLine(
        description="A", quantity="3", unit="und", price="10",
        tax={"name": "QA", "rate": "0", "mode": "EXCLUSIVE"},
    )], "PEN", {"kind": "PERCENT", "value": "0"})
    assert Decimal(result["total"]) == 30
    assert result["tax_configured"] is True


def test_bootstrap_only_adds_sales_tables_to_empty_database(service):
    with service.store.transaction() as repo:
        names = {row[0] for row in repo.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert "ventas_cotizaciones" in names
    assert "ventas_movimientos" in names
    assert "proyectos" not in names


def test_draft_save_open_issue_and_revision_immutability(service):
    new = quote_document(service, [taxable_line()])
    saved = service.save_draft(new)
    assert saved["number"].startswith("COT-")
    assert Decimal(saved["totals"]["total"]) == 30
    assert saved["revision_state"] == "BORRADOR"

    issued = service.save_draft(saved, issue=True)
    assert issued["revision_state"] == "EMITIDA"
    assert issued["hash"]
    old = service.open_document(issued["id"], issued["revision_id"])
    assert old["lines"] == issued["lines"]

    with pytest.raises(ConflictError) as exc:
        # A stale emitted revision may not be saved in place.
        service.save_draft(issued)
    assert exc.value is not None

    revision = service.new_revision(issued["id"], issued["token"])
    assert revision["revision_state"] == "BORRADOR"
    assert revision["version"] == 2
    revision["lines"][0]["price"] = "20"
    updated = service.save_draft(revision)
    assert Decimal(updated["totals"]["total"]) == 60
    unchanged = service.open_document(issued["id"], issued["revision_id"])
    assert Decimal(unchanged["totals"]["total"]) == 30


def test_inventory_moves_only_by_explicit_movement(service):
    item = service.save_item(asdict(Item(
        sku="QA-PAINT-4L", name="Pintura sintética", kind="PRODUCTO",
        unit="envase", physical_unit="L", price="21", currency="PEN",
        tracks_stock=True,
    )))
    service.register_movement(item["id"], "ENTRADA", "6", date.today().isoformat(), "Saldo inicial QA")
    before = service.movements(item["id"])
    assert len(before) == 1
    assert Decimal(service.inventory()[0]["available"]) == 6

    line = service.line_from_item(item["id"], "PEN")
    line["quantity"] = "9"
    doc = quote_document(service, [line])
    saved = service.save_draft(doc)
    assert "faltante 3" in " ".join(service.stock_warnings(saved["lines"]))
    # Quote edit/issue must not write inventory movements.
    assert service.movements(item["id"]) == before
    with pytest.raises(ValidationError):
        service.register_movement(item["id"], "SALIDA", "7", date.today().isoformat(), "Overdraw")
    assert service.movements(item["id"]) == before


def test_failsafe_on_unconfigured_tax(service):
    doc = quote_document(service, [asdict(QuoteLine(description="Sin tasa", quantity="1", unit="und", price="4"))])
    saved = service.save_draft(doc)
    with pytest.raises(ValidationError):
        service.save_draft(saved, issue=True)


def test_legacy_construction_schema_not_modified_by_sales(tmp_path):
    path = tmp_path / "isolated-existing.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE proyectos(id INTEGER PRIMARY KEY, nombre TEXT NOT NULL)")
    con.execute("INSERT INTO proyectos(id,nombre) VALUES (17,'Obra de control')")
    con.commit()
    con.close()
    service = SalesService(path, actor="qa")
    service.save_draft(quote_document(service, [taxable_line()]))
    con = sqlite3.connect(path)
    assert con.execute("SELECT id,nombre FROM proyectos").fetchall() == [(17, "Obra de control")]
    con.close()
