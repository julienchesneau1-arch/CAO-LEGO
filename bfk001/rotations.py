"""Groupe des 24 rotations discretes (HORS CONTRAT, extension de la Section C).

Le contrat definit `Orientation` par ses contraintes — coefficients dans
{-1,0,1}, orthogonalite, determinant +1 — mais ne fournit aucun moyen d'en
construire une autrement qu'en ecrivant neuf entiers a la main. Pour un
logiciel de CAO, c'est une zone d'ombre : toute rotation utilisateur (« tourne
la piece d'un quart de tour ») doit passer par une matrice ecrite en dur.

Ce module enumere le groupe et le nomme. Il n'ajoute aucune semantique : les
24 elements sont exactement ceux que `Orientation` accepte deja.
"""

from __future__ import annotations

import itertools
from typing import Tuple

from .geometry import Orientation

__all__ = [
    "IDENTITY",
    "ROT_X_90",
    "ROT_X_180",
    "ROT_X_270",
    "ROT_Y_90",
    "ROT_Y_180",
    "ROT_Y_270",
    "ROT_Z_90",
    "ROT_Z_180",
    "ROT_Z_270",
    "all_rotations",
    "rotation_x",
    "rotation_y",
    "rotation_z",
]

IDENTITY = Orientation.identity()

ROT_X_90 = Orientation(1, 0, 0, 0, 0, -1, 0, 1, 0)
"""Quart de tour autour de X : (x, y, z) -> (x, -z, y)."""

ROT_Y_90 = Orientation(0, 0, 1, 0, 1, 0, -1, 0, 0)
"""Quart de tour autour de Y : (x, y, z) -> (z, y, -x)."""

ROT_Z_90 = Orientation(0, -1, 0, 1, 0, 0, 0, 0, 1)
"""Quart de tour autour de Z : (x, y, z) -> (-y, x, z)."""

ROT_X_180 = ROT_X_90.compose(ROT_X_90)
ROT_X_270 = ROT_X_180.compose(ROT_X_90)
ROT_Y_180 = ROT_Y_90.compose(ROT_Y_90)
ROT_Y_270 = ROT_Y_180.compose(ROT_Y_90)
ROT_Z_180 = ROT_Z_90.compose(ROT_Z_90)
ROT_Z_270 = ROT_Z_180.compose(ROT_Z_90)


def _quarter_turns(base: Orientation, quarter_turns: int) -> Orientation:
    """base eleve a la puissance quarter_turns, modulo 4. Exact dans Z."""
    if isinstance(quarter_turns, bool) or not isinstance(quarter_turns, int):
        raise TypeError("quarter_turns doit etre un entier")
    result = IDENTITY
    for _ in range(quarter_turns % 4):
        result = result.compose(base)
    return result


def rotation_x(quarter_turns: int) -> Orientation:
    """Rotation de quarter_turns quarts de tour autour de X."""
    return _quarter_turns(ROT_X_90, quarter_turns)


def rotation_y(quarter_turns: int) -> Orientation:
    """Rotation de quarter_turns quarts de tour autour de Y."""
    return _quarter_turns(ROT_Y_90, quarter_turns)


def rotation_z(quarter_turns: int) -> Orientation:
    """Rotation de quarter_turns quarts de tour autour de Z."""
    return _quarter_turns(ROT_Z_90, quarter_turns)


def all_rotations() -> Tuple[Orientation, ...]:
    """Les 24 rotations valides, enumerees et verifiees a la construction.

    Une matrice orthogonale a coefficients dans {-1,0,1} est une matrice de
    permutation signee : 6 permutations x 8 combinaisons de signes = 48
    candidates, dont exactement la moitie a un determinant de +1. Les 24 autres
    sont des reflexions, refusees par Orientation.
    """
    rotations = []
    for permutation in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            rows = [[0, 0, 0] for _ in range(3)]
            for row, column in enumerate(permutation):
                rows[row][column] = signs[row]
            try:
                rotations.append(
                    Orientation(*(value for row in rows for value in row))
                )
            except ValueError:
                continue  # determinant -1 : reflexion, hors groupe
    return tuple(rotations)
