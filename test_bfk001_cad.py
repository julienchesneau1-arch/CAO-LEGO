"""
BFK-001 v3.3.2 — Couche CAO : rotations, recherche rapide, pose incrementale,
verdict de placement, persistance.

Tout ce qui est teste ici est HORS CONTRAT : ce sont les briques manquantes
entre le noyau et un logiciel de conception assistee. Aucune n'emet de jugement
propre — chacune delegue aux autorites du contrat, et c'est precisement ce que
ces tests verifient.
"""

from __future__ import annotations

import json

import pytest

import bfk001_kernel as bfk

BRICK_H = bfk.BRICK_HEIGHT_LDU
TOP = bfk.BRICK_HEIGHT_LDU + bfk.STUD_HEIGHT_LDU


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
    return bfk.LEGO_TOLERANCE


def volume(aabb):
    return (
        (aabb.max.x - aabb.min.x)
        * (aabb.max.y - aabb.min.y)
        * (aabb.max.z - aabb.min.z)
    )


def wall():
    """Mur croise : 5x5 briques au sol, 4x4 briques decalees d'un tenon dessus."""
    parts = {}
    for i in range(5):
        for j in range(5):
            name = f"L{i}{j}"
            parts[name] = bfk.place_brick(name, (40 * i, 40 * j, 0))
    for i in range(4):
        for j in range(4):
            name = f"U{i}{j}"
            parts[name] = bfk.place_brick(name, (40 * i + 20, 40 * j + 20, BRICK_H))
    return parts


def geometries_for(placed_parts):
    return {part_id: bfk.brick_geometry(2, 2) for part_id in placed_parts}


# =============================================================================
# Les 24 rotations (Section C, extension)
# =============================================================================


def test_rotation_group_is_exactly_the_24_rotations():
    rotations = bfk.all_rotations()
    assert len(rotations) == 24
    assert len(set(rotations)) == 24

    identity = bfk.Orientation.identity()
    assert identity in rotations
    for rotation in rotations:
        assert rotation.determinant() == 1
        assert rotation.compose(rotation.inverse()) == identity
        assert rotation.inverse() in rotations
        for other in rotations:
            assert rotation.compose(other) in rotations, "groupe non ferme"


def test_named_rotations_are_consistent():
    identity = bfk.Orientation.identity()
    for quarter_turn, half_turn, three_quarters, axis in (
        (bfk.ROT_X_90, bfk.ROT_X_180, bfk.ROT_X_270, bfk.rotation_x),
        (bfk.ROT_Y_90, bfk.ROT_Y_180, bfk.ROT_Y_270, bfk.rotation_y),
        (bfk.ROT_Z_90, bfk.ROT_Z_180, bfk.ROT_Z_270, bfk.rotation_z),
    ):
        assert axis(1) == quarter_turn
        assert axis(2) == half_turn
        assert axis(3) == three_quarters
        assert axis(4) == identity
        assert axis(-1) == three_quarters
        assert quarter_turn.compose(three_quarters) == identity

    assert bfk.ROT_Z_90.apply(V(3, 4, 5)) == V(-4, 3, 5)
    assert bfk.ROT_X_90.apply(V(3, 4, 5)) == V(3, -5, 4)
    assert bfk.ROT_Y_90.apply(V(3, 4, 5)) == V(5, 4, -3)


def test_pose_inversion_round_trips_under_every_rotation():
    point = V(37, -19, 53)
    for rotation in bfk.all_rotations():
        pose = (V(7, -2, 11), rotation)
        world = bfk.transform_local_to_world(point, pose)
        assert bfk.transform_world_to_local(world, pose) == point

        inverse = bfk.invert_pose(pose)
        assert bfk.compose_poses(pose, inverse) == (V(0, 0, 0), bfk.Orientation.identity())
        assert bfk.transform_local_to_world(world, inverse) == point

        # Une rotation preserve exactement le volume : aucune dilatation cachee.
        box = BX((0, 0, 0), (40, 20, 24))
        assert volume(bfk.transform_aabb(box, pose)) == volume(box)


def test_rotated_brick_still_clutches():
    """Une brique 2x2 tournee d'un quart de tour s'empile a l'identique."""
    tolerance = TOL()
    geometry = bfk.brick_geometry(2, 2)
    lower = bfk.place_brick("A", (0, 0, 0))
    upper = bfk.place_brick("B", (40, 0, BRICK_H), orientation=bfk.ROT_Z_90)

    assert bfk.collide(geometry, lower.pose, geometry, upper.pose) is bfk.CollisionStatus.CONTACT

    placed = {"A": lower, "B": upper}
    state = bfk.assemble(placed, tolerance)
    assert [(a, b, len(bonds)) for a, b, bonds in state.graph.edges] == [("A", "B", 4)]
    report = bfk.validate(state.graph, placed, geometries_for(placed), tolerance)
    assert report.ok, report.violations


# =============================================================================
# Recherche acceleree (Section H.4)
# =============================================================================


def test_lattice_search_is_complete_and_far_smaller():
    placed = wall()
    tolerance = TOL()
    index = bfk.build_index(placed)

    reference = set(
        bfk.ReferenceSearchApproximation().find_candidate_pairs(index, placed, tolerance)
    )
    fast = set(
        bfk.LatticeSearchApproximation().find_candidate_pairs(index, placed, tolerance)
    )
    physical = bfk.physical_pairs(placed, tolerance)

    assert physical, "fixture invalide : aucun bond"
    assert physical <= fast, "H1 viole par la recherche acceleree"
    assert fast <= reference
    assert len(fast) * 10 < len(reference), "aucun gain d'echelle mesurable"

    # H1 formel, via le validateur, sur les deux implementations.
    assert bfk.check_h1_search_coverage(placed, tolerance) == ()
    assert (
        bfk.check_h1_search_coverage(
            placed, tolerance, search=bfk.LatticeSearchApproximation()
        )
        == ()
    )


def test_lattice_search_yields_the_same_graph():
    placed = wall()
    tolerance = TOL()

    reference_state = bfk.assemble(placed, tolerance)
    fast_state = bfk.assemble(
        placed, tolerance, search=bfk.LatticeSearchApproximation()
    )

    assert [
        (a, b, len(bonds)) for a, b, bonds in reference_state.graph.edges
    ] == [(a, b, len(bonds)) for a, b, bonds in fast_state.graph.edges]

    report = bfk.validate(
        fast_state.graph,
        placed,
        geometries_for(placed),
        tolerance,
        search=bfk.LatticeSearchApproximation(),
    )
    assert report.ok, report.violations


def test_lattice_search_handles_wide_tolerances():
    """Marge non nulle, puis repli sur la reference : H1 tient dans les deux cas."""
    placed = wall()
    index = bfk.build_index(placed)

    # marge = 1 : 27 cellules balayees, bien moins que le nombre de connecteurs.
    wide = bfk.ConnectorTolerance(max_position_error_ldu=1.0, max_angular_error_deg=0.0)
    fast = set(bfk.LatticeSearchApproximation().find_candidate_pairs(index, placed, wide))
    assert bfk.physical_pairs(placed, wide) <= fast

    # marge enorme : le balayage couterait plus que la reference -> repli.
    huge = bfk.ConnectorTolerance(max_position_error_ldu=100.0, max_angular_error_deg=0.0)
    small = {name: placed[name] for name in ("L00", "L01", "U00")}
    index_small = bfk.build_index(small)
    fallback = set(
        bfk.LatticeSearchApproximation().find_candidate_pairs(index_small, small, huge)
    )
    reference = set(
        bfk.ReferenceSearchApproximation().find_candidate_pairs(index_small, small, huge)
    )
    assert fallback == reference
    assert bfk.physical_pairs(small, huge) <= fallback


# =============================================================================
# Pose incrementale
# =============================================================================


def test_add_part_matches_full_assembly_and_preserves_bond_identity():
    tolerance = TOL()
    initial = {"A": bfk.place_brick("A", (0, 0, 0))}
    state = bfk.assemble(initial, tolerance)

    state, parts = bfk.add_part(state, initial, bfk.place_brick("B", (0, 0, BRICK_H)), tolerance)
    bonds_after_first = state.graph.edges[0][2]

    state, parts = bfk.add_part(
        state, parts, bfk.place_brick("C", (0, 0, 2 * BRICK_H)), tolerance
    )

    # Structure identique a un assemblage complet.
    complete = bfk.assemble(parts, tolerance)
    assert [(a, b, len(x)) for a, b, x in state.graph.edges] == [
        (a, b, len(x)) for a, b, x in complete.graph.edges
    ]

    # Les bonds A-B n'ont pas ete re-emis : meme objets, trace d'audit stable.
    assert state.graph.edges[0][2] is bonds_after_first
    assert all(bfk.is_oracle_issued(bond) for _, _, bonds in state.graph.edges for bond in bonds)

    # Les entrees ne sont jamais mutees.
    assert len(initial) == 1
    assert bfk.check_h3_authority_integrity(state.graph) == ()

    report = bfk.validate(state.graph, parts, geometries_for(parts), tolerance)
    assert report.ok, report.violations


def test_remove_part_keeps_remaining_bonds():
    tolerance = TOL()
    parts = {
        "A": bfk.place_brick("A", (0, 0, 0)),
        "B": bfk.place_brick("B", (0, 0, BRICK_H)),
        "C": bfk.place_brick("C", (0, 0, 2 * BRICK_H)),
    }
    state = bfk.assemble(parts, tolerance)
    ab_bonds = dict(((a, b), bonds) for a, b, bonds in state.graph.edges)[("A", "B")]

    reduced, remaining = bfk.remove_part(state, parts, "C")
    assert set(remaining) == {"A", "B"}
    assert [(a, b) for a, b, _ in reduced.graph.edges] == [("A", "B")]
    assert reduced.graph.edges[0][2] is ab_bonds
    assert len(parts) == 3, "le mapping d'entree a ete mute"

    with pytest.raises(KeyError):
        bfk.remove_part(state, parts, "inconnue")


# =============================================================================
# Verdict de placement
# =============================================================================


def test_evaluate_placement_answers_the_cad_question():
    tolerance = TOL()
    geometry = bfk.brick_geometry(2, 2)
    placed = {"A": bfk.place_brick("A", (0, 0, 0))}
    geometries = {"A": geometry}

    seated = bfk.evaluate_placement(
        placed, geometries, bfk.place_brick("B", (0, 0, BRICK_H)), geometry, tolerance
    )
    assert seated.is_legal
    assert seated.collision is bfk.CollisionStatus.CONTACT
    assert seated.bond_count == 4
    assert seated.supporting_parts == ("A",)

    overlapping = bfk.evaluate_placement(
        placed,
        geometries,
        bfk.place_brick("B", (bfk.HALF_STUD_LDU, 0, BRICK_H)),
        geometry,
        tolerance,
    )
    assert not overlapping.is_legal
    assert overlapping.collision is bfk.CollisionStatus.PENETRATION
    assert overlapping.blocking_parts == ("A",)

    floating = bfk.evaluate_placement(
        placed, geometries, bfk.place_brick("B", (200, 0, 10 * BRICK_H)), geometry, tolerance
    )
    assert not floating.is_legal, "une piece ni fondee ni reliee viole H4"
    assert floating.collision is bfk.CollisionStatus.CLEAR
    assert floating.bond_count == 0

    on_ground = bfk.evaluate_placement(
        placed, geometries, bfk.place_brick("B", (200, 0, 0)), geometry, tolerance
    )
    assert on_ground.is_legal
    assert on_ground.foundation.status is bfk.FoundationStatus.FOUNDED

    sunk = bfk.evaluate_placement(
        placed, geometries, bfk.place_brick("B", (200, 0, -1)), geometry, tolerance
    )
    assert not sunk.is_legal
    assert sunk.foundation.status is bfk.FoundationStatus.INVALID

    # Evaluation pure : rien n'a bouge.
    assert set(placed) == {"A"}
    with pytest.raises(ValueError):
        bfk.evaluate_placement(
            placed, geometries, bfk.place_brick("A", (0, 0, 5 * BRICK_H)), geometry, tolerance
        )


# =============================================================================
# Persistance
# =============================================================================


def test_document_never_carries_a_bond():
    tolerance = TOL()
    parts = {
        "A": bfk.place_brick("A", (0, 0, 0)),
        # Tournee d'un quart de tour : la translation compense la rotation du
        # repere local, l'empilement reste exact.
        "B": bfk.place_brick("B", (40, 0, BRICK_H), orientation=bfk.ROT_Z_90),
    }
    geometries = geometries_for(parts)
    state = bfk.assemble(parts, tolerance)
    assert state.graph.edges, "fixture invalide : aucun bond a perdre"

    payload = bfk.dumps_model(parts, geometries)
    assert "bond" not in payload.lower()
    assert "edge" not in payload.lower()

    document = json.loads(payload)
    assert document["version"] == bfk.DOCUMENT_VERSION
    assert set(document) == {"version", "geometries", "connector_sets", "parts"}
    # Les geometries sont mises en facteur : deux briques identiques ne
    # dupliquent pas leurs vingt-deux vides dans le fichier.
    assert len(document["geometries"]) == 1
    assert len(document["parts"]) == 2

    reloaded_parts, reloaded_geometries, reloaded_instances = bfk.loads_model(payload)
    assert reloaded_parts == parts
    assert reloaded_geometries == geometries
    assert reloaded_instances == {}, "aucune identite catalogue dans cette fixture"

    # Les liaisons sont RE-EMISES par l'oracle, pas relues : nouveaux objets,
    # meme structure, et H3 tient toujours.
    reloaded_state = bfk.assemble(reloaded_parts, tolerance)
    assert [(a, b, len(x)) for a, b, x in reloaded_state.graph.edges] == [
        (a, b, len(x)) for a, b, x in state.graph.edges
    ]
    assert reloaded_state.graph.edges[0][2] != state.graph.edges[0][2]
    assert bfk.check_h3_authority_integrity(reloaded_state.graph) == ()

    report = bfk.validate(
        reloaded_state.graph, reloaded_parts, reloaded_geometries, tolerance
    )
    assert report.ok, report.violations


def test_document_validation_rejects_corrupted_input():
    parts = {"A": bfk.place_brick("A", (0, 0, 0))}
    document = bfk.to_document(parts, geometries_for(parts))

    with pytest.raises(ValueError):
        bfk.from_document({"version": "autre", "parts": []})

    reflected = json.loads(json.dumps(document))
    reflected["parts"][0]["pose"]["orientation"] = [1, 0, 0, 0, 1, 0, 0, 0, -1]
    with pytest.raises(ValueError):
        bfk.from_document(reflected)  # determinant -1 : reflexion

    skewed = json.loads(json.dumps(document))
    premier_jeu = next(iter(skewed["connector_sets"]))
    skewed["connector_sets"][premier_jeu][0]["local_normal"] = [1, 1, 0]
    with pytest.raises(ValueError):
        bfk.from_document(skewed)  # normale non axiale

    orphelin = json.loads(json.dumps(document))
    orphelin["parts"][0]["connectors_ref"] = "inconnu"
    with pytest.raises(ValueError):
        bfk.from_document(orphelin)

    duplicated = json.loads(json.dumps(document))
    duplicated["parts"].append(duplicated["parts"][0])
    with pytest.raises(ValueError):
        bfk.from_document(duplicated)

    inverted = json.loads(json.dumps(document))
    premiere = next(iter(inverted["geometries"]))
    inverted["geometries"][premiere]["exterior"]["min"] = [999, 999, 999]
    with pytest.raises(ValueError):
        bfk.from_document(inverted)  # min > max

    orpheline = json.loads(json.dumps(document))
    orpheline["parts"][0]["geometry_ref"] = "inconnue"
    with pytest.raises(ValueError):
        bfk.from_document(orpheline)


# =============================================================================
# Catalogue et nomenclature
# =============================================================================


def test_catalog_parts_are_buildable_and_valid():
    """Chaque reference du catalogue se pose, se connecte et passe H1-H6."""
    tolerance = TOL()
    for design_id, part in sorted(bfk.CATALOG.items()):
        base, base_geometry, _ = bfk.place("base", design_id, (0, 0, 0))
        top, top_geometry, _ = bfk.place(
            "top", design_id, (0, 0, part.body_height_ldu)
        )
        placed = {"base": base, "top": top}
        geometries = {"base": base_geometry, "top": top_geometry}

        state = bfk.assemble(placed, tolerance)

        if not part.has_studs:
            # Une tuile est une piece de finition : rien ne s'y accroche.
            # Deux tuiles empilees ne forment donc pas un objet, et H5 doit le
            # dire — c'est la meme verite que pour la mosaique naive.
            assert state.graph.edges == (), f"{design_id} ({part.name})"
            assert bfk.check_h5_disconnected(state.graph), (
                f"{design_id} : deux pieces sans liaison ne sont pas un objet"
            )
            assert bfk.check_h2_collision(placed, geometries) == ()
            continue

        expected_bonds = part.studs_x * part.studs_y
        assert [(a, b, len(bonds)) for a, b, bonds in state.graph.edges] == [
            ("base", "top", expected_bonds)
        ], f"{design_id} ({part.name})"

        report = bfk.validate(state.graph, placed, geometries, tolerance)
        assert report.ok, (design_id, report.violations)

    with pytest.raises(KeyError):
        bfk.definition("9999")


def test_bill_of_materials_counts_by_reference_and_colour():
    instances = {}
    for index in range(3):
        _, _, instance = bfk.place(f"R{index}", "3001", (0, 0, 24 * index), color_id=4)
        instances[instance.part_id] = instance
    _, _, white = bfk.place("W", "3022", (0, 0, 96), color_id=15)
    instances["W"] = white

    lines = bfk.bill_of_materials(instances)
    assert [(l.design_id, l.color_id, l.quantity) for l in lines] == [
        ("3001", 4, 3),
        ("3022", 15, 1),
    ]
    assert lines[0].name == "Brick 2 x 4"
    assert bfk.LDRAW_COLORS[4] == "Red"
    assert bfk.bill_of_materials({}) == ()


def test_document_round_trips_part_identity():
    """Un document sans identite est constructible mais pas achetable."""
    tolerance = TOL()
    parts, geometries, instances = {}, {}, {}
    for index, (part_id, design_id, color) in enumerate(
        (("A", "3003", 4), ("B", "3003", 15))
    ):
        placed, geometry, instance = bfk.place(
            part_id, design_id, (0, 0, 24 * index), color_id=color
        )
        parts[part_id], geometries[part_id], instances[part_id] = placed, geometry, instance

    payload = bfk.dumps_model(parts, geometries, instances)
    reloaded_parts, reloaded_geometries, reloaded_instances = bfk.loads_model(payload)

    assert reloaded_parts == parts
    assert reloaded_geometries == geometries
    assert reloaded_instances == instances
    assert bfk.bill_of_materials(reloaded_instances) == bfk.bill_of_materials(instances)

    state = bfk.assemble(reloaded_parts, tolerance)
    assert bfk.check_h3_authority_integrity(state.graph) == ()

    corrupted = json.loads(payload)
    corrupted["parts"][0]["color_id"] = "rouge"
    with pytest.raises(ValueError):
        bfk.from_document(corrupted)
