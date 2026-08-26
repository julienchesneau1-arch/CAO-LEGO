"""La page elle-meme, executee dans un vrai navigateur.

Ce fichier existe a cause de deux defauts que vingt tests verts n'ont pas vus,
parce qu'aucun n'executait le JavaScript de la page :

1. `PAGE` etait une chaine Python NON brute. Le `\\n` du script y devenait un
   saut de ligne reel, ce qui coupait un litteral JavaScript en deux : la page
   entiere ne se parsait plus. Le serveur, lui, la servait parfaitement.
2. Ma propre politique de securite (`default-src 'none'`) interdisait a la page
   d'appeler SON PROPRE serveur : `connect-src` retombe sur `default-src`. Le
   bouton ne faisait rien.

Les deux sont des defauts de TRAJET, comme ceux du § 5.48 : chaque composant
etait correct, c'est la jonction qui ne l'etait pas. Un test qui s'arrete au
HTTP ne peut pas les voir — il faut un moteur de rendu.

Playwright n'est PAS une dependance du projet : le noyau et la chaine
n'emploient que la bibliotheque standard, et rien de ce qui est livre n'en a
besoin. C'est un outil de verification, et ce fichier se saute proprement quand
il est absent — en le disant, pour qu'un saut ne passe pas pour un succes.
"""

import base64
import json
import os
import pathlib
import threading
import unittest
import zipfile

import bfk001 as bfk
from bfk001.webapp import Atelier, creer_serveur

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - depend du poste
    sync_playwright = None

CHROMIUM = os.environ.get(
    "CHROMIUM", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
)


def photo_png(cote=64):
    pixels = bytearray()
    for y in range(cote):
        for x in range(cote):
            dedans = ((x - cote / 2) ** 2 + (y - cote / 2) ** 2
                      < (cote * 0.3) ** 2)
            pixels += bytes((210, 60, 40) if dedans
                            else (40 + x * 120 // cote, 90, 170))
    return bfk.write_png(bfk.Image(cote, cote, bytes(pixels)))


@unittest.skipIf(sync_playwright is None, "playwright absent : page non verifiee")
@unittest.skipUnless(pathlib.Path(CHROMIUM).exists(),
                     f"navigateur absent en {CHROMIUM}")
class TestPageDansUnNavigateur(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.serveur = creer_serveur("127.0.0.1", 0, Atelier())
        cls.fil = threading.Thread(target=cls.serveur.serve_forever, daemon=True)
        cls.fil.start()
        cls.base = f"http://127.0.0.1:{cls.serveur.server_address[1]}"
        cls.dossier = pathlib.Path(
            os.environ.get("TMPDIR", "/tmp")) / "bfk_page_essai"
        cls.dossier.mkdir(exist_ok=True)
        cls.photo = cls.dossier / "photo.png"
        cls.photo.write_bytes(photo_png())

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        cls.serveur.server_close()

    def setUp(self):
        self.incidents = []
        self._playwright = sync_playwright().start()
        self.navigateur = self._playwright.chromium.launch(
            executable_path=CHROMIUM)
        self.page = self.navigateur.new_page(
            viewport={"width": 1280, "height": 1000})
        self.page.on("pageerror",
                     lambda e: self.incidents.append(f"JS: {e}"))
        self.page.on("console", lambda m: self.incidents.append(
            f"console {m.type}: {m.text}") if m.type == "error" else None)

    def tearDown(self):
        self.navigateur.close()
        self._playwright.stop()

    def fabriquer(self, **champs):
        self.page.goto(self.base + "/", wait_until="load")
        self.page.set_input_files("#fichier", str(self.photo))
        for identifiant, valeur in champs.items():
            if identifiant == "relief":
                self.page.select_option("#relief", valeur)
            else:
                self.page.fill("#" + identifiant, valeur)
        self.page.click("#lancer")
        self.page.wait_for_selector("#resultat", state="visible", timeout=180000)

    def test_la_page_se_charge_sans_la_moindre_erreur(self):
        self.page.goto(self.base + "/", wait_until="load")
        self.assertEqual(self.incidents, [], "\n".join(self.incidents))
        self.assertTrue(self.page.is_disabled("#lancer"),
                        "on ne fabrique rien sans photo")

    def test_deposer_une_photo_active_le_bouton(self):
        self.page.goto(self.base + "/", wait_until="load")
        self.page.set_input_files("#fichier", str(self.photo))
        # Attente par SELECTEUR et non par `wait_for_function` : cette
        # derniere evalue une chaine, ce que la politique de securite de la
        # page interdit a juste titre. C'est le test qui s'adapte.
        self.page.wait_for_selector("#lancer:not([disabled])", timeout=15000)
        self.assertTrue(self.page.is_visible("#vignette"))

    def test_le_bouton_fabrique_vraiment_une_mosaique(self):
        # C'est CE test qui echouait sur les deux defauts : script casse, puis
        # requete interdite par la politique de securite.
        self.fabriquer(studs="16", hauteur="16")
        self.assertEqual(self.incidents, [], "\n".join(self.incidents))
        chiffres = self.page.inner_text("#chiffres")
        self.assertIn("pieces", chiffres)
        self.assertIn("ΔE", chiffres)
        self.assertIn("livre   :", self.page.inner_text("#journal"))

    def test_les_onglets_montrent_trois_images_differentes(self):
        self.fabriquer(studs="16", hauteur="16", relief="2")
        vues = set()
        for titre in ("Rendu", "Joints reels", "Relief eclaire"):
            self.page.click(f"#onglets button:has-text('{titre}')")
            self.page.wait_for_timeout(150)
            vues.add(self.page.get_attribute("#rendu", "src"))
        self.assertEqual(len(vues), 3, "trois onglets, trois apercus distincts")

    def test_le_bouton_de_telechargement_rend_l_archive_complete(self):
        self.fabriquer(studs="16", hauteur="16")
        with self.page.expect_download(timeout=60000) as attente:
            self.page.click("#telecharger button")
        archive = self.dossier / "recu.zip"
        attente.value.save_as(str(archive))
        with zipfile.ZipFile(archive) as zf:
            noms = sorted(zf.namelist())
            self.assertIn("notice.pdf", noms)
            self.assertIn("liste_de_course.csv", noms)
            self.assertTrue(zf.read("notice.pdf").startswith(b"%PDF-"))

    def test_une_erreur_du_serveur_est_montree_et_non_avalee(self):
        self.page.goto(self.base + "/", wait_until="load")
        self.page.set_input_files("#fichier", str(self.photo))
        self.page.fill("#studs", "16")
        self.page.fill("#hauteur", "16")
        # Un reglage que le navigateur ne peut pas pre-valider : « couleurs »
        # est un champ libre. Les bornes de « taille » sont, elles, tenues par
        # le navigateur lui-meme — le formulaire ne part meme pas, ce qui est
        # le bon comportement mais ne teste pas le trajet d'erreur.
        self.page.click("#formulaire summary")
        self.page.fill("#couleurs", "beaucoup")
        self.page.click("#lancer")
        self.page.wait_for_selector("#etat.erreur", timeout=60000)
        self.assertTrue(self.page.inner_text("#etat").strip())
        self.assertFalse(self.page.is_disabled("#lancer"),
                         "apres une erreur, on doit pouvoir reessayer")
        self.assertFalse(self.page.is_visible("#resultat"),
                         "aucun resultat ne doit s'afficher apres un refus")

    def test_la_page_ne_demande_aucune_ressource_exterieure(self):
        externes = []
        self.page.on("request", lambda r: externes.append(r.url)
                     if not r.url.startswith(self.base) else None)
        self.fabriquer(studs="16", hauteur="16")
        self.assertEqual([u for u in externes if not u.startswith("data:")], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
