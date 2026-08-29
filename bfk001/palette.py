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

import bisect
import math
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "LegoColor",
    "Palette",
    "PROVISIONAL_PALETTE",
    "load_ldconfig",
    "srgb_to_lab",
    "delta_e",
    "delta_e_selection",
    "dominant_colors",
    "PaletteGap",
    "gap_report",
    "find_ldconfig",
    "load_best_palette",
    "installer_palette",
    "PaletteRefusee",
    "SOURCES_PALETTE",
    "PALETTE_INSTALLEE",
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
    lego_id: Optional[int] = None
    """Identifiant de couleur du systeme LEGO, quand LDConfig le donne.

    Il est en commentaire dans le fichier officiel — « // LEGOID 26 - Black » —
    et c'est le SEUL identifiant partage entre LDraw et les catalogues
    commerciaux. Sans lui, faire correspondre une couleur LDraw a une couleur
    BrickLink demande de recopier une table a la main ; avec lui, la
    correspondance s'importe. 138 des 162 couleurs en portent un."""

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


_VINGT_CINQ_7 = 25.0 ** 7

_SL_MAX = 1 + 0.015 * 2500 / math.sqrt(20 + 2500)
"""Maximum de SL sur L dans [0, 100], atteint aux extremes. Sert de borne a la
coupure exacte de `Palette.nearest` : dE2000 >= |dL| / SL_MAX."""

_CACHE_LAB: Dict[Rgb, Tuple[float, float, float]] = {}
_CACHE_LAB_MAX = 200_000
"""Une photo repasse sans cesse par les memes teintes : la conversion vaut
d'etre gardee — mais pas au point d'avaler la memoire sur une image de 12 Mpx."""


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


def delta_e76(first: Rgb, second: Rgb) -> float:
    """Ecart percu, CIE 1976 : distance euclidienne dans L*a*b*.

    Conservee parce qu'elle est simple, rapide et qu'elle sert de repere de
    lecture. Elle ne sert PLUS a choisir une couleur : voir `delta_e2000`.
    """
    a, b = srgb_to_lab(first), srgb_to_lab(second)
    return (
        (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
    ) ** 0.5


def _delta_e2000_lab(lab1, lab2, kL: float = 1.0, kC: float = 1.0,
                     kH: float = 1.0, rotation: bool = True) -> float:
    """CIEDE2000 entre deux points L*a*b* deja convertis.

    `rotation=False` omet le terme croise RT.tC.tH. Ce n'est plus CIEDE2000 et
    ce n'est pas un raccourci de calcul : voir `Palette.nearest`, qui explique
    pourquoi la formule standard est le mauvais outil pour CHOISIR une couleur
    dans une palette grossiere.
    """
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    Cb7 = Cb ** 7
    G = 0.5 * (1 - math.sqrt(Cb7 / (Cb7 + _VINGT_CINQ_7))) if Cb else 0.5
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = 0.0 if (a1p == 0 and b1 == 0) else math.degrees(math.atan2(b1, a1p)) % 360
    h2p = 0.0 if (a2p == 0 and b2 == 0) else math.degrees(math.atan2(b2, a2p)) % 360

    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2)

    Lb = (L1 + L2) / 2
    Cbp = (C1p + C2p) / 2
    if C1p * C2p == 0:
        Hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        Hbp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        Hbp = (h1p + h2p + 360) / 2
    else:
        Hbp = (h1p + h2p - 360) / 2

    T = (
        1
        - 0.17 * math.cos(math.radians(Hbp - 30))
        + 0.24 * math.cos(math.radians(2 * Hbp))
        + 0.32 * math.cos(math.radians(3 * Hbp + 6))
        - 0.20 * math.cos(math.radians(4 * Hbp - 63))
    )
    SL = 1 + 0.015 * (Lb - 50) ** 2 / math.sqrt(20 + (Lb - 50) ** 2)
    SC = 1 + 0.045 * Cbp
    SH = 1 + 0.015 * Cbp * T
    Cbp7 = Cbp ** 7
    RC = 2 * math.sqrt(Cbp7 / (Cbp7 + _VINGT_CINQ_7)) if Cbp else 0.0
    RT = -math.sin(math.radians(60 * math.exp(-(((Hbp - 275) / 25) ** 2)))) * RC

    tL, tC, tH = dLp / (kL * SL), dCp / (kC * SC), dHp / (kH * SH)
    croise = RT * tC * tH if rotation else 0.0
    return math.sqrt(max(0.0, tL * tL + tC * tC + tH * tH + croise))


def delta_e2000(first: Rgb, second: Rgb) -> float:
    """Ecart percu, CIEDE2000 — la metrique recommandee par la CIE.

    Repere de lecture, etabli par la litterature colorimetrique :
      < 1   imperceptible          2-10  perceptible au premier coup d'oeil
      1-2   perceptible a l'oeil exerce   > 10  couleurs franchement differentes

    Pourquoi elle et pas la distance euclidienne dans L*a*b* : L*a*b* n'est pas
    aussi uniforme qu'annonce, et sa region BLEUE est franchement distordue.
    Mesure faite sur la palette officielle : pour #005AB4, un bleu franc, CIE76
    choisit Violet (#4354A3) plutot que Blue (#0055BF) — qui est presque la
    meme couleur — et gagne de 0,68 delta E. CIEDE2000 corrige precisement
    cela : son terme de rotation RT est centre sur H = 275 deg, c'est-a-dire
    sur les bleus, parce que la CIE a constate la meme chose.

    Le prix est un facteur deux sur la recherche du plus proche. C'est payable,
    et une tuile franchement fausse dans un visage coute plus cher que ca.
    """
    return _delta_e2000_lab(srgb_to_lab(first), srgb_to_lab(second))


# Choisir une couleur, c'est un jugement percu : c'est CIEDE2000 qui tranche.
delta_e = delta_e2000


def delta_e_selection(first: Rgb, second: Rgb) -> float:
    """L'ecart qui sert a CHOISIR une couleur dans une palette grossiere.

    CIEDE2000 sans son terme de rotation. Ce n'est pas une approximation : la
    formule standard est le mauvais outil ici, et `Palette.nearest` explique
    pourquoi en detail. `delta_e` reste la mesure de reference — c'est elle
    qui dit ce que vaut le resultat, et elle est exacte au dix-millieme sur
    les quinze paires de controle de Sharma.
    """
    return _delta_e2000_lab(srgb_to_lab(first), srgb_to_lab(second),
                            rotation=False)


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
        # Palette triee par clarte, pour la coupure exacte de `nearest`.
        self._par_clarte: Tuple[int, ...] = tuple(
            sorted(range(len(self._colors)), key=lambda i: self._lab[i][0])
        )
        self._clartes: Tuple[float, ...] = tuple(
            self._lab[i][0] for i in self._par_clarte
        )
        self._proches: Dict[Rgb, LegoColor] = {}

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
        """Couleur perceptuellement la plus proche, au sens de CIEDE2000.

        EXACTE, et pourtant elle n'evalue pas toute la palette. La coupure
        repose sur une borne inferieure demontrable, pas sur une heuristique :

            dE2000^2 = tL^2 + tC^2 + tH^2 + RT.tC.tH   avec RT dans [-2, 0]

        or tC^2 + tH^2 + RT.tC.tH >= tC^2 + tH^2 - 2|tC||tH| = (|tC|-|tH|)^2,
        qui est positif. Donc dE2000 >= |tL| = |dL| / SL, et SL est borne :
        SL = 1 + 0,015 (Lm-50)^2 / racine(20 + (Lm-50)^2) <= 1,748 sur [0, 100].

        D'ou : dE2000 >= |dL| / 1,748. En parcourant la palette par clarte
        croissante autour de la cible, des que |dL| / 1,748 depasse le meilleur
        ecart deja trouve, aucune couleur plus loin ne peut faire mieux.

        Une presélection par CIE76 avait ete essayee d'abord — bien plus simple
        et bien plus rapide. Mesure sur 4000 cibles : 1,5 % de desaccords a 8
        candidats, 0,33 % encore a 16. Elle reintroduisait exactement le biais
        de CIE76 que CIEDE2000 sert a corriger. Rejetee.

        LE TERME DE ROTATION EST OMIS ICI, et c'est une decision, pas un
        raccourci. CIEDE2000 porte un terme croise RT.tC.tH, toujours negatif,
        qui modelise une interaction observee dans la region bleue POUR DE
        PETITS ECARTS — la CIE borne explicitement la formule aux ecarts
        faibles. Choisir une couleur dans une palette de quatre-vingts teintes,
        c'est comparer des ecarts de 5 a 40 : le terme y agit hors de son
        domaine de validite, et il retranche.

        Mesure sur un gris sombre neutre, RVB(62, 68, 70), photographie reelle :

            couleur              tL      tC      tH   RT.tC.tH   dE2000
            Purple             0,97   25,16   17,62    -731,03    14,61
            Dark Bluish Grey  15,00    0,55   -4,79       0,00    15,76

        Le violet sature gagne. Sans le terme croise il vaut 30,73 et perd, ce
        qui est le bon resultat : un gris neutre ne se remplace pas par un
        violet. Sur une photo de velo noir, ce defaut peignait des dizaines de
        tuiles magenta sur une porte noire.

        L'omission ne casse pas la coupure, et pour une raison plus simple que
        celle que j'avais d'abord ecrite. J'avais dit « retirer un terme
        negatif ne peut qu'augmenter l'ecart » — c'est faux, et un test l'a
        montre : RT est bien negatif, mais le produit RT.tC.tH change de signe
        avec tC et tH, donc il ajoute parfois. La vraie raison tient en une
        ligne : sans le terme croise, l'ecart vaut racine(tL^2 + tC^2 + tH^2),
        qui est superieur ou egal a |tL| par construction. La borne
        ecart >= |dL| / 1,748 vaut donc directement, sans rien supposer du
        signe de quoi que ce soit.

        `delta_e2000` et `delta_e` gardent la formule standard, exacte au
        millieme sur les quinze paires de controle de Sharma : c'est elle qui
        MESURE la fidelite. Choisir et mesurer ne demandent pas le meme outil.
        """
        # Le mode « auto » interroge trois fois les memes tenons : une fois
        # pour la version sans tramage, une fois pour mesurer l'ecart a la
        # palette, une fois pour la version tramee. Deux tiers de ce travail
        # sont identiques.
        trouvee = self._proches.get(rgb)
        if trouvee is not None:
            return trouvee
        target = _CACHE_LAB.get(rgb)
        if target is None:
            target = srgb_to_lab(rgb)
            if len(_CACHE_LAB) < _CACHE_LAB_MAX:
                _CACHE_LAB[rgb] = target
        cible_l = target[0]
        clartes = self._clartes
        ordre = self._par_clarte
        nombre = len(ordre)
        droite = bisect.bisect_left(clartes, cible_l)
        gauche = droite - 1
        best_index = ordre[0]
        best_distance = float("inf")
        infini = float("inf")
        while gauche >= 0 or droite < nombre:
            # Toujours le voisin le plus proche en clarte : |dL| croit donc
            # de facon monotone, et la coupure peut arreter tout le reste.
            ecart_gauche = cible_l - clartes[gauche] if gauche >= 0 else infini
            ecart_droite = clartes[droite] - cible_l if droite < nombre else infini
            if ecart_gauche <= ecart_droite:
                index, gauche, ecart = ordre[gauche], gauche - 1, ecart_gauche
            else:
                index, droite, ecart = ordre[droite], droite + 1, ecart_droite
            if ecart / _SL_MAX >= best_distance:
                break
            distance = _delta_e2000_lab(self._lab[index], target,
                                        rotation=False)
            if distance < best_distance:
                best_distance = distance
                best_index = index
        choisie = self._colors[best_index]
        if len(self._proches) < _CACHE_LAB_MAX:
            self._proches[rgb] = choisie
        return choisie

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

        # Le nombre de grappes suit le budget de couleurs. Il etait plafonne a
        # 24, et ce plafond BRIDAIT le resultat : sur un degrade riche, N=32
        # ne gagnait rien sur N=24 — le proxy ne savait plus les distinguer.
        clusters = dominant_colors(pixels, min(96, max(16, count * 3)))
        labs = [(srgb_to_lab(couleur), part) for couleur, part in clusters]

        # Distance courante de chaque grappe a la palette deja retenue. La
        # tenir a jour rend le glouton lineaire en `count` au lieu de
        # quadratique : ajouter une couleur ne peut que RAPPROCHER une grappe,
        # donc un simple minimum suffit, et le resultat est identique.
        meilleur = [float("inf")] * len(labs)
        retenues: List[LegoColor] = []
        restantes = list(self._colors)

        while len(retenues) < count and restantes:
            elue = None
            cout_elu = None
            distances_elues = None
            for candidate in restantes:
                lab_candidate = srgb_to_lab(candidate.rgb)
                distances = [
                    min(actuel, _delta_e2000_lab(lab, lab_candidate))
                    for actuel, (lab, _) in zip(meilleur, labs)
                ]
                cout = sum(d * part for d, (_, part) in zip(distances, labs))
                if cout_elu is None or cout < cout_elu:
                    cout_elu, elue, distances_elues = cout, candidate, distances
            retenues.append(elue)
            restantes.remove(elue)
            meilleur = distances_elues

        return Palette(retenues)

    def subset_curve(
        self, pixels: Sequence[Rgb], maximum: int = 24
    ) -> Tuple[Tuple[LegoColor, float], ...]:
        """Courbe cout / fidelite : (nombre de couleurs, ecart moyen).

        Rend la SUITE elle-meme : la couleur ajoutee a chaque tour et l'ecart
        moyen qui en resulte. Les N premieres forment la palette pour N.

        Elle rend les couleurs, et pas seulement les ecarts, pour une raison
        precise : `best_subset` fait varier son nombre de grappes avec `count`,
        donc sa reponse pour N n'est PAS le prefixe de cette courbe. Choisir N
        ici puis rappeler `best_subset(N)` livrerait une autre palette que
        celle qu'on a mesuree. On garde donc la suite mesuree.
        """
        if maximum < 1:
            raise ValueError("une palette compte au moins une couleur")
        maximum = min(maximum, len(self._colors))
        clusters = dominant_colors(pixels, min(96, max(16, maximum * 3)))
        labs = [(srgb_to_lab(couleur), part) for couleur, part in clusters]
        total = sum(part for _, part in labs) or 1.0

        meilleur = [float("inf")] * len(labs)
        restantes = list(self._colors)
        courbe: List[Tuple[int, float]] = []
        while len(courbe) < maximum and restantes:
            elue = None
            cout_elu = None
            distances_elues = None
            for candidate in restantes:
                lab_candidate = srgb_to_lab(candidate.rgb)
                distances = [
                    min(actuel, _delta_e2000_lab(lab, lab_candidate))
                    for actuel, (lab, _) in zip(meilleur, labs)
                ]
                cout = sum(d * part for d, (_, part) in zip(distances, labs))
                if cout_elu is None or cout < cout_elu:
                    cout_elu, elue, distances_elues = cout, candidate, distances
            restantes.remove(elue)
            meilleur = distances_elues
            courbe.append((elue, cout_elu / total))
        return tuple(courbe)

    def cheapest_subset(
        self, pixels: Sequence[Rgb], tolerance: float = 0.5, maximum: int = 24
    ) -> "Palette":
        """La plus PETITE palette dont l'ecart PAR TUILE reste dans `tolerance`.

        ATTENTION a ce que cette fonction ne mesure pas. Elle juge l'ecart
        moyen tuile par tuile, et cet ecart plafonne vite : sur un paysage, il
        ne bouge plus au-dela de huit couleurs. La JUSTESSE TONALE, elle,
        continue de s'ameliorer bien apres — 3,7 delta E avec la palette
        entiere contre 5,0 avec huit couleurs, et 7,5 contre 12,3 au pire.
        C'est elle qui gouverne la lecture d'ensemble du tableau.

        Pour arbitrer sur les deux criteres a la fois, voir
        `mosaic.cheapest_palette`, qui evalue la mosaique reelle. Celle-ci
        reste utile quand on veut un choix instantane sans construire de
        modele.
        Chaque couleur en plus est un sachet a trouver, a payer et a ranger.
        """
        if tolerance < 0:
            raise ValueError("une tolerance est positive")
        courbe = self.subset_curve(pixels, maximum)
        plancher = min(ecart for _, ecart in courbe)
        for rang, (_, ecart) in enumerate(courbe, start=1):
            if ecart <= plancher + tolerance:
                return Palette(couleur for couleur, _ in courbe[:rang])
        raise AssertionError  # pragma: no cover - le minimum est dans la courbe


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
    dernier_legoid = None
    for line in text.splitlines():
        # Le LEGOID precede sa couleur, en commentaire. On le retient pour la
        # ligne !COLOUR qui suit, et on l'oublie ensuite : l'associer a la
        # mauvaise couleur serait pire que de ne pas l'avoir.
        marque = _LEGOID_LINE.match(line)
        if marque:
            dernier_legoid = int(marque.group(1))
            continue
        match = _COLOUR_LINE.match(line)
        if not match:
            continue
        name, code, value = match.group(1), int(match.group(2)), match.group(3)
        legoid, dernier_legoid = dernier_legoid, None
        if code in seen:
            continue
        seen.add(code)
        colors.append(
            LegoColor(
                code,
                name.replace("_", " "),
                (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)),
                _finish_of(line),
                legoid,
            )
        )
    if not colors:
        raise ValueError("aucune ligne !COLOUR exploitable dans ce LDConfig")
    return Palette(colors)


_LEGOID_LINE = re.compile(r"^0\s+//\s*LEGOID\s+(\d+)\s*-")

PALETTE_INSTALLEE = "~/.brickforge/LDConfig.ldr"
"""Ou `installer_palette` depose le fichier, et le premier endroit ou on regarde.

En tete de liste a dessein : une installation DELIBEREE l'emporte sur ce qu'un
autre logiciel a pu laisser trainer.
"""

SOURCES_PALETTE = (
    "https://library.ldraw.org/library/official/LDConfig.ldr",
    "https://www.ldraw.org/library/official/LDConfig.ldr",
    "https://raw.githubusercontent.com/trevorsandy/lpub3d/master/mainApp/extras/LDConfig.ldr",
)
"""Ou chercher le fichier, dans l'ordre. Les deux premieres sont les adresses
officielles de LDraw.org ; la troisieme est le miroir que LPub3D distribue avec
son installateur, pour les reseaux qui n'atteignent pas la premiere.

Aucune n'a ete verifiee depuis cette machine sauf la troisieme — le proxy de ce
conteneur bloque ldraw.org. C'est dit ici plutot que sous-entendu : le mecanisme
est teste, la joignabilite des deux premieres adresses ne l'est pas.
"""

LDCONFIG_EMPLACEMENTS = (
    PALETTE_INSTALLEE,
    "~/.ldraw/LDConfig.ldr",
    "~/ldraw/LDConfig.ldr",
    "~/Library/Application Support/LDraw/LDConfig.ldr",
    "/usr/share/ldraw/LDConfig.ldr",
    "/usr/local/share/ldraw/LDConfig.ldr",
    "/opt/ldraw/LDConfig.ldr",
    "C:/Users/Public/Documents/LDraw/LDConfig.ldr",
    "C:/Program Files/LDraw/LDConfig.ldr",
    "~/Library/Application Support/LeoCAD/library/LDConfig.ldr",
    "~/.local/share/leocad/library/LDConfig.ldr",
    "C:/Program Files/Studio 2.0/ldraw/LDConfig.ldr",
    "/Applications/Studio 2.0/ldraw/LDConfig.ldr",
    "C:/Program Files/BrickLink/Stud.io/ldraw/LDConfig.ldr",
    "/Applications/Studio 2.0/PartsLibrary/ldraw/LDConfig.ldr",
    "~/Documents/LDraw/LDConfig.ldr",
    "~/Applications/LDraw/LDConfig.ldr",
)
"""Ou LDraw, LeoCAD et BrickLink Studio deposent le fichier de couleurs.

Le fichier n'est PAS embarque dans ce depot. Il appartient a LDraw.org et se
distribue sous CCAL 2.0 — une licence qui autorise la redistribution avec
attribution, mais qui definit l'oeuvre par une ligne `!LICENSE` que
LDConfig.ldr ne porte pas. L'ambiguite n'est pas tranchable ici, et
redistribuer un fichier dont on ne peut pas etablir la licence n'est pas une
decision a prendre tout seul. On le CHERCHE donc la ou il se trouve deja.
"""


def find_ldconfig(extra: Optional[Sequence[str]] = None) -> Optional[str]:
    """Chemin du premier LDConfig.ldr lisible, ou None.

    Rend la palette officielle disponible sans aucun drapeau des que LDraw,
    LeoCAD ou Studio est installe — ce qui est le cas de quiconque construit
    vraiment en LEGO.
    """
    import os

    # LDRAWDIR est la variable d'environnement que la distribution LDraw pose
    # elle-meme, et que tous ses outils lisent. La chercher avant les chemins
    # devines, c'est demander a l'installation ou elle est plutot que de le
    # supposer — et c'est la seule facon de trouver une installation posee
    # ailleurs que dans les six endroits habituels.
    racines = [os.environ[nom] for nom in ("LDRAWDIR", "LDRAW_DIR", "LDRAWPATH")
               if os.environ.get(nom)]
    depuis_env = [os.path.join(racine, sous, "LDConfig.ldr")
                  for racine in racines for sous in ("", "ldraw")]
    for chemin in list(extra or ()) + depuis_env + list(LDCONFIG_EMPLACEMENTS):
        complet = os.path.expanduser(chemin)
        if os.path.isfile(complet) and os.access(complet, os.R_OK):
            return complet
    return None


class PaletteRefusee(ValueError):
    """Ce qui a ete telecharge n'est pas une palette LDraw exploitable."""


DELAI_TELECHARGEMENT = 20.0
"""Secondes accordees a chaque source.

Trois sources a soixante secondes font trois minutes d'attente muette quand un
reseau bloque la premiere. Vingt suffisent largement a vingt-huit kilo-octets,
et ne donnent pas l'impression que le programme est mort.
"""


def installer_palette(destination: Optional[str] = None,
                      sources: Sequence[str] = SOURCES_PALETTE,
                      ouvrir=None, dire=None) -> Tuple[str, Palette]:
    """Telecharge la palette officielle et l'installe. Rend (chemin, palette).

    Ce depot n'embarque PAS `LDConfig.ldr` : le fichier appartient a LDraw.org
    et ne porte aucune mention de licence qu'on puisse verifier. Le redistribuer
    serait exactement ce que ce projet s'interdit — recopier une donnee dont on
    n'a pas verifie la provenance. L'installer sur la machine de qui le demande
    est autre chose : c'est ce que fait tout outil de CAO LEGO.

    Ce qui est telecharge est VERIFIE avant d'etre ecrit. Un proxy d'entreprise
    qui rend une page de connexion, un miroir devenu 404 renvoye en HTML, un
    fichier tronque : tous produisent quelque chose qui n'est pas une palette,
    et rien ne doit s'installer dans ce cas. Une palette silencieusement fausse
    serait pire que pas de palette du tout — c'est toute la mosaique qui
    sortirait d'a cote.

    `ouvrir` est injectable pour que ce mecanisme se teste SANS reseau ;
    `dire` recoit une ligne par source essayee, pour qu'une attente reseau ne
    ressemble pas a un programme mort.
    """
    import os
    import urllib.request

    if ouvrir is None:                       # pragma: no cover - reseau
        def ouvrir(url):
            with urllib.request.urlopen(url,
                                        timeout=DELAI_TELECHARGEMENT) as reponse:
                return reponse.read()

    chemin = os.path.expanduser(destination or PALETTE_INSTALLEE)
    echecs = []
    for source in sources:
        if dire is not None:
            dire(f"  j'essaie {source}")
        try:
            octets = ouvrir(source)
        except Exception as raison:          # pragma: no cover - depend du reseau
            echecs.append(f"{source} : {type(raison).__name__}")
            continue
        try:
            palette = _verifier_palette(octets.decode("utf-8", errors="replace"))
        except PaletteRefusee as raison:
            echecs.append(f"{source} : {raison}")
            continue
        os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
        # Ecriture puis remplacement : une coupure en cours de telechargement ne
        # doit pas laisser un demi-fichier a l'endroit ou on ira le lire.
        provisoire = chemin + ".partiel"
        with open(provisoire, "wb") as fichier:
            fichier.write(octets)
        os.replace(provisoire, chemin)
        return chemin, palette
    raise PaletteRefusee(
        "aucune source n'a rendu une palette exploitable :\n  "
        + "\n  ".join(echecs)
        + "\nTelechargez LDConfig.ldr a la main et passez --ldconfig CHEMIN."
    )


COULEURS_MINIMALES = 100
SOLIDES_MINIMAUX = 40


def _verifier_palette(texte: str) -> Palette:
    """Refuse tout ce qui n'est pas une vraie palette officielle.

    Les seuils ne sont pas arbitraires : LDConfig en compte 159 dont 80 solides.
    Un fichier qui en donne moins de 100, ou moins de 40 solides, n'est pas la
    palette officielle — c'est une page d'erreur, un fragment, ou autre chose.
    """
    try:
        palette = load_ldconfig(texte)
    except Exception as raison:
        raise PaletteRefusee(f"illisible ({type(raison).__name__})") from None
    solides = sum(1 for couleur in palette if couleur.is_solid)
    if len(palette) < COULEURS_MINIMALES or solides < SOLIDES_MINIMAUX:
        raise PaletteRefusee(
            f"{len(palette)} couleurs dont {solides} solides, il en faut au "
            f"moins {COULEURS_MINIMALES} et {SOLIDES_MINIMAUX}"
        )
    return palette


def load_best_palette(extra: Optional[Sequence[str]] = None) -> Tuple[Palette, str]:
    """(palette, provenance). La palette officielle si on la trouve.

    Rend toujours quelque chose d'utilisable, et dit toujours ce que c'est :
    une palette silencieusement degradee est pire qu'une palette absente.
    """
    chemin = find_ldconfig(extra)
    if chemin is None:
        return PROVISIONAL_PALETTE, "provisoire (12 couleurs recopiees a la main)"
    with open(chemin, "r", encoding="utf-8", errors="replace") as fichier:
        return load_ldconfig(fichier.read()), chemin


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

    # La boucle interieure est le point le plus chaud de la chaine apres la
    # collision : douze passes sur tous les pixels, douze centres chacune.
    # Ecrite avec `min(range(count), key=lambda ...)` et un `sum(... for t in
    # range(3))`, elle creait 5,3 millions de generateurs et 1,3 million de
    # fermetures pour une mosaique de 96 tenons. Deroulee, elle rend EXACTEMENT
    # la meme chose : la somme part de zero dans le meme ordre, `x ** 2` et
    # `x * x` sont le meme flottant, et le `<` strict garde le premier minimum
    # comme le faisait `min`. Verifie par empreinte SHA-256 des livrables.
    for _ in range(12):
        groupes = [[] for _ in range(count)]
        for index, lab in enumerate(labs):
            l0, l1, l2 = lab
            plus_proche = 0
            c0, c1, c2 = centres[0]
            d0, d1, d2 = l0 - c0, l1 - c1, l2 - c2
            meilleure = d0 * d0 + d1 * d1 + d2 * d2
            for c in range(1, count):
                c0, c1, c2 = centres[c]
                d0, d1, d2 = l0 - c0, l1 - c1, l2 - c2
                distance = d0 * d0 + d1 * d1 + d2 * d2
                if distance < meilleure:
                    meilleure = distance
                    plus_proche = c
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
