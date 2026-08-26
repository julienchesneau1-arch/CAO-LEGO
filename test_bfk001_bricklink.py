"""Liste de course commandable : ce qui n'est pas dans la table n'est pas deviné."""

import unittest
import xml.etree.ElementTree as ET

import bfk001 as bfk
from bfk001.bricklink import UnmappedColors, dumps_wanted_list, load_color_map
from bfk001.catalog import BomLine

TABLE = "ldraw,bricklink\n0,11\n15,1\n71,86\n4,5\n2,6\n"


class TestLectureDeLaTable(unittest.TestCase):
    def test_deux_colonnes_virgule_ou_point_virgule(self):
        self.assertEqual(load_color_map("0,11\n15;1\n"), {0: 11, 15: 1})

    def test_entete_commentaires_et_lignes_vides_ignores(self):
        self.assertEqual(
            load_color_map("ldraw,bricklink\n\n# note\n0,11\n  \n15,1\n"),
            {0: 11, 15: 1},
        )

    def test_une_contradiction_est_refusee(self):
        # Deux codes BrickLink pour un meme code LDraw : silencieusement, le
        # dernier gagnerait et une partie de la commande serait fausse.
        with self.assertRaises(ValueError) as capture:
            load_color_map("0,11\n0,12\n")
        self.assertIn("deja associe", str(capture.exception))
        # Repeter la MEME correspondance reste licite.
        self.assertEqual(load_color_map("0,11\n0,11\n"), {0: 11})

    def test_une_table_vide_ou_illisible_est_refusee(self):
        for texte in ("", "# rien\n", "\n\n"):
            with self.assertRaises(ValueError):
                load_color_map(texte)
        with self.assertRaises(ValueError):
            load_color_map("0,11\nune ligne cassee\n")

    def test_une_ligne_a_une_colonne_est_refusee(self):
        with self.assertRaises(ValueError):
            load_color_map("0\n")


class TestExport(unittest.TestCase):
    def bom(self):
        return [
            BomLine("3070b", "Tile 1 x 1", 0, 186),
            BomLine("2431", "Tile 1 x 4", 15, 42),
            BomLine("3020", "Plate 2 x 4", 71, 300),
        ]

    def test_le_xml_est_bien_forme_et_complet(self):
        table = load_color_map(TABLE)
        racine = ET.fromstring(dumps_wanted_list(self.bom(), table))
        self.assertEqual(racine.tag, "INVENTORY")
        articles = racine.findall("ITEM")
        self.assertEqual(len(articles), 3)
        lus = {
            (a.findtext("ITEMID"), int(a.findtext("COLOR")),
             int(a.findtext("MINQTY")))
            for a in articles
        }
        self.assertEqual(
            lus, {("3070b", 11, 186), ("2431", 1, 42), ("3020", 86, 300)}
        )
        for article in articles:
            self.assertEqual(article.findtext("ITEMTYPE"), "P")

    def test_une_couleur_absente_de_la_table_fait_echouer(self):
        # Le point du module : ne pas livrer une commande partiellement fausse.
        table = load_color_map("0,11\n")
        with self.assertRaises(UnmappedColors) as capture:
            dumps_wanted_list(self.bom(), table)
        self.assertEqual(capture.exception.codes, (15, 71))

    def test_les_quantites_sont_celles_de_la_nomenclature(self):
        table = load_color_map(TABLE)
        racine = ET.fromstring(dumps_wanted_list(self.bom(), table))
        self.assertEqual(
            sum(int(a.findtext("MINQTY")) for a in racine.findall("ITEM")),
            sum(l.quantity for l in self.bom()),
        )

    def test_une_reference_peut_etre_corrigee_au_cas_par_cas(self):
        table = load_color_map(TABLE)
        xml = dumps_wanted_list(self.bom(), table, part_map={"3070b": "3070"})
        racine = ET.fromstring(xml)
        self.assertIn("3070", {a.findtext("ITEMID") for a in racine.findall("ITEM")})

    def test_une_reference_exotique_ne_casse_pas_le_xml(self):
        table = load_color_map("0,11\n")
        xml = dumps_wanted_list(
            [BomLine("a&b<c>", "bizarre", 0, 1)], table
        )
        racine = ET.fromstring(xml)
        self.assertEqual(racine.find("ITEM").findtext("ITEMID"), "a&b<c>")


class TestChaineComplete(unittest.TestCase):
    def test_depuis_une_vraie_mosaique(self):
        import random

        random.seed(4)
        pixels = bytes(random.randrange(256) for _ in range(12 * 12 * 3))
        mosaique = bfk.mosaic.from_image(
            bfk.Image(12, 12, pixels),
            bfk.PROVISIONAL_PALETTE.solids_only(),
            12, 12,
        )
        nomenclature = bfk.bill_of_materials(
            mosaique.instances, mosaique.placed_parts
        )
        codes = {l.color_id for l in nomenclature}
        table = {code: 100 + index for index, code in enumerate(sorted(codes))}
        racine = ET.fromstring(dumps_wanted_list(nomenclature, table))
        self.assertEqual(len(racine.findall("ITEM")), len(nomenclature))
        # Toutes les pieces du modele figurent sur la commande, sans exception.
        self.assertEqual(
            sum(int(a.findtext("MINQTY")) for a in racine.findall("ITEM")),
            mosaique.part_count,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
