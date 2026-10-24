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


# Los tests usan QApplication y QWidget en import-time; algunos mantienen
# timers/eventFilters vivos. No dejar que el destructor de Python los libere
# con el runtime de Qt ya en desmontaje.
def pytest_sessionfinish(session, exitstatus):
    import pytest
    try:
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtWidgets import QApplication, QToolTip
        from shiboken6 import isValid
    except ImportError:
        return
    app = QApplication.instance()
    if app is None:
        return
    try:
        QToolTip.hideText()
        for widget in list(app.topLevelWidgets()):
            if isValid(widget):
                widget.close()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
    except RuntimeError as exc:
        # La limpieza no debe ocultar un problema del framework.
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        print(f"ERROR: teardown Qt inválido: {exc}", flush=True)
