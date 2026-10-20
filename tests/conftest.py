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
