"""Le fond de la mosaique : emprise exacte, et il tient.

Un fond qui deborde laisse un lisere de plate grise nue autour de l'oeuvre.
Un fond qui ne tient pas n'est pas un objet. Les deux se verifient ici sur
tout le domaine praticable, parce que la construction n'en donne pas de preuve.
"""

import random
import unittest
from collections import Counter, defaultdict, deque

import bfk001 as bfk
from bfk001.catalog import CATALOG
from bfk001.lego import STUD_PITCH_LDU
from bfk001.mosaic import _decouper_axe, _paver, _plaques


def pave(ancre_x, ancre_y, studs_x, studs_y):
    """Rectangles (en tenons) poses par _paver, sans passer par le noyau."""
    poses = []
    _paver(
        lambda part_id, design, translation, color: poses.append(
            (design, translation[0] // STUD_PITCH_LDU, translation[1] // STUD_PITCH_LDU)
        ),
        "X", ancre_x, ancre_y, studs_x, studs_y, 0, 71,
    )
    rectangles = []
    for design, x, y in poses:
        piece = CATALOG[design]
        rectangles.append((x, y, x + piece.studs_x, y + piece.studs_y))
    return rectangles


def recouvre_exactement(rectangles, studs_x, studs_y):
    """Chaque tenon de l'emprise couvert une fois, et rien au-dela."""
    compte = Counter()
    for x0, y0, x1, y1 in rectangles:
        if x0 < 0 or y0 < 0 or x1 > studs_x or y1 > studs_y:
            return False
        for y in range(y0, y1):
            for x in range(x0, x1):
                compte[(x, y)] += 1
    return len(compte) == studs_x * studs_y and set(compte.values()) == {1}


def fond_connexe(bas, haut):
    """Deux couches liees des qu'elles se recouvrent d'au moins un tenon.

    C'est ce que H5 constate, sans construire le modele : deux plates cote a
    cote dans la meme couche ne se lient pas, seul le recouvrement lie.
    """
    voisins = defaultdict(set)
    for i, (ax0, ay0, ax1, ay1) in enumerate(bas):
        for j, (bx0, by0, bx1, by1) in enumerate(haut):
            if ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1:
                voisins[("b", i)].add(("h", j))
                voisins[("h", j)].add(("b", i))
    noeuds = [("b", i) for i in range(len(bas))] + [("h", j) for j in range(len(haut))]
    vus, file = set(), deque(noeuds[:1])
    while file:
        noeud = file.popleft()
        if noeud in vus:
            continue
        vus.add(noeud)
        file.extend(voisins[noeud] - vus)
    return len(vus) == len(noeuds)


class TestPavage(unittest.TestCase):
    def test_reseau_nu_jamais_fusionne(self):
        # Fusionner un reste d'un tenon replacerait les plates sur la phase de
        # la couche du dessous, et le fond se scinderait en colonnes.
        self.assertEqual(_decouper_axe(0, 4, 13), [(0, 4), (4, 8), (8, 12), (12, 13)])
        self.assertEqual(_decouper_axe(-2, 4, 13), [(0, 2), (2, 6), (6, 10), (10, 13)])
        self.assertEqual(_decouper_axe(-1, 2, 6), [(0, 1), (1, 3), (3, 5), (5, 6)])

    def test_decoupe_couvre_exactement(self):
        for largeur in (1, 2):
            for profondeur in range(1, 6):
                for depart in range(4):
                    aire = sum(
                        CATALOG[d].studs_x * CATALOG[d].studs_y
                        for d, _, _ in _plaques(largeur, profondeur, depart)
                    )
                    self.assertEqual(aire, largeur * profondeur,
                                     (largeur, profondeur, depart))

    def test_colonne_etroite_phasee_pour_enjamber(self):
        # Une 1x2 n'enjambe un joint du dessous (multiples de 4) que si elle
        # commence sur un tenon impair. Depart pair => une 1x1 re-phase.
        depart_pair = _plaques(1, 4, 2)
        self.assertEqual(depart_pair[0][0], "3024")
        debuts = [2 + dy for _, _, dy in depart_pair[1:]]
        self.assertTrue(any(d % 2 for d in debuts), debuts)
        depart_impair = _plaques(1, 4, 3)
        self.assertEqual(depart_impair[0][0], "3023")

    def test_aucune_rotation_necessaire(self):
        # Toutes les references employees existent dans le bon sens : une
        # rotation mal appliquee deplacerait l'origine de la piece.
        employees = set()
        for largeur in (1, 2):
            for profondeur in range(1, 6):
                for depart in range(4):
                    employees |= {d for d, _, _ in _plaques(largeur, profondeur, depart)}
        for design in employees:
            self.assertIn(design, CATALOG)


class TestFond(unittest.TestCase):
    def test_emprise_exacte_et_connexe_sur_tout_le_domaine(self):
        # Balayage exhaustif : la construction ne donne aucune preuve, donc on
        # verifie. 2x2 a 24x24 en entier, puis les carres jusqu'a 64.
        echecs = []
        formats = [(x, y) for x in range(2, 25) for y in range(2, 25)]
        formats += [(n, n) for n in range(25, 65)]
        formats += [(2, 96), (96, 2), (3, 61), (61, 3), (48, 96)]
        for studs_x, studs_y in formats:
            bas = pave(0, 0, studs_x, studs_y)
            haut = pave(-1, -2, studs_x, studs_y)
            if not recouvre_exactement(bas, studs_x, studs_y):
                echecs.append((studs_x, studs_y, "couche 0 deborde ou troue"))
            elif not recouvre_exactement(haut, studs_x, studs_y):
                echecs.append((studs_x, studs_y, "couche 1 deborde ou troue"))
            elif not fond_connexe(bas, haut):
                echecs.append((studs_x, studs_y, "fond scinde"))
        self.assertEqual(echecs, [], f"{len(echecs)} formats sur {len(formats)}")

    def test_le_modele_reel_ne_deborde_pas(self):
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        random.seed(77)
        for cote in (7, 12, 13, 16, 23):
            pixels = bytes(random.randrange(256) for _ in range(cote * cote * 3))
            mosaique = bfk.mosaic.from_image(
                bfk.Image(cote, cote, pixels), palette, cote, cote
            )
            tuiles = {
                mosaique.tile_id(r, c)
                for r in range(cote)
                for c in range(cote)
            }
            boites = [
                mosaique.placed_parts[p].aabb
                for p in mosaique.placed_parts
                if p not in tuiles
            ]
            self.assertEqual(
                (
                    min(b.min.x for b in boites), min(b.min.y for b in boites),
                    max(b.max.x for b in boites), max(b.max.y for b in boites),
                ),
                (0, 0, cote * STUD_PITCH_LDU, cote * STUD_PITCH_LDU),
                f"lisere de substrat nu autour d'une mosaique {cote}x{cote}",
            )

    def test_le_modele_reel_passe_les_six_invariants(self):
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        random.seed(78)
        for cote in (5, 9, 13, 14, 17):
            pixels = bytes(random.randrange(256) for _ in range(cote * cote * 3))
            mosaique = bfk.mosaic.from_image(
                bfk.Image(cote, cote, pixels), palette, cote, cote
            )
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

    def test_panneaux_refusent_un_format_incompatible(self):
        # Un panneau 16x16 qui depasse laisserait une plate nue au bord.
        palette = bfk.PROVISIONAL_PALETTE.solids_only()
        random.seed(79)
        grille = bfk.mosaic.quantize(
            bfk.Image(20, 20, bytes(random.randrange(256) for _ in range(1200))),
            palette, 20, 20,
        )
        with self.assertRaises(ValueError):
            bfk.mosaic.build(grille, substrate="panels")
        grille16 = bfk.mosaic.quantize(
            bfk.Image(16, 16, bytes(random.randrange(256) for _ in range(768))),
            palette, 16, 16,
        )
        self.assertEqual(bfk.mosaic.build(grille16, substrate="panels").studs_x, 16)


if __name__ == "__main__":
    unittest.main(verbosity=2)
