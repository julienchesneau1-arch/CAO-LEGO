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


def test_le_tramage_auto_juge_la_grille_livree_et_non_une_grille_intermediaire():
    """Le tramage « auto » decidait sur une grille que la chaine modifie apres.

    Trouve sur une photo reelle. Le tramage y gagnait 5,20 delta E sur le pire
    ecart tonal — largement au-dessus du seuil — et le nettoyage des tuiles
    isolees, applique juste apres, effacait 604 des 710 tuiles tramees et
    ramenait le gain a 0,00. On payait 227 pieces et tout le grain pour rien.

    Les deux etapes ont ete ajoutees a des moments differents ; personne
    n'avait regarde leur interaction. Ce test la regarde : sur une image ou le
    tramage produit du grain que le nettoyage efface, la decision doit basculer
    des qu'on lui dit avec quelle tolerance l'appelant nettoiera.
    """
    from bfk001.mosaic import (_cadrer, _quantifier, denoise, fidelity,
                               isolated_tiles, quantize, DITHER_AUTO_MIN_GAIN)
    from bfk001.imaging import resample_box

    palette = bfk.PROVISIONAL_PALETTE.solids_only()
    # Un degrade neutre dans les mi-tons, la ou la palette provisoire a son
    # plus grand trou de clarte (L* 46 -> 67) : le tramage s'y agite le plus,
    # et le nettoyage reprend presque tout ce qu'il a seme.
    cote = 200
    pixels = [(int(120 + 50 * y / cote), int(122 + 48 * y / cote),
               int(118 + 50 * y / cote))
              for y in range(cote) for _ in range(cote)]
    image = bfk.Image.from_pixels(cote, cote, pixels)

    sx = sy = 48
    cadree = _cadrer(image, sx, sy, "crop", 0.5)
    reduite = resample_box(cadree, sx, sy)
    sans = _quantifier(reduite, palette, sx, sy, False)
    avec = _quantifier(reduite, palette, sx, sy, "adaptive")

    brut = fidelity(sans, cadree, 4)[1] - fidelity(avec, cadree, 4)[1]
    livre = (fidelity(denoise(sans, cadree, 4.0, "stretch", 0.5), cadree, 4)[1]
             - fidelity(denoise(avec, cadree, 4.0, "stretch", 0.5), cadree, 4)[1])

    # L'image doit bien poser la question : gain franc avant nettoyage, gain
    # efface apres. Sans cela le test ne prouverait rien.
    assert brut >= DITHER_AUTO_MIN_GAIN, f"gain brut trop faible : {brut}"
    assert livre < DITHER_AUTO_MIN_GAIN, f"le nettoyage ne l'efface pas : {livre}"

    sans_tolerance = quantize(image, palette, sx, sy, "auto", "crop", 0.5)
    avec_tolerance = quantize(image, palette, sx, sy, "auto", "crop", 0.5,
                              denoise_tolerance=4.0)
    assert sans_tolerance == avec, "sans tolerance, la decision reste l'ancienne"
    assert avec_tolerance == sans, "avec tolerance, le tramage doit etre ecarte"
    assert (len(isolated_tiles(avec_tolerance))
            < len(isolated_tiles(sans_tolerance)))


def test_le_tramage_auto_reste_choisi_la_ou_il_sert_vraiment():
    """Le correctif ne doit pas jeter le tramage la ou il gagne pour de bon.

    Un ciel degrade est le cas d'ecole : des bandes franches que le tramage
    casse, et un gain qui SURVIT au nettoyage.
    """
    from bfk001.mosaic import _cadrer, _quantifier, quantize
    from bfk001.imaging import resample_box

    palette = bfk.PROVISIONAL_PALETTE.solids_only()
    cote = 200
    pixels = [(int(70 + 130 * y / cote), int(120 + 110 * y / cote),
               int(210 - 30 * y / cote))
              for y in range(cote) for _ in range(cote)]
    ciel = bfk.Image.from_pixels(cote, cote, pixels)

    sx = sy = 48
    reduite = resample_box(_cadrer(ciel, sx, sy, "crop", 0.5), sx, sy)
    trame = _quantifier(reduite, palette, sx, sy, "adaptive")
    assert quantize(ciel, palette, sx, sy, "auto", "crop", 0.5,
                    denoise_tolerance=4.0) == trame
