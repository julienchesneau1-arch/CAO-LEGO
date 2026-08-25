"""BFK-001 v3.3.2 — Section H : SearchApproximation.

Responsabilite : produire l'ensemble C des paires a soumettre a l'oracle.
AUCUNE garantie mecanique sur les paires retournees. Ce module ne connait pas
PhysicalBond (verification d'acyclicite, Section O) : il ne peut donc pas
affirmer qu'une paire est connectee.

Obligation H1 : P inclus dans C, pour tout etat de construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol, Tuple

from .connectors import Connector, ConnectorTolerance, _compatible
from .geometry import AABB, Pose
from .spatial import SpatialCandidateIndex

__all__ = [
    "PlacedPart",
    "SearchApproximation",
    "ReferenceSearchApproximation",
]


# =============================================================================
# Section H.1 — PlacedPart
# =============================================================================


@dataclass(frozen=True)
class PlacedPart:
    """Value object de reference spatiale. Aucune autorite mecanique.

    `aabb` est l'AABB MONDE pre-calcule ; `connectors` reste en coordonnees
    LOCALES (la pose porte le passage au monde).
    """

    part_id: str
    pose: Pose
    aabb: AABB
    connectors: Tuple[Connector, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.part_id, str) or not self.part_id:
            raise TypeError("PlacedPart.part_id doit etre une chaine non vide")
        if not isinstance(self.aabb, AABB):
            raise TypeError("PlacedPart.aabb doit etre un AABB monde")
        if not isinstance(self.connectors, tuple):
            raise TypeError(
                "PlacedPart.connectors doit etre un Tuple[Connector, ...], jamais une List"
            )
        for connector in self.connectors:
            if not isinstance(connector, Connector):
                raise TypeError("PlacedPart.connectors ne contient que des Connector")


# =============================================================================
# Section H.2 — Protocole SearchApproximation
# =============================================================================


class SearchApproximation(Protocol):
    """Porte l'obligation H1 (P inclus dans C)."""

    def find_candidate_pairs(
        self,
        index: SpatialCandidateIndex,
        placed_parts: Mapping[str, PlacedPart],
        tolerance: ConnectorTolerance,
    ) -> Iterable[Tuple[str, str, Connector, Connector]]:
        """Retourne des tuples (part_id_a, part_id_b, connector_a, connector_b)."""
        ...


# =============================================================================
# Section H.3 — Implementation de reference O(n^2)
# =============================================================================


class ReferenceSearchApproximation:
    """Implementation de reference O(n^2) : triviale, exhaustive, lente, demontrable.

    Oracle de completude physique (decision A.4) : tout index rapide futur est
    valide contre elle, au sens P inclus dans C_fast — et NON C_ref inclus dans
    C_fast (Section H.4).
    """

    def find_candidate_pairs(
        self,
        index: SpatialCandidateIndex,
        placed_parts: Mapping[str, PlacedPart],
        tolerance: ConnectorTolerance,
    ) -> Iterable[Tuple[str, str, Connector, Connector]]:
        """Ignore l'index et la tolerance : aucun elagage, aucune heuristique."""
        for id_a, part_a in placed_parts.items():
            for id_b, part_b in placed_parts.items():
                if id_a >= id_b:
                    continue
                for conn_a in part_a.connectors:
                    for conn_b in part_b.connectors:
                        if not _compatible(conn_a.ctype, conn_b.ctype):
                            continue
                        yield (id_a, id_b, conn_a, conn_b)
