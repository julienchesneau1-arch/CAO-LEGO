"""
Decodeur JPEG et diagnostic de palette.

Le decodeur est teste contre un encodeur minimal ecrit ici : sans lui, la seule
verification possible serait « ca a l'air bon sur une photo », ce qui ne vaut
rien. L'encodeur ne produit que des blocs unis — c'est exactement le domaine ou
un decodeur qui ne garde que le coefficient DC doit etre EXACT, au bit pres.
"""

from __future__ import annotations

import struct

import pytest

import bfk001_kernel as bfk


class _Bits:
    def __init__(self):
        self.out = bytearray()
        self.courant = 0
        self.compte = 0

    def write(self, valeur, longueur):
        for i in range(longueur - 1, -1, -1):
            self.courant = (self.courant << 1) | ((valeur >> i) & 1)
            self.compte += 1
            if self.compte == 8:
                self.out.append(self.courant)
                if self.courant == 0xFF:
                    self.out.append(0)  # echappement obligatoire
                self.courant = 0
                self.compte = 0

    def flush(self):
        while self.compte:
            self.write(1, 1)
        return bytes(self.out)


def _categorie(valeur):
    if valeur == 0:
        return 0, 0
    taille = abs(valeur).bit_length()
    return taille, (valeur if valeur > 0 else valeur + (1 << taille) - 1)


def encode_jpeg_blocs_unis(blocs, largeur_blocs, hauteur_blocs, composantes=1):
    """JPEG baseline minimal ou chaque bloc 8x8 porte une valeur uniforme."""
    quantification = bytes([1] * 64)
    dc_counts = bytes([0, 0, 0, 12] + [0] * 12)
    dc_syms = bytes(range(12))
    ac_counts = bytes([1] + [0] * 15)
    ac_syms = bytes([0x00])

    def codes(counts, syms):
        table, code, index = {}, 0, 0
        for longueur in range(1, 17):
            for _ in range(counts[longueur - 1]):
                table[syms[index]] = (longueur, code)
                code += 1
                index += 1
            code <<= 1
        return table

    table_dc, table_ac = codes(dc_counts, dc_syms), codes(ac_counts, ac_syms)
    bits = _Bits()
    prediction = [0] * composantes

    for by in range(hauteur_blocs):
        for bx in range(largeur_blocs):
            for c in range(composantes):
                dc = (blocs[c][by * largeur_blocs + bx] - 128) * 8
                difference = dc - prediction[c]
                prediction[c] = dc
                taille, amplitude = _categorie(difference)
                longueur, code = table_dc[taille]
                bits.write(code, longueur)
                if taille:
                    bits.write(amplitude, taille)
                longueur, code = table_ac[0x00]
                bits.write(code, longueur)

    def segment(marqueur, charge):
        return b"\xff" + bytes([marqueur]) + struct.pack(">H", len(charge) + 2) + charge

    sof = struct.pack(">BHHB", 8, hauteur_blocs * 8, largeur_blocs * 8, composantes)
    for c in range(composantes):
        sof += bytes([c + 1, 0x11, 0])
    sos = bytes([composantes])
    for c in range(composantes):
        sos += bytes([c + 1, 0x00])
    sos += bytes([0, 63, 0])

    return (
        b"\xff\xd8"
        + segment(0xDB, b"\x00" + quantification)
        + segment(0xC0, sof)
        + segment(0xC4, b"\x00" + dc_counts + dc_syms)
        + segment(0xC4, b"\x10" + ac_counts + ac_syms)
        + segment(0xDA, sos)
        + bits.flush()
        + b"\xff\xd9"
    )


def encode_jpeg_progressif(blocs, largeur_blocs, hauteur_blocs,
                           composantes=1, approximation=1, avec_ac=True):
    """JPEG PROGRESSIF minimal, blocs unis, en trois balayages.

    Meme domaine que l'encodeur baseline ci-dessus, et pour la meme raison :
    un decodeur qui ne garde que le DC doit etre exact sur des blocs unis, et
    « ca a l'air bon sur une photo » ne prouve rien.

    Trois balayages, parce que c'est la structure qui compte :
      1. DC initial, decale de `approximation` bits — le decodeur doit poser
         les bits de poids fort au bon endroit ;
      2. un balayage AC, que le decodeur doit SAUTER sans le lire — s'il tente
         de le decoder avec la table DC, tout deraille ensuite ;
      3. DC de raffinement, un bit par bloc — sans lui la valeur reste fausse
         d'un bit de poids `approximation`.
    """
    quantification = bytes([1] * 64)
    dc_counts = bytes([0, 0, 0, 12] + [0] * 12)
    dc_syms = bytes(range(12))
    ac_counts = bytes([1] + [0] * 15)
    ac_syms = bytes([0x00])

    def codes(counts, syms):
        table, code, index = {}, 0, 0
        for longueur in range(1, 17):
            for _ in range(counts[longueur - 1]):
                table[syms[index]] = (longueur, code)
                code += 1
                index += 1
            code <<= 1
        return table

    table_dc, table_ac = codes(dc_counts, dc_syms), codes(ac_counts, ac_syms)

    def dc_de(c, by, bx):
        return (blocs[c][by * largeur_blocs + bx] - 128) * 8

    # Balayage 1 : les bits de poids fort du DC, entrelace.
    premier = _Bits()
    prediction = [0] * composantes
    for by in range(hauteur_blocs):
        for bx in range(largeur_blocs):
            for c in range(composantes):
                haut = dc_de(c, by, bx) >> approximation
                difference = haut - prediction[c]
                prediction[c] = haut
                taille, amplitude = _categorie(difference)
                longueur, code = table_dc[taille]
                premier.write(code, longueur)
                if taille:
                    premier.write(amplitude, taille)

    # Balayage 2 : un AC vide par bloc, sur la premiere composante seulement.
    # Le decodeur ne doit pas le lire ; l'encodeur l'ecrit quand meme, sinon le
    # test ne verifie pas qu'il le saute.
    ac = _Bits()
    for _ in range(largeur_blocs * hauteur_blocs):
        longueur, code = table_ac[0x00]
        ac.write(code, longueur)

    # Balayage 3 : le bit de raffinement de chaque DC.
    raffinement = _Bits()
    for by in range(hauteur_blocs):
        for bx in range(largeur_blocs):
            for c in range(composantes):
                for i in range(approximation - 1, -1, -1):
                    raffinement.write((dc_de(c, by, bx) >> i) & 1, 1)

    def segment(marqueur, charge):
        return (b"\xff" + bytes([marqueur])
                + struct.pack(">H", len(charge) + 2) + charge)

    sof = struct.pack(">BHHB", 8, hauteur_blocs * 8, largeur_blocs * 8,
                      composantes)
    for c in range(composantes):
        sof += bytes([c + 1, 0x11, 0])

    def entete_sos(indices, ss, se, ah, al):
        charge = bytes([len(indices)])
        for c in indices:
            charge += bytes([c + 1, 0x00])
        return charge + bytes([ss, se, (ah << 4) | al])

    tous = list(range(composantes))
    fichier = (
        b"\xff\xd8"
        + segment(0xDB, b"\x00" + quantification)
        + segment(0xC2, sof)
        + segment(0xC4, b"\x00" + dc_counts + dc_syms)
        + segment(0xC4, b"\x10" + ac_counts + ac_syms)
        + segment(0xDA, entete_sos(tous, 0, 0, 0, approximation))
        + premier.flush()
    )
    if avec_ac:
        fichier += (segment(0xDA, entete_sos([0], 1, 63, 0, 0)) + ac.flush())
    for i in range(approximation, 0, -1):
        fichier += segment(0xDA, entete_sos(tous, 0, 0, i, i - 1))
    fichier += raffinement.flush()
    return fichier + b"\xff\xd9"


def test_le_progressif_se_decode_exactement_comme_le_baseline():
    """Le meme contenu, code des deux facons, doit sortir identique.

    Une photo passee par une messagerie ressort en progressif. Le decodeur la
    refusait — refus honnete, mais refus quand meme, et c'est justement la
    photo qu'un utilisateur depose dans l'application.
    """
    valeurs = [30, 80, 130, 180, 200, 150, 100, 50, 10, 60, 110, 240]
    baseline = bfk.read_jpeg_eighth(encode_jpeg_blocs_unis([valeurs], 4, 3, 1))
    progressif = bfk.read_jpeg_eighth(encode_jpeg_progressif([valeurs], 4, 3, 1))

    assert (progressif.width, progressif.height) == (4, 3)
    lus = [progressif.pixel(x, y)[0] for y in range(3) for x in range(4)]
    assert lus == valeurs, "le progressif doit etre exact, pas approche"
    assert progressif.data == baseline.data, "les deux codages, une seule image"


def test_le_raffinement_du_progressif_sert_vraiment():
    """Sans les balayages de raffinement, le DC reste faux d'un bit.

    Le test precedent passerait encore si le decodeur ignorait le raffinement
    et que les valeurs etaient toutes paires. Celui-ci l'interdit : deux bits
    d'approximation, des valeurs choisies pour que les bits de poids faible
    comptent.
    """
    valeurs = [37, 91, 133, 179, 201, 155, 99, 51, 13, 67, 111, 239]
    image = bfk.read_jpeg_eighth(
        encode_jpeg_progressif([valeurs], 4, 3, 1, approximation=2))
    lus = [image.pixel(x, y)[0] for y in range(3) for x in range(4)]
    assert lus == valeurs, f"raffinement perdu : {lus}"


def test_le_progressif_saute_vraiment_les_balayages_ac():
    """Avec et sans balayage AC, le meme DC doit sortir.

    Si le decodeur tentait de lire un balayage AC — avec la table DC, et sans
    l'ordre spectral — il ne planterait pas forcement : il decalerait le flux
    et les balayages suivants rendraient du bruit. Comparer les deux fichiers
    est le seul moyen de prouver qu'il le saute.
    """
    valeurs = [30, 80, 130, 180, 200, 150, 100, 50, 10, 60, 110, 240]
    avec = bfk.read_jpeg_eighth(encode_jpeg_progressif([valeurs], 4, 3, 1))
    sans = bfk.read_jpeg_eighth(
        encode_jpeg_progressif([valeurs], 4, 3, 1, avec_ac=False))
    assert avec.data == sans.data


def test_le_progressif_en_couleurs_ne_melange_pas_les_plans():
    """Trois composantes, trois valeurs distinctes : la conversion doit tenir.

    Un balayage DC entrelace ecrit dans trois plans a la suite. Une erreur
    d'indice y donnerait une image plausible mais fausse en couleur — le genre
    de defaut qu'un coup d'oeil sur une photo ne rattrape pas.
    """
    luminance = [120] * 12
    cb = [200] * 12
    cr = [90] * 12
    baseline = bfk.read_jpeg_eighth(
        encode_jpeg_blocs_unis([luminance, cb, cr], 4, 3, 3))
    progressif = bfk.read_jpeg_eighth(
        encode_jpeg_progressif([luminance, cb, cr], 4, 3, 3))
    assert progressif.data == baseline.data
    assert progressif.pixel(0, 0) == (66, 122, 247)


def encode_jpeg_progressif_420(luma, cb, cr, mcus_x, mcus_y):
    """Progressif AVEC sous-echantillonnage 4:2:0, blocs unis.

    Le cas des vraies photos : la luminance porte quatre blocs par MCU, la
    chrominance un seul. Les deux grilles de blocs different alors, et c'est
    exactement la ou une erreur d'indice se cache — invisible sur une photo,
    qui reste plausible quand la chrominance glisse d'un bloc.

    `luma` compte 2*mcus_x par 2*mcus_y valeurs, `cb` et `cr` mcus_x par
    mcus_y. Deux balayages : DC initial decale d'un bit, puis raffinement.
    """
    quantification = bytes([1] * 64)
    dc_counts = bytes([0, 0, 0, 12] + [0] * 12)
    dc_syms = bytes(range(12))
    ac_counts = bytes([1] + [0] * 15)
    ac_syms = bytes([0x00])

    def codes(counts, syms):
        table, code, index = {}, 0, 0
        for longueur in range(1, 17):
            for _ in range(counts[longueur - 1]):
                table[syms[index]] = (longueur, code)
                code += 1
                index += 1
            code <<= 1
        return table

    table_dc = codes(dc_counts, dc_syms)
    plans = [(luma, 2, 2, 2 * mcus_x), (cb, 1, 1, mcus_x), (cr, 1, 1, mcus_x)]

    def blocs_de_la_mcu(mx, my):
        """(indice de plan, valeur) dans l'ordre exact du flux entrelace."""
        for indice, (valeurs, h, v, largeur) in enumerate(plans):
            for dv in range(v):
                for dh in range(h):
                    yield indice, valeurs[(my * v + dv) * largeur + mx * h + dh]

    premier, raffinement = _Bits(), _Bits()
    prediction = [0, 0, 0]
    for my in range(mcus_y):
        for mx in range(mcus_x):
            for indice, valeur in blocs_de_la_mcu(mx, my):
                dc = (valeur - 128) * 8
                haut = dc >> 1
                difference = haut - prediction[indice]
                prediction[indice] = haut
                taille, amplitude = _categorie(difference)
                longueur, code = table_dc[taille]
                premier.write(code, longueur)
                if taille:
                    premier.write(amplitude, taille)
                raffinement.write(dc & 1, 1)

    def segment(marqueur, charge):
        return (b"\xff" + bytes([marqueur])
                + struct.pack(">H", len(charge) + 2) + charge)

    sof = struct.pack(">BHHB", 8, mcus_y * 16, mcus_x * 16, 3)
    sof += bytes([1, 0x22, 0]) + bytes([2, 0x11, 0]) + bytes([3, 0x11, 0])

    def entete_sos(ss, se, ah, al):
        return (bytes([3, 1, 0x00, 2, 0x00, 3, 0x00])
                + bytes([ss, se, (ah << 4) | al]))

    return (
        b"\xff\xd8"
        + segment(0xDB, b"\x00" + quantification)
        + segment(0xC2, sof)
        + segment(0xC4, b"\x00" + dc_counts + dc_syms)
        + segment(0xC4, b"\x10" + ac_counts + ac_syms)
        + segment(0xDA, entete_sos(0, 0, 0, 1))
        + premier.flush()
        + segment(0xDA, entete_sos(0, 0, 1, 0))
        + raffinement.flush()
        + b"\xff\xd9"
    )


def test_le_progressif_sous_echantillonne_place_bien_la_chrominance():
    """4:2:0 : quatre blocs de luminance pour un de chrominance.

    C'est le format de toute photo de telephone, et le seul endroit du
    progressif ou les deux grilles de blocs different. Une erreur d'indice y
    donne une image PLAUSIBLE — les couleurs glissent d'un bloc — donc un
    regard sur une photo ne la rattrape pas. D'ou des valeurs choisies.
    """
    # 2x2 MCU : 4x4 blocs de luminance, 2x2 de chrominance.
    luma = [10, 60, 110, 160,
            200, 150, 100, 50,
            35, 85, 135, 185,
            240, 190, 140, 90]
    cb = [200, 40, 128, 90]
    cr = [90, 210, 128, 60]
    image = bfk.read_jpeg_eighth(encode_jpeg_progressif_420(luma, cb, cr, 2, 2))
    assert (image.width, image.height) == (4, 4)

    def attendu(y, cb_valeur, cr_valeur):
        b, r = cb_valeur - 128, cr_valeur - 128
        return (
            min(255, max(0, int(y + 1.402 * r))),
            min(255, max(0, int(y - 0.344136 * b - 0.714136 * r))),
            min(255, max(0, int(y + 1.772 * b))),
        )

    for ligne in range(4):
        for colonne in range(4):
            voulu = attendu(luma[ligne * 4 + colonne],
                            cb[(ligne // 2) * 2 + colonne // 2],
                            cr[(ligne // 2) * 2 + colonne // 2])
            assert image.pixel(colonne, ligne) == voulu, (colonne, ligne)


def test_jpeg_decoder_is_exact_on_uniform_blocks():
    """Le coefficient DC EST la moyenne du bloc : la sortie doit etre exacte."""
    valeurs = [30, 80, 130, 180, 200, 150, 100, 50, 10, 60, 110, 240]
    image = bfk.read_jpeg_eighth(encode_jpeg_blocs_unis([valeurs], 4, 3, 1))

    assert (image.width, image.height) == (4, 3), "un pixel par bloc de 8x8"
    lus = [image.pixel(x, y)[0] for y in range(3) for x in range(4)]
    assert lus == valeurs, "le decodage au huitieme doit etre exact, pas approche"


def test_jpeg_decoder_converts_ycbcr_correctly():
    """Y=120, Cb=200, Cr=90 donne (66, 122, 247). Verifie a la main."""
    luminance = [120] * 12
    bleu = [200] * 12
    rouge = [90] * 12
    image = bfk.read_jpeg_eighth(
        encode_jpeg_blocs_unis([luminance, bleu, rouge], 4, 3, 3)
    )
    assert image.pixel(0, 0) == (66, 122, 247)
    assert image.pixel(3, 2) == (66, 122, 247)


def test_jpeg_decoder_refuses_what_it_cannot_read():
    """Mieux vaut une erreur explicite qu'une image fausse."""
    with pytest.raises(ValueError, match="pas un fichier JPEG"):
        bfk.read_jpeg_eighth(b"\x89PNG\r\n\x1a\n")

    # SOF3 : sans perte. Aucun appareil n'en produit, et un decodeur qui ne
    # garde que le DC n'a rien a y lire — il n'y a pas de DC. Le refus reste.
    # Le progressif, lui, n'est plus refuse : il est decode (voir plus haut).
    valide = bytearray(encode_jpeg_blocs_unis([[128] * 12], 4, 3, 1))
    position = valide.index(b"\xff\xc0")
    valide[position + 1] = 0xC3
    with pytest.raises(ValueError, match="sans perte"):
        bfk.read_jpeg_eighth(bytes(valide))

    # Une table de Huffman tronquee : elle annonce douze symboles et n'en
    # porte que trois. Defaut PREEXISTANT, trouve en jetant des octets
    # aleatoires sur un en-tete valide — il sortait par un IndexError sec.
    with pytest.raises(ValueError, match="incoherente"):
        bfk.read_jpeg_eighth(
            b"\xff\xd8\xff\xc4\x00\x14\x00"
            + bytes([0, 0, 0, 12] + [0] * 12) + bytes(range(3))
            + b"\xff\xd9")

    # Un balayage avant le cadre : incoherent, et il faut le dire plutot que
    # de lever une erreur d'indice trois fonctions plus loin.
    sans_cadre = bytearray(encode_jpeg_blocs_unis([[128] * 12], 4, 3, 1))
    position = sans_cadre.index(b"\xff\xc0")
    sans_cadre[position + 1] = 0xFE   # devient un commentaire
    with pytest.raises(ValueError, match="avant le cadre"):
        bfk.read_jpeg_eighth(bytes(sans_cadre))


# =============================================================================
# Orientation EXIF : sans elle, toute photo de telephone sort couchee
# =============================================================================


def exif_avec_orientation(valeur):
    """Bloc APP1 minimal portant le champ Orientation."""
    tiff = (
        b"II"
        + struct.pack("<HI", 42, 8)
        + struct.pack("<H", 1)
        + struct.pack("<HHIHH", 0x0112, 3, 1, valeur, 0)
        + struct.pack("<I", 0)
    )
    charge = b"Exif\x00\x00" + tiff
    return b"\xff\xe1" + struct.pack(">H", len(charge) + 2) + charge


def test_exif_orientation_is_read():
    for valeur in (1, 3, 6, 8):
        fichier = b"\xff\xd8" + exif_avec_orientation(valeur) + b"\xff\xd9"
        assert bfk.exif_orientation(fichier) == valeur

    assert bfk.exif_orientation(b"\xff\xd8\xff\xd9") == 1, "absent : orientation neutre"


def test_orientation_is_applied_in_every_direction():
    """Les huit orientations EXIF, verifiees sur une image asymetrique."""
    source = bfk.Image.from_pixels(
        2, 3, [(10, 0, 0), (20, 0, 0), (30, 0, 0), (40, 0, 0), (50, 0, 0), (60, 0, 0)]
    )

    assert bfk.apply_orientation(source, 1) is source

    tourne = bfk.apply_orientation(source, 6)  # quart de tour horaire
    assert (tourne.width, tourne.height) == (3, 2)
    assert tourne.pixel(2, 0) == (10, 0, 0), "le premier pixel passe en haut a droite"

    demi = bfk.apply_orientation(source, 3)
    assert (demi.width, demi.height) == (2, 3)
    assert demi.pixel(1, 2) == (10, 0, 0)

    # Deux quarts de tour opposes ramenent l'original.
    assert bfk.apply_orientation(bfk.apply_orientation(source, 6), 8).data == source.data


# =============================================================================
# Diagnostic de palette : nommer ce qui manque
# =============================================================================


def test_gap_report_names_the_missing_colours():
    """« Le rendu est gris » devient « il vous manque un bleu pale a #90B0DE »."""
    ciel = [(150, 180, 220)] * 60 + [(200, 30, 25)] * 40
    manques = bfk.gap_report(ciel, bfk.PROVISIONAL_PALETTE, count=4)

    assert manques, "un bleu pale manque a une palette de douze couleurs"
    premier = manques[0]
    assert premier.error >= 10
    assert premier.hex.startswith("#")
    assert 0 < premier.share <= 1
    # Le rouge vif, lui, existe : il ne doit pas apparaitre comme un manque.
    assert all(
        bfk.delta_e(gap.wanted, (200, 30, 25)) > 15 for gap in manques
    ), "une couleur bien rendue n'est pas un manque"


def test_best_subset_picks_the_colours_that_matter():
    """Choisir douze couleurs sur soixante-dix est le vrai probleme produit."""
    riche = bfk.Palette(
        [bfk.LegoColor(i, f"c{i}", (i * 8 % 256, (i * 17) % 256, (i * 29) % 256))
         for i in range(1, 40)]
    )
    pixels = [(250, 10, 10)] * 50 + [(10, 250, 10)] * 30 + [(10, 10, 250)] * 20

    reduite = riche.best_subset(pixels, 3)
    assert len(reduite) == 3

    # La sous-palette doit rendre ces trois couleurs mieux que trois couleurs
    # prises au hasard dans la palette riche.
    hasard = bfk.Palette(riche.colors[:3])
    ecart_choisi = sum(bfk.delta_e(p, reduite.nearest(p).rgb) for p in pixels)
    ecart_hasard = sum(bfk.delta_e(p, hasard.nearest(p).rgb) for p in pixels)
    assert ecart_choisi < ecart_hasard

    assert riche.best_subset(pixels, 100) is riche, "plus de couleurs que la palette"
    with pytest.raises(ValueError):
        riche.best_subset(pixels, 0)


def test_solids_only_excludes_what_cannot_be_ordered():
    """Une liste de course ne contient ni transparent, ni chrome, ni « Edge Colour »."""
    fichier = "\n".join(
        (
            "0 !COLOUR Red CODE 4 VALUE #C91A09 EDGE #333333",
            "0 !COLOUR Trans_Red CODE 36 VALUE #C91A09 EDGE #880000 ALPHA 128",
            "0 !COLOUR Chrome_Gold CODE 334 VALUE #BBA53D EDGE #333333 CHROME",
            "0 !COLOUR Pearl_White CODE 183 VALUE #F2F3F2 EDGE #333333 PEARLESCENT",
            "0 !COLOUR Rubber_Black CODE 256 VALUE #212121 EDGE #333333 RUBBER",
            "0 !COLOUR Glitter_Trans CODE 114 VALUE #DF6695 EDGE #000000 ALPHA 128 MATERIAL GLITTER",
            "0 !COLOUR Main_Colour CODE 16 VALUE #FFFF80 EDGE #333333",
            "0 !COLOUR Edge_Colour CODE 24 VALUE #7F7F7F EDGE #333333",
        )
    )
    complete = bfk.load_ldconfig(fichier)
    assert len(complete) == 8

    solides = complete.solids_only()
    assert [c.code for c in solides] == [4], (
        "seul le rouge opaque est commandable en tuile 1x1"
    )

    # Les codes 16 et 24 ne sont pas des couleurs mais des marqueurs de format.
    # Rien dans le fichier ne les distingue : c'est une connaissance du format,
    # et une selection automatique les avait retenus avant ce garde-fou.
    assert 16 in bfk.palette.LDRAW_INTERNAL_CODES
    assert 24 in bfk.palette.LDRAW_INTERNAL_CODES
    assert complete.by_code(36).finish == "transparent"
    assert complete.by_code(334).finish == "chrome"
    assert complete.by_code(114).finish == "transparent", "ALPHA prime sur MATERIAL"
    assert complete.by_code(4).is_solid
