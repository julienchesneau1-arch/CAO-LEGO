"""BFK-001 v3.3.2 — Section K : invariants HARD H1 a H6.

Ce module est un consommateur : il ne cree aucun bond, ne modifie aucun etat,
et n'accorde d'autorite qu'aux fonctions qui la detiennent (oracle pour la
mecanique, collide pour la geometrie, check_foundation pour la fondation).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Set, Tuple

from .collision import CollisionGeometry, CollisionStatus, collide
from .connectors import ConnectorTolerance
from .foundation import FoundationStatus, check_foundation
from .graph import ConstructionGraph
from .oracle import evaluate_connector_pair, is_oracle_issued
from .search import PlacedPart, ReferenceSearchApproximation, SearchApproximation
from .spatial import GridSpatialIndex, ReferenceSpatialIndex, SpatialCandidateIndex

__all__ = [
    "InvariantViolation",
    "ValidationReport",
    "physical_pairs",
    "check_h1_search_coverage",
    "check_h2_collision",
    "check_h3_authority_integrity",
    "check_h4_floating",
    "check_h5_disconnected",
    "check_h6_foundation",
    "validate",
]


@dataclass(frozen=True)
class InvariantViolation:
    invariant: str
    detail: str


@dataclass(frozen=True)
class ValidationReport:
    violations: Tuple[InvariantViolation, ...]

    @property
    def ok(self) -> bool:
        return not self.violations

    def of(self, invariant: str) -> Tuple[InvariantViolation, ...]:
        return tuple(v for v in self.violations if v.invariant == invariant)


PairKey = Tuple[str, str, object, object]


def physical_pairs(
    placed_parts: Mapping[str, PlacedPart],
    tolerance: ConnectorTolerance,
) -> Set[PairKey]:
    """P : paires de connecteurs pour lesquelles l'oracle emet un PhysicalBond.

    Enumeration exhaustive O(n^2) INDEPENDANTE de toute SearchApproximation :
    c'est la reference contre laquelle H1 est verifie.
    """
    found: Set[PairKey] = set()
    for id_a, part_a in placed_parts.items():
        for id_b, part_b in placed_parts.items():
            if id_a >= id_b:
                continue
            for conn_a in part_a.connectors:
                for conn_b in part_b.connectors:
                    if (
                        evaluate_connector_pair(
                            conn_a, part_a.pose, conn_b, part_b.pose, tolerance
                        )
                        is not None
                    ):
                        found.add((id_a, id_b, conn_a, conn_b))
    return found


def check_h1_search_coverage(
    placed_parts: Mapping[str, PlacedPart],
    tolerance: ConnectorTolerance,
    search: Optional[SearchApproximation] = None,
    index: Optional[SpatialCandidateIndex] = None,
) -> Tuple[InvariantViolation, ...]:
    """H1_SEARCH_COVERAGE : P inclus dans C.

    Un bond valide ne peut jamais etre omis par la recherche evaluee.
    """
    search = ReferenceSearchApproximation() if search is None else search
    index = _index_of(placed_parts) if index is None else index

    candidates = set(search.find_candidate_pairs(index, placed_parts, tolerance))
    missing = physical_pairs(placed_parts, tolerance) - candidates
    return tuple(
        InvariantViolation(
            "H1_SEARCH_COVERAGE",
            f"bond valide absent des candidats : {id_a} <-> {id_b}",
        )
        for id_a, id_b, _, _ in sorted(missing, key=lambda pair: (pair[0], pair[1]))
    )


def check_h2_collision(
    placed_parts: Mapping[str, PlacedPart],
    geometries: Mapping[str, CollisionGeometry],
) -> Tuple[InvariantViolation, ...]:
    """H2_COLLISION : penetration_count == 0.

    Elagage par grille uniforme, SANS perte : deux pieces dont les AABB monde
    sont disjoints sont CLEAR par la Section F.4, et la requete de
    GridSpatialIndex est un sur-ensemble exhaustif des pieces non disjointes.
    Ecarter une paire non retournee ne peut donc masquer aucune penetration.
    L'index est construit ici, jamais recu : un accelerateur injecte n'offre
    aucune garantie d'exhaustivite (Section G) et n'a pas a porter un invariant.

    Toute piece placee DOIT avoir une geometrie. Ignorer silencieusement une
    piece sans geometrie rendrait un H2 vert qui ne veut rien dire : c'est
    exactement ainsi qu'un validateur cesse d'etre utile.
    """
    _require_geometries(placed_parts, geometries, "H2_COLLISION")

    grid = GridSpatialIndex()
    for part_id, part in placed_parts.items():
        grid.insert(part_id, part.aabb)

    violations: List[InvariantViolation] = []
    for id_a, part_a in placed_parts.items():
        for id_b in grid.query(part_a.aabb):
            if id_b <= id_a:
                continue
            status = collide(
                geometries[id_a], part_a.pose, geometries[id_b], placed_parts[id_b].pose
            )
            if status is CollisionStatus.PENETRATION:
                violations.append(
                    InvariantViolation("H2_COLLISION", f"PENETRATION {id_a} / {id_b}")
                )
    return tuple(violations)


def _require_geometries(
    placed_parts: Mapping[str, PlacedPart],
    geometries: Mapping[str, CollisionGeometry],
    invariant: str,
) -> None:
    """Un invariant ne se prononce jamais sur une piece qu'il ne voit pas."""
    missing = sorted(set(placed_parts) - set(geometries))
    if missing:
        raise KeyError(
            f"{invariant} : geometrie absente pour {', '.join(missing)}. "
            "Un invariant ne peut pas etre declare satisfait sur une piece "
            "dont la geometrie est inconnue."
        )


def check_h3_authority_integrity(
    graph: ConstructionGraph,
) -> Tuple[InvariantViolation, ...]:
    """H3_AUTHORITY_INTEGRITY : aucun PhysicalBond externe a l'oracle."""
    violations: List[InvariantViolation] = []
    for id_a, id_b, bonds in graph.edges:
        for bond in bonds:
            if not is_oracle_issued(bond):
                violations.append(
                    InvariantViolation(
                        "H3_AUTHORITY_INTEGRITY",
                        f"bond non emis par l'oracle sur l'arete {id_a} <-> {id_b}",
                    )
                )
    return tuple(violations)


def _adjacency(graph: ConstructionGraph) -> Dict[str, Set[str]]:
    adjacency: Dict[str, Set[str]] = {part_id: set() for part_id, _, _ in graph.parts}
    for id_a, id_b, bonds in graph.edges:
        if not bonds:
            continue
        adjacency.setdefault(id_a, set()).add(id_b)
        adjacency.setdefault(id_b, set()).add(id_a)
    return adjacency


def _component(adjacency: Mapping[str, Set[str]], start: str) -> Set[str]:
    seen = {start}
    stack = [start]
    while stack:
        current = stack.pop()
        for neighbour in adjacency.get(current, ()):
            if neighbour not in seen:
                seen.add(neighbour)
                stack.append(neighbour)
    return seen


def check_h4_floating(
    graph: ConstructionGraph,
    founded_part_ids: Tuple[str, ...],
) -> Tuple[InvariantViolation, ...]:
    """H4_FLOATING : toute piece non fondee a une chaine de bonds vers une fondation."""
    adjacency = _adjacency(graph)
    founded = set(founded_part_ids)
    violations: List[InvariantViolation] = []
    for part_id, _, _ in graph.parts:
        if part_id in founded:
            continue
        if not (_component(adjacency, part_id) & founded):
            violations.append(
                InvariantViolation("H4_FLOATING", f"piece flottante : {part_id}")
            )
    return tuple(violations)


def check_h5_disconnected(graph: ConstructionGraph) -> Tuple[InvariantViolation, ...]:
    """H5_DISCONNECTED : le graphe de construction est connexe."""
    part_ids = [part_id for part_id, _, _ in graph.parts]
    if len(part_ids) <= 1:
        return ()
    adjacency = _adjacency(graph)
    reachable = _component(adjacency, part_ids[0])
    isolated = sorted(set(part_ids) - reachable)
    return tuple(
        InvariantViolation("H5_DISCONNECTED", f"piece non reliee : {part_id}")
        for part_id in isolated
    )


def check_h6_foundation(
    placed_parts: Mapping[str, PlacedPart],
    geometries: Mapping[str, CollisionGeometry],
    foundation_plane_z: int = 0,
) -> Tuple[InvariantViolation, ...]:
    """H6_FOUNDATION : toute piece au plan de fondation satisfait check_foundation.

    Une piece sous le plan est INVALIDE ; une piece exactement au plan doit etre
    geometriquement fondee.
    """
    _require_geometries(placed_parts, geometries, "H6_FOUNDATION")

    violations: List[InvariantViolation] = []
    for part_id, part in placed_parts.items():
        result = check_foundation(
            geometries[part_id].exterior,
            part.connectors,
            part.pose,
            foundation_plane_z,
        )
        if result.status is FoundationStatus.INVALID:
            violations.append(
                InvariantViolation(
                    "H6_FOUNDATION",
                    f"{part_id} penetre le plan de fondation (min.z={result.world_min_z})",
                )
            )
        elif (
            result.world_min_z == foundation_plane_z
            and result.status is not FoundationStatus.FOUNDED
        ):
            violations.append(
                InvariantViolation(
                    "H6_FOUNDATION",
                    f"{part_id} repose sur le plan sans connecteur femelle vers le bas",
                )
            )
    return tuple(violations)


def founded_part_ids(
    placed_parts: Mapping[str, PlacedPart],
    geometries: Mapping[str, CollisionGeometry],
    foundation_plane_z: int = 0,
) -> Tuple[str, ...]:
    """Identifiants des pieces geometriquement fondees (support de H4)."""
    _require_geometries(placed_parts, geometries, "H4_FLOATING")
    return tuple(
        part_id
        for part_id, part in placed_parts.items()
        if check_foundation(
            geometries[part_id].exterior,
            part.connectors,
            part.pose,
            foundation_plane_z,
        ).is_founded
    )


def _index_of(placed_parts: Mapping[str, PlacedPart]) -> ReferenceSpatialIndex:
    index = ReferenceSpatialIndex()
    for part_id, part in placed_parts.items():
        index.insert(part_id, part.aabb)
    return index


def validate(
    graph: ConstructionGraph,
    placed_parts: Mapping[str, PlacedPart],
    geometries: Mapping[str, CollisionGeometry],
    tolerance: ConnectorTolerance,
    search: Optional[SearchApproximation] = None,
    index: Optional[SpatialCandidateIndex] = None,
    foundation_plane_z: int = 0,
) -> ValidationReport:
    """Agrege H1 a H6 en un rapport unique."""
    founded = founded_part_ids(placed_parts, geometries, foundation_plane_z)
    violations: Tuple[InvariantViolation, ...] = (
        check_h1_search_coverage(placed_parts, tolerance, search, index)
        + check_h2_collision(placed_parts, geometries)
        + check_h3_authority_integrity(graph)
        + check_h4_floating(graph, founded)
        + check_h5_disconnected(graph)
        + check_h6_foundation(placed_parts, geometries, foundation_plane_z)
    )
    return ValidationReport(violations)
