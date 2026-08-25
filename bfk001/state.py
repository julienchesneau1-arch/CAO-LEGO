"""BFK-001 v3.3.2 — Section J : ConstructionState.

Pur conteneur immuable (decision A.5). Aucune methode de mutation, aucune
reference vers un objet mutable : la construction d'un nouvel etat releve d'une
fonction d'orchestration exterieure au contrat.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, runtime_checkable

from .geometry import AABB
from .graph import ConstructionGraph

__all__ = ["SpatialSnapshot", "ConstructionState"]


@runtime_checkable
class SpatialSnapshot(Protocol):
    """Vue de lecture seule d'un index spatial : query uniquement."""

    def query(self, region: AABB) -> Iterable[str]:
        """Meme semantique que SpatialCandidateIndex.query."""
        ...


@dataclass(frozen=True)
class ConstructionState:
    """Pur conteneur immuable. Ne calcule pas, ne stocke que."""

    graph: ConstructionGraph
    spatial_snapshot: SpatialSnapshot

    def __post_init__(self) -> None:
        if not isinstance(self.graph, ConstructionGraph):
            raise TypeError("ConstructionState.graph doit etre un ConstructionGraph")
        if not callable(getattr(self.spatial_snapshot, "query", None)):
            raise TypeError(
                "ConstructionState.spatial_snapshot doit implementer query(region)"
            )
        for mutator in ("insert", "remove"):
            if hasattr(self.spatial_snapshot, mutator):
                raise TypeError(
                    "ConstructionState.spatial_snapshot doit etre query-only : "
                    f"'{mutator}' expose un index mutable (Section J.1)"
                )
