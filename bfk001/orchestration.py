"""BFK-001 v3.3.2 — Orchestration (HORS CONTRAT, Section J / Section Q).

Le contrat interdit a ConstructionState de se construire lui-meme : la
composition d'un nouvel etat revient a une fonction d'orchestration exterieure.
Ce module en fournit une, minimale et pure : elle ne decide rien, elle appelle
les autorites dans l'ordre et empile des Tuple.

  recherche (C) -> oracle (P) -> graphe -> etat

Aucune fonction de ce module ne juge la mecanique ni la geometrie.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Tuple

from .connectors import ConnectorTolerance
from .graph import ConstructionGraph
from .oracle import PhysicalBond, evaluate_connector_pair
from .search import PlacedPart, ReferenceSearchApproximation, SearchApproximation
from .spatial import FrozenSpatialSnapshot, ReferenceSpatialIndex, SpatialCandidateIndex
from .state import ConstructionState

__all__ = ["with_part", "without_part", "build_index", "assemble"]


def with_part(
    placed_parts: Mapping[str, PlacedPart],
    part: PlacedPart,
) -> Dict[str, PlacedPart]:
    """Retourne un NOUVEAU mapping ; l'entree n'est jamais mutee."""
    if not isinstance(part, PlacedPart):
        raise TypeError("with_part attend un PlacedPart")
    if part.part_id in placed_parts:
        raise ValueError(f"identifiant deja place : {part.part_id}")
    updated = dict(placed_parts)
    updated[part.part_id] = part
    return updated


def without_part(
    placed_parts: Mapping[str, PlacedPart],
    part_id: str,
) -> Dict[str, PlacedPart]:
    """Retourne un NOUVEAU mapping prive de part_id ; l'entree n'est jamais mutee."""
    updated = dict(placed_parts)
    updated.pop(part_id, None)
    return updated


def build_index(placed_parts: Mapping[str, PlacedPart]) -> ReferenceSpatialIndex:
    index = ReferenceSpatialIndex()
    for part_id, part in placed_parts.items():
        index.insert(part_id, part.aabb)
    return index


def assemble(
    placed_parts: Mapping[str, PlacedPart],
    tolerance: ConnectorTolerance,
    search: Optional[SearchApproximation] = None,
    index: Optional[SpatialCandidateIndex] = None,
) -> ConstructionState:
    """Compose un ConstructionState immuable a partir des pieces placees.

    Chaque candidat produit par la recherche est soumis a l'oracle : seul un
    PhysicalBond emis par celui-ci devient une arete.
    """
    if not isinstance(tolerance, ConnectorTolerance):
        raise TypeError("assemble attend une ConnectorTolerance explicite")

    search = ReferenceSearchApproximation() if search is None else search
    index = build_index(placed_parts) if index is None else index

    bonds_by_edge: Dict[Tuple[str, str], List[PhysicalBond]] = {}
    for id_a, id_b, conn_a, conn_b in search.find_candidate_pairs(
        index, placed_parts, tolerance
    ):
        part_a = placed_parts[id_a]
        part_b = placed_parts[id_b]
        bond = evaluate_connector_pair(
            conn_a, part_a.pose, conn_b, part_b.pose, tolerance
        )
        if bond is None:
            continue
        bonds_by_edge.setdefault((id_a, id_b), []).append(bond)

    graph = ConstructionGraph(
        parts=tuple(
            (part_id, part.aabb, part.connectors)
            for part_id, part in placed_parts.items()
        ),
        edges=tuple(
            (id_a, id_b, tuple(bonds))
            for (id_a, id_b), bonds in sorted(bonds_by_edge.items())
        ),
    )
    snapshot = FrozenSpatialSnapshot(
        tuple(sorted((part_id, part.aabb) for part_id, part in placed_parts.items()))
    )
    return ConstructionState(graph=graph, spatial_snapshot=snapshot)
