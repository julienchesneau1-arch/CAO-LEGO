"""Commande LEGO Pick a Brick : l'element id s'importe, il ne se calcule pas.

Ce fichier verifie surtout des REFUS. Une liste de course a laquelle il manque
une ligne se repare a la main ; une liste de course dont une ligne designe la
mauvaise couleur se paie en pieces livrees, payees et inutilisables. Les tests
qui comptent ici sont ceux qui empechent la seconde.
"""

import unittest

import bfk001 as bfk
from bfk001 import pickabrick
from bfk001.catalog import BomLine
from bfk001.palette import LegoColor, Palette
from bfk001.pickabrick import (ELEMENTS_PAR_ENVOI, ElementsIllisibles,
                               dumps_upload, elements_for_bom, missing_report,
                               read_color_names, read_elements)

PALETTE = Palette([
    LegoColor(0, "Black", (5, 19, 29), "solid", 26),
    LegoColor(15, "White", (255, 255, 255), "solid", 1),
    LegoColor(71, "Light_Bluish_Grey", (160, 165, 169), "solid", 194),
    LegoColor(4, "Red", (201, 26, 9), "solid", 21),
    LegoColor(191, "Bright_Light_Orange", (254, 186, 4), "solid", None),
])

# Trois formes de catalogue, celles qui circulent reellement. Les element ids
# employes ici sont ceux du fichier de test : rien de ce depot ne pretend
# connaitre le vrai numero d'une piece dans une couleur.
REBRICKABLE = (
    "element_id,part_num,color_id,design_id\n"
    "600001,3024,71,3024\n"
    "600002,3070b,71,3070\n"
    "600003,3024,0,3024\n"
    "600004,3020,0,3020\n"
)
REBRICKABLE_COULEURS = (
    "id,name,rgb,is_trans\n"
    "0,Black,05131D,f\n"
    "71,Light Bluish Gray,A0A5A9,f\n"
)
BRICKLINK_PCC = (
    "Item No\tColor ID\tColor Name\tCode\n"
    "3024\t86\tLight Bluish Gray\t600001\n"
    "3070b\t86\tLight Bluish Gray\t600002\n"
    "3024\t11\tBlack\t600003\n"
)
PAR_LEGOID = (
    "Element ID,Design ID,LEGO Color ID\n"
    "600001,3024,194\n"
    "600003,3024,26\n"
)

BOM = [
    BomLine("3024", "Plate 1 x 1", 71, 40),
    BomLine("3070b", "Tile 1 x 1 with Groove", 71, 12),
    BomLine("3024", "Plate 1 x 1", 4, 3),
]


class TestLectureDuCatalogue(unittest.TestCase):
    def test_forme_rebrickable_avec_sa_table_de_couleurs(self):
        table = read_elements(REBRICKABLE, read_color_names(REBRICKABLE_COULEURS))
        self.assertEqual(table.cle, "nom")
        self.assertEqual(table.entrees[("3024", "light bluish gray")], "600001")
        self.assertEqual(table.lignes_lues, 4)
        self.assertEqual(table.lignes_ignorees, 0)

    def test_forme_bricklink_tabulee_se_lit_seule(self):
        # Cet export porte le NOM de la couleur : aucun second fichier requis.
        table = read_elements(BRICKLINK_PCC)
        self.assertEqual(table.cle, "nom")
        self.assertEqual(table.entrees[("3070b", "light bluish gray")], "600002")

    def test_forme_a_identifiant_lego_passe_par_le_legoid(self):
        table = read_elements(PAR_LEGOID)
        self.assertEqual(table.cle, "lego")
        self.assertEqual(table.entrees[("3024", "194")], "600001")

    def test_un_identifiant_de_couleur_nu_est_refuse(self):
        # Le coeur du module. 71 est « Light Bluish Gray » chez LDraw, un tout
        # autre gris chez BrickLink : le lire sans savoir d'ou il vient
        # commanderait la mauvaise couleur, et personne ne s'en apercevrait
        # avant la livraison.
        nu = "element_id,part_num,color_id\n600001,3024,71\n"
        with self.assertRaises(ElementsIllisibles) as capture:
            read_elements(nu)
        message = str(capture.exception)
        self.assertIn("quel systeme", message)
        self.assertIn("colors.csv", message)
        # Avec la table de couleurs, le meme fichier passe.
        self.assertTrue(read_elements(nu, read_color_names(REBRICKABLE_COULEURS)))

    def test_la_colonne_nom_ne_se_laisse_pas_prendre_pour_la_colonne_id(self):
        # Piege reel : chercher « color » par prefixe attrape « color id ».
        # On lirait alors « 86 » comme un nom de couleur, aucune correspondance
        # ne tomberait juste, et AUCUNE erreur ne se leverait.
        table = read_elements(BRICKLINK_PCC)
        for (_, couleur) in table.entrees:
            self.assertFalse(couleur.isdigit(), f"« {couleur} » est un numero")

    def test_les_colonnes_sont_reconnues_a_leur_entete_pas_a_leur_position(self):
        melange = (
            "design_id,color_name,element_id\n"
            "3024,Light Bluish Gray,600001\n"
        )
        table = read_elements(melange)
        self.assertEqual(table.entrees[("3024", "light bluish gray")], "600001")

    def test_un_entete_de_deux_lettres_ne_designe_pas_une_colonne(self):
        # « no » cherche par prefixe attraperait « notes » ; « number »
        # attraperait « number of sets ». On lirait alors une colonne de texte
        # comme une reference de piece : aucune correspondance, aucune erreur.
        piege = (
            "element_id,notes,number of sets,design_id,color_name\n"
            "600001,rien,42,3024,Black\n"
        )
        table = read_elements(piege)
        self.assertEqual(table.entrees[("3024", "black")], "600001")

    def test_la_normalisation_des_noms_est_celle_de_bricklink(self):
        # Deux normalisations divergentes apparieraient la meme couleur ici et
        # pas la, sans qu'aucun test de l'un ou l'autre module ne le voie.
        from bfk001.bricklink import _normaliser
        from bfk001 import pickabrick
        self.assertIs(pickabrick._normaliser, _normaliser)

    def test_les_lignes_illisibles_sont_comptees_pas_avalees(self):
        abime = REBRICKABLE + "600005,3020\n" + ",3020,0,3020\n"
        table = read_elements(abime, read_color_names(REBRICKABLE_COULEURS))
        self.assertEqual(table.lignes_lues, 4)
        self.assertEqual(table.lignes_ignorees, 2)

    def test_un_element_qui_casserait_le_csv_est_ecarte(self):
        # Une colonne mal decoupee produit des « element ids » qui n'en sont
        # pas. Les ecrire donnerait un CSV que Pick a Brick refuse sans dire ou.
        table = read_elements(
            "element_id,design_id,color_name\n"
            '600001,3024,Black\n'
            '"6000 02",3020,Black\n',
        )
        self.assertEqual(len(table), 1)
        self.assertEqual(table.lignes_ignorees, 1)

    def test_un_catalogue_compresse_se_lit_sans_qu_on_l_ouvre(self):
        import gzip
        import io
        import zipfile
        from bfk001.pickabrick import decompresser

        self.assertEqual(decompresser(REBRICKABLE.encode()), REBRICKABLE)
        self.assertEqual(
            decompresser(gzip.compress(REBRICKABLE.encode())), REBRICKABLE)
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as archive:
            archive.writestr("elements.csv", REBRICKABLE)
        self.assertEqual(decompresser(tampon.getvalue()), REBRICKABLE)

    def test_un_petit_fichier_qui_deviendrait_enorme_est_refuse(self):
        # Un .gz de 200 Ko peut contenir 200 Mo. `gzip.decompress` allouerait
        # le tout avant qu'on puisse dire non.
        import gzip
        from bfk001.pickabrick import (TAILLE_DECOMPRESSEE_MAXIMALE,
                                       decompresser)

        bombe = gzip.compress(b"\0" * (TAILLE_DECOMPRESSEE_MAXIMALE + 1))
        self.assertLess(len(bombe), 1 << 20, "la bombe doit rester petite")
        with self.assertRaises(ElementsIllisibles) as capture:
            decompresser(bombe)
        self.assertIn("Mo une fois ouvert", str(capture.exception))

    def test_le_filtre_des_pieces_ne_change_aucun_resultat(self):
        # Filtrer a la lecture divise la memoire par mille sur un catalogue
        # complet. Ce qui est ecarte ne pouvait apparaitre dans aucune
        # nomenclature : les deux lectures doivent donner le meme fichier.
        from bfk001.pickabrick import PIECES_UTILES

        bruit = "".join(f"90000{i},9999{i},Black\n" for i in range(20))
        texte = "element_id,design_id,color_name\n600020,3070b,Black\n" + bruit
        lot = [BomLine("3070b", "Tile 1 x 1", 0, 9)]
        large = read_elements(texte)
        etroit = read_elements(texte, pieces=PIECES_UTILES)
        self.assertEqual(len(etroit), 1)
        self.assertEqual(etroit.lignes_ecartees, 20)
        self.assertEqual(elements_for_bom(lot, large, PALETTE)[0],
                         elements_for_bom(lot, etroit, PALETTE)[0])

    def test_un_catalogue_vide_ou_sans_les_colonnes_utiles_est_refuse(self):
        for texte in ("", "\n\n", "element_id,quantity\n600001,4\n",
                      "part_num,color_name\n3024,Black\n"):
            with self.assertRaises(ElementsIllisibles):
                read_elements(texte)

    def test_une_table_de_couleurs_vide_ou_muette_est_refusee(self):
        for texte in ("", "id,rgb\n71,A0A5A9\n"):
            with self.assertRaises(ElementsIllisibles):
                read_color_names(texte)


class TestDeLaNomenclatureAuFichier(unittest.TestCase):
    def test_chaque_lot_trouve_son_element(self):
        table = read_elements(REBRICKABLE, read_color_names(REBRICKABLE_COULEURS))
        trouves, absents, _ = elements_for_bom(BOM, table, PALETTE)
        self.assertEqual(dict(trouves), {"600001": 40, "600002": 12})
        self.assertEqual([l.color_id for l in absents], [4])

    def test_les_trois_formes_donnent_le_meme_element(self):
        # Meme piece, meme couleur, trois catalogues d'origines differentes :
        # si les trois ne tombent pas sur le meme numero, c'est la lecture qui
        # est fausse, pas les catalogues.
        lot = [BomLine("3024", "Plate 1 x 1", 71, 5)]
        for texte, noms in ((REBRICKABLE, read_color_names(REBRICKABLE_COULEURS)),
                            (BRICKLINK_PCC, None), (PAR_LEGOID, None)):
            trouves, absents, _ = elements_for_bom(
                lot, read_elements(texte, noms), PALETTE)
            self.assertEqual(trouves, [("600001", 5)])
            self.assertEqual(absents, [])

    def test_la_reference_tronquee_n_est_qu_un_recours_et_se_compte(self):
        # LDraw ecrit `3070b`, LEGO ecrit `3070` : meme moule aujourd'hui. Le
        # repli est licite, mais il se declare — c'est la seule correspondance
        # de ce module qui ne soit pas litterale.
        table = read_elements(REBRICKABLE, read_color_names(REBRICKABLE_COULEURS))
        _, _, replis = elements_for_bom(
            [BomLine("3070b", "Tile 1 x 1", 71, 2)], table, PALETTE)
        self.assertEqual(replis, 1)
        # Quand les deux ecritures figurent, l'exacte gagne.
        deux = read_elements(
            "element_id,design_id,color_name\n"
            "600002,3070,Light Bluish Gray\n"
            "600009,3070b,Light Bluish Gray\n")
        trouves, _, replis = elements_for_bom(
            [BomLine("3070b", "Tile 1 x 1", 71, 2)], deux, PALETTE)
        self.assertEqual(trouves, [("600009", 2)])
        self.assertEqual(replis, 0)

    def test_une_couleur_sans_legoid_ne_s_invente_pas(self):
        # `Bright_Light_Orange` n'a pas de LEGOID dans cette palette : contre un
        # catalogue qui n'indexe que par LEGOID, elle doit ressortir absente et
        # non appariee au hasard.
        table = read_elements(PAR_LEGOID)
        trouves, absents, _ = elements_for_bom(
            [BomLine("3024", "Plate 1 x 1", 191, 7)], table, PALETTE)
        self.assertEqual(trouves, [])
        self.assertEqual(len(absents), 1)

    def test_aucun_element_ne_sort_qui_ne_soit_entre(self):
        table = read_elements(REBRICKABLE, read_color_names(REBRICKABLE_COULEURS))
        connus = set(table.entrees.values())
        trouves, _, _ = elements_for_bom(BOM, table, PALETTE)
        self.assertTrue(set(e for e, _ in trouves) <= connus)


    def test_la_liste_lisible_et_le_fichier_d_envoi_disent_la_meme_chose(self):
        # Deux fichiers, un seul calcul. S'ils divergeaient, le desaccord
        # passerait inapercu : personne ne compare un CSV a deux colonnes avec
        # une liste de courses.
        from bfk001.imaging import Image, write_png
        from bfk001.pipeline import Reglages, run

        table = read_elements(
            "element_id,design_id,color_name\n"
            "600020,3070b,Black\n"
            "600021,41539,Light Bluish Gray\n")
        pixels = [(255, 255, 255) if (x + y) % 2 else (5, 19, 29)
                  for y in range(8) for x in range(8)]
        resultat = run(
            write_png(Image.from_pixels(8, 8, pixels)),
            Reglages(studs=8, hauteur=8, tramage="aucun", cadre=0),
            palette=PALETTE, palette_complete=PALETTE, table_elements=table)

        envoi = {}
        for ligne in resultat.fichiers["commande_lego.csv"].decode(
                ).splitlines()[1:]:
            element, quantite = ligne.split(",")
            envoi[element] = int(quantite)

        lisible = {}
        lignes = resultat.fichiers["liste_de_course.csv"].decode().splitlines()
        self.assertIn("element_id", lignes[0])
        for ligne in lignes[1:]:
            champs = ligne.rsplit(",", 1)
            element = champs[1]
            if element:
                quantite = int(champs[0].rsplit(",", 1)[1])
                lisible[element] = lisible.get(element, 0) + quantite
        self.assertEqual(envoi, lisible)

    def test_sans_catalogue_la_liste_lisible_n_a_pas_la_colonne(self):
        from bfk001.imaging import Image, write_png
        from bfk001.pipeline import Reglages, run

        resultat = run(write_png(Image.from_pixels(8, 8, [(5, 19, 29)] * 64)),
                       Reglages(studs=8, hauteur=8, cadre=0),
                       palette=PALETTE, palette_complete=PALETTE)
        entete = resultat.fichiers["liste_de_course.csv"].decode().splitlines()[0]
        self.assertNotIn("element_id", entete)


class TestDuFichierDEnvoi(unittest.TestCase):
    def test_l_entete_est_celui_que_pick_a_brick_attend(self):
        envois = dumps_upload([("600001", 40)])
        self.assertEqual(envois[0].splitlines()[0], "elementId,quantity")
        self.assertEqual(envois[0].splitlines()[1], "600001,40")
        self.assertTrue(envois[0].endswith("\n"))

    def test_les_quantites_d_un_meme_element_s_additionnent(self):
        self.assertIn("600001,7", dumps_upload([("600001", 4), ("600001", 3)])[0])

    def test_au_dela_de_la_limite_on_decoupe_plutot_que_d_echouer(self):
        lots = [(str(600000 + i), i + 1) for i in range(ELEMENTS_PAR_ENVOI + 1)]
        envois = dumps_upload(lots)
        self.assertEqual(len(envois), 2)
        vus = []
        for envoi in envois:
            lignes = envoi.splitlines()
            self.assertEqual(lignes[0], "elementId,quantity")
            self.assertLessEqual(len(lignes) - 1, ELEMENTS_PAR_ENVOI)
            vus.extend(l.split(",")[0] for l in lignes[1:])
        # Rien de perdu, rien en double : c'est tout ce qu'un decoupage doit
        # promettre.
        self.assertEqual(sorted(vus), sorted(e for e, _ in lots))
        self.assertEqual(len(set(vus)), len(vus))

    def test_le_gros_lot_vient_en_premier(self):
        lignes = dumps_upload([("600001", 2), ("600002", 90)])[0].splitlines()
        self.assertEqual(lignes[1], "600002,90")

    def test_un_envoi_vide_reste_un_csv_valide(self):
        self.assertEqual(dumps_upload([]), ["elementId,quantity\n"])
        self.assertEqual(dumps_upload([("600001", 0)]), ["elementId,quantity\n"])

    def test_le_rapport_des_manquants_donne_de_quoi_chercher(self):
        rapport = missing_report([BomLine("3024", "Plate 1 x 1", 4, 3)], PALETTE)
        lignes = rapport.splitlines()
        self.assertEqual(lignes[0],
                         "design_id,nom,code_couleur,couleur,lego_color_id,quantite")
        self.assertIn("Red", lignes[1])
        self.assertIn("21", lignes[1])       # le LEGOID, pour la recherche


class TestBoutEnBout(unittest.TestCase):
    def test_la_chaine_produit_le_csv_et_le_rapport(self):
        from bfk001.imaging import Image, write_png
        from bfk001.pipeline import Reglages, run

        pixels = [(255, 255, 255) if (x + y) % 2 else (5, 19, 29)
                  for y in range(8) for x in range(8)]
        photo = write_png(Image.from_pixels(8, 8, pixels))
        # Le catalogue couvre les tuiles noires et le substrat, pas le blanc :
        # une commande partielle est exactement le cas a verifier.
        table = read_elements(
            "element_id,design_id,color_name\n"
            "600020,3070b,Black\n"
            "600021,41539,Light Bluish Gray\n")
        resultat = run(
            photo,
            Reglages(studs=8, hauteur=8, tramage="aucun", cadre=0,
                     titre="essai"),
            palette=PALETTE, palette_complete=PALETTE,
            table_elements=table,
        )
        self.assertIn("commande_lego.csv", resultat.fichiers)
        csv = resultat.fichiers["commande_lego.csv"].decode()
        self.assertEqual(csv.splitlines()[0], "elementId,quantity")
        connus = set(table.entrees.values())
        for ligne in csv.splitlines()[1:]:
            self.assertIn(ligne.split(",")[0], connus)
        # Le blanc n'est dans aucun catalogue ici : il doit sortir en clair.
        self.assertIn("pieces_sans_element.csv", resultat.fichiers)
        self.assertIn("White",
                      resultat.fichiers["pieces_sans_element.csv"].decode())
        journal = "\n".join(t for _, t in resultat.journal)
        self.assertIn("commande LEGO", journal)
        self.assertIn("disponibilite", journal)

    def test_sans_catalogue_rien_n_est_produit_ni_promis(self):
        from bfk001.imaging import Image, write_png
        from bfk001.pipeline import Reglages, run

        photo = write_png(Image.from_pixels(8, 8, [(5, 19, 29)] * 64))
        resultat = run(photo, Reglages(studs=8, hauteur=8, cadre=0),
                       palette=PALETTE, palette_complete=PALETTE)
        self.assertNotIn("commande_lego.csv", resultat.fichiers)
        self.assertIn("liste_de_course.csv", resultat.fichiers)


class TestAtelier(unittest.TestCase):
    def test_le_catalogue_donne_au_lanceur_sert_a_chaque_fabrication(self):
        # Un catalogue d'elements est une propriete de l'INSTALLATION : donne
        # une fois, il doit valoir pour toutes les oeuvres suivantes.
        from bfk001.imaging import Image, write_png
        from bfk001.webapp import Atelier

        table = read_elements(
            "element_id,design_id,color_name\n"
            "600020,3070b,Black\n"
            "600021,41539,Light Bluish Gray\n")
        atelier = Atelier(palette=PALETTE, palette_complete=PALETTE,
                          note_palette=("info", "palette d'essai"),
                          table_elements=table)
        photo = write_png(Image.from_pixels(8, 8, [(5, 19, 29)] * 64))
        for _ in range(2):
            reponse = atelier.fabriquer({
                "photo": "data:image/png;base64,"
                         + __import__("base64").b64encode(photo).decode(),
                "reglages": {"studs": 8, "hauteur": 8, "cadre": 0},
            })
            self.assertIn("commande_lego.csv", reponse["fichiers"])


class TestApiPublique(unittest.TestCase):
    def test_le_module_est_reexporte_par_la_facade(self):
        self.assertIn("pickabrick", bfk.__all__)
        self.assertIs(bfk.read_elements, read_elements)


if __name__ == "__main__":
    unittest.main()


# =============================================================================
# Le catalogue decide quelles couleurs existent — au lieu de la finition
# =============================================================================


def _catalogue(couleurs, designs=("3070b", "3069b", "2431")):
    """Catalogue de synthese : ces couleurs, dans ces references."""
    lignes = ["Element ID,Design ID,Color Name"]
    numero = 6000000
    for nom in couleurs:
        for design in designs:
            numero += 1
            lignes.append(f"{numero},{design},{nom}")
    return pickabrick.read_elements("\n".join(lignes))


class TestLeCatalogueProuveAuLieuDeSupposer(unittest.TestCase):
    """La regle par defaut est fausse dans les DEUX sens.

    Trop large : une couleur mate obsolete reste retenue alors qu'aucune tuile
    n'existe plus dedans, et l'utilisateur ne l'apprend qu'en commandant. Trop
    etroite : les nacrees existent bel et bien en tuile 1x1, et les ecarter
    coute 0,7 delta E sur une photo reelle — autant que doubler la resolution.
    """

    def palette(self):
        return bfk.PROVISIONAL_PALETTE

    def test_une_couleur_sans_tuile_est_ecartee_meme_si_elle_est_mate(self):
        noms = [c.name for c in self.palette() if c.is_solid]
        table = _catalogue(noms[:2])
        dispo, ecartees = pickabrick.couleurs_prouvees(
            self.palette(), table, ("3070b", "3069b", "2431"))
        self.assertEqual(sorted(c.name for c in dispo), sorted(noms[:2]))
        self.assertTrue(ecartees, "tout le reste doit etre ecarte")
        for couleur in ecartees:
            self.assertNotIn(couleur.name, noms[:2])

    def test_une_couleur_non_mate_est_RETENUE_si_le_catalogue_la_prouve(self):
        # Le coeur du renversement : la finition ne decide plus.
        nacree = LegoColor(297, "Pearl Gold", (0xAA, 0x7F, 0x2E),
                           finish="pearl", lego_id=297)
        palette = Palette(list(self.palette()) + [nacree])
        self.assertFalse(nacree.is_solid, "la couleur d'essai n'est pas mate")
        table = _catalogue(["Pearl Gold"])
        dispo, _ = pickabrick.couleurs_prouvees(
            palette, table, ("3070b", "3069b", "2431"))
        self.assertIn("Pearl Gold", [c.name for c in dispo],
                      "prouvee par le catalogue, donc retenue")

    def test_il_faut_TOUTES_les_references_pas_seulement_la_1x1(self):
        # La fusion des tuiles est automatique : une couleur qui n'a pas la
        # 1x4 rendrait la liste incommandable des que la fusion s'en sert.
        noms = [c.name for c in self.palette() if c.is_solid][:1]
        partiel = _catalogue(noms, designs=("3070b",))
        exigeant, _ = pickabrick.couleurs_prouvees(
            self.palette(), partiel, ("3070b", "3069b", "2431"))
        indulgent, _ = pickabrick.couleurs_prouvees(
            self.palette(), partiel, ("3070b",))
        self.assertEqual(exigeant, [])
        self.assertEqual([c.name for c in indulgent], noms)

    def test_les_marqueurs_ldraw_ne_passent_jamais(self):
        # 16 et 24 ne sont pas des couleurs. Un catalogue qui les nommerait
        # ne doit pas les faire entrer.
        table = _catalogue(["Main Colour", "Edge Colour"])
        dispo, _ = pickabrick.couleurs_prouvees(
            self.palette(), table, ("3070b",))
        self.assertEqual([c.code for c in dispo if c.code in (16, 24)], [])


class TestLaChaineAdopteLeCatalogue(unittest.TestCase):
    def photo(self):
        pixels = bytearray()
        for y in range(80):
            for x in range(80):
                pixels += bytes(((x * 3) % 256, (y * 3) % 256,
                                 ((x + y) * 2) % 256))
        return bfk.write_png(bfk.Image(80, 80, bytes(pixels)))

    def fabriquer(self, table):
        from bfk001 import pipeline

        return pipeline.run(
            self.photo(), pipeline.Reglages(studs=16, hauteur=16, titre="c"),
            palette=bfk.PROVISIONAL_PALETTE.solids_only(),
            palette_complete=bfk.PROVISIONAL_PALETTE,
            table_elements=table, note_palette=("info", "essai"))

    def test_un_catalogue_complet_est_adopte_et_annonce(self):
        from bfk001 import pipeline

        noms = [c.name for c in bfk.PROVISIONAL_PALETTE
                if c.is_solid and c.code not in (16, 24)]
        # Assez de couleurs pour depasser le plancher.
        table = _catalogue(noms * 1)
        resultat = self.fabriquer(table)
        texte = "\n".join(t for _, t in resultat.journal)
        if len(noms) >= pipeline.COULEURS_PROUVEES_MINIMUM:
            self.assertIn("PROUVEES par le catalogue", texte)
        else:
            # La palette provisoire est trop petite : la chaine doit le DIRE
            # et garder la palette de finition, pas livrer trois couleurs.
            self.assertIn("catalogue PARTIEL", texte)

    def test_un_catalogue_partiel_est_refuse_en_le_disant(self):
        table = _catalogue(["Black", "White"])
        resultat = self.fabriquer(table)
        texte = "\n".join(t for _, t in resultat.journal)
        self.assertIn("catalogue PARTIEL", texte)
        self.assertIn("verifiez que le fichier est complet", texte)
        # Et surtout : la mosaique n'est PAS livree en deux couleurs.
        self.assertGreater(resultat.mesures["lots"], 2)

    def test_un_catalogue_maigre_est_adopte_mais_en_ALERTE(self):
        """Correct sur le fond, jamais en silence.

        Un catalogue nettement plus etroit que la regle de finition est presque
        toujours un fichier incomplet. On l'adopte — on ne commande pas des
        tuiles qui n'existent pas — mais degrader le rendu sans le dire serait
        le pire des deux : mesure sur une photo reelle, 6,7 -> 9,2 delta E.
        """
        from bfk001 import pipeline

        # La palette provisoire ne compte que douze couleurs : trop peu pour
        # que « la moitie » veuille dire quelque chose. On en fabrique une
        # assez grande ici — un test qui se saute ne prouve rien.
        large = Palette(
            [LegoColor(900 + i, f"Essai {i}",
                       ((i * 37) % 256, (i * 91) % 256, (i * 53) % 256))
             for i in range(60)])
        noms = [c.name for c in large]
        seuil = pipeline.COULEURS_PROUVEES_MINIMUM
        table = _catalogue(noms[:seuil])
        resultat = pipeline.run(
            self.photo(), pipeline.Reglages(studs=16, hauteur=16, titre="c"),
            palette=large, palette_complete=large,
            table_elements=table, note_palette=("info", "essai"))
        niveaux = [n for n, t in resultat.journal if "couleurs:" in t]
        self.assertEqual(niveaux, ["alerte"],
                         "un catalogue maigre doit ALERTER, pas informer")
        texte = "\n".join(t for _, t in resultat.journal)
        self.assertIn("catalogue INCOMPLET", texte)

    def test_sans_catalogue_rien_ne_change(self):
        resultat = self.fabriquer(None)
        texte = "\n".join(t for _, t in resultat.journal)
        self.assertNotIn("PROUVEES par le catalogue", texte)
        self.assertNotIn("catalogue PARTIEL", texte)
