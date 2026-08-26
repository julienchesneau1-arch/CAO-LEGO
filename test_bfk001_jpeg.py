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

    # SOF2 : progressif. Le decodeur doit le dire, pas rendre du bruit.
    valide = bytearray(encode_jpeg_blocs_unis([[128] * 12], 4, 3, 1))
    position = valide.index(b"\xff\xc0")
    valide[position + 1] = 0xC2
    with pytest.raises(ValueError, match="progressif"):
        bfk.read_jpeg_eighth(bytes(valide))


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
