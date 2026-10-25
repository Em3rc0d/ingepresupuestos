# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded file tasks outside the GUI thread; no daemon threads or forced termination."""
from PySide6.QtCore import QThread, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from core.ventas.domain.errors import SalesError
from utils.i18n import tr
from .common import DirtyDialog

_RUNNING = set()


class FileTask(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, job):
        super().__init__()
        self.job = job

    def run(self):
        try:
            result = self.job()
        except (SalesError, OSError, ValueError) as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit(tr('No se pudo completar la operación. No se confirma ningún resultado; revise el respaldo antes de reintentar.'))
        else:
            self.succeeded.emit(result)
        finally:
            self.job = None


class AsyncDialog(DirtyDialog):
    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.busy = False
        self._on_result = None

    def start(self, job, on_result):
        if self.busy:
            return
        self.busy = True
        self._on_result = on_result
        self.body.setEnabled(False)
        worker = FileTask(job)
        _RUNNING.add(worker)
        worker.succeeded.connect(self._success)
        worker.failed.connect(self._failure)
        worker.finished.connect(lambda task=worker: _RUNNING.discard(task))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    @Slot(object)
    def _success(self, result):
        self.busy = False
        self.body.setEnabled(True)
        callback = self._on_result
        self._on_result = None
        if callback:
            callback(result)

    @Slot(str)
    def _failure(self, message):
        self.busy = False
        self.body.setEnabled(True)
        self._on_result = None
        QMessageBox.warning(self, tr('Cotizaciones de Ventas'), message)

    def confirm_discard(self):
        if self.busy:
            QMessageBox.information(self, tr('Operación en curso'), tr('Espere a que termine la lectura o el guardado antes de cerrar.'))
            return False
        return super().confirm_discard()
