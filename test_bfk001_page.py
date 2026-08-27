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


def _catalogues(palette, dossier):
    """Deux catalogues FACTICES, ecrits dans le dossier du test.

    Ces numeros ne sont pas de vrais element ids et ne quittent pas /tmp : ce
    qu'on verifie ici est le TRAJET — depot, lecture, commande, telechargement —
    pas la valeur des numeros, qui vient du catalogue de l'utilisateur.
    """
    elements = ["element_id,design_id,color_name"]
    couleurs = []
    numero = 8000000
    for design in sorted(bfk.CATALOG):
        for couleur in palette:
            numero += 1
            elements.append(
                f"{numero},{design},{couleur.name.replace('_', ' ')}")
    for rang, couleur in enumerate(palette, start=1):
        couleurs.append(f"{couleur.code},{rang}")
    un = dossier / "elements_factices.csv"
    deux = dossier / "bricklink_factice.csv"
    un.write_text("\n".join(elements) + "\n")
    deux.write_text("\n".join(couleurs) + "\n")
    return un, deux


@unittest.skipIf(sync_playwright is None, "playwright absent : page non verifiee")
@unittest.skipUnless(pathlib.Path(CHROMIUM).exists(),
                     f"navigateur absent en {CHROMIUM}")
class TestPageDansUnNavigateur(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.memoire = pathlib.Path(
            os.environ.get("TMPDIR", "/tmp")) / "bfk_page_catalogues"
        # Le dossier de memoire est celui du test : un test n'ecrit pas dans le
        # « ~/.brickforge » de qui le lance.
        cls.atelier = Atelier(dossier=cls.memoire)
        cls.serveur = creer_serveur("127.0.0.1", 0, cls.atelier)
        cls.fil = threading.Thread(target=cls.serveur.serve_forever, daemon=True)
        cls.fil.start()
        cls.base = f"http://127.0.0.1:{cls.serveur.server_address[1]}"
        cls.dossier = pathlib.Path(
            os.environ.get("TMPDIR", "/tmp")) / "bfk_page_essai"
        cls.dossier.mkdir(exist_ok=True)
        cls.photo = cls.dossier / "photo.png"
        cls.photo.write_bytes(photo_png())
        cls.elements, cls.couleurs_bl = _catalogues(
            cls.atelier.palette_complete, cls.dossier)

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
        self.page.wait_for_selector("#resultat.montre", timeout=180000)

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
        self.page.click("#fins summary")
        self.page.fill("#couleurs", "beaucoup")
        self.page.click("#lancer")
        self.page.wait_for_selector("#etat.erreur", timeout=60000)
        self.assertTrue(self.page.inner_text("#etat").strip())
        self.assertFalse(self.page.is_disabled("#lancer"),
                         "apres une erreur, on doit pouvoir reessayer")
        self.assertFalse(self.page.is_visible("#resultat"),
                         "aucun resultat ne doit s'afficher apres un refus")

    # ------------------------------------------------------------------ #
    # Les commandes qui ne sont pas des champs de saisie
    # ------------------------------------------------------------------ #

    def test_les_puces_de_format_ecrivent_dans_le_champ(self):
        # Une puce n'est pas un doublon du champ : c'est le champ qu'elle
        # remplit. Si les deux divergeaient, on fabriquerait une taille et on
        # en lirait une autre.
        self.page.goto(self.base + "/", wait_until="load")
        self.page.click("#formats button:has-text('64')")
        self.assertEqual(self.page.input_value("#studs"), "64")
        self.assertEqual(
            self.page.get_attribute("#formats button:has-text('64')",
                                    "aria-pressed"), "true")
        self.assertEqual(
            self.page.get_attribute("#formats button:has-text('48')",
                                    "aria-pressed"), "false")
        # Et dans l'autre sens : taper une taille libre n'enfonce aucune puce.
        self.page.fill("#studs", "40")
        self.page.dispatch_event("#studs", "input")
        enfoncees = self.page.eval_on_selector_all(
            "#formats button", "n => n.filter(b => b.ariaPressed === 'true').length")
        self.assertEqual(enfoncees, 0)
        self.assertEqual(self.incidents, [], "\n".join(self.incidents))

    def test_les_pastilles_de_cadre_pilotent_le_champ_cache(self):
        self.page.goto(self.base + "/", wait_until="load")
        self.assertEqual(self.page.input_value("#cadre"), "2|0")
        self.page.click("#teintes button[title='brun rougeatre']")
        self.assertEqual(self.page.input_value("#cadre"), "2|70")
        # L'epaisseur et la couleur sont deux choix independants.
        self.page.check("#cadre_large")
        self.assertEqual(self.page.input_value("#cadre"), "3|70")
        # « sans » n'a pas d'epaisseur : la case ne doit pas le ressusciter.
        self.page.click("#teintes button.sans")
        self.assertEqual(self.page.input_value("#cadre"), "0")
        self.page.uncheck("#cadre_large")
        self.assertEqual(self.page.input_value("#cadre"), "0")
        self.assertEqual(self.incidents, [], "\n".join(self.incidents))

    def test_le_comparateur_superpose_deux_images_de_meme_taille(self):
        # Un « avant / apres » desaligne ferait juger un decalage plutot que la
        # quantification. Les deux images doivent avoir les MEMES dimensions
        # naturelles, mesurees dans le navigateur.
        self.fabriquer(studs="16", hauteur="16")
        tailles = self.page.eval_on_selector_all(
            "#scene img",
            "n => n.map(i => [i.naturalWidth, i.naturalHeight])")
        self.assertEqual(len(tailles), 2)
        self.assertEqual(tailles[0], tailles[1])
        self.assertGreater(tailles[0][0], 0)
        self.assertFalse(self.page.eval_on_selector(
            "#scene", "n => n.classList.contains('simple')"))

    def test_tirer_la_poignee_devoile_la_photo(self):
        self.fabriquer(studs="16", hauteur="16")
        boite = self.page.locator("#scene").bounding_box()
        avant = self.page.eval_on_selector("#avant", "n => n.style.clipPath")
        self.page.mouse.move(boite["x"] + boite["width"] * 0.5,
                             boite["y"] + boite["height"] * 0.5)
        self.page.mouse.down()
        self.page.mouse.move(boite["x"] + boite["width"] * 0.85,
                             boite["y"] + boite["height"] * 0.5, steps=6)
        self.page.mouse.up()
        apres = self.page.eval_on_selector("#avant", "n => n.style.clipPath")
        self.assertNotEqual(avant, apres, "la poignee n'a rien deplace")
        self.assertEqual(self.incidents, [], "\n".join(self.incidents))

    def test_le_comparateur_se_retire_hors_du_rendu(self):
        # Superposer la photo a la vue des joints comparerait deux choses
        # differentes : la ou ca n'a pas de sens, ca ne s'affiche pas.
        self.fabriquer(studs="16", hauteur="16")
        self.page.click("#onglets button:has-text('Joints reels')")
        self.page.wait_for_timeout(120)
        self.assertTrue(self.page.eval_on_selector(
            "#scene", "n => n.classList.contains('simple')"))
        self.assertFalse(self.page.is_visible("#poignee"))
        self.page.click("#onglets button:has-text('Rendu')")
        self.page.wait_for_timeout(120)
        self.assertTrue(self.page.is_visible("#poignee"))

    def test_la_source_n_est_pas_un_onglet(self):
        # Elle n'a aucun sens seule : c'est la moitie gauche du comparateur.
        self.fabriquer(studs="16", hauteur="16")
        self.assertNotIn("source", self.page.inner_text("#onglets").lower())

    # ------------------------------------------------------------------ #
    # Commander : le trajet complet, depuis la page
    # ------------------------------------------------------------------ #

    def poser_les_catalogues(self):
        self.page.goto(self.base + "/", wait_until="load")
        self.page.click("#catalogues summary")
        self.page.set_input_files("#cat_elements", str(self.elements))
        self.page.set_input_files("#cat_bricklink", str(self.couleurs_bl))
        self.page.click("#poser_catalogues")
        self.page.wait_for_selector("#etat_catalogues .etat", timeout=30000)

    def test_sans_catalogue_la_carte_commander_le_dit_et_ouvre_le_panneau(self):
        self.__class__.atelier.oublier_catalogues()
        self.fabriquer(studs="16", hauteur="16")
        texte = self.page.inner_text("#commander")
        self.assertIn("Aucune commande prete", texte)
        # Le panneau s'ouvre tout seul : c'est la ou se trouve la reponse.
        self.assertTrue(self.page.is_visible("#cat_elements"))
        self.assertEqual(self.incidents, [], "\n".join(self.incidents))

    def test_deposer_les_catalogues_depuis_la_page_les_enregistre(self):
        self.__class__.atelier.oublier_catalogues()
        self.poser_les_catalogues()
        etat = self.page.inner_text("#etat_catalogues")
        self.assertIn("Elements LEGO", etat)
        self.assertIn("BrickLink", etat)
        # Et le serveur les a vraiment retenus, pas seulement la page.
        self.assertTrue(self.__class__.atelier.table_elements)
        self.assertTrue(self.__class__.atelier.table_bricklink)
        self.assertEqual(self.incidents, [], "\n".join(self.incidents))

    def test_la_commande_lego_se_telecharge_et_est_un_csv_valide(self):
        self.__class__.atelier.oublier_catalogues()
        self.poser_les_catalogues()
        self.page.set_input_files("#fichier", str(self.photo))
        self.page.fill("#studs", "16")
        self.page.fill("#hauteur", "16")
        self.page.click("#lancer")
        self.page.wait_for_selector("#resultat.montre", timeout=180000)

        commander = self.page.inner_text("#commander")
        self.assertIn("Pick a Brick", commander)
        self.assertIn("BrickLink", commander)

        with self.page.expect_download(timeout=60000) as attente:
            self.page.click("#commander a[download='commande_lego.csv']")
        recu = self.dossier / "commande_lego.csv"
        attente.value.save_as(str(recu))
        lignes = recu.read_text().splitlines()
        self.assertEqual(lignes[0], "elementId,quantity")
        self.assertGreater(len(lignes), 1)
        for ligne in lignes[1:]:
            element, quantite = ligne.split(",")
            self.assertTrue(element.isdigit(), ligne)
            self.assertGreater(int(quantite), 0)
        self.assertEqual(self.incidents, [], "\n".join(self.incidents))

    def test_le_bouton_bricklink_met_le_xml_a_portee_de_collage(self):
        # BrickLink importe par copier-coller, pas par fichier. Le bouton doit
        # aboutir dans les deux cas : presse-papier direct, ou zone de texte
        # deja selectionnee quand l'origine ne le permet pas.
        self.__class__.atelier.oublier_catalogues()
        self.poser_les_catalogues()
        self.page.set_input_files("#fichier", str(self.photo))
        self.page.fill("#studs", "16")
        self.page.fill("#hauteur", "16")
        self.page.click("#lancer")
        self.page.wait_for_selector("#resultat.montre", timeout=180000)
        self.page.click("#commander button.action")
        self.page.wait_for_selector("#commander .boutique:last-child p:last-of-type",
                                    timeout=15000)
        self.page.wait_for_timeout(400)
        dit = self.page.inner_text("#commander")
        self.assertTrue("XML copie" in dit or "Ctrl-C" in dit, dit)
        self.assertEqual(self.incidents, [], "\n".join(self.incidents))

    def test_un_resultat_deja_affiche_est_signale_comme_perime(self):
        # Deposer les catalogues APRES avoir fabrique : la carte « Commander »
        # affichee a ete calculee sans eux, et rien ne le dirait autrement.
        self.__class__.atelier.oublier_catalogues()
        self.fabriquer(studs="16", hauteur="16")
        self.assertIn("Aucune commande prete", self.page.inner_text("#commander"))
        # Le panneau s'est ouvert tout seul : la carte « Commander » y renvoie.
        self.assertTrue(self.page.is_visible("#poser_catalogues"))
        self.page.set_input_files("#cat_elements", str(self.elements))
        self.page.click("#poser_catalogues")
        self.page.wait_for_selector("#etat_catalogues .etat", timeout=30000)
        self.assertIn("refabriquez", self.page.inner_text("#etat"))
        self.assertEqual(self.incidents, [], "\n".join(self.incidents))

    def test_la_notice_se_telecharge_seule_sans_passer_par_le_zip(self):
        # Personne ne telecharge une archive pour en extraire un fichier dont
        # il ignore le nom. La notice et la liste doivent etre a un clic.
        self.fabriquer(studs="16", hauteur="16")
        emporter = self.page.inner_text("#emporter")
        self.assertIn("La notice", emporter)
        self.assertIn("La liste de courses", emporter)

        with self.page.expect_download(timeout=60000) as attente:
            self.page.click("#emporter a[download='notice.pdf']")
        recu = self.dossier / "notice_directe.pdf"
        attente.value.save_as(str(recu))
        octets = recu.read_bytes()
        self.assertTrue(octets.startswith(b"%PDF-"))
        self.assertGreater(len(octets), 5000)
        self.assertEqual(self.incidents, [], "\n".join(self.incidents))

    def test_un_raccourci_n_est_propose_que_si_le_fichier_existe(self):
        # `apercu_relief.png` n'est pas produit sans relief ; un raccourci vers
        # un fichier absent rendrait un 404 au clic.
        self.fabriquer(studs="16", hauteur="16")
        liens = self.page.eval_on_selector_all(
            "#emporter a", "n => n.map(a => a.getAttribute('download'))")
        self.assertTrue(liens)
        for nom in liens:
            reponse = self.page.request.get(
                self.page.eval_on_selector(
                    f"#emporter a[download='{nom}']", "a => a.href"))
            self.assertTrue(reponse.ok, f"{nom} rend {reponse.status}")

    def test_les_liens_fabriques_par_le_script_s_ouvrent_en_dehors(self):
        # Les liens vers Pick a Brick et BrickLink sont construits par le
        # script : ils n'existent pas dans le HTML servi, et seul un vrai DOM
        # peut dire s'ils portent target et rel.
        self.__class__.atelier.oublier_catalogues()
        self.poser_les_catalogues()
        self.page.set_input_files("#fichier", str(self.photo))
        self.page.fill("#studs", "16")
        self.page.fill("#hauteur", "16")
        self.page.click("#lancer")
        self.page.wait_for_selector("#resultat.montre", timeout=180000)
        liens = self.page.eval_on_selector_all(
            "#commander a[href^='http']",
            "n => n.map(a => [a.href, a.target, a.rel])")
        self.assertTrue(liens, "aucun lien de commande")
        for adresse, cible, relation in liens:
            self.assertEqual(cible, "_blank", adresse)
            self.assertIn("noopener", relation, adresse)

    def test_la_page_ne_demande_aucune_ressource_exterieure(self):
        externes = []
        self.page.on("request", lambda r: externes.append(r.url)
                     if not r.url.startswith(self.base) else None)
        self.fabriquer(studs="16", hauteur="16")
        self.assertEqual([u for u in externes if not u.startswith("data:")], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
