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
            ["apercu.png", "apercu_joints.png", "liste_de_course.csv",
             "modele.json", "modele.ldr", "notice.pdf", "notice.txt"],
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
