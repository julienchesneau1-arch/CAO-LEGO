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
from typing import Iterable, List, Sequence, Tuple

__all__ = [
    "LegoColor",
    "Palette",
    "PROVISIONAL_PALETTE",
    "load_ldconfig",
    "srgb_to_lab",
    "delta_e",
    "dominant_colors",
    "PaletteGap",
    "gap_report",
]

Rgb = Tuple[int, int, int]


@dataclass(frozen=True)
class LegoColor:
    """Une couleur du systeme : code LDraw, nom, valeur RVB, finition.

    La finition n'est pas decorative : une couleur transparente, chromee,
    nacree ou pailletee n'existe pas forcement en tuile 1x1, et parfois
    n'existe pas du tout. Une liste de course batie dessus serait
    incommandable.
    """

    code: int
    name: str
    rgb: Rgb
    finish: str = "solid"

    @property
    def is_solid(self) -> bool:
        return self.finish == "solid"

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


def delta_e(first: Rgb, second: Rgb) -> float:
    """Ecart percu entre deux couleurs (CIE76).

    Repere de lecture, etabli par la litterature colorimetrique :
      < 1   imperceptible          2-10  perceptible au premier coup d'oeil
      1-2   perceptible a l'oeil exerce   > 10  couleurs franchement differentes

    Sans cette mesure, « rendu fidele » n'est qu'une opinion.
    """
    a, b = srgb_to_lab(first), srgb_to_lab(second)
    return (
        (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
    ) ** 0.5


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

    def solids_only(self) -> "Palette":
        """Les couleurs opaques et mates : celles qu'on peut reellement commander.

        Ecarte transparent, chrome, nacre, metallise, caoutchouc et pailleté —
        la finition est lue dans le fichier officiel, jamais deduite du nom.

        Ecarte aussi les codes 16 et 24. Ce ne sont pas des couleurs mais des
        marqueurs internes au format LDraw : 16 signifie « la couleur courante »
        et 24 « la couleur des aretes ». Rien ne les distingue des autres dans
        le fichier, et une liste de course contenant « Edge Colour » est
        incommandable. Trouve en lisant une selection automatique qui l'avait
        retenue.
        """
        return Palette(
            color
            for color in self._colors
            if color.is_solid and color.code not in LDRAW_INTERNAL_CODES
        )

    def best_subset(self, pixels: Sequence[Rgb], count: int) -> "Palette":
        """Les `count` couleurs de CETTE palette qui rendent le mieux ces pixels.

        Une mosaique ne se commande pas en quatre-vingts couleurs : chaque
        teinte supplementaire est un sachet, un cout, une reference a trouver.
        La question n'est donc pas « toutes les couleurs » mais « lesquelles ».

        Selection gloutonne sur les couleurs dominantes de l'image, ponderee par
        leur surface : a chaque tour on ajoute la couleur qui reduit le plus
        l'ecart total.

        Un critere « minimax » a ete essaye ici — minimiser le PIRE ecart plutot
        que l'ecart moyen, pour empecher un grand aplat de sacrifier un petit
        sujet. Il a ete retire : mesurablement pire (13,1 contre 9,7 delta E de
        moyenne), sans ameliorer le pire ecart d'un dixieme, et surtout il
        repondait a un probleme inexistant — voir docs/ZONES_DOMBRE.md, section
        5.17. Un reglage qui ne gagne nulle part ne merite pas d'exister.
        """
        if count < 1:
            raise ValueError("une palette compte au moins une couleur")
        if count >= len(self._colors):
            return self

        clusters = dominant_colors(pixels, min(24, max(8, count * 2)))
        retenues: List[LegoColor] = []
        restantes = list(self._colors)

        while len(retenues) < count and restantes:
            meilleure = None
            meilleur_cout = None
            for candidate in restantes:
                essai = retenues + [candidate]
                cout = sum(
                    part * min(delta_e(couleur, c.rgb) for c in essai)
                    for couleur, part in clusters
                )
                if meilleur_cout is None or cout < meilleur_cout:
                    meilleur_cout = cout
                    meilleure = candidate
            retenues.append(meilleure)
            restantes.remove(meilleure)

        return Palette(retenues)


PROVISIONAL_PALETTE = Palette(
    (
        LegoColor(0, "Black", (0x05, 0x13, 0x1D)),
        LegoColor(1, "Blue", (0x00, 0x55, 0xBF)),
        LegoColor(2, "Green", (0x25, 0x7A, 0x3E)),  # corrige : #237841 etait faux
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
"""PROVISOIRE — 12 couleurs recopiees a la main, dont onze verifiees exactes
contre le fichier officiel et une corrigee (Green valait #237841 au lieu de
#257A3E). Douze couleurs ne suffisent a aucune photo : sur un paysage, elles
laissent 17,8 delta E d'ecart la ou la palette officielle en laisse 9,7.
Remplacer par load_ldconfig()."""


_COLOUR_LINE = re.compile(
    r"^\s*0\s+!COLOUR\s+(\S+).*?\bCODE\s+(\d+)\b.*?\bVALUE\s+#([0-9A-Fa-f]{6})",
)

LDRAW_INTERNAL_CODES = frozenset({16, 24})
"""Codes LDraw qui ne designent pas une couleur : 16 = couleur courante,
24 = couleur des aretes. Ce sont des marqueurs de format, pas des produits."""


_FINISHES = (
    ("ALPHA", "transparent"),
    ("CHROME", "chrome"),
    ("PEARLESCENT", "pearl"),
    ("METAL", "metal"),
    ("RUBBER", "rubber"),
    ("MATERIAL", "material"),
)


def _finish_of(line: str) -> str:
    """Finition declaree par la ligne elle-meme, jamais devinee."""
    for mot_cle, finition in _FINISHES:
        if re.search(r"\b" + mot_cle + r"\b", line):
            return finition
    return "solid"


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
                _finish_of(line),
            )
        )
    if not colors:
        raise ValueError("aucune ligne !COLOUR exploitable dans ce LDConfig")
    return Palette(colors)


# =============================================================================
# Diagnostic : ce qui manque a une palette, pour une image donnee
# =============================================================================


@dataclass(frozen=True)
class PaletteGap:
    """Une couleur que l'image reclame et que la palette ne sait pas rendre."""

    wanted: Rgb
    share: float          # part des tuiles concernees, de 0 a 1
    best_available: LegoColor
    error: float          # delta E entre la couleur voulue et la meilleure dispo

    @property
    def hex(self) -> str:
        return "#%02X%02X%02X" % self.wanted


def dominant_colors(pixels: Sequence[Rgb], count: int = 12, seed: int = 7):
    """Les `count` couleurs qui resument le mieux ces pixels (k-moyennes en Lab).

    Sert de BORNE SUPERIEURE : c'est le meilleur qu'une palette de cette taille
    puisse faire sur cette image. Comparer une vraie palette a cette borne
    separe ce qui manque de couleurs de ce qui manque de resolution.
    """
    import random

    if not pixels:
        raise ValueError("aucun pixel a resumer")
    labs = [srgb_to_lab(pixel) for pixel in pixels]
    generateur = random.Random(seed)
    centres = [labs[generateur.randrange(len(labs))] for _ in range(count)]
    groupes: list = [[] for _ in range(count)]

    for _ in range(12):
        groupes = [[] for _ in range(count)]
        for index, lab in enumerate(labs):
            plus_proche = min(
                range(count),
                key=lambda c: sum((lab[t] - centres[c][t]) ** 2 for t in range(3)),
            )
            groupes[plus_proche].append(index)
        for c in range(count):
            if groupes[c]:
                centres[c] = tuple(
                    sum(labs[i][t] for i in groupes[c]) / len(groupes[c])
                    for t in range(3)
                )

    resultat = []
    for c in range(count):
        if not groupes[c]:
            continue
        moyenne = tuple(
            sum(pixels[i][t] for i in groupes[c]) // len(groupes[c]) for t in range(3)
        )
        resultat.append((moyenne, len(groupes[c]) / len(pixels)))
    return sorted(resultat, key=lambda entree: -entree[1])


def gap_report(
    pixels: Sequence[Rgb],
    palette: "Palette",
    count: int = 12,
    threshold: float = 10.0,
) -> Tuple[PaletteGap, ...]:
    """Ce que l'image reclame et que la palette ne peut pas rendre.

    Transforme « le rendu est gris » en « 1620 tuiles veulent un bleu pale
    autour de #AEC8E8, et votre palette n'a que du Light Bluish Gray a 22 delta
    E ». C'est la difference entre une plainte et une decision.
    """
    manques = []
    for couleur, part in dominant_colors(pixels, count):
        meilleure = palette.nearest(couleur)
        ecart = delta_e(couleur, meilleure.rgb)
        if ecart >= threshold:
            manques.append(PaletteGap(couleur, part, meilleure, ecart))
    return tuple(sorted(manques, key=lambda gap: -gap.share * gap.error))
