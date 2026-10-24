"""Independent UI/export smoke checks on synthetic data. Never touches user DB."""
from dataclasses import asdict
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sqlite3

from core.ventas.application.services import SalesService
from core.ventas.domain.models import QuoteLine
from core.ventas.infrastructure.exporters import export_pdf, export_xlsx


def _service_and_issued(db):
    sqlite3.connect(db).close()
    service = SalesService(db, actor="QA")
    doc = service.new_document()
    doc["header"].update({
        "customer": {"name": "Cliente QA"},
        "issuer": "Emisor QA",
        "title": "Cotización sintética QA",
        "date": date.today().isoformat(),
    })
    doc["lines"] = [asdict(QuoteLine(
        description="Material sintético",
        quantity="3", unit="und", price="12.50",
        tax={"name": "Tasa de ensayo", "mode": "EXCLUSIVE", "rate": "0"},
    ))]
    saved = service.save_draft(doc)
    return service, service.save_draft(saved, issue=True)


def test_export_issued_pdf_and_xlsx_from_same_snapshot(tmp_path):
    from openpyxl import load_workbook
    from pypdf import PdfReader

    service, issued = _service_and_issued(tmp_path / "sales-export.db")
    root = Path(__file__).resolve().parents[2]
    pdf, xlsx = tmp_path / "cotizacion.pdf", tmp_path / "cotizacion.xlsx"
    export_pdf(issued, pdf, root / "resources" / "fonts")
    export_xlsx(issued, xlsx)
    assert pdf.exists() and pdf.stat().st_size > 300
    assert xlsx.exists() and xlsx.stat().st_size > 300
    reader = PdfReader(pdf)
    assert len(reader.pages) >= 1
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert issued["number"] in text
    assert issued["totals"]["total"] in text
    wb = load_workbook(xlsx, read_only=True, data_only=True)
    cells = [str(cell) for row in wb.active.values for cell in row if cell is not None]
    assert issued["number"] in cells
    assert issued["totals"]["total"] in cells
    wb.close()


def test_sales_workspace_constructs_and_shows_offscreen(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication
    import core.config as config
    from views.ventas.shell import SalesView

    path = tmp_path / "sales-ui.db"
    sqlite3.connect(path).close()
    monkeypatch.setattr(config, "DB_PATH", path)
    app = QApplication.instance() or QApplication([])
    user = SimpleNamespace(id=101, username="qa", nombre="QA", es_invitado=False)
    view = SalesView(user)
    view.show()
    app.processEvents()
    assert view.tabs.count() == 5
    assert view.isVisible()
    view.close()
    view.deleteLater()
    QCoreApplication.sendPostedEvents(None, 0)
    app.processEvents()
