"""Colorimetrie : la grandeur qu'on moyenne, et la metrique qui tranche.

Deux erreurs systematiques ont ete trouvees ici, et ni l'une ni l'autre ne se
voyait dans un test de structure. Les tests ci-dessous les verrouillent.
"""

import math
import random
import inspect
import unittest

import bfk001 as bfk
from bfk001.palette import _delta_e2000_lab, delta_e2000, delta_e76, srgb_to_lab


def lumiere(canal: int) -> float:
    """sRGB -> lumiere lineaire. Reimplementee ici, exprès : un test qui
    appelle la fonction testee ne teste rien."""
    u = canal / 255
    return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4


class TestMoyenneEnLumiere(unittest.TestCase):
    def test_le_damier_rend_la_moitie_de_la_lumiere(self):
        # Cas d'ecole a reponse connue : moitie noir, moitie blanc renvoie
        # exactement 50 % de la lumiere. sRGB 127 n'en renvoie que 21 %.
        damier = bytearray()
        for y in range(16):
            for x in range(16):
                v = 255 if (x + y) % 2 else 0
                damier += bytes((v, v, v))
        obtenu = bfk.resample_box(bfk.Image(16, 16, bytes(damier)), 1, 1).pixel(0, 0)
        self.assertEqual(obtenu, (188, 188, 188))
        self.assertAlmostEqual(lumiere(obtenu[0]), 0.5, delta=0.005)

    def test_propriete_generale_sur_des_paires_quelconques(self):
        rnd = random.Random(31)
        for _ in range(60):
            a, b = rnd.randrange(256), rnd.randrange(256)
            paire = bfk.Image(2, 1, bytes((a, a, a, b, b, b)))
            obtenu = bfk.resample_box(paire, 1, 1).pixel(0, 0)[0]
            attendu = (lumiere(a) + lumiere(b)) / 2
            self.assertLess(abs(lumiere(obtenu) - attendu), 0.004, (a, b, obtenu))

    def test_une_couleur_uniforme_est_rendue_telle_quelle(self):
        # Le passage par la lumiere ne doit rien deplacer quand il n'y a rien
        # a moyenner : c'est la condition pour que la correction soit sure.
        rnd = random.Random(5)
        for _ in range(40):
            rgb = tuple(rnd.randrange(256) for _ in range(3))
            uni = bfk.Image(4, 4, bytes(rgb) * 16)
            self.assertEqual(bfk.resample_box(uni, 2, 2).pixel(0, 0), rgb)

    def test_la_mesure_de_fidelite_moyenne_aussi_en_lumiere(self):
        # Mesurer sur la mauvaise grandeur, c'est ne pas mesurer la bonne chose.
        from bfk001.mosaic import _average

        self.assertEqual(_average([(0, 0, 0), (255, 255, 255)], 2), (188, 188, 188))
        self.assertEqual(_average([(120, 30, 200)], 1), (120, 30, 200))


class TestCadrage(unittest.TestCase):
    def cercle(self, largeur, hauteur, rayon=100):
        """Un cercle PARFAIT : s'il ressort ovale, la chaine deforme."""
        cx, cy = largeur // 2, hauteur // 2
        pixels = bytearray()
        for y in range(hauteur):
            for x in range(largeur):
                dedans = (x - cx) ** 2 + (y - cy) ** 2 < rayon ** 2
                pixels += bytes((220, 40, 30) if dedans else (245, 245, 245))
        return bfk.Image(largeur, hauteur, bytes(pixels))

    def rapport_du_cercle(self, grille):
        cases = [
            (x, y)
            for y, ligne in enumerate(grille)
            for x, couleur in enumerate(ligne)
            if couleur.code in (4, 320)
        ]
        largeur = max(x for x, _ in cases) - min(x for x, _ in cases) + 1
        hauteur = max(y for _, y in cases) - min(y for _, y in cases) + 1
        return largeur / hauteur

    def test_une_photo_4_3_dans_un_carre_n_est_pas_ecrasee(self):
        # LE defaut : presque toute photo est en 4:3 ou 3:2, presque toute
        # mosaique LEGO Art est carree. Etirer ecrasait tout d'un quart.
        photo = self.cercle(400, 300)
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        rogne = bfk.mosaic.quantize(photo, palette, 48, 48, dither=False)
        etire = bfk.mosaic.quantize(photo, palette, 48, 48, dither=False, fit="stretch")
        self.assertAlmostEqual(self.rapport_du_cercle(rogne), 1.0, delta=0.08)
        self.assertLess(self.rapport_du_cercle(etire), 0.85)

    def test_le_portrait_aussi(self):
        photo = self.cercle(300, 400)
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        grille = bfk.mosaic.quantize(photo, palette, 48, 48, dither=False)
        self.assertAlmostEqual(self.rapport_du_cercle(grille), 1.0, delta=0.08)

    def test_la_decoupe_refuse_de_deborder_en_silence(self):
        image = bfk.Image(10, 10, bytes(300))
        for args in ((-1, 0, 5, 5), (0, 0, 11, 5), (6, 6, 5, 5), (0, 0, 0, 5)):
            with self.assertRaises(ValueError, msg=args):
                bfk.crop(image, *args)

    def test_la_fenetre_de_cadrage_se_deplace(self):
        # Le sujet n'est pas toujours au centre, et rien ici ne sait ou il est.
        gauche = bytes((255, 0, 0)) * 20 + bytes((0, 0, 255)) * 20
        image = bfk.Image(40, 10, gauche * 10)
        self.assertEqual(bfk.crop_to_ratio(image, 1.0, 0.0).pixel(0, 0), (255, 0, 0))
        self.assertEqual(bfk.crop_to_ratio(image, 1.0, 1.0).pixel(9, 0), (0, 0, 255))
        for mauvais in (-0.1, 1.1):
            with self.assertRaises(ValueError):
                bfk.crop_to_ratio(image, 1.0, mauvais)

    def test_une_image_deja_au_bon_rapport_est_intacte(self):
        motif = bytes((i % 256) for i in range(24 * 24 * 3))
        image = bfk.Image(24, 24, motif)
        self.assertEqual(bfk.crop_to_ratio(image, 1.0), image)

    def test_fit_inconnu_refuse(self):
        with self.assertRaises(ValueError):
            bfk.mosaic.quantize(
                bfk.Image(8, 8, bytes(192)), bfk.PROVISIONAL_PALETTE, 4, 4, fit="zoom"
            )


class TestMetriquePerceptive(unittest.TestCase):
    def test_proprietes_de_ciede2000(self):
        rnd = random.Random(4)
        couleurs = [tuple(rnd.randrange(256) for _ in range(3)) for _ in range(40)]
        for rgb in couleurs:
            self.assertEqual(delta_e2000(rgb, rgb), 0.0)
        for a, b in zip(couleurs, couleurs[1:]):
            self.assertAlmostEqual(delta_e2000(a, b), delta_e2000(b, a), places=12)

    def test_croissance_le_long_d_un_segment(self):
        # Une distance perceptive doit croitre quand on s'eloigne.
        depart, arrivee = (20, 40, 60), (200, 180, 90)
        precedent = -1.0
        for pas in range(21):
            milieu = tuple(
                round(depart[i] + (arrivee[i] - depart[i]) * pas / 20) for i in range(3)
            )
            valeur = delta_e2000(depart, milieu)
            self.assertGreaterEqual(valeur + 1e-9, precedent)
            precedent = valeur

    def test_gris_voisins_proches_de_cie76(self):
        # Sur l'axe neutre, CIEDE2000 ne corrige que la luminosite (SL) : il
        # doit rester du meme ordre que CIE76, jamais s'en ecarter d'un facteur.
        for niveau in range(40, 220, 20):
            a, b = (niveau,) * 3, (niveau + 3,) * 3
            rapport = delta_e2000(a, b) / delta_e76(a, b)
            self.assertGreater(rapport, 0.6)
            self.assertLess(rapport, 1.1)

    def test_le_bleu_n_est_plus_rendu_par_un_violet(self):
        # LE defaut qui a motive le changement. #005AB4 et #0055BF sont
        # quasiment la meme couleur ; CIE76 preferait pourtant Violet #4354A3,
        # de 0,68 delta E. C'est la distorsion connue de la region bleue de
        # L*a*b*, et le terme de rotation de CIEDE2000 est centre dessus.
        bleu = bfk.LegoColor(1, "Blue", (0x00, 0x55, 0xBF))
        violet = bfk.LegoColor(2, "Violet", (0x43, 0x54, 0xA3))
        palette = bfk.Palette((bleu, violet))
        cible = (0x00, 0x5A, 0xB4)

        self.assertLess(delta_e76(cible, violet.rgb), delta_e76(cible, bleu.rgb))
        self.assertLess(delta_e2000(cible, bleu.rgb), delta_e2000(cible, violet.rgb))
        self.assertIs(palette.nearest(cible), bleu)

    def test_nearest_est_bien_le_minimum_de_la_metrique(self):
        rnd = random.Random(8)
        palette = bfk.PROVISIONAL_PALETTE
        for _ in range(40):
            rgb = tuple(rnd.randrange(256) for _ in range(3))
            choisie = palette.nearest(rgb)
            meilleur = min(delta_e2000(rgb, c.rgb) for c in palette)
            self.assertAlmostEqual(delta_e2000(rgb, choisie.rgb), meilleur, places=12)

    def test_le_cache_lab_ne_change_pas_les_resultats(self):
        from bfk001 import palette as module

        palette = bfk.PROVISIONAL_PALETTE
        rgb = (77, 133, 199)
        module._CACHE_LAB.clear()
        premier = palette.nearest(rgb)
        second = palette.nearest(rgb)   # cette fois depuis le cache
        self.assertIs(premier, second)
        self.assertEqual(module._CACHE_LAB[rgb], srgb_to_lab(rgb))

    def test_version_lab_et_version_rgb_concordent(self):
        rnd = random.Random(12)
        for _ in range(30):
            a = tuple(rnd.randrange(256) for _ in range(3))
            b = tuple(rnd.randrange(256) for _ in range(3))
            self.assertAlmostEqual(
                delta_e2000(a, b),
                _delta_e2000_lab(srgb_to_lab(a), srgb_to_lab(b)),
                places=12,
            )

    def test_delta_e_designe_la_metrique_qui_tranche(self):
        self.assertIs(bfk.delta_e, delta_e2000)


class TestDiffusionEnSerpentin(unittest.TestCase):
    def test_le_serpentin_alterne_bien_le_sens(self):
        # Floyd-Steinberg toujours parcouru dans le meme sens produit des
        # vermicules diagonaux, visibles a l'echelle de la tuile. On verifie
        # que l'erreur part bien a GAUCHE sur les rangs impairs.
        palette = bfk.Palette((
            bfk.LegoColor(15, "White", (255, 255, 255)),
            bfk.LegoColor(0, "Black", (0, 0, 0)),
        ))
        # Un gris moyen : chaque tuile pousse la moitie de son erreur au voisin.
        gris = bfk.Image(32, 32, bytes((110, 110, 110)) * (32 * 32))
        grille = bfk.mosaic.quantize(gris, palette, 8, 8, dither=True)
        codes = [[c.code for c in ligne] for ligne in grille]
        # Le motif ne doit pas etre identique d'un rang a l'autre : c'est la
        # signature du serpentin, et l'inverse est celle des vermicules.
        self.assertNotEqual(codes[1], codes[2])
        # Et il reste equilibre : la moitie environ de chaque teinte.
        blancs = sum(c == 15 for ligne in codes for c in ligne)
        self.assertGreater(blancs, 8)
        self.assertLess(blancs, 56)

    def test_le_tramage_preserve_la_lumiere_moyenne(self):
        # C'est la raison d'etre de la diffusion d'erreur, et c'est ce que
        # mesure le critere tonal : ce que le direct ne sait pas faire.
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        rnd = random.Random(3)
        pixels = bytearray()
        for y in range(96):
            for x in range(96):
                t = (x + y) / 192
                pixels += bytes((int(40 + 150 * t), int(80 + 120 * t), int(160 + 60 * t)))
        degrade = bfk.Image(96, 96, bytes(pixels))
        direct = bfk.mosaic.quantize(degrade, palette, 32, 32, dither=False)
        trame = bfk.mosaic.quantize(degrade, palette, 32, 32, dither="adaptive")
        self.assertLess(
            bfk.mosaic.fidelity(trame, degrade, 4)[0],
            bfk.mosaic.fidelity(direct, degrade, 4)[0],
        )

    def test_le_plafond_de_force_borne_le_grain_invente(self):
        # Le grain invente : la variation d'une tuile a sa voisine QUE LA PHOTO
        # NE CONTIENT PAS. C'est la seule chose que le tramage puisse abimer,
        # et c'est ce que le plafond borne.
        from bfk001.mosaic import (
            DITHER_MAX_STRENGTH,
            _quantization_error_strength,
        )

        self.assertLessEqual(DITHER_MAX_STRENGTH, 1.0)
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        # Une couleur tres loin de la palette : la force serait saturee a 1.
        loin = bfk.Image(64, 64, bytes((128, 150, 120)) * (64 * 64))
        reduite = bfk.resample_box(loin, 16, 16)
        force = _quantization_error_strength(reduite, palette, 16, 16)
        maxi = max(v for ligne in force for v in ligne)
        self.assertGreater(maxi, 0.0)
        self.assertLessEqual(maxi, DITHER_MAX_STRENGTH + 1e-9)

    def test_le_grain_reste_sous_celui_du_tramage_plein(self):
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        pixels = bytearray()
        for y in range(96):
            for x in range(96):
                t = (x + y) / 192
                pixels += bytes((int(40 + 150 * t), int(90 + 110 * t), int(150 + 70 * t)))
        degrade = bfk.Image(96, 96, bytes(pixels))

        def variation(grille):
            cote = len(grille)
            total = compte = 0.0
            for y in range(cote):
                for x in range(cote):
                    for dx, dy in ((1, 0), (0, 1)):
                        nx, ny = x + dx, y + dy
                        if nx < cote and ny < cote:
                            total += delta_e2000(grille[y][x].rgb, grille[ny][nx].rgb)
                            compte += 1
            return total / compte

        adaptatif = variation(bfk.mosaic.quantize(degrade, palette, 32, 32, "adaptive"))
        plein = variation(bfk.mosaic.quantize(degrade, palette, 32, 32, True))
        direct = variation(bfk.mosaic.quantize(degrade, palette, 32, 32, False))
        self.assertLess(direct, adaptatif)
        self.assertLess(adaptatif, plein)

    def test_le_defaut_est_l_adaptatif(self):
        palette = bfk.PROVISIONAL_PALETTE
        image = bfk.Image(32, 32, bytes((90, 120, 95)) * (32 * 32))
        self.assertEqual(
            bfk.mosaic.quantize(image, palette, 8, 8),
            bfk.mosaic.quantize(image, palette, 8, 8, dither="adaptive"),
        )


class TestSelectionDeSousPalette(unittest.TestCase):
    def pixels_riches(self, cote=32):
        pixels = []
        for y in range(cote):
            for x in range(cote):
                pixels.append((
                    int(20 + 235 * x / cote),
                    int(20 + 235 * y / cote),
                    int(120 + 100 * ((x + y) / (2 * cote))),
                ))
        return pixels

    def test_le_minimum_courant_donne_le_meme_resultat_que_le_recalcul(self):
        # L'optimisation est EXACTE, pas approchee :
        #   cout(R + [c]) = somme_i part_i * min(min_{r dans R} d(i,r), d(i,c))
        # Ajouter une couleur ne peut que rapprocher une grappe. On le verifie
        # plutot que de le croire.
        from bfk001.palette import _delta_e2000_lab, dominant_colors, srgb_to_lab

        pixels = self.pixels_riches()
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        clusters = dominant_colors(pixels, min(96, max(16, 6 * 3)))
        labs = [(srgb_to_lab(c), part) for c, part in clusters]

        naif: list = []
        restantes = list(palette)
        while len(naif) < 6:
            elue = min(
                restantes,
                key=lambda cand: sum(
                    part * min(
                        _delta_e2000_lab(lab, srgb_to_lab(c.rgb))
                        for c in naif + [cand]
                    )
                    for lab, part in labs
                ),
            )
            naif.append(elue)
            restantes.remove(elue)

        rapide = list(palette.best_subset(pixels, 6))
        self.assertEqual([c.code for c in rapide], [c.code for c in naif])

    def test_un_budget_plus_grand_rapproche_de_la_palette_entiere(self):
        # Le proxy etait plafonne a 24 grappes, et ce plafond bridait tout :
        # N=32 ne gagnait rien sur N=24, parce que le proxy ne savait plus
        # distinguer. Le nombre de grappes suit desormais le budget.
        pixels = self.pixels_riches(48)
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        complete = sum(
            delta_e2000(p, palette.nearest(p).rgb) for p in pixels
        ) / len(pixels)
        precedent = None
        for budget in (3, 6, 9):
            sous = palette.best_subset(pixels, budget)
            self.assertEqual(len(sous), budget)
            ecart = sum(delta_e2000(p, sous.nearest(p).rgb) for p in pixels) / len(pixels)
            self.assertGreaterEqual(ecart + 1e-9, complete)
            if precedent is not None:
                self.assertLessEqual(ecart, precedent + 1e-9)
            precedent = ecart

    def test_budget_egal_ou_superieur_rend_la_palette_entiere(self):
        palette = bfk.PROVISIONAL_PALETTE
        pixels = self.pixels_riches(16)
        self.assertIs(palette.best_subset(pixels, len(palette)), palette)
        self.assertIs(palette.best_subset(pixels, len(palette) + 5), palette)
        with self.assertRaises(ValueError):
            palette.best_subset(pixels, 0)


class TestPaletteOfficielle(unittest.TestCase):
    def test_recherche_ne_rend_que_des_fichiers_lisibles(self):
        self.assertIsNone(bfk.find_ldconfig(["/n/existe/pas/LDConfig.ldr"]))

    def test_repli_annonce_ce_qu_il_est(self):
        # Une palette silencieusement degradee est pire qu'une palette absente.
        palette, provenance = bfk.load_best_palette(["/n/existe/pas.ldr"])
        if provenance.startswith("provisoire"):
            self.assertEqual(len(palette), len(bfk.PROVISIONAL_PALETTE))
        else:  # pragma: no cover - une machine ou LDraw est installe
            self.assertGreater(len(palette), 100)

    def test_lecture_d_un_ldconfig_minimal(self):
        texte = "\n".join([
            "0 LDraw.org Configuration File",
            "0 !COLOUR Blue CODE 1 VALUE #0055BF EDGE #333333",
            "0 !COLOUR Trans_Red CODE 36 VALUE #C91A09 EDGE #333 ALPHA 128",
        ])
        palette = bfk.load_ldconfig(texte)
        self.assertEqual(len(palette), 2)
        self.assertEqual(len(palette.solids_only()), 1)
        self.assertEqual(palette.by_code(1).rgb, (0x00, 0x55, 0xBF))


if __name__ == "__main__":
    unittest.main(verbosity=2)


def codes(grille):
    """Grille -> codes couleur. Comparer des LegoColor rend un echec illisible."""
    return tuple(tuple(c.code for c in ligne) for ligne in grille)


class TestTramageAutomatique(unittest.TestCase):
    """Le tramage n'a pas de bon reglage universel : il en faut un par image."""

    def scene(self, f, cote=192):
        return bfk.Image(
            cote, cote,
            bytes(
                max(0, min(255, c))
                for y in range(cote)
                for x in range(cote)
                for c in f(x / cote, y / cote)
            ),
        )

    def palette(self):
        return bfk.PROVISIONAL_PALETTE.solids_only()

    def test_un_aplat_sur_la_palette_n_est_jamais_trame(self):
        # Rien a gagner : la couleur voulue existe deja. Tramer ne ferait
        # qu'ajouter du grain sur une zone deja juste.
        rouge = self.palette().nearest((200, 30, 25)).rgb
        photo = self.scene(lambda u, v: rouge)
        self.assertEqual(
            codes(bfk.mosaic.quantize(photo, self.palette(), 16, 16, "auto")),
            codes(bfk.mosaic.quantize(photo, self.palette(), 16, 16, False)),
        )

    def test_le_tramage_se_declenche_bien_quelque_part(self):
        # Sans ce test, une regle trop severe rendrait le tramage inerte sans
        # que rien ne le signale. Sur un jeu de scenes variees, au moins une
        # doit le declencher — et quand il se declenche, le pire ecart tonal
        # doit s'ameliorer, sinon la regle ne fait pas ce qu'elle annonce.
        scenes = [
            lambda u, v: (int(120 + 60 * v), int(150 + 55 * v), 228),
            lambda u, v: (int(30 + 200 * u), int(40 + 120 * v), int(200 - 90 * u)),
            lambda u, v: (int(230 - 90 * v), int(120 + 90 * u), 60),
        ]
        declenches = 0
        for f in scenes:
            photo = self.scene(f)
            auto = codes(bfk.mosaic.quantize(photo, self.palette(), 32, 32, "auto"))
            sans = codes(bfk.mosaic.quantize(photo, self.palette(), 32, 32, False))
            if auto != sans:
                declenches += 1
                self.assertLess(
                    bfk.mosaic.fidelity(
                        bfk.mosaic.quantize(photo, self.palette(), 32, 32, "auto"),
                        photo, 4)[1],
                    bfk.mosaic.fidelity(
                        bfk.mosaic.quantize(photo, self.palette(), 32, 32, False),
                        photo, 4)[1],
                )
        self.assertGreater(declenches, 0, "le tramage automatique ne se declenche jamais")

    def test_le_choix_suit_exactement_le_critere_annonce(self):
        # Le critere est le PIRE ecart tonal, avec une marge d'un delta E.
        for f in (
            lambda u, v: (int(120 + 60 * v), int(150 + 55 * v), 228),
            lambda u, v: (200, 30, 25) if u < 0.5 else (25, 120, 60),
            lambda u, v: (int(230 - 60 * v), int(190 - 50 * v), int(160 - 40 * v)),
        ):
            photo = self.scene(f)
            sans = bfk.mosaic.quantize(photo, self.palette(), 32, 32, False)
            avec = bfk.mosaic.quantize(photo, self.palette(), 32, 32, "adaptive")
            auto = bfk.mosaic.quantize(photo, self.palette(), 32, 32, "auto")
            gain = (bfk.mosaic.fidelity(sans, photo, 4)[1]
                    - bfk.mosaic.fidelity(avec, photo, 4)[1])
            attendu = avec if gain >= bfk.mosaic.DITHER_AUTO_MIN_GAIN else sans
            self.assertEqual(codes(auto), codes(attendu), f"gain {gain:.2f}")

    def test_auto_est_le_defaut(self):
        self.assertEqual(
            inspect.signature(bfk.mosaic.quantize).parameters["dither"].default,
            "auto",
        )
        self.assertEqual(
            inspect.signature(bfk.mosaic.build).parameters["dither"].default
            if "dither" in inspect.signature(bfk.mosaic.build).parameters
            else "auto",
            "auto",
        )

    def test_valeur_inconnue_refusee(self):
        photo = self.scene(lambda u, v: (10, 20, 30))
        with self.assertRaises(ValueError):
            bfk.mosaic.quantize(photo, self.palette(), 8, 8, "flou")


class TestRechercheExacteEtElaguee(unittest.TestCase):
    """`nearest` n'evalue pas toute la palette — et rend pourtant l'exact."""

    def palettes(self):
        return [
            bfk.PROVISIONAL_PALETTE,
            bfk.PROVISIONAL_PALETTE.solids_only(),
            bfk.Palette([
                bfk.LegoColor(i, f"C{i}", (i * 9 % 256, i * 31 % 256, i * 57 % 256))
                for i in range(1, 60)
            ]),
        ]

    def force_brute(self, palette, rgb):
        from bfk001.palette import _delta_e2000_lab, srgb_to_lab

        cible = srgb_to_lab(rgb)
        return min(
            palette, key=lambda c: (_delta_e2000_lab(srgb_to_lab(c.rgb), cible), c.code)
        )

    def test_identique_a_la_force_brute(self):
        rnd = random.Random(23)
        for palette in self.palettes():
            for _ in range(400):
                rgb = tuple(rnd.randrange(256) for _ in range(3))
                attendu = self.force_brute(palette, rgb)
                obtenu = palette.nearest(rgb)
                self.assertAlmostEqual(
                    bfk.delta_e2000(rgb, obtenu.rgb),
                    bfk.delta_e2000(rgb, attendu.rgb),
                    places=9,
                    msg=f"{rgb} -> {obtenu.name} au lieu de {attendu.name}",
                )

    def test_les_extremes_aussi(self):
        # Les bornes de clarte sont la ou la coupure risque de deborder.
        for palette in self.palettes():
            for rgb in ((0, 0, 0), (255, 255, 255), (0, 0, 255), (255, 0, 0),
                        (1, 1, 1), (254, 254, 254), (0, 255, 0)):
                attendu = self.force_brute(palette, rgb)
                self.assertAlmostEqual(
                    bfk.delta_e2000(rgb, palette.nearest(rgb).rgb),
                    bfk.delta_e2000(rgb, attendu.rgb),
                    places=9,
                    msg=f"{rgb}",
                )

    def test_la_borne_de_coupure_est_valide(self):
        # dE2000 >= |dL| / SL_MAX. Si cette inegalite tombait, la coupure
        # ecarterait la bonne couleur en silence.
        from bfk001.palette import _SL_MAX, _delta_e2000_lab, srgb_to_lab

        rnd = random.Random(24)
        for _ in range(3000):
            a = srgb_to_lab(tuple(rnd.randrange(256) for _ in range(3)))
            b = srgb_to_lab(tuple(rnd.randrange(256) for _ in range(3)))
            self.assertGreaterEqual(
                _delta_e2000_lab(a, b) + 1e-9, abs(a[0] - b[0]) / _SL_MAX, (a, b)
            )

    def test_le_cache_ne_change_pas_la_reponse(self):
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        rnd = random.Random(25)
        cibles = [tuple(rnd.randrange(256) for _ in range(3)) for _ in range(200)]
        premier = [palette.nearest(rgb).code for rgb in cibles]
        second = [palette.nearest(rgb).code for rgb in cibles]
        self.assertEqual(premier, second)
        neuve = bfk.Palette(palette.colors)
        self.assertEqual(premier, [neuve.nearest(rgb).code for rgb in cibles])
