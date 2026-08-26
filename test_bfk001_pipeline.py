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
    return bfk.Image.from_pixels(width, height, pixels)


# =============================================================================
# Perception
# =============================================================================


def test_png_round_trip_and_box_resampling():
    image = image_test(32, 32)
    assert bfk.read_png(bfk.write_png(image)) == image

    # Moyenne de bloc EN LUMIERE LINEAIRE. Un damier noir/blanc renvoie
    # exactement la moitie de la lumiere ; la valeur sRGB correspondante est
    # 188, pas 127. Moyenner les octets reviendrait a moyenner des logarithmes
    # — 23 delta E d'erreur, plus que ce que coute toute la palette.
    damier = bfk.Image.from_pixels(
        4, 4,
        ((255, 255, 255) if (x + y) % 2 else (0, 0, 0) for y in range(4) for x in range(4)),
    )
    assert bfk.resample_box(damier, 2, 2).pixels == ((188, 188, 188),) * 4

    # La propriete generale : la moyenne d'un bloc doit renvoyer la meme
    # lumiere que le bloc. On la verifie sur des paires quelconques.
    def lumiere(canal):
        u = canal / 255
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4

    for sombre, clair in ((0, 128), (30, 90), (64, 192), (200, 255)):
        paire = bfk.Image(2, 1, bytes((sombre,) * 3 + (clair,) * 3))
        obtenu = bfk.resample_box(paire, 1, 1).pixel(0, 0)[0]
        attendu = (lumiere(sombre) + lumiere(clair)) / 2
        assert abs(lumiere(obtenu) - attendu) < 0.004, (sombre, clair, obtenu)

    with pytest.raises(ValueError):
        bfk.read_png(b"ceci n'est pas un png")


def test_quantization_is_perceptual_and_ordered():
    palette = bfk.PROVISIONAL_PALETTE
    assert palette.nearest((250, 10, 5)).name == "Red"
    assert palette.nearest((20, 20, 25)).name == "Black"
    assert palette.nearest((240, 200, 60)).name == "Yellow"

    # L'ORDRE des operations est ce qui compte : moyenner d'abord, quantifier
    # ensuite. La tuile doit porter la couleur de palette la plus proche de la
    # MOYENNE, et non l'une des deux couleurs d'origine choisie au hasard.
    damier = bfk.Image.from_pixels(
        4, 4,
        ((255, 0, 0) if (x + y) % 2 else (255, 255, 255) for y in range(4) for x in range(4)),
    )
    moyenne = bfk.resample_box(damier, 1, 1).pixel(0, 0)
    assert moyenne == (255, 188, 188)
    assert bfk.mosaic.quantize(damier, palette, 1, 1)[0][0] is palette.nearest(moyenne)

    # Avec 12 couleurs, cette moyenne tombe faute de rose dans la palette : la
    # finesse d'une mosaique tient d'abord au nombre de couleurs disponibles,
    # pas a l'algorithme. Raison de plus pour importer LDConfig.
    assert palette.nearest(moyenne).name in ("Red", "White", "Tan")


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

    assert mosaique.stud_count == 64
    assert mosaique.tile_count <= 64, "la fusion ne cree jamais de piece en plus"
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
    # Toutes references de tuiles confondues : la fusion en emploie plusieurs,
    # mais elles doivent couvrir exactement les 64 tenons, ni plus ni moins.
    tuiles = [l for l in nomenclature if bfk.CATALOG[l.design_id].has_studs is False]
    assert sum(l.quantity for l in tuiles) == mosaique.tile_count
    assert sum(
        l.quantity * bfk.CATALOG[l.design_id].studs_y for l in tuiles
    ) == mosaique.stud_count

    # Le disque rouge et le fond bleu se retrouvent dans la liste de course.
    # Toutes references de tuiles confondues : depuis la fusion, une aplat de
    # couleur peut n'exister qu'en 1x2 ou 1x4, et chercher dans les seules 1x1
    # ferait rater la couleur la plus etendue de l'image.
    couleurs = {l.color_id for l in tuiles}
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


# =============================================================================
# Fidelite : mesurer plutot que juger
# =============================================================================


def image_modulee(width=96, height=96):
    """Visage stylise : des teintes qui n'existent dans aucune palette LEGO."""
    pixels = []
    for y in range(height):
        for x in range(width):
            centered = (x - width // 2) ** 2 + (y - height // 2) ** 2
            if centered < (width // 3) ** 2:
                t = 1 - centered / (width // 3) ** 2
                pixels.append((int(175 + 65 * t), int(135 + 55 * t), int(105 + 45 * t)))
            else:
                pixels.append((40 + y // 3, 70 + y // 4, 150))
    return bfk.Image.from_pixels(width, height, pixels)


def test_viewing_distance_settles_the_dithering_question():
    """La physique de l'oeil tranche, pas le gout.

    Un tenon fait 8 mm. Deux tuiles voisines ne se confondent qu'a 55 m : a
    toute distance humaine, l'oeil voit chaque tuile. Mesurer la fidelite a
    une distance de regard superieure a une tuile, c'est evaluer une mosaique
    depuis un autre departement.
    """
    assert bfk.mosaic.blending_tiles(0.5) == 1
    assert bfk.mosaic.blending_tiles(1.5) == 1
    assert bfk.mosaic.blending_tiles(3.0) == 1
    # Il faut soit reculer enormement, soit une maille bien plus fine.
    assert bfk.mosaic.blending_tiles(60.0) >= 2
    assert bfk.mosaic.blending_tiles(1.5, stud_mm=0.2) >= 2

    with pytest.raises(ValueError):
        bfk.mosaic.blending_tiles(0)


def test_dithering_is_a_measured_trade_off_not_an_improvement():
    """Le tramage : ce qu'il coute, ce qu'il rapporte, et ce qui est par defaut."""
    palette = bfk.PROVISIONAL_PALETTE
    plat = image_test()          # deux aplats francs
    module = image_modulee()     # teintes absentes de la palette

    sans_plat = bfk.mosaic.quantize(plat, palette, 32, 32, dither=False)
    avec_plat = bfk.mosaic.quantize(plat, palette, 32, 32, dither=True)
    adaptatif_plat = bfk.mosaic.quantize(plat, palette, 32, 32, dither="adaptive")

    # De pres — la seule distance reelle — tramer un aplat le degrade.
    proche = bfk.mosaic.blending_tiles(1.5)
    assert bfk.mosaic.fidelity(sans_plat, plat, proche)[0] < bfk.mosaic.fidelity(
        avec_plat, plat, proche
    )[0]
    # L'adaptatif, lui, laisse les aplats tranquilles : il colle au direct.
    assert bfk.mosaic.fidelity(adaptatif_plat, plat, proche)[0] < bfk.mosaic.fidelity(
        avec_plat, plat, proche
    )[0]

    # A distance de fusion — situation qui n'existe pas en LEGO, mais qui
    # existerait sur un medium a maille fine — le tramage ecrase le direct.
    sans_module = bfk.mosaic.quantize(module, palette, 32, 32, dither=False)
    avec_module = bfk.mosaic.quantize(module, palette, 32, 32, dither=True)
    assert bfk.mosaic.fidelity(avec_module, module, 4)[0] < bfk.mosaic.fidelity(
        sans_module, module, 4
    )[0]

    # Le defaut de la chaine est l'ADAPTATIF. Floyd-Steinberg complet gagne
    # sur le critere tonal et perd a l'oeil — il transforme un ciel en neige ;
    # ne rien tramer laisse des bandes a bord franc, et l'oeil est plus
    # sensible a un bord qu'a du grain. L'adaptatif ne trame que la ou la
    # palette ne sait pas produire la couleur.
    assert bfk.mosaic.quantize(plat, palette, 16, 16) == bfk.mosaic.quantize(
        plat, palette, 16, 16, dither="adaptive"
    )
    # Ce qui le rend sur comme defaut : sur une couleur QUE LA PALETTE SAIT
    # rendre, il ne trame rien du tout. Le critere n'est pas « l'image est
    # plate », c'est « la couleur voulue existe deja » — un aplat gris-vert que
    # la palette rate gagne au tramage, un aplat rouge vif ne peut qu'y perdre.
    exacte = palette.by_code(4).rgb          # Red, presente telle quelle
    aplat_exact = bfk.Image(64, 64, bytes(exacte) * (64 * 64))
    direct = bfk.mosaic.quantize(aplat_exact, palette, 16, 16, dither=False)
    adaptatif = bfk.mosaic.quantize(aplat_exact, palette, 16, 16, dither="adaptive")
    assert adaptatif == direct
    assert {c.code for ligne in adaptatif for c in ligne} == {4}
    # Alors que Floyd-Steinberg complet salirait meme celui-la.
    complet = bfk.mosaic.quantize(aplat_exact, palette, 16, 16, dither=True)
    assert complet == direct  # ici l'erreur diffusee est nulle : rien a salir

    # Et sur une couleur ABSENTE de la palette, l'adaptatif melange bien deux
    # teintes voisines — c'est tout son interet.
    absente = bfk.Image(64, 64, bytes((120, 140, 110)) * (64 * 64))
    melange = bfk.mosaic.quantize(absente, palette, 16, 16, dither="adaptive")
    assert len({c.code for ligne in melange for c in ligne}) > 1

    with pytest.raises(ValueError):
        bfk.mosaic.quantize(plat, palette, 16, 16, dither="peut-etre")
    with pytest.raises(ValueError):
        bfk.mosaic.fidelity(sans_plat, plat, block=0)


# =============================================================================
# Substrat : le noyau arbitre, il ne suggere pas
# =============================================================================


def test_panel_substrate_is_refused_because_it_does_not_hold():
    """Neuf plates 16x16 au lieu de 613 pieces — et un objet en neuf morceaux.

    C'est le substrat des sets LEGO Art officiels. Ils tiennent par leur cadre,
    qui n'est pas une piece structurelle. Le noyau refuse de certifier ce qu'un
    cadre absent est cense tenir : c'est exactement son role.
    """
    tolerance = bfk.LEGO_TOLERANCE
    grille = bfk.mosaic.quantize(image_test(), bfk.PROVISIONAL_PALETTE, 32, 32)
    # 32x32 est la plus petite taille ou un panneau 16x16 a du sens.

    croise = bfk.mosaic.build(grille, substrate="crossed")
    panneaux = bfk.mosaic.build(grille, substrate="panels")

    substrat_croise = croise.part_count - croise.tile_count
    substrat_panneaux = panneaux.part_count - panneaux.tile_count
    assert substrat_panneaux == 4, "32x32 tenons = quatre plates 16x16"
    # Le croise reste plus cher — il faut deux couches qui s'enjambent —, mais
    # depuis la fusion des plates l'ecart n'a plus rien d'un facteur vingt :
    # 70 pieces contre 4 sur une 32x32, la ou le pavage en 2x4 en demandait 325.
    assert substrat_croise > 4 * substrat_panneaux, "le substrat croise reste plus cher"
    assert substrat_croise < 30 * substrat_panneaux, "la fusion doit avoir joue"

    for mosaique, attendu in ((croise, True), (panneaux, False)):
        etat = bfk.assemble(
            mosaique.placed_parts, tolerance, search=bfk.LatticeSearchApproximation()
        )
        # Aucune penetration dans les deux cas : la geometrie est saine.
        assert bfk.check_h2_collision(mosaique.placed_parts, mosaique.geometries) == ()
        connexe = bfk.check_h5_disconnected(etat.graph) == ()
        assert connexe is attendu

    with pytest.raises(ValueError):
        bfk.mosaic.build(grille, substrate="carton")


# =============================================================================
# Decodage PNG : les filtres que produisent les vrais appareils
# =============================================================================


def encode_png_avec_filtre(image, filtre):
    """Encodeur de test imposant un filtre donne.

    `write_png` du noyau n'emet que le filtre 0. Se contenter de ses propres
    fichiers pour tester son decodeur, c'est ne tester qu'un cinquieme du
    format — et pas celui que produisent les appareils photo, qui utilisent
    Sub et Paeth.
    """
    import struct
    import zlib

    from bfk001.imaging import _paeth

    stride = image.width * 3
    raw = bytearray()
    precedente = bytearray(stride)
    for y in range(image.height):
        ligne = bytearray(image.data[y * stride : (y + 1) * stride])
        sortie = bytearray(stride)
        for i in range(stride):
            a = ligne[i - 3] if i >= 3 else 0
            b = precedente[i]
            c = precedente[i - 3] if i >= 3 else 0
            if filtre == 1:
                sortie[i] = (ligne[i] - a) & 0xFF
            elif filtre == 2:
                sortie[i] = (ligne[i] - b) & 0xFF
            elif filtre == 3:
                sortie[i] = (ligne[i] - (a + b) // 2) & 0xFF
            elif filtre == 4:
                sortie[i] = (ligne[i] - _paeth(a, b, c)) & 0xFF
            else:
                sortie[i] = ligne[i]
        raw.append(filtre)
        raw.extend(sortie)
        precedente = ligne

    def bloc(genre, charge):
        return (
            len(charge).to_bytes(4, "big")
            + genre
            + charge
            + zlib.crc32(genre + charge).to_bytes(4, "big")
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + bloc(b"IHDR", struct.pack(">IIBBBBB", image.width, image.height, 8, 2, 0, 0, 0))
        + bloc(b"IDAT", zlib.compress(bytes(raw), 6))
        + bloc(b"IEND", b"")
    )


def test_png_decoder_handles_every_filter_exactly():
    """Les cinq filtres PNG, au bit pres."""
    source = image_modulee(24, 24)
    for filtre in (0, 1, 2, 3, 4):
        relu = bfk.read_png(encode_png_avec_filtre(source, filtre))
        assert relu.data == source.data, f"filtre {filtre}"

    with pytest.raises(ValueError):
        bfk.read_png(encode_png_avec_filtre(source, 9))


def test_image_is_stored_as_bytes_not_tuples():
    """Une photo de 12 Mpx en tuples demanderait 860 Mo. En octets : 36 Mo."""
    image = image_test(16, 16)
    assert isinstance(image.data, bytes)
    assert len(image.data) == 16 * 16 * 3
    assert image.pixel(0, 0) == image.pixels[0]
    assert image.pixel(15, 15) == image.pixels[-1]

    with pytest.raises(ValueError):
        bfk.Image(4, 4, b"trop court")
