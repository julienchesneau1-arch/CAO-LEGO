"""Notice imprimable : structure du PDF, rendu des pages, ordre de montage.

Un PDF qui « s'ouvre » ne prouve rien : les lecteurs reparent silencieusement
les tables de renvois cassees. On relit donc le fichier octet par octet.
"""

import random
import re
import unittest
import zlib

import bfk001 as bfk
from bfk001 import booklet as bk


def petite_mosaique(cote=12, graine=3):
    random.seed(graine)
    pixels = bytes(random.randrange(256) for _ in range(cote * cote * 3))
    image = bfk.Image(cote, cote, pixels)
    palette = bfk.PROVISIONAL_PALETTE.solids_only()
    return bfk.mosaic.from_image(image, palette, cote, cote), palette


def plan_de(mosaique):
    etat = bfk.assemble(
        mosaique.placed_parts,
        bfk.LEGO_TOLERANCE,
        search=bfk.LatticeSearchApproximation(),
    )
    return bfk.plan_build(mosaique.placed_parts, etat.graph, mosaique.instances)


def disseque(pdf):
    """Structure du PDF, verifiee sans rien supposer. Rend (objets, pages)."""
    assert pdf.startswith(b"%PDF-1."), "en-tete absent"
    assert pdf.rstrip().endswith(b"%%EOF"), "marqueur de fin absent"

    ancres = list(re.finditer(rb"startxref\s+(\d+)\s+%%EOF", pdf))
    assert len(ancres) == 1, f"{len(ancres)} startxref"
    debut = int(ancres[0].group(1))
    tete = re.match(rb"xref\n(\d+) (\d+)\n", pdf[debut:])
    assert tete, f"table illisible: {pdf[debut:debut + 32]!r}"
    assert int(tete.group(1)) == 0, "la table doit commencer a l'objet 0"
    nombre = int(tete.group(2))

    base = debut + tete.end()
    entrees = []
    for index in range(nombre):
        brut = pdf[base + 20 * index : base + 20 * (index + 1)]
        assert re.fullmatch(rb"\d{10} \d{5} [nf] \n", brut), (index, brut)
        entrees.append((int(brut[:10]), brut[17:18]))
    assert entrees[0][1] == b"f", "l'objet 0 doit etre libre"

    # Le coeur du controle : chaque decalage tombe pile sur son en-tete.
    for numero, (decalage, genre) in enumerate(entrees[1:], start=1):
        assert genre == b"n"
        attendu = b"%d 0 obj\n" % numero
        assert pdf[decalage : decalage + len(attendu)] == attendu, numero

    suite = pdf[base + 20 * nombre :]
    trailer = re.match(rb"trailer\n<< /Size (\d+) /Root (\d+) 0 R >>\n", suite)
    assert trailer, f"trailer illisible: {suite[:64]!r}"
    assert int(trailer.group(1)) == nombre
    racine = int(trailer.group(2))
    assert pdf[entrees[racine][0] :].startswith(
        b"%d 0 obj\n<< /Type /Catalog" % racine
    )

    for flux in re.finditer(rb"<<([^<>]*)>>\nstream\n", pdf):
        longueur = int(re.search(rb"/Length (\d+)", flux.group(1)).group(1))
        fin = flux.end() + longueur
        assert pdf[fin : fin + 10] == b"\nendstream", "longueur de flux fausse"
        zlib.decompress(pdf[flux.end() : fin])

    kids = re.search(rb"/Type /Pages /Kids \[([^\]]*)\] /Count (\d+)", pdf)
    numeros = [int(n) for n in re.findall(rb"(\d+) 0 R", kids.group(1))]
    assert len(numeros) == int(kids.group(2)), "/Count ment sur /Kids"
    for numero in numeros:
        assert pdf[entrees[numero][0] :].startswith(
            b"%d 0 obj\n<< /Type /Page " % numero
        )

    corps = [int(n) for n in re.findall(rb"\n(\d+) 0 obj\n", b"\n" + pdf)]
    assert corps == list(range(1, nombre)), "objet orphelin ou numero saute"
    return nombre - 1, len(numeros)


class TestEcriturePdf(unittest.TestCase):
    def test_structure_exacte(self):
        image = bfk.Image(4, 3, bytes(range(36)))
        pdf = bk.write_pdf(
            [
                bk.PdfPage(((40.0, 700.0, 12.0, "Page une", True),), (),
                           ((image, (40.0, 400.0, 200.0, 150.0)),)),
                bk.PdfPage(((40.0, 700.0, 9.0, "Page deux", False),),
                           ((40.0, 100.0, 20.0, 20.0, (10, 20, 30)),)),
            ]
        )
        objets, pages = disseque(pdf)
        self.assertEqual(pages, 2)
        self.assertGreater(objets, 5)

    def test_fascicule_vide_refuse(self):
        with self.assertRaises(ValueError):
            bk.write_pdf([])

    def test_image_sans_cadre_refusee(self):
        image = bfk.Image(1, 1, b"\x00\x00\x00")
        with self.assertRaises(ValueError):
            bk.PdfPage((), (), ((image, None),))
        with self.assertRaises(ValueError):
            bk.PdfPage((), (), ((None, (0.0, 0.0, 1.0, 1.0)),))
        with self.assertRaises(ValueError):
            bk.PdfPage((), (), ((image, (0.0, 0.0, 1.0)),))

    def test_plusieurs_images_sur_une_page(self):
        # La page d'etape en porte deux : la bande et le reperage. Une seule
        # obligeait a choisir entre montrer et situer.
        image = bfk.Image(2, 2, bytes(12))
        pdf = bk.write_pdf([bk.PdfPage(
            (), (), ((image, (0.0, 0.0, 10.0, 10.0)),
                     (image, (20.0, 20.0, 10.0, 10.0))))])
        disseque(pdf)
        flux = b"".join(
            zlib.decompress(bloc.split(b"stream\n", 1)[1].rsplit(b"\nendstream", 1)[0])
            for bloc in pdf.split(b"endobj")
            if b"/Filter /FlateDecode" in bloc and b"/Subtype /Image" not in bloc
        )
        self.assertIn(b"/Im0 Do", flux)
        self.assertIn(b"/Im1 Do", flux)
        self.assertIn(b"/Im0", pdf)
        self.assertIn(b"/Im1", pdf)

    def test_echappement_conserve_les_accents(self):
        # WinAnsiEncoding EST cp1252 : rien a translitterer, donc rien a perdre.
        self.assertEqual(bk._escape("etape reglee"), b"etape reglee")
        self.assertEqual(bk._escape("prêt à coller"), "prêt à coller".encode("cp1252"))
        self.assertEqual(bk._escape("a(b)c\\d"), rb"a\(b\)c\\d")

    def test_parenthese_deballancee_ne_casse_pas_le_flux(self):
        # Une parenthese non echappee terminerait la chaine et decalerait tout
        # le contenu : le PDF resterait syntaxiquement plausible et illisible.
        image = bfk.Image(1, 1, b"\x00\x00\x00")
        pdf = bk.write_pdf(
            [bk.PdfPage(((10.0, 10.0, 9.0, "fin de ligne ) piege (", False),),
                        (), ((image, (0.0, 0.0, 10.0, 10.0)),))]
        )
        disseque(pdf)
        contenus = b"".join(
            zlib.decompress(
                pdf[m.end() : m.end() + int(re.search(rb"/Length (\d+)", m.group(1)).group(1))]
            )
            for m in re.finditer(rb"<<([^<>]*)>>\nstream\n", pdf)
            if b"/Filter /FlateDecode" in m.group(1) and b"/Image" not in m.group(1)
        )
        self.assertIn(rb"fin de ligne \) piege \(", contenus)


class TestPiecesDUneLigne(unittest.TestCase):
    def test_la_lecture_nomme_les_pieces_posees(self):
        # Depuis la fusion, « 4 rouges » designe UNE tuile 1x4. Faire prendre
        # quatre 1x1 enverrait chercher des pieces absentes du sachet.
        mosaique, _ = petite_mosaique(cote=16, graine=8)
        for row in range(mosaique.studs_y):
            attendu = [
                (pose.length, pose.color.code, pose.level)
                for pose in sorted(
                    (p for p in mosaique.tiles if p.row == row),
                    key=lambda p: p.column,
                )
            ]
            lu = [(n, c.code, e) for n, c, e in bk.row_runs(mosaique, row)]
            self.assertEqual(lu, attendu, row)

    def test_la_ligne_est_couverte_exactement(self):
        mosaique, _ = petite_mosaique()
        for row in range(mosaique.studs_y):
            self.assertEqual(
                sum(n for n, _, _ in bk.row_runs(mosaique, row)), mosaique.studs_x
            )

    def test_la_couleur_lue_est_celle_de_la_grille(self):
        mosaique, _ = petite_mosaique()
        for row in range(mosaique.studs_y):
            colonne = 0
            for longueur, couleur, _ in bk.row_runs(mosaique, row):
                for decalage in range(longueur):
                    self.assertEqual(
                        mosaique.grid[row][colonne + decalage].code, couleur.code
                    )
                colonne += longueur

    def test_ligne_hors_mosaique_refusee(self):
        mosaique, _ = petite_mosaique()
        with self.assertRaises(IndexError):
            bk.row_runs(mosaique, mosaique.studs_y)


class TestCodesCouleur(unittest.TestCase):
    def test_la_plus_employee_recoit_A(self):
        mosaique, _ = petite_mosaique(cote=16, graine=5)
        codes = bk.color_codes(mosaique)
        comptes = {}
        for ligne in mosaique.grid:
            for color in ligne:
                comptes[color.code] = comptes.get(color.code, 0) + 1
        dominante = max(comptes, key=lambda c: (comptes[c], -c))
        self.assertEqual(codes[dominante], "A")

    def test_codes_uniques_et_stables(self):
        mosaique, _ = petite_mosaique(cote=16, graine=5)
        codes = bk.color_codes(mosaique)
        self.assertEqual(len(set(codes.values())), len(codes))
        self.assertEqual(codes, bk.color_codes(mosaique))

    def test_au_dela_de_vingt_six_couleurs(self):
        # A..Z puis AA, AB… : jamais deux couleurs sous le meme code.
        couleurs = [
            bfk.LegoColor(code, f"C{code}", (code % 256, 0, 0))
            for code in range(60)
        ]
        grille = tuple(
            tuple(couleurs[(ligne * 60 + colonne) % 60] for colonne in range(60))
            for ligne in range(1)
        )
        faux = type("M", (), {"grid": grille})()
        codes = bk.color_codes(faux)
        self.assertEqual(len(set(codes.values())), 60)
        self.assertIn("AA", codes.values())

    def test_la_lecture_emploie_les_codes(self):
        mosaique, _ = petite_mosaique(cote=12, graine=5)
        codes = bk.color_codes(mosaique)
        lecture = bk._lecture(mosaique, [0], codes)
        texte = " ".join(lecture[0][1])
        attendu = " · ".join(
            f"{compte}{codes[color.code]}"
            for compte, color, _ in bk.row_runs(mosaique, 0)
        )
        self.assertEqual(texte, attendu)
        # Et pas les noms complets, qui se confondent deux a deux.
        self.assertNotIn("Bluish", texte)


class TestRenduAvancement(unittest.TestCase):
    def setUp(self):
        self.mosaique, self.palette = petite_mosaique()

    def test_trois_etats_distincts(self):
        s = 10
        vue = bk.render_progress(self.mosaique, 4, 5, scale=s, grid=0)
        centre = lambda r, c: vue.pixel(c * s + s // 2, r * s + s // 2)

        # A poser : damier gris, qui n'est la couleur d'aucune tuile.
        self.assertIn(centre(7, 3), (bk.GRIS_FUTUR, bk.GRIS_FUTUR_BIS))
        # En cours : la couleur exacte de la tuile a prendre.
        self.assertEqual(centre(4, 3), self.mosaique.grid[4][3].rgb)
        # Deja pose : la meme teinte, mais palie vers le blanc.
        pose = centre(1, 3)
        vraie = self.mosaique.grid[1][3].rgb
        self.assertEqual(pose, bk._paler(vraie, bk.PALEUR_POSE))
        self.assertTrue(all(p >= v for p, v in zip(pose, vraie)))

    def test_le_reste_a_poser_ne_ressemble_a_aucune_tuile(self):
        # Un gris pali et un gris « vide » se confondent : la ou l'oeuvre est
        # grise, le constructeur ne saurait plus ou il en est. Le damier, lui,
        # n'est la couleur d'aucune tuile — il ne peut pas etre lu de travers.
        s = 10
        vue = bk.render_progress(self.mosaique, 2, 2, scale=s, grid=0)
        voisins = {
            vue.pixel(c * s + s // 2, 6 * s + s // 2)
            for c in range(self.mosaique.studs_x)
        }
        self.assertEqual(voisins, {bk.GRIS_FUTUR, bk.GRIS_FUTUR_BIS})
        # Et il alterne aussi d'une ligne a l'autre.
        self.assertNotEqual(
            vue.pixel(s // 2, 6 * s + s // 2), vue.pixel(s // 2, 7 * s + s // 2)
        )

    def test_bande_hors_mosaique_refusee(self):
        with self.assertRaises(ValueError):
            bk.render_progress(self.mosaique, 0, self.mosaique.studs_y)
        with self.assertRaises(ValueError):
            bk.render_progress(self.mosaique, 3, 2)

    def test_aucune_couleur_inventee_dans_la_bande(self):
        # Invariant du rendu : dans la bande en cours, tout pixel est soit la
        # couleur exacte de sa tuile, soit cette couleur ASSOMBRIE par une
        # reglure. Jamais une teinte etrangere — elle ferait prendre la
        # mauvaise brique. Les traits de delimitation, eux, sont hors bande.
        s = 10
        vue = bk.render_progress(self.mosaique, 4, 5, scale=s, grid=4)
        for row in (4, 5):
            for column in range(self.mosaique.studs_x):
                exacte = self.mosaique.grid[row][column].rgb
                # Zero, une ou deux reglures (leur croisement) : rien d'autre.
                permises = {
                    tuple(round(round(c * 0.65) * 0.65) for c in exacte),
                    tuple(round(c * 0.65) for c in exacte),
                    exacte,
                }
                for dy in range(s):
                    for dx in range(s):
                        pixel = vue.pixel(column * s + dx, row * s + dy)
                        self.assertIn(pixel, permises, (row, column, dx, dy))

    def test_les_traits_de_bande_restent_hors_de_la_bande(self):
        s = 10
        vue = bk.render_progress(self.mosaique, 4, 5, scale=s, grid=0)
        noirs = {
            y
            for y in range(vue.height)
            if vue.pixel(vue.width // 2, y) == (0, 0, 0)
        }
        self.assertTrue(noirs)
        self.assertTrue(all(y < 4 * s or y >= 6 * s for y in noirs), sorted(noirs))

    def test_premiere_bande_ne_deborde_pas(self):
        vue = bk.render_progress(self.mosaique, 0, 1, scale=8, grid=0)
        self.assertEqual(vue.pixel(4, 4), self.mosaique.grid[0][0].rgb)

    def test_couche_de_fond_montre_le_decalage(self):
        tuiles = {
            self.mosaique.tile_id(r, c)
            for r in range(self.mosaique.studs_y)
            for c in range(self.mosaique.studs_x)
        }
        fond = sorted(set(self.mosaique.placed_parts) - tuiles)
        par_z = {}
        for part_id in fond:
            par_z.setdefault(
                self.mosaique.placed_parts[part_id].aabb.min.z, []
            ).append(part_id)
        couches = [par_z[z] for z in sorted(par_z)]
        self.assertEqual(len(couches), 2)
        seule = bk.render_layer(self.mosaique, couches[1], palette=self.palette)
        avec = bk.render_layer(
            self.mosaique, couches[1], couches[0], palette=self.palette
        )
        self.assertEqual((seule.width, seule.height), (avec.width, avec.height))
        # Les joints de la couche du dessous doivent RESTER visibles.
        self.assertNotEqual(seule.data, avec.data)

    def test_couche_vide_refusee(self):
        with self.assertRaises(ValueError):
            bk.render_layer(self.mosaique, [])

    def test_teinte_inconnue_reste_neutre(self):
        # Jamais une valeur inventee : un gris visiblement provisoire.
        self.assertEqual(bk._teinte(9999, self.palette), (160, 160, 160))
        self.assertEqual(bk._teinte(9999, None), (160, 160, 160))
        self.assertEqual(bk._teinte(4, self.palette), self.palette.by_code(4).rgb)


class TestFascicule(unittest.TestCase):
    def test_chaine_complete(self):
        mosaique, palette = petite_mosaique()
        plan = plan_de(mosaique)
        bom = bfk.bill_of_materials(mosaique.instances, mosaique.placed_parts)
        pdf = bk.build_booklet(mosaique, plan, bom, palette=palette, title="Essai")
        objets, pages = disseque(pdf)
        # couverture + liste + deux couches de fond + au moins une bande
        self.assertGreaterEqual(pages, 5)
        self.assertGreater(objets, pages)

    def test_toutes_les_tuiles_recoivent_une_page(self):
        mosaique, palette = petite_mosaique()
        bandes = bk._decouper_bandes(mosaique, 4, bk._mise_en_page(mosaique))
        couvertes = sorted(row for bande in bandes for row in bande)
        self.assertEqual(couvertes, list(range(mosaique.studs_y)))
        self.assertTrue(all(len(b) <= 4 for b in bandes))

    def test_decoupage_toujours_progressif(self):
        mosaique, _ = petite_mosaique()
        bandes = bk._decouper_bandes(mosaique, 4, bk._mise_en_page(mosaique))
        self.assertTrue(all(len(b) >= 1 for b in bandes))
        plat = [row for bande in bandes for row in bande]
        self.assertEqual(plat, sorted(plat))

    def test_ordre_verifie_contre_le_plan(self):
        # Un prerequis relegue apres l'etape qui en depend doit etre refuse :
        # c'est la seule chose que la mise en page n'a pas le droit de casser.
        etapes = (
            bfk.BuildStep("E1", ("a",), (), "fond"),
            bfk.BuildStep("E2", ("b",), ("E1",), "dessus"),
        )
        plan = bfk.InstructionGraph(steps=etapes)
        bk._verifier_ordre(plan, {"a": 3, "b": 4})
        bk._verifier_ordre(plan, {"a": 3, "b": 3})
        with self.assertRaises(ValueError):
            bk._verifier_ordre(plan, {"a": 5, "b": 4})

    def test_la_legende_figure_sur_chaque_page_de_bande(self):
        mosaique, palette = petite_mosaique(cote=16, graine=6)
        mise = bk._mise_en_page(mosaique)
        pages, _ = bk._pages_etapes(mosaique, [[0, 1]], mise)
        for page in pages:
            for color in mise.couleurs:
                self.assertIn(color.rgb, [r[4] for r in page.rects], color.name)
                self.assertIn(
                    mise.codes[color.code], [t[3] for t in page.texts], color.name
                )

    def test_rien_ne_deborde_de_la_page(self):
        mosaique, palette = petite_mosaique(cote=32, graine=9)
        plan = plan_de(mosaique)
        bom = bfk.bill_of_materials(mosaique.instances, mosaique.placed_parts)
        pages = []
        vrai = bk.write_pdf
        try:
            bk.write_pdf = lambda p, **kw: (pages.extend(p), vrai(p, **kw))[1]
            bk.build_booklet(mosaique, plan, bom, palette=palette)
        finally:
            bk.write_pdf = vrai
        self.assertGreater(len(pages), 4)
        # 28 points = 10 mm : la zone qu'une imprimante de bureau ne rend pas.
        # Verifier « dans la page » ne suffit pas — ce qui tombe la est perdu.
        SUR = 28.0
        for numero, page in enumerate(pages, start=1):
            for x, y, corps, texte, _ in page.texts:
                largeur = len(texte) * corps * bk.LARGEUR_CARACTERE
                self.assertGreaterEqual(y, SUR, (numero, texte))
                self.assertLessEqual(y + corps, bk.A4_HEIGHT - SUR, (numero, texte))
                self.assertGreaterEqual(x, SUR, (numero, texte))
                self.assertLessEqual(x + largeur, bk.A4_WIDTH - SUR, (numero, texte))
            for x, y, w, h, _ in page.rects:
                self.assertGreaterEqual(y, SUR, numero)
                self.assertGreaterEqual(x, SUR, numero)
                self.assertLessEqual(x + w, bk.A4_WIDTH - SUR, numero)
                self.assertLessEqual(y + h, bk.A4_HEIGHT - SUR, numero)
            if page.image_rect is not None:
                x, y, w, h = page.image_rect
                self.assertGreaterEqual(x, SUR, numero)
                self.assertGreaterEqual(y, SUR, numero)
                self.assertLessEqual(x + w, bk.A4_WIDTH - SUR, numero)
                self.assertLessEqual(y + h, bk.A4_HEIGHT - SUR, numero)

    def test_une_etape_tient_toujours_sur_une_page(self):
        # L'ancienne notice lisait chaque ligne en clair, et cette lecture
        # pouvait deborder : il fallait des pages de suite. Une image ne
        # deborde pas. Meme la bande la plus haute tient sur une page.
        mosaique, _ = petite_mosaique(cote=24, graine=4)
        for lignes in (1, 4, 8, 12):
            pages, ou = bk._pages_etapes(
                mosaique, [list(range(lignes))], bk._mise_en_page(mosaique))
            self.assertEqual(len(pages), 1, f"{lignes} lignes")
            self.assertEqual(ou, [0])
            # La bande, le reperage, et un dessin par reference de l'encart.
            self.assertGreaterEqual(len(pages[0].images), 2)
            self.assertEqual(pages[0].images[-1][0].width,
                             bk.render_locator(mosaique, 0, lignes - 1).width,
                             "le reperage vient en dernier")

    def test_plusieurs_etapes_par_page_quand_elles_tiennent(self):
        # Une notice LEGO met deux a quatre etapes numerotees par page. Une
        # seule laissait les deux tiers de la feuille blancs.
        mosaique, _ = petite_mosaique(cote=32, graine=6)
        mise = bk._mise_en_page(mosaique)
        bandes = bk._decouper_bandes(mosaique, 4, mise)
        pages, ou = bk._pages_etapes(mosaique, bandes, mise)
        self.assertEqual(len(ou), len(bandes))
        self.assertLess(len(pages), len(bandes),
                        "aucune page ne porte deux etapes")
        # Chaque page porte au moins une bande, et l'ordre est croissant.
        self.assertEqual(ou, sorted(ou))
        self.assertEqual(set(ou), set(range(len(pages))))

    def test_chaque_bande_est_placee_sur_exactement_une_page(self):
        mosaique, _ = petite_mosaique(cote=48, graine=12)
        mise = bk._mise_en_page(mosaique)
        bandes = bk._decouper_bandes(mosaique, 4, mise)
        pages, ou = bk._pages_etapes(mosaique, bandes, mise)
        self.assertEqual(len(ou), len(bandes))
        self.assertTrue(all(0 <= n < len(pages) for n in ou))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestDessinDesPieces(unittest.TestCase):
    """Les pieces dessinees en perspective, comme dans une notice LEGO."""

    ROUGE = (200, 60, 40)

    def test_une_brique_est_plus_haute_qu_une_tuile_de_meme_emprise(self):
        brique = bk.render_piece("3010", self.ROUGE, 8.0)   # Brick 1 x 4
        tuile = bk.render_piece("2431", self.ROUGE, 8.0)    # Tile 1 x 4
        self.assertEqual(brique.width, tuile.width)
        self.assertGreater(brique.height, tuile.height,
                           "24 LDU de corps contre 8 : ca doit se voir")

    def test_les_tenons_se_voient_et_une_tuile_n_en_a_pas(self):
        # `has_studs` vient du catalogue : une tuile n'a pas de tenons parce
        # que le catalogue le dit, pas parce que son nom commence par « Tile ».
        plate = bk.render_piece("3024", self.ROUGE, 12.0)   # Plate 1 x 1
        tuile = bk.render_piece("3070b", self.ROUGE, 12.0)  # Tile 1 x 1
        self.assertGreater(plate.height, tuile.height)
        self.assertNotEqual(plate.data, tuile.data)

    def test_les_trois_faces_ont_trois_eclairements(self):
        # Sans cet ecart, un cube isometrique se lit comme un hexagone plat.
        image = bk.render_piece("3001", self.ROUGE, 14.0)   # Brick 2 x 4
        teintes = {image.pixel(x, y)
                   for y in range(image.height) for x in range(image.width)}
        rouges = sorted({t[0] for t in teintes if t[0] > t[1] > t[2] - 1})
        self.assertGreaterEqual(len(rouges), 3, "trois faces, trois valeurs")

    def test_une_piece_ronde_ne_se_dessine_pas_comme_une_carree(self):
        ronde = bk.render_piece("98138", self.ROUGE, 14.0)
        carree = bk.render_piece("3070b", self.ROUGE, 14.0)
        self.assertNotEqual(ronde.data, carree.data)

    def test_la_couleur_demandee_est_celle_du_dessus(self):
        image = bk.render_piece("3070b", self.ROUGE, 16.0)
        teintes = [image.pixel(x, y)
                   for y in range(image.height) for x in range(image.width)]
        self.assertIn(self.ROUGE, teintes,
                      "la face du dessus porte la couleur telle quelle")

    def test_aucune_piece_du_catalogue_ne_deborde_de_sa_case(self):
        # La borne de largeur seule laissait passer les grandes plates
        # carrees : en isometrie une 8x8 est aussi haute que large.
        from bfk001.catalog import CATALOG
        for design in sorted(CATALOG):
            _, largeur, hauteur = bk._dessin_de_piece(
                design, self.ROUGE, 86.0, (255, 255, 255), hauteur_max=19.0)
            self.assertLessEqual(largeur, 88.0, design)
            self.assertLessEqual(hauteur, 21.0, design)

    def test_l_encart_dessine_une_piece_par_reference(self):
        mosaique, _ = petite_mosaique(cote=16, graine=3)
        mise = bk._mise_en_page(mosaique)
        rects, textes, images, hauteur = bk._encart_pieces(
            mosaique, [0, 1], mise.codes, 40.0, 800.0, 515.0)
        attendues, _ = bk.pieces_of_band(mosaique, [0, 1])
        self.assertEqual(len(images), len(attendues))
        self.assertGreater(hauteur, 20.0)
        for _, (x, y, w, h) in images:
            self.assertGreater(w, 0)
            self.assertGreater(h, 0)


class TestMiseEnPage(unittest.TestCase):
    """Rien ne doit sortir de la page. Personne ne relit un PDF de dix pages.

    Ce controle existe parce qu'il a trouve un vrai defaut : la page du cadre
    ecrivait trois phrases d'un seul tenant, dont une debordait la marge droite
    de 109 points — soit 69 points AU-DELA du bord du papier. La phrase etait
    coupee a l'impression, sur la derniere page de toute notice avec cadre,
    c'est-a-dire par defaut. Aucun test ne regardait la geometrie des pages.

    Il ne verifie pas une page choisie : il verifie une PROPRIETE sur toutes
    les pages de huit fascicules aux reglages differents.
    """

    CONFIGURATIONS = (
        ("cadre par defaut", dict(studs=24, hauteur=24)),
        ("sans cadre", dict(studs=24, hauteur=24, cadre=0)),
        ("cadre epais", dict(studs=24, hauteur=24, cadre=8)),
        ("relief", dict(studs=24, hauteur=24, relief=3)),
        ("tuiles rondes", dict(studs=16, hauteur=16, references="art")),
        ("format allonge", dict(studs=32, hauteur=8)),
        ("minuscule", dict(studs=2, hauteur=2)),
        ("bandes larges", dict(studs=24, hauteur=24, lignes_par_page=8)),
    )

    _CACHE: dict = {}

    def pages_de(self, **reglages):
        """Les pages telles que `build_booklet` les a construites.

        Memorisees par configuration : trois controles portent sur les memes
        huit fascicules, et les rebatir chaque fois triplait le cout de ce
        fichier pour rien.

        On intercepte `write_pdf` plutot que de relire le PDF : ce qu'on veut
        verifier est la GEOMETRIE decidee, et la relire depuis les octets
        n'ajouterait qu'un decodeur a se tromper.
        """
        from bfk001 import booklet
        from bfk001.imaging import Image, write_png
        from bfk001.pipeline import Reglages, run

        pixels = [(int(30 + 200 * x / 96), int(60 + 150 * y / 96),
                   int(200 - 120 * y / 96))
                  for y in range(96) for x in range(96)]
        photo = write_png(Image.from_pixels(96, 96, pixels))

        cle = tuple(sorted(reglages.items()))
        if cle in self._CACHE:
            return self._CACHE[cle]

        capturees = []
        vrai = booklet.write_pdf

        def espion(pages, *args, **kwargs):
            capturees.append(list(pages))
            return vrai(pages, *args, **kwargs)

        booklet.write_pdf = espion
        try:
            run(photo, Reglages(titre="essai", **reglages))
        finally:
            booklet.write_pdf = vrai
        self.assertTrue(capturees)
        self._CACHE[cle] = capturees[0]
        return capturees[0]

    def test_rien_ne_sort_de_la_page(self):
        from bfk001 import booklet as B

        for etiquette, reglages in self.CONFIGURATIONS:
            pages = self.pages_de(**reglages)
            self.assertTrue(pages, etiquette)
            for numero, page in enumerate(pages, start=1):
                ou = f"{etiquette}, page {numero}"
                for x, y, largeur, hauteur, _rvb in page.rects:
                    self.assertGreaterEqual(x, -0.01, ou)
                    self.assertGreaterEqual(y, -0.01, ou)
                    self.assertLessEqual(x + largeur, B.A4_WIDTH + 0.01, ou)
                    self.assertLessEqual(y + hauteur, B.A4_HEIGHT + 0.01, ou)
                for _image, (x, y, largeur, hauteur) in page.images:
                    self.assertGreaterEqual(x, -0.01, ou)
                    self.assertGreaterEqual(y, -0.01, ou)
                    self.assertLessEqual(x + largeur, B.A4_WIDTH + 0.01, ou)
                    self.assertLessEqual(y + hauteur, B.A4_HEIGHT + 0.01, ou)

    def test_aucune_ligne_ne_deborde_les_marges(self):
        from bfk001 import booklet as B

        for etiquette, reglages in self.CONFIGURATIONS:
            for numero, page in enumerate(self.pages_de(**reglages), start=1):
                for x, y, corps, texte, _gras in page.texts:
                    fin = x + len(texte) * corps * B.LARGEUR_CARACTERE
                    self.assertLessEqual(
                        fin, B.A4_WIDTH - B.MARGE + 0.5,
                        f"{etiquette}, page {numero} : « {texte[:50]} » depasse "
                        f"de {fin - (B.A4_WIDTH - B.MARGE):.0f} pt")
                    self.assertGreaterEqual(x, B.MARGE - 0.5, etiquette)
                    self.assertGreater(y, 20.0, f"{etiquette} : « {texte[:40]} »")
                    self.assertLess(y, B.A4_HEIGHT, etiquette)

    def test_deux_images_d_une_meme_page_ne_se_recouvrent_pas(self):
        # Le reperage et la vue de l'etape cohabitent : s'ils se chevauchaient,
        # l'un masquerait l'autre sans qu'aucun test ne s'en apercoive.
        for etiquette, reglages in self.CONFIGURATIONS:
            for numero, page in enumerate(self.pages_de(**reglages), start=1):
                cadres = [cadre for _image, cadre in page.images]
                for i, a in enumerate(cadres):
                    for b in cadres[i + 1:]:
                        recouvre = (a[0] < b[0] + b[2] and b[0] < a[0] + a[2]
                                    and a[1] < b[1] + b[3] and b[1] < a[1] + a[3])
                        self.assertFalse(
                            recouvre, f"{etiquette}, page {numero} : deux "
                            "images se chevauchent")

    def test_le_replieur_de_prose_coupe_aux_espaces(self):
        from bfk001.booklet import _replier

        phrase = "Les briques d'une assise sur l'autre ne tombent pas au meme " \
                 "endroit : c'est ce croisement qui fait un mur."
        lignes = _replier(phrase, 10.5, 515.0)
        self.assertGreater(len(lignes), 1, "une phrase longue doit se replier")
        self.assertEqual(" ".join(lignes), " ".join(phrase.split()),
                         "replier ne perd ni n'ajoute un mot")
        for ligne in lignes:
            self.assertLessEqual(len(ligne) * 10.5 * 0.55, 515.0 + 0.01)
        # Un mot plus long que la ligne sort seul plutot que de disparaitre.
        self.assertEqual(_replier("a" * 300, 9.0, 100.0), ["a" * 300])


class TestLaNoticeDitVrai(unittest.TestCase):
    """La mise en page etait verifiee, son CONTENU ne l'etait pas.

    Une notice peut tenir dans ses marges et raconter n'importe quoi. Ces
    controles portent sur la seule promesse qui compte : si on la suit, on
    obtient le modele — chaque piece une fois, la bonne, au bon endroit.
    """

    CONFIGURATIONS = (
        ("48 tenons", dict(studs=48, hauteur=48)),
        ("relief", dict(studs=32, hauteur=32, relief=3)),
        ("sans cadre", dict(studs=24, hauteur=24, cadre=0)),
        ("tuiles larges", dict(studs=16, hauteur=16, references="large")),
        ("tuiles rondes", dict(studs=16, hauteur=16, references="art")),
        ("en sections", dict(studs=32, hauteur=32, sections=16)),
        ("palette bridee", dict(studs=24, hauteur=24, couleurs="6")),
    )

    _CACHE: dict = {}

    def fabriquer(self, **reglages):
        """Le plan et les bandes REELLEMENT employes par la chaine."""
        from bfk001 import booklet, instructions, pipeline
        from bfk001.imaging import Image, write_png
        from bfk001.pipeline import Reglages, run

        cle = tuple(sorted(reglages.items()))
        if cle in self._CACHE:
            return self._CACHE[cle]

        photo = write_png(Image.from_pixels(160, 160, [
            (int(30 + 200 * x / 160), int(70 + 150 * y / 160), (x * y) % 251)
            for y in range(160) for x in range(160)]))

        vus = {}
        vrai_plan = instructions.plan_build
        vraies_bandes = booklet._decouper_bandes

        def espion_plan(placed, graph, instances, par_etape):
            plan = vrai_plan(placed, graph, instances, par_etape)
            vus.setdefault("plan", (plan, placed))
            return plan

        def espion_bandes(mosaique, lignes, mise):
            bandes = vraies_bandes(mosaique, lignes, mise)
            vus.setdefault("bandes", (mosaique, bandes, mise))
            return bandes

        pipeline.instructions.plan_build = espion_plan
        booklet._decouper_bandes = espion_bandes
        try:
            run(photo, Reglages(titre="essai", **reglages))
        finally:
            pipeline.instructions.plan_build = vrai_plan
            booklet._decouper_bandes = vraies_bandes
        self._CACHE[cle] = vus
        return vus

    def test_suivre_toutes_les_etapes_pose_exactement_le_modele(self):
        """Une piece oubliee, et le modele ne tient pas. Une piece en double,
        et on en achete une de trop puis on cherche ou la mettre."""
        for etiquette, reglages in self.CONFIGURATIONS:
            plan, placees = self.fabriquer(**reglages)["plan"]
            posees = [p for etape in plan.steps for p in etape.part_ids]
            self.assertEqual(len(posees), len(set(posees)),
                             f"{etiquette} : une piece posee deux fois")
            self.assertEqual(set(posees), set(placees),
                             f"{etiquette} : le plan et le modele different")

    def test_les_bandes_couvrent_chaque_rangee_une_fois(self):
        # Une rangee absente, et une bande entiere de l'oeuvre n'est montree
        # nulle part. Une rangee en double, et on la pose deux fois.
        for etiquette, reglages in self.CONFIGURATIONS:
            mosaique, bandes, _ = self.fabriquer(**reglages)["bandes"]
            rangs = [r for bande in bandes for r in bande]
            self.assertEqual(len(rangs), len(set(rangs)),
                             f"{etiquette} : rangee citee deux fois")
            self.assertEqual(set(rangs), set(range(mosaique.studs_y)),
                             f"{etiquette} : rangees manquantes")

    def test_chaque_couleur_employee_a_sa_lettre_et_elle_est_unique(self):
        """Sans lettre, la notice imprime « ? ». Deux couleurs qui partagent
        une lettre, et on pose la mauvaise sans jamais s'en apercevoir."""
        for etiquette, reglages in self.CONFIGURATIONS:
            mosaique, _, mise = self.fabriquer(**reglages)["bandes"]
            employees = {pose.color.code for pose in mosaique.tiles}
            self.assertFalse(employees - set(mise.codes),
                             f"{etiquette} : couleur sans lettre")
            lettres = [mise.codes[code] for code in employees]
            self.assertEqual(len(lettres), len(set(lettres)),
                             f"{etiquette} : deux couleurs, une lettre")

    def test_l_encart_de_chaque_bande_annonce_ce_qu_elle_contient(self):
        """« Ce qu'il faut sortir du sachet » doit etre exact a la piece.

        Les pieces se lisent dans les tuiles REELLEMENT posees : depuis la
        fusion, quatre tenons rouges peuvent etre une seule 1x4, et faire
        prendre quatre 1x1 serait une consigne fausse.
        """
        import collections

        from bfk001.booklet import pieces_of_band

        for etiquette, reglages in self.CONFIGURATIONS:
            mosaique, bandes, _ = self.fabriquer(**reglages)["bandes"]
            total = 0
            for numero, bande in enumerate(bandes):
                annonce = collections.Counter()
                for design, couleur, quantite in pieces_of_band(mosaique, bande)[0]:
                    annonce[(design, couleur.code)] += quantite
                attendu = collections.Counter()
                for pose in mosaique.tiles:
                    if bande[0] <= pose.row <= bande[-1]:
                        attendu[(pose.design_id, pose.color.code)] += 1
                self.assertEqual(annonce, attendu,
                                 f"{etiquette}, bande {numero}")
                total += sum(annonce.values())
            # Et la somme de tous les encarts, c'est toute l'oeuvre.
            self.assertEqual(total, len(mosaique.tiles), etiquette)
