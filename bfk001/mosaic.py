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
from .lego import BRICK_HEIGHT_LDU, PLATE_HEIGHT_LDU, STUD_PITCH_LDU
from .rotations import ROT_Z_90
from .palette import (PROVISIONAL_PALETTE, LegoColor, Palette, delta_e,
                      delta_e_selection, srgb_to_lab)
from .search import PlacedPart

__all__ = [
    "Mosaic",
    "TilePlacement",
    "tile_id",
    "TILE_SET_MINIMAL",
    "TILE_SET_ART",
    "TILE_SET_STANDARD",
    "TILE_SET_LARGE",
    "quantize",
    "denoise",
    "isolated_tiles",
    "DENOISE_TOLERANCE",
    "DITHER_AUTO_MIN_GAIN",
    "PaletteCost",
    "palette_cost_curve",
    "cheapest_palette",
    "cost_of_grid",
    "build",
    "from_image",
    "preview",
    "frame_courses",
    "FRAME_BRICKS",
    "FRAME_COLOR",
    "FRAME_THICKNESS",
    "relief_from_luminance",
    "relief_from_image",
    "relief_edge_alignment",
    "etage_field",
    "smooth_relief",
    "relief_speckle",
    "relief_plateaus",
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
TILE_SET_ART = ("98138",)
"""Tuiles RONDES, comme les mosaiques LEGO Art officielles. Aucune fusion
possible — elles n'existent qu'en 1x1 — donc le prix plein : un tenon, une
piece. C'est l'aspect qu'on achete, en trame de points plutot qu'en aplats."""
TILE_SET_STANDARD = ("3070b", "3069b", "2431")
TILE_SET_LARGE = ("3070b", "3069b", "63864", "2431", "6636", "4162")

SUBSTRATE_DESIGN = "3020"   # Plate 2 x 4
PANEL_DESIGN = "91405"      # Plate 16 x 16, celle des sets LEGO Art
TILE_DESIGN = "3070b"       # Tile 1 x 1 with Groove
SUBSTRATE_COLOR = 71        # Light Bluish Gray : invisible sous la mosaique

FRAME_BRICKS = ("3010", "3004", "3005")
"""Briques du cadre : 1x4, 1x2, 1x1. Le catalogue n'en contient pas de plus
longues, et je n'en ajoute pas sans avoir verifie leurs cotes dans une piece
LDraw reelle. La decoupe optimale (`_decoupe_optimale`) fait le reste."""

FRAME_COLOR = 0             # Black : le cadre des sets LEGO Art
FRAME_THICKNESS = 2
"""Epaisseur du cadre, en tenons. Deux, comme les sets officiels : un tenon
fait un lisere, trois mange la place sans rien ajouter."""


RELIEF_LIGHTING = 0.22
"""Force de l'eclairage simule d'une marche de relief, par niveau d'ecart.
Reperage visuel, pas une grandeur physique."""

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

    frame: int = 0
    """Epaisseur du cadre, en tenons. 0 : oeuvre sans cadre."""
    frame_color: int = FRAME_COLOR
    frame_courses: int = 0
    """Assises de briques du cadre. Zero quand il n'y a pas de cadre."""

    def tile_id(self, row: int, column: int) -> str:
        return tile_id(row, column)

    @property
    def outer_x(self) -> int:
        """Largeur HORS TOUT, cadre compris, en tenons."""
        return self.studs_x + 2 * self.frame

    @property
    def outer_y(self) -> int:
        return self.studs_y + 2 * self.frame

    @property
    def frame_count(self) -> int:
        """Briques du cadre. Le reste des pieces est l'oeuvre et son fond."""
        return sum(1 for nom in self.placed_parts if nom.startswith("C"))

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
    offset=0.5,
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


DENOISE_TOLERANCE = 4.0
"""Ecart supplementaire tolere, en delta E, pour effacer une tuile isolee.

Ce n'est pas un seuil de perception : c'est le prix qu'on accepte de payer sur
UNE tuile pour en gagner la coherence. Mesure a 4, sur trois images, la
degradation moyenne va de 0,00 a 0,03 delta E — invisible — pour 5 a 6 % de
pieces en moins et 40 a 75 % de tuiles isolees en moins.

A zero, rien n'est efface.
"""


def isolated_tiles(grid):
    """Les tuiles dont aucun voisin orthogonal ne partage la couleur.

    C'est presque toujours un artefact de quantification et non un detail de
    la photo : une tuile qui ne ressemble a aucune de ses quatre voisines
    n'existait pas dans l'image, elle est nee du choix de palette. Elle coute
    en plus une piece a elle seule, et brise la suite qui la traverse.
    """
    hauteur, largeur = len(grid), len(grid[0]) if grid else 0
    seules = []
    for y in range(hauteur):
        for x in range(largeur):
            voisins = [
                (vy, vx) for vy, vx in ((y - 1, x), (y + 1, x),
                                        (y, x - 1), (y, x + 1))
                if 0 <= vy < hauteur and 0 <= vx < largeur
            ]
            if voisins and all(grid[vy][vx].code != grid[y][x].code
                               for vy, vx in voisins):
                seules.append((y, x))
    return tuple(seules)


def denoise(grid, image: Image, tolerance: float = DENOISE_TOLERANCE,
            fit: str = "crop", offset=0.5):
    """Efface les tuiles isolees quand ca ne coute presque rien.

    Une tuile isolee prend la couleur DOMINANTE de ses voisines, a deux
    conditions, et les deux comptent :

    1. au moins deux voisines partagent cette couleur. Une tuile entouree de
       quatre couleurs differentes est dans une zone de detail, pas dans un
       aplat : l'effacer inventerait une uniformite qui n'existe pas ;
    2. l'ecart a la PHOTO ne s'aggrave pas de plus de `tolerance`. C'est ce
       qui protege les vrais details isoles — un oeil sombre au milieu d'une
       joue depasse largement quatre delta E et reste.

    Mesure a la tolerance par defaut, palette officielle, 48 tenons :

        image        isolees      pieces      ecart par tuile
        velo         142 -> 90    867 -> 811  7,82 -> 7,84
        tournesols    66 -> 17    834 -> 791  6,16 -> 6,19
        portrait      31 -> 20   1024 -> 1017 10,55 -> 10,56

    Le gain est double et il va dans le meme sens : moins de grain a l'oeil,
    moins de pieces a poser. Le cout tient dans la deuxieme decimale.
    """
    if tolerance < 0:
        raise ValueError("une tolerance de debruitage est positive")
    if not grid or not grid[0]:
        raise ValueError("grille vide")
    if tolerance == 0:
        return grid
    hauteur, largeur = len(grid), len(grid[0])
    reduite = resample_box(
        _cadrer(image, largeur, hauteur, fit, offset), largeur, hauteur
    )
    sortie = [list(rang) for rang in grid]
    for y, x in isolated_tiles(grid):
        voisins = [
            grid[vy][vx] for vy, vx in ((y - 1, x), (y + 1, x),
                                        (y, x - 1), (y, x + 1))
            if 0 <= vy < hauteur and 0 <= vx < largeur
        ]
        compte: Dict[int, int] = {}
        for couleur in voisins:
            compte[couleur.code] = compte.get(couleur.code, 0) + 1
        code, nombre = max(compte.items(), key=lambda item: (item[1], -item[0]))
        if nombre < 2:
            continue
        candidat = next(c for c in voisins if c.code == code)
        pixel = reduite.pixel(x, y)
        avant = delta_e_selection(pixel, grid[y][x].rgb)
        apres = delta_e_selection(pixel, candidat.rgb)
        if apres - avant <= tolerance:
            sortie[y][x] = candidat
    return tuple(tuple(rang) for rang in sortie)


def _cadrer(image: Image, studs_x: int, studs_y: int, fit: str, offset) -> Image:
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
    level: int = 0
    """Elevation, en epaisseurs de plate. 0 pour une oeuvre plate."""


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


@dataclass(frozen=True)
class _CouleurEtagee:
    """Une couleur a une altitude. Sert a interdire la fusion d'une marche.

    `_fusionner_ligne` regroupe par `.code` : en y mettant l'altitude, deux
    tuiles de meme couleur mais d'etages differents cessent d'etre fusionnables
    — ce qu'elles sont physiquement, puisqu'une piece unique ne peut pas etre a
    deux hauteurs.
    """

    color: LegoColor
    niveau: int

    @property
    def code(self):
        return (self.color.code, self.niveau)


def _verifier_relief(heights, studs_x: int, studs_y: int):
    """Normalise et controle la carte d'elevations."""
    if heights is None:
        return [[0] * studs_x for _ in range(studs_y)]
    if len(heights) != studs_y or any(len(ligne) != studs_x for ligne in heights):
        raise ValueError(
            f"la carte de relief doit faire {studs_x} x {studs_y}, comme l'oeuvre"
        )
    sortie = []
    for ligne in heights:
        rang = []
        for valeur in ligne:
            if isinstance(valeur, bool) or not isinstance(valeur, int) or valeur < 0:
                raise ValueError(
                    "une elevation est un entier positif d'epaisseurs de plate, "
                    f"pas {valeur!r}"
                )
            rang.append(valeur)
        sortie.append(rang)
    return sortie


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
    """(largeur, profondeur, reference), plus grande aire d'abord, deux sens.

    Le tri doit etre TOTAL, et il ne l'etait pas. La cle « aire, puis plus
    petit cote » laisse a egalite les deux orientations d'une meme plate — une
    2x4 et une 4x2 ont la meme aire et le meme petit cote. Huit des vingt-et-une
    formes etaient dans ce cas. Python departage alors les ex aequo par l'ordre
    d'iteration de l'ensemble, et cet ordre depend du hachage des CHAINES, donc
    de PYTHONHASHSEED, donc du lancement.

    Consequence mesuree avant correction : la meme photo, la meme commande, et
    des listes de courses differentes d'une execution a l'autre. Une notice
    imprimee ne correspondait plus forcement aux pieces commandees. Le defaut
    ne se voyait qu'avec du relief, seul chemin qui appelle cette fonction sur
    des formes de tailles variees.

    Les deux derniers termes de la cle n'ont donc aucune signification
    esthetique : ils ne sont la que pour rendre l'ordre total. A aire et petit
    cote egaux, on prend la reference dans l'ordre alphabetique, puis
    l'orientation la moins large.
    """
    formes = set()
    for design, a, b in disponibles:
        formes.add((a, b, design))
        formes.add((b, a, design))
    return sorted(formes, key=_cle_de_forme)


def _cle_de_forme(forme):
    """Ordre des formes de fond. Doit etre TOTAL — voir `_formes_de_fond`.

    Nommee plutot qu'ecrite en lambda pour que le test puisse verifier son
    injectivite sur le catalogue reel. Une cle a egalite rend le modele
    dependant du hachage, et un test qui recopierait la cle ne verifierait
    que sa propre copie.
    """
    largeur, profondeur, design = forme
    return (-(largeur * profondeur), -min(largeur, profondeur), design, largeur)


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


def _poser_couche_de_relief(add, prefixe, cellules, z, color) -> int:
    """Pose une couche de RELIEF : un ensemble quelconque de cellules, en
    plates fusionnees.

    Les cellules ne forment pas un rectangle — c'est la silhouette de ce que
    l'image veut relever. On part donc d'une plate 1x1 par cellule et on
    fusionne, ce qui est licite quelle que soit la forme : fusionner des plates
    deja posees est une contraction du graphe de liaison, et contracter ne
    peut pas deconnecter (voir `_fusionner_plaques`).
    """
    poses = [(x, y, 1, 1, "3024") for x, y in sorted(cellules)]
    poses = _fusionner_plaques(poses, PLAQUES_DE_FOND)
    for numero, (x, y, largeur, profondeur, design) in enumerate(poses):
        piece = CATALOG[design]
        tournee = (piece.studs_x, piece.studs_y) != (largeur, profondeur)
        add(*place_at(
            f"{prefixe}_{numero}",
            design,
            (x * STUD_PITCH_LDU, y * STUD_PITCH_LDU, z),
            orientation=ROT_Z_90 if tournee else None,
            color_id=color,
        ))
    return len(poses)


def frame_courses(tile_top_ldu: int, base_z: int) -> int:
    """Combien d'assises de briques pour que le cadre DEPASSE la mosaique.

    Un cadre a fleur de la surface n'est pas un cadre, c'est une bordure. Il
    faut qu'il porte une ombre sur l'oeuvre — c'est ce qui fait qu'un tableau
    encadre se lit comme un tableau. Une assise sans relief donne 16 LDU de
    lisere, soit 6,4 mm ; avec deux etages de relief la premiere assise
    arriverait pile a fleur, et il en faut donc deux.
    """
    assises = 1
    while base_z + assises * BRICK_HEIGHT_LDU <= tile_top_ldu:
        assises += 1
    return assises


def _decoupe_decalee(longueur: int, disponibles, decalage: int):
    """Decoupe d'un run, avec un DEPART decale pour croiser les joints.

    Deux assises decoupees a l'identique donnent un mur dont tous les joints
    sont alignes verticalement : il se fend le long de ces joints. Le decalage
    d'une assise sur l'autre est ce qui fait un mur — c'est le meme appareil
    que le fond croise, et la meme raison.
    """
    if decalage <= 0 or longueur <= decalage:
        return _decoupe_optimale(longueur, disponibles)
    return [decalage] + _decoupe_optimale(longueur - decalage, disponibles)


def _cadre(add, studs_x: int, studs_y: int, epaisseur: int, base_z: int,
           assises: int, color: int, bricks=FRAME_BRICKS) -> int:
    """Cadre en briques autour de l'emprise. Rend le nombre de pieces posees.

    L'emprise passee est celle du SUBSTRAT — mosaique plus cadre — et le cadre
    occupe l'anneau exterieur d'epaisseur `epaisseur`.

    Deux appareils se croisent, et aucun n'est decoratif :

    - EN PLAN, les bandes horizontales courent sur toute la largeur une assise
      sur deux, les bandes verticales l'autre. Sans cela les quatre angles
      seraient quatre joints verticaux traversants, et le cadre s'ouvrirait aux
      coins comme un cadre a onglet mal colle.
    - EN ELEVATION, la decoupe de chaque run part avec un decalage d'une assise
      sur l'autre, pour que les joints ne se superposent pas.
    """
    if epaisseur < 1:
        raise ValueError("un cadre fait au moins un tenon d'epaisseur")
    if assises < 1:
        raise ValueError("un cadre fait au moins une assise")
    longueurs = sorted(
        (CATALOG[design].studs_y for design in bricks), reverse=True
    )
    par_longueur = {CATALOG[design].studs_y: design for design in bricks}
    if 1 not in par_longueur:
        raise ValueError("il faut la brique 1x1 : sans elle, un run premier "
                         "ne pourrait pas etre couvert exactement")
    poses = 0
    for assise in range(assises):
        z = base_z + assise * BRICK_HEIGHT_LDU
        horizontales_pleines = assise % 2 == 0
        decalage = 2 if assise % 2 else 0
        bandes = []
        if horizontales_pleines:
            for y in list(range(epaisseur)) + list(
                    range(studs_y - epaisseur, studs_y)):
                bandes.append((0, y, studs_x, True))
            for x in list(range(epaisseur)) + list(
                    range(studs_x - epaisseur, studs_x)):
                bandes.append((x, epaisseur, studs_y - 2 * epaisseur, False))
        else:
            for x in list(range(epaisseur)) + list(
                    range(studs_x - epaisseur, studs_x)):
                bandes.append((x, 0, studs_y, False))
            for y in list(range(epaisseur)) + list(
                    range(studs_y - epaisseur, studs_y)):
                bandes.append((epaisseur, y, studs_x - 2 * epaisseur, True))
        for x0, y0, longueur, couchee in bandes:
            if longueur <= 0:
                continue
            curseur = 0
            for morceau in _decoupe_decalee(longueur, longueurs, decalage):
                design = par_longueur[morceau]
                x = x0 + (curseur if couchee else 0)
                y = y0 + (0 if couchee else curseur)
                add(*place_at(
                    f"C{assise}_{poses}", design,
                    (x * STUD_PITCH_LDU, y * STUD_PITCH_LDU, z),
                    orientation=ROT_Z_90 if couchee else None,
                    color_id=color,
                ))
                poses += 1
                curseur += morceau
    return poses


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
    heights: Optional[Sequence[Sequence[int]]] = None,
    frame: int = 0,
    frame_color: int = FRAME_COLOR,
) -> Mosaic:
    """Grille de couleurs -> modele complet : substrat + tuiles.

    `heights` donne l'elevation de chaque tuile, en epaisseurs de plate (3,2 mm
    chacune). None ou tout a zero : oeuvre plate, comportement d'origine.

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

    if frame < 0:
        raise ValueError("une epaisseur de cadre est positive")
    if frame and substrate == "panels":
        raise ValueError(
            "le substrat 'panels' n'accepte pas de cadre : ses panneaux ne se "
            "lient deja pas entre eux, y poser un cadre masquerait le probleme "
            "sans le resoudre"
        )
    # L'emprise du SUBSTRAT porte le cadre en plus de l'oeuvre ; la mosaique,
    # elle, garde sa taille et se decale vers l'interieur. Un cadre qui
    # rognerait l'image ne serait pas un cadre, ce serait un recadrage.
    emprise_x = studs_x + 2 * frame
    emprise_y = studs_y + 2 * frame
    width = emprise_x * STUD_PITCH_LDU
    depth = emprise_y * STUD_PITCH_LDU

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
            enregistrer, "S0", 0, 0, emprise_x, emprise_y, 0, substrate_color
        )

        # Couche 1 : meme pavage decale d'un tenon en x et de deux en y. Chaque
        # plate y chevauche quatre plates de la couche 0 : c'est ce decalage, et
        # lui seul, qui fait tenir le fond d'un seul tenant. Un pavage sans
        # decalage, ou decale sur un seul axe, se scinde en bandes disjointes —
        # H5 le voit.
        couche_haute = _paver(
            enregistrer, "S1", -1, -2, emprise_x, emprise_y,
            PLATE_HEIGHT_LDU, substrate_color,
        )
        _verifier_fond((couche_basse, couche_haute), emprise_x, emprise_y)
        tile_z = 2 * PLATE_HEIGHT_LDU

    # Derniere couche : la mosaique. La ligne 0 de l'image est en haut, donc au
    # y le plus grand : le modele se lit comme la photo, vu du dessus.
    #
    # La fusion se fait LIGNE PAR LIGNE et jamais en colonnes. Ce n'est pas une
    # limite technique — la rotation existe — mais un choix : la notice se lit
    # ligne par ligne, et une tuile a cheval sur deux lignes obligerait a la
    # poser depuis deux pages differentes.
    # Relief : une couche de plates par niveau, sous les tuiles qu'elle porte.
    elevations = _verifier_relief(heights, studs_x, studs_y)
    maximum = max((h for ligne in elevations for h in ligne), default=0)
    for niveau in range(1, maximum + 1):
        cellules = {
            (column + frame, studs_y - 1 - row + frame)
            for row in range(studs_y)
            for column in range(studs_x)
            if elevations[row][column] >= niveau
        }
        _poser_couche_de_relief(
            enregistrer, f"R{niveau}", cellules,
            tile_z + (niveau - 1) * PLATE_HEIGHT_LDU, substrate_color,
        )

    poses: List[TilePlacement] = []
    for row, colors in enumerate(grid):
        y = (studs_y - 1 - row + frame) * STUD_PITCH_LDU
        # La fusion ne franchit pas une marche : deux tuiles de meme couleur a
        # des altitudes differentes sont deux pieces, forcement.
        marquees = tuple(
            _CouleurEtagee(color, elevations[row][column])
            for column, color in enumerate(colors)
        )
        for column, longueur, marquee in _fusionner_ligne(marquees, longueurs):
            color = marquee.color
            design = par_longueur[longueur]
            placed, geometry, instance = place_at(
                tile_id(row, column),
                design,
                ((column + frame) * STUD_PITCH_LDU, y,
                 tile_z + elevations[row][column] * PLATE_HEIGHT_LDU),
                orientation=ROT_Z_90 if longueur > 1 else None,
                color_id=color.code,
            )
            parts[placed.part_id] = placed
            geometries[placed.part_id] = geometry
            instances[placed.part_id] = instance
            poses.append(
                TilePlacement(
                    row, column, longueur, design, color, elevations[row][column]
                )
            )

    assises = 0
    if frame:
        # Le cadre se pose APRES les tuiles : sa hauteur depend de la leur, et
        # le relief peut la faire monter d'une assise entiere.
        sommet = tile_z + maximum * PLATE_HEIGHT_LDU + PLATE_HEIGHT_LDU
        assises = frame_courses(sommet, tile_z)
        _cadre(enregistrer, emprise_x, emprise_y, frame, tile_z, assises,
               frame_color)

    return Mosaic(
        studs_x, studs_y, grid, parts, geometries, instances, tuple(poses),
        frame, frame_color, assises,
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
    offset=0.5,
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


def relief_from_luminance(
    grid, levels: int = 2, invert: bool = False, thresholds: str = "otsu"
) -> List[List[int]]:
    """Carte d'elevations tiree de la CLARTE des tuiles : clair = haut.

    C'est une CONVENTION, pas une mesure. Une photo ne contient aucune
    information de profondeur : rien dans le fichier ne dit qu'un visage est
    devant un mur. Elever selon la clarte est le parti du bas-relief — celui
    des medailles et des camees — et il fonctionne parce que l'oeil lit
    spontanement le clair comme proche et l'ombre comme creux.

    Il se trompe donc exactement la ou la photo contredit cette lecture : un
    sujet sombre sur fond clair sortira en creux. `invert` retourne la
    convention ; `build(heights=...)` accepte n'importe quelle carte si vous en
    avez une meilleure.

    ATTENTION : cette fonction lit la grille QU'ON LUI DONNE. Si cette grille
    est tramee, le relief herite du tramage et devient un lit de clous — un
    tiers des cases en tours isolees sur un portrait mesure. Passez par
    `relief_from_image`, qui lit une grille non tramee et regularise.

    `thresholds` decide OU tombent les marches, et c'est la question qui fait
    la difference entre une sculpture et une carte d'etat-major.

    "uniform" tranche la plage de clarte en parts egales. C'est ce que faisait
    cette fonction, et c'est un mauvais decoupage : les marches tombent au
    milieu des degrades, et quand la photo n'a pas de clarte a cet endroit,
    l'etage ne sert a rien tout en coutant ses plates. Mesure sur un portrait
    a trois etages : le decoupage uniforme n'emploie que les hauteurs 0 et 3 —
    trois couches de relief pour la silhouette qu'une seule donnait, 144
    pieces pour rien.

    "otsu" (defaut) place les seuils dans les creux de l'histogramme, la ou
    l'image se separe en regions.

    Nuance mesuree, et je l'avais d'abord surevaluee : sur une grille DEJA
    quantifiee, l'ecart entre les deux decoupages est faible, parce que la
    quantification a deja separe l'image en regions — elle a fait une part du
    travail d'Otsu. Le gros du gain apparait quand les seuils se posent sur la
    clarte continue, ce que fait `relief_from_image` : 0,85 de rendement
    contre 0,70, 9 plateaux contre 30, aucune case isolee contre 17.
    """
    if levels < 1:
        raise ValueError("un relief compte au moins un niveau")
    if thresholds not in ("otsu", "uniform"):
        raise ValueError("thresholds vaut 'otsu' ou 'uniform'")
    clartes = [[srgb_to_lab(c.rgb)[0] for c in ligne] for ligne in grid]
    plancher = min(v for ligne in clartes for v in ligne)
    plafond = max(v for ligne in clartes for v in ligne)
    if plafond - plancher < 1e-9:
        return [[0] * len(grid[0]) for _ in grid]
    if thresholds == "uniform":
        seuils = [plancher + (plafond - plancher) * (k + 1) / (levels + 1)
                  for k in range(levels)]
    else:
        seuils = _seuils_otsu(clartes, levels)
    return [
        [
            (levels - sum(1 for s in seuils if valeur >= s)) if invert
            else sum(1 for s in seuils if valeur >= s)
            for valeur in ligne
        ]
        for ligne in clartes
    ]


def _seuils_otsu(valeurs, nombre: int, bins: int = 128) -> List[float]:
    """Seuils d'Otsu multi-niveaux, par programmation dynamique.

    Otsu maximise la variance INTER-classes. Concretement : les seuils tombent
    dans les CREUX de l'histogramme, la ou l'image se separe vraiment en
    regions, au lieu de couper au milieu d'un degrade.

    L'exhaustif serait en bins^nombre — 128^4, quatre milliards. La
    programmation dynamique le ramene a bins^2 x nombre : `H(a, b)` ne depend
    que de l'intervalle, donc le meilleur decoupage en k classes de 0..b se
    deduit du meilleur decoupage en k-1 classes de 0..a-1.
    """
    plancher = min(v for ligne in valeurs for v in ligne)
    plafond = max(v for ligne in valeurs for v in ligne)
    if plafond - plancher < 1e-9:
        return [plancher] * nombre
    histogramme = [0] * bins
    for ligne in valeurs:
        for v in ligne:
            case = int((v - plancher) / (plafond - plancher) * bins)
            histogramme[min(bins - 1, case)] += 1
    poids = [0.0] * (bins + 1)
    moments = [0.0] * (bins + 1)
    for i in range(bins):
        poids[i + 1] = poids[i] + histogramme[i]
        moments[i + 1] = moments[i] + histogramme[i] * i

    def inertie(a: int, b: int) -> float:
        """Contribution de la classe a..b a la variance inter-classes."""
        masse = poids[b + 1] - poids[a]
        return 0.0 if masse == 0 else (moments[b + 1] - moments[a]) ** 2 / masse

    meilleur = [[0.0] * bins for _ in range(nombre + 2)]
    coupe = [[0] * bins for _ in range(nombre + 2)]
    for b in range(bins):
        meilleur[1][b] = inertie(0, b)
    for k in range(2, nombre + 2):
        for b in range(bins):
            score, arg = -1.0, 0
            for a in range(1, b + 1):
                valeur = meilleur[k - 1][a - 1] + inertie(a, b)
                if valeur > score:
                    score, arg = valeur, a
            meilleur[k][b] = score
            coupe[k][b] = arg
    bornes = []
    b = bins - 1
    for k in range(nombre + 1, 1, -1):
        a = coupe[k][b]
        bornes.append(a)
        b = a - 1
    bornes.reverse()
    return [plancher + (plafond - plancher) * a / bins for a in bornes]


def relief_edge_alignment(
    heights, image: Image, fit: str = "crop", offset=0.5
) -> float:
    """Rendement des marches du relief, entre 0 et 1. Se lit sur la PHOTO.

    Un relief ne se voit que par ses marches : une marche porte une ombre, le
    reste est plat. La question n'est donc pas « quelle hauteur » mais « ou
    tombent les frontieres ». Au milieu d'un degrade, on obtient une carte
    d'etat-major — des courbes de niveau qui ne designent rien. Sur les
    contours du sujet, on obtient une sculpture.

    On compare donc le contraste de la PHOTO le long des K marches reellement
    posees au contraste des K frontieres les plus contrastees qu'offre cette
    photo. 1,0 : on ne pouvait pas mieux placer K marches. 0,5 : la moitie du
    contraste disponible est gaspillee.

    La normalisation par K n'est pas un detail. La premiere version de cette
    mesure divisait par le contraste MOYEN, et elle etait fausse : un relief a
    une seule marche, posee sur le contour le plus fort, obtenait le meilleur
    score possible, et tout etage supplementaire le degradait mecaniquement.
    Elle recompensait le fait d'en faire moins.

    La reference est la photo et non la grille quantifiee : c'est la photo qui
    dit ou sont les contours, la grille n'en est qu'une approximation.
    """
    if not heights or not heights[0]:
        raise ValueError("carte d'elevations vide")
    studs_y, studs_x = len(heights), len(heights[0])
    reduite = resample_box(
        _cadrer(image, studs_x, studs_y, fit, offset), studs_x, studs_y
    )
    clartes = [[srgb_to_lab(reduite.pixel(x, y))[0] for x in range(studs_x)]
               for y in range(studs_y)]
    sous_marche, toutes = [], []
    for y in range(studs_y):
        for x in range(studs_x):
            for dy, dx in ((0, 1), (1, 0)):
                yy, xx = y + dy, x + dx
                if yy >= studs_y or xx >= studs_x:
                    continue
                ecart = abs(clartes[y][x] - clartes[yy][xx])
                toutes.append(ecart)
                if heights[y][x] != heights[yy][xx]:
                    sous_marche.append(ecart)
    if not sous_marche:
        return 0.0
    toutes.sort(reverse=True)
    plafond = toutes[:len(sous_marche)]
    moyenne_plafond = sum(plafond) / len(plafond)
    if moyenne_plafond < 1e-9:
        return 0.0
    return (sum(sous_marche) / len(sous_marche)) / moyenne_plafond


def smooth_relief(heights, passes: int = 1) -> List[List[int]]:
    """Regularise une carte d'elevations en PLATEAUX (mediane 3x3).

    Un bas-relief LEGO Art est fait de plateaux : de grandes regions a une
    meme hauteur, separees par une frontiere nette. Une elevation calculee
    case par case n'a aucune raison d'etre coherente. Une case relevee dont
    aucun voisin ne partage la hauteur n'est pas une sculpture, c'est un
    clou : l'oeil la lit comme du bruit, et elle coute a elle seule une tour
    de plates.

    La mediane est le bon filtre ici, et pas la moyenne. Elle ne cree aucune
    hauteur intermediaire — sa sortie est toujours une hauteur deja presente
    dans la fenetre — et elle preserve les marches franches au lieu de les
    biseauter. Une case isolee est minoritaire dans sa fenetre : elle
    disparait. Un plateau reste.

    Mesure sur les Tournesols, 48x48, deux etages, palette officielle :

        carte d'elevations        cases isolees   plateaux   pieces
        clarte de la grille                   5         16     1123
        + une passe de mediane                0          8     1113

    Moins de bruit ET moins de pieces. Une deuxieme passe n'apporte plus
    rien (7 isolees, 17 plateaux) : le bruit qui reste n'est pas isole, il
    est en amas, et un amas est une forme, pas une erreur.
    """
    if passes < 0:
        raise ValueError("un nombre de passes est positif")
    carte = [list(ligne) for ligne in heights]
    if not carte or not carte[0]:
        return carte
    hauteur, largeur = len(carte), len(carte[0])
    for _ in range(passes):
        suivante = []
        for y in range(hauteur):
            rang = []
            for x in range(largeur):
                fenetre = sorted(
                    carte[yy][xx]
                    for yy in range(max(0, y - 1), min(hauteur, y + 2))
                    for xx in range(max(0, x - 1), min(largeur, x + 2))
                )
                rang.append(fenetre[len(fenetre) // 2])
            suivante.append(rang)
        carte = suivante
    return carte


def relief_speckle(heights) -> int:
    """Nombre de cases dont AUCUN voisin orthogonal ne partage la hauteur.

    C'est la mesure du mouchetage. Zero ne veut pas dire « beau », mais toute
    valeur elevee veut dire « bruite » : ces cases sont des tours isolees.
    """
    carte = [list(ligne) for ligne in heights]
    if not carte or not carte[0]:
        return 0
    hauteur, largeur = len(carte), len(carte[0])
    total = 0
    for y in range(hauteur):
        for x in range(largeur):
            voisins = []
            if y:
                voisins.append(carte[y - 1][x])
            if y + 1 < hauteur:
                voisins.append(carte[y + 1][x])
            if x:
                voisins.append(carte[y][x - 1])
            if x + 1 < largeur:
                voisins.append(carte[y][x + 1])
            if voisins and all(v != carte[y][x] for v in voisins):
                total += 1
    return total


def relief_plateaus(heights) -> Tuple[int, ...]:
    """Tailles des PLATEAUX, du plus grand au plus petit.

    Un plateau est une composante connexe (4-voisinage) d'une meme hauteur.
    Peu de plateaux larges : une sculpture. Des centaines de plateaux d'une
    case : du grain. C'est le meme chiffre qui distingue les deux, et il se
    lit sans regarder l'image.
    """
    carte = [list(ligne) for ligne in heights]
    if not carte or not carte[0]:
        return ()
    hauteur, largeur = len(carte), len(carte[0])
    vus = [[False] * largeur for _ in range(hauteur)]
    tailles = []
    for y0 in range(hauteur):
        for x0 in range(largeur):
            if vus[y0][x0]:
                continue
            niveau = carte[y0][x0]
            pile = [(y0, x0)]
            vus[y0][x0] = True
            taille = 0
            while pile:
                y, x = pile.pop()
                taille += 1
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < hauteur and 0 <= xx < largeur:
                        if not vus[yy][xx] and carte[yy][xx] == niveau:
                            vus[yy][xx] = True
                            pile.append((yy, xx))
            tailles.append(taille)
    return tuple(sorted(tailles, reverse=True))


def relief_from_image(
    image: Image,
    studs_x: int,
    studs_y: int,
    levels: int = 2,
    invert: bool = False,
    passes: int = 1,
    thresholds: str = "otsu",
    fit: str = "crop",
    offset=0.5,
    **refuses,
) -> List[List[int]]:
    """Carte d'elevations lue sur la PHOTO. C'est le chemin a prendre.

    Le relief ne passe par aucune quantification : ni palette, ni tramage. Il
    lit la clarte de l'image reduite a la resolution de l'oeuvre, et decoupe
    cette clarte en etages aux seuils d'Otsu.

    Deux defauts sont evites, et ce sont deux defauts distincts.

    LE TRAMAGE. `relief_from_luminance` lit la grille qu'on lui donne, et la
    chaine lui donnait la grille tramee. Le tramage echange de la justesse
    tonale contre du bruit spatial, marche gagnant parce que l'oeil fond ce
    bruit dans les couleurs. Une elevation ne se fond jamais : une marche de
    3,2 mm porte une ombre, accroche la lumiere rasante, se voit de cote. Le
    damier que l'oeil devait ignorer devenait un lit de clous — 1473 des 3840
    cases d'un portrait en tours isolees, 1136 pieces, 22 % du modele.

    LE DECOUPAGE. Trancher la plage de clarte en parts egales pose les
    marches au milieu des degrades. Otsu les pose dans les creux de
    l'histogramme, la ou l'image se separe en regions.

    Les deux corrections sont complementaires, et aucune ne suffit seule.
    Tournesols 48x48, deux etages, `relief_edge_alignment` en reference :

        source des seuils      rendement  plateaux  isolees  pieces
        grille + uniforme           0,76         8        0    1128
        grille + otsu               0,76         8        0    1108
        clarte + uniforme           0,70        30       17    1145
        clarte + otsu               0,85         9        0    1114

    Lire la clarte SANS Otsu est le pire des quatre : la quantification, en
    aplatissant l'image en regions de couleur, faisait deja une part du
    travail d'Otsu, et s'en passer sans le remplacer perd au change. C'est
    Otsu qui rend la lecture directe payante, et la lecture directe qui rend
    Otsu payant.

    La palette n'entre pas dans le calcul, et ce n'est pas un oubli : le
    relief decrit la STRUCTURE de la photo, pas les briques disponibles. Deux
    palettes differentes donnent le meme relief.
    """
    if "dither" in refuses:
        raise TypeError(
            "le relief ne quantifie plus du tout : il lit la clarte de la "
            "photo. Un relief trame est un lit de clous (voir la docstring)"
        )
    if "palette" in refuses:
        raise TypeError(
            "le relief ne depend pas de la palette : il decrit la structure "
            "de la photo, pas les briques disponibles"
        )
    if refuses:
        raise TypeError(f"parametres inconnus : {sorted(refuses)}")
    if not isinstance(studs_x, int) or not isinstance(studs_y, int):
        # Le parametre `palette`, en deuxieme position, a disparu : le relief
        # n'en depend pas. Le dire ici evite une erreur incomprehensible dix
        # lignes plus bas.
        raise TypeError(
            "relief_from_image(image, studs_x, studs_y, ...) : la palette n'est "
            "plus un parametre, le relief ne depend pas des briques disponibles"
        )
    if levels < 1:
        raise ValueError("un relief compte au moins un niveau")
    if thresholds not in ("otsu", "uniform"):
        raise ValueError("thresholds vaut 'otsu' ou 'uniform'")
    reduite = resample_box(
        _cadrer(image, studs_x, studs_y, fit, offset), studs_x, studs_y
    )
    clartes = [[srgb_to_lab(reduite.pixel(x, y))[0] for x in range(studs_x)]
               for y in range(studs_y)]
    return etage_field(clartes, levels, invert, thresholds, passes)


def etage_field(values, levels: int = 2, invert: bool = False,
                thresholds: str = "otsu", passes: int = 1) -> List[List[int]]:
    """Une carte de valeurs quelconque -> des etages de plates.

    Sert deux fois : la clarte de la photo (le bas-relief par convention) et
    une carte de profondeur (la profondeur mesuree). Les deux ne different que
    par la grandeur qu'on etage — la mecanique du decoupage est la meme, et il
    n'y a aucune raison qu'elle existe en deux exemplaires.
    """
    if levels < 1:
        raise ValueError("un relief compte au moins un niveau")
    if thresholds not in ("otsu", "uniform"):
        raise ValueError("thresholds vaut 'otsu' ou 'uniform'")
    if not values or not values[0]:
        raise ValueError("carte de valeurs vide")
    plancher = min(v for ligne in values for v in ligne)
    plafond = max(v for ligne in values for v in ligne)
    if plafond - plancher < 1e-9:
        return [[0] * len(values[0]) for _ in values]
    if thresholds == "uniform":
        seuils = [plancher + (plafond - plancher) * (k + 1) / (levels + 1)
                  for k in range(levels)]
    else:
        seuils = _seuils_otsu(values, levels)
    brute = [
        [
            (levels - sum(1 for s in seuils if v >= s)) if invert
            else sum(1 for s in seuils if v >= s)
            for v in ligne
        ]
        for ligne in values
    ]
    return smooth_relief(brute, passes)


def preview(
    mosaic: Mosaic, scale: int = 8, seams: bool = False, relief: bool = False,
    frame_rgb=None,
) -> Image:
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

    if relief and any(pose.level for pose in mosaic.tiles):
        # Eclairage lambertien tres simple, lumiere en haut a gauche. C'est une
        # SIMULATION destinee a juger le relief avant de le construire, pas un
        # rendu physique : une marche de 3,2 mm ne projette pas cette ombre-la.
        # Sans elle, une vue de dessus ne montre strictement rien du relief, et
        # on ne peut pas decider s'il sert l'image.
        etage = {}
        for pose in mosaic.tiles:
            for decalage in range(pose.length):
                etage[(pose.row, pose.column + decalage)] = pose.level
        for row in range(mosaic.studs_y):
            for column in range(mosaic.studs_x):
                ici = etage.get((row, column), 0)
                haut = etage.get((row - 1, column), ici)
                gauche = etage.get((row, column - 1), ici)
                # Une face qui monte vers la lumiere s'eclaire, une qui
                # s'en detourne s'assombrit.
                facteur = 1.0 + RELIEF_LIGHTING * ((ici - haut) + (ici - gauche))
                facteur = max(0.35, min(1.6, facteur))
                if facteur == 1.0:
                    continue
                for dy in range(scale):
                    debut = ((row * scale + dy) * width + column * scale) * 3
                    for index in range(debut, debut + scale * 3):
                        data[index] = max(0, min(255, round(data[index] * facteur)))

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

    oeuvre = Image(width, height, bytes(data))
    if mosaic.frame:
        oeuvre = _entourer(oeuvre, mosaic, scale, frame_rgb)
    return oeuvre


def source_preview(reduite: Image, mosaic: Mosaic, scale: int = 8,
                   frame_rgb=None) -> Image:
    """La PHOTO telle que la mosaique l'a vue : un pixel par tenon, agrandi.

    Sert a comparer. Un « avant / apres » ne veut rien dire si les deux images
    ne montrent pas la meme chose : la photo d'origine est rognee au rapport de
    l'oeuvre, moyennee par tenon, et l'apercu porte un cadre qu'elle n'a pas.
    Superposer la photo brute produirait un glissement, et un glissement fait
    mentir la comparaison — on croirait juger la quantification alors qu'on
    regarde un decalage.

    Cette image-ci sort du MEME cadrage et du MEME reechantillonnage que la
    grille quantifiee, et recoit le meme cadre. Elle se superpose au pixel pres.

    Elle montre aussi ce que le cadrage a coupe, qui n'etait visible nulle part.
    """
    if scale <= 0:
        raise ValueError("echelle invalide")
    if reduite.width != mosaic.studs_x or reduite.height != mosaic.studs_y:
        raise ValueError(
            f"la source reduite fait {reduite.width}x{reduite.height}, "
            f"la mosaique {mosaic.studs_x}x{mosaic.studs_y}"
        )
    data = bytearray()
    for y in range(mosaic.studs_y):
        ligne = bytearray()
        for x in range(mosaic.studs_x):
            debut = (y * reduite.width + x) * 3
            ligne.extend(reduite.data[debut:debut + 3] * scale)
        data.extend(ligne * scale)
    oeuvre = Image(mosaic.studs_x * scale, mosaic.studs_y * scale, bytes(data))
    if mosaic.frame:
        oeuvre = _entourer(oeuvre, mosaic, scale, frame_rgb)
    return oeuvre


def _rvb_du_cadre(code: int, fourni):
    """Couleur du cadre pour l'apercu, sans imposer une palette a `preview`.

    Le modele ne porte qu'un CODE de couleur : c'est la palette qui sait le
    traduire, et une mosaique n'en embarque pas. L'appelant qui en a une la
    passe ; sinon on cherche dans la palette provisoire, et a defaut on rend un
    gris tres sombre plutot que d'inventer une teinte.
    """
    if fourni is not None:
        return tuple(fourni)
    for couleur in PROVISIONAL_PALETTE:
        if couleur.code == code:
            return couleur.rgb
    return (26, 26, 26)


def _entourer(oeuvre: Image, mosaic: Mosaic, scale: int, frame_rgb) -> Image:
    """Pose le cadre autour de l'apercu, avec l'ombre qu'il porte.

    L'ombre n'est pas un ornement. Un cadre a fleur de la surface se lit comme
    une bordure peinte ; ce qui le fait lire comme un CADRE, c'est qu'il monte
    au-dessus de l'oeuvre et projette une ombre sur elle. Le modele monte
    reellement — une assise de briques depasse de 6,4 mm — et l'apercu doit le
    montrer, sinon il decrit autre chose que ce qu'on va construire.
    """
    rvb = bytes(_rvb_du_cadre(mosaic.frame_color, frame_rgb))
    bord = mosaic.frame * scale
    largeur = oeuvre.width + 2 * bord
    hauteur = oeuvre.height + 2 * bord
    data = bytearray(rvb * (largeur * hauteur))

    # Un lisere clair en haut a gauche et sombre en bas a droite : la meme
    # lumiere que celle du relief, pour que les deux apercus se ressemblent.
    def teinter(x0, y0, x1, y1, facteur):
        for y in range(max(0, y0), min(hauteur, y1)):
            for x in range(max(0, x0), min(largeur, x1)):
                i = (y * largeur + x) * 3
                for canal in range(3):
                    data[i + canal] = max(0, min(
                        255, round(data[i + canal] * facteur) + (
                            18 if facteur > 1 else 0)))

    lisere = max(1, scale // 4)
    teinter(0, 0, largeur, lisere, 1.35)
    teinter(0, 0, lisere, hauteur, 1.35)
    teinter(0, hauteur - lisere, largeur, hauteur, 0.55)
    teinter(largeur - lisere, 0, largeur, hauteur, 0.55)

    for y in range(oeuvre.height):
        source = y * oeuvre.width * 3
        cible = ((y + bord) * largeur + bord) * 3
        data[cible:cible + oeuvre.width * 3] = oeuvre.data[
            source:source + oeuvre.width * 3]

    # L'ombre portee du cadre sur l'oeuvre, en haut et a gauche de l'ouverture.
    ombre = max(1, scale // 2)
    for profondeur in range(ombre):
        force = 0.55 + 0.45 * (profondeur / ombre)
        y = bord + profondeur
        for x in range(bord, bord + oeuvre.width):
            i = (y * largeur + x) * 3
            for canal in range(3):
                data[i + canal] = round(data[i + canal] * force)
        x = bord + profondeur
        for y2 in range(bord + profondeur, bord + oeuvre.height):
            i = (y2 * largeur + x) * 3
            for canal in range(3):
                data[i + canal] = round(data[i + canal] * force)

    return Image(largeur, hauteur, bytes(data))


