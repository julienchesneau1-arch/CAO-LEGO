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
from typing import Dict, List, Mapping, Tuple

from .catalog import PartInstance, place
from .collision import CollisionGeometry
from .imaging import _REENCODAGE, Image, resample_box
from .imaging import _TABLE_LUMIERE as _LUMIERE
from .lego import PLATE_HEIGHT_LDU, STUD_PITCH_LDU
from .palette import LegoColor, Palette, delta_e
from .search import PlacedPart

__all__ = [
    "Mosaic",
    "tile_id",
    "quantize",
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

SUBSTRATE_DESIGN = "3020"   # Plate 2 x 4
PANEL_DESIGN = "91405"      # Plate 16 x 16, celle des sets LEGO Art
TILE_DESIGN = "3070b"       # Tile 1 x 1 with Groove
SUBSTRATE_COLOR = 71        # Light Bluish Gray : invisible sous la mosaique


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

    def tile_id(self, row: int, column: int) -> str:
        return tile_id(row, column)

    @property
    def tile_count(self) -> int:
        return self.studs_x * self.studs_y

    @property
    def part_count(self) -> int:
        return len(self.placed_parts)


def quantize(
    image: Image,
    palette: Palette,
    studs_x: int,
    studs_y: int,
    dither: object = False,
) -> Tuple[Tuple[LegoColor, ...], ...]:
    """Image -> grille de couleurs LEGO.

    Deux etapes, dans cet ordre : moyenner d'abord (chaque tenon recoit la
    couleur moyenne de sa zone), quantifier ensuite. L'inverse — quantifier
    puis reduire — melangerait des couleurs de palette entre elles et
    produirait des teintes qui n'existent pas.

    `dither` accepte trois valeurs :

      False      quantification directe : chaque tuile prend la couleur de
                 palette la plus proche. Propre sur les aplats, brutal sur les
                 modeles.
      True       diffusion d'erreur de Floyd-Steinberg partout : l'ecart entre
                 la couleur voulue et la couleur posee est reporte sur les
                 tenons voisins, ce qui simule des teintes absentes.
      "adaptive" diffusion PONDEREE par l'ecart a la palette : pleine la ou la
                 couleur voulue n'existe pas, nulle la ou elle existe deja.

    Le defaut est False, et cette valeur est le resultat d'une mesure suivie
    d'une correction.

    Mesure : a trois tuiles de distance de regard, le tramage adaptatif ecrase
    la quantification directe — 5,9 contre 12,3 delta E sur une image mixte.
    Tout indiquait qu'il fallait l'activer par defaut.

    Correction : cette distance de regard n'existe pas. Un tenon fait 8 mm ;
    deux tuiles voisines ne se confondent qu'a 55 m (voir `blending_tiles`).
    A toute distance reelle, l'oeil voit chaque tuile separement — donc il voit
    le damier que produit le tramage, et le rendu se degrade au lieu de
    s'ameliorer. La mesure decrivait une situation impossible.

    Le tramage reste disponible : il redevient le bon choix des que le motif
    est plus fin que le pouvoir separateur de l'oeil — une impression de
    l'apercu, un ecran, ou un futur medium a maille serree.
    """
    if studs_x <= 0 or studs_y <= 0:
        raise ValueError("dimensions de mosaique invalides")
    if dither not in (True, False, "adaptive"):
        raise ValueError("dither vaut True, False ou 'adaptive'")
    reduced = resample_box(image, studs_x, studs_y)

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
        row: List[LegoColor] = []
        for x in range(studs_x):
            wanted = tuple(min(255, max(0, round(v))) for v in buffer[y][x])
            chosen = palette.nearest(wanted)
            row.append(chosen)
            facteur = strength[y][x]
            if facteur <= 0:
                continue
            error = [
                (buffer[y][x][i] - chosen.rgb[i]) * facteur for i in range(3)
            ]
            for dx, dy, weight in ((1, 0, 7), (-1, 1, 3), (0, 1, 5), (1, 1, 1)):
                nx, ny = x + dx, y + dy
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
                    1.0,
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


def _paver(add, prefixe, ancre_x, ancre_y, studs_x, studs_y, z, color) -> int:
    """Pave l'emprise de l'oeuvre de plates sur un reseau ancre ailleurs.

    Sans le rognage, la couche decalee depasse de un tenon en x et de deux en y
    sur chaque bord : l'oeuvre finie porte un lisere de plate grise nue, visible,
    et paye en pieces. Mesure sur une 48x48 : substrat x -20..980 pour une
    mosaique x 0..960.
    """
    pose = 0
    for x0, x1 in _decouper_axe(ancre_x, 2, studs_x):
        for y0, y1 in _decouper_axe(ancre_y, 4, studs_y):
            for design, dx, dy in _plaques(x1 - x0, y1 - y0, y0):
                add(
                    f"{prefixe}_{pose}",
                    design,
                    ((x0 + dx) * STUD_PITCH_LDU, (y0 + dy) * STUD_PITCH_LDU, z),
                    color,
                )
                pose += 1
    return pose


def build(
    grid: Tuple[Tuple[LegoColor, ...], ...],
    substrate_color: int = SUBSTRATE_COLOR,
    substrate: str = "crossed",
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

    def add(part_id: str, design_id: str, translation, color: int) -> None:
        placed, geometry, instance = place(
            part_id, design_id, translation, color_id=color
        )
        parts[part_id] = placed
        geometries[part_id] = geometry
        instances[part_id] = instance

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
        _paver(add, "S0", 0, 0, studs_x, studs_y, 0, substrate_color)

        # Couche 1 : meme pavage decale d'un tenon en x et de deux en y. Chaque
        # plate y chevauche quatre plates de la couche 0 : c'est ce decalage, et
        # lui seul, qui fait tenir le fond d'un seul tenant. Un pavage sans
        # decalage, ou decale sur un seul axe, se scinde en bandes disjointes —
        # H5 le voit.
        _paver(add, "S1", -1, -2, studs_x, studs_y, PLATE_HEIGHT_LDU, substrate_color)
        tile_z = 2 * PLATE_HEIGHT_LDU

    # Derniere couche : la mosaique. La ligne 0 de l'image est en haut, donc au
    # y le plus grand : le modele se lit comme la photo, vu du dessus.
    for row, colors in enumerate(grid):
        y = (studs_y - 1 - row) * STUD_PITCH_LDU
        for column, color in enumerate(colors):
            add(
                tile_id(row, column),
                TILE_DESIGN,
                (column * STUD_PITCH_LDU, y, tile_z),
                color.code,
            )

    return Mosaic(studs_x, studs_y, grid, parts, geometries, instances)


def from_image(
    image: Image,
    palette: Palette,
    studs_x: int,
    studs_y: int,
    substrate_color: int = SUBSTRATE_COLOR,
    dither: object = False,
    substrate: str = "crossed",
) -> Mosaic:
    """Chaine complete : photo -> modele constructible."""
    return build(
        quantize(image, palette, studs_x, studs_y, dither),
        substrate_color,
        substrate,
    )


def preview(mosaic: Mosaic, scale: int = 8) -> Image:
    """Apercu du rendu, un carre par tuile. Sert a juger a l'oeil."""
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
    return Image(width, height, bytes(data))
