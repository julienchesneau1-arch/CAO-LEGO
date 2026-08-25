"""
BFK-001 v3.3.2 — Phase 7 : integration et invariants HARD H1 a H6 (Section K).

Ces tests exercent la chaine complete :
    recherche (C) -> oracle (P) -> graphe -> etat -> validation

Chaque invariant est teste dans les deux sens : un etat conforme ne produit
aucune violation, et un etat deliberement casse produit exactement la violation
attendue. Un validateur qui ne mord jamais ne vaut rien.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import pytest

import bfk001_kernel as bfk

BRICK_H = 24
BRICK_W = 40


def V(x, y, z):
    return bfk.LDUVector(x, y, z)


def BX(lo, hi):
    return bfk.AABB(V(*lo), V(*hi))


def P(translation=(0, 0, 0), orientation=None):
    return (
        V(*translation),
        bfk.Orientation.identity() if orientation is None else orientation,
    )


def TOL():
    return bfk.ConnectorTolerance(max_position_error_ldu=0.5, max_angular_error_deg=5.0)


def connectors_2x2():
    males = tuple(
        bfk.Connector("stud_male", V(x, y, BRICK_H), V(0, 0, 1))
        for x in (10, 30)
        for y in (10, 30)
    )
    females = tuple(
        bfk.Connector("stud_female", V(x, y, 0), V(0, 0, -1))
        for x in (10, 30)
        for y in (10, 30)
    )
    return males + females


def geometry_2x2():
    """Brique 2x2 a dessous creux : exterieur plein, cavite interne."""
    return bfk.CollisionGeometry(
        exterior=BX((0, 0, 0), (BRICK_W, BRICK_W, BRICK_H)),
        voids=(BX((2, 2, 0), (BRICK_W - 2, BRICK_W - 2, BRICK_H - 4)),),
    )


def brick(part_id, translation=(0, 0, 0)):
    pose = P(translation)
    return bfk.PlacedPart(
        part_id=part_id,
        pose=pose,
        aabb=bfk.transform_aabb(geometry_2x2().exterior, pose),
        connectors=connectors_2x2(),
    )


def stack(part_ids_and_translations):
    return {
        part_id: brick(part_id, translation)
        for part_id, translation in part_ids_and_translations
    }


def geometries_for(placed_parts):
    return {part_id: geometry_2x2() for part_id in placed_parts}


# =============================================================================
# Etat conforme
# =============================================================================


def test_valid_stack_satisfies_h1_to_h6():
    placed = stack((("A", (0, 0, 0)), ("B", (0, 0, BRICK_H))))
    tolerance = TOL()
    state = bfk.assemble(placed, tolerance)

    assert len(state.graph.parts) == 2
    assert len(state.graph.edges) == 1
    edge_a, edge_b, bonds = state.graph.edges[0]
    assert (edge_a, edge_b) == ("A", "B")
    assert len(bonds) == 4, "4 tenons engages"
    assert all(bfk.is_oracle_issued(bond) for bond in bonds)

    report = bfk.validate(
        state.graph, placed, geometries_for(placed), tolerance
    )
    assert report.ok, report.violations


def test_snapshot_is_query_only_and_consistent():
    placed = stack((("A", (0, 0, 0)), ("B", (0, 0, BRICK_H))))
    state = bfk.assemble(placed, TOL())

    found = tuple(state.spatial_snapshot.query(BX((0, 0, 0), (1, 1, 1))))
    assert found == ("A",)
    assert not hasattr(state.spatial_snapshot, "insert")
    assert not hasattr(state.spatial_snapshot, "remove")


# =============================================================================
# H1 — SEARCH COVERAGE
# =============================================================================


class BlindSearchApproximation:
    """Recherche deliberement incomplete : ne propose jamais rien."""

    def find_candidate_pairs(self, index, placed_parts, tolerance):
        return ()


def test_h1_detects_incomplete_search():
    placed = stack((("A", (0, 0, 0)), ("B", (0, 0, BRICK_H))))
    tolerance = TOL()

    assert bfk.check_h1_search_coverage(placed, tolerance) == ()

    violations = bfk.check_h1_search_coverage(
        placed, tolerance, search=BlindSearchApproximation()
    )
    assert violations, "une recherche aveugle doit violer H1"
    assert all(v.invariant == "H1_SEARCH_COVERAGE" for v in violations)


# =============================================================================
# H2 — COLLISION
# =============================================================================


def test_h2_detects_penetration():
    placed = stack((("A", (0, 0, 0)), ("B", (0, 0, BRICK_H))))
    assert bfk.check_h2_collision(placed, geometries_for(placed)) == ()

    interpenetrating = stack((("A", (0, 0, 0)), ("B", (0, 0, BRICK_H // 2))))
    violations = bfk.check_h2_collision(
        interpenetrating, geometries_for(interpenetrating)
    )
    assert len(violations) == 1
    assert violations[0].invariant == "H2_COLLISION"


# =============================================================================
# H3 — AUTHORITY INTEGRITY
# =============================================================================


def test_h3_rejects_bond_not_issued_by_oracle():
    placed = stack((("A", (0, 0, 0)), ("B", (0, 0, BRICK_H))))
    state = bfk.assemble(placed, TOL())
    assert bfk.check_h3_authority_integrity(state.graph) == ()

    forged = object.__new__(bfk.PhysicalBond)
    tampered = bfk.ConstructionGraph(
        parts=state.graph.parts,
        edges=(("A", "B", (forged,)),),
    )
    violations = bfk.check_h3_authority_integrity(tampered)
    assert len(violations) == 1
    assert violations[0].invariant == "H3_AUTHORITY_INTEGRITY"


def test_physical_bond_cannot_be_subclassed():
    with pytest.raises(TypeError):

        class ForgedBond(bfk.PhysicalBond):  # noqa: N801
            pass


# =============================================================================
# H4 / H5 — FLOATING et DISCONNECTED
# =============================================================================


def test_h4_and_h5_detect_floating_island():
    placed = stack(
        (("A", (0, 0, 0)), ("B", (0, 0, BRICK_H)), ("Z", (400, 400, 10 * BRICK_H)))
    )
    tolerance = TOL()
    state = bfk.assemble(placed, tolerance)
    geometries = geometries_for(placed)
    founded = bfk.founded_part_ids(placed, geometries)
    assert founded == ("A",)

    floating = bfk.check_h4_floating(state.graph, founded)
    assert [v.detail for v in floating] == ["piece flottante : Z"]

    disconnected = bfk.check_h5_disconnected(state.graph)
    assert [v.detail for v in disconnected] == ["piece non reliee : Z"]

    report = bfk.validate(state.graph, placed, geometries, tolerance)
    assert not report.ok
    assert report.of("H4_FLOATING")
    assert report.of("H5_DISCONNECTED")
    assert report.of("H2_COLLISION") == ()


# =============================================================================
# H6 — FOUNDATION
# =============================================================================


def test_h6_detects_ground_penetration_and_bad_seating():
    placed = stack((("A", (0, 0, 0)),))
    assert bfk.check_h6_foundation(placed, geometries_for(placed)) == ()

    sunk = stack((("A", (0, 0, -1)),))
    violations = bfk.check_h6_foundation(sunk, geometries_for(sunk))
    assert len(violations) == 1
    assert "penetre" in violations[0].detail

    upside_down_pose = P((0, 0, BRICK_H), bfk.Orientation(1, 0, 0, 0, -1, 0, 0, 0, -1))
    flipped = {
        "A": bfk.PlacedPart(
            part_id="A",
            pose=upside_down_pose,
            aabb=bfk.transform_aabb(geometry_2x2().exterior, upside_down_pose),
            connectors=connectors_2x2(),
        )
    }
    violations = bfk.check_h6_foundation(flipped, geometries_for(flipped))
    assert len(violations) == 1
    assert violations[0].invariant == "H6_FOUNDATION"


# =============================================================================
# Section I.2 — InstructionGraph.validate_dag
# =============================================================================


@dataclass(frozen=True)
class Step:
    step_id: str
    depends_on: Tuple[str, ...]


def test_validate_dag():
    acyclic = bfk.InstructionGraph(
        steps=(
            Step("s1", ()),
            Step("s2", ("s1",)),
            Step("s3", ("s1", "s2")),
        )
    )
    assert acyclic.validate_dag() is True

    cyclic = bfk.InstructionGraph(
        steps=(Step("s1", ("s2",)), Step("s2", ("s1",)))
    )
    assert cyclic.validate_dag() is False

    unknown = bfk.InstructionGraph(steps=(Step("s1", ("absent",)),))
    assert unknown.validate_dag() is False

    duplicated = bfk.InstructionGraph(steps=(Step("s1", ()), Step("s1", ())))
    assert duplicated.validate_dag() is False


# =============================================================================
# Determinisme et purete de l'orchestration
# =============================================================================


def test_assemble_is_deterministic_and_pure():
    placed = stack((("A", (0, 0, 0)), ("B", (0, 0, BRICK_H))))
    first = bfk.assemble(placed, TOL())
    second = bfk.assemble(placed, TOL())

    assert [(a, b, len(bonds)) for a, b, bonds in first.graph.edges] == [
        (a, b, len(bonds)) for a, b, bonds in second.graph.edges
    ]
    assert first.graph.parts == second.graph.parts
    # Les bonds sont opaques : deux emissions distinctes ne sont jamais egales.
    assert first.graph.edges[0][2] != second.graph.edges[0][2]

    with pytest.raises(ValueError):
        bfk.with_part(placed, brick("A", (0, 0, 3 * BRICK_H)))
