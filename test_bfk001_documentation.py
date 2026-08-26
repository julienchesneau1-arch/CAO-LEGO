"""La documentation est verifiee comme du code.

Un registre perime est une zone d'ombre — il donne une fausse assurance, ce qui
est pire que l'absence d'assurance. Ce fichier attrape les derives que j'ai
laissees passer plusieurs fois : references croisees vers des sections
inexistantes, sous-sections dans le desordre, fichiers annonces mais jamais
produits, options documentees mais absentes.
"""

import pathlib
import re
import unittest

RACINE = pathlib.Path(__file__).parent
REGISTRE = RACINE / "docs" / "ZONES_DOMBRE.md"
LISEZMOI = RACINE / "README.md"
DEMO = RACINE / "demo_lego_art.py"


class TestRegistre(unittest.TestCase):
    def setUp(self):
        self.texte = REGISTRE.read_text(encoding="utf-8")

    def test_toutes_les_references_croisees_resolvent(self):
        existantes = set(re.findall(r"^### (\d+\.\d+)", self.texte, re.M))
        citees = set(re.findall(r"§+\s*(\d+\.\d+)", self.texte))
        self.assertTrue(citees, "aucune reference : le controle ne verifie rien")
        manquantes = sorted(citees - existantes)
        self.assertEqual(manquantes, [], f"references orphelines : {manquantes}")

    def test_les_sous_sections_sont_dans_l_ordre(self):
        # Elles se sont lues 6.5, 6.6, 6.1, 6.2, 6.3, 6.4 pendant un moment.
        par_partie = {}
        for numero in re.findall(r"^### (\d+)\.(\d+)", self.texte, re.M):
            par_partie.setdefault(int(numero[0]), []).append(int(numero[1]))
        for partie, sous in par_partie.items():
            self.assertEqual(
                sous, sorted(sous), f"partie {partie} dans le desordre : {sous}"
            )

    def test_aucun_numero_de_section_en_double(self):
        numeros = re.findall(r"^### (\d+\.\d+)", self.texte, re.M)
        doublons = {n for n in numeros if numeros.count(n) > 1}
        self.assertEqual(doublons, set(), f"sections dupliquees : {doublons}")

    def test_les_zones_declarees_fermees_le_sont_vraiment(self):
        # Chaque ligne « FERMEE » du tableau des zones ouvertes doit nommer le
        # module qui la ferme, ou la section qui l'explique.
        for ligne in self.texte.splitlines():
            if "**FERMÉE" in ligne:
                self.assertTrue(
                    re.search(r"`[a-z_]+\.py`|§ \d+\.\d+", ligne),
                    f"zone fermee sans preuve : {ligne[:80]}",
                )


class TestPromessesDeLaCommande(unittest.TestCase):
    def setUp(self):
        self.demo = DEMO.read_text(encoding="utf-8")
        self.lisezmoi = LISEZMOI.read_text(encoding="utf-8")

    def test_les_fichiers_annonces_sont_produits(self):
        # Le README a liste des sorties qui n'existaient plus, et l'inverse.
        annonces = set(re.findall(r"`([a-z_]+\.(?:png|csv|txt|pdf|json|ldr|xml))`",
                                  self.lisezmoi))
        produits = set(re.findall(r'"([a-z_]+\.(?:png|csv|txt|pdf|json|ldr|xml))"',
                                  self.demo))
        self.assertTrue(produits, "la commande ne produit rien ?")
        jamais = sorted(annonces - produits - {"photo.jpg", "couleurs.csv"})
        self.assertEqual(jamais, [], f"annonces mais jamais produits : {jamais}")

    def test_les_options_documentees_existent(self):
        options = set(re.findall(r"`(--[a-z-]+)", self.lisezmoi))
        declarees = set(re.findall(r'"(--[a-z-]+)"', self.demo))
        self.assertTrue(declarees)
        fantomes = sorted(options - declarees)
        self.assertEqual(fantomes, [], f"options documentees, absentes : {fantomes}")

    def test_chaque_module_du_paquet_est_dans_l_arborescence_du_lisezmoi(self):
        modules = {
            chemin.name
            for chemin in (RACINE / "bfk001").glob("*.py")
            if chemin.name != "__init__.py"
        }
        manquants = sorted(m for m in modules if f"bfk001/{m}" not in self.lisezmoi)
        self.assertEqual(manquants, [], f"modules absents du README : {manquants}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
