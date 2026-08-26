"""Colorimetrie : la grandeur qu'on moyenne, et la metrique qui tranche.

Deux erreurs systematiques ont ete trouvees ici, et ni l'une ni l'autre ne se
voyait dans un test de structure. Les tests ci-dessous les verrouillent.
"""

import math
import random
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
