"""Decouper une grande oeuvre en sections que l'on batit separement.

Deux promesses, et ce fichier ne verifie rien d'autre :

  1. chaque section est un modele COMPLET, valide toute seule ;
  2. l'assemblage entier, couche de jonction comprise, est valide aussi.

Ce qui n'est PAS promis — la rigidite — n'est pas teste, parce que le noyau
ne sait pas la mesurer. H5 dit « d'un seul tenant », pas « ne plie pas ».
"""

import random
import unittest

import bfk001 as bfk
from bfk001.panels import (Assembly, Section, build_assembly, split_grid,
                           _verifier_jonction)


def grille(cote, graine=7):
    random.seed(graine)
    return bfk.mosaic.quantize(
        bfk.Image(cote, cote,
                  bytes(random.randrange(256) for _ in range(cote * cote * 3))),
        bfk.PROVISIONAL_PALETTE.solids_only(), cote, cote,
    )


def violations(parts, geometries):
    etat = bfk.assemble(parts, bfk.LEGO_TOLERANCE,
                        search=bfk.LatticeSearchApproximation())
    return (
        bfk.check_h2_collision(parts, geometries)
        + bfk.check_h3_authority_integrity(etat.graph)
        + bfk.check_h4_floating(
            etat.graph, bfk.founded_part_ids(parts, geometries))
        + bfk.check_h5_disconnected(etat.graph)
        + bfk.check_h6_foundation(parts, geometries)
    )


class TestDecoupage(unittest.TestCase):
    """Le decoupage seul, sans rien construire."""

    def test_les_sections_recouvrent_la_grille_exactement(self):
        g = grille(20)
        vues = {}
        for _, _, x0, y0, morceau in split_grid(g, 8):
            for j, rang in enumerate(morceau):
                for i, couleur in enumerate(rang):
                    case = (x0 + i, y0 + j)
                    self.assertNotIn(case, vues, "case livree deux fois")
                    vues[case] = couleur
        self.assertEqual(len(vues), 20 * 20)
        for y in range(20):
            for x in range(20):
                self.assertEqual(vues[(x, y)], g[y][x])

    def test_la_derniere_section_est_plus_petite_et_c_est_normal(self):
        sections = split_grid(grille(20), 8)
        largeurs = {len(m[0]) for *_, m in sections}
        self.assertEqual(largeurs, {8, 4})

    def test_une_grille_vide_ou_une_section_absurde_sont_refusees(self):
        with self.assertRaises(ValueError):
            split_grid((), 8)
        with self.assertRaises(ValueError):
            split_grid(grille(8), 1)


class TestJonction(unittest.TestCase):
    """Le controle qui decide si l'assemblage tiendra."""

    def test_un_joint_non_enjambe_est_refuse(self):
        # Poses fabriquees a la main : deux plates qui s'arretent pile sur le
        # joint. C'est exactement l'arrangement des panneaux officiels, et le
        # noyau le refuse — a juste titre.
        poses = [(0, 0, 8, 8, "41539"), (8, 0, 8, 8, "41539")]
        with self.assertRaises(ValueError) as saisi:
            _verifier_jonction(poses, 16, 8, 8)
        self.assertIn("x=8", str(saisi.exception))

    def test_une_plate_a_cheval_suffit(self):
        poses = [(0, 0, 8, 8, "41539"), (8, 0, 8, 8, "41539"),
                 (6, 0, 4, 2, "3020")]
        _verifier_jonction(poses, 16, 8, 8)   # ne leve pas

    def test_les_deux_axes_sont_controles(self):
        poses = [(0, 0, 8, 8, "41539"), (0, 8, 8, 8, "41539")]
        with self.assertRaises(ValueError) as saisi:
            _verifier_jonction(poses, 8, 16, 8)
        self.assertIn("y=8", str(saisi.exception))


class TestAssemblage(unittest.TestCase):
    """Les deux promesses, mesurees par le noyau."""

    @classmethod
    def setUpClass(cls):
        cls.grille = grille(16)
        cls.assemblage = build_assembly(cls.grille, section_side=8)

    def test_chaque_section_tient_toute_seule(self):
        # C'est la promesse qui rend le decoupage utile : on batit une section
        # sur une table, on la range, on passe a la suivante.
        self.assertEqual(len(self.assemblage.sections), 4)
        for section in self.assemblage.sections:
            fautes = violations(section.mosaic.placed_parts,
                                section.mosaic.geometries)
            self.assertEqual([(v.invariant, v.detail) for v in fautes], [],
                             section.name)

    def test_l_assemblage_entier_tient_aussi(self):
        fautes = violations(self.assemblage.placed_parts,
                            self.assemblage.geometries)
        self.assertEqual([(v.invariant, v.detail) for v in fautes[:5]], [])

    def test_la_couche_de_jonction_existe_et_reste_modeste(self):
        self.assertGreater(self.assemblage.join_count, 0)
        entier = bfk.mosaic.build(self.grille,
                                  tiles=bfk.mosaic.TILE_SET_STANDARD)
        surcout = self.assemblage.part_count / entier.part_count - 1
        self.assertLess(surcout, 0.15,
                        "decouper ne doit pas couter un sixieme du modele")

    def test_les_sections_portent_les_bonnes_couleurs(self):
        # Une section decalee d'une ligne donnerait une oeuvre fausse et
        # parfaitement valide : le noyau ne verrait rien.
        for section in self.assemblage.sections:
            for j, rang in enumerate(section.mosaic.grid):
                for i, couleur in enumerate(rang):
                    self.assertEqual(
                        couleur.code,
                        self.grille[section.y0 + j][section.x0 + i].code,
                        f"{section.name} ligne {j} colonne {i}")

    def test_aucune_piece_ne_partage_son_identifiant(self):
        # Quatre sections baties par le meme code produisent quatre fois les
        # memes noms ; sans prefixe, trois sections disparaitraient dans un
        # dictionnaire.
        total = sum(s.mosaic.part_count for s in self.assemblage.sections)
        self.assertEqual(
            len(self.assemblage.placed_parts),
            total + self.assemblage.join_count,
        )

    def test_le_relief_suit_sa_section(self):
        elevations = [[1 if x < 8 else 0 for x in range(16)] for _ in range(16)]
        avec = build_assembly(self.grille, section_side=8, heights=elevations)
        gauche = [s for s in avec.sections if s.column == 0]
        droite = [s for s in avec.sections if s.column == 1]
        self.assertTrue(all(any(t.level for t in s.mosaic.tiles) for s in gauche))
        self.assertTrue(all(not any(t.level for t in s.mosaic.tiles)
                            for s in droite))

    def test_decouper_ce_qui_n_a_pas_besoin_de_l_etre_est_refuse(self):
        for cote in (16, 20, 64):
            with self.assertRaises(ValueError, msg=str(cote)):
                build_assembly(self.grille, section_side=cote)

    def test_un_ruban_en_derniere_section_est_refuse(self):
        # 20 tenons en sections de 16 laisserait une bande de 4.
        with self.assertRaises(ValueError) as saisi:
            build_assembly(grille(20), section_side=16)
        self.assertIn("ruban", str(saisi.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestCadre(unittest.TestCase):
    """Le cadre : ce qu'il ferme, ce qu'il porte, ce qu'il rend possible."""

    def petite(self, cote=16, graine=5):
        return grille(cote, graine)

    def test_le_cadre_entoure_sans_rogner_l_image(self):
        g = self.petite()
        nu = bfk.mosaic.build(g, tiles=bfk.mosaic.TILE_SET_STANDARD)
        avec = bfk.mosaic.build(g, tiles=bfk.mosaic.TILE_SET_STANDARD, frame=2)
        self.assertEqual(avec.studs_x, nu.studs_x)
        self.assertEqual(avec.outer_x, nu.studs_x + 4)
        self.assertEqual(avec.tile_count, nu.tile_count,
                         "un cadre qui rognerait l'image serait un recadrage")
        self.assertGreater(avec.frame_count, 0)

    def test_le_cadre_depasse_toujours_la_surface(self):
        # Un cadre a fleur n'est pas un cadre : c'est une bordure peinte.
        g = self.petite()
        for relief in (0, 2, 4):
            elevations = ([[relief] * 16 for _ in range(16)]
                          if relief else None)
            m = bfk.mosaic.build(g, tiles=bfk.mosaic.TILE_SET_STANDARD,
                                 heights=elevations, frame=2)
            briques = [n for n in m.placed_parts if n.startswith("C")]
            sommet_cadre = max(m.placed_parts[n].aabb.max.z for n in briques)
            sommet_tuiles = max(
                m.placed_parts[m.tile_id(t.row, t.column)].aabb.max.z
                for t in m.tiles)
            self.assertGreater(sommet_cadre, sommet_tuiles, f"relief {relief}")

    def test_le_cadre_passe_les_six_invariants(self):
        for relief in (0, 2):
            g = self.petite()
            elevations = ([[relief if (x + y) % 3 else 0 for x in range(16)]
                           for y in range(16)] if relief else None)
            m = bfk.mosaic.build(g, tiles=bfk.mosaic.TILE_SET_STANDARD,
                                 heights=elevations, frame=2)
            fautes = violations(m.placed_parts, m.geometries)
            self.assertEqual([(v.invariant, v.detail) for v in fautes], [],
                             f"relief {relief}")

    def test_les_assises_croisent_leurs_joints(self):
        # Deux assises decoupees a l'identique donnent un mur qui se fend le
        # long de ses joints. C'est le meme appareil que le fond croise.
        g = self.petite()
        m = bfk.mosaic.build(g, tiles=bfk.mosaic.TILE_SET_STANDARD,
                             heights=[[2] * 16 for _ in range(16)], frame=2)
        self.assertEqual(m.frame_courses, 2)
        par_assise = {}
        for nom, piece in m.placed_parts.items():
            if nom.startswith("C"):
                par_assise.setdefault(piece.aabb.min.z, set()).add(
                    (piece.aabb.min.x, piece.aabb.min.y))
        altitudes = sorted(par_assise)
        self.assertEqual(len(altitudes), 2)
        self.assertNotEqual(par_assise[altitudes[0]], par_assise[altitudes[1]],
                            "les deux assises tombent au meme endroit")

    def test_le_cadre_rend_constructible_une_bande_d_un_tenon(self):
        # Sans cadre, le fond d'une bande 1x40 se scinde en dix-neuf morceaux
        # et `build` refuse. Le cadre elargit l'emprise et la ceinture.
        etroite = tuple(
            tuple(ligne[:1]) for ligne in grille(40, graine=11)
        )
        with self.assertRaises(ValueError):
            bfk.mosaic.build(etroite, tiles=bfk.mosaic.TILE_SET_STANDARD)
        m = bfk.mosaic.build(etroite, tiles=bfk.mosaic.TILE_SET_STANDARD,
                             frame=2)
        self.assertEqual([(v.invariant, v.detail)
                          for v in violations(m.placed_parts, m.geometries)], [])

    def test_le_cadre_ceinture_les_sections(self):
        g = grille(16, graine=8)
        a = build_assembly(g, section_side=8, frame=2)
        self.assertEqual(a.outer_x, 20)
        self.assertGreater(a.frame_count, 0)
        fautes = violations(a.placed_parts, a.geometries)
        self.assertEqual([(v.invariant, v.detail) for v in fautes], [])
        # Et aucune section ne porte de cadre : il appartient a l'ensemble.
        for section in a.sections:
            self.assertEqual(section.mosaic.frame, 0)

    def test_un_cadre_absurde_est_refuse(self):
        g = self.petite()
        with self.assertRaises(ValueError):
            bfk.mosaic.build(g, tiles=bfk.mosaic.TILE_SET_STANDARD, frame=-1)
        with self.assertRaises(ValueError):
            bfk.mosaic.build(g, substrate="panels",
                             tiles=bfk.mosaic.TILE_SET_STANDARD, frame=2)
