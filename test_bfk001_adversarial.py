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

    # Chaque autorite de la chaine est franchie une fois et une seule ;
    # intersection_aabb est en outre reutilise a l'interieur de solid_overlap,
    # ce qui est legitime (primitive geometrique, pas autorite de statut).
    assert calls.count("geometric_relation") == 1
    assert calls.count("solid_overlap") == 1
    assert calls.count("collision_status") == 1

    order = []
    for name in calls:
        if name not in order:
            order.append(name)
    assert order == [
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


def test_angular_tolerance_is_ignored():
    """Section D.2 : max_angular_error_deg est present mais JAMAIS lu en BFK-001.

    L'oracle statue sur l'egalite exacte des normales opposees : faire varier la
    tolerance angulaire ne peut donc rien changer a son verdict.
    """
    a = brick("A", (0, 0, 0))
    b = brick("B", (0, 0, BRICK_H))
    male = males()[0]
    female = females()[0]

    verdicts = set()
    for angular in (0.0, 5.0, 90.0, 1e9):
        tolerance = bfk.ConnectorTolerance(
            max_position_error_ldu=0.5, max_angular_error_deg=angular
        )
        verdicts.add(
            bfk.evaluate_connector_pair(male, a.pose, female, b.pose, tolerance)
            is not None
        )
        # Normales non opposees (brique tournee de 90 deg autour de X) :
        # aucune tolerance angulaire ne peut sauver la paire.
        rotated = brick("B", (0, 0, BRICK_H), bfk.Orientation(1, 0, 0, 0, 0, -1, 0, 1, 0))
        assert (
            bfk.evaluate_connector_pair(male, a.pose, female, rotated.pose, tolerance)
            is None
        )
    assert verdicts == {True}, "la tolerance angulaire a influence l'oracle"


# =============================================================================
# Tolerance — decisions A.2 et D.2, valeur du systeme LEGO
# =============================================================================


def test_connector_tolerance_has_no_default():
    """A.2 : ConnectorTolerance est obligatoire, sans aucune valeur par defaut."""
    with pytest.raises(TypeError):
        bfk.ConnectorTolerance()
    with pytest.raises(TypeError):
        bfk.ConnectorTolerance(max_position_error_ldu=0.5)
    with pytest.raises(TypeError):
        bfk.ConnectorTolerance(max_angular_error_deg=0.0)

    # LEGO_TOLERANCE est une constante nommee, pas un defaut : rien ne l'injecte
    # implicitement dans l'oracle ni dans le pipeline de recherche.
    signature = inspect.signature(bfk.evaluate_connector_pair)
    assert signature.parameters["tolerance"].default is inspect.Parameter.empty


def test_tolerance_is_lattice_safe():
    """La tolerance LEGO est strictement equivalente a la coincidence exacte.

    Dans Z^3, deux sites de connexion distincts sont distants d'au moins 1 LDU.
    Une tolerance strictement inferieure a 1 LDU ne peut donc JAMAIS accepter
    autre chose qu'une coincidence parfaite : la propriete est verifiee, pas
    supposee.
    """
    tolerance = bfk.LEGO_TOLERANCE
    assert 0 < tolerance.max_position_error_ldu < bfk.MIN_LATTICE_SEPARATION_LDU
    assert tolerance.max_angular_error_deg == 0.0

    male = bfk.Connector("stud_male", V(10, 10, BRICK_H), V(0, 0, 1))
    female = bfk.Connector("stud_female", V(10, 10, 0), V(0, 0, -1))
    seated = P((0, 0, BRICK_H))

    assert bfk.evaluate_connector_pair(male, P(), female, seated, tolerance) is not None

    offsets = [
        (dx, dy, dz)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        for dz in (-1, 0, 1)
        if (dx, dy, dz) != (0, 0, 0)
    ]
    offsets += [
        (0, 0, bfk.PLATE_HEIGHT_LDU),        # une plate au-dessus
        (0, 0, -bfk.PLATE_HEIGHT_LDU),       # une plate en dessous
        (bfk.HALF_STUD_LDU, 0, 0),           # un demi-tenon (jumper)
        (0, bfk.HALF_STUD_LDU, 0),
        (bfk.STUD_PITCH_LDU, 0, 0),          # le tenon voisin
    ]
    for dx, dy, dz in offsets:
        pose = P((dx, dy, BRICK_H + dz))
        assert (
            bfk.evaluate_connector_pair(male, P(), female, pose, tolerance) is None
        ), f"bond fantome a l'ecart ({dx}, {dy}, {dz})"


# =============================================================================
# H3 — ce qui rend l'invariant verifiable plutot que declaratif
# =============================================================================


def test_bond_identity_is_required_for_h3():
    """Le stub litteral du contrat rendrait H3 VIDE DE SENS.

    `@dataclass(frozen=True) class PhysicalBond: pass` donne a toutes ses
    instances la meme valeur et le meme hash. Un registre d'emission accepterait
    alors n'importe quelle contrefacon des qu'un seul vrai bond y figure : H3
    passerait au vert en ne verifiant rien. L'identite d'objet n'est donc pas
    une preference d'implementation, c'est la condition de l'invariant.
    """
    from dataclasses import dataclass as _dataclass

    @_dataclass(frozen=True)
    class ContractStubBond:  # exactement le stub de la Section E.1
        pass

    registre = {ContractStubBond()}
    assert ContractStubBond() in registre, (
        "propriete a documenter : avec un dataclass sans champ, toute "
        "contrefacon est indistinguable d'un bond authentique"
    )

    # L'implementation reelle, elle, distingue.
    a = brick("A", (0, 0, 0))
    b = brick("B", (0, 0, BRICK_H))
    first = bfk.evaluate_connector_pair(males()[0], a.pose, females()[0], b.pose, TOL())
    second = bfk.evaluate_connector_pair(males()[0], a.pose, females()[0], b.pose, TOL())

    assert first is not None and second is not None
    assert first is not second, "chaque verdict positif frappe un jeton neuf"
    assert first != second, "un bond est un jeton, pas une valeur"
    assert bfk.is_oracle_issued(first) and bfk.is_oracle_issued(second)
    assert not bfk.is_oracle_issued(object.__new__(bfk.PhysicalBond))


def test_bond_copies_to_itself_and_refuses_serialization():
    """Copier un etat ne doit pas transformer ses liaisons en contrefacons."""
    import copy
    import pickle

    placed = {"A": brick("A", (0, 0, 0)), "B": brick("B", (0, 0, BRICK_H))}
    state = bfk.assemble(placed, TOL())
    bond = state.graph.edges[0][2][0]

    assert copy.copy(bond) is bond
    assert copy.deepcopy(bond) is bond
    # Le reflexe naturel du backtracking reste sur : H3 tient apres copie.
    assert bfk.check_h3_authority_integrity(copy.deepcopy(state).graph) == ()

    with pytest.raises(TypeError):
        pickle.dumps(bond)  # un bond relu d'un fichier serait une contrefacon


def test_graph_rejects_structural_fictions():
    """Un graphe ne peut pas affirmer une connexite qui n'existe pas."""
    placed = {"A": brick("A", (0, 0, 0)), "B": brick("B", (0, 0, BRICK_H))}
    state = bfk.assemble(placed, TOL())
    parts = state.graph.parts
    bonds = state.graph.edges[0][2]

    with pytest.raises(ValueError):  # extremite non declaree : H4/H5 sur une fiction
        bfk.ConstructionGraph(parts=parts, edges=(("A", "FANTOME", bonds),))

    with pytest.raises(ValueError):  # boucle sur soi
        bfk.ConstructionGraph(parts=parts, edges=(("A", "A", bonds),))

    with pytest.raises(ValueError):  # arete sans liaison : ne connecte rien
        bfk.ConstructionGraph(parts=parts, edges=(("A", "B", ()),))

    with pytest.raises(ValueError):  # arete dupliquee
        bfk.ConstructionGraph(
            parts=parts, edges=(("A", "B", bonds), ("B", "A", bonds))
        )

    with pytest.raises(ValueError):  # identifiant de piece duplique
        bfk.ConstructionGraph(parts=parts + (parts[0],), edges=())

    # Le graphe legitime, lui, passe.
    assert bfk.ConstructionGraph(parts=parts, edges=(("A", "B", bonds),))


def test_oracle_holds_on_unbounded_coordinates():
    """Z^3 n'est pas borne : l'oracle doit statuer a n'importe quelle echelle.

    math.sqrt() leve OverflowError au-dela d'environ 1e154. Le contrat promet
    une arithmetique exacte sur des entiers arbitraires : l'oracle ecarte donc
    d'abord par un calcul entier exact.
    """
    tolerance = TOL()
    male = bfk.Connector("stud_male", V(0, 0, 0), V(0, 0, 1))
    female = bfk.Connector("stud_female", V(0, 0, 0), V(0, 0, -1))
    astronomique = 10 ** 200

    assert (
        bfk.evaluate_connector_pair(
            male, P(), female, P((astronomique, 0, 0)), tolerance
        )
        is None
    )
    # Et a la meme echelle, une coincidence exacte reste une liaison.
    assert (
        bfk.evaluate_connector_pair(
            male,
            P((astronomique, astronomique, astronomique)),
            female,
            P((astronomique, astronomique, astronomique)),
            tolerance,
        )
        is not None
    )


def test_tolerance_rejects_non_finite_values():
    """Une tolerance infinie connecterait tout a tout."""
    with pytest.raises(ValueError):
        bfk.ConnectorTolerance(float("inf"), 0.0)
    with pytest.raises(ValueError):
        bfk.ConnectorTolerance(0.5, float("nan"))
    with pytest.raises(ValueError):
        bfk.ConnectorTolerance(-0.1, 0.0)


def test_collision_status_refuses_incoherent_input():
    """L'autorite de derivation refuse une entree qui se contredit."""
    piece = (BX((0, 0, 0), (1, 1, 1)),)

    with pytest.raises(ValueError):  # DISJOINT impose overlap None
        bfk.collision_status(bfk.GeometricRelation.DISJOINT, piece)
    with pytest.raises(ValueError):  # TOUCHING impose overlap None
        bfk.collision_status(bfk.GeometricRelation.TOUCHING, piece)
    with pytest.raises(ValueError):  # une partition vide vaut None, pas ()
        bfk.collision_status(bfk.GeometricRelation.OVERLAPPING, ())
    with pytest.raises(TypeError):
        bfk.collision_status(bfk.GeometricRelation.OVERLAPPING, [BX((0, 0, 0), (1, 1, 1))])

    assert (
        bfk.collision_status(bfk.GeometricRelation.OVERLAPPING, None)
        is bfk.CollisionStatus.CONTACT
    )
    assert (
        bfk.collision_status(bfk.GeometricRelation.OVERLAPPING, piece)
        is bfk.CollisionStatus.PENETRATION
    )


# =============================================================================
# Les decodeurs d'images sont le SEUL endroit qui lit des octets non fiables
# =============================================================================

import unittest


def _png_brut(largeur, hauteur, idat, profondeur=8, type_couleur=2):
    """Un PNG dont l'en-tete et la charge se contredisent librement."""
    import struct as _s
    return (b"\x89PNG\r\n\x1a\n"
            + _s.pack(">I", 13) + b"IHDR"
            + _s.pack(">IIBBBBB", largeur, hauteur, profondeur, type_couleur,
                      0, 0, 0) + b"\x00\x00\x00\x00"
            + _s.pack(">I", len(idat)) + b"IDAT" + idat + b"\x00\x00\x00\x00"
            + _s.pack(">I", 0) + b"IEND" + b"\x00\x00\x00\x00")


class TestUnEnTeteNeSeCroitPas(unittest.TestCase):
    """Treize octets d'en-tete decident de tout ce que le decodeur alloue.

    Rien n'oblige ces treize octets a dire la verite, et ce sont les SEULS
    octets de toute la chaine qui viennent d'un inconnu par le reseau. Avant
    cette borne : un PNG de deux cents octets annoncant 2147483647 carre
    faisait remonter une `zlib.error` hors contrat — dans le serveur, la
    connexion tombait sans un mot — et un JPEG de 171 octets annoncant
    32000x32000 occupait le processeur pendant des MINUTES.
    """

    def test_un_png_aux_dimensions_impossibles_est_refuse(self):
        import zlib as _z
        faux = _png_brut(2 ** 31 - 1, 2 ** 31 - 1, _z.compress(b"\x00" * 16))
        with self.assertRaises(ValueError) as capture:
            bfk.read_png(faux)
        self.assertIn("millions de pixels", str(capture.exception))

    def test_un_jpeg_aux_dimensions_impossibles_est_refuse_TOUT_DE_SUITE(self):
        import struct as _s
        import time as _t

        def segment(marqueur, charge):
            return (b"\xff" + bytes([marqueur])
                    + _s.pack(">H", len(charge) + 2) + charge)

        sof = _s.pack(">BHHB", 8, 32000, 32000, 1) + bytes([1, 0x11, 0])
        faux = (b"\xff\xd8"
                + segment(0xDB, b"\x00" + bytes([1] * 64))
                + segment(0xC0, sof)
                + segment(0xC4, b"\x00" + bytes([0, 0, 0, 12] + [0] * 12)
                          + bytes(range(12)))
                + segment(0xC4, b"\x10" + bytes([1] + [0] * 15) + bytes([0]))
                + segment(0xDA, bytes([1, 1, 0x00, 0, 63, 0]))
                + b"\x00" * 20 + b"\xff\xd9")
        depart = _t.perf_counter()
        with self.assertRaises(ValueError) as capture:
            bfk.read_jpeg_eighth(faux)
        # Le refus doit etre IMMEDIAT : c'est tout l'interet de le poser avant
        # l'allocation. Une seconde est deja mille fois trop.
        self.assertLess(_t.perf_counter() - depart, 1.0)
        self.assertIn("millions de pixels", str(capture.exception))

    def test_une_bombe_de_decompression_est_refusee(self):
        import zlib as _z
        # 50 Mo de zeros en quelques kilo-octets, dans un PNG qui n'annonce
        # que 64x64. Avant : decompresse en entier, puis accepte.
        charge = _z.compress(b"\x00" * (50 * 1024 * 1024), 9)
        self.assertLess(len(charge), 100_000, "la bombe doit etre petite")
        with self.assertRaises(ValueError) as capture:
            bfk.read_png(_png_brut(64, 64, charge))
        self.assertIn("depasse", str(capture.exception))

    def test_un_flux_zlib_corrompu_reste_dans_le_contrat(self):
        # `zlib.error` n'est pas une `ValueError` : elle traversait le module.
        with self.assertRaises(ValueError):
            bfk.read_png(_png_brut(8, 8, b"ceci n'est pas du zlib"))

    def test_les_dimensions_nulles_sont_refusees(self):
        import zlib as _z
        for largeur, hauteur in ((0, 8), (8, 0), (0, 0)):
            with self.assertRaises(ValueError):
                bfk.read_png(_png_brut(largeur, hauteur,
                                       _z.compress(b"\x00" * 16)))

    def test_une_photo_ordinaire_passe_toujours(self):
        # La borne ne doit refuser AUCUN appareil reel : 61 Mpx est le plus gros
        # capteur grand public, et il reste sous le plafond.
        from bfk001.imaging import PIXELS_MAXIMUM, _bornes_de_l_image
        self.assertGreater(PIXELS_MAXIMUM, 9504 * 6336,
                           "un plein format 61 Mpx doit passer")
        self.assertGreater(PIXELS_MAXIMUM, 8064 * 6048,
                           "un telephone 48 Mpx doit passer")
        _bornes_de_l_image(9504, 6336, "PNG")   # ne leve pas
        image = bfk.Image(6, 4, bytes([120, 30, 200] * 24))
        relu = bfk.read_png(bfk.write_png(image))
        self.assertEqual(relu.data, image.data,
                         "une image ordinaire traverse la borne inchangee")


# =============================================================================
# Elaguer les decoupes sans jamais rendre H2 aveugle
# =============================================================================


class TestLElagageDesVidesEstExact(unittest.TestCase):
    """`solid_overlap` ecarte les vides disjoints de la base. C'est PROUVABLE.

    `pieces` part de `(base,)` et `_subtract_box` ne rend que des sous-boites
    de son argument : par recurrence, tout morceau est inclus dans `base`. Un
    vide disjoint de `base` est donc disjoint de chaque morceau, et le passer
    dans la boucle ne peut rien retirer.

    L'enjeu n'est pas la vitesse mais le contraire : une optimisation qui
    rendrait H2 AVEUGLE serait le pire defaut possible de ce depot — un
    invariant vert qui ne veut rien dire. D'ou ces cas, construits pour que
    le vide qui compte soit noye parmi ceux qui ne comptent pas.
    """

    @staticmethod
    def boite(x0, y0, z0, x1, y1, z1):
        from bfk001.geometry import AABB, LDUVector
        return AABB(LDUVector(x0, y0, z0), LDUVector(x1, y1, z1))

    def loin(self, combien=220):
        """Des vides tres a l'ecart : ils ne peuvent rien retirer."""
        return tuple(self.boite(1000 + i * 10, 0, 0, 1005 + i * 10, 5, 5)
                     for i in range(combien))

    def setUp(self):
        from bfk001.collision import solid_overlap
        from bfk001.geometry import intersection_aabb
        self.recouvrement = solid_overlap
        self.intersection = intersection_aabb
        self.a = self.boite(0, 0, 0, 100, 100, 100)
        self.vide = self.boite(40, 40, 40, 60, 60, 60)

    def test_un_corps_loge_dans_le_vide_ne_penetre_pas(self):
        b = self.boite(45, 45, 45, 55, 55, 55)
        resultat = self.recouvrement(
            self.intersection(self.a, b), self.a,
            (self.vide,) + self.loin(), b, ())
        self.assertIsNone(resultat, "loge dans le vide : CONTACT, pas PENETRATION")

    def test_le_meme_vide_NOYE_parmi_220_inutiles_compte_toujours(self):
        import random
        b = self.boite(45, 45, 45, 55, 55, 55)
        melange = list(self.loin()) + [self.vide]
        random.Random(3).shuffle(melange)
        self.assertIsNone(
            self.recouvrement(self.intersection(self.a, b), self.a,
                              tuple(melange), b, ()),
            "l'ordre des vides ne doit rien changer")

    def test_un_corps_qui_DEBORDE_du_vide_est_toujours_vu(self):
        # Le cas qui compte : si l'elagage effacait le vide utile, on
        # trouverait plus de matiere ; s'il effacait la detection, moins.
        b = self.boite(45, 45, 45, 70, 55, 55)
        avec_bruit = self.recouvrement(
            self.intersection(self.a, b), self.a,
            (self.vide,) + self.loin(), b, ())
        sans_bruit = self.recouvrement(
            self.intersection(self.a, b), self.a, (self.vide,), b, ())
        self.assertIsNotNone(avec_bruit, "le debordement est une PENETRATION")
        self.assertEqual(
            sorted((r.min, r.max) for r in avec_bruit),
            sorted((r.min, r.max) for r in sans_bruit),
            "les vides lointains ne changent pas la region trouvee")

    def test_sans_le_vide_utile_la_penetration_est_franche(self):
        b = self.boite(45, 45, 45, 55, 55, 55)
        self.assertIsNotNone(
            self.recouvrement(self.intersection(self.a, b), self.a,
                              self.loin(), b, ()),
            "sans vide, un corps entierement dedans PENETRE")

    def test_un_vide_qui_touche_la_base_sans_volume_ne_retire_rien(self):
        # Contact de volume nul : `intersection_aabb` rend None, et retirer
        # une tranche d'epaisseur nulle ne retire aucune matiere. L'elagage
        # doit se comporter comme la boucle complete.
        b = self.boite(45, 45, 45, 55, 55, 55)
        base = self.intersection(self.a, b)
        tangent = self.boite(55, 45, 45, 65, 55, 55)   # colle a la face x=55
        avec = self.recouvrement(base, self.a, (tangent,), b, ())
        sans = self.recouvrement(base, self.a, (), b, ())
        self.assertEqual(
            sorted((r.min, r.max) for r in avec or ()),
            sorted((r.min, r.max) for r in sans or ()),
            "un vide tangent ne retire rien, elague ou non")


class TestDeuxCoinsValentHuit(unittest.TestCase):
    """`transform_aabb` ne transforme plus que deux coins. C'est EXACT.

    `Orientation` n'accepte que des coefficients dans {-1, 0, 1} avec
    M^T M = I : cela force exactement une valeur non nulle par ligne et par
    colonne — une permutation SIGNEE des axes. Chaque coordonnee de sortie
    vaut donc +/- une seule coordonnee d'entree, et ses extremes viennent des
    extremes de celle-la : `min` et `max`.

    Le raisonnement est court, ce qui le rend facile a croire a tort. Ces
    tests le verifient sur les 24 orientations plutot que sur deux.
    """

    def toutes_les_orientations(self):
        import itertools
        from bfk001.geometry import Orientation
        trouvees = []
        for coefficients in itertools.product((-1, 0, 1), repeat=9):
            try:
                trouvees.append(Orientation(*coefficients))
            except (ValueError, TypeError):
                pass
        return trouvees

    def test_le_noyau_n_accepte_exactement_que_les_24_rotations(self):
        # La demonstration repose entierement sur cette contrainte : si une
        # 25e orientation passait, le raccourci deviendrait faux.
        self.assertEqual(len(self.toutes_les_orientations()), 24)

    def test_deux_coins_donnent_le_meme_resultat_que_huit(self):
        import random
        from bfk001.geometry import (AABB, LDUVector, transform_aabb,
                                     transform_local_to_world)

        def par_huit(boite, pose):
            coins = [transform_local_to_world(LDUVector(x, y, z), pose)
                     for x in (boite.min.x, boite.max.x)
                     for y in (boite.min.y, boite.max.y)
                     for z in (boite.min.z, boite.max.z)]
            return AABB(
                LDUVector(min(c.x for c in coins), min(c.y for c in coins),
                          min(c.z for c in coins)),
                LDUVector(max(c.x for c in coins), max(c.y for c in coins),
                          max(c.z for c in coins)))

        tirage = random.Random(11)
        essais = 0
        for orientation in self.toutes_les_orientations():
            for _ in range(20):
                x, y, z = (tirage.randint(-200, 200) for _ in range(3))
                boite = AABB(
                    LDUVector(x, y, z),
                    LDUVector(x + tirage.randint(1, 80),
                              y + tirage.randint(1, 80),
                              z + tirage.randint(1, 80)))
                pose = (LDUVector(tirage.randint(-500, 500),
                                  tirage.randint(-500, 500),
                                  tirage.randint(-500, 500)), orientation)
                self.assertEqual(transform_aabb(boite, pose),
                                 par_huit(boite, pose))
                essais += 1
        self.assertEqual(essais, 24 * 20)


class TestIntersectionEtRelationNeDiventJamaisPasPareil(unittest.TestCase):
    """`intersection_aabb` ne passe plus par `geometric_relation`.

    Elle appliquait le critere en appelant la relation, puis recalculait les
    intervalles pour batir le resultat : deux fois le meme travail sur 2,7
    millions d'appels. Le critere est desormais ecrit sur place — donc il peut
    DERIVER, et c'est le seul risque de ce changement.
    """

    def test_les_deux_sont_d_accord_sur_quarante_mille_paires(self):
        import random
        from bfk001.geometry import (AABB, GeometricRelation, LDUVector,
                                     geometric_relation, intersection_aabb)

        tirage = random.Random(5)

        def boite():
            x, y, z = (tirage.randint(-40, 40) for _ in range(3))
            return AABB(LDUVector(x, y, z),
                        LDUVector(x + tirage.randint(0, 50),
                                  y + tirage.randint(0, 50),
                                  z + tirage.randint(0, 50)))

        desaccords = 0
        for _ in range(40000):
            a, b = boite(), boite()
            attendu = (geometric_relation(a, b)
                       is GeometricRelation.OVERLAPPING)
            if (intersection_aabb(a, b) is not None) != attendu:
                desaccords += 1
        self.assertEqual(desaccords, 0)

    def test_un_contact_de_volume_nul_ne_rend_rien(self):
        from bfk001.geometry import AABB, LDUVector, intersection_aabb
        a = AABB(LDUVector(0, 0, 0), LDUVector(10, 10, 10))
        for touche in (AABB(LDUVector(10, 0, 0), LDUVector(20, 10, 10)),
                       AABB(LDUVector(10, 10, 0), LDUVector(20, 20, 10)),
                       AABB(LDUVector(10, 10, 10), LDUVector(20, 20, 20))):
            self.assertIsNone(intersection_aabb(a, touche),
                              "face, arete ou sommet : volume nul")

    def test_elle_refuse_toujours_ce_qui_n_est_pas_un_AABB(self):
        from bfk001.geometry import AABB, LDUVector, intersection_aabb
        a = AABB(LDUVector(0, 0, 0), LDUVector(10, 10, 10))
        with self.assertRaises(TypeError):
            intersection_aabb(a, "pas une boite")
        with self.assertRaises(TypeError):
            intersection_aabb(None, a)


# =============================================================================
# Le memo de verdicts : il vit DANS le module qui porte H2, donc il se prouve
# =============================================================================


class TestMemoDeCollision:
    """Un memo faux ici ne casserait pas la chaine : il rendrait H2 vert.

    C'est la panne la plus grave que ce depot puisse produire — une mosaique
    declaree valide alors que deux pieces s'interpenetrent. Ces tests ne
    verifient donc pas que le memo est rapide, mais qu'il est INCAPABLE de
    changer un verdict.
    """

    @staticmethod
    def _boite(x0, y0, z0, x1, y1, z1):
        from bfk001.geometry import AABB, LDUVector
        return AABB(LDUVector(x0, y0, z0), LDUVector(x1, y1, z1))

    def _geometrie(self, decalage=(0, 0, 0), vides=()):
        from bfk001.collision import CollisionGeometry
        dx, dy, dz = decalage
        exterieur = self._boite(dx, dy, dz, dx + 40, dy + 40, dz + 24)
        return CollisionGeometry(
            exterieur,
            tuple(self._boite(dx + a, dy + b, dz + c, dx + d, dy + e, dz + f)
                  for a, b, c, d, e, f in vides),
        )

    def test_le_verdict_est_invariant_par_translation(self):
        """La propriete sur laquelle repose TOUT le memo. Si elle est fausse,
        le memo est faux."""
        from bfk001.collision import collide_world, oublier_les_verdicts
        vides = ((4, 4, 0, 16, 16, 20),)
        for dx, dy, dz in ((0, 0, 0), (1, 0, 0), (-7, 13, 5), (10**6, -10**6, 3)):
            oublier_les_verdicts()
            reference = collide_world(self._geometrie(vides=vides),
                                      self._geometrie((10, 10, 0), vides))
            oublier_les_verdicts()
            translate = collide_world(
                self._geometrie((dx, dy, dz), vides),
                self._geometrie((dx + 10, dy + 10, dz), vides))
            assert reference is translate, (dx, dy, dz)

    def test_memo_chaud_ou_froid_le_verdict_ne_change_jamais(self):
        """Differentiel sur un millier de situations tirees au hasard."""
        import random
        from bfk001.collision import (collide_world, oublier_les_verdicts,
                                      _status_from_world)
        from bfk001.geometry import geometric_relation

        def sans_memo(a, b):
            return _status_from_world(
                geometric_relation(a.exterior, b.exterior), a, b)

        alea = random.Random(20260829)
        vides_possibles = ((), ((4, 4, 0, 16, 16, 20),),
                           ((4, 4, 0, 16, 16, 20), (24, 24, 0, 36, 36, 20)))
        desaccords = 0
        oublier_les_verdicts()
        for _ in range(1000):
            a = self._geometrie(
                (alea.randint(-60, 60), alea.randint(-60, 60),
                 alea.randint(-48, 48)), alea.choice(vides_possibles))
            b = self._geometrie(
                (alea.randint(-60, 60), alea.randint(-60, 60),
                 alea.randint(-48, 48)), alea.choice(vides_possibles))
            if collide_world(a, b) is not sans_memo(a, b):
                desaccords += 1
        assert desaccords == 0

    def test_un_memo_chaud_de_CLEAR_ne_masque_pas_une_penetration(self):
        """Le scenario de panne : mille verdicts sains, puis un conflit reel."""
        from bfk001.collision import (CollisionStatus, collide_world,
                                      oublier_les_verdicts)
        oublier_les_verdicts()
        for i in range(1000):
            assert collide_world(
                self._geometrie((0, 0, 0)),
                self._geometrie((100 + i * 40, 0, 0))) is CollisionStatus.CLEAR
        assert collide_world(
            self._geometrie((0, 0, 0)),
            self._geometrie((10, 10, 0))) is CollisionStatus.PENETRATION

    def test_deux_formes_differentes_ne_partagent_jamais_un_numero(self):
        """La seule chose dont depend la justesse : un numero identifie une
        forme et une seule. L'oubli d'une forme n'en reattribue pas le numero.
        """
        from bfk001 import collision
        collision.oublier_les_verdicts()
        vus = {}
        for cote in range(1, 200):
            geometrie = collision.CollisionGeometry(
                self._boite(0, 0, 0, cote, 40, 24), ())
            numero, _ = geometrie.forme_et_origine()
            assert numero not in vus or vus[numero] == cote, (
                f"le numero {numero} a servi pour {vus.get(numero)} puis {cote}")
            vus[numero] = cote

    def test_l_oubli_d_une_forme_coute_un_calcul_jamais_un_verdict_faux(self):
        """On reduit la table des formes a presque rien et on verifie que les
        verdicts restent ceux du calcul direct."""
        from bfk001 import collision
        from bfk001.geometry import geometric_relation
        ancien = collision.FORMES_MEMORISEES
        collision.FORMES_MEMORISEES = 2
        try:
            collision.oublier_les_verdicts()
            for i in range(50):
                a = collision.CollisionGeometry(
                    self._boite(0, 0, 0, 20 + i, 40, 24), ())
                b = collision.CollisionGeometry(
                    self._boite(10, 10, 0, 50 + i, 50, 24), ())
                attendu = collision._status_from_world(
                    geometric_relation(a.exterior, b.exterior), a, b)
                assert collision.collide_world(a, b) is attendu
        finally:
            collision.FORMES_MEMORISEES = ancien
            collision.oublier_les_verdicts()

    def test_le_cache_d_instance_ne_touche_ni_l_egalite_ni_la_representation(self):
        """Le cache est pose sur une classe GELEE. Il ne doit rester qu'un
        cache : invisible a l'egalite, au hachage et a la representation."""
        from bfk001.collision import CollisionGeometry
        a = CollisionGeometry(self._boite(0, 0, 0, 40, 40, 24), ())
        b = CollisionGeometry(self._boite(0, 0, 0, 40, 40, 24), ())
        a.forme_et_origine()                       # pose le cache sur `a` seul
        assert a == b
        assert repr(a) == repr(b)
        assert dataclasses.astuple(a) == dataclasses.astuple(b)
        assert "forme" not in repr(a)

    def test_le_memo_est_borne(self):
        from bfk001 import collision
        ancien = collision.VERDICTS_MEMORISES
        collision.VERDICTS_MEMORISES = 16
        try:
            collision.oublier_les_verdicts()
            for i in range(200):
                collision.collide_world(self._geometrie((0, 0, 0)),
                                        self._geometrie((100 + i * 40, 0, 0)))
            assert collision.verdicts_memorises()["situations"] <= 16
        finally:
            collision.VERDICTS_MEMORISES = ancien
            collision.oublier_les_verdicts()

    def test_il_retrouve_vraiment_ce_qu_il_a_juge(self):
        """Sans ce test, le memo pourrait ne jamais servir sans qu'on le voie."""
        from bfk001 import collision
        collision.oublier_les_verdicts()
        for _ in range(100):
            collision.collide_world(self._geometrie((0, 0, 0)),
                                    self._geometrie((10, 10, 0)))
        etat = collision.verdicts_memorises()
        assert etat["juges"] == 100
        assert etat["retrouves"] == 99
        assert etat["situations"] == 1


class TestLesStructuresRestentSansDictionnaire:
    """`__slots__` sur les structures de base : 22 % de memoire en moins.

    Mesure sur un carre de 128 tenons, A/B alterne, empreintes identiques :
    223 Mo sans, 174 Mo avec. Ces classes se comptent par centaines de milliers
    — une seule pieces de 2x2 porte une pose, un AABB monde, huit connecteurs
    et une geometrie a neuf vides — et chaque `__dict__` vide pese plus de cent
    octets.

    Le retirer ne casserait aucun test fonctionnel : la memoire remonterait
    d'un quart en silence, et le plafond d'un conteneur hebergé baisserait
    d'autant. D'ou ce test, qui ne verifie rien d'autre que l'absence du
    dictionnaire.
    """

    def test_les_classes_les_plus_nombreuses_n_ont_pas_de_dictionnaire(self):
        from bfk001.collision import CollisionGeometry
        from bfk001.connectors import Connector
        from bfk001.geometry import AABB, LDUVector, Orientation
        from bfk001.search import PlacedPart

        vecteur = LDUVector(1, 2, 3)
        sans_dictionnaire = (
            vecteur,
            AABB(LDUVector(0, 0, 0), LDUVector(1, 1, 1)),
            Orientation(1, 0, 0, 0, 1, 0, 0, 0, 1),
            Connector("stud_male", vecteur, LDUVector(0, 0, 1)),
        )
        for objet in sans_dictionnaire:
            assert not hasattr(objet, "__dict__"), type(objet).__name__
            assert hasattr(type(objet), "__slots__"), type(objet).__name__

        assert "__slots__" in vars(PlacedPart)

        # `CollisionGeometry` en est volontairement exclue : elle garde son
        # numero de forme SUR L'INSTANCE (Section F.2 bis), ce qui demande un
        # dictionnaire. Elle est aussi cent fois moins nombreuse que les AABB
        # qu'elle contient — lesquelles, elles, ont bien des slots.
        geometrie = CollisionGeometry(
            AABB(LDUVector(0, 0, 0), LDUVector(40, 40, 24)), ())
        assert hasattr(geometrie, "__dict__")

    def test_geler_reste_geler(self):
        """slots ne doit pas avoir troque l'immuabilite contre de la memoire."""
        import dataclasses
        from bfk001.geometry import LDUVector
        vecteur = LDUVector(1, 2, 3)
        with pytest.raises(dataclasses.FrozenInstanceError):
            vecteur.x = 9

    def test_l_egalite_le_hachage_et_astuple_sont_intacts(self):
        from bfk001.geometry import AABB, LDUVector
        a = AABB(LDUVector(0, 0, 0), LDUVector(1, 2, 3))
        b = AABB(LDUVector(0, 0, 0), LDUVector(1, 2, 3))
        assert a == b
        assert hash(a) == hash(b)
        assert len({a, b}) == 1
        assert dataclasses.astuple(a) == ((0, 0, 0), (1, 2, 3))
        assert repr(a) == repr(b)


class TestLesFormesSontPartagees:
    """Onze formes, seize mille pieces : un objet par forme, pas par piece.

    Mesure sur un carre de 128 tenons, avant partage : 16 471 geometries
    locales pour ONZE valeurs distinctes, 16 471 tuples de connecteurs pour
    onze valeurs, 88 160 connecteurs pour 132 — et 551 984 `LDUVector` vivants,
    presque tous copies de la meme poignee de formes.

    Ces objets sont geles et ne contiennent que des champs geles : deux pieces
    du meme dessin peuvent partager le meme objet sans qu'aucun code puisse
    s'en apercevoir. A/B alterne, empreinte des livrables identique aux six
    executions : 177 Mo -> 128 Mo et 10,80 s -> 9,48 s.

    Ce test existe parce que retirer le memo ne casserait rien de visible : la
    memoire remonterait de 28 % en silence.
    """

    def test_deux_appels_rendent_le_MEME_objet_et_non_deux_egaux(self):
        from bfk001.lego import brick_connectors, brick_geometry
        assert brick_geometry(2, 2) is brick_geometry(2, 2)
        assert brick_connectors(2, 2) is brick_connectors(2, 2)

    def test_des_parametres_differents_rendent_des_objets_differents(self):
        """Un memo qui rendrait la meme piece pour deux tailles serait pire que
        pas de memo du tout."""
        from bfk001.lego import BRICK_HEIGHT_LDU, PLATE_HEIGHT_LDU, brick_geometry
        assert brick_geometry(2, 2) is not brick_geometry(2, 4)
        assert brick_geometry(2, 4) is not brick_geometry(4, 2)
        assert (brick_geometry(2, 2, BRICK_HEIGHT_LDU)
                is not brick_geometry(2, 2, PLATE_HEIGHT_LDU))
        assert (brick_geometry(2, 2, BRICK_HEIGHT_LDU, True)
                is not brick_geometry(2, 2, BRICK_HEIGHT_LDU, False))

    def test_la_geometrie_partagee_est_bien_celle_qu_on_attend(self):
        """Le partage ne doit rien changer a la geometrie elle-meme."""
        from bfk001.lego import (BRICK_HEIGHT_LDU, STUD_HEIGHT_LDU,
                                 STUD_PITCH_LDU, brick_geometry)
        geometrie = brick_geometry(2, 2)
        assert geometrie.exterior.min.as_tuple() == (0, 0, 0)
        assert geometrie.exterior.max.as_tuple() == (
            2 * STUD_PITCH_LDU, 2 * STUD_PITCH_LDU,
            BRICK_HEIGHT_LDU + STUD_HEIGHT_LDU)

    def test_une_mosaique_ne_fabrique_plus_qu_une_forme_par_dessin(self):
        """Le test qui compte : sur un modele reel, combien d'objets pour
        combien de valeurs ?"""
        from bfk001.catalog import place_at
        from bfk001.lego import STUD_PITCH_LDU

        geometries, connecteurs = [], []
        for i in range(200):
            placee, geometrie, _ = place_at(
                f"t{i}", "3070b", (i * STUD_PITCH_LDU, 0, 0), color_id=0)
            geometries.append(geometrie)
            connecteurs.append(placee.connectors)
        assert len({id(c) for c in connecteurs}) == 1, (
            "200 tuiles identiques ne doivent tenir qu'un tuple de connecteurs")
        assert len({id(g) for g in geometries}) == 1, (
            "200 tuiles identiques ne doivent tenir qu'une geometrie")
        assert len(set(geometries)) == 1

    def test_le_memo_est_borne(self):
        from bfk001.lego import brick_geometry
        assert brick_geometry.cache_info().maxsize == 256


class TestLesMemosTiennentAPlusieursFils:
    """L'atelier heberge est multi-fils, et son nombre de places est reglable.

    Les trois memos poses pour optimiser la chaine — verdicts, formes, dessins
    de pieces — sont des `OrderedDict` de module. `get` puis `move_to_end` sont
    deux appels : une eviction entre les deux est un `KeyError`. Et le compteur
    de numeros de forme est un lire-modifier-ecrire dont depend TOUTE la
    justesse du memo de collision.

    Ces tests ne prouvent pas l'absence de course — aucun test ne le peut. Ils
    echouent en revanche si quelqu'un retire les verrous et qu'une course se
    produit, et ils documentent ce qui serait alors casse.
    """

    @staticmethod
    def _geometrie(cote, decalage=0):
        from bfk001.collision import CollisionGeometry
        from bfk001.geometry import AABB, LDUVector
        return CollisionGeometry(
            AABB(LDUVector(decalage, 0, 0),
                 LDUVector(decalage + cote, 40, 24)), ())

    def test_huit_fils_ne_font_ni_planter_ni_mentir_le_memo_de_collision(self):
        import random
        import threading
        from bfk001 import collision
        from bfk001.geometry import geometric_relation

        def sans_memo(a, b):
            return collision._status_from_world(
                geometric_relation(a.exterior, b.exterior), a, b)

        # Bornes serrees a l'extreme : c'est la que les evictions se bousculent.
        formes, verdicts = (collision.FORMES_MEMORISEES,
                            collision.VERDICTS_MEMORISES)
        collision.FORMES_MEMORISEES = 4
        collision.VERDICTS_MEMORISES = 8
        collision.oublier_les_verdicts()
        incidents, desaccords = [], []

        def travail(graine):
            alea = random.Random(graine)
            try:
                for _ in range(400):
                    a = self._geometrie(alea.choice((20, 40, 60)),
                                        alea.randint(-80, 80))
                    b = self._geometrie(alea.choice((20, 40, 60)),
                                        alea.randint(-80, 80))
                    if collision.collide_world(a, b) is not sans_memo(a, b):
                        desaccords.append((a, b))
            except Exception as raison:          # pragma: no cover - la panne
                incidents.append(repr(raison))

        try:
            fils = [threading.Thread(target=travail, args=(i,))
                    for i in range(8)]
            for fil in fils:
                fil.start()
            for fil in fils:
                fil.join(timeout=120)
            assert incidents == [], f"le memo a plante : {incidents[:2]}"
            assert desaccords == [], "le memo a rendu un verdict faux"
        finally:
            collision.FORMES_MEMORISEES = formes
            collision.VERDICTS_MEMORISES = verdicts
            collision.oublier_les_verdicts()

    def test_deux_formes_ne_partagent_pas_un_numero_meme_a_douze_fils(self):
        """Le cas qui rendrait le memo FAUX plutot que cassant : deux fils qui
        lisent le meme numero avant de l'ecrire l'attribueraient a deux formes
        differentes, et une paire recevrait le verdict d'une autre."""
        import threading
        from bfk001 import collision

        collision.oublier_les_verdicts()
        depart = threading.Barrier(12)
        resultats = [None] * 12

        def travail(indice):
            depart.wait()
            resultats[indice] = [
                (self._geometrie(1000 + indice * 200 + k).forme_et_origine()[0],
                 1000 + indice * 200 + k)
                for k in range(200)
            ]

        fils = [threading.Thread(target=travail, args=(i,)) for i in range(12)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join(timeout=120)

        par_numero = {}
        for vus in resultats:
            for numero, cote in vus or ():
                assert par_numero.get(numero, cote) == cote, (
                    f"le numero {numero} a servi pour deux formes : "
                    f"{par_numero[numero]} et {cote}")
                par_numero[numero] = cote
        assert len(par_numero) == 12 * 200
        collision.oublier_les_verdicts()

    def test_le_memo_de_dessins_tient_a_plusieurs_fils(self):
        import threading
        from bfk001 import booklet

        memo = booklet.MEMO_DESSINS
        booklet.MEMO_DESSINS = 2          # eviction a chaque appel ou presque
        incidents = []

        def travail(graine):
            try:
                for i in range(12):
                    booklet.render_piece("3070b", (200, 30 + i, 40),
                                         echelle=6.0 + (graine % 3))
            except Exception as raison:      # pragma: no cover - la panne
                incidents.append(repr(raison))

        try:
            fils = [threading.Thread(target=travail, args=(i,))
                    for i in range(6)]
            for fil in fils:
                fil.start()
            for fil in fils:
                fil.join(timeout=120)
            assert incidents == [], f"le memo de dessins a plante : {incidents[:2]}"
        finally:
            booklet.MEMO_DESSINS = memo
            booklet._MEMO_PIECES.clear()

    def test_les_verrous_sont_bien_la(self):
        """Sans ce test, un verrou retire par distraction ne ferait echouer
        aucun des trois precedents une fois sur mille."""
        import threading
        from bfk001 import booklet, collision
        from bfk001 import imaging
        assert isinstance(collision._VERROU, type(threading.Lock()))
        assert isinstance(booklet._VERROU_MEMO, type(threading.Lock()))
        assert isinstance(imaging._VERROU_REDUCTION, type(threading.Lock()))

    def test_le_memo_de_reduction_tient_a_plusieurs_fils(self):
        """Celui-ci ne peut pas mentir — reference faible et verification
        d'identite — mais il peut planter comme les autres."""
        import threading
        import bfk001 as bfk
        from bfk001 import imaging

        memo = imaging.MEMO_REDUCTIONS
        imaging.MEMO_REDUCTIONS = 1
        images = [bfk.Image(24, 24, bytes((i * 7 + j) % 256
                                          for j in range(24 * 24 * 3)))
                  for i in range(4)]
        incidents = []

        def travail(graine):
            try:
                for i in range(20):
                    imaging.resample_box(images[(graine + i) % 4], 8, 8)
            except Exception as raison:      # pragma: no cover - la panne
                incidents.append(repr(raison))

        try:
            fils = [threading.Thread(target=travail, args=(i,))
                    for i in range(6)]
            for fil in fils:
                fil.start()
            for fil in fils:
                fil.join(timeout=120)
            assert incidents == [], f"le memo de reduction a plante : {incidents[:2]}"
        finally:
            imaging.MEMO_REDUCTIONS = memo
            imaging._MEMO_REDUCTION.clear()
