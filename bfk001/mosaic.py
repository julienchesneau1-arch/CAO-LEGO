"""Mosaique LEGO Art : image -> modele constructible (HORS CONTRAT, couche 2).

Ce module est un SOLVEUR, pas une autorite : il propose un placement, et le
noyau juge. Rien de ce qu'il produit n'est repute valide avant d'avoir passe
H1 a H6.

La technique retenue est celle des sets LEGO Art officiels : des tuiles 1x1
lisses posees sur un fond. Le fond n'est pas un detail — c'est lui qui fait
l'objet. Des tuiles posees cote a cote ne se lient pas entre elles : sans
substrat, la mosaique passe la collision, la fondation et le test de flottement
sans un seul defaut, et tombe en morceaux des qu'on la souleve. Seul H5 le voit
(cf. test_naive_mosaic_is_rejected_by_the_kernel).

Le substrat est donc fait de deux couches de plates 2x4 croisees : la couche
haute chevauche quatre plates de la couche basse et les solidarise. C'est le
running bond, la plus ancienne technique de macon.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

from .catalog import CATALOG, PartInstance, place, place_at
from .collision import CollisionGeometry
from .imaging import _REENCODAGE, Image, crop_to_ratio, resample_box
from .imaging import _TABLE_LUMIERE as _LUMIERE
from .lego import PLATE_HEIGHT_LDU, STUD_PITCH_LDU
from .rotations import ROT_Z_90
from .palette import LegoColor, Palette, delta_e
from .search import PlacedPart

__all__ = [
    "Mosaic",
    "TilePlacement",
    "tile_id",
    "TILE_SET_MINIMAL",
    "TILE_SET_STANDARD",
    "TILE_SET_LARGE",
    "quantize",
    "DITHER_AUTO_MIN_GAIN",
    "PaletteCost",
    "palette_cost_curve",
    "cheapest_palette",
    "cost_of_grid",
    "build",
    "from_image",
    "preview",
    "fidelity",
    "blending_tiles",
]

VISUAL_ACUITY_ARCMIN = 1.0
"""Pouvoir separateur de l'oeil humain : environ une minute d'arc."""


def blending_tiles(distance_m: float, stud_mm: float = 8.0) -> int:
    """Combien de tuiles voisines l'oeil FUSIONNE a cette distance.

    C'est ce qui tranche la question du tramage, et ce n'est pas une affaire de
    gout. Un tenon fait 8 mm ; a 1,5 m l'oeil separe 0,44 mm. Il faudrait
    reculer a 55 m pour que deux tuiles voisines se confondent — c'est-a-dire
    regarder une toile de 38 cm depuis l'autre bout d'un terrain de football.

    Consequence directe : sur une mosaique LEGO, la seule mesure de fidelite
    honnete est tuile a tuile (block = 1). Toute mesure a une distance de
    regard superieure decrit une situation qui n'existe pas — et fait paraitre
    bon un tramage que l'oeil verra comme un damier.
    """
    if distance_m <= 0 or stud_mm <= 0:
        raise ValueError("distance et taille de tenon doivent etre positives")
    acuite_mm = (VISUAL_ACUITY_ARCMIN / 60) * (3.141592653589793 / 180) * distance_m * 1000
    return max(1, int(acuite_mm / stud_mm))

# Jeux de tuiles. Fusionner des tuiles voisines de meme couleur ne change
# aucune COULEUR — une 1x4 rouge montre exactement les memes quatre tenons
# rouges que quatre 1x1 — et divise le nombre de pieces par deux.
#
# Mais elle change la SURFACE, et ce depot a d'abord affirme le contraire. Une
# 1x4 n'a pas de joint interne la ou quatre 1x1 en ont trois : le resultat
# n'est plus la grille reguliere des sets LEGO Art officiels, c'est un appareil
# a joints decales, comme un mur de briques. Les sets officiels n'emploient que
# des 1x1, et c'est sans doute pour cette raison. `preview(..., seams=True)`
# montre la difference avant de commander.
#
# Mesure sur un paysage 48x48, palette officielle :
#
#   references employees     pieces   lots a commander
#   1x1 seule                  2304   15
#   1x1, 1x2                   1571   23      -32 %
#   1x1, 1x2, 1x4              1283   30      -44 %   <- defaut
#   + 1x3                      1234   37      -46 %
#   + 1x6, 1x8                 1105   50      -52 %
#
# Le defaut s'arrete a trois references : au-dela, chaque point de pieces gagne
# coute plusieurs lots supplementaires a trouver, et les tuiles longues sont
# rares dans beaucoup de couleurs. Le 1x3 coute sept lots pour deux points.
TILE_SET_MINIMAL = ("3070b",)
TILE_SET_STANDARD = ("3070b", "3069b", "2431")
TILE_SET_LARGE = ("3070b", "3069b", "63864", "2431", "6636", "4162")

SUBSTRATE_DESIGN = "3020"   # Plate 2 x 4
PANEL_DESIGN = "91405"      # Plate 16 x 16, celle des sets LEGO Art
TILE_DESIGN = "3070b"       # Tile 1 x 1 with Groove
SUBSTRATE_COLOR = 71        # Light Bluish Gray : invisible sous la mosaique

SEAM_DARKENING = 0.62
"""Assombrissement du joint entre deux pieces, pour l'apercu. Sur du vrai LEGO
le joint est une ligne d'ombre fine ; ce n'est pas une valeur mesuree, c'est un
reperage — il sert a VOIR le motif des joints, pas a le simuler."""


def tile_id(row: int, column: int) -> str:
    """Identifiant de la tuile en (ligne, colonne). Une seule definition.

    Le fascicule doit pouvoir retrouver la piece qui realise un pixel. Que ce
    schema soit ecrit a deux endroits, et les deux divergeront un jour.
    """
    return f"T{row}_{column}"


@dataclass(frozen=True)
class Mosaic:
    """Resultat du solveur : la grille voulue et le modele qui la realise."""

    studs_x: int
    studs_y: int
    grid: Tuple[Tuple[LegoColor, ...], ...]  # grid[ligne][colonne], ligne 0 = haut
    placed_parts: Mapping[str, PlacedPart]
    geometries: Mapping[str, CollisionGeometry]
    instances: Mapping[str, PartInstance]
    tiles: Tuple[TilePlacement, ...] = ()
    """Les tuiles reellement posees, dans l'ordre de lecture. La notice les lit
    ICI et non dans la grille : depuis la fusion, « 4 rouges » designe une seule
    piece 1x4, et faire prendre quatre 1x1 serait une consigne fausse."""

    def tile_id(self, row: int, column: int) -> str:
        return tile_id(row, column)

    @property
    def stud_count(self) -> int:
        """Tenons de l'oeuvre. C'est la RESOLUTION, elle ne bouge pas."""
        return self.studs_x * self.studs_y

    @property
    def tile_count(self) -> int:
        """PIECES de mosaique a poser. Depuis la fusion, ce n'est plus le
        nombre de tenons : une tuile 1x4 en couvre quatre a elle seule."""
        return len(self.tiles)

    @property
    def tile_ids(self) -> Tuple[str, ...]:
        """Identifiants des tuiles reellement posees, dans l'ordre de lecture."""
        return tuple(tile_id(t.row, t.column) for t in self.tiles)

    @property
    def part_count(self) -> int:
        return len(self.placed_parts)


def quantize(
    image: Image,
    palette: Palette,
    studs_x: int,
    studs_y: int,
    dither: object = "auto",
    fit: str = "crop",
    offset: float = 0.5,
) -> Tuple[Tuple[LegoColor, ...], ...]:
    """Image -> grille de couleurs LEGO.

    Trois etapes, dans cet ordre : CADRER, moyenner, quantifier.

    Cadrer d'abord. `fit="crop"` (defaut) decoupe la photo au rapport de la
    mosaique. `fit="stretch"` l'etire — ce que faisait la chaine, et c'etait un
    defaut grave : un cercle parfait dans une photo 4:3 ressortait a un rapport
    de 0,750, ecrase d'un quart. Un visage avec lui. Or presque toute photo est
    en 4:3 ou 3:2 et presque toute mosaique LEGO Art est carree.

    Moyenner ensuite, quantifier enfin. L'inverse — quantifier puis reduire —
    melangerait des couleurs de palette entre elles et produirait des teintes
    qui n'existent pas.

    `dither` accepte trois valeurs :

      False      quantification directe : chaque tuile prend la couleur de
                 palette la plus proche. Propre sur les aplats, brutal sur les
                 modeles.
      True       diffusion d'erreur de Floyd-Steinberg partout : l'ecart entre
                 la couleur voulue et la couleur posee est reporte sur les
                 tenons voisins, ce qui simule des teintes absentes.
      "adaptive" diffusion PONDEREE par l'ecart a la palette : pleine la ou la
                 couleur voulue n'existe pas, nulle la ou elle existe deja.

    Le defaut est "adaptive", et cette valeur a ete etablie, puis renversee,
    puis retablie. L'histoire vaut d'etre lue avant de la changer.

    1. Mesure : a trois tuiles de distance de regard, le tramage adaptatif
       ecrasait la quantification directe. Tout indiquait de l'activer.
    2. Correction : cette distance de regard n'existe pas. Un tenon fait 8 mm ;
       deux tuiles ne se confondent qu'a 55 m (voir `blending_tiles`). A toute
       distance reelle l'oeil voit chaque tuile — donc il voit le damier. Le
       defaut est repasse a False.
    3. Renversement : l'argument du point 2 est juste pour Floyd-Steinberg
       COMPLET — l'essai visuel le confirme sans appel, il transforme un ciel
       en neige, avec des tuiles roses et beiges dans du bleu. Mais il compare
       le tramage a « rien », alors que l'alternative reelle est une BANDE A
       BORD FRANC. Et l'oeil est plus sensible a un bord qu'a du grain : la
       detection de contours est son operation de base. Le tramage adaptatif
       n'echange donc pas « propre » contre « bruite », il echange un bord
       saillant contre une transition diffuse — et seulement la ou la palette
       ne sait vraiment pas produire la couleur.

    Mesure du renversement, palette officielle, trois images, en CIEDE2000 :

        image     variante      par tuile   tonal   pire   couleurs
        ciel      aucun              6,17    5,64   7,29          6
        ciel      adaptatif          6,40    4,71   6,69          7
        ciel      Floyd-S complet    9,15    1,99   5,49         19
        paysage   aucun              7,68    5,55  12,42         13
        paysage   adaptatif          8,32    3,76   7,77         15
        paysage   Floyd-S complet   11,29    2,76  10,11         28

    Floyd-Steinberg complet gagne sur le papier — c'est le meilleur chiffre
    tonal de la table — et perd a l'oeil. C'est le rappel qu'aucune de ces
    mesures ne remplace le fait de regarder.

    Le prix de l'adaptatif est une liste de course plus longue : +2 references
    sur ces essais, +8 sur une image tres texturee. `--couleurs N` la borne.

    La diffusion se fait en SERPENTIN — un rang sur deux parcouru a l'envers.
    Floyd-Steinberg parcouru toujours dans le meme sens produit des vermicules
    diagonaux, visibles a l'echelle de la tuile ; le serpentin les casse pour
    trois lignes de code, resserre les transitions et fait tomber le nombre de
    references de 18 a 15 sur le paysage. Jamais pire, mesure sur les trois.

    Piste essayee et REFUTEE : ponderer aussi par la DOUCEUR locale, pour ne
    tramer que les degrades et laisser les zones deja texturees tranquilles.
    L'idee semblait juste — c'est le critere du premier essai, avec le signe
    inverse. Mesure : 0,1 delta E d'ecart, dans le bruit. Un reglage qui ne
    gagne nulle part ne merite pas d'exister.
    """
    if studs_x <= 0 or studs_y <= 0:
        raise ValueError("dimensions de mosaique invalides")
    if dither == "auto":
        # Le tramage n'a pas de bon reglage universel : il en faut un PAR IMAGE.
        # Mesure sur six scenes — un ciel degrade gagne 1,7 delta E sur son pire
        # ecart tonal et vaut le grain ; un portrait aux grands aplats de peau
        # le PERD (10,17 -> 11,52) tout en gagnant huit points de grain. Un
        # defaut fixe se trompe forcement sur l'une des deux.
        #
        # Le critere est le PIRE ecart tonal, pas le moyen : le travail du
        # tramage est de supprimer les echecs francs — bandes, faux contours —,
        # pas de grappiller une moyenne. S'il n'y arrive pas, il n'ajoute que
        # du grain. La marge de 1 delta E est le seuil de perception : en deca,
        # on ne troque pas du grain visible contre un gain invisible.
        # Le cadrage et le reechantillonnage sont faits UNE fois et partages :
        # les repeter pour chacune des deux quantifications triplerait le
        # travail le plus cher de la chaine sur une photo de douze megapixels.
        cadree = _cadrer(image, studs_x, studs_y, fit, offset)
        reduite = resample_box(cadree, studs_x, studs_y)
        sans = _quantifier(reduite, palette, studs_x, studs_y, False)
        avec = _quantifier(reduite, palette, studs_x, studs_y, "adaptive")
        gain = fidelity(sans, cadree, 4)[1] - fidelity(avec, cadree, 4)[1]
        return avec if gain >= DITHER_AUTO_MIN_GAIN else sans

    if dither not in (True, False, "adaptive"):
        raise ValueError("dither vaut True, False, 'adaptive' ou 'auto'")
    image = _cadrer(image, studs_x, studs_y, fit, offset)
    reduced = resample_box(image, studs_x, studs_y)

    return _quantifier(reduced, palette, studs_x, studs_y, dither)


def _cadrer(image: Image, studs_x: int, studs_y: int, fit: str, offset: float) -> Image:
    """Cadrage prealable, isole pour n'etre fait qu'une fois en mode « auto »."""
    if fit not in ("crop", "stretch"):
        raise ValueError("fit vaut 'crop' ou 'stretch'")
    if fit == "crop":
        return crop_to_ratio(image, studs_x / studs_y, offset)
    return image


def _quantifier(reduced, palette, studs_x, studs_y, dither):
    """Grille reduite -> couleurs LEGO. Le cadrage et la moyenne sont deja faits."""
    if dither is False:
        return tuple(
            tuple(palette.nearest(reduced.pixel(x, y)) for x in range(studs_x))
            for y in range(studs_y)
        )

    strength = (
        _quantization_error_strength(reduced, palette, studs_x, studs_y)
        if dither == "adaptive"
        else [[1.0] * studs_x for _ in range(studs_y)]
    )

    buffer = [
        [list(map(float, reduced.pixel(x, y))) for x in range(studs_x)]
        for y in range(studs_y)
    ]
    grid: List[List[LegoColor]] = []
    for y in range(studs_y):
        # Serpentin : un rang sur deux a l'envers, diffusion miroir avec lui.
        sens = -1 if y % 2 else 1
        row: List[Optional[LegoColor]] = [None] * studs_x
        for x in range(studs_x - 1, -1, -1) if sens < 0 else range(studs_x):
            wanted = tuple(min(255, max(0, round(v))) for v in buffer[y][x])
            chosen = palette.nearest(wanted)
            row[x] = chosen
            facteur = strength[y][x]
            if facteur <= 0:
                continue
            error = [
                (buffer[y][x][i] - chosen.rgb[i]) * facteur for i in range(3)
            ]
            for dx, dy, weight in ((1, 0, 7), (-1, 1, 3), (0, 1, 5), (1, 1, 1)):
                nx, ny = x + dx * sens, y + dy
                if 0 <= nx < studs_x and 0 <= ny < studs_y:
                    for i in range(3):
                        buffer[ny][nx][i] += error[i] * weight / 16
        grid.append(row)
    return tuple(tuple(row) for row in grid)


DITHER_NEGLIGIBLE_DELTA_E = 4.0
"""En deca de cet ecart a la palette, la couleur voulue existe deja : tramer ne
ferait que salir une tuile deja juste."""

DITHER_FULL_DELTA_E = 16.0
"""Au dela, la couleur voulue est franchement absente de la palette : seule la
diffusion d'erreur peut la simuler."""

DITHER_AUTO_MIN_GAIN = 1.0
"""Gain minimal, sur le PIRE ecart tonal, pour que « auto » decide de tramer.

Un delta E : le seuil sous lequel l'oeil exerce ne distingue plus deux couleurs
cote a cote. En deca, on troquerait du grain visible contre un gain invisible."""

DITHER_MAX_STRENGTH = 0.5
"""Fraction maximale de l'erreur diffusee, meme quand la palette est tres loin.

Ce n'est pas un reglage au jugement : c'est le GENOU de la courbe, mesure. Au
dela, la diffusion n'achete plus rien et ne fait qu'ajouter du grain.

    plafond   tonal   pire   grain invente (delta E de plus que la photo)
       0,00    5,72  13,12          +0,52
       0,35    4,79  11,00          +4,01
       0,50    4,25   8,54          +5,52
       1,00    4,08   8,54          +6,06

A 0,50 le pire ecart tonal a deja rejoint celui du tramage plein. Passer a 1,00
gagne 0,17 delta E et coute un demi-point de grain — et ce grain se voit : le
coin de ciel lavande d'une photo d'essai se criblait de tuiles blanches et
roses. Le grain est mesure comme l'exces de variation d'une tuile a sa voisine
par rapport a ce que la photo en contient au meme pas : c'est de la texture
INVENTEE, celle qui n'est dans aucune photo."""


def _quantization_error_strength(
    reduced: Image, palette: Palette, studs_x: int, studs_y: int
):
    """Force de tramage par tuile, de 0 a 1, selon l'ECART A LA PALETTE.

    Premiere version de ce critere : le contraste local de l'image. La mesure
    l'a refute — un aplat gris clair, parfaitement uniforme, gagnait pourtant
    enormement au tramage. La raison est evidente apres coup : ce qui appelle
    le tramage n'est pas que l'image varie, c'est que la couleur VOULUE
    n'existe pas dans la palette. Un aplat rouge vif tombe pile sur une couleur
    LEGO : le tramer ne peut que le degrader. Un aplat gris-vert ne tombe sur
    rien : seul le melange de deux tuiles voisines peut le rendre.

    Le critere est donc l'erreur de quantification elle-meme.
    """
    force = []
    for y in range(studs_y):
        ligne = []
        for x in range(studs_x):
            voulue = reduced.pixel(x, y)
            ecart = delta_e(voulue, palette.nearest(voulue).rgb)
            ligne.append(
                min(
                    DITHER_MAX_STRENGTH,
                    max(
                        0.0,
                        (ecart - DITHER_NEGLIGIBLE_DELTA_E)
                        / (DITHER_FULL_DELTA_E - DITHER_NEGLIGIBLE_DELTA_E),
                    ),
                )
            )
        force.append(ligne)
    return force


def fidelity(
    grid: Tuple[Tuple[LegoColor, ...], ...],
    image: Image,
    block: int = 1,
) -> Tuple[float, float]:
    """(ecart moyen, ecart maximal) entre la mosaique et l'image, en delta E.

    Deux lectures, selon `block`, et les deux sont necessaires.

    `block=1` — FIDELITE PAR TUILE. Chaque tenon contre la zone qu'il remplace.
    C'est la mesure de la finesse : elle est bornee par la palette.

    `block>1` — JUSTESSE TONALE. On compare la lumiere moyenne de regions de
    block x block tuiles. L'oeil n'a pas besoin de fusionner les tuiles pour
    juger qu'une zone est trop sombre : il integre les grandes surfaces, et une
    erreur systematique s'y voit a toute distance. C'est cette mesure, et elle
    seule, qui a revele que l'echantillonnage moyennait des octets sRGB au lieu
    de la lumiere — 24 delta E d'erreur tonale au pire, ramenes a 9.

    L'ancienne lecture de `block` — « le nombre de tuiles que l'oeil fusionne »,
    donc 1 a toute distance humaine — n'etait pas fausse, elle etait trop
    etroite : elle ne laissait pas poser la question tonale.
    """
    if block < 1:
        raise ValueError("la distance de regard se compte en tuiles, au moins une")

    studs_y = len(grid)
    studs_x = len(grid[0])
    rendered = _render_rgb(grid)
    reference = resample_box(image, studs_x, studs_y)

    ecarts = []
    for y0 in range(0, studs_y, block):
        for x0 in range(0, studs_x, block):
            zone = [
                (x, y)
                for y in range(y0, min(y0 + block, studs_y))
                for x in range(x0, min(x0 + block, studs_x))
            ]
            moyenne_rendue = _average((rendered[y][x] for x, y in zone), len(zone))
            moyenne_source = _average((reference.pixel(x, y) for x, y in zone), len(zone))
            ecarts.append(delta_e(moyenne_rendue, moyenne_source))
    return (sum(ecarts) / len(ecarts), max(ecarts))


def _render_rgb(grid):
    return [[color.rgb for color in row] for row in grid]


def _average(couleurs, count: int):
    """Moyenne d'un groupe de couleurs, EN LUMIERE LINEAIRE.

    Meme raison qu'a l'echantillonnage : sRGB est un encodage en puissance, et
    en moyenner les octets n'a pas de sens physique. Une mesure faite sur la
    mauvaise grandeur ne mesure pas la bonne chose.
    """
    total = [0.0, 0.0, 0.0]
    for couleur in couleurs:
        for i in range(3):
            total[i] += _LUMIERE[couleur[i]]
    return tuple(_REENCODAGE[round(65535 * value / count)] for value in total)


@dataclass(frozen=True)
class TilePlacement:
    """Une tuile de la mosaique : ou elle commence, combien de tenons elle couvre."""

    row: int
    column: int
    length: int
    design_id: str
    color: LegoColor


def _references_par_longueur(tiles: Sequence[str]):
    """Jeu de tuiles -> (longueur -> reference, longueurs decroissantes)."""
    par_longueur: Dict[int, str] = {}
    for design in tiles:
        piece = CATALOG[design]
        if piece.studs_x != 1 or piece.has_studs:
            raise ValueError(
                f"{design} n'est pas une tuile lisse 1 x N : une mosaique se "
                "termine par une surface plate, et la fusion se fait en ligne."
            )
        par_longueur[piece.studs_y] = design
    if 1 not in par_longueur:
        raise ValueError(
            "il faut au moins la tuile 1 x 1 : sans elle, un run de longueur "
            "premiere ne pourrait pas etre couvert exactement."
        )
    return par_longueur, sorted(par_longueur, reverse=True)


def _decoupe_optimale(longueur: int, disponibles: Sequence[int]) -> List[int]:
    """Decoupe d'un run en un MINIMUM de tuiles. Programmation dynamique.

    Glouton « la plus longue d'abord » n'est pas optimal en general : avec des
    tuiles de 1, 3 et 4, un run de 6 se decoupe en 3+3 et non en 4+1+1. La DP
    coute quelques microsecondes et enleve la question.
    """
    infini = float("inf")
    cout = [0] + [infini] * longueur
    choix = [0] * (longueur + 1)
    for n in range(1, longueur + 1):
        for taille in disponibles:
            if taille <= n and cout[n - taille] + 1 < cout[n]:
                cout[n] = cout[n - taille] + 1
                choix[n] = taille
    if cout[longueur] == infini:  # pragma: no cover - la 1x1 est toujours la
        raise ValueError("aucune tuile ne permet de couvrir ce run")
    morceaux, reste = [], longueur
    while reste:
        morceaux.append(choix[reste])
        reste -= choix[reste]
    return morceaux


def _fusionner_ligne(colors, disponibles):
    """Ligne de couleurs -> (colonne, longueur, couleur) des tuiles a poser."""
    sortie = []
    colonne = 0
    largeur = len(colors)
    while colonne < largeur:
        fin = colonne
        while fin + 1 < largeur and colors[fin + 1].code == colors[colonne].code:
            fin += 1
        for taille in _decoupe_optimale(fin - colonne + 1, disponibles):
            sortie.append((colonne, taille, colors[colonne]))
            colonne += taille
    return sortie


def _decouper_axe(ancre: int, pas: int, longueur: int) -> List[Tuple[int, int]]:
    """Partition de [0, longueur) par un reseau de pas `pas` ancre en `ancre`.

    Les cellules qui debordent sont ROGNEES, jamais fusionnees avec leur
    voisine. Fusionner paraissait plus propre — ca evite les cellules d'un seul
    tenon — mais ca replace les plates sur la phase de la couche du dessous, et
    le fond entier se scinde alors en colonnes independantes. C'est le decalage
    qui fait tenir le fond ; on ne touche pas a sa phase.
    """
    cellules: List[Tuple[int, int]] = []
    borne = ancre
    while borne < longueur:
        debut, fin = max(borne, 0), min(borne + pas, longueur)
        if fin > debut:
            cellules.append((debut, fin))
        borne += pas
    return cellules


def _profondeur_utile(reste: int) -> int:
    """Longueur de la prochaine plate large, sans laisser un tenon seul."""
    if reste >= 6 or reste == 4:
        return 4
    if reste in (3, 5):
        return 3
    return reste  # 1 ou 2


def _plaques(largeur: int, profondeur: int, depart_y: int) -> List[Tuple[str, int, int]]:
    """Rectangle -> plates du catalogue le recouvrant EXACTEMENT.

    `depart_y` est l'ordonnee absolue du rectangle, en tenons. Elle n'est pas
    decorative : une colonne large d'un seul tenon — ce que le rognage produit
    au bord — ne peut relier la couche du dessous que dans l'autre sens, et une
    plate 1x2 n'enjambe un joint du dessous (aux multiples de 4 tenons) que si
    elle commence sur un tenon IMPAIR. Quand le depart est pair, on decale donc
    d'une 1x1. Sans ce decalage, les bandes du fond restent independantes et H5
    refuse le modele — verifie sur les 1521 formats de 2x2 a 40x40.

    Aucune rotation : toutes ces references existent deja dans le bon sens.
    """
    pieces: List[Tuple[str, int, int]] = []
    x = 0
    while x < largeur:
        if largeur - x >= 2:
            y = 0
            while y < profondeur:
                d = _profondeur_utile(profondeur - y)
                design = {4: "3020", 3: "3021", 2: "3022"}.get(d)
                if design is None:  # profondeur 1 : oeuvre d'un seul tenon
                    pieces.append(("3024", x, y))
                    pieces.append(("3024", x + 1, y))
                else:
                    pieces.append((design, x, y))
                y += d
            x += 2
        else:
            y = 0
            if depart_y % 2 == 0 and profondeur >= 3:
                pieces.append(("3024", x, y))
                y += 1
            while y < profondeur:
                if profondeur - y >= 2:
                    pieces.append(("3023", x, y))
                    y += 2
                else:
                    pieces.append(("3024", x, y))
                    y += 1
            x += 1
    return pieces


# Plates de fond utilisables pour la fusion, de la plus grande a la plus petite.
# Le fond ne se voit pas : sa seule qualite est de tenir. Le paver en 2x4
# coutait 657 pieces sur une 48x48, soit un tiers du modele pour quelque chose
# d'invisible. References verifiees contre parts.lst de LDraw.
PLAQUES_DE_FOND = (
    ("41539", 8, 8), ("3036", 6, 8), ("3958", 6, 6), ("3035", 4, 8),
    ("3032", 4, 6), ("3031", 4, 4), ("3034", 2, 8), ("3795", 2, 6),
    ("3020", 2, 4), ("3021", 2, 3), ("3022", 2, 2), ("3023", 1, 2),
    ("3024", 1, 1),
)


def _formes_de_fond(disponibles):
    """(largeur, profondeur, reference), plus grande aire d'abord, deux sens."""
    formes = set()
    for design, a, b in disponibles:
        formes.add((a, b, design))
        formes.add((b, a, design))
    return sorted(formes, key=lambda f: (-(f[0] * f[1]), -min(f[0], f[1])))


def _fusionner_plaques(poses, disponibles):
    """Fusionne des plates VOISINES en plates plus grandes.

    Le theoreme qui rend l'operation sure : contracter deux sommets d'un graphe
    connexe laisse un graphe connexe. Fusionner des plates DEJA POSEES revient
    exactement a contracter deux sommets du graphe de liaison — donc le fond ne
    peut pas se scinder, quelle que soit la taille de l'oeuvre.

    Repaver a partir de zero avec de grandes plates ne marche pas, et la mesure
    dit precisement pourquoi. Un reseau grossier 8x8 decale de moitie tient
    TOUJOURS tant qu'on le regarde au niveau du reseau : zero echec sur 441
    formats. Mais les cellules rognees du bord ne sont pas des pieces reelles —
    un rectangle 3x7 n'existe pas — et il faut les decouper en plates du
    catalogue. C'est cette decoupe qui realigne les joints sur ceux de la
    couche du dessous : 294 formats sur 441 se scindent alors.

    La fusion ne cree jamais de joint nouveau. Elle ne peut donc rien
    realigner, et le probleme ne se pose pas.

    `poses` : liste de (x, y, largeur, profondeur, reference), en tenons.
    """
    proprietaire: Dict[Tuple[int, int], int] = {}
    vivantes = list(poses)
    for index, (x, y, w, h, _) in enumerate(vivantes):
        for j in range(h):
            for i in range(w):
                proprietaire[(x + i, y + j)] = index

    for largeur, profondeur, design in _formes_de_fond(disponibles):
        for index in range(len(vivantes)):
            piece = vivantes[index]
            if piece is None:
                continue
            x0, y0 = piece[0], piece[1]
            if piece[2] == largeur and piece[3] == profondeur:
                continue
            couverts = set()
            entier = True
            for j in range(profondeur):
                for i in range(largeur):
                    autre = proprietaire.get((x0 + i, y0 + j))
                    if autre is None:
                        entier = False
                        break
                    couverts.add(autre)
                if not entier:
                    break
            if not entier or len(couverts) < 2:
                continue
            # Aucune des plates concernees ne doit deborder du rectangle vise :
            # sinon la fusion n'est plus une contraction, elle est un repavage.
            aire = 0
            for autre in couverts:
                voisine = vivantes[autre]
                if voisine is None:
                    entier = False
                    break
                vx, vy, vw, vh, _ = voisine
                if vx < x0 or vy < y0 or vx + vw > x0 + largeur or vy + vh > y0 + profondeur:
                    entier = False
                    break
                aire += vw * vh
            if not entier or aire != largeur * profondeur:
                continue
            for autre in couverts:
                vivantes[autre] = None
            vivantes[index] = (x0, y0, largeur, profondeur, design)
            for j in range(profondeur):
                for i in range(largeur):
                    proprietaire[(x0 + i, y0 + j)] = index
    return [piece for piece in vivantes if piece is not None]


def _verifier_fond(couches, studs_x, studs_y) -> None:
    """Refuse un fond qui ne tient pas d'un seul tenant.

    Deux plates posees cote a cote dans la meme couche ne se lient PAS : seul
    le recouvrement d'une couche a l'autre lie. Le fond est donc connexe si et
    seulement si le graphe biparti « couche 0 <-> couche 1, arete des qu'elles
    partagent un tenon » l'est. On le verifie par union-find en parcourant les
    tenons une fois : lineaire, exact, et ca ne code aucune regle biscornue.

    La regle biscornue existe pourtant — une mosaique d'un tenon de large tient
    jusqu'a quatre tenons de long et pas au-dela, deux tenons de haut jusqu'a
    deux de large — mais l'ecrire en dur serait une devinette a maintenir. Mieux
    vaut constater.

    Sans ce garde-fou, `build` rendait un modele que les invariants du noyau
    refusaient ensuite : l'information etait disponible ici, et gratuite.
    """
    if len(couches) != 2:  # pragma: no cover - le substrat croise en a deux
        return
    parent: Dict[Tuple[int, int], Tuple[int, int]] = {}

    def racine(noeud):
        while parent[noeud] != noeud:
            parent[noeud] = parent[parent[noeud]]
            noeud = parent[noeud]
        return noeud

    occupant: List[Dict[Tuple[int, int], Tuple[int, int]]] = []
    for rang, couche in enumerate(couches):
        carte = {}
        for index, (x, y, largeur, profondeur, _) in enumerate(couche):
            parent[(rang, index)] = (rang, index)
            for j in range(profondeur):
                for i in range(largeur):
                    carte[(x + i, y + j)] = (rang, index)
        occupant.append(carte)

    for tenon, bas in occupant[0].items():
        haut = occupant[1].get(tenon)
        if haut is None:
            continue
        a, b = racine(bas), racine(haut)
        if a != b:
            parent[a] = b

    composantes = {racine(noeud) for noeud in parent}
    if len(composantes) > 1:
        raise ValueError(
            f"une mosaique {studs_x} x {studs_y} ne tient pas ensemble : son "
            f"fond se scinde en {len(composantes)} morceaux independants. "
            "Une oeuvre d'un seul tenon de large ne peut pas etre tenue par un "
            "substrat croise au-dela de quelques tenons — il n'y a pas de place "
            "pour croiser. Elargissez-la."
        )


def _paver(add, prefixe, ancre_x, ancre_y, studs_x, studs_y, z, color,
           fusion: bool = True) -> int:
    """Pave l'emprise de l'oeuvre de plates sur un reseau ancre ailleurs.

    Sans le rognage, la couche decalee depasse de un tenon en x et de deux en y
    sur chaque bord : l'oeuvre finie porte un lisere de plate grise nue, visible,
    et paye en pieces. Mesure sur une 48x48 : substrat x -20..980 pour une
    mosaique x 0..960.
    """
    poses = []
    for x0, x1 in _decouper_axe(ancre_x, 2, studs_x):
        for y0, y1 in _decouper_axe(ancre_y, 4, studs_y):
            for design, dx, dy in _plaques(x1 - x0, y1 - y0, y0):
                piece = CATALOG[design]
                poses.append(
                    (x0 + dx, y0 + dy, piece.studs_x, piece.studs_y, design)
                )
    if fusion:
        poses = _fusionner_plaques(poses, PLAQUES_DE_FOND)

    for pose, (x, y, largeur, profondeur, design) in enumerate(poses):
        # La fusion peut avoir tourne une plate : on vise le coin, pas l'origine.
        piece = CATALOG[design]
        tournee = (piece.studs_x, piece.studs_y) != (largeur, profondeur)
        placed, geometry, instance = place_at(
            f"{prefixe}_{pose}",
            design,
            (x * STUD_PITCH_LDU, y * STUD_PITCH_LDU, z),
            orientation=ROT_Z_90 if tournee else None,
            color_id=color,
        )
        add(placed, geometry, instance)
    return poses


def build(
    grid: Tuple[Tuple[LegoColor, ...], ...],
    substrate_color: int = SUBSTRATE_COLOR,
    substrate: str = "crossed",
    tiles: Sequence[str] = TILE_SET_STANDARD,
) -> Mosaic:
    """Grille de couleurs -> modele complet : substrat + tuiles.

    Deux substrats, et le choix n'est pas cosmetique :

    "crossed" (defaut) deux couches de plates 2x4 croisees, rognees a l'emprise
              exacte de l'oeuvre. Cher en pieces — 657 pour une mosaique 48x48 —
              mais l'objet tient TOUT SEUL, sans lisere gris au bord. Le noyau
              le certifie sur les six invariants.

    "panels"  des plates 16x16, celles des sets LEGO Art officiels. Neuf pieces
              au lieu de 657. Mais deux plates posees cote a cote ne se lient
              pas : H5 refusera le modele, et il aura raison. Les sets
              officiels tiennent par leur CADRE, qui n'est pas une piece LEGO
              structurelle et n'est pas modelise ici. Ce substrat n'est donc
              utilisable qu'en connaissance de cause.

    Le noyau ne choisit pas a la place du concepteur ; il refuse de certifier
    ce qui ne tient pas.
    """
    if substrate not in ("crossed", "panels"):
        raise ValueError("substrate vaut 'crossed' ou 'panels'")
    par_longueur, longueurs = _references_par_longueur(tiles)
    if not grid or not grid[0]:
        raise ValueError("grille vide")
    studs_y = len(grid)
    studs_x = len(grid[0])
    if any(len(row) != studs_x for row in grid):
        raise ValueError("grille non rectangulaire")

    width = studs_x * STUD_PITCH_LDU
    depth = studs_y * STUD_PITCH_LDU

    parts: Dict[str, PlacedPart] = {}
    geometries: Dict[str, CollisionGeometry] = {}
    instances: Dict[str, PartInstance] = {}

    def enregistrer(placed, geometry, instance) -> None:
        parts[placed.part_id] = placed
        geometries[placed.part_id] = geometry
        instances[placed.part_id] = instance

    def add(part_id: str, design_id: str, translation, color: int) -> None:
        enregistrer(*place(part_id, design_id, translation, color_id=color))

    if substrate == "panels":
        if studs_x % 16 or studs_y % 16:
            raise ValueError(
                "le substrat 'panels' pave en plates 16x16 : il exige des cotes "
                f"multiples de 16, or {studs_x}x{studs_y} ne l'est pas. Un "
                "panneau qui depasse laisse une plate nue au bord de l'oeuvre."
            )
        panel = 16 * STUD_PITCH_LDU
        for i, x in enumerate(range(0, width, panel)):
            for j, y in enumerate(range(0, depth, panel)):
                add(f"P_{i}_{j}", PANEL_DESIGN, (x, y, 0), substrate_color)
        tile_z = PLATE_HEIGHT_LDU
    else:
        # Couche 0 : pavage de plates 2x4, a partir de l'origine.
        couche_basse = _paver(
            enregistrer, "S0", 0, 0, studs_x, studs_y, 0, substrate_color
        )

        # Couche 1 : meme pavage decale d'un tenon en x et de deux en y. Chaque
        # plate y chevauche quatre plates de la couche 0 : c'est ce decalage, et
        # lui seul, qui fait tenir le fond d'un seul tenant. Un pavage sans
        # decalage, ou decale sur un seul axe, se scinde en bandes disjointes —
        # H5 le voit.
        couche_haute = _paver(
            enregistrer, "S1", -1, -2, studs_x, studs_y,
            PLATE_HEIGHT_LDU, substrate_color,
        )
        _verifier_fond((couche_basse, couche_haute), studs_x, studs_y)
        tile_z = 2 * PLATE_HEIGHT_LDU

    # Derniere couche : la mosaique. La ligne 0 de l'image est en haut, donc au
    # y le plus grand : le modele se lit comme la photo, vu du dessus.
    #
    # La fusion se fait LIGNE PAR LIGNE et jamais en colonnes. Ce n'est pas une
    # limite technique — la rotation existe — mais un choix : la notice se lit
    # ligne par ligne, et une tuile a cheval sur deux lignes obligerait a la
    # poser depuis deux pages differentes.
    poses: List[TilePlacement] = []
    for row, colors in enumerate(grid):
        y = (studs_y - 1 - row) * STUD_PITCH_LDU
        for column, longueur, color in _fusionner_ligne(colors, longueurs):
            design = par_longueur[longueur]
            placed, geometry, instance = place_at(
                tile_id(row, column),
                design,
                (column * STUD_PITCH_LDU, y, tile_z),
                orientation=ROT_Z_90 if longueur > 1 else None,
                color_id=color.code,
            )
            parts[placed.part_id] = placed
            geometries[placed.part_id] = geometry
            instances[placed.part_id] = instance
            poses.append(TilePlacement(row, column, longueur, design, color))

    return Mosaic(
        studs_x, studs_y, grid, parts, geometries, instances, tuple(poses)
    )


def from_image(
    image: Image,
    palette: Palette,
    studs_x: int,
    studs_y: int,
    substrate_color: int = SUBSTRATE_COLOR,
    dither: object = "auto",
    substrate: str = "crossed",
    fit: str = "crop",
    offset: float = 0.5,
    tiles: Sequence[str] = TILE_SET_STANDARD,
) -> Mosaic:
    """Chaine complete : photo -> modele constructible."""
    return build(
        quantize(image, palette, studs_x, studs_y, dither, fit, offset),
        substrate_color,
        substrate,
        tiles,
    )


@dataclass(frozen=True)
class PaletteCost:
    """Ce que coute et ce que rend une palette de N couleurs, mesure."""

    palette: Palette
    per_tile: float      # ecart moyen tuile par tuile, delta E
    tonal_mean: float    # justesse d'ensemble, par blocs de 4x4 tuiles
    tonal_worst: float
    tiles: int           # pieces de mosaique apres fusion
    lots: int            # references x couleurs a commander


def palette_cost_curve(
    image: Image,
    palette: Palette,
    studs_x: int,
    studs_y: int,
    maximum: int = 20,
    tiles: Sequence[str] = TILE_SET_STANDARD,
    **quantize_options,
) -> Tuple[PaletteCost, ...]:
    """Cout et rendu de chaque taille de palette, sur la mosaique REELLE.

    `Palette.cheapest_subset` juge sur un proxy par grappes, qui ne voit que
    l'ecart tuile par tuile. Cet ecart plafonne des huit couleurs alors que la
    justesse tonale continue de s'ameliorer bien au-dela : le proxy conclurait
    « huit suffisent » pendant que la lecture d'ensemble du tableau se degrade
    d'un tiers. Ici on construit la mosaique et on mesure les deux.

    C'est plus lent — une quantification par taille — mais c'est la seule
    mesure qui reponde a la question posee : combien coute vraiment chaque
    sachet qu'on ajoute, et qu'est-ce qu'il achete.
    """
    from .catalog import bill_of_materials

    reduite = resample_box(image, studs_x, studs_y)
    pixels = [reduite.pixel(x, y) for y in range(studs_y) for x in range(studs_x)]
    courbe = palette.subset_curve(pixels, maximum)

    # Le substrat ne depend pas de la palette : on le mesure UNE fois et on
    # l'ajoute a chaque candidate, au lieu de rebatir un modele complet a
    # chaque fois pour en relire deux nombres.
    substrat = _cout_du_substrat(studs_x, studs_y)
    return tuple(
        _mesurer_palette(
            image,
            Palette(couleur for couleur, _ in courbe[:rang]),
            studs_x, studs_y, tiles, quantize_options, substrat,
        )
        for rang in range(1, len(courbe) + 1)
    )


def _cout_du_substrat(studs_x: int, studs_y: int) -> Tuple[int, int]:
    """(pieces, lots) du fond seul. Independant de la palette et de l'image."""
    from .catalog import bill_of_materials

    unie = Palette([LegoColor(SUBSTRATE_COLOR, "fond", (128, 128, 128))])
    grille = tuple(
        tuple(unie.colors[0] for _ in range(studs_x)) for _ in range(studs_y)
    )
    modele = build(grille, tiles=TILE_SET_MINIMAL)
    tuiles = set(modele.tile_ids)
    fond = {p: i for p, i in modele.instances.items() if p not in tuiles}
    return (
        modele.part_count - modele.tile_count,
        len({(i.design_id, i.color_id) for i in fond.values()}),
    )


def cost_of_grid(
    grid, tiles: Sequence[str] = TILE_SET_STANDARD
) -> Tuple[int, int]:
    """(pieces de mosaique, lots de tuiles) SANS construire le modele.

    La courbe de cout evalue une quinzaine de palettes. Construire une mosaique
    complete pour chacune — geometries, connecteurs, substrat, verification de
    connexite — coutait neuf secondes pour n'en lire que deux nombres. Or ces
    deux nombres se deduisent de la grille seule : la fusion se fait ligne par
    ligne et ne depend de rien d'autre.

    Le substrat est volontairement exclu : il ne depend pas de la palette, donc
    il ne discrimine aucune candidate. `palette_cost_curve` le rajoute une fois.
    """
    par_longueur, longueurs = _references_par_longueur(tiles)
    pieces = 0
    lots = set()
    for colors in grid:
        for _, longueur, color in _fusionner_ligne(colors, longueurs):
            pieces += 1
            lots.add((par_longueur[longueur], color.code))
    return pieces, len(lots)


def _mesurer_palette(image, palette, studs_x, studs_y, tiles, options,
                     substrat=(0, 0)) -> PaletteCost:
    """Mesure ce qu'une palette coute et ce qu'elle rend, sans bâtir le modele."""
    grille = quantize(image, palette, studs_x, studs_y, **options)
    tonal_moyen, tonal_pire = fidelity(grille, image, 4)
    pieces, lots = cost_of_grid(grille, tiles)
    return PaletteCost(
        palette,
        fidelity(grille, image, 1)[0],
        tonal_moyen,
        tonal_pire,
        pieces,
        lots + substrat[1],
    )


def cheapest_palette(
    image: Image,
    palette: Palette,
    studs_x: int,
    studs_y: int,
    tolerance: float = 1.0,
    maximum: int = 20,
    tiles: Sequence[str] = TILE_SET_STANDARD,
    **quantize_options,
) -> Tuple[Palette, PaletteCost, PaletteCost]:
    """La palette la MOINS CHERE dont le rendu reste proche de la reference.

    Trois corrections par rapport a la version precedente, chacune revelee par
    une mesure qui la contredisait :

    1. La palette ENTIERE fait partie des candidates. Elle etait absente, et
       sur un portrait elle se trouve etre a la fois la plus fidele et la MOINS
       chere en pieces — 776 tuiles contre 1458 pour sept couleurs. Reduire la
       palette elargit les ecarts, ce qui declenche le tramage, ce qui brise
       les suites de meme couleur, ce qui multiplie les pieces. Une fonction
       qui promet le meilleur cout ne peut pas ignorer ce candidat-la.

    2. Le critere retenu est le COUT — pieces d'abord, lots ensuite — et non la
       taille de la palette. Une palette plus petite n'est pas moins chere par
       definition ; c'etait pourtant l'hypothese implicite.

    3. La reference est la palette entiere, pas le meilleur de chaque critere
       pris separement. Les deux criteres sont optimises par des palettes
       differentes : exiger d'etre a `tolerance` du meilleur des DEUX ne
       laissait, sur un portrait, aucune candidate admissible.

    Une candidate est admissible si elle ne degrade NI l'ecart par tuile NI la
    justesse tonale de plus de `tolerance` par rapport a la palette entiere.
    Parmi les admissibles, on prend la moins chere.
    """
    if tolerance < 0:
        raise ValueError("une tolerance est positive")
    courbe = list(
        palette_cost_curve(
            image, palette, studs_x, studs_y, maximum, tiles, **quantize_options
        )
    )
    if len(palette) > len(courbe):
        courbe.append(
            _mesurer_palette(
                image, palette, studs_x, studs_y, tiles, quantize_options,
                _cout_du_substrat(studs_x, studs_y),
            )
        )
    reference = courbe[-1]
    admissibles = [
        cout
        for cout in courbe
        if cout.per_tile <= reference.per_tile + tolerance
        and cout.tonal_mean <= reference.tonal_mean + tolerance
    ]
    retenu = min(admissibles or [reference], key=lambda c: (c.tiles, c.lots))
    return retenu.palette, retenu, reference


def preview(mosaic: Mosaic, scale: int = 8, seams: bool = False) -> Image:
    """Apercu du rendu, un carre par tenon. Sert a juger a l'oeil.

    `seams=True` trace les JOINTS REELS entre pieces, et pas la grille des
    tenons. La difference n'est pas cosmetique et elle contredit ce que ce
    depot a d'abord affirme : fusionner les tuiles ne change pas les couleurs,
    mais change la SURFACE. Une tuile 1x4 n'a pas de joint interne la ou quatre
    1x1 en ont trois, et le resultat n'est plus la grille reguliere des sets
    LEGO Art officiels — c'est un appareil a joints decales, comme un mur de
    briques. Les sets officiels n'emploient que des 1x1, et c'est sans doute
    pour cette raison.

    Le choix reste au concepteur (`tiles=TILE_SET_MINIMAL` rend la grille
    uniforme, deux fois plus chere), mais il doit pouvoir le VOIR avant de
    commander. D'ou cette option.
    """
    if scale <= 0:
        raise ValueError("echelle invalide")
    width = mosaic.studs_x * scale
    height = mosaic.studs_y * scale
    data = bytearray()
    for y in range(height):
        row = mosaic.grid[y // scale]
        ligne = bytearray()
        for color in row:
            ligne.extend(bytes(color.rgb) * scale)
        data.extend(ligne)

    if seams and scale >= 3:
        def assombrir(px: int, py: int) -> None:
            index = (py * width + px) * 3
            data[index : index + 3] = bytes(
                round(canal * SEAM_DARKENING) for canal in data[index : index + 3]
            )

        for pose in mosaic.tiles:
            x0, y0 = pose.column * scale, pose.row * scale
            largeur = pose.length * scale
            for decalage in range(scale):
                assombrir(x0, y0 + decalage)
                assombrir(min(width - 1, x0 + largeur - 1), y0 + decalage)
            for decalage in range(largeur):
                colonne = min(width - 1, x0 + decalage)
                assombrir(colonne, y0)
                assombrir(colonne, min(height - 1, y0 + scale - 1))

    return Image(width, height, bytes(data))
