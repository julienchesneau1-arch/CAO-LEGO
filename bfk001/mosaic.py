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
from typing import Dict, Mapping, Tuple

from .catalog import PartInstance, place
from .collision import CollisionGeometry
from .imaging import Image, resample_box
from .lego import PLATE_HEIGHT_LDU, STUD_PITCH_LDU
from .palette import LegoColor, Palette
from .search import PlacedPart

__all__ = ["Mosaic", "quantize", "build", "from_image", "preview"]

SUBSTRATE_DESIGN = "3020"   # Plate 2 x 4
TILE_DESIGN = "3070b"       # Tile 1 x 1 with Groove
SUBSTRATE_COLOR = 71        # Light Bluish Gray : invisible sous la mosaique


@dataclass(frozen=True)
class Mosaic:
    """Resultat du solveur : la grille voulue et le modele qui la realise."""

    studs_x: int
    studs_y: int
    grid: Tuple[Tuple[LegoColor, ...], ...]  # grid[ligne][colonne], ligne 0 = haut
    placed_parts: Mapping[str, PlacedPart]
    geometries: Mapping[str, CollisionGeometry]
    instances: Mapping[str, PartInstance]

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
) -> Tuple[Tuple[LegoColor, ...], ...]:
    """Image -> grille de couleurs LEGO.

    Deux etapes, dans cet ordre : moyenner d'abord (chaque tenon recoit la
    couleur moyenne de sa zone), quantifier ensuite. L'inverse — quantifier
    puis reduire — melangerait des couleurs de palette entre elles et
    produirait des teintes qui n'existent pas.
    """
    if studs_x <= 0 or studs_y <= 0:
        raise ValueError("dimensions de mosaique invalides")
    reduced = resample_box(image, studs_x, studs_y)
    return tuple(
        tuple(palette.nearest(reduced.pixel(x, y)) for x in range(studs_x))
        for y in range(studs_y)
    )


def build(
    grid: Tuple[Tuple[LegoColor, ...], ...],
    substrate_color: int = SUBSTRATE_COLOR,
) -> Mosaic:
    """Grille de couleurs -> modele complet : substrat croise + tuiles."""
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

    # Couche 0 : pavage de plates 2x4 (40 x 80 LDU), a partir de l'origine.
    for i, x in enumerate(range(0, width, 2 * STUD_PITCH_LDU)):
        for j, y in enumerate(range(0, depth, 4 * STUD_PITCH_LDU)):
            add(f"S0_{i}_{j}", SUBSTRATE_DESIGN, (x, y, 0), substrate_color)

    # Couche 1 : meme pavage decale d'un tenon en x et de deux en y. Chaque
    # plate y chevauche quatre plates de la couche 0 : c'est ce decalage, et
    # lui seul, qui fait tenir le fond d'un seul tenant.
    for i, x in enumerate(range(-STUD_PITCH_LDU, width, 2 * STUD_PITCH_LDU)):
        for j, y in enumerate(range(-2 * STUD_PITCH_LDU, depth, 4 * STUD_PITCH_LDU)):
            add(
                f"S1_{i}_{j}",
                SUBSTRATE_DESIGN,
                (x, y, PLATE_HEIGHT_LDU),
                substrate_color,
            )

    # Couche 2 : la mosaique. La ligne 0 de l'image est en haut, donc au y le
    # plus grand : le modele se lit comme la photo, vu du dessus.
    tile_z = 2 * PLATE_HEIGHT_LDU
    for row, colors in enumerate(grid):
        y = (studs_y - 1 - row) * STUD_PITCH_LDU
        for column, color in enumerate(colors):
            add(
                f"T{row}_{column}",
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
) -> Mosaic:
    """Chaine complete : photo -> modele constructible."""
    return build(quantize(image, palette, studs_x, studs_y), substrate_color)


def preview(mosaic: Mosaic, scale: int = 8) -> Image:
    """Apercu du rendu, un carre par tuile. Sert a juger a l'oeil."""
    if scale <= 0:
        raise ValueError("echelle invalide")
    width = mosaic.studs_x * scale
    height = mosaic.studs_y * scale
    pixels = []
    for y in range(height):
        row = mosaic.grid[y // scale]
        for x in range(width):
            pixels.append(row[x // scale].rgb)
    return Image(width, height, tuple(pixels))
