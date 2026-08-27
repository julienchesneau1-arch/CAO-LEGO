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


class TestImportDeLaTableDeCouleurs(unittest.TestCase):
    """La table de correspondance s'IMPORTE, elle ne se recopie pas.

    C'etait la derniere donnee que je disais ne pas pouvoir fournir sans
    l'inventer. LDConfig porte le LEGOID — l'identifiant de couleur du systeme
    LEGO — pour 131 de ses 162 couleurs, et BrickLink publie le meme dans son
    export. La correspondance se deduit.
    """

    EXPORT = "\n".join([
        "Color ID\tColor Name\tRGB\tType\tLEGO Color ID",
        "11\tBlack\t212121\tSolid\t26",
        "86\tDark Bluish Gray\t6C6E68\tSolid\t199",
        "8\tBrown\t583927\tSolid\t217",
        "3\tYellow\tF2CD37\tSolid\t24",
    ])

    def palette(self):
        return bfk.Palette([
            bfk.LegoColor(0, "Black", (5, 19, 29), "solid", 26),
            bfk.LegoColor(72, "Dark_Bluish_Grey", (108, 110, 104), "solid", 199),
            bfk.LegoColor(6, "Brown", (88, 57, 39), "solid", None),
            bfk.LegoColor(999, "Inventee", (1, 2, 3), "solid", 4242),
        ])

    def test_l_appariement_se_fait_par_legoid(self):
        table, orphelines = bfk.bricklink.color_map_from_catalog(
            self.EXPORT, self.palette())
        self.assertEqual(table[0], 11)
        self.assertEqual(table[72], 86, "LEGOID 199 des deux cotes")

    def test_le_nom_rattrape_ce_que_le_legoid_ne_couvre_pas(self):
        # « Brown » n'a pas de LEGOID dans cette palette de test : c'est le nom
        # normalise qui l'apparie.
        table, _ = bfk.bricklink.color_map_from_catalog(
            self.EXPORT, self.palette())
        self.assertEqual(table[6], 8)

    def test_grey_et_gray_designent_la_meme_couleur(self):
        # LDraw ecrit « Dark_Bluish_Grey », BrickLink « Dark Bluish Gray ».
        # Le tiret bas et l'orthographe ne sont pas des differences de couleur.
        sans_legoid = bfk.Palette([
            bfk.LegoColor(72, "Dark_Bluish_Grey", (108, 110, 104))])
        table, orphelines = bfk.bricklink.color_map_from_catalog(
            self.EXPORT, sans_legoid)
        self.assertEqual(table.get(72), 86)
        self.assertEqual(orphelines, ())

    def test_ce_qui_ne_s_apparie_pas_est_rendu_et_non_devine(self):
        table, orphelines = bfk.bricklink.color_map_from_catalog(
            self.EXPORT, self.palette())
        self.assertNotIn(999, table)
        self.assertEqual(len(orphelines), 1)
        self.assertIn("Inventee", orphelines[0])

    def test_les_colonnes_sont_reconnues_a_leur_entete(self):
        # L'ordre des colonnes n'est promis nulle part.
        inverse = "\n".join([
            "LEGO Color ID;Color Name;Color ID",
            "26;Black;11",
            "199;Dark Bluish Gray;86",
        ])
        table, _ = bfk.bricklink.color_map_from_catalog(inverse, self.palette())
        self.assertEqual(table[0], 11)
        self.assertEqual(table[72], 86)

    def test_les_deux_formats_se_reconnaissent_tout_seuls(self):
        table, orphelines = bfk.bricklink.read_color_map(
            self.EXPORT, self.palette())
        self.assertEqual(table[0], 11)
        deux_colonnes, rien = bfk.bricklink.read_color_map("0,11\n72,86\n")
        self.assertEqual(deux_colonnes, {0: 11, 72: 86})
        self.assertEqual(rien, ())

    def test_un_export_sans_palette_est_refuse_plutot_que_devine(self):
        with self.assertRaises(ValueError):
            bfk.bricklink.read_color_map(self.EXPORT)

    def test_le_gabarit_donne_de_quoi_completer(self):
        gabarit = bfk.bricklink.color_map_template(self.palette(), {0: 11})
        self.assertIn("0,11", gabarit)
        self.assertIn("999,", gabarit)
        self.assertIn("LEGOID 4242", gabarit)
        self.assertIn("#010203", gabarit)
        # Il se relit meme PARTIELLEMENT rempli : une ligne vide est une
        # absence, pas une erreur. La couleur ressort simplement non appariee.
        partiel = bfk.load_color_map(gabarit)
        self.assertEqual(partiel, {0: 11})
        rempli = gabarit.replace("999,", "999,777")
        table = bfk.load_color_map(rempli)
        self.assertEqual(table[999], 777)
        self.assertEqual(table[0], 11)
