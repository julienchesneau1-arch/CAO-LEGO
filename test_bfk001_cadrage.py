"""Recadrage attentionnel : mieux qu'un centrage aveugle, pas un regard.

Ce fichier teste aussi ce que l'heuristique NE fait PAS. Un critere qu'on ne
sait pas mettre en defaut est un critere qu'on n'a pas compris.
"""

import unittest

import bfk001 as bfk
from bfk001.imaging import attentional_offset, crop_to_ratio, detail_profile


def portrait_haut(w=300, h=500, tete_y=90, rayon=70):
    """Sujet detaille haut dans le cadre, fond uni : le cas qui decapite."""
    data = bytearray()
    for y in range(h):
        for x in range(w):
            if (x - w // 2) ** 2 + (y - tete_y) ** 2 < rayon ** 2:
                data += bytes((235, 195, 165) if (x + y) % 2 else (215, 175, 145))
            elif y > h * 0.76:
                data += bytes((70, 90, 120))
            else:
                data += bytes((150, 170, 205))
    return bfk.Image(w, h, bytes(data))


def uni(w, h, couleur=(120, 130, 140)):
    return bfk.Image(w, h, bytes(couleur) * (w * h))


class TestProfilDeDetail(unittest.TestCase):
    def test_un_aplat_n_a_aucun_detail(self):
        for axe in ("x", "y"):
            self.assertEqual(set(detail_profile(uni(80, 60), axe)), {0.0})

    def test_une_zone_texturee_porte_plus_de_detail_qu_un_aplat(self):
        image = portrait_haut()
        profil = detail_profile(image, "y")
        bandes = len(profil)
        # La tete occupe y de 20 a 160 sur 500 : le premier tiers.
        tete = sum(profil[: bandes // 3])
        milieu = sum(profil[bandes // 3 : 2 * bandes // 3])
        self.assertGreater(tete, milieu * 5, (tete, milieu))

    def test_un_bord_franc_ne_dicte_pas_le_cadrage(self):
        # Le PIC par bande tombe sur l'arete sol/ciel : un seul rang, gradient
        # enorme. C'est exact, et ce serait un mauvais critere de cadrage — une
        # ligne d'horizon n'est pas un sujet. La fenetre INTEGREE, elle, suit la
        # zone texturee, parce qu'un damier contribue sur des dizaines de rangs
        # la ou une arete ne contribue que sur un. C'est pour ca que
        # `attentional_offset` somme au lieu de chercher un maximum.
        image = portrait_haut()
        profil = detail_profile(image, "y")
        pic = max(range(len(profil)), key=lambda i: profil[i])
        self.assertGreater(pic / len(profil), 0.6, "le pic est bien sur l'arete")
        self.assertLess(
            attentional_offset(image, 1.0), 0.3,
            "et pourtant la fenetre retenue est celle de la tete",
        )

    def test_axe_inconnu_refuse(self):
        with self.assertRaises(ValueError):
            detail_profile(uni(10, 10), "z")


class TestDecalageAttentionnel(unittest.TestCase):
    def test_il_garde_la_tete_que_le_centrage_coupe(self):
        # LE cas qui justifie la fonction.
        image = portrait_haut()
        cote = image.width
        aveugle = round((image.height - cote) * 0.5)
        auto = round((image.height - cote) * attentional_offset(image, 1.0))
        self.assertGreater(aveugle, 20, "le centrage doit bien couper la tete")
        self.assertLessEqual(auto, 20, "l'automatique doit la garder entiere")
        self.assertGreaterEqual(auto + cote, 160)

    def test_il_reste_dans_les_bornes(self):
        for ratio in (0.4, 0.75, 1.0, 1.6, 3.0):
            for image in (portrait_haut(), portrait_haut(500, 300, 60, 50)):
                decalage = attentional_offset(image, ratio)
                self.assertGreaterEqual(decalage, 0.0)
                self.assertLessEqual(decalage, 1.0)

    def test_sur_un_aplat_il_recentre(self):
        # Quand la mesure ne dit rien, on ne s'ecarte pas du comportement
        # precedent : le centre. Une heuristique muette doit rester neutre.
        self.assertAlmostEqual(attentional_offset(uni(300, 500), 1.0), 0.5, places=2)
        self.assertAlmostEqual(attentional_offset(uni(500, 300), 1.0), 0.5, places=2)

    def test_une_image_deja_au_bon_rapport_ne_bouge_pas(self):
        self.assertEqual(attentional_offset(portrait_haut(400, 400), 1.0), 0.5)

    def test_rapport_invalide_refuse(self):
        with self.assertRaises(ValueError):
            attentional_offset(uni(10, 10), 0.0)

    def test_ce_qu_il_ne_sait_pas_faire(self):
        # Le critere mesure du DETAIL, pas un sujet. Un fond tres texture
        # derriere un visage lisse l'attire vers le fond — c'est une limite
        # reelle, pas un bug, et elle est ecrite dans la docstring.
        w, h = 300, 500
        data = bytearray()
        for y in range(h):
            for x in range(w):
                if (x - 150) ** 2 + (y - 90) ** 2 < 4900:
                    data += bytes((220, 180, 150))          # visage LISSE, haut
                elif y > 350:
                    data += bytes((30, 90, 30) if (x * y) % 3 else (200, 220, 80))
                else:
                    data += bytes((150, 170, 205))
        piege = bfk.Image(w, h, bytes(data))
        self.assertGreater(
            attentional_offset(piege, 1.0), 0.5,
            "le critere suit le detail : ici il descend vers le feuillage",
        )


class TestIntegrationCadrage(unittest.TestCase):
    def test_auto_traverse_la_chaine(self):
        image = portrait_haut()
        decoupee = crop_to_ratio(image, 1.0, "auto")
        self.assertEqual(decoupee.width, decoupee.height)
        self.assertEqual(decoupee.width, image.width)

    def test_auto_et_valeur_donnent_le_meme_type_de_resultat(self):
        image = portrait_haut()
        auto = crop_to_ratio(image, 1.0, "auto")
        fixe = crop_to_ratio(image, 1.0, attentional_offset(image, 1.0))
        self.assertEqual(auto.data, fixe.data)

    def test_une_valeur_absurde_est_refusee(self):
        image = portrait_haut()
        for mauvais in (-0.1, 1.5, "milieu", None, True):
            with self.assertRaises(ValueError, msg=repr(mauvais)):
                crop_to_ratio(image, 1.0, mauvais)

    def test_la_mosaique_accepte_auto(self):
        image = portrait_haut(120, 200)
        mosaique = bfk.mosaic.from_image(
            image, bfk.PROVISIONAL_PALETTE.solids_only(), 16, 16,
            fit="crop", offset="auto",
        )
        self.assertEqual(mosaique.stud_count, 256)


if __name__ == "__main__":
    unittest.main(verbosity=2)
