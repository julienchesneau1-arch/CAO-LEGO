"""Export LDraw : le fichier produit doit decrire EXACTEMENT le meme modele.

Le registre notait cet export comme delibérement absent : ecrire un exporteur
sans les vraies origines de pieces produit des fichiers faux, et rien ne le
signale — le fichier s'ouvre, il est simplement faux. D'ou ce test, qui relit
le fichier et reconstruit les empreintes pour les comparer a celles du noyau.
"""

import random
import unittest

import bfk001 as bfk
from bfk001.catalog import CATALOG
from bfk001.ldraw import dumps_ldr, part_origin_offset, to_ldraw_point
from bfk001.lego import STUD_PITCH_LDU
from bfk001.rotations import ROT_Z_90, all_rotations


def relire(texte):
    """Fichier LDraw -> {reference : AABB reconstruite, en axes du NOYAU}.

    Reconstruction independante de l'ecriture : on repart de la boite locale de
    la piece en axes LDraw, on applique la matrice et la translation lues dans
    le fichier, puis on revient aux axes du noyau.
    """
    boites = {}
    for index, ligne in enumerate(texte.splitlines()):
        morceaux = ligne.split()
        if not morceaux or morceaux[0] != "1":
            continue
        x, y, z = (int(v) for v in morceaux[2:5])
        matrice = [int(v) for v in morceaux[5:14]]
        design = morceaux[14][:-4]
        piece = CATALOG[design]

        demi_x = piece.studs_x * STUD_PITCH_LDU // 2
        demi_z = piece.studs_y * STUD_PITCH_LDU // 2
        haut = -4 if piece.has_studs else 0   # les tenons depassent vers -y
        coins = [
            (sx * demi_x, sy, sz * demi_z)
            for sx in (-1, 1)
            for sy in (haut, piece.body_height_ldu)
            for sz in (-1, 1)
        ]
        monde = []
        for cx, cy, cz in coins:
            monde.append((
                x + matrice[0] * cx + matrice[1] * cy + matrice[2] * cz,
                y + matrice[3] * cx + matrice[4] * cy + matrice[5] * cz,
                z + matrice[6] * cx + matrice[7] * cy + matrice[8] * cz,
            ))
        # Retour aux axes du noyau : inverse de (x, -z, y).
        noyau = [(mx, mz, -my) for mx, my, mz in monde]
        boites[index] = (
            min(p[0] for p in noyau), min(p[1] for p in noyau),
            min(p[2] for p in noyau), max(p[0] for p in noyau),
            max(p[1] for p in noyau), max(p[2] for p in noyau),
        )
    return boites


class TestConventions(unittest.TestCase):
    def test_le_changement_d_axes_est_une_rotation(self):
        # Determinant -1 = reflexion : la mosaique sortirait en miroir, un
        # visage inverse, un texte a l'envers, et rien ne le signalerait.
        colonnes = [to_ldraw_point(*b) for b in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
        (a, b, c), (d, e, f), (g, h, i) = zip(*colonnes)
        self.assertEqual(
            a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g), 1
        )

    def test_l_origine_est_celle_lue_dans_3001(self):
        # Corps de 3001.dat : x de -40 a 40, z de -20 a 20, y de 0 a 24.
        # Donc centre de l'empreinte, face superieure du corps.
        self.assertEqual(part_origin_offset("3001"), (20, 40, 24))
        self.assertEqual(part_origin_offset("3070b"), (10, 10, 8))
        self.assertEqual(part_origin_offset("2431"), (10, 40, 8))

    def test_toutes_les_rotations_donnent_une_matrice_entiere_propre(self):
        from bfk001.ldraw import _matrice_ldraw

        for orientation in all_rotations():
            matrice = _matrice_ldraw(orientation)
            self.assertEqual(len(matrice), 9)
            self.assertTrue(all(v in (-1, 0, 1) for v in matrice), matrice)
            a, b, c, d, e, f, g, h, i = matrice
            det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
            self.assertEqual(det, 1, matrice)


class TestAllerRetour(unittest.TestCase):
    def mosaique(self, cote=12, graine=5):
        random.seed(graine)
        pixels = bytes(random.randrange(256) for _ in range(cote * cote * 3))
        return bfk.mosaic.from_image(
            bfk.Image(cote, cote, pixels),
            bfk.PROVISIONAL_PALETTE.solids_only(),
            cote, cote,
        )

    def test_le_fichier_decrit_le_meme_modele(self):
        # LE test : si l'origine ou les axes etaient faux, les empreintes
        # relues ne tomberaient pas sur celles que le noyau a calculees.
        mosaique = self.mosaique()
        texte = dumps_ldr(mosaique.placed_parts, mosaique.instances)
        relues = sorted(relire(texte).values())
        attendues = sorted(
            (p.aabb.min.x, p.aabb.min.y, p.aabb.min.z,
             p.aabb.max.x, p.aabb.max.y, p.aabb.max.z)
            for p in mosaique.placed_parts.values()
        )
        self.assertEqual(len(relues), len(attendues))
        self.assertEqual(relues, attendues)

    def test_les_pieces_tournees_aussi(self):
        mosaique = self.mosaique(cote=16, graine=9)
        identite = bfk.Orientation.identity()
        tournees = [
            p for p in mosaique.placed_parts.values() if p.pose[1] != identite
        ]
        self.assertTrue(tournees, "sans piece tournee, ce test ne verifie rien")
        relues = relire(dumps_ldr(mosaique.placed_parts, mosaique.instances))
        self.assertEqual(len(relues), mosaique.part_count)
        attendues = {
            (p.aabb.min.x, p.aabb.min.y, p.aabb.min.z,
             p.aabb.max.x, p.aabb.max.y, p.aabb.max.z)
            for p in mosaique.placed_parts.values()
        }
        self.assertEqual(set(relues.values()), attendues)

    def test_toutes_les_rotations_survivent_a_l_aller_retour(self):
        from bfk001.catalog import place_at

        for design in ("3001", "3020", "3070b", "2431"):
            for orientation in all_rotations():
                placed, _, instance = place_at(
                    "p", design, (60, 40, 20), orientation=orientation, color_id=4
                )
                texte = dumps_ldr({"p": placed}, {"p": instance})
                (relu,) = relire(texte).values()
                self.assertEqual(
                    relu,
                    (placed.aabb.min.x, placed.aabb.min.y, placed.aabb.min.z,
                     placed.aabb.max.x, placed.aabb.max.y, placed.aabb.max.z),
                    f"{design} sous {orientation}",
                )

    def test_les_couleurs_sont_celles_du_modele(self):
        mosaique = self.mosaique()
        texte = dumps_ldr(mosaique.placed_parts, mosaique.instances)
        codes = {
            int(l.split()[1]) for l in texte.splitlines() if l.startswith("1 ")
        }
        self.assertEqual(codes, {i.color_id for i in mosaique.instances.values()})

    def test_une_piece_sans_identite_est_refusee(self):
        mosaique = self.mosaique()
        partielles = dict(mosaique.instances)
        partielles.pop(next(iter(partielles)))
        with self.assertRaises(KeyError):
            dumps_ldr(mosaique.placed_parts, partielles)

    def test_l_entete_dit_de_quoi_depend_la_justesse(self):
        mosaique = self.mosaique()
        entete = dumps_ldr(mosaique.placed_parts, mosaique.instances).splitlines()[:8]
        texte = " ".join(entete)
        self.assertIn("Axes", texte)
        self.assertIn("3001.dat", texte)


if __name__ == "__main__":
    unittest.main(verbosity=2)
