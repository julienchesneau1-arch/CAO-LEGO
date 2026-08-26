"""Fusion des tuiles : moins de pieces, exactement le meme rendu.

Une tuile 1x4 rouge montre les memes quatre tenons rouges que quatre tuiles
1x1. La fusion ne coute donc AUCUNE fidelite — c'est ce que ce fichier
verifie d'abord, parce que c'est la seule chose qui pourrait la disqualifier.
"""

import random
import unittest
from collections import Counter

import bfk001 as bfk
from bfk001.catalog import CATALOG, place_at
from bfk001.lego import STUD_PITCH_LDU
from bfk001.mosaic import (
    TILE_SET_LARGE,
    TILE_SET_MINIMAL,
    TILE_SET_STANDARD,
    _decoupe_optimale,
    _fusionner_ligne,
)
from bfk001.rotations import ROT_Z_90


def grille_test(cote=24, graine=4):
    random.seed(graine)
    pixels = bytes(random.randrange(256) for _ in range(cote * cote * 3))
    return bfk.mosaic.quantize(
        bfk.Image(cote, cote, pixels),
        bfk.PROVISIONAL_PALETTE.solids_only(),
        cote,
        cote,
    )


def grille_structuree(cote=32):
    """Aplats et degrades — ce que contient une vraie photo, contrairement au
    bruit uniforme ou aucune suite ne depasse deux tenons."""
    data = bytearray()
    for y in range(cote * 4):
        for x in range(cote * 4):
            if y < cote * 2:
                data += bytes((60, 90, 200))            # ciel
            elif (x - cote * 2) ** 2 + (y - cote * 3) ** 2 < (cote) ** 2:
                data += bytes((200, 40, 30))            # disque
            else:
                data += bytes((40, 110, 60))            # sol
    return bfk.mosaic.quantize(
        bfk.Image(cote * 4, cote * 4, bytes(data)),
        bfk.PROVISIONAL_PALETTE.solids_only(),
        cote,
        cote,
    )


class TestDecoupeOptimale(unittest.TestCase):
    def test_couvre_exactement(self):
        for dispo in ([1], [1, 2], [1, 2, 4], [1, 2, 3, 4], [1, 2, 3, 4, 6, 8]):
            for longueur in range(1, 40):
                morceaux = _decoupe_optimale(longueur, dispo)
                self.assertEqual(sum(morceaux), longueur, (dispo, longueur))
                self.assertTrue(all(m in dispo for m in morceaux))

    def test_est_bien_le_minimum(self):
        # Comparaison a une recherche exhaustive : la DP doit l'egaler.
        def minimum_force_brute(longueur, dispo, memo={}):
            cle = (longueur, tuple(dispo))
            if cle in memo:
                return memo[cle]
            if longueur == 0:
                return 0
            meilleur = min(
                (minimum_force_brute(longueur - t, dispo) + 1
                 for t in dispo if t <= longueur),
                default=float("inf"),
            )
            memo[cle] = meilleur
            return meilleur

        for dispo in ([1, 2, 4], [1, 3, 4], [1, 2, 3, 4, 6, 8]):
            for longueur in range(1, 25):
                self.assertEqual(
                    len(_decoupe_optimale(longueur, dispo)),
                    minimum_force_brute(longueur, dispo),
                    (dispo, longueur),
                )

    def test_le_glouton_naif_serait_battu(self):
        # Justification de la DP : avec 1, 3 et 4, un run de 6 se decoupe en
        # 3+3 et non en 4+1+1. Prendre la plus longue d'abord coute une piece.
        self.assertEqual(sorted(_decoupe_optimale(6, [4, 3, 1])), [3, 3])


class TestFusionDUneLigne(unittest.TestCase):
    def test_ne_fusionne_jamais_deux_couleurs(self):
        grille = grille_test()
        for ligne in grille:
            colonne = 0
            for depart, longueur, couleur in _fusionner_ligne(ligne, [4, 2, 1]):
                self.assertEqual(depart, colonne)
                for decalage in range(longueur):
                    self.assertEqual(ligne[colonne + decalage].code, couleur.code)
                colonne += longueur
            self.assertEqual(colonne, len(ligne))

    def test_moins_de_pieces_avec_des_tuiles_plus_longues(self):
        grille = grille_test()
        comptes = [
            sum(len(_fusionner_ligne(l, dispo)) for l in grille)
            for dispo in ([1], [2, 1], [4, 2, 1], [8, 6, 4, 3, 2, 1])
        ]
        self.assertEqual(comptes, sorted(comptes, reverse=True), comptes)


class TestPlacementAuCoin(unittest.TestCase):
    def test_le_coin_vise_est_le_coin_obtenu(self):
        # `place` translate l'ORIGINE ; sous rotation l'origine n'est plus le
        # coin, et une tuile tournee atterrit a cote. `place_at` vise le coin.
        for design, rotation, empreinte in (
            ("3070b", None, (20, 20)),
            ("3069b", ROT_Z_90, (40, 20)),
            ("2431", ROT_Z_90, (80, 20)),
            ("2431", None, (20, 80)),
            ("3020", ROT_Z_90, (80, 40)),
        ):
            piece, _, _ = place_at("t", design, (140, 60, 16), orientation=rotation)
            self.assertEqual(
                (piece.aabb.min.x, piece.aabb.min.y, piece.aabb.min.z),
                (140, 60, 16),
                design,
            )
            self.assertEqual(
                (piece.aabb.max.x - piece.aabb.min.x,
                 piece.aabb.max.y - piece.aabb.min.y),
                empreinte,
                design,
            )


class TestMosaiqueFusionnee(unittest.TestCase):
    def test_aucune_couleur_ne_change(self):
        # Ce que la fusion ne touche pas : chaque tenon garde sa couleur.
        grille = grille_test()
        reference = bfk.mosaic.build(grille, tiles=TILE_SET_MINIMAL)
        for jeu in (TILE_SET_STANDARD, TILE_SET_LARGE):
            fusionnee = bfk.mosaic.build(grille, tiles=jeu)
            self.assertEqual(fusionnee.grid, reference.grid)
            self.assertEqual(
                bfk.mosaic.preview(fusionnee, 4).data,
                bfk.mosaic.preview(reference, 4).data,
            )

    def test_mais_la_surface_change_et_ce_test_le_dit(self):
        # Ce que la fusion touche, et que ce depot a d'abord nie : les JOINTS.
        # Une 1x4 n'a pas de joint interne la ou quatre 1x1 en ont trois. Le
        # resultat n'est plus la grille reguliere des sets LEGO Art officiels,
        # c'est un appareil a joints decales. Affirmer « rendu identique »
        # etait faux ; l'apercu a joints le montre.
        grille = grille_test()
        reference = bfk.mosaic.build(grille, tiles=TILE_SET_MINIMAL)
        fusionnee = bfk.mosaic.build(grille, tiles=TILE_SET_STANDARD)
        self.assertNotEqual(
            bfk.mosaic.preview(fusionnee, 8, seams=True).data,
            bfk.mosaic.preview(reference, 8, seams=True).data,
        )
        # Et le jeu minimal, lui, rend bien la grille uniforme : chaque tuile
        # y fait un tenon, donc chaque tenon porte son propre contour.
        self.assertTrue(all(pose.length == 1 for pose in reference.tiles))

    def test_les_joints_n_apparaissent_qu_a_la_demande(self):
        grille = grille_test()
        mosaique = bfk.mosaic.build(grille, tiles=TILE_SET_STANDARD)
        self.assertNotEqual(
            bfk.mosaic.preview(mosaique, 8).data,
            bfk.mosaic.preview(mosaique, 8, seams=True).data,
        )

    def test_les_tuiles_couvrent_la_grille_exactement(self):
        grille = grille_test()
        for jeu in (TILE_SET_MINIMAL, TILE_SET_STANDARD, TILE_SET_LARGE):
            mosaique = bfk.mosaic.build(grille, tiles=jeu)
            couvert = Counter()
            for pose in mosaique.tiles:
                for decalage in range(pose.length):
                    couvert[(pose.row, pose.column + decalage)] += 1
                    self.assertEqual(
                        mosaique.grid[pose.row][pose.column + decalage].code,
                        pose.color.code,
                    )
            self.assertEqual(len(couvert), mosaique.stud_count)
            self.assertEqual(set(couvert.values()), {1})

    def test_le_gain_depend_de_l_image_et_jamais_negatif(self):
        # Le gain n'est pas une propriete du code mais de l'IMAGE. Sur du bruit
        # pur il n'y a aucune suite a fusionner et le gain est presque nul ;
        # sur une image structuree il est massif. Les deux sont verifies, et
        # dans les deux cas la fusion ne cree jamais de piece en plus.
        for grille, plafond, etiquette in (
            (grille_test(cote=32, graine=6), 1.00, "bruit"),
            (grille_structuree(32), 0.45, "image structuree"),
        ):
            minimale = bfk.mosaic.build(grille, tiles=TILE_SET_MINIMAL)
            standard = bfk.mosaic.build(grille, tiles=TILE_SET_STANDARD)
            self.assertEqual(minimale.stud_count, standard.stud_count, etiquette)
            self.assertEqual(minimale.tile_count, minimale.stud_count, etiquette)
            self.assertLessEqual(
                standard.tile_count, minimale.tile_count * plafond, etiquette
            )

    def test_la_nomenclature_couvre_tous_les_tenons(self):
        grille = grille_test()
        mosaique = bfk.mosaic.build(grille, tiles=TILE_SET_STANDARD)
        lignes = bfk.bill_of_materials(mosaique.instances, mosaique.placed_parts)
        tenons = sum(
            ligne.quantity * CATALOG[ligne.design_id].studs_y
            for ligne in lignes
            if not CATALOG[ligne.design_id].has_studs
        )
        self.assertEqual(tenons, mosaique.stud_count)

    def test_le_modele_fusionne_passe_les_six_invariants(self):
        for cote, jeu in ((13, TILE_SET_STANDARD), (16, TILE_SET_LARGE)):
            mosaique = bfk.mosaic.build(grille_test(cote, cote), tiles=jeu)
            etat = bfk.assemble(
                mosaique.placed_parts,
                bfk.LEGO_TOLERANCE,
                search=bfk.LatticeSearchApproximation(),
            )
            violations = (
                bfk.check_h2_collision(mosaique.placed_parts, mosaique.geometries)
                + bfk.check_h3_authority_integrity(etat.graph)
                + bfk.check_h4_floating(
                    etat.graph,
                    bfk.founded_part_ids(mosaique.placed_parts, mosaique.geometries),
                )
                + bfk.check_h5_disconnected(etat.graph)
                + bfk.check_h6_foundation(mosaique.placed_parts, mosaique.geometries)
            )
            self.assertEqual(
                [(v.invariant, v.detail) for v in violations], [], f"{cote}x{cote}"
            )

    def test_une_reference_a_tenons_est_refusee(self):
        # Une mosaique se termine par une surface plate : une plate a tenons
        # ferait un rendu granuleux, et la fusion ne se fait qu'en ligne.
        grille = grille_test(cote=8)
        with self.assertRaises(ValueError):
            bfk.mosaic.build(grille, tiles=("3070b", "3023"))
        with self.assertRaises(ValueError):
            bfk.mosaic.build(grille, tiles=("3070b", "3068b"))

    def test_sans_la_1x1_c_est_refuse(self):
        with self.assertRaises(ValueError):
            bfk.mosaic.build(grille_test(cote=8), tiles=("3069b", "2431"))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestCoutDeLaPalette(unittest.TestCase):
    """Combien coute vraiment chaque sachet qu'on ajoute, et qu'achete-t-il."""

    def image(self):
        return bfk.Image(
            64, 64,
            bytes(
                v
                for y in range(64)
                for x in range(64)
                for v in ((40, 90, 200) if y < 32
                          else (200, 50, 40) if (x - 32) ** 2 + (y - 48) ** 2 < 200
                          else (50, 120, 60))
            ),
        )

    def test_la_courbe_est_monotone_sur_le_proxy(self):
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        reduite = bfk.resample_box(self.image(), 16, 16)
        pixels = [reduite.pixel(x, y) for y in range(16) for x in range(16)]
        ecarts = [ecart for _, ecart in palette.subset_curve(pixels, 8)]
        self.assertEqual(ecarts, sorted(ecarts, reverse=True), ecarts)

    def test_la_palette_rendue_est_bien_le_prefixe_mesure(self):
        # `best_subset` fait varier son nombre de grappes avec `count` : sa
        # reponse pour N n'est PAS le prefixe de la courbe. Choisir N sur la
        # courbe puis rappeler best_subset livrerait une autre palette que
        # celle qu'on vient de mesurer.
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        reduite = bfk.resample_box(self.image(), 16, 16)
        pixels = [reduite.pixel(x, y) for y in range(16) for x in range(16)]
        courbe = palette.subset_curve(pixels, 8)
        choisie = palette.cheapest_subset(pixels, 0.5, 8)
        self.assertEqual(
            [c.code for c in choisie],
            [c.code for c, _ in courbe[: len(choisie)]],
        )

    def test_le_cout_mesure_porte_sur_la_mosaique_reelle(self):
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        courbe = bfk.mosaic.palette_cost_curve(self.image(), palette, 16, 16, maximum=6)
        self.assertEqual([len(c.palette) for c in courbe], list(range(1, 7)))
        for cout in courbe:
            self.assertGreater(cout.tiles, 0)
            self.assertGreater(cout.lots, 0)
            self.assertGreaterEqual(cout.tonal_worst, cout.tonal_mean)
        # Une couleur unique ne peut pas battre six couleurs sur le ton.
        self.assertGreater(courbe[0].tonal_mean, courbe[-1].tonal_mean)

    def test_la_palette_entiere_est_candidate(self):
        # Elle etait absente, et sur un portrait elle se trouve etre a la fois
        # la plus fidele ET la moins chere en pieces : reduire la palette
        # elargit les ecarts, ce qui declenche le tramage, ce qui brise les
        # suites de meme couleur, ce qui multiplie les pieces. Une fonction qui
        # promet le meilleur cout ne peut pas ignorer ce candidat-la.
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        _, _, reference = bfk.mosaic.cheapest_palette(
            self.image(), palette, 16, 16, tolerance=0.0, maximum=4
        )
        self.assertEqual(len(reference.palette), len(palette))

    def test_le_critere_est_le_cout_pas_la_taille_de_palette(self):
        # Une palette plus petite n'est pas moins chere par definition. Le
        # retenu doit etre le moins cher des admissibles, pas le plus petit.
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        image = self.image()
        courbe = list(bfk.mosaic.palette_cost_curve(image, palette, 16, 16, maximum=6))
        retenu_palette, retenu, reference = bfk.mosaic.cheapest_palette(
            image, palette, 16, 16, tolerance=1.0, maximum=6
        )
        admissibles = [
            c for c in courbe + [reference]
            if c.per_tile <= reference.per_tile + 1.0
            and c.tonal_mean <= reference.tonal_mean + 1.0
        ]
        self.assertEqual(
            (retenu.tiles, retenu.lots),
            min((c.tiles, c.lots) for c in admissibles),
        )

    def test_le_choix_economique_dit_ce_qu_il_abandonne(self):
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        _, retenu, reference = bfk.mosaic.cheapest_palette(
            self.image(), palette, 16, 16, tolerance=0.5, maximum=6
        )
        # Le contrat : ni l'ecart par tuile ni la justesse tonale ne se
        # degradent de plus que la tolerance, et le cout ne monte pas.
        self.assertLessEqual(retenu.per_tile, reference.per_tile + 0.5 + 1e-9)
        self.assertLessEqual(retenu.tonal_mean, reference.tonal_mean + 0.5 + 1e-9)
        self.assertLessEqual((retenu.tiles, retenu.lots),
                             (reference.tiles, reference.lots))

    def test_une_tolerance_plus_large_ne_coute_jamais_plus_cher(self):
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        couts = [
            bfk.mosaic.cheapest_palette(
                self.image(), palette, 16, 16, tolerance=t, maximum=6)[1]
            for t in (0.0, 1.0, 8.0)
        ]
        pieces = [c.tiles for c in couts]
        self.assertEqual(pieces, sorted(pieces, reverse=True), pieces)

    def test_tolerance_negative_refusee(self):
        with self.assertRaises(ValueError):
            bfk.mosaic.cheapest_palette(
                self.image(), bfk.PROVISIONAL_PALETTE, 8, 8, tolerance=-1
            )


class TestCoutSansConstruire(unittest.TestCase):
    """Compter les pieces sans batir le modele — et compter juste."""

    def grilles(self):
        for cote, graine in ((16, 3), (24, 7), (31, 11)):
            yield bfk.mosaic.quantize(
                bfk.Image(
                    cote, cote,
                    bytes(random.Random(graine).randrange(256)
                          for _ in range(cote * cote * 3)),
                ),
                bfk.PROVISIONAL_PALETTE.solids_only(),
                cote, cote,
            )

    def test_identique_au_modele_reellement_construit(self):
        # Si ces deux comptes divergeaient, la courbe de cout choisirait la
        # palette sur des chiffres que le modele livre ne confirme pas.
        for grille in self.grilles():
            for jeu in (TILE_SET_MINIMAL, TILE_SET_STANDARD, TILE_SET_LARGE):
                modele = bfk.mosaic.build(grille, tiles=jeu)
                tuiles = set(modele.tile_ids)
                lots = {
                    (modele.instances[t].design_id, modele.instances[t].color_id)
                    for t in tuiles
                }
                self.assertEqual(
                    bfk.mosaic.cost_of_grid(grille, jeu),
                    (modele.tile_count, len(lots)),
                    (len(grille), len(jeu)),
                )

    def test_le_substrat_en_est_exclu_et_c_est_voulu(self):
        # Il ne depend pas de la palette, donc il ne discrimine aucune
        # candidate : le compter quinze fois serait quinze fois inutile.
        grille = next(iter(self.grilles()))
        pieces, _ = bfk.mosaic.cost_of_grid(grille)
        modele = bfk.mosaic.build(grille)
        self.assertEqual(pieces, modele.tile_count)
        self.assertLess(pieces, modele.part_count)

    def test_un_jeu_invalide_est_refuse_ici_aussi(self):
        grille = next(iter(self.grilles()))
        with self.assertRaises(ValueError):
            bfk.mosaic.cost_of_grid(grille, ("3070b", "3023"))
        with self.assertRaises(ValueError):
            bfk.mosaic.cost_of_grid(grille, ("2431",))
