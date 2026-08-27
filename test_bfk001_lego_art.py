"""
BFK-001 — Ce que le noyau sait deja faire, et refuse de faire, pour une
mosaique style LEGO Art.

Ces tests ne construisent pas une mosaique a partir d'une photo : aucun solveur
n'existe. Ils etablissent ce qui est acquis au niveau du noyau — et surtout ce
que le noyau REFUSE, car c'est la que se joue la difference entre « ca s'affiche
a l'ecran » et « ca tient dans la main ».
"""

from __future__ import annotations

import pytest

import bfk001_kernel as bfk

STUD = bfk.STUD_PITCH_LDU
PLATE = bfk.PLATE_HEIGHT_LDU
COTE = 8  # mosaique 8 x 8 tenons


def V(x, y, z):
    return bfk.LDUVector(x, y, z)


def TOL():
    return bfk.LEGO_TOLERANCE


def add(parts, geometries, instances, part_id, design_id, translation, color=15):
    placed, geometry, instance = bfk.place(
        part_id, design_id, translation, color_id=color
    )
    parts[part_id] = placed
    geometries[part_id] = geometry
    instances[part_id] = instance


def mosaique_naive():
    """Les tuiles posees a plat sur le sol, sans rien dessous."""
    parts, geometries, instances = {}, {}, {}
    for i in range(COTE):
        for j in range(COTE):
            add(
                parts, geometries, instances,
                f"T{i}_{j}", "3024", (STUD * i, STUD * j, 0), color=(i + j) % 2 * 4,
            )
    return parts, geometries, instances


def mosaique_sur_substrat():
    """La meme mosaique, sur deux couches de plates croisees.

    Deux plates cote a cote ne se lient PAS : seule une couche superieure qui
    les chevauche les solidarise. C'est la technique du running bond, et ce
    n'est pas une elegance de constructeur — c'est ce qui fait la difference
    entre un tas de pieces et un objet.
    """
    parts, geometries, instances = {}, {}, {}
    # Couche 0 : pavage de plates 2x4 (40 x 80 LDU)
    for i, x in enumerate(range(0, COTE * STUD, 2 * STUD)):
        for j, y in enumerate(range(0, COTE * STUD, 4 * STUD)):
            add(parts, geometries, instances, f"A{i}_{j}", "3020", (x, y, 0), color=71)
    # Couche 1 : meme pavage decale d'un tenon en x et de deux en y -> il
    # chevauche quatre plates de la couche 0 et les relie.
    for i, x in enumerate(range(-STUD, COTE * STUD, 2 * STUD)):
        for j, y in enumerate(range(-2 * STUD, COTE * STUD, 4 * STUD)):
            add(parts, geometries, instances, f"B{i}_{j}", "3020", (x, y, PLATE), color=71)
    # Couche 2 : la mosaique proprement dite
    for i in range(COTE):
        for j in range(COTE):
            add(
                parts, geometries, instances,
                f"T{i}_{j}", "3024", (STUD * i, STUD * j, 2 * PLATE),
                color=(0, 4, 14, 15)[(i + j) % 4],
            )
    return parts, geometries, instances


def test_naive_mosaic_is_rejected_by_the_kernel():
    """Une mosaique posee a plat est un tas de pieces, pas un objet.

    C'est le cas ou une CAO naive dirait « c'est bon, ca s'affiche » : chaque
    tuile est bien posee, aucune ne penetre sa voisine, toutes reposent sur le
    plan. Et pourtant l'objet n'existe pas — il tombe en morceaux des qu'on le
    souleve. H5 est le seul a le voir.
    """
    parts, geometries, instances = mosaique_naive()
    tolerance = TOL()
    state = bfk.assemble(parts, tolerance, search=bfk.LatticeSearchApproximation())

    assert len(parts) == COTE * COTE
    assert state.graph.edges == (), "des tuiles cote a cote ne se lient pas"

    assert bfk.check_h2_collision(parts, geometries) == ()   # rien ne penetre
    assert bfk.check_h6_foundation(parts, geometries) == ()  # tout repose au sol
    assert bfk.check_h4_floating(
        state.graph, bfk.founded_part_ids(parts, geometries)
    ) == ()                                                  # rien ne flotte

    disconnected = bfk.check_h5_disconnected(state.graph)
    assert len(disconnected) == COTE * COTE - 1, (
        "H5 doit voir que l'objet n'est pas d'un seul tenant"
    )


def test_mosaic_on_substrate_satisfies_every_invariant():
    """La meme mosaique, correctement fondee, passe les six invariants."""
    parts, geometries, instances = mosaique_sur_substrat()
    tolerance = TOL()
    state = bfk.assemble(parts, tolerance, search=bfk.LatticeSearchApproximation())

    report = bfk.validate(
        state.graph, parts, geometries, tolerance,
        search=bfk.LatticeSearchApproximation(),
    )
    assert report.ok, report.violations
    assert state.graph.edges, "le substrat doit produire des liaisons"

    # La liste de course est complete et verifiee contre les pieces posees.
    nomenclature = bfk.bill_of_materials(instances, parts)
    total = sum(ligne.quantity for ligne in nomenclature)
    assert total == len(parts)
    tuiles = [l for l in nomenclature if l.design_id == "3024"]
    assert sum(l.quantity for l in tuiles) == COTE * COTE
    assert {l.color_id for l in tuiles} == {0, 4, 14, 15}


def test_bill_of_materials_refuses_to_be_incomplete():
    """Une piece sans identite disparaitrait de la liste de course."""
    parts, geometries, instances = mosaique_naive()
    ampute = {k: v for k, v in instances.items() if k != "T0_0"}

    with pytest.raises(KeyError, match="T0_0"):
        bfk.bill_of_materials(ampute, parts)

    # Sans garde-fou, l'omission passe silencieusement — et se paie en pieces
    # manquantes le jour du montage.
    assert sum(l.quantity for l in bfk.bill_of_materials(ampute)) == len(parts) - 1


def test_catalog_plate_references_are_the_real_ones():
    """3021 est une Plate 2x3, pas une 2x4. La 2x4 est la 3020.

    Le document de reflexion produit inversait les deux. Une liste de course
    fondee dessus aurait fait livrer les mauvaises pieces.
    """
    assert bfk.definition("3020").name == "Plate 2 x 4"
    assert (bfk.definition("3020").studs_x, bfk.definition("3020").studs_y) == (2, 4)
    assert bfk.definition("3021").name == "Plate 2 x 3"
    assert (bfk.definition("3021").studs_x, bfk.definition("3021").studs_y) == (2, 3)
    assert bfk.definition("3024").name == "Plate 1 x 1"
    for design_id, part in bfk.CATALOG.items():
        assert part.design_id == design_id
        assert part.body_height_ldu in (bfk.BRICK_HEIGHT_LDU, bfk.PLATE_HEIGHT_LDU)


def test_le_tramage_auto_juge_les_grilles_NETTOYEES():
    """Le critere doit porter sur la grille livree, pas sur une intermediaire.

    Trouve sur une photo reelle (§ 5.61) : le tramage y gagnait 5,20 delta E
    sur le pire ecart tonal, et le nettoyage des tuiles isolees, applique juste
    apres, effacait 604 des 710 tuiles tramees et ramenait le gain a 0,00.

    Ce test verifie le MECANISME et non son effet, et c'est delibere : depuis
    que le critere pese aussi le grain (§ 5.66), la condition de grain tranche
    avant, et aucune scene construite ne fait plus basculer la decision par le
    seul nettoyage. Le cablage reste juste et doit le rester ; un test qui
    passerait par la sortie ne le verifierait plus.
    """
    from bfk001 import mosaic
    from bfk001.mosaic import quantize

    palette = bfk.PROVISIONAL_PALETTE.solids_only()
    cote = 160
    image = bfk.Image.from_pixels(cote, cote, [
        (int(120 + 50 * y / cote), int(122 + 48 * y / cote),
         int(118 + 50 * y / cote))
        for y in range(cote) for _ in range(cote)])

    appels = []
    vrai = mosaic.denoise

    def espion(grille, source, tolerance, fit, offset=0.5):
        appels.append(tolerance)
        return vrai(grille, source, tolerance, fit, offset)

    mosaic.denoise = espion
    try:
        quantize(image, palette, 32, 32, "auto", "crop", 0.5)
        sans_tolerance = list(appels)
        appels.clear()
        quantize(image, palette, 32, 32, "auto", "crop", 0.5,
                 denoise_tolerance=4.0)
        avec_tolerance = list(appels)
    finally:
        mosaic.denoise = vrai

    assert sans_tolerance == [], "sans tolerance, rien ne doit etre nettoye"
    assert avec_tolerance == [4.0, 4.0], (
        "les DEUX candidats doivent etre juges nettoyes, pas un seul")


def test_le_nettoyage_efface_ce_que_le_tramage_a_seme():
    """Le fait mesure qui a impose la correction du § 5.61.

    Sans lui, la decision se prenait sur des grilles que la chaine modifiait
    ensuite — et le nettoyage reprenait presque tout ce que le tramage avait
    seme, avec le gain qui le justifiait.
    """
    from bfk001.mosaic import (_cadrer, _quantifier, denoise, fidelity,
                               isolated_tiles)
    from bfk001.imaging import resample_box

    palette = bfk.PROVISIONAL_PALETTE.solids_only()
    cote = 200
    image = bfk.Image.from_pixels(cote, cote, [
        (int(120 + 50 * y / cote), int(122 + 48 * y / cote),
         int(118 + 50 * y / cote))
        for y in range(cote) for _ in range(cote)])

    sx = sy = 48
    cadree = _cadrer(image, sx, sy, "crop", 0.5)
    reduite = resample_box(cadree, sx, sy)
    sans = _quantifier(reduite, palette, sx, sy, False)
    avec = _quantifier(reduite, palette, sx, sy, "adaptive")

    semees = len(isolated_tiles(avec))
    restantes = len(isolated_tiles(denoise(avec, cadree, 4.0, "stretch", 0.5)))
    assert restantes < semees / 2, (semees, restantes)

    brut = fidelity(sans, cadree, 4)[1] - fidelity(avec, cadree, 4)[1]
    livre = (fidelity(denoise(sans, cadree, 4.0, "stretch", 0.5), cadree, 4)[1]
             - fidelity(denoise(avec, cadree, 4.0, "stretch", 0.5), cadree, 4)[1])
    assert brut > livre, (brut, livre)


def test_le_critere_tonal_est_aveugle_au_grain_et_on_sait_de_combien():
    """Une limite connue du critere, epinglee plutot qu'affirmee en prose.

    Un ecart tonal se mesure sur la MOYENNE d'un bloc de 4x4 tuiles, et une
    moyenne ne voit pas le grain qu'elle moyenne : deux damiers de tons opposes
    ont la meme moyenne qu'un aplat. Le critere peut donc choisir le tramage
    alors que `detail_gap`, qui compare aux memes points physiques sans
    moyenner, le juge PIRE.

    Ce test ne demande pas de corriger : il exige que le compromis reste
    visible. Une condition de grain corrigerait bien le cas de la photo, mais
    refuserait aussi le degrade pur, ou le tramage adoucit vraiment les bords
    de bande — meme perte de detail, verdict visuel oppose, aucun seuil ne les
    separe. Qui touchera au critere saura ce qu'il echange.
    """
    from bfk001.mosaic import (_cadrer, _quantifier, denoise, detail_gap,
                               fidelity, grille_de_mesure, quantize,
                               DITHER_AUTO_MIN_GAIN)
    from bfk001.imaging import resample_box

    palette = bfk.PROVISIONAL_PALETTE.solids_only()
    cote = 200
    ciel = bfk.Image.from_pixels(cote, cote, [
        (int(70 + 130 * y / cote), int(120 + 110 * y / cote),
         int(210 - 30 * y / cote))
        for y in range(cote) for _ in range(cote)])

    sx = sy = 48
    cadree = _cadrer(ciel, sx, sy, "crop", 0.5)
    reduite = resample_box(cadree, sx, sy)
    sans = denoise(_quantifier(reduite, palette, sx, sy, False), cadree,
                   4.0, "stretch", 0.5)
    avec = denoise(_quantifier(reduite, palette, sx, sy, "adaptive"), cadree,
                   4.0, "stretch", 0.5)
    mesure = grille_de_mesure(sx, sy)

    gain_tonal = fidelity(sans, cadree, 4)[1] - fidelity(avec, cadree, 4)[1]
    gain_detail = (detail_gap(sans, cadree, sx, sy, mesure)
                   - detail_gap(avec, cadree, sx, sy, mesure))

    # Les deux mesures se contredisent : c'est le fait a epingler.
    assert gain_tonal >= DITHER_AUTO_MIN_GAIN, gain_tonal
    assert gain_detail < 0, gain_detail

    # Et c'est le tonal qui tranche aujourd'hui, en connaissance de cause.
    trame = _quantifier(reduite, palette, sx, sy, "adaptive")
    assert quantize(ciel, palette, sx, sy, "auto", "crop", 0.5,
                    denoise_tolerance=4.0) == trame


def test_le_tramage_explicite_reste_possible():
    """Le critere « auto » est conservateur ; il ne doit rien interdire.

    Sur un degrade PUR le tramage pose une ceinture d'une tuile le long de
    chaque bord de bande, et cela adoucit vraiment la transition. Aucune des
    mesures disponibles ne distingue ce grain-la du semis d'une photographie —
    la perte de detail vaut -0,12 dans un cas, -0,13 dans l'autre. « auto »
    tranche donc du cote rattrapable, et un mot suffit a le renverser.
    """
    from bfk001.mosaic import _cadrer, _quantifier, quantize
    from bfk001.imaging import resample_box

    palette = bfk.PROVISIONAL_PALETTE.solids_only()
    cote = 200
    ciel = bfk.Image.from_pixels(cote, cote, [
        (int(70 + 130 * y / cote), int(120 + 110 * y / cote),
         int(210 - 30 * y / cote))
        for y in range(cote) for _ in range(cote)])

    sx = sy = 48
    reduite = resample_box(_cadrer(ciel, sx, sy, "crop", 0.5), sx, sy)
    for mode in ("adaptive", True):
        attendu = _quantifier(reduite, palette, sx, sy, mode)
        assert quantize(ciel, palette, sx, sy, mode, "crop", 0.5) == attendu


def test_la_quantification_atteint_le_plancher_de_la_palette():
    """Aucun choix de couleur ne fait mieux, et on peut le prouver.

    Le plancher est l'ecart si chaque tenon prenait la MEILLEURE couleur
    existante. Si le resultat l'atteint, la quantification est optimale — pas
    « bonne », optimale — et chercher un meilleur algorithme de choix est perdu
    d'avance. Mesure sur une photo reelle : plancher 6,68, obtenu 6,68.
    """
    from bfk001.mosaic import _cadrer, _quantifier, fidelity, palette_floor
    from bfk001.imaging import resample_box

    palette = bfk.PROVISIONAL_PALETTE.solids_only()
    cote = 200
    pixels = [(int(20 + 200 * x / cote), int(60 + 150 * y / cote),
               int((x * y) % 233))
              for y in range(cote) for x in range(cote)]
    image = bfk.Image.from_pixels(cote, cote, pixels)

    sx = sy = 32
    cadree = _cadrer(image, sx, sy, "crop", 0.5)
    reduite = resample_box(cadree, sx, sy)
    grille = _quantifier(reduite, palette, sx, sy, False)

    plancher = palette_floor(reduite, palette)
    obtenu = fidelity(grille, cadree, 1)[0]
    # Sans tramage, chaque tenon prend le plus proche : le resultat EST le
    # plancher. Un ecart signalerait que `nearest` n'est pas optimal.
    assert abs(obtenu - plancher) < 0.05, (obtenu, plancher)
    # Et le plancher est strictement positif : une palette finie ne peut pas
    # rendre une photo continue.
    assert plancher > 0.5


def test_la_mesure_de_detail_refuse_une_grille_trop_grossiere():
    """Une grille plus grossiere que la mosaique rate son detail au lieu de le
    mesurer — et faisait passer 128 tenons pour pire que 96."""
    from bfk001.mosaic import _cadrer, _quantifier, detail_gap, grille_de_mesure
    from bfk001.imaging import resample_box

    palette = bfk.PROVISIONAL_PALETTE.solids_only()
    image = bfk.Image.from_pixels(128, 128, [
        (x * 2, y * 2, 128) for y in range(128) for x in range(128)])
    cadree = _cadrer(image, 48, 48, "crop", 0.5)
    grille = _quantifier(resample_box(cadree, 48, 48), palette, 48, 48, False)

    with pytest.raises(ValueError, match="plus grossiere"):
        detail_gap(grille, cadree, 48, 48, (16, 16))
    assert detail_gap(grille, cadree, 48, 48, grille_de_mesure(48, 48)) > 0


def test_le_detail_s_ameliore_avec_la_taille_la_ou_l_ecart_par_tuile_stagne():
    """Les deux mesures ne disent pas la meme chose, et c'est le sujet.

    `fidelity(block=1)` compare chaque tuile a la zone qu'elle remplace : la
    zone retrecit avec le nombre de tenons, donc la mesure reste plate. Elle est
    bornee par la palette. `detail_gap` compare aux MEMES points physiques,
    quelle que soit la taille — c'est elle qui voit ce qu'on gagne.

    Sur une photo reelle : par tuile 6,79 -> 6,66 de 32 a 96 tenons (rien),
    detail 10,0 -> 7,9 (beaucoup).
    """
    from bfk001.mosaic import (_cadrer, _quantifier, detail_gap, fidelity,
                               grille_de_mesure)
    from bfk001.imaging import resample_box

    palette = bfk.PROVISIONAL_PALETTE.solids_only()
    # La structure doit vivre a une echelle que 24 tenons ratent et que 96
    # resout : dans une image de 240 pixels, cela fait des motifs d'une
    # douzaine de pixels (10 px par tenon a 24, 2,5 px a 96). Un damier plus
    # fin que TOUTES les resolutions comparees serait moyenne pareil par
    # toutes, et ne prouverait rien — c'est l'erreur du premier essai.
    n = 240
    pixels = []
    for y in range(n):
        for x in range(n):
            clair = ((x // 12) + (y // 12)) % 2
            pixels.append((230, 225, 210) if clair else (35, 45, 70))
    image = bfk.Image.from_pixels(n, n, pixels)

    tailles = (24, 48, 96)
    mesure = grille_de_mesure(max(tailles), max(tailles))
    par_tuile, details = [], []
    for cote in tailles:
        cadree = _cadrer(image, cote, cote, "crop", 0.5)
        grille = _quantifier(resample_box(cadree, cote, cote), palette,
                             cote, cote, False)
        par_tuile.append(fidelity(grille, cadree, 1)[0])
        details.append(detail_gap(grille, cadree, cote, cote, mesure))

    # Le detail s'ameliore franchement, et de facon monotone.
    assert details == sorted(details, reverse=True), details
    assert details[0] - details[-1] > 1.0, details
    # L'ecart par tuile, lui, bouge a peine : il ne repond pas a la question.
    assert abs(par_tuile[0] - par_tuile[-1]) < details[0] - details[-1]


def test_le_conseil_de_format_met_les_formats_en_balance():
    from bfk001.pipeline import conseil_de_format

    palette = bfk.PROVISIONAL_PALETTE.solids_only()
    n = 160
    image = bfk.Image.from_pixels(n, n, [
        (int(30 + 200 * x / n), int(70 + 140 * y / n), (x * y) % 251)
        for y in range(n) for x in range(n)])

    from bfk001.pipeline import Reglages

    reglages = Reglages(studs=24, hauteur=24)
    conseils = conseil_de_format(image, 24, 24, palette, reglages,
                                 multiples=(1.0, 2.0))
    assert [c["studs_x"] for c in conseils] == [24, 48]
    # Plus grand : plus de pieces, et plus de detail.
    assert conseils[1]["pieces"] > conseils[0]["pieces"]
    assert conseils[1]["detail"] < conseils[0]["detail"]
    # Les centimetres sont ceux de l'oeuvre HORS TOUT, cadre compris : c'est
    # la mesure qu'on prend contre un mur, et le cadre par defaut ajoute deux
    # tenons de chaque cote.
    hors_tout = 24 + 2 * reglages.cadre
    assert conseils[0]["largeur_cm"] == round(hors_tout * 0.8)
    # Sans cadre, la taille redescend a celle de l'image seule.
    nu = conseil_de_format(image, 24, 24, palette,
                           Reglages(studs=24, hauteur=24, cadre=0),
                           multiples=(1.0,))[0]
    assert nu["largeur_cm"] == round(24 * 0.8)
