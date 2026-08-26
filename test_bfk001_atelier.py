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
        self.assertAlmostEqual(resultat.mesures["largeur_mm"], 16 * 8.0, places=6)

    def test_une_mosaique_qui_ne_tient_pas_n_est_pas_livree(self):
        # Un tenon de large : les tuiles ne se lient a rien. Le noyau refuse,
        # et la chaine ne doit surtout pas ecrire de fichiers quand meme.
        with self.assertRaises((ModeleRefuse, ValueError)):
            run(photo(), Reglages(studs=1, hauteur=40))


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

    def test_la_page_se_sert_et_ne_reclame_aucune_ressource_externe(self):
        with urllib.request.urlopen(self.base + "/", timeout=30) as reponse:
            page = reponse.read().decode("utf-8")
            politique = reponse.headers["Content-Security-Policy"]
        self.assertIn("<title>", page)
        self.assertIn("default-src 'none'", politique)
        # Aucune adresse absolue : la page doit fonctionner hors ligne.
        for motif in ("http://", "https://", "//cdn"):
            self.assertNotIn(motif, page.replace("http://127.0.0.1", ""))

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
