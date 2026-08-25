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
    "GridSpatialIndex",
    "FrozenSpatialSnapshot",
]

DEFAULT_CELL_SIZE_LDU = 40
"""Cote de cellule par defaut : 40 LDU = 2 tenons = l'emprise d'une brique 2x2.

Une piece courante occupe donc 1 a 8 cellules. Un choix beaucoup plus petit
multiplie les cellules par piece ; beaucoup plus grand ramene au balayage
lineaire.
"""


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
        return FrozenSpatialSnapshot(
            tuple(sorted(self._entries.items(), key=lambda entry: entry[0]))
        )


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


class GridSpatialIndex:
    """Grille uniforme : accelerateur spatial reel, a requete EXHAUSTIVE.

    Une piece est enregistree dans toutes les cellules que son AABB recouvre.
    Deux AABB non disjoints partagent au moins un point, donc au moins une
    cellule : interroger la grille avec l'AABB d'une piece retourne donc
    NECESSAIREMENT toutes les pieces qui la touchent ou la traversent. La
    requete est un sur-ensemble exact des voisins — jamais un filtre approximatif.

    C'est ce qui autorise a s'en servir pour elaguer H2 sans affaiblir
    l'invariant : les paires ecartees sont, par construction, DISJOINT, donc
    CLEAR (Section F.4).

    Frontiere d'autorite inchangee (Section G) : la grille dit « regarde ici ».
    Elle ne dit jamais « connectes ».
    """

    def __init__(self, cell_size_ldu: int = DEFAULT_CELL_SIZE_LDU) -> None:
        if isinstance(cell_size_ldu, bool) or not isinstance(cell_size_ldu, int):
            raise TypeError("cell_size_ldu doit etre un entier")
        if cell_size_ldu <= 0:
            raise ValueError("cell_size_ldu doit etre strictement positif")
        self._cell_size = cell_size_ldu
        self._cells: Dict[Tuple[int, int, int], set] = {}
        self._entries: Dict[str, AABB] = {}

    def _cells_of(self, aabb: AABB) -> Iterable[Tuple[int, int, int]]:
        size = self._cell_size
        for cx in range(aabb.min.x // size, aabb.max.x // size + 1):
            for cy in range(aabb.min.y // size, aabb.max.y // size + 1):
                for cz in range(aabb.min.z // size, aabb.max.z // size + 1):
                    yield (cx, cy, cz)

    def query(self, region: AABB) -> Iterable[str]:
        """Sur-ensemble exhaustif des pieces non disjointes de la region."""
        if not isinstance(region, AABB):
            raise TypeError("query attend un AABB")
        found: set = set()
        for cell in self._cells_of(region):
            found.update(self._cells.get(cell, ()))
        return tuple(sorted(found))

    def insert(self, part_id: str, aabb: AABB) -> None:
        if not isinstance(part_id, str):
            raise TypeError("part_id doit etre une chaine")
        if not isinstance(aabb, AABB):
            raise TypeError("insert attend un AABB")
        if part_id in self._entries:
            self.remove(part_id)
        self._entries[part_id] = aabb
        for cell in self._cells_of(aabb):
            self._cells.setdefault(cell, set()).add(part_id)

    def remove(self, part_id: str) -> None:
        aabb = self._entries.pop(part_id, None)
        if aabb is None:
            return
        for cell in self._cells_of(aabb):
            bucket = self._cells.get(cell)
            if bucket is None:
                continue
            bucket.discard(part_id)
            if not bucket:
                del self._cells[cell]

    def snapshot(self) -> "FrozenSpatialSnapshot":
        return FrozenSpatialSnapshot(
            tuple(sorted(self._entries.items(), key=lambda entry: entry[0]))
        )
