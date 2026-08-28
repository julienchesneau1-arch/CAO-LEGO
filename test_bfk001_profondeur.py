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


class TestOrientationDeLaCarteEmbarquee(unittest.TestCase):
    """Le cas le plus courant : une photo de telephone prise en portrait.

    L'appareil stocke des pixels COUCHES et note Orientation = 6. La photo
    decodee est redressee ; la carte de profondeur, elle, est ecrite dans le
    repere des pixels stockes et ne porte aucun EXIF. Sans redressement, la
    photo sort debout et la carte reste couchee — `DepthMismatch` refuse, et
    la fonctionnalite ne sert jamais.
    """

    def exif(self, orientation):
        import struct
        tiff = b"II" + struct.pack("<HI", 0x2A, 8)
        ifd = (struct.pack("<H", 1)
               + struct.pack("<HHI", 0x0112, 3, 1)
               + struct.pack("<HH", orientation, 0)
               + struct.pack("<I", 0))
        return b"Exif\x00\x00" + tiff + ifd

    def fichier(self, orientation, largeur, hauteur):
        charge = bfk.write_png(carte(largeur, hauteur))
        xmp = XMP + (b'<x:xmpmeta><rdf:RDF><rdf:Description GDepth:Data="'
                     + base64.b64encode(charge)
                     + b'"/></rdf:RDF></x:xmpmeta>')
        octets = b"\xff\xd8"
        for paquet in (self.exif(orientation), xmp):
            octets += b"\xff\xe1" + (len(paquet) + 2).to_bytes(2, "big") + paquet
        return octets + b"\xff\xd9"

    def test_la_carte_est_redressee_comme_la_photo(self):
        lue = bfk.embedded_depth(self.fichier(6, 40, 20))
        self.assertEqual((lue.width, lue.height), (20, 40),
                         "une carte couchee sous une photo debout est inutile")

    def test_sans_exif_rien_ne_bouge(self):
        lue = bfk.embedded_depth(self.fichier(1, 40, 20))
        self.assertEqual((lue.width, lue.height), (40, 20))

    def test_et_la_carte_redressee_passe_le_controle_de_proportions(self):
        # Le test qui dit que la correction sert a quelque chose : sans elle,
        # ce meme appel levait DepthMismatch.
        photo = photo_contraire(60, 120)
        lue = bfk.embedded_depth(self.fichier(6, 40, 20))
        hauteurs = bfk.heights_from_depth(lue, photo, 12, 24, 2)
        self.assertEqual((len(hauteurs), len(hauteurs[0])), (24, 12))


class TestLaCarteSubitLeMemeCadrageQueLaPhoto(unittest.TestCase):
    """Le defaut le plus vicieux de cette chaine : deux traitements differents
    appliques a deux descriptions de la MEME scene.

    Une photo 4:3 dans une mosaique carree est rognee. Si la carte de
    profondeur, elle, est etiree, elle ne decrit plus le meme cadre. Le
    controle de proportions refusait alors toute photo qui n'etait pas deja au
    format de l'oeuvre — c'est-a-dire presque toutes.
    """

    def scene(self, largeur, hauteur, x_relatif=0.30, rayon=0.28):
        """Sujet PROCHE a `x_relatif` de la largeur, fond lointain."""
        photo, prof = bytearray(), bytearray()
        for y in range(hauteur):
            for x in range(largeur):
                dedans = ((x - largeur * x_relatif) ** 2
                          + (y - hauteur * 0.5) ** 2 < (hauteur * rayon) ** 2)
                photo += bytes((30, 25, 40) if dedans else (215, 215, 225))
                prof += bytes((255, 255, 255) if dedans else (30, 30, 30))
        return (bfk.Image(largeur, hauteur, bytes(photo)),
                bfk.Image(largeur, hauteur, bytes(prof)))

    def test_une_photo_43_dans_une_mosaique_carree_ne_doit_plus_etre_refusee(self):
        photo, prof = self.scene(320, 240)
        hauteurs = bfk.heights_from_depth(prof, photo, 24, 24, 1,
                                          fit="crop", offset=0.5)
        self.assertEqual((len(hauteurs), len(hauteurs[0])), (24, 24))

    def test_etirer_la_carte_au_lieu_de_la_rogner_est_bien_attrape(self):
        # Ce que faisait le cablage : comparer la photo DEJA rognee a la carte
        # entiere. La garde doit refuser, c'est elle qui a revele le defaut.
        photo, prof = self.scene(320, 240)
        rognee = bfk.crop_to_ratio(photo, 1.0, 0.5)
        with self.assertRaises(DepthMismatch):
            bfk.heights_from_depth(prof, rognee, 24, 24, 1, fit="stretch")

    def test_le_relief_suit_la_fenetre_de_cadrage(self):
        # Petit sujet a l'extreme gauche : la fenetre de droite (x >= 80) ne
        # le contient pas du tout, celle de gauche le contient entierement.
        photo, prof = self.scene(320, 240, x_relatif=0.12, rayon=0.12)
        def releves(offset):
            h = bfk.heights_from_depth(prof, photo, 24, 24, 1,
                                       fit="crop", offset=offset)
            return sum(1 for ligne in h for v in ligne if v > 0)
        self.assertGreater(releves(0.0), 15, "le sujet doit sortir a gauche")
        self.assertEqual(releves(1.0), 0, "et disparaitre a droite")


class TestCablageDeLaCommande(unittest.TestCase):
    """La chaine complete, au point exact ou le defaut se trouvait."""

    class Options:
        carte_profondeur = None
        profondeur_inversee = False
        relief = 2
        studs = 24
        seuils = "otsu"

    def test_la_commande_accepte_une_carte_sur_une_photo_43(self):
        import pathlib as _p
        import tempfile
        from bfk001 import pipeline

        photo, prof = TestLaCarteSubitLeMemeCadrageQueLaPhoto().scene(320, 240)
        with tempfile.TemporaryDirectory() as dossier:
            chemin = _p.Path(dossier) / "prof.png"
            chemin.write_bytes(bfk.write_png(prof))
            reglages = pipeline.Reglages(studs=24, hauteur=24, relief=2)
            rognee = bfk.crop_to_ratio(photo, 1.0, 0.5)
            hauteurs, provenance = pipeline.carte_de_relief(
                rognee, photo, 0.5, b"", reglages, 24,
                carte_fournie=chemin.read_bytes(),
            )
        self.assertIn("MESUREE", provenance)
        self.assertEqual((len(hauteurs), len(hauteurs[0])), (24, 24))
        self.assertGreater(max(v for ligne in hauteurs for v in ligne), 0)


def paysage(largeur, hauteur):
    """Un ciel clair au-dessus d'un sol sombre.

    Le cas ou la convention du camee se trompe le plus visiblement : elle
    n'entend rien a la profondeur, elle lit la clarte, et sur un paysage la
    clarte est en haut alors que le proche est en bas.
    """
    pixels = bytearray()
    for y in range(hauteur):
        clair = y < hauteur // 2
        v = 225 if clair else 45
        for _ in range(largeur):
            pixels += bytes((v, v, v))
    return bfk.Image(largeur, hauteur, bytes(pixels))


class TestLaPenteDuRelief(unittest.TestCase):
    """`relief_tilt` : l'instrument qui a trouve le ciel en saillie."""

    def test_une_carte_haute_devant_donne_une_pente_positive(self):
        carte = [[3, 3]] * 3 + [[1, 1]] * 3 + [[0, 0]] * 3
        self.assertAlmostEqual(bfk.mosaic.relief_tilt(carte), 3.0)

    def test_une_carte_basse_devant_donne_une_pente_negative(self):
        carte = [[0, 0]] * 3 + [[1, 1]] * 3 + [[3, 3]] * 3
        self.assertAlmostEqual(bfk.mosaic.relief_tilt(carte), -3.0)

    def test_une_carte_plate_ne_penche_pas(self):
        self.assertAlmostEqual(bfk.mosaic.relief_tilt([[2, 2]] * 9), 0.0)

    def test_le_tiers_du_milieu_ne_compte_pas(self):
        # Trois lignes hautes, trois basses, et un milieu extreme qui ne doit
        # rien changer : la mesure compare les deux BORDS de l'image.
        carte = [[2, 2]] * 3 + [[9, 9]] * 3 + [[0, 0]] * 3
        self.assertAlmostEqual(bfk.mosaic.relief_tilt(carte), 2.0)

    def test_une_carte_trop_courte_ou_vide_ne_fait_pas_tomber(self):
        self.assertEqual(bfk.mosaic.relief_tilt([]), 0.0)
        self.assertEqual(bfk.mosaic.relief_tilt([[]]), 0.0)
        self.assertEqual(bfk.mosaic.relief_tilt([[1], [2]]), 0.0)


class TestLaConventionSeRenverse(unittest.TestCase):
    """Le defaut : « clair = haut » etait un choix qu'on ne pouvait pas faire.

    `--profondeur-inversee` ne parle que de l'ENCODAGE d'une carte fournie.
    Sans carte, le relief se lit sur la clarte et rien ne pouvait le
    retourner — sur un paysage, le ciel sortait devant le sol de cinq
    millimetres et il n'y avait aucun recours.
    """

    def setUp(self):
        self.photo = paysage(240, 240)

    def hauteurs(self, inverse):
        from bfk001 import pipeline

        reglages = pipeline.Reglages(studs=24, hauteur=24, relief=3,
                                     relief_inverse=inverse)
        return pipeline.carte_de_relief(
            self.photo, self.photo, 0.5, b"", reglages, 24)

    def test_par_defaut_le_ciel_ressort(self):
        hauteurs, provenance = self.hauteurs(False)
        self.assertGreater(bfk.mosaic.relief_tilt(hauteurs), 1.0)
        self.assertIn("clair = haut", provenance)

    def test_renversee_le_ciel_passe_au_fond(self):
        hauteurs, provenance = self.hauteurs(True)
        self.assertLess(bfk.mosaic.relief_tilt(hauteurs), -1.0)
        self.assertIn("sombre = haut", provenance)

    def test_les_deux_conventions_restent_une_convention(self):
        # Ni l'une ni l'autre n'est une mesure, et le journal ne doit jamais
        # laisser croire le contraire.
        for inverse in (False, True):
            _, provenance = self.hauteurs(inverse)
            self.assertIn("aucune profondeur mesuree", provenance)
            self.assertNotIn("MESUREE", provenance)

    def test_une_carte_fournie_ignore_la_convention_de_clarte(self):
        # La carte est une mesure : le drapeau de convention ne la concerne
        # pas, et doit rester sans effet sur ce chemin.
        from bfk001 import pipeline

        depuis = carte(240, 240)
        rendus = []
        for inverse in (False, True):
            reglages = pipeline.Reglages(studs=24, hauteur=24, relief=3,
                                         relief_inverse=inverse)
            hauteurs, provenance = pipeline.carte_de_relief(
                self.photo, self.photo, 0.5, b"", reglages, 24,
                carte_fournie=bfk.write_png(depuis))
            self.assertIn("MESUREE", provenance)
            rendus.append(hauteurs)
        self.assertEqual(rendus[0], rendus[1])


def bandeau(largeur, hauteur, haut, bas):
    """Deux bandes horizontales de clarte imposee."""
    pixels = bytearray()
    for y in range(hauteur):
        v = haut if y < hauteur // 2 else bas
        for _ in range(largeur):
            pixels += bytes((v, v, v))
    return bfk.Image(largeur, hauteur, bytes(pixels))


class TestLaPenteSeLitDansLeJournal(unittest.TestCase):
    """Un relief a l'envers etait invisible : le journal n'en disait rien."""

    def journal(self, **options):
        from bfk001 import pipeline

        resultat = pipeline.run(
            bfk.write_png(paysage(240, 240)),
            pipeline.Reglages(studs=24, hauteur=24, relief=3, **options),
            palette=bfk.PROVISIONAL_PALETTE.solids_only(),
            palette_complete=bfk.PROVISIONAL_PALETTE,
            note_palette=("info", "essai"))
        return "\n".join(texte for _, texte in resultat.journal)

    def test_la_pente_est_annoncee_et_le_ciel_denonce(self):
        texte = self.journal()
        self.assertIn("tiers haut", texte)
        self.assertIn("RESSORT", texte)

    def test_renversee_la_pente_est_annoncee_sans_reproche(self):
        texte = self.journal(relief_inverse=True)
        self.assertIn("tiers haut", texte)
        self.assertNotIn("RESSORT", texte)

    def test_renversee_un_haut_qui_ressort_est_quand_meme_signale(self):
        """L'observation vaut toujours ; le remede, non.

        Le premier jet taisait la remarque des que `relief_inverse` etait mis,
        au motif que le remede etait deja pris. Un ciel SOMBRE renverse
        ressort exactement pareil, et le journal serait redevenu muet sur le
        seul cas qu'il existe pour attraper.
        """
        from bfk001 import pipeline

        nuit = bandeau(240, 240, 45, 225)   # ciel sombre, sol clair
        resultat = pipeline.run(
            bfk.write_png(nuit),
            pipeline.Reglages(studs=24, hauteur=24, relief=3,
                              relief_inverse=True),
            palette=bfk.PROVISIONAL_PALETTE.solids_only(),
            palette_complete=bfk.PROVISIONAL_PALETTE,
            note_palette=("info", "essai"))
        texte = "\n".join(t for _, t in resultat.journal)
        self.assertIn("RESSORT", texte)
        self.assertNotIn("renversez", texte,
                         "le remede est deja pris : le proposer serait faux")

    def test_une_carte_mesuree_qui_penche_renvoie_a_la_carte(self):
        # Une carte encodee a l'envers place le fond devant. C'est le defaut
        # que `--profondeur-inversee` corrige, et rien ne le signalait.
        from bfk001 import pipeline

        photo = bandeau(240, 240, 120, 120)
        # Proche = clair par defaut : un haut clair met le haut DEVANT.
        depuis = bandeau(240, 240, 250, 20)
        resultat = pipeline.run(
            bfk.write_png(photo),
            pipeline.Reglages(studs=24, hauteur=24, relief=3),
            palette=bfk.PROVISIONAL_PALETTE.solids_only(),
            palette_complete=bfk.PROVISIONAL_PALETTE,
            carte_profondeur=bfk.write_png(depuis),
            note_palette=("info", "essai"))
        texte = "\n".join(t for _, t in resultat.journal)
        self.assertIn("MESUREE", texte)
        self.assertIn("RESSORT", texte)
        self.assertIn("verifiez le sens de la carte", texte)
        self.assertNotIn("renversez", texte,
                         "la convention de clarte ne concerne pas une carte")

    def test_une_oeuvre_plate_ne_parle_pas_de_pente(self):
        from bfk001 import pipeline

        resultat = pipeline.run(
            bfk.write_png(paysage(240, 240)),
            pipeline.Reglages(studs=24, hauteur=24),
            palette=bfk.PROVISIONAL_PALETTE.solids_only(),
            palette_complete=bfk.PROVISIONAL_PALETTE,
            note_palette=("info", "essai"))
        texte = "\n".join(t for _, t in resultat.journal)
        self.assertNotIn("tiers haut", texte)


class TestLaCommandeExposeLaConvention(unittest.TestCase):
    """Un reglage qui n'atteint pas la facade n'existe pas pour l'utilisateur."""

    def test_la_ligne_de_commande_porte_le_drapeau(self):
        import demo_lego_art

        analyseur = demo_lego_art.construire_analyseur()
        options = analyseur.parse_args(["photo.png", "--relief-inverse"])
        self.assertTrue(options.relief_inverse)
        self.assertFalse(analyseur.parse_args(["photo.png"]).relief_inverse)

    def test_la_page_porte_la_case_et_la_transmet(self):
        from bfk001 import webapp

        self.assertIn('id="relief_inverse"', webapp.PAGE)
        self.assertIn("relief_inverse:", webapp.PAGE)
        reglages = webapp._reglages({"studs": "24", "relief": "2",
                                    "relief_inverse": True})
        self.assertTrue(reglages.relief_inverse)
        self.assertFalse(webapp._reglages({"studs": "24"}).relief_inverse)
