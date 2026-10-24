# SPDX-License-Identifier: GPL-3.0-or-later
class SalesError(Exception):
    """Error presentable sin filtrar SQL o datos privados."""


class ValidationError(SalesError):
    pass


class ConflictError(SalesError):
    pass


class StorageError(SalesError):
    pass
