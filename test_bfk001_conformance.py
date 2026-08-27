"""
BFK-001 v3.3.2 — Conformite par tirage aleatoire (graine fixe).

Les suites precedentes verifient des fixtures choisies : elles prouvent que le
noyau se comporte bien la ou on l'a regarde. Celle-ci attaque les proprietes
elles-memes sur des configurations tirees au sort, y compris absurdes
(pieces qui s'interpenetrent, briques posees sous le sol, rotations
arbitraires). Une propriete qui survit a plusieurs centaines de tirages n'est
plus une intention.

Graine fixe : un echec est reproductible a l'identique.
"""

from __future__ import annotations

import random

import pytest

import bfk001_kernel as bfk

SEED = 20260825
GRID = 6  # cote du domaine de tirage pour les tests de partition
CONNECTOR_BUDGET = 200  # borne le cout de l'audit H1, quadratique par nature


def V(x, y, z):
    return bfk.LDUVector(x, y, z)


def BX(lo, hi):
    return bfk.AABB(V(*lo), V(*hi))


def random_box(rng, span=GRID):
    """Boite aleatoire a coordonnees entieres, negatives comprises.

    Le domaine traverse volontairement l'origine : c'est la que les divisions
    entieres et les decoupes changent de signe.
    """
    lo = [rng.randrange(-span, span) for _ in range(3)]
    hi = [value + rng.randrange(1, span + 1) for value in lo]
    return BX(tuple(lo), tuple(hi))


def unit_cells(aabb):
    """Cellules unitaires strictement interieures a l'AABB.

    Les coordonnees etant entieres, une boite est exactement l'union de ses
    cellules unitaires : la comparaison au niveau cellule est EXACTE, ce n'est
    pas un echantillonnage.
    """
    return {
        (x, y, z)
        for x in range(aabb.min.x, aabb.max.x)
        for y in range(aabb.min.y, aabb.max.y)
        for z in range(aabb.min.z, aabb.max.z)
    }


def random_state(rng, part_count):
    """Assemblage tire au sort : references, positions, rotations.

    Le tirage n'est pas uniforme, et c'est deliberé : deux tiers des pieces
    sont posees sur la face superieure d'une piece deja placee — c'est ce qui
    produit de vrais empilements, donc de vrais bonds a auditer. Le tiers
    restant tombe n'importe ou, dans n'importe laquelle des 24 rotations, pour
    que les cas absurdes soient represents eux aussi : briques couchees,
    retournees, enfoncees dans le sol, interpenetrees.
    """
    design_ids = sorted(bfk.CATALOG)
    parts, geometries = {}, {}
    sites = [(0, 0, 0)]  # faces superieures disponibles
    budget = CONNECTOR_BUDGET

    for index in range(part_count):
        part_id = f"P{index}"
        # L'audit H1 est quadratique EN CONNECTEURS, par conception : il ne
        # presume rien de ce qu'il verifie. Une seule plate 16x16 en apporte
        # 512 et suffit a faire exploser le cout. On borne donc l'etat tire,
        # pas la rigueur de l'audit.
        #
        # Le tirage regarde le budget AVANT de choisir. Tirer a l'aveugle puis
        # renoncer marchait tant que le catalogue etait fait de petites pieces ;
        # depuis qu'il contient des plates 8x8, l'aveugle renoncait presque a
        # chaque fois et l'etat tire ne contenait plus assez de liaisons pour
        # que l'audit ait quoi que ce soit a auditer.
        abordables = [
            d for d in design_ids
            if 2 * bfk.CATALOG[d].studs_x * bfk.CATALOG[d].studs_y <= budget
        ]
        if not abordables:
            break
        design_id = rng.choice(abordables)
        definition = bfk.CATALOG[design_id]
        budget -= 2 * definition.studs_x * definition.studs_y
        height = definition.body_height_ldu

        if rng.randrange(3):  # deux fois sur trois : pose alignee sur un site
            x, y, z = rng.choice(sites)
            orientation = rng.choice(UPRIGHT)
            translation = (
                x + bfk.STUD_PITCH_LDU * rng.randrange(-1, 2),
                y + bfk.STUD_PITCH_LDU * rng.randrange(-1, 2),
                z,
            )
        else:  # une fois sur trois : n'importe ou, n'importe comment
            orientation = rng.choice(bfk.all_rotations())
            translation = (
                bfk.STUD_PITCH_LDU * rng.randrange(-2, 3),
                bfk.STUD_PITCH_LDU * rng.randrange(-2, 3),
                bfk.PLATE_HEIGHT_LDU * rng.randrange(0, 6),
            )

        placed, geometry, _ = bfk.place(
            part_id, design_id, translation, orientation=orientation
        )
        parts[part_id] = placed
        geometries[part_id] = geometry
        sites.append((translation[0], translation[1], translation[2] + height))

    return parts, geometries


UPRIGHT = tuple(bfk.rotation_z(quarter) for quarter in range(4))


# =============================================================================
# H1 — la recherche acceleree ne perd jamais un bond
# =============================================================================


def test_h1_holds_on_random_states():
    rng = random.Random(SEED)
    tolerance = bfk.LEGO_TOLERANCE
    reference = bfk.ReferenceSearchApproximation()
    lattice = bfk.LatticeSearchApproximation()

    states_with_bonds = 0
    for _ in range(40):
        parts, _ = random_state(rng, rng.randrange(2, 7))
        index = bfk.build_index(parts)

        physical = bfk.physical_pairs(parts, tolerance)
        if physical:
            states_with_bonds += 1

        assert physical <= set(reference.find_candidate_pairs(index, parts, tolerance))
        assert physical <= set(lattice.find_candidate_pairs(index, parts, tolerance))

        # Meme graphe, quelle que soit la recherche employee.
        by_reference = bfk.assemble(parts, tolerance)
        by_lattice = bfk.assemble(parts, tolerance, search=lattice)
        assert [(a, b, len(x)) for a, b, x in by_reference.graph.edges] == [
            (a, b, len(x)) for a, b, x in by_lattice.graph.edges
        ]
        assert bfk.check_h3_authority_integrity(by_lattice.graph) == ()

    assert states_with_bonds >= 5, "tirage degenere : presque aucun bond teste"


# =============================================================================
# Section F — l'autorite geometrique, propriete par propriete
# =============================================================================


def test_solid_overlap_partition_is_exact_on_random_boxes():
    """Union exacte, interieurs disjoints, aucun morceau de volume nul."""
    rng = random.Random(SEED + 1)
    non_empty = 0

    for _ in range(800):
        solid_a = random_box(rng)
        solid_b = random_box(rng)
        voids_a = tuple(random_box(rng) for _ in range(rng.randrange(0, 3)))
        voids_b = tuple(random_box(rng) for _ in range(rng.randrange(0, 3)))
        intersection = bfk.intersection_aabb(solid_a, solid_b)
        if intersection is None:
            continue

        pieces = bfk.solid_overlap(intersection, solid_a, voids_a, solid_b, voids_b)

        # Verite calculee independamment, cellule par cellule.
        expected = unit_cells(intersection) & unit_cells(solid_a) & unit_cells(solid_b)
        for void in voids_a + voids_b:
            expected -= unit_cells(void)

        if not expected:
            assert pieces is None, "region vide : None attendu, jamais un tuple vide"
            continue

        non_empty += 1
        assert pieces is not None and len(pieces) > 0
        covered = set()
        for piece in pieces:
            cells = unit_cells(piece)
            assert cells, "morceau de volume nul interdit"
            assert not (covered & cells), "interieurs non disjoints"
            covered |= cells
        assert covered == expected, "partition inexacte"

    assert non_empty >= 60, "tirage degenere : trop peu de regions non vides"


def test_collide_is_symmetric_and_consistent():
    """collide(a, b) == collide(b, a) : sinon H2 dependrait de l'ordre d'iteration."""
    rng = random.Random(SEED + 2)
    seen = set()

    for _ in range(300):
        geometry_a = bfk.CollisionGeometry(
            random_box(rng), tuple(random_box(rng) for _ in range(rng.randrange(0, 3)))
        )
        geometry_b = bfk.CollisionGeometry(
            random_box(rng), tuple(random_box(rng) for _ in range(rng.randrange(0, 3)))
        )
        pose_a = (V(rng.randrange(-4, 5), rng.randrange(-4, 5), rng.randrange(-4, 5)),
                  rng.choice(bfk.all_rotations()))
        pose_b = (V(rng.randrange(-4, 5), rng.randrange(-4, 5), rng.randrange(-4, 5)),
                  rng.choice(bfk.all_rotations()))

        status = bfk.collide(geometry_a, pose_a, geometry_b, pose_b)
        assert status is bfk.collide(geometry_b, pose_b, geometry_a, pose_a)
        seen.add(status)

        relation = bfk.geometric_relation(
            bfk.transform_aabb(geometry_a.exterior, pose_a),
            bfk.transform_aabb(geometry_b.exterior, pose_b),
        )
        if relation is bfk.GeometricRelation.DISJOINT:
            assert status is bfk.CollisionStatus.CLEAR
        else:
            assert status is not bfk.CollisionStatus.CLEAR

    assert seen == set(bfk.CollisionStatus), "les trois statuts doivent etre atteints"


def test_grid_index_query_is_exhaustive():
    """La requete de la grille est un sur-ensemble EXACT des voisins.

    C'est la propriete sur laquelle repose l'elagage de H2 : si elle tombe, une
    penetration peut passer inapercue.
    """
    rng = random.Random(SEED + 3)

    for _ in range(60):
        boxes = {}
        grid = bfk.GridSpatialIndex(cell_size_ldu=rng.choice((1, 3, 8, 40)))
        for index in range(rng.randrange(1, 12)):
            part_id = f"P{index}"
            low = V(
                rng.randrange(-40, 40), rng.randrange(-40, 40), rng.randrange(-40, 40)
            )
            box = bfk.AABB(
                low,
                V(
                    low.x + rng.randrange(1, 40),
                    low.y + rng.randrange(1, 40),
                    low.z + rng.randrange(1, 40),
                ),
            )
            boxes[part_id] = box
            grid.insert(part_id, box)

        region = BX((-20, -20, -20), (20, 20, 20))
        returned = set(grid.query(region))
        neighbours = {
            part_id
            for part_id, box in boxes.items()
            if bfk.geometric_relation(box, region) is not bfk.GeometricRelation.DISJOINT
        }
        assert neighbours <= returned, "requete non exhaustive : elagage dangereux"

        removed = next(iter(boxes))
        grid.remove(removed)
        assert removed not in set(grid.query(region))


# =============================================================================
# Sections B / C — arithmetique exacte sous rotation quelconque
# =============================================================================


def test_transforms_round_trip_and_preserve_volume():
    rng = random.Random(SEED + 4)
    rotations = bfk.all_rotations()

    for _ in range(300):
        point = V(rng.randrange(-500, 500), rng.randrange(-500, 500), rng.randrange(-500, 500))
        pose = (
            V(rng.randrange(-200, 200), rng.randrange(-200, 200), rng.randrange(-200, 200)),
            rng.choice(rotations),
        )
        world = bfk.transform_local_to_world(point, pose)
        assert bfk.transform_world_to_local(world, pose) == point
        for component in (world.x, world.y, world.z):
            assert type(component) is int

        box = random_box(rng, span=40)
        transformed = bfk.transform_aabb(box, pose)
        extents = lambda aabb: sorted(  # noqa: E731
            (aabb.max.x - aabb.min.x, aabb.max.y - aabb.min.y, aabb.max.z - aabb.min.z)
        )
        assert extents(transformed) == extents(box), "rotation dilatante"

        # Une normale ne subit jamais la translation, quelle que soit la pose.
        normal = rng.choice(
            (V(1, 0, 0), V(-1, 0, 0), V(0, 1, 0), V(0, -1, 0), V(0, 0, 1), V(0, 0, -1))
        )
        direction = bfk.transform_local_direction_to_world(normal, pose[1])
        assert sorted(abs(value) for value in direction.as_tuple()) == [0, 0, 1]


def test_oracle_verdict_is_invariant_under_rigid_motion():
    """Deplacer tout l'assemblage ne change aucun verdict mecanique.

    Propriete fondamentale d'un noyau de CAO : la physique ne depend pas de
    l'endroit ou l'on a pose le repere.
    """
    rng = random.Random(SEED + 5)
    tolerance = bfk.LEGO_TOLERANCE

    for _ in range(20):
        parts, _ = random_state(rng, rng.randrange(2, 5))
        reference_bonds = len(bfk.physical_pairs(parts, tolerance))

        shift = V(
            bfk.STUD_PITCH_LDU * rng.randrange(-10, 11),
            bfk.STUD_PITCH_LDU * rng.randrange(-10, 11),
            bfk.BRICK_HEIGHT_LDU * rng.randrange(-10, 11),
        )
        moved = {
            part_id: bfk.PlacedPart(
                part_id=part_id,
                pose=(part.pose[0] + shift, part.pose[1]),
                aabb=bfk.AABB(part.aabb.min + shift, part.aabb.max + shift),
                connectors=part.connectors,
            )
            for part_id, part in parts.items()
        }
        assert len(bfk.physical_pairs(moved, tolerance)) == reference_bonds


def test_h4_par_composantes_rend_exactement_ce_que_rendait_le_parcours_par_piece():
    """H4 se calculait par un parcours du graphe PAR PIECE : n parcours de n
    pieces, donc un cout quadratique la ou une seule passe suffit. Les
    composantes connexes ne dependent pas de la piece par laquelle on
    interroge.

    Le remplacement n'a d'interet que s'il rend EXACTEMENT la meme chose,
    ordre des violations compris — c'est ce que ce tirage verifie, sur des
    graphes ou tout se produit : composantes multiples, pieces isolees,
    fondations absentes, fondations partout.
    """
    from bfk001.validation import (InvariantViolation, _adjacency, _component,
                                   check_h4_floating)

    class Graphe:
        def __init__(self, parts, edges):
            self.parts, self.edges = parts, edges

    def par_piece(graph, founded_part_ids):
        adjacency = _adjacency(graph)
        founded = set(founded_part_ids)
        return tuple(
            InvariantViolation("H4_FLOATING", f"piece flottante : {part_id}")
            for part_id, _, _ in graph.parts
            if part_id not in founded
            and not (_component(adjacency, part_id) & founded)
        )

    alea = random.Random(SEED)
    vus_flottants = vus_sains = 0
    for _ in range(300):
        n = alea.randint(1, 22)
        parts = tuple((f"p{i}", None, None) for i in range(n))
        # Densite tiree elle aussi : tantot un graphe eclate, tantot connexe.
        densite = alea.choice((0.0, 0.06, 0.15, 0.4))
        edges = tuple(
            (f"p{i}", f"p{j}", (object(),) if alea.random() < 0.9 else ())
            for i in range(n) for j in range(i + 1, n)
            if alea.random() < densite
        )
        graphe = Graphe(parts, edges)
        fondees = tuple(f"p{i}" for i in range(n) if alea.random() < 0.25)

        attendu = par_piece(graphe, fondees)
        obtenu = check_h4_floating(graphe, fondees)
        assert [v.detail for v in attendu] == [v.detail for v in obtenu]
        assert [v.invariant for v in attendu] == [v.invariant for v in obtenu]
        vus_flottants += bool(obtenu)
        vus_sains += not obtenu

    # Un tirage qui ne produirait jamais de violation ne prouverait rien.
    assert vus_flottants > 20 and vus_sains > 20
