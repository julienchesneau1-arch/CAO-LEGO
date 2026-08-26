"""Palette LEGO et quantification couleur (HORS CONTRAT, couche perception).

AVERTISSEMENT, et il compte : la palette integree ci-dessous est PROVISOIRE.
Elle contient les codes LDraw dont les valeurs sont les plus etablies, recopies
a la main — exactement le geste qui avait fait etiqueter la reference 3021
« Plate 2x4 » alors qu'elle designe une Plate 2x3.

La palette officielle (~70 couleurs actives, correspondances BrickLink et
Element ID) doit etre IMPORTEE, pas recopiee : `load_ldconfig()` lit le fichier
LDConfig.ldr fourni avec toute distribution LDraw et remplace integralement la
palette provisoire en une ligne. Tant que ce fichier n'est pas fourni, toute
liste de course produite ici est a verifier.

La quantification travaille en CIE L*a*b* et non en RVB : deux couleurs a
distance RVB egale peuvent etre percues tres differemment, et une mosaique se
juge a l'oeil, pas au calcul.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence, Tuple

__all__ = [
    "LegoColor",
    "Palette",
    "PROVISIONAL_PALETTE",
    "load_ldconfig",
    "srgb_to_lab",
]

Rgb = Tuple[int, int, int]


@dataclass(frozen=True)
class LegoColor:
    """Une couleur du systeme : code LDraw, nom, valeur RVB."""

    code: int
    name: str
    rgb: Rgb

    def __post_init__(self) -> None:
        if isinstance(self.code, bool) or not isinstance(self.code, int):
            raise TypeError("LegoColor.code doit etre un entier")
        if len(self.rgb) != 3 or not all(0 <= value <= 255 for value in self.rgb):
            raise ValueError(f"valeur RVB invalide : {self.rgb}")


def _linearize(component: int) -> float:
    value = component / 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def srgb_to_lab(rgb: Rgb) -> Tuple[float, float, float]:
    """Conversion sRGB -> CIE L*a*b* (illuminant D65).

    Hors du noyau, donc les flottants sont ici chez eux : la perception
    coloree n'a rien d'entier.
    """
    r, g, b = (_linearize(component) for component in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else t * 841 / 108 + 4 / 29

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


class Palette:
    """Ensemble de couleurs disponibles, avec recherche du plus proche percu."""

    def __init__(self, colors: Iterable[LegoColor]) -> None:
        self._colors: Tuple[LegoColor, ...] = tuple(colors)
        if not self._colors:
            raise ValueError("une palette vide ne permet aucune quantification")
        codes = [color.code for color in self._colors]
        if len(set(codes)) != len(codes):
            raise ValueError("code couleur duplique dans la palette")
        self._lab = tuple(srgb_to_lab(color.rgb) for color in self._colors)

    def __len__(self) -> int:
        return len(self._colors)

    def __iter__(self):
        return iter(self._colors)

    @property
    def colors(self) -> Tuple[LegoColor, ...]:
        return self._colors

    def by_code(self, code: int) -> LegoColor:
        for color in self._colors:
            if color.code == code:
                return color
        raise KeyError(f"couleur absente de la palette : {code}")

    def nearest(self, rgb: Rgb) -> LegoColor:
        """Couleur perceptuellement la plus proche (delta E 1976 en L*a*b*)."""
        target = srgb_to_lab(rgb)
        best_index = 0
        best_distance = float("inf")
        for index, lab in enumerate(self._lab):
            distance = (
                (lab[0] - target[0]) ** 2
                + (lab[1] - target[1]) ** 2
                + (lab[2] - target[2]) ** 2
            )
            if distance < best_distance:
                best_distance = distance
                best_index = index
        return self._colors[best_index]

    def restricted_to(self, codes: Sequence[int]) -> "Palette":
        """Sous-palette : un modele reel se limite aux couleurs approvisionnables."""
        wanted = set(codes)
        return Palette(color for color in self._colors if color.code in wanted)


PROVISIONAL_PALETTE = Palette(
    (
        LegoColor(0, "Black", (0x05, 0x13, 0x1D)),
        LegoColor(1, "Blue", (0x00, 0x55, 0xBF)),
        LegoColor(2, "Green", (0x23, 0x78, 0x41)),
        LegoColor(4, "Red", (0xC9, 0x1A, 0x09)),
        LegoColor(6, "Brown", (0x58, 0x39, 0x27)),
        LegoColor(14, "Yellow", (0xF2, 0xCD, 0x37)),
        LegoColor(15, "White", (0xFF, 0xFF, 0xFF)),
        LegoColor(19, "Tan", (0xE4, 0xCD, 0x9E)),
        LegoColor(70, "Reddish Brown", (0x58, 0x2A, 0x12)),
        LegoColor(71, "Light Bluish Gray", (0xA0, 0xA5, 0xA9)),
        LegoColor(72, "Dark Bluish Gray", (0x6C, 0x6E, 0x68)),
        LegoColor(320, "Dark Red", (0x72, 0x0E, 0x0F)),
    )
)
"""PROVISOIRE — 12 couleurs recopiees a la main. Remplacer par load_ldconfig()."""


_COLOUR_LINE = re.compile(
    r"^\s*0\s+!COLOUR\s+(\S+).*?\bCODE\s+(\d+)\b.*?\bVALUE\s+#([0-9A-Fa-f]{6})",
)


def load_ldconfig(text: str) -> Palette:
    """Lit un LDConfig.ldr et en tire la palette officielle.

    C'est la voie a privilegier : aucune valeur n'est alors recopiee a la main.
    Les couleurs speciales (transparentes, chromees, pailletees) sont conservees
    telles quelles — c'est a la couche produit de restreindre la palette aux
    couleurs reellement approvisionnables, via `Palette.restricted_to`.
    """
    colors = []
    seen = set()
    for line in text.splitlines():
        match = _COLOUR_LINE.match(line)
        if not match:
            continue
        name, code, value = match.group(1), int(match.group(2)), match.group(3)
        if code in seen:
            continue
        seen.add(code)
        colors.append(
            LegoColor(
                code,
                name.replace("_", " "),
                (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)),
            )
        )
    if not colors:
        raise ValueError("aucune ligne !COLOUR exploitable dans ce LDConfig")
    return Palette(colors)
