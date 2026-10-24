# SPDX-License-Identifier: GPL-3.0-or-later
"""Future read-only boundary. Deliberately NOT connected to sales UI in v1."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ConstructionEstimateSnapshot:
    source_project_id: int
    source_partida_id: int
    source_hash: str
    captured_at: str
    source_version: str
    description: str
    quantity: str
    unit: str
    cost_basis: str | None
    cost_currency: str | None


class ConstructionSnapshotReader(Protocol):
    """Pending: implementation and non-mutation audit; never set sale price from cost."""
    def read_partida(self, project_id: int, partida_id: int) -> ConstructionEstimateSnapshot: ...
