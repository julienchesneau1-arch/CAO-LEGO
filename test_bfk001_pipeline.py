"""
Chaine complete : photo -> mosaique LEGO Art -> liste de course -> notice.

C'est la demande produit, bout en bout, au niveau ou elle est aujourd'hui
realisable : le solveur propose, le noyau juge, la nomenclature compte, le plan
ordonne. Le rendu graphique de la notice n'en fait pas partie.
"""

from __future__ import annotations

import pytest

import bfk001_kernel as bfk


def image_test(width=64, height=64):
    """Disque rouge sur fond bleu : deux aplats francs, faciles a verifier."""
    pixels = []
    for y in range(height):
        for x in range(width):
            centered = (x - width // 2) ** 2 + (y - height // 2) ** 2
            pixels.append((220, 30, 20) if centered < (width // 4) ** 2 else (30, 60, 180))
    return bfk.Image(width, height, tuple(pixels))


# =============================================================================
# Perception
# =============================================================================


def test_png_round_trip_and_box_resampling():
    image = image_test(32, 32)
    assert bfk.read_png(bfk.write_png(image)) == image

    # Moyenne de bloc : un damier noir/blanc devient uniformement gris.
    damier = bfk.Image(
        4, 4,
        tuple((255, 255, 255) if (x + y) % 2 else (0, 0, 0) for y in range(4) for x in range(4)),
    )
    assert bfk.resample_box(damier, 2, 2).pixels == ((127, 127, 127),) * 4

    with pytest.raises(ValueError):
        bfk.read_png(b"ceci n'est pas un png")


def test_quantization_is_perceptual_and_ordered():
    palette = bfk.PROVISIONAL_PALETTE
    assert palette.nearest((250, 10, 5)).name == "Red"
    assert palette.nearest((20, 20, 25)).name == "Black"
    assert palette.nearest((240, 200, 60)).name == "Yellow"

    # L'ORDRE des operations est ce qui compte : moyenner d'abord, quantifier
    # ensuite. Un damier rouge/blanc a pour moyenne (255, 127, 127) ; la tuile
    # doit porter la couleur de palette la plus proche de CETTE moyenne, et non
    # l'une des deux couleurs d'origine choisie au hasard.
    damier = bfk.Image(
        4, 4,
        tuple((255, 0, 0) if (x + y) % 2 else (255, 255, 255) for y in range(4) for x in range(4)),
    )
    moyenne = bfk.resample_box(damier, 1, 1).pixel(0, 0)
    assert moyenne == (255, 127, 127)
    assert bfk.mosaic.quantize(damier, palette, 1, 1)[0][0] is palette.nearest(moyenne)

    # Avec 12 couleurs, cette moyenne tombe sur Red faute de rose dans la
    # palette : la finesse d'une mosaique tient d'abord au nombre de couleurs
    # disponibles, pas a l'algorithme. Raison de plus pour importer LDConfig.
    assert palette.nearest(moyenne).name == "Red"


def test_ldconfig_import_replaces_the_provisional_palette():
    """La palette officielle s'importe, elle ne se recopie pas."""
    officiel = "\n".join(
        (
            "0 !COLOUR Black CODE 0 VALUE #05131D EDGE #808080",
            "0 !COLOUR Bright_Green CODE 10 VALUE #4B9F4A EDGE #000000",
            "0 // commentaire",
            "0 !COLOUR Medium_Azure CODE 322 VALUE #36AEBF EDGE #000000",
        )
    )
    palette = bfk.load_ldconfig(officiel)
    assert len(palette) == 3
    assert palette.by_code(322).name == "Medium Azure"
    assert palette.nearest((60, 180, 190)).code == 322
    assert len(palette.restricted_to([0, 10])) == 2

    with pytest.raises(ValueError):
        bfk.load_ldconfig("aucune couleur ici")


# =============================================================================
# Chaine complete
# =============================================================================


def test_image_becomes_a_model_the_kernel_certifies():
    """Photo -> modele -> six invariants verts -> liste de course complete."""
    tolerance = bfk.LEGO_TOLERANCE
    mosaique = bfk.mosaic.from_image(image_test(), bfk.PROVISIONAL_PALETTE, 8, 8)

    assert mosaique.tile_count == 64
    assert mosaique.part_count > mosaique.tile_count, "le substrat doit exister"

    state = bfk.assemble(
        mosaique.placed_parts, tolerance, search=bfk.LatticeSearchApproximation()
    )
    rapport = bfk.validate(
        state.graph,
        mosaique.placed_parts,
        mosaique.geometries,
        tolerance,
        search=bfk.LatticeSearchApproximation(),
    )
    assert rapport.ok, rapport.violations

    nomenclature = bfk.bill_of_materials(mosaique.instances, mosaique.placed_parts)
    assert sum(ligne.quantity for ligne in nomenclature) == mosaique.part_count
    tuiles = sum(l.quantity for l in nomenclature if l.design_id == "3070b")
    assert tuiles == mosaique.tile_count

    # Le disque rouge et le fond bleu se retrouvent dans la liste de course.
    couleurs = {l.color_id for l in nomenclature if l.design_id == "3070b"}
    assert bfk.PROVISIONAL_PALETTE.nearest((220, 30, 20)).code in couleurs
    assert bfk.PROVISIONAL_PALETTE.nearest((30, 60, 180)).code in couleurs


def test_preview_renders_the_grid_faithfully():
    mosaique = bfk.mosaic.from_image(image_test(), bfk.PROVISIONAL_PALETTE, 8, 8)
    apercu = bfk.mosaic.preview(mosaique, scale=4)

    assert (apercu.width, apercu.height) == (32, 32)
    assert apercu.pixel(0, 0) == mosaique.grid[0][0].rgb
    assert apercu.pixel(31, 31) == mosaique.grid[7][7].rgb
    assert bfk.read_png(bfk.write_png(apercu)) == apercu


# =============================================================================
# Notice
# =============================================================================


def test_build_plan_is_physically_executable():
    """Aucune etape ne demande de poser une piece en l'air."""
    tolerance = bfk.LEGO_TOLERANCE
    mosaique = bfk.mosaic.from_image(image_test(), bfk.PROVISIONAL_PALETTE, 8, 8)
    state = bfk.assemble(
        mosaique.placed_parts, tolerance, search=bfk.LatticeSearchApproximation()
    )
    plan = bfk.plan_build(
        mosaique.placed_parts, state.graph, mosaique.instances, max_parts_per_step=8
    )

    assert plan.validate_dag()

    # Chaque piece apparait une fois et une seule.
    posees = [part_id for step in plan.steps for part_id in step.part_ids]
    assert sorted(posees) == sorted(mosaique.placed_parts)

    # Simulation du montage : a chaque etape, tout ce qui porte les pieces de
    # l'etape doit deja etre en place.
    portee = {part_id: set() for part_id in mosaique.placed_parts}
    for id_a, id_b, bonds in state.graph.edges:
        if not bonds:
            continue
        z_a = mosaique.placed_parts[id_a].aabb.min.z
        z_b = mosaique.placed_parts[id_b].aabb.min.z
        if z_a < z_b:
            portee[id_b].add(id_a)
        elif z_b < z_a:
            portee[id_a].add(id_b)

    en_place: set = set()
    identifiants = {step.step_id for step in plan.steps}
    for step in plan.steps:
        assert set(step.depends_on) <= identifiants
        for part_id in step.part_ids:
            manquant = portee[part_id] - en_place - set(step.part_ids)
            assert not manquant, (
                f"{step.step_id} pose {part_id} avant son support {manquant}"
            )
        en_place.update(step.part_ids)

    texte = bfk.render_text(plan)
    assert "NOTICE DE MONTAGE" in texte
    assert str(len(plan.steps)) in texte


def test_plan_groups_by_colour_to_spare_the_builder():
    """Une notice qui fait changer de sachet a chaque piece est une mauvaise notice."""
    tolerance = bfk.LEGO_TOLERANCE
    mosaique = bfk.mosaic.from_image(image_test(), bfk.PROVISIONAL_PALETTE, 8, 8)
    state = bfk.assemble(
        mosaique.placed_parts, tolerance, search=bfk.LatticeSearchApproximation()
    )
    plan = bfk.plan_build(
        mosaique.placed_parts, state.graph, mosaique.instances, max_parts_per_step=64
    )

    for step in plan.steps:
        couleurs = {mosaique.instances[p].color_id for p in step.part_ids}
        references = {mosaique.instances[p].design_id for p in step.part_ids}
        assert len(couleurs) == 1, "une etape, une couleur"
        assert len(references) == 1, "une etape, une reference"

    with pytest.raises(ValueError):
        bfk.plan_build(mosaique.placed_parts, state.graph, max_parts_per_step=0)
