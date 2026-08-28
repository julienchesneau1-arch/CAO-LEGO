"""La chaine partagee et l'interface qui la sert.

Deux facades — la commande et le navigateur — appellent le meme
`pipeline.run`. Ce fichier verifie la chaine elle-meme, puis le TRAJET
complet : un vrai serveur, une vraie requete HTTP, une vraie archive.

Ce n'est pas du zele. Les deux derniers defauts trouves dans ce depot
(§ 5.48) etaient des defauts de trajet — des parametres mal passes d'un
composant correct a un autre composant correct — et aucun test de composant
ne pouvait les voir.
"""

import base64
import json
import pathlib
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from io import BytesIO

import bfk001 as bfk
from bfk001.pipeline import ModeleRefuse, Reglages, lire_image, run
from bfk001.webapp import Atelier, creer_serveur


def photo(largeur=96, hauteur=96):
    """Un disque colore sur un fond degrade. Assez de matiere pour quantifier."""
    pixels = bytearray()
    for y in range(hauteur):
        for x in range(largeur):
            dedans = ((x - largeur / 2) ** 2 + (y - hauteur / 2) ** 2
                      < (min(largeur, hauteur) * 0.3) ** 2)
            if dedans:
                pixels += bytes((210, 60, 40))
            else:
                pixels += bytes((40 + x * 120 // largeur, 90,
                                 180 - y * 60 // hauteur))
    return bfk.write_png(bfk.Image(largeur, hauteur, bytes(pixels)))


def photo_image(largeur=96, hauteur=96):
    """La meme scene, non encodee : ce que le cache de reduction manipule."""
    return bfk.read_png(photo(largeur, hauteur))


def carte_de_profondeur(largeur=96, hauteur=96):
    pixels = bytearray()
    for y in range(hauteur):
        for x in range(largeur):
            proche = ((x - largeur / 2) ** 2 + (y - hauteur / 2) ** 2
                      < (min(largeur, hauteur) * 0.3) ** 2)
            v = 255 if proche else 30
            pixels += bytes((v, v, v))
    return bfk.write_png(bfk.Image(largeur, hauteur, bytes(pixels)))


PETIT = Reglages(studs=16, hauteur=16, titre="essai")


class TestChaine(unittest.TestCase):
    def test_elle_livre_tous_les_fichiers_annonces(self):
        resultat = run(photo(), PETIT)
        self.assertEqual(
            sorted(resultat.fichiers),
            ["apercu.png", "apercu_joints.png", "apercu_source.png",
             "liste_de_course.csv", "modele.json", "modele.ldr",
             "notice.pdf", "notice.txt"],
        )
        self.assertTrue(resultat.fichiers["notice.pdf"].startswith(b"%PDF-"))
        self.assertTrue(resultat.fichiers["apercu.png"].startswith(
            b"\x89PNG\r\n\x1a\n"))

    def test_le_relief_ajoute_son_apercu_et_seulement_alors(self):
        sans = run(photo(), PETIT)
        avec = run(photo(), Reglages(studs=16, hauteur=16, relief=2))
        self.assertNotIn("apercu_relief.png", sans.fichiers)
        self.assertIn("apercu_relief.png", avec.fichiers)

    def test_les_trois_formats_d_entree_sont_lus(self):
        image = bfk.Image(4, 4, bytes(range(48)))
        self.assertEqual(lire_image(bfk.write_png(image)).width, 4)
        self.assertEqual(
            lire_image(b"P6\n4 4\n255\n" + image.data).width, 4)
        with self.assertRaises(ValueError):
            lire_image(b"GIF89a" + b"\x00" * 40)

    def test_le_journal_est_ordonne_et_etiquete(self):
        resultat = run(photo(), PETIT)
        self.assertTrue(resultat.journal)
        self.assertTrue(all(flux in ("info", "alerte")
                            for flux, _ in resultat.journal))
        self.assertTrue(resultat.lignes[0].startswith("image   :"))
        # Le dernier mot revient toujours a ce qui est livre.
        self.assertTrue(resultat.lignes[-1].startswith("livre   :"))

    def test_un_reglage_absurde_est_refuse_a_la_construction(self):
        for mauvais in (dict(studs=0), dict(relief=-1),
                        dict(references="briques"), dict(tramage="parfois"),
                        dict(seuils="au hasard")):
            with self.assertRaises(ValueError, msg=repr(mauvais)):
                Reglages(**mauvais)

    def test_la_carte_de_profondeur_traverse_la_chaine(self):
        # Le trajet complet de la profondeur mesuree, jusqu'au fichier livre.
        avec = run(photo(), Reglages(studs=16, hauteur=16, relief=2),
                   carte_profondeur=carte_de_profondeur())
        sans = run(photo(), Reglages(studs=16, hauteur=16, relief=2))
        self.assertIn("MESUREE", avec.mesures["provenance_relief"])
        self.assertIn("CONVENTION", sans.mesures["provenance_relief"])
        self.assertNotEqual(avec.fichiers["apercu_relief.png"],
                            sans.fichiers["apercu_relief.png"])

    def test_les_mesures_decrivent_ce_qui_est_livre(self):
        resultat = run(photo(), PETIT)
        self.assertEqual(resultat.mesures["studs_x"], 16)
        self.assertEqual(resultat.mesures["tenons"], 256)
        self.assertGreater(resultat.mesures["pieces"],
                           resultat.mesures["tuiles"])
        # La dimension annoncee est celle HORS TOUT : c'est elle qu'on
        # accroche au mur. L'image est plus petite d'un cadre de chaque cote.
        self.assertAlmostEqual(resultat.mesures["largeur_mm"], 20 * 8.0, places=6)
        self.assertAlmostEqual(
            resultat.mesures["image_largeur_mm"], 16 * 8.0, places=6)

    def test_une_mosaique_qui_ne_tient_pas_n_est_pas_livree(self):
        # Un tenon de large SANS CADRE : le fond se scinde en dix-neuf
        # morceaux. Le noyau refuse, et la chaine ne doit surtout pas ecrire
        # de fichiers quand meme.
        with self.assertRaises((ModeleRefuse, ValueError)):
            run(photo(), Reglages(studs=1, hauteur=40, cadre=0))

    def test_le_cadre_rend_constructibles_des_formats_qui_ne_l_etaient_pas(self):
        # Conséquence inattendue et mesuree : une bande d'un tenon de large est
        # impossible sans cadre — son fond se scinde — et parfaitement valide
        # avec. Le cadre n'est pas qu'un ornement : c'est une ceinture, et
        # l'emprise qu'il ajoute suffit a paver un fond d'un seul tenant.
        resultat = run(photo(), Reglages(studs=1, hauteur=40, cadre=2))
        self.assertGreater(resultat.mesures["pieces"], 0)
        self.assertEqual(resultat.mesures["cadre"], 2)


class TestAtelier(unittest.TestCase):
    """La logique du serveur, sans ouvrir de socket."""

    def setUp(self):
        self.atelier = Atelier()

    def requete(self, **reglages):
        return {
            "photo": base64.b64encode(photo()).decode(),
            "reglages": dict({"studs": 16, "hauteur": 16}, **reglages),
        }

    def test_une_fabrication_rend_apercus_journal_et_jeton(self):
        reponse = self.atelier.fabriquer(self.requete())
        self.assertIn("apercu.png", reponse["apercus"])
        self.assertTrue(reponse["apercus"]["apercu.png"]
                        .startswith("data:image/png;base64,"))
        self.assertTrue(reponse["jeton"])
        self.assertTrue(reponse["journal"])

    def test_le_jeton_donne_une_archive_complete(self):
        reponse = self.atelier.fabriquer(self.requete())
        archive = self.atelier.archive(reponse["jeton"])
        with zipfile.ZipFile(BytesIO(archive)) as zf:
            self.assertEqual(sorted(zf.namelist()), reponse["fichiers"])
            self.assertTrue(zf.read("notice.pdf").startswith(b"%PDF-"))

    def test_un_jeton_inconnu_ne_rend_rien(self):
        with self.assertRaises(KeyError):
            self.atelier.archive("jeton-invente")

    def test_le_navigateur_peut_envoyer_une_data_uri_entiere(self):
        requete = self.requete()
        requete["photo"] = "data:image/png;base64," + requete["photo"]
        self.assertIn("apercu.png",
                      self.atelier.fabriquer(requete)["apercus"])

    def test_les_entrees_malformees_sont_refusees_et_non_devinees(self):
        for mauvaise, motif in (
            ({}, "aucune photo"),
            ({"photo": 42}, "base64"),
            ({"photo": "pas du base64 !!"}, "base64"),
            ({"photo": base64.b64encode(photo()).decode(),
              "reglages": "grand"}, "objet attendu"),
            ({"photo": base64.b64encode(photo()).decode(),
              "reglages": {"studs": "beaucoup"}}, "entier"),
        ):
            with self.assertRaises(ValueError, msg=repr(mauvaise)[:60]) as saisi:
                self.atelier.fabriquer(mauvaise)
            self.assertIn(motif, str(saisi.exception))

    def test_les_vieux_resultats_sont_oublies(self):
        from bfk001.webapp import RESULTATS_GARDES
        jetons = [self.atelier.fabriquer(self.requete())["jeton"]
                  for _ in range(RESULTATS_GARDES + 2)]
        with self.assertRaises(KeyError):
            self.atelier.archive(jetons[0])
        self.atelier.archive(jetons[-1])  # le dernier repond toujours


class TestTrajetHttp(unittest.TestCase):
    """Un vrai serveur, une vraie requete. Le trajet, pas les composants."""

    @classmethod
    def setUpClass(cls):
        cls.serveur = creer_serveur("127.0.0.1", 0, Atelier())
        cls.fil = threading.Thread(target=cls.serveur.serve_forever, daemon=True)
        cls.fil.start()
        cls.base = f"http://127.0.0.1:{cls.serveur.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        cls.serveur.server_close()

    def poster(self, corps: dict):
        requete = urllib.request.Request(
            self.base + "/fabriquer",
            data=json.dumps(corps).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(requete, timeout=180) as reponse:
            return reponse.status, json.loads(reponse.read().decode("utf-8"))

    # Les seules adresses exterieures que la page a le droit de porter, et
    # UNIQUEMENT comme liens qu'un humain clique. Toute autre doit faire
    # echouer le test : c'est ainsi qu'on remarque une quatrieme ajoutee
    # distraitement.
    DESTINATIONS = (
        "https://www.lego.com/pick-and-build/pick-a-brick",
        "https://www.bricklink.com/v2/wanted/upload.page",
        "https://rebrickable.com/downloads/",
    )

    def test_la_page_se_sert_et_ne_charge_aucune_ressource_externe(self):
        import re

        with urllib.request.urlopen(self.base + "/", timeout=30) as reponse:
            page = reponse.read().decode("utf-8")
            politique = reponse.headers["Content-Security-Policy"]
        self.assertIn("<title>", page)
        self.assertIn("default-src 'none'", politique)

        # Une RESSOURCE est chargee sans que personne ne le demande : c'est
        # cela qu'on interdit. Un LIEN qu'un humain clique pour aller commander
        # n'est pas une ressource — il ne part que s'il le decide.
        for motif in ('src="http', "src='http", '@import', "url(http",
                      '<link', "//cdn"):
            self.assertNotIn(motif, page.replace("http://127.0.0.1", ""),
                             f"ressource externe : {motif}")

        adresses = set(re.findall(r"https?://[^\s\"'<>)]+", page))
        adresses = {a for a in adresses if not a.startswith("http://127.0.0.1")}
        self.assertEqual(adresses, set(self.DESTINATIONS),
                         "adresse exterieure non prevue dans la page")

    def test_tout_lien_exterieur_ecrit_dans_la_page_s_ouvre_en_dehors(self):
        # `target=_blank` sans `rel=noopener` donnerait a la page ouverte une
        # poignee sur celle-ci. Ligne facile a oublier.
        #
        # Ce test ne voit que les liens ECRITS dans le HTML. Ceux que le script
        # fabrique sont verifies dans le vrai navigateur
        # (`test_bfk001_page.py`), seul endroit d'ou on peut les regarder.
        import re

        with urllib.request.urlopen(self.base + "/", timeout=30) as reponse:
            page = reponse.read().decode("utf-8")
        liens = re.findall(r"<a\s[^>]*href=\"https?://[^>]*>", page)
        self.assertTrue(liens, "aucun lien exterieur ecrit dans la page")
        for lien in liens:
            self.assertIn('target="_blank"', lien)
            self.assertIn("noopener", lien)

    def test_deposer_une_photo_rend_une_mosaique_telechargeable(self):
        code, reponse = self.poster({
            "photo": base64.b64encode(photo()).decode(),
            "reglages": {"studs": 16, "hauteur": 16, "relief": 1},
        })
        self.assertEqual(code, 200)
        self.assertIn("apercu_relief.png", reponse["apercus"])
        self.assertGreater(reponse["mesures"]["pieces"], 0)

        url = f"{self.base}/telecharger/{reponse['jeton']}.zip"
        with urllib.request.urlopen(url, timeout=60) as archive:
            self.assertEqual(archive.headers["Content-Type"], "application/zip")
            octets = archive.read()
        with zipfile.ZipFile(BytesIO(octets)) as zf:
            self.assertIn("notice.pdf", zf.namelist())
            self.assertTrue(zf.read("modele.ldr").startswith(b"0 "))

    def test_une_requete_sans_photo_repond_400_et_le_dit(self):
        with self.assertRaises(urllib.error.HTTPError) as saisi:
            self.poster({"reglages": {"studs": 16}})
        self.assertEqual(saisi.exception.code, 400)
        self.assertIn("aucune photo",
                      json.loads(saisi.exception.read())["erreur"])

    def test_un_jeton_expire_repond_404(self):
        with self.assertRaises(urllib.error.HTTPError) as saisi:
            urllib.request.urlopen(
                self.base + "/telecharger/inconnu.zip", timeout=30)
        self.assertEqual(saisi.exception.code, 404)

    def test_rien_ne_se_sert_depuis_le_disque(self):
        # Aucune traversee possible : il n'y a pas de racine de fichiers.
        for chemin in ("/../bfk001/mosaic.py", "/etc/passwd",
                       "/telecharger/../../secret.zip"):
            with self.assertRaises(urllib.error.HTTPError, msg=chemin) as saisi:
                urllib.request.urlopen(self.base + chemin, timeout=30)
            self.assertEqual(saisi.exception.code, 404)

    def test_un_corps_trop_grand_est_refuse_avant_lecture(self):
        from bfk001.webapp import TAILLE_MAXIMALE
        requete = urllib.request.Request(
            self.base + "/fabriquer", data=b"{}",
            headers={"Content-Type": "application/json",
                     "Content-Length": str(TAILLE_MAXIMALE + 1)},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as saisi:
            urllib.request.urlopen(requete, timeout=30)
        self.assertEqual(saisi.exception.code, 413)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestCatalogues(unittest.TestCase):
    """Donner un catalogue une fois, et ne plus y penser.

    Les numeros employes ici sont FACTICES et ne quittent pas /tmp : ce qu'on
    verifie est le trajet — depot, lecture, memoire, commande — pas la valeur
    des numeros, qui vient du catalogue de l'utilisateur.
    """

    ELEMENTS = ("element_id,part_num,color_id,design_id\n"
                "700001,3070b,71,3070\n"
                "700002,41539,71,41539\n"
                "700003,91405,71,91405\n"
                "700004,3024,71,3024\n"
                "999999,99999,71,99999\n")
    COULEURS = "id,name,rgb\n71,Light Bluish Gray,A0A5A9\n0,Black,05131D\n"

    def atelier(self, dossier=None):
        return Atelier(dossier=dossier)

    def uri(self, texte, octets=None):
        brut = octets if octets is not None else texte.encode("utf-8")
        return "data:text/csv;base64," + base64.b64encode(brut).decode()

    def test_sans_dossier_rien_n_est_ecrit_hors_de_la_memoire_vive(self):
        # Une bibliotheque n'ecrit pas dans le dossier personnel de qui
        # l'importe parce que c'est pratique pour l'application.
        atelier = Atelier()
        self.assertFalse(atelier.memoire)
        self.assertIsNone(atelier.etat_catalogues()["dossier"])

    def test_un_catalogue_depose_sert_a_la_fabrication_suivante(self):
        import tempfile
        atelier = self.atelier(tempfile.mkdtemp())
        etat = atelier.definir_catalogues({
            "elements": self.uri(self.ELEMENTS),
            "elements_couleurs": self.uri(self.COULEURS),
        })
        self.assertEqual(etat["elements"]["references"], 4)
        reponse = atelier.fabriquer({
            "photo": base64.b64encode(photo(48, 48)).decode(),
            "reglages": {"studs": 16, "hauteur": 16, "cadre": 0},
        })
        self.assertIn("commande_lego.csv", reponse["fichiers"])
        self.assertGreater(reponse["mesures"]["commande_lego_lots"], 0)

    def test_ce_qui_est_retenu_survit_au_redemarrage(self):
        import tempfile
        dossier = pathlib.Path(tempfile.mkdtemp())
        premier = self.atelier(dossier)
        premier.definir_catalogues({
            "elements": self.uri(self.ELEMENTS),
            "elements_couleurs": self.uri(self.COULEURS),
        })
        avant = dict(premier.table_elements.entrees)

        second = self.atelier(dossier)
        self.assertIsNotNone(second.table_elements)
        self.assertEqual(dict(second.table_elements.entrees), avant)
        # Et ce qui est ecrit n'est pas le catalogue d'origine : il tient en
        # quelques lignes, et il se relit SANS la table de couleurs.
        garde = (dossier / "elements.tsv").read_text()
        self.assertLess(len(garde), len(self.ELEMENTS) * 2)
        self.assertNotIn("999999", garde)

    def test_un_catalogue_compresse_se_depose_tel_quel(self):
        import gzip
        import tempfile
        atelier = self.atelier(tempfile.mkdtemp())
        etat = atelier.definir_catalogues({
            "elements": self.uri(None, gzip.compress(self.ELEMENTS.encode())),
            "elements_couleurs": self.uri(None,
                                          gzip.compress(self.COULEURS.encode())),
        })
        self.assertEqual(etat["elements"]["references"], 4)

    def test_une_lecture_qui_echoue_laisse_l_etat_precedent_intact(self):
        # Un catalogue a moitie remplace serait pire que pas de catalogue : on
        # croirait pouvoir commander.
        import tempfile
        atelier = self.atelier(tempfile.mkdtemp())
        atelier.definir_catalogues({
            "elements": self.uri(self.ELEMENTS),
            "elements_couleurs": self.uri(self.COULEURS),
        })
        avant = dict(atelier.table_elements.entrees)
        with self.assertRaises(ValueError):
            atelier.definir_catalogues({
                "elements": self.uri("rien du tout\n"),
                "elements_couleurs": self.uri(self.COULEURS),
            })
        self.assertEqual(dict(atelier.table_elements.entrees), avant)

    def test_la_table_de_couleurs_seule_est_refusee(self):
        atelier = Atelier()
        with self.assertRaises(ValueError) as saisi:
            atelier.definir_catalogues({
                "elements_couleurs": self.uri(self.COULEURS)})
        self.assertIn("ensemble", str(saisi.exception))

    def test_oublier_efface_la_memoire_et_le_disque(self):
        import tempfile
        dossier = pathlib.Path(tempfile.mkdtemp())
        atelier = self.atelier(dossier)
        atelier.definir_catalogues({
            "elements": self.uri(self.ELEMENTS),
            "elements_couleurs": self.uri(self.COULEURS),
        })
        self.assertTrue((dossier / "elements.tsv").exists())
        etat = atelier.oublier_catalogues()
        self.assertIsNone(etat["elements"])
        self.assertFalse((dossier / "elements.tsv").exists())
        self.assertIsNone(self.atelier(dossier).table_elements)


class TestTrajetHttpCommande(unittest.TestCase):
    """Deposer un catalogue et repartir avec le CSV, en HTTP reel."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.dossier = pathlib.Path(tempfile.mkdtemp())
        cls.atelier = Atelier(dossier=cls.dossier)
        cls.serveur = creer_serveur("127.0.0.1", 0, cls.atelier)
        cls.fil = threading.Thread(target=cls.serveur.serve_forever, daemon=True)
        cls.fil.start()
        cls.base = f"http://127.0.0.1:{cls.serveur.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        cls.serveur.server_close()

    def poster(self, chemin, corps):
        requete = urllib.request.Request(
            self.base + chemin, data=json.dumps(corps).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(requete, timeout=180) as reponse:
            return reponse.status, json.loads(reponse.read().decode("utf-8"))

    def test_le_trajet_complet_depuis_le_reseau(self):
        with urllib.request.urlopen(self.base + "/catalogues", timeout=30) as r:
            self.assertIsNone(json.loads(r.read())["elements"])

        code, etat = self.poster("/catalogues", {
            "elements": "data:text/csv;base64," + base64.b64encode(
                TestCatalogues.ELEMENTS.encode()).decode(),
            "elements_couleurs": "data:text/csv;base64," + base64.b64encode(
                TestCatalogues.COULEURS.encode()).decode(),
        })
        self.assertEqual(code, 200)
        self.assertEqual(etat["elements"]["references"], 4)

        code, reponse = self.poster("/fabriquer", {
            "photo": base64.b64encode(photo(48, 48)).decode(),
            "reglages": {"studs": 16, "hauteur": 16, "cadre": 0},
        })
        self.assertIn("commande_lego.csv", reponse["fichiers"])

        url = (f"{self.base}/fichier/{reponse['jeton']}/commande_lego.csv")
        with urllib.request.urlopen(url, timeout=30) as fichier:
            self.assertTrue(
                fichier.headers["Content-Type"].startswith("text/csv"))
            self.assertIn("commande_lego.csv",
                          fichier.headers["Content-Disposition"])
            lignes = fichier.read().decode().splitlines()
        self.assertEqual(lignes[0], "elementId,quantity")
        self.assertGreater(len(lignes), 1)

    def test_un_fichier_qui_n_a_pas_ete_fabrique_repond_404(self):
        code, reponse = self.poster("/fabriquer", {
            "photo": base64.b64encode(photo(48, 48)).decode(),
            "reglages": {"studs": 16, "hauteur": 16, "cadre": 0},
        })
        jeton = reponse["jeton"]
        # Le nom n'est jamais employe comme chemin : il est cherche dans le
        # dictionnaire du resultat, et rien d'autre n'existe.
        for nom in ("../../etc/passwd", "secret.txt", "..%2f..%2fetc%2fpasswd"):
            with self.assertRaises(urllib.error.HTTPError, msg=nom) as saisi:
                urllib.request.urlopen(
                    f"{self.base}/fichier/{jeton}/{nom}", timeout=30)
            self.assertEqual(saisi.exception.code, 404)

    def test_un_catalogue_illisible_repond_400_et_le_dit(self):
        with self.assertRaises(urllib.error.HTTPError) as saisi:
            self.poster("/catalogues", {
                "elements": "data:text/csv;base64," + base64.b64encode(
                    b"ni queue ni tete\n").decode()})
        self.assertEqual(saisi.exception.code, 400)
        self.assertTrue(json.loads(saisi.exception.read())["erreur"])


class TestComparateurSource(unittest.TestCase):
    """L'apercu de la source : « avant / apres » n'a de sens que s'il s'aligne.

    Superposer la photo BRUTE a l'oeuvre produirait un glissement — rognage,
    moyenne par tenon, cadre — et un glissement fait mentir la comparaison : on
    croirait juger la quantification en regardant un decalage.
    """

    def petite(self, cote=24, frame=0):
        from bfk001 import mosaic
        from bfk001.imaging import resample_box
        from bfk001.pipeline import palette_utilisable

        complete, _ = palette_utilisable()
        palette = complete.solids_only()
        pixels = []
        for y in range(96):
            for x in range(96):
                pixels.append((x * 255 // 96, y * 255 // 96,
                               (x + y) * 255 // 192))
        image = bfk.Image.from_pixels(96, 96, pixels)
        grille = mosaic.quantize(image, palette, cote, cote, dither=False)
        mosaique = mosaic.build(grille, substrate_color=71, frame=frame)
        reduite = resample_box(mosaic._cadrer(image, cote, cote, "crop", 0.5),
                               cote, cote)
        return mosaic, mosaique, reduite

    def test_les_deux_apercus_ont_exactement_la_meme_taille(self):
        for frame in (0, 2, 3):
            mosaic, mosaique, reduite = self.petite(frame=frame)
            rendu = mosaic.preview(mosaique, scale=8)
            source = mosaic.source_preview(reduite, mosaique, scale=8)
            self.assertEqual((rendu.width, rendu.height),
                             (source.width, source.height),
                             f"cadre de {frame} tenons")

    def test_une_source_qui_ne_correspond_pas_est_refusee(self):
        # Une source de la mauvaise taille produirait un glissement muet.
        mosaic, mosaique, reduite = self.petite()
        fausse = bfk.Image.from_pixels(8, 8, [(0, 0, 0)] * 64)
        with self.assertRaises(ValueError) as capture:
            mosaic.source_preview(fausse, mosaique, scale=8)
        self.assertIn("8x8", str(capture.exception))

    def test_la_source_n_est_pas_le_rendu(self):
        # Si les deux images etaient identiques, le comparateur ne montrerait
        # rien — et la quantification serait parfaite, ce qu'elle n'est pas.
        mosaic, mosaique, reduite = self.petite()
        self.assertNotEqual(mosaic.preview(mosaique, scale=8).data,
                            mosaic.source_preview(reduite, mosaique, scale=8).data)

    def test_le_cadre_de_la_source_est_celui_de_l_oeuvre(self):
        # Le coin superieur gauche est du cadre dans les deux images : c'est ce
        # qui garantit que la poignee du comparateur ne revele pas un bord
        # different d'un cote et de l'autre.
        mosaic, mosaique, reduite = self.petite(frame=2)
        rendu = mosaic.preview(mosaique, scale=8, frame_rgb=(20, 20, 20))
        source = mosaic.source_preview(reduite, mosaique, scale=8,
                                       frame_rgb=(20, 20, 20))
        self.assertEqual(rendu.data[:3], source.data[:3])

    def test_la_chaine_livre_la_source_a_cote_de_l_apercu(self):
        resultat = run(photo(), Reglages(studs=16, hauteur=16, cadre=0))
        self.assertIn("apercu_source.png", resultat.fichiers)
        rendu = bfk.read_png(resultat.fichiers["apercu.png"])
        source = bfk.read_png(resultat.fichiers["apercu_source.png"])
        self.assertEqual((rendu.width, rendu.height),
                         (source.width, source.height))

class TestDecoupeEnSections(unittest.TestCase):
    """La decoupe traverse-t-elle la chaine jusqu'aux fichiers livres ?"""

    def test_chaque_section_a_sa_notice_et_son_apercu(self):
        resultat = run(photo(), Reglages(studs=16, hauteur=16, sections=8))
        sections = sorted(n for n in resultat.fichiers if "/" in n)
        self.assertEqual(sections, [
            f"section_{ligne}_{colonne}/{fichier}"
            for ligne in (1, 2) for colonne in (1, 2)
            for fichier in ("apercu.png", "notice.pdf")
        ])
        for nom in sections:
            if nom.endswith(".pdf"):
                self.assertTrue(resultat.fichiers[nom].startswith(b"%PDF-"))

    def test_ce_qui_est_compte_est_ce_qui_est_livre(self):
        # Une decoupe ajoute quatre fonds et une couche de jonction. Annoncer
        # le compte de l'oeuvre d'un seul tenant serait annoncer autre chose
        # que ce qu'on met dans le carton.
        entier = run(photo(), Reglages(studs=16, hauteur=16))
        decoupe = run(photo(), Reglages(studs=16, hauteur=16, sections=8))
        self.assertGreater(decoupe.mesures["pieces"], entier.mesures["pieces"])
        self.assertEqual(decoupe.mesures["sections"], 4)
        self.assertEqual(entier.mesures["sections"], 0)
        # Les COULEURS, elles, ne bougent pas : c'est la meme oeuvre.
        self.assertEqual(decoupe.mesures["delta_e"], entier.mesures["delta_e"])
        self.assertEqual(decoupe.fichiers["apercu.png"],
                         entier.fichiers["apercu.png"])

    def test_une_decoupe_impossible_est_refusee_et_expliquee(self):
        from bfk001.pipeline import run as executer
        with self.assertRaises(ValueError) as saisi:
            executer(photo(), Reglages(studs=16, hauteur=16, sections=16))
        self.assertIn("rien a decouper", str(saisi.exception))

    def test_l_atelier_transmet_la_decoupe(self):
        atelier = Atelier()
        reponse = atelier.fabriquer({
            "photo": base64.b64encode(photo()).decode(),
            "reglages": {"studs": 16, "hauteur": 16, "sections": "8"},
        })
        self.assertEqual(reponse["mesures"]["sections"], 4)
        self.assertIn("section_1_1/apercu.png", reponse["apercus"])
        with zipfile.ZipFile(BytesIO(atelier.archive(reponse["jeton"]))) as zf:
            self.assertIn("section_2_2/notice.pdf", zf.namelist())


class TestMemoDeReduction(unittest.TestCase):
    """Le cache de reechantillonnage : plus vite, et EXACTEMENT pareil.

    Reduire une photo de telephone au format d'une mosaique lit douze millions
    de pixels. La chaine le demandait HUIT fois sur la meme image — deux pour
    quantifier, quatre pour mesurer la fidelite, une pour le debruitage, une
    pour l'apercu de la source. Sept dixiemes du travail d'image etaient une
    repetition exacte : 27 s pour une photo de 12 Mpx, contre 4,4 s ensuite.

    Une optimisation qui change la sortie n'est pas une optimisation, c'est un
    bug. Ces tests comparent les OCTETS livres, cache actif contre cache
    neutralise, et pas seulement le nombre de pieces.
    """

    def empreintes(self, photo, **reglages):
        import hashlib
        from bfk001.pipeline import Reglages, run

        resultat = run(photo, Reglages(titre="essai", **reglages))
        return {nom: hashlib.sha256(contenu).hexdigest()
                for nom, contenu in resultat.fichiers.items()}

    def test_le_cache_ne_change_pas_un_octet_de_ce_qui_est_livre(self):
        from bfk001 import imaging

        cas = (
            ("petite", photo(96, 96), dict(studs=24, hauteur=24)),
            ("relief", photo(240, 240), dict(studs=24, hauteur=24, relief=2)),
            ("tramage auto", photo(300, 200), dict(studs=32, hauteur=24)),
            ("sans cadre", photo(200, 200), dict(studs=16, hauteur=16, cadre=0)),
        )
        garde = imaging.MEMO_REDUCTIONS
        try:
            for etiquette, image, reglages in cas:
                imaging.MEMO_REDUCTIONS = garde
                imaging._MEMO_REDUCTION.clear()
                avec = self.empreintes(image, **reglages)

                imaging.MEMO_REDUCTIONS = 0   # chaque appel recalcule
                imaging._MEMO_REDUCTION.clear()
                sans = self.empreintes(image, **reglages)

                self.assertEqual(avec, sans, f"{etiquette} : le cache change "
                                 "la sortie, ce n'est plus une optimisation")
        finally:
            imaging.MEMO_REDUCTIONS = garde
            imaging._MEMO_REDUCTION.clear()

    def test_deux_images_distinctes_ne_partagent_jamais_une_reduction(self):
        # Le cache est indexe par IDENTITE. S'il rendait la reduction d'une
        # autre image, la mosaique sortirait simplement fausse — sans erreur,
        # sans trace. C'est le seul mode de panne qui compte ici.
        from bfk001.imaging import Image, resample_box

        claire = Image.from_pixels(64, 64, [(240, 240, 240)] * 4096)
        sombre = Image.from_pixels(64, 64, [(10, 10, 10)] * 4096)
        a = resample_box(claire, 8, 8)
        b = resample_box(sombre, 8, 8)
        self.assertNotEqual(a.data, b.data)
        self.assertEqual(resample_box(claire, 8, 8).data, a.data)

    def test_le_cache_ne_retient_pas_la_photo_en_memoire(self):
        # Une reference forte etait mon premier reflexe, et c'etait une fuite :
        # cent megaoctets gardes en vie entre deux fabrications, pour rien.
        import gc
        import weakref
        from bfk001 import imaging
        from bfk001.imaging import resample_box

        imaging._MEMO_REDUCTION.clear()
        source = photo_image(200, 150)
        resample_box(source, 40, 30)
        suivi = weakref.ref(source)
        del source
        gc.collect()
        self.assertIsNone(suivi(), "le cache garde la photo en vie")

    def test_une_entree_morte_ne_sert_jamais_a_une_autre_image(self):
        # Un identifiant se recycle des que l'objet meurt. Sans la
        # verification d'identite, une nouvelle image nee a l'adresse d'une
        # ancienne recevrait la reduction de l'ancienne — et la mosaique
        # sortirait fausse, sans une ligne d'erreur.
        import gc
        from bfk001 import imaging
        from bfk001.imaging import Image, resample_box

        imaging._MEMO_REDUCTION.clear()
        for _ in range(40):
            claire = Image.from_pixels(40, 40, [(250, 250, 250)] * 1600)
            self.assertEqual(resample_box(claire, 4, 4).data,
                             bytes([250]) * (4 * 4 * 3))
            del claire
            gc.collect()
            sombre = Image.from_pixels(40, 40, [(4, 4, 4)] * 1600)
            self.assertEqual(resample_box(sombre, 4, 4).data,
                             bytes([4]) * (4 * 4 * 3))
            del sombre
            gc.collect()

    def test_le_cache_rend_le_meme_objet_et_reste_borne(self):
        from bfk001 import imaging
        from bfk001.imaging import Image, resample_box

        imaging._MEMO_REDUCTION.clear()
        source = photo_image(120, 90)
        self.assertIs(resample_box(source, 30, 22), resample_box(source, 30, 22))

        # Au-dela du plafond, les plus anciennes tombent : ce ne sont pas les
        # sorties qui pesent mais les ENTREES, gardees pour que l'identite
        # reste valide.
        for i in range(imaging.MEMO_REDUCTIONS + 3):
            resample_box(photo_image(60 + i, 50 + i), 10, 10)
        self.assertLessEqual(len(imaging._MEMO_REDUCTION),
                             imaging.MEMO_REDUCTIONS)


class TestPaletteDepuisLAtelier(unittest.TestCase):
    """La palette officielle s'installe depuis la page, pas en ligne de commande.

    Le depot n'embarque pas `LDConfig.ldr` : il appartient a LDraw.org et ne
    porte aucune mention de licence verifiable. L'installer sur la machine de
    qui le demande est autre chose que le redistribuer — c'est ce que fait tout
    outil de CAO LEGO.
    """

    def ldconfig(self, couleurs=150):
        return "\n".join(
            ["0 LDraw.org Configuration File"]
            + [f"0 !COLOUR T{i} CODE {i} VALUE #{i:02X}4020 EDGE #333333"
               for i in range(1, couleurs + 1)]
        ).encode()

    def test_l_atelier_dit_quelle_palette_il_emploie(self):
        petite = bfk.Palette([bfk.LegoColor(0, "Black", (5, 19, 29)),
                              bfk.LegoColor(15, "White", (255, 255, 255))])
        atelier = Atelier(palette=petite, palette_complete=petite,
                          note_palette=("alerte", "  palette : PROVISOIRE"))
        etat = atelier.etat_palette()
        self.assertEqual(etat["couleurs"], 2)
        self.assertTrue(etat["provisoire"])
        self.assertIn("palette", atelier.etat_catalogues())

    def test_installer_remplace_la_palette_sans_redemarrer(self):
        import pathlib as _p
        import tempfile

        from bfk001 import palette as module

        petite = bfk.Palette([bfk.LegoColor(0, "Black", (5, 19, 29)),
                              bfk.LegoColor(15, "White", (255, 255, 255))])
        atelier = Atelier(palette=petite, palette_complete=petite,
                          note_palette=("alerte", "  palette : PROVISOIRE"))
        cible = _p.Path(tempfile.mkdtemp()) / "LDConfig.ldr"
        charge = self.ldconfig()
        vraie = module.installer_palette

        def fausse():
            return vraie(str(cible), ["http://exemple/ok"],
                         ouvrir=lambda url: charge)

        module.installer_palette = fausse
        try:
            etat = atelier.installer_palette()
        finally:
            module.installer_palette = vraie

        self.assertEqual(etat["couleurs"], 150)
        self.assertFalse(etat["provisoire"])
        # Et la fabrication suivante emploie VRAIMENT la nouvelle palette.
        reponse = atelier.fabriquer({
            "photo": base64.b64encode(photo(48, 48)).decode(),
            "reglages": {"studs": 12, "hauteur": 12, "cadre": 0},
        })
        self.assertGreater(reponse["mesures"]["couleurs"], 2)

    def test_l_adresse_ne_vient_jamais_de_la_page(self):
        # Une URL fournie par le reseau ferait de ce serveur un relais pour
        # aller chercher n'importe quoi a la place de qui l'heberge.
        import inspect

        from bfk001.webapp import Atelier as A

        signature = inspect.signature(A.installer_palette)
        self.assertEqual(list(signature.parameters), ["self"])


class TestLArbitrageDuTramageSePublie(unittest.TestCase):
    """Un arbitrage dont on ne publie qu'un cote n'en est pas un.

    Le journal disait « ce grain coute +0,39 delta E » sans jamais dire contre
    QUOI. Le gain etait calcule dans `quantize`, servait a decider, et etait
    jete. On lisait donc le prix sans le bien.
    """

    def gain_rapporte(self, **options):
        from bfk001 import pipeline

        resultat = pipeline.run(
            photo(160, 200),
            pipeline.Reglages(studs=20, titre="essai", **options),
            palette=bfk.PROVISIONAL_PALETTE.solids_only(),
            palette_complete=bfk.PROVISIONAL_PALETTE,
            note_palette=("info", "essai"))
        return "\n".join(t for _, t in resultat.journal)

    def test_le_gain_sort_par_le_meme_appel_que_la_decision(self):
        # Le recalculer ailleurs le ferait diverger : c'est arrive deux fois
        # dans ce depot (§ 5.61, § 5.64). Le rapport suit la decision.
        rapport = {}
        image = bfk.read_png(photo(160, 200))
        grille = bfk.mosaic.quantize(
            image, bfk.PROVISIONAL_PALETTE.solids_only(), 20, 25,
            "auto", "stretch", rapport=rapport)
        self.assertIn("gain_tonal", rapport)
        self.assertIn("trame", rapport)
        self.assertEqual(rapport["seuil"], bfk.mosaic.DITHER_AUTO_MIN_GAIN)
        # La cle dit bien ce qui a ete livre.
        nette = bfk.mosaic.quantize(
            image, bfk.PROVISIONAL_PALETTE.solids_only(), 20, 25,
            False, "stretch")
        self.assertEqual(rapport["trame"], grille != nette)

    def test_le_journal_chiffre_le_gain_dans_les_deux_sens(self):
        texte = self.gain_rapporte()
        self.assertIn("tramage :", texte)
        self.assertIn("delta E", texte)
        # Quel que soit le verdict, un nombre accompagne le mot.
        ligne = next(l for l in texte.splitlines() if "tramage :" in l)
        self.assertRegex(ligne, r"-?\d+\.\d\d delta E",
                         f"verdict sans chiffre : {ligne}")

    def test_un_tramage_impose_ne_pretend_pas_avoir_arbitre(self):
        # Sans « auto », aucune comparaison n'a lieu : annoncer un gain serait
        # inventer un chiffre.
        texte = self.gain_rapporte(tramage="complet")
        self.assertNotIn("tramage : applique", texte)


class TestConseilDeFormat(unittest.TestCase):
    """Le conseil doit annoncer ce que la chaine FABRIQUE, pas autre chose."""

    def test_il_annonce_exactement_ce_que_la_chaine_livre(self):
        """Le defaut qu'il faut empecher de revenir.

        La premiere version quantifiait de son cote : sans cadre, sans
        nettoyage, sans tramage automatique. Elle annoncait des nombres de
        pieces faux de -32 a +91 — et les ecarts se compensaient a moitie, ce
        qui est le pire des cas : les chiffres paraissaient justes.

        C'est le defaut du tramage (§ 5.61) refait un commit plus tard :
        evaluer une grille qui n'est pas celle qu'on livre. Deux fois la meme
        erreur veut dire que le probleme etait la DUPLICATION, pas
        l'inattention. Ce test verifie l'egalite sur des reglages qui touchent
        chacun un maillon different.
        """
        from bfk001.pipeline import Reglages, conseil_de_format, lire_image, run

        image = lire_image(photo(160, 200))
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        for etiquette, options in (
                ("par defaut", {}),
                ("sans cadre", {"cadre": 0}),
                ("cadre epais", {"cadre": 4}),
                ("relief", {"relief": 2}),
                ("relief renverse", {"relief": 2, "relief_inverse": True}),
                ("tuiles larges", {"references": "large"}),
                ("sans nettoyage", {"debruitage": 0.0}),
                ("tramage impose", {"tramage": "complet"}),
        ):
            reglages = Reglages(studs=20, titre="essai", **options)
            hauteur = round(20 * image.height / image.width)
            conseil = conseil_de_format(image, 20, hauteur, palette, reglages,
                                        multiples=(1.0,))[0]
            livre = run(photo(160, 200), reglages,
                        palette=palette,
                        palette_complete=bfk.PROVISIONAL_PALETTE,
                        note_palette=("info", "essai")).mesures
            self.assertEqual(conseil["pieces"], livre["pieces"], etiquette)
            self.assertEqual(conseil["studs_x"], livre["studs_x"], etiquette)

    def test_la_vignette_montre_le_meme_morceau_avec_plus_de_tuiles(self):
        # Une vignette de l'oeuvre entiere a 74 pixels de large est identique
        # pour 32 et pour 96 tenons : elle decore, elle n'informe pas. Le tiers
        # central, affiche a largeur constante, porte lui trois fois plus de
        # tuiles dans la version fine — c'est ce qu'on veut montrer.
        from bfk001.pipeline import Reglages, conseil_de_format, lire_image

        image = lire_image(photo(160, 160))
        conseils = conseil_de_format(
            image, 16, 16, bfk.PROVISIONAL_PALETTE.solids_only(),
            Reglages(studs=16, hauteur=16), multiples=(1.0, 2.0, 4.0))
        largeurs = [bfk.read_png(c["detail_vu"]).width for c in conseils]
        self.assertEqual(largeurs, sorted(largeurs), largeurs)
        self.assertGreater(largeurs[-1], largeurs[0] * 2)
        # Et l'apercu entier reste disponible a cote.
        for c in conseils:
            self.assertGreater(bfk.read_png(c["apercu"]).width,
                               bfk.read_png(c["detail_vu"]).width)

    def test_les_formats_conseilles_encadrent_celui_qu_on_a_demande(self):
        from bfk001.pipeline import Reglages, conseil_de_format, lire_image

        image = lire_image(photo(120, 120))
        conseils = conseil_de_format(image, 24, 24,
                                     bfk.PROVISIONAL_PALETTE.solids_only(),
                                     Reglages(studs=24, hauteur=24))
        tailles = [c["studs_x"] for c in conseils]
        self.assertEqual(tailles, sorted(tailles))
        self.assertIn(24, tailles)
        self.assertLess(min(tailles), 24)
        self.assertGreater(max(tailles), 24)
        # Plus grand veut dire plus de pieces et plus de detail, toujours.
        for avant, apres in zip(conseils, conseils[1:]):
            self.assertGreater(apres["pieces"], avant["pieces"])
            self.assertLess(apres["detail"], avant["detail"])

    def test_le_conseil_par_le_reseau_refuse_une_requete_sans_photo(self):
        atelier = Atelier()
        with self.assertRaises(ValueError):
            atelier.conseiller({"reglages": {"studs": 16}})
