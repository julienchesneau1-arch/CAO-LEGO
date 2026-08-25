"""BFK-001 v3.3.2 — Section G : SpatialCandidateIndex, et vue de lecture seule.

Frontiere d'autorite : un index peut dire "regarde ici". Il ne peut JAMAIS dire
"connectes" ou "pas connectes". L'obligation H1 incombe a SearchApproximation,
pas a l'index (note Section G).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Protocol, Tuple

from .geometry import AABB, GeometricRelation, geometric_relation

__all__ = [
    "SpatialCandidateIndex",
    "ReferenceSpatialIndex",
    "FrozenSpatialSnapshot",
]


class SpatialCandidateIndex(Protocol):
    """Accelerateur spatial mutable."""

    def query(self, region: AABB) -> Iterable[str]:
        """Retourne des identifiants candidats. AUCUNE garantie d'exhaustivite."""
        ...

    def insert(self, part_id: str, aabb: AABB) -> None:
        """Indexe une nouvelle piece."""
        ...

    def remove(self, part_id: str) -> None:
        """Desindexe une piece."""
        ...


class ReferenceSpatialIndex:
    """Index de reference : balayage lineaire exact, sans structure acceleratrice.

    Hors contrat au sens strict (le contrat ne definit qu'un Protocol), mais
    necessaire a l'orchestration et aux tests. Conserve volontairement trivial :
    aucune heuristique, aucun elagage cache.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, AABB] = {}

    def query(self, region: AABB) -> Iterable[str]:
        """Tout identifiant dont l'AABB n'est pas DISJOINT de la region."""
        if not isinstance(region, AABB):
            raise TypeError("query attend un AABB")
        return tuple(
            part_id
            for part_id, aabb in self._entries.items()
            if geometric_relation(aabb, region) is not GeometricRelation.DISJOINT
        )

    def insert(self, part_id: str, aabb: AABB) -> None:
        if not isinstance(part_id, str):
            raise TypeError("part_id doit etre une chaine")
        if not isinstance(aabb, AABB):
            raise TypeError("insert attend un AABB")
        self._entries[part_id] = aabb

    def remove(self, part_id: str) -> None:
        self._entries.pop(part_id, None)

    def snapshot(self) -> "FrozenSpatialSnapshot":
        """Vue de lecture seule, detachee de l'index (value object)."""
        return FrozenSpatialSnapshot(tuple(sorted(self._entries.items())))


@dataclass(frozen=True)
class FrozenSpatialSnapshot:
    """Implementation du protocole SpatialSnapshot (Section J.1) : query seul.

    Value object immuable : aucune methode insert/remove, aucune reference vers
    un index mutable.
    """

    entries: Tuple[Tuple[str, AABB], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.entries, tuple):
            raise TypeError("FrozenSpatialSnapshot.entries doit etre un Tuple")
        for entry in self.entries:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise TypeError("chaque entree est un Tuple[str, AABB]")
            part_id, aabb = entry
            if not isinstance(part_id, str) or not isinstance(aabb, AABB):
                raise TypeError("chaque entree est un Tuple[str, AABB]")

    def query(self, region: AABB) -> Iterable[str]:
        if not isinstance(region, AABB):
            raise TypeError("query attend un AABB")
        return tuple(
            part_id
            for part_id, aabb in self.entries
            if geometric_relation(aabb, region) is not GeometricRelation.DISJOINT
        )
