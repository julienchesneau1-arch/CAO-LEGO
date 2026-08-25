"""
BFK-001 v3.3.2 — Tests adversariaux T1a a T14 (Section M du contrat).

Regle absolue (Section M) : aucun test ne reconstruit l'etat interne qu'il
pretend auditer. Les tests n'utilisent que la surface publique exposee par
`bfk001_kernel` et les deux autorites (oracle mecanique, autorite geometrique).

Convention de fixture : brique 2x2 LDU-like
  - 1 tenon        = 20 LDU
  - hauteur brique = 24 LDU
  - empreinte 2x2  = 40 x 40 LDU
  - tenons males   : ctype "stud_male",   normale locale (0, 0, +1), z = 24
  - tenons femelles: ctype "stud_female", normale locale (0, 0, -1), z = 0
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import math

import pytest

import bfk001_kernel as bfk

# =============================================================================
# Fixtures communes
# =============================================================================

STUD = 20
BRICK_H = 24
BRICK_W = 40
BRICK_EXTERIOR = ((0, 0, 0), (BRICK_W, BRICK_W, BRICK_H))


def V(x, y, z):
    return bfk.LDUVector(x, y, z)


def BX(lo, hi):
    return bfk.AABB(V(*lo), V(*hi))


def IDENTITY():
    return bfk.Orientation(1, 0, 0, 0, 1, 0, 0, 0, 1)


def ROT_Z_90():
    """Rotation +90 deg autour de Z : (x, y, z) -> (-y, x, z)."""
    return bfk.Orientation(0, -1, 0, 1, 0, 0, 0, 0, 1)


def ROT_X_180():
    """Rotation 180 deg autour de X : (x, y, z) -> (x, -y, -z)."""
    return bfk.Orientation(1, 0, 0, 0, -1, 0, 0, 0, -1)


def P(translation=(0, 0, 0), orientation=None):
    return (V(*translation), IDENTITY() if orientation is None else orientation)


def TOL(pos=0.5, ang=5.0):
    return bfk.ConnectorTolerance(max_position_error_ldu=pos, max_angular_error_deg=ang)


def males():
    return tuple(
        bfk.Connector("stud_male", V(x, y, BRICK_H), V(0, 0, 1))
        for x in (10, 30)
        for y in (10, 30)
    )


def females():
    return tuple(
        bfk.Connector("stud_female", V(x, y, 0), V(0, 0, -1))
        for x in (10, 30)
        for y in (10, 30)
    )


def brick(part_id, translation=(0, 0, 0), orientation=None, connectors=None):
    pose = P(translation, orientation)
    conns = males() + females() if connectors is None else connectors
    return bfk.PlacedPart(
        part_id=part_id,
        pose=pose,
        aabb=bfk.transform_aabb(BX(*BRICK_EXTERIOR), pose),
        connectors=conns,
    )


def indexed(placed_parts):
    index = bfk.ReferenceSpatialIndex()
    for part_id, part in placed_parts.items():
        index.insert(part_id, part.aabb)
    return index


def physical_pairs(placed_parts, tolerance):
    """P : ensemble des paires pour lesquelles l'oracle emet un PhysicalBond.

    Calcule exhaustivement et INDEPENDAMMENT de toute SearchApproximation :
    seul l'oracle est interroge.
    """
    found = set()
    for id_a, part_a in placed_parts.items():
        for id_b, part_b in placed_parts.items():
            if id_a >= id_b:
                continue
            for conn_a in part_a.connectors:
                for conn_b in part_b.connectors:
                    bond = bfk.evaluate_connector_pair(
                        conn_a, part_a.pose, conn_b, part_b.pose, tolerance
                    )
                    if bond is not None:
                        found.add((id_a, id_b, conn_a, conn_b))
    return found


def volume(aabb):
    return (
        (aabb.max.x - aabb.min.x)
        * (aabb.max.y - aabb.min.y)
        * (aabb.max.z - aabb.min.z)
    )


# =============================================================================
# T1a / T1b — Isolation de l'autorite mecanique (Sections A.8, E)
# =============================================================================

FORBIDDEN_SYMBOLS = (
    "SearchApproximation",
    "ReferenceSearchApproximation",
    "SpatialCandidateIndex",
    "ReferenceSpatialIndex",
    "SpatialSnapshot",
    "ConstructionState",
    "ConstructionGraph",
    "InstructionGraph",
    "PlacedPart",
    "CollisionGeometry",
    "CollisionStatus",
    "collide",
    "solid_overlap",
    "collision_status",
    "geometric_relation",
    "intersection_aabb",
    "check_foundation",
)

FORBIDDEN_MODULE_SUBSTRINGS = (
    "search",
    "spatial",
    "state",
    "graph",
    "collision",
    "foundation",
    "validation",
    "orchestr",
    "voxel",
    "solver",
    "registry",
    "index",
    "kernel",
)


def test_oracle_signature_isolation():
    """T1a : la signature de l'oracle n'expose que des primitives."""
    signature = inspect.signature(bfk.evaluate_connector_pair)
    assert tuple(signature.parameters) == (
        "connector_a",
        "pose_a",
        "connector_b",
        "pose_b",
        "tolerance",
    )

    annotations = dict(getattr(bfk.evaluate_connector_pair, "__annotations__", {}))
    expected = {
        "connector_a": "Connector",
        "pose_a": "Pose",
        "connector_b": "Connector",
        "pose_b": "Pose",
        "tolerance": "ConnectorTolerance",
        "return": "Optional[PhysicalBond]",
    }
    assert set(annotations) == set(expected), "annotations manquantes ou surnumeraires"
    for name, annotation in annotations.items():
        assert str(annotation).replace(" ", "") == expected[name]

    rendered = " ".join(str(a) for a in annotations.values())
    for symbol in FORBIDDEN_SYMBOLS:
        assert symbol not in rendered, f"signature contaminee par {symbol}"


def test_oracle_dependency_isolation():
    """T1b : le module de l'oracle n'importe aucun module interdit."""
    module = inspect.getmodule(bfk.evaluate_connector_pair)
    assert module is not None

    tree = ast.parse(inspect.getsource(module))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
            imported.extend(alias.name for alias in node.names)

    for name in imported:
        lowered = name.lower()
        for forbidden in FORBIDDEN_MODULE_SUBSTRINGS:
            assert forbidden not in lowered, (
                f"import interdit dans le module de l'oracle : {name}"
            )

    for symbol in FORBIDDEN_SYMBOLS:
        assert not hasattr(module, symbol), (
            f"symbole interdit visible depuis le module de l'oracle : {symbol}"
        )


def test_physical_bond_is_opaque():
    """T1a (complement) : PhysicalBond n'a pas de constructeur public."""
    with pytest.raises(TypeError):
        bfk.PhysicalBond()

    a = brick("A", (0, 0, 0))
    b = brick("B", (0, 0, BRICK_H))
    bond = bfk.evaluate_connector_pair(
        a.connectors[0], a.pose, females()[0], b.pose, TOL()
    )
    assert bond is not None
    assert bfk.is_oracle_issued(bond) is True

    forged = object.__new__(bfk.PhysicalBond)
    assert bfk.is_oracle_issued(forged) is False


# =============================================================================
# T2 / T8 / T9 — H1_SEARCH_COVERAGE (Sections A.7, H, K)
# =============================================================================


def test_search_coverage_completeness():
    """T2 : la recherche de reference est exhaustive sur les paires compatibles."""
    placed = {"A": brick("A", (0, 0, 0)), "B": brick("B", (0, 0, BRICK_H))}
    tolerance = TOL()
    candidates = set(
        bfk.ReferenceSearchApproximation().find_candidate_pairs(
            indexed(placed), placed, tolerance
        )
    )

    # 4 males x 4 femelles dans chaque sens = 32 paires compatibles.
    assert len(candidates) == 32
    known = ("A", "B", males()[0], females()[0])
    assert known in candidates

    for _, _, conn_a, conn_b in candidates:
        assert {conn_a.ctype, conn_b.ctype} == {"stud_male", "stud_female"}


class PermissiveIndex:
    """Index qui retourne TOUT : un accelerateur ne juge jamais la mecanique."""

    def __init__(self, part_ids):
        self._part_ids = tuple(part_ids)

    def query(self, region):
        return self._part_ids

    def insert(self, part_id, aabb):
        return None

    def remove(self, part_id):
        return None


def test_search_no_false_mechanical_claim():
    """T3 : un index permissif ne cree aucun bond ; l'oracle rejette."""
    placed = {
        "A": brick("A", (0, 0, 0)),
        "B": brick("B", (0, 0, BRICK_H + 1)),  # 1 LDU de trop : aucun bond
    }
    tolerance = TOL()
    candidates = list(
        bfk.ReferenceSearchApproximation().find_candidate_pairs(
            PermissiveIndex(placed), placed, tolerance
        )
    )
    assert candidates, "l'index permissif doit produire des candidats"

    for id_a, id_b, conn_a, conn_b in candidates:
        bond = bfk.evaluate_connector_pair(
            conn_a, placed[id_a].pose, conn_b, placed[id_b].pose, tolerance
        )
        assert bond is None, "un candidat ne vaut jamais preuve mecanique"


def test_candidate_implies_nothing():
    """T7 : deux pieces lointaines produisent des candidats, jamais de bond."""
    placed = {"A": brick("A", (0, 0, 0)), "B": brick("B", (400, 0, BRICK_H))}
    tolerance = TOL()
    candidates = list(
        bfk.ReferenceSearchApproximation().find_candidate_pairs(
            indexed(placed), placed, tolerance
        )
    )
    assert len(candidates) == 32
    assert physical_pairs(placed, tolerance) == set()


def test_bond_implies_candidate():
    """T8 : H1 = P inclus dans C pour la recherche de reference."""
    placed = {
        "A": brick("A", (0, 0, 0)),
        "B": brick("B", (0, 0, BRICK_H)),
        "C": brick("C", (BRICK_W, 0, 0)),
    }
    tolerance = TOL()
    candidates = set(
        bfk.ReferenceSearchApproximation().find_candidate_pairs(
            indexed(placed), placed, tolerance
        )
    )
    physical = physical_pairs(placed, tolerance)
    assert len(physical) == 4, "4 tenons engages entre A et B"
    assert physical <= candidates


class FastSearchApproximation:
    """Index rapide hypothetique : elagage spatial par proximite."""

    def find_candidate_pairs(self, index, placed_parts, tolerance):
        margin = math.ceil(tolerance.max_position_error_ldu)
        for id_a, part_a in placed_parts.items():
            region = bfk.AABB(
                bfk.LDUVector(
                    part_a.aabb.min.x - margin,
                    part_a.aabb.min.y - margin,
                    part_a.aabb.min.z - margin,
                ),
                bfk.LDUVector(
                    part_a.aabb.max.x + margin,
                    part_a.aabb.max.y + margin,
                    part_a.aabb.max.z + margin,
                ),
            )
            for id_b in index.query(region):
                if id_a >= id_b:
                    continue
                part_b = placed_parts[id_b]
                for conn_a in part_a.connectors:
                    for conn_b in part_b.connectors:
                        pair = {conn_a.ctype, conn_b.ctype}
                        if pair == {"stud_male", "stud_female"}:
                            yield (id_a, id_b, conn_a, conn_b)


def test_fast_subset_physical():
    """T9 : P inclus dans C_fast ; C_ref inclus dans C_fast n'est PAS exige."""
    placed = {
        "A": brick("A", (0, 0, 0)),
        "B": brick("B", (0, 0, BRICK_H)),
        "Z": brick("Z", (4000, 0, 0)),  # hors de portee
    }
    tolerance = TOL()
    index = indexed(placed)

    reference = set(
        bfk.ReferenceSearchApproximation().find_candidate_pairs(
            index, placed, tolerance
        )
    )
    fast = set(FastSearchApproximation().find_candidate_pairs(index, placed, tolerance))
    physical = physical_pairs(placed, tolerance)

    assert physical, "fixture invalide : aucun bond physique"
    assert physical <= fast, "H1 viole par l'index rapide"
    assert fast < reference, "la fixture doit exhiber C_fast strictement inclus dans C_ref"


# =============================================================================
# T4 — Fondation exacte (Section L)
# =============================================================================


def test_foundation_exact_integer():
    """T4 : arithmetique entiere exacte au plan de fondation."""
    exterior = BX(*BRICK_EXTERIOR)

    founded = bfk.check_foundation(exterior, males() + females(), P((0, 0, 0)))
    assert founded.status is bfk.FoundationStatus.FOUNDED

    no_female = bfk.check_foundation(exterior, males(), P((0, 0, 0)))
    assert no_female.status is bfk.FoundationStatus.UNFOUNDED

    above = bfk.check_foundation(exterior, males() + females(), P((0, 0, 1)))
    assert above.status is bfk.FoundationStatus.UNFOUNDED

    below = bfk.check_foundation(exterior, males() + females(), P((0, 0, -1)))
    assert below.status is bfk.FoundationStatus.INVALID

    # Brique retournee : min.z == 0 mais la normale femelle pointe vers le haut.
    flipped = bfk.check_foundation(
        exterior, males() + females(), P((0, 0, BRICK_H), ROT_X_180())
    )
    assert flipped.status is bfk.FoundationStatus.UNFOUNDED

    # Plan de fondation non nul : la regle reste exacte.
    raised = bfk.check_foundation(
        exterior, males() + females(), P((0, 0, 96)), foundation_plane_z=96
    )
    assert raised.status is bfk.FoundationStatus.FOUNDED


# =============================================================================
# T5 / T6 / T12 / T14 — Autorite geometrique et collision (Section F)
# =============================================================================



def hollow_brick():
    """Piece dont le sommet (z in [20, 24]) est un void."""
    return bfk.CollisionGeometry(
        exterior=BX((0, 0, 0), (20, 20, 24)),
        voids=(BX((0, 0, 20), (20, 20, 24)),),
    )


def solid_brick():
    return bfk.CollisionGeometry(exterior=BX((0, 0, 0), (20, 20, 24)), voids=())


def test_collision_void_contact():
    """T5 : recouvrement integralement absorbe par un void -> CONTACT."""
    status = bfk.collide(hollow_brick(), P((0, 0, 0)), solid_brick(), P((0, 0, 20)))
    assert status is bfk.CollisionStatus.CONTACT


def test_collision_exact_penetration():
    """T6 : matiere solide en conflit -> PENETRATION."""
    status = bfk.collide(hollow_brick(), P((0, 0, 0)), solid_brick(), P((0, 0, 16)))
    assert status is bfk.CollisionStatus.PENETRATION


def test_collision_clear_and_contact():
    """T5 (complement) : DISJOINT -> CLEAR, TOUCHING -> CONTACT."""
    assert (
        bfk.collide(solid_brick(), P((0, 0, 0)), solid_brick(), P((0, 0, 200)))
        is bfk.CollisionStatus.CLEAR
    )
    assert (
        bfk.collide(solid_brick(), P((0, 0, 0)), solid_brick(), P((0, 0, 24)))
        is bfk.CollisionStatus.CONTACT
    )


def test_solid_overlap_exact_decomposition():
    """T12 : partition exacte, jamais une AABB englobante approximative."""
    intersection = BX((0, 0, 16), (20, 20, 24))
    solid_a = BX((0, 0, 0), (20, 20, 24))
    voids_a = (BX((0, 0, 20), (20, 20, 24)),)
    solid_b = BX((0, 0, 16), (20, 20, 44))
    voids_b = (BX((5, 5, 16), (15, 15, 20)),)

    parts = bfk.solid_overlap(intersection, solid_a, voids_a, solid_b, voids_b)
    assert parts is not None
    assert isinstance(parts, tuple)
    assert all(isinstance(piece, bfk.AABB) for piece in parts)

    # R = [0,20]x[0,20]x[16,20] prive de [5,15]x[5,15]x[16,20]
    # volume attendu = 20*20*4 - 10*10*4 = 1600 - 400 = 1200
    assert sum(volume(piece) for piece in parts) == 1200

    for i, piece in enumerate(parts):
        assert volume(piece) > 0
        for other in parts[i + 1 :]:
            assert bfk.intersection_aabb(piece, other) is None, "interieurs non disjoints"
        assert bfk.intersection_aabb(piece, voids_a[0]) is None
        assert bfk.intersection_aabb(piece, voids_b[0]) is None
        assert bfk.geometric_relation(piece, intersection) is not bfk.GeometricRelation.DISJOINT

    # Sur-approximation interdite : l'AABB englobante des morceaux a un volume
    # strictement superieur au volume reel de la region.
    hull_min = bfk.LDUVector(
        min(p.min.x for p in parts), min(p.min.y for p in parts), min(p.min.z for p in parts)
    )
    hull_max = bfk.LDUVector(
        max(p.max.x for p in parts), max(p.max.y for p in parts), max(p.max.z for p in parts)
    )
    assert volume(bfk.AABB(hull_min, hull_max)) > 1200
    assert parts != (bfk.AABB(hull_min, hull_max),)


def test_solid_overlap_empty_is_none():
    """T5 (complement) : region vide -> None, jamais un tuple vide."""
    result = bfk.solid_overlap(
        BX((0, 0, 20), (20, 20, 24)),
        BX((0, 0, 0), (20, 20, 24)),
        (BX((0, 0, 20), (20, 20, 24)),),
        BX((0, 0, 20), (20, 20, 44)),
        (),
    )
    assert result is None


def test_collide_chain_completeness():
    """T14 : collide() suit la chaine contractuelle, dans l'ordre."""
    module = inspect.getmodule(bfk.collide)
    calls = []

    def spy(name, function):
        def wrapper(*args, **kwargs):
            calls.append(name)
            return function(*args, **kwargs)

        return wrapper

    originals = {
        name: getattr(module, name)
        for name in ("geometric_relation", "intersection_aabb", "solid_overlap", "collision_status")
    }
    try:
        for name, function in originals.items():
            setattr(module, name, spy(name, function))
        status = bfk.collide(hollow_brick(), P((0, 0, 0)), solid_brick(), P((0, 0, 16)))
    finally:
        for name, function in originals.items():
            setattr(module, name, function)

    assert status is bfk.CollisionStatus.PENETRATION
    assert calls == [
        "geometric_relation",
        "intersection_aabb",
        "solid_overlap",
        "collision_status",
    ]


# =============================================================================
# T10 / T13 — Immutabilite de l'etat (Sections I, J)
# =============================================================================


def test_immutable_state_snapshot():
    """T10 : ajouter une piece ne modifie jamais l'etat anterieur."""
    tolerance = TOL()
    parts_1 = {"A": brick("A", (0, 0, 0)), "B": brick("B", (0, 0, BRICK_H))}
    state_1 = bfk.assemble(parts_1, tolerance)

    graph_before = state_1.graph
    parts_before = state_1.graph.parts
    edges_before = state_1.graph.edges

    parts_2 = bfk.with_part(parts_1, brick("C", (0, 0, 2 * BRICK_H)))
    state_2 = bfk.assemble(parts_2, tolerance)

    assert len(parts_1) == 2, "le mapping d'entree a ete mute"
    assert state_1.graph is graph_before
    assert state_1.graph.parts is parts_before
    assert state_1.graph.edges is edges_before
    assert len(state_1.graph.parts) == 2
    assert len(state_2.graph.parts) == 3
    assert state_2 is not state_1


def test_state_deep_immutability():
    """T13 : Tuple partout, aucune mutation possible."""
    tolerance = TOL()
    placed = {"A": brick("A", (0, 0, 0)), "B": brick("B", (0, 0, BRICK_H))}
    state = bfk.assemble(placed, tolerance)

    assert isinstance(state.graph.parts, tuple)
    assert isinstance(state.graph.edges, tuple)
    for part in state.graph.parts:
        assert isinstance(part, tuple)
        assert isinstance(part[2], tuple)
    for edge in state.graph.edges:
        assert isinstance(edge, tuple)
        assert isinstance(edge[2], tuple)

    with pytest.raises(TypeError):
        state.graph.parts[0] = None

    with pytest.raises(dataclasses.FrozenInstanceError):
        state.graph = None

    with pytest.raises(dataclasses.FrozenInstanceError):
        state.graph.parts = ()

    with pytest.raises(TypeError):
        bfk.ConstructionGraph(parts=[], edges=())

    with pytest.raises(TypeError):
        bfk.ConstructionGraph(parts=(), edges=[])

    for forbidden in ("add_part", "insert", "remove", "append"):
        assert not hasattr(state, forbidden)
        assert not hasattr(state.graph, forbidden)

    # Un ConstructionState ne peut pas referencer un index mutable.
    with pytest.raises(TypeError):
        bfk.ConstructionState(
            graph=state.graph, spatial_snapshot=bfk.ReferenceSpatialIndex()
        )


# =============================================================================
# T11 — Arithmetique exacte (Sections B, C)
# =============================================================================


def test_exact_arithmetic_rotation():
    """T11 : rotation exacte dans Z^3, aucune contamination flottante."""
    local = V(3, 4, 5)

    direction = bfk.transform_local_direction_to_world(local, ROT_Z_90())
    assert direction == V(-4, 3, 5)
    for component in (direction.x, direction.y, direction.z):
        assert type(component) is int

    world = bfk.transform_local_to_world(local, P((7, -2, 11), ROT_Z_90()))
    assert world == V(3, 1, 16)
    for component in (world.x, world.y, world.z):
        assert type(component) is int

    # Une direction ne subit JAMAIS la translation de la pose.
    pose = P((7, -2, 11), ROT_Z_90())
    assert bfk.transform_local_direction_to_world(local, pose[1]) == V(-4, 3, 5)
    assert bfk.transform_local_to_world(local, pose) != direction

    # transform_aabb reste exact sous rotation.
    rotated = bfk.transform_aabb(BX((0, 0, 0), (40, 20, 24)), P((0, 0, 0), ROT_Z_90()))
    assert rotated == bfk.AABB(V(-20, 0, 0), V(0, 40, 24))
    for component in (rotated.min.x, rotated.min.y, rotated.min.z):
        assert type(component) is int

    # Les entiers non entiers sont refuses a la source.
    with pytest.raises(TypeError):
        bfk.LDUVector(1.0, 0, 0)
