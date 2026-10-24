"""Shared pytest guard: a test must never block.

Offscreen, a modal QMessageBox waits forever for a click that never comes, and
the whole run hangs with no clue.  Every static message box raises instead,
naming the dialog, so the test fails at once and says why.  A test that
expects a message box patches it itself (monkeypatch wins over this).
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def _no_modal(kind):
    def _raise(parent=None, title='', text='', *args, **kwargs):
        raise RuntimeError(f"modal QMessageBox.{kind} would block the test: "
                           f"{title!r}: {str(text)[:200]!r}")
    return staticmethod(_raise)


def pytest_configure(config):
    from PySide6.QtWidgets import QMessageBox
    for kind in ('information', 'warning', 'critical', 'question'):
        setattr(QMessageBox, kind, _no_modal(kind))



def pytest_collection_finish(session):
    """Reproduce la inicialización de Inter que main.py hace antes de dibujar.

    Sin ella, el runner Windows usa una fuente fallback y falla en anchuras y
    sangrías que no corresponden a la UI real.
    """
    from pathlib import Path

    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    fonts = Path(__file__).resolve().parents[1] / "resources" / "fonts"
    for name in ("Inter.ttf", "Inter-Italic.ttf", "Inter-Bold.ttf", "Inter-BoldItalic.ttf"):
        f = fonts / name
        if f.exists():
            QFontDatabase.addApplicationFont(str(f))
    app.setFont(QFont("Inter", 10))


def pytest_sessionfinish(session, exitstatus):
    """No destruir explícitamente widgets compartidos al finalizar los tests.

    La eliminación directa de QObjects bajo Qt genera 'pure virtual method
    called'. Solo detener tooltips y procesar eventos ya publicados.
    """
    from PySide6.QtWidgets import QApplication, QToolTip

    app = QApplication.instance()
    if app is not None:
        QToolTip.hideText()
        app.processEvents()
