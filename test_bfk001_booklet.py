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
                bk.PdfPage(((40.0, 700.0, 12.0, "Page une", True),), (), image,
                           (40.0, 400.0, 200.0, 150.0)),
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
            bk.PdfPage((), (), image, None)
        with self.assertRaises(ValueError):
            bk.PdfPage((), (), None, (0.0, 0.0, 1.0, 1.0))

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
                        (), image, (0.0, 0.0, 10.0, 10.0))]
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


class TestSuitesDeCouleur(unittest.TestCase):
    def test_regroupement(self):
        rouge = bfk.LegoColor(4, "Red", (200, 0, 0))
        noir = bfk.LegoColor(0, "Black", (0, 0, 0))
        runs = bk.row_runs([rouge, rouge, noir, rouge])
        self.assertEqual([(n, c.name) for n, c in runs],
                         [(2, "Red"), (1, "Black"), (1, "Red")])

    def test_regroupement_par_code_et_non_par_identite(self):
        # Deux instances egales sont la meme brique : les separer ferait
        # recompter le constructeur pour rien.
        a = bfk.LegoColor(4, "Red", (200, 0, 0))
        b = bfk.LegoColor(4, "Red", (200, 0, 0))
        self.assertIsNot(a, b)
        self.assertEqual(bk.row_runs([a, b, a]), ((3, a),))

    def test_somme_conservee(self):
        mosaique, _ = petite_mosaique()
        for ligne in mosaique.grid:
            self.assertEqual(sum(n for n, _ in bk.row_runs(ligne)), len(ligne))


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
        bandes = bk._decouper_bandes(mosaique, 4)
        couvertes = sorted(row for bande in bandes for row in bande)
        self.assertEqual(couvertes, list(range(mosaique.studs_y)))
        self.assertTrue(all(len(b) <= 4 for b in bandes))

    def test_decoupage_toujours_progressif(self):
        mosaique, _ = petite_mosaique()
        bandes = bk._decouper_bandes(mosaique, 4)
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
        for numero, page in enumerate(pages, start=1):
            for x, y, corps, texte, _ in page.texts:
                largeur = len(texte) * corps * bk.LARGEUR_CARACTERE
                self.assertGreaterEqual(y, 20.0, (numero, texte))
                self.assertLessEqual(y + corps, bk.A4_HEIGHT - 20.0, (numero, texte))
                self.assertGreaterEqual(x, 10.0, (numero, texte))
                self.assertLessEqual(x + largeur, bk.A4_WIDTH - 10.0, (numero, texte))
            if page.image_rect is not None:
                x, y, w, h = page.image_rect
                self.assertGreaterEqual(x, 0.0)
                self.assertGreaterEqual(y, 0.0)
                self.assertLessEqual(x + w, bk.A4_WIDTH)
                self.assertLessEqual(y + h, bk.A4_HEIGHT)

    def test_lecture_trop_longue_passe_en_page_de_suite(self):
        # Plutot que de tronquer — c'est-a-dire de perdre des tuiles.
        mosaique, _ = petite_mosaique(cote=24, graine=4)
        minimum = bk.IMAGE_MIN
        try:
            bk.IMAGE_MIN = 640.0  # etrangle la place laissee a la lecture
            pages = bk._pages_bande(mosaique, list(range(8)), 1, 1)
        finally:
            bk.IMAGE_MIN = minimum
        self.assertGreater(len(pages), 1)
        self.assertIsNotNone(pages[0].image)
        self.assertTrue(all(p.image is None for p in pages[1:]))

    def test_bande_par_defaut_tient_sur_une_page(self):
        mosaique, _ = petite_mosaique(cote=48, graine=12)
        for bande in bk._decouper_bandes(mosaique, 4):
            self.assertEqual(len(bk._pages_bande(mosaique, bande, 1, 1)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
