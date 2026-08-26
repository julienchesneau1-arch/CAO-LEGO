"""La profondeur MESUREE, par opposition a la convention.

Tout le relief livre ailleurs est une convention : elever selon la clarte est
le parti du camee, et il se trompe la ou la photo le contredit. Ce fichier
verifie le seul chemin qui ne soit pas une convention — une carte de
profondeur, fournie ou extraite du fichier photo lui-meme.

Les conteneurs sont fabriques ici, a la norme. C'est une limite qu'il faut
dire : ils verifient l'analyseur contre le FORMAT, pas contre les
particularites d'un appareil reel, que je n'ai pas sous la main.
"""

import base64
import unittest

import bfk001 as bfk
from bfk001.depth import DepthMismatch, NoEmbeddedDepth


def carte(largeur, hauteur, valeur_dedans=255, valeur_dehors=30):
    """Deux profondeurs seulement : un disque proche sur un fond lointain."""
    pixels = bytearray()
    for y in range(hauteur):
        for x in range(largeur):
            dedans = ((x - largeur / 2) ** 2 + (y - hauteur / 2) ** 2
                      < (min(largeur, hauteur) * 0.3) ** 2)
            v = valeur_dedans if dedans else valeur_dehors
            pixels += bytes((v, v, v))
    return bfk.Image(largeur, hauteur, bytes(pixels))


def photo_contraire(largeur, hauteur):
    """Sujet SOMBRE sur fond CLAIR : le cas ou la convention se trompe."""
    pixels = bytearray()
    for y in range(hauteur):
        for x in range(largeur):
            dedans = ((x - largeur / 2) ** 2 + (y - hauteur / 2) ** 2
                      < (min(largeur, hauteur) * 0.3) ** 2)
            v = 30 if dedans else 220
            pixels += bytes((v, v, v))
    return bfk.Image(largeur, hauteur, bytes(pixels))


def jpeg_minimal(app1: bytes = b"", suite: bytes = b"") -> bytes:
    """SOI, un APP1 facultatif, EOI — puis ce qu'on veut concatener.

    Suffisant pour l'analyse de conteneur, qui ne decode jamais l'image
    primaire : elle cherche ses entetes et la fin de son balayage.
    """
    segment = b""
    if app1:
        segment = b"\xff\xe1" + (len(app1) + 2).to_bytes(2, "big") + app1
    return b"\xff\xd8" + segment + b"\xff\xd9" + suite


XMP = b"http://ns.adobe.com/xap/1.0/\x00"
XMP_ETENDU = b"http://ns.adobe.com/xmp/extension/\x00"


class TestLectureDeCarte(unittest.TestCase):
    def test_les_trois_formats_se_lisent(self):
        image = carte(24, 24)
        png = bfk.write_png(image)
        ppm = b"P6\n24 24\n255\n" + image.data
        self.assertEqual(bfk.read_depth_map(png).width, 24)
        self.assertEqual(bfk.read_depth_map(ppm).width, 24)

    def test_un_format_inconnu_est_refuse_et_non_devine(self):
        with self.assertRaises(ValueError):
            bfk.read_depth_map(b"GIF89a" + b"\x00" * 40)


class TestCorrespondanceAvecLaPhoto(unittest.TestCase):
    """Le controle qui separe un relief juste d'un relief faux mais propre."""

    def test_une_carte_d_un_autre_cadrage_est_refusee(self):
        photo = photo_contraire(240, 240)
        with self.assertRaises(DepthMismatch):
            bfk.heights_from_depth(carte(320, 240), photo, 24, 24, 2)

    def test_un_arrondi_de_redimensionnement_reste_tolere(self):
        # 239x240 contre 240x240 : moins d'un demi pour cent, c'est la meme
        # image a un pixel pres. La refuser serait un faux positif.
        photo = photo_contraire(240, 240)
        hauteurs = bfk.heights_from_depth(carte(239, 240), photo, 24, 24, 2)
        self.assertEqual(len(hauteurs), 24)


class TestLaMesureContreditLaConvention(unittest.TestCase):
    """Le seul cas qui justifie tout ce module."""

    def setUp(self):
        self.photo = photo_contraire(240, 240)
        self.carte = carte(240, 240)

    def centre_et_bord(self, hauteurs):
        cote = len(hauteurs)
        return hauteurs[cote // 2][cote // 2], hauteurs[0][0]

    def test_la_convention_enfonce_un_sujet_sombre(self):
        convention = bfk.mosaic.relief_from_image(self.photo, 24, 24, 2)
        centre, bord = self.centre_et_bord(convention)
        self.assertLess(centre, bord,
                        "clair = haut : un sujet sombre DOIT sortir en creux")

    def test_la_mesure_le_remet_devant(self):
        mesure = bfk.heights_from_depth(self.carte, self.photo, 24, 24, 2)
        centre, bord = self.centre_et_bord(mesure)
        self.assertGreater(centre, bord,
                           "la carte dit que le sujet est proche")

    def test_la_convention_d_encodage_se_retourne(self):
        distance = bfk.heights_from_depth(
            self.carte, self.photo, 24, 24, 2, near_is_bright=False)
        centre, bord = self.centre_et_bord(distance)
        self.assertLess(centre, bord)


class TestMedianePlutotQueMoyenne(unittest.TestCase):
    """Moyenner deux distances de part et d'autre d'un bord invente une
    distance qui n'existe nulle part dans la scene."""

    def test_la_moyenne_fabrique_des_profondeurs_absentes(self):
        source = carte(240, 240)
        moyenne = bfk.resample_box(source, 48, 48)
        valeurs_moyenne = {sum(moyenne.pixel(x, y)) // 3
                           for y in range(48) for x in range(48)}
        valeurs_mediane = {round(v) for ligne in
                           bfk.resample_median(source, 48, 48) for v in ligne}
        self.assertEqual(len(valeurs_mediane), 2,
                         "la scene n'a que deux profondeurs")
        self.assertGreater(len(valeurs_moyenne), 5,
                           "la moyenne devrait en inventer d'autres")

    def test_et_le_relief_qui_en_sort_est_mouchete(self):
        source = carte(240, 240)
        moyenne = bfk.resample_box(source, 48, 48)
        champ = [[sum(moyenne.pixel(x, y)) / 3 for x in range(48)]
                 for y in range(48)]
        par_moyenne = bfk.mosaic.etage_field(champ, 2)
        par_mediane = bfk.mosaic.etage_field(
            bfk.resample_median(source, 48, 48), 2)
        self.assertEqual(bfk.mosaic.relief_speckle(par_mediane), 0)
        self.assertGreater(bfk.mosaic.relief_speckle(par_moyenne), 5)

    def test_un_champ_lisse_ne_souffre_d_aucune_des_deux(self):
        # La mediane n'est pas gratuite : elle serait un defaut si elle
        # degradait les degres reels. Sur un degrade, les deux coincident.
        pixels = bytearray()
        for y in range(240):
            for x in range(240):
                v = x * 255 // 239
                pixels += bytes((v, v, v))
        lisse = bfk.Image(240, 240, bytes(pixels))
        med = bfk.resample_median(lisse, 24, 24)
        moy = bfk.resample_box(lisse, 24, 24)
        ecarts = [abs(med[y][x] - sum(moy.pixel(x, y)) / 3)
                  for y in range(24) for x in range(24)]
        self.assertLess(max(ecarts), 12.0, "les deux doivent coincider")


class TestProfondeurEmbarquee(unittest.TestCase):
    """Un JPEG de mode portrait porte souvent la profondeur mesuree."""

    def paquet_gdepth(self, charge: bytes) -> bytes:
        encodee = base64.b64encode(charge)
        return XMP + (
            b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
            b'<rdf:RDF xmlns:GDepth="http://ns.google.com/photos/1.0/depthmap/">'
            b'<rdf:Description GDepth:Format="RangeInverse" GDepth:Data="'
            + encodee + b'"/></rdf:RDF></x:xmpmeta>'
        )

    def test_le_format_gdepth_se_lit(self):
        charge = bfk.write_png(carte(32, 32))
        fichier = jpeg_minimal(self.paquet_gdepth(charge))
        lue = bfk.embedded_depth(fichier)
        self.assertEqual((lue.width, lue.height), (32, 32))

    def test_une_charge_gdepth_tronquee_est_signalee_et_non_devinee(self):
        paquet = self.paquet_gdepth(bfk.write_png(carte(16, 16)))
        abime = paquet.replace(b'GDepth:Data="', b'GDepth:Data="@@@')
        with self.assertRaises(NoEmbeddedDepth):
            bfk.embedded_depth(jpeg_minimal(abime))

    def test_le_format_dynamic_depth_se_lit(self):
        charge = bfk.write_png(carte(40, 40))
        annuaire = XMP + (
            b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF>'
            b'<rdf:Description xmlns:Container="http://ns.google.com/photos/'
            b'dd/1.0/container/">'
            b'<Container:Directory><rdf:Seq>'
            b'<rdf:li><Container:Item Item:Semantic="Primary" '
            b'Item:Mime="image/jpeg" Item:Length="0"/></rdf:li>'
            b'<rdf:li><Container:Item Item:Semantic="Depth" '
            b'Item:Mime="image/png" Item:Length="' +
            str(len(charge)).encode() + b'"/></rdf:li>'
            b'</rdf:Seq></Container:Directory>'
            b'</rdf:Description></rdf:RDF></x:xmpmeta>'
        )
        lue = bfk.embedded_depth(jpeg_minimal(annuaire, suite=charge))
        self.assertEqual((lue.width, lue.height), (40, 40))

    def test_le_xmp_etendu_est_reassemble_dans_l_ordre(self):
        # Une carte depasse souvent les 65 533 octets d'un segment APP1 : elle
        # deborde dans des segments etendus, qu'un lecteur naif concatene dans
        # l'ordre ou il les rencontre — et l'ordre du fichier n'est pas garanti.
        charge = bfk.write_png(carte(24, 24))
        complet = self.paquet_gdepth(charge)
        tete, queue = complet[:len(XMP) + 60], complet[len(XMP) + 60:]
        milieu = len(queue) // 2
        empreinte = b"a" * 32
        def etendu(decalage, corps):
            return (XMP_ETENDU + empreinte
                    + len(queue).to_bytes(4, "big")
                    + decalage.to_bytes(4, "big") + corps)
        fichier = b"\xff\xd8"
        # Volontairement dans le DESORDRE dans le fichier.
        for paquet in (tete,
                       etendu(milieu, queue[milieu:]),
                       etendu(0, queue[:milieu])):
            fichier += b"\xff\xe1" + (len(paquet) + 2).to_bytes(2, "big") + paquet
        fichier += b"\xff\xd9"
        lue = bfk.embedded_depth(fichier)
        self.assertEqual((lue.width, lue.height), (24, 24))

    def test_une_photo_ordinaire_n_a_pas_de_profondeur_et_ce_n_est_pas_une_panne(self):
        with self.assertRaises(NoEmbeddedDepth):
            bfk.embedded_depth(jpeg_minimal())
        with self.assertRaises(NoEmbeddedDepth):
            bfk.embedded_depth(jpeg_minimal(XMP + b"<x:xmpmeta/>"))

    def test_ce_qui_n_est_pas_un_jpeg_est_refuse(self):
        with self.assertRaises(ValueError):
            bfk.embedded_depth(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
