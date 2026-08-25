"""BFK-001 v3.3.2 — Orchestration (HORS CONTRAT, Section J / Section Q).

Le contrat interdit a ConstructionState de se construire lui-meme : la
composition d'un nouvel etat revient a une fonction d'orchestration exterieure.
Ce module en fournit une, minimale et pure : elle ne decide rien, elle appelle
les autorites dans l'ordre et empile des Tuple.

  recherche (C) -> oracle (P) -> graphe -> etat

Aucune fonction de ce module ne juge la mecanique ni la geometrie.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

from .collision import CollisionGeometry, CollisionStatus, collide
from .connectors import ConnectorTolerance
from .foundation import FoundationCheck, check_foundation
from .graph import ConstructionGraph
from .oracle import PhysicalBond, evaluate_connector_pair
from .search import PlacedPart, ReferenceSearchApproximation, SearchApproximation
from .spatial import FrozenSpatialSnapshot, ReferenceSpatialIndex, SpatialCandidateIndex
from .state import ConstructionState

__all__ = [
    "with_part",
    "without_part",
    "build_index",
    "assemble",
    "add_part",
    "remove_part",
    "PlacementVerdict",
    "evaluate_placement",
]


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


def _snapshot_of(placed_parts: Mapping[str, PlacedPart]) -> FrozenSpatialSnapshot:
    return FrozenSpatialSnapshot(
        tuple(sorted((part_id, part.aabb) for part_id, part in placed_parts.items()))
    )


def _bonds_involving(
    part_id: str,
    placed_parts: Mapping[str, PlacedPart],
    tolerance: ConnectorTolerance,
    search: SearchApproximation,
    index: SpatialCandidateIndex,
) -> Dict[Tuple[str, str], List[PhysicalBond]]:
    """Bonds emis par l'oracle entre part_id et le reste de l'assemblage.

    Completude : H1 garantit que la recherche produit tout bond valide de
    l'etat ; filtrer sur les paires touchant part_id ne peut donc omettre
    aucune liaison de cette piece.
    """
    bonds_by_edge: Dict[Tuple[str, str], List[PhysicalBond]] = {}
    for id_a, id_b, conn_a, conn_b in search.find_candidate_pairs(
        index, placed_parts, tolerance
    ):
        if part_id not in (id_a, id_b):
            continue
        bond = evaluate_connector_pair(
            conn_a,
            placed_parts[id_a].pose,
            conn_b,
            placed_parts[id_b].pose,
            tolerance,
        )
        if bond is None:
            continue
        bonds_by_edge.setdefault((id_a, id_b), []).append(bond)
    return bonds_by_edge


def add_part(
    state: ConstructionState,
    placed_parts: Mapping[str, PlacedPart],
    part: PlacedPart,
    tolerance: ConnectorTolerance,
    search: Optional[SearchApproximation] = None,
    index: Optional[SpatialCandidateIndex] = None,
) -> Tuple[ConstructionState, Dict[str, PlacedPart]]:
    """Pose incrementale : retourne (nouvel etat, nouveau mapping).

    Seules les liaisons de la piece ajoutee sont evaluees. Les aretes
    existantes sont reprises PAR REFERENCE : les PhysicalBond deja emis
    conservent leur identite, si bien qu'un audit ne voit pas defiler de
    nouvelles liaisons a chaque pose. C'est ce qui rend une trace de
    construction lisible.

    Aucune mutation : l'etat et le mapping d'entree sortent intacts.
    """
    updated_parts = with_part(placed_parts, part)
    search = ReferenceSearchApproximation() if search is None else search
    index = build_index(updated_parts) if index is None else index

    new_bonds = _bonds_involving(part.part_id, updated_parts, tolerance, search, index)
    edges = dict(
        ((id_a, id_b), bonds) for id_a, id_b, bonds in state.graph.edges
    )
    for edge, bonds in new_bonds.items():
        edges[edge] = tuple(bonds)

    graph = ConstructionGraph(
        parts=tuple(
            (part_id, placed.aabb, placed.connectors)
            for part_id, placed in updated_parts.items()
        ),
        edges=tuple(
            (id_a, id_b, tuple(bonds))
            for (id_a, id_b), bonds in sorted(edges.items())
        ),
    )
    return (
        ConstructionState(graph=graph, spatial_snapshot=_snapshot_of(updated_parts)),
        updated_parts,
    )


def remove_part(
    state: ConstructionState,
    placed_parts: Mapping[str, PlacedPart],
    part_id: str,
) -> Tuple[ConstructionState, Dict[str, PlacedPart]]:
    """Retrait incremental : retourne (nouvel etat, nouveau mapping).

    Les liaisons des autres pieces sont conservees par reference — retirer une
    piece ne peut pas creer de bond, seulement en supprimer. Rien n'est
    re-evalue, donc rien ne peut deriver.
    """
    if part_id not in placed_parts:
        raise KeyError(f"piece absente de l'assemblage : {part_id}")
    updated_parts = without_part(placed_parts, part_id)

    graph = ConstructionGraph(
        parts=tuple(
            (identifier, placed.aabb, placed.connectors)
            for identifier, placed in updated_parts.items()
        ),
        edges=tuple(
            (id_a, id_b, bonds)
            for id_a, id_b, bonds in state.graph.edges
            if part_id not in (id_a, id_b)
        ),
    )
    return (
        ConstructionState(graph=graph, spatial_snapshot=_snapshot_of(updated_parts)),
        updated_parts,
    )


@dataclass(frozen=True)
class PlacementVerdict:
    """Reponse a la question que pose reellement un logiciel de CAO :
    « puis-je poser cette piece ici ? »

    Le verdict n'invente aucune regle. Il applique a la piece candidate les
    invariants HARD deja votes :
      - H2 : aucune PENETRATION avec une piece existante ;
      - H6 : la piece ne passe pas sous le plan de fondation ;
      - H4 : la piece est fondee, ou reliee par au moins un bond.
    Chaque composante est produite par son autorite : collide, check_foundation,
    evaluate_connector_pair.
    """

    part_id: str
    collision: CollisionStatus
    blocking_parts: Tuple[str, ...]
    supporting_parts: Tuple[str, ...]
    bond_count: int
    foundation: FoundationCheck

    @property
    def is_supported(self) -> bool:
        return self.foundation.is_founded or self.bond_count > 0

    @property
    def is_legal(self) -> bool:
        return (
            self.collision is not CollisionStatus.PENETRATION
            and self.foundation.is_valid
            and self.is_supported
        )


def evaluate_placement(
    placed_parts: Mapping[str, PlacedPart],
    geometries: Mapping[str, CollisionGeometry],
    candidate: PlacedPart,
    candidate_geometry: CollisionGeometry,
    tolerance: ConnectorTolerance,
    search: Optional[SearchApproximation] = None,
    foundation_plane_z: int = 0,
) -> PlacementVerdict:
    """Evalue une pose SANS rien modifier : pur calcul, aucun etat produit.

    Une CAO appelle ceci a chaque mouvement de souris ; `add_part` n'est appele
    qu'au relachement.
    """
    if candidate.part_id in placed_parts:
        raise ValueError(f"identifiant deja place : {candidate.part_id}")

    worst = CollisionStatus.CLEAR
    blocking: List[str] = []
    for part_id, part in placed_parts.items():
        geometry = geometries.get(part_id)
        if geometry is None:
            continue
        status = collide(candidate_geometry, candidate.pose, geometry, part.pose)
        if status is CollisionStatus.PENETRATION:
            blocking.append(part_id)
            worst = CollisionStatus.PENETRATION
        elif status is CollisionStatus.CONTACT and worst is CollisionStatus.CLEAR:
            worst = CollisionStatus.CONTACT

    search = ReferenceSearchApproximation() if search is None else search
    hypothetical = with_part(placed_parts, candidate)
    bonds_by_edge = _bonds_involving(
        candidate.part_id,
        hypothetical,
        tolerance,
        search,
        build_index(hypothetical),
    )
    supporting = tuple(
        sorted(
            {
                identifier
                for edge in bonds_by_edge
                for identifier in edge
                if identifier != candidate.part_id
            }
        )
    )
    bond_count = sum(len(bonds) for bonds in bonds_by_edge.values())

    return PlacementVerdict(
        part_id=candidate.part_id,
        collision=worst,
        blocking_parts=tuple(sorted(blocking)),
        supporting_parts=supporting,
        bond_count=bond_count,
        foundation=check_foundation(
            candidate_geometry.exterior,
            candidate.connectors,
            candidate.pose,
            foundation_plane_z,
        ),
    )
