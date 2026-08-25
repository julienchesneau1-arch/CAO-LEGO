"""Catalogue de pieces et nomenclature (HORS CONTRAT).

Le contrat identifie une piece par un `part_id` : c'est un identifiant
d'INSTANCE (« la troisieme brique du mur »), pas une reference de piece. Un
logiciel de CAO a besoin des deux :

    part_id    "U23"   quelle piece de l'assemblage
    design_id  "3001"  quelle reference LEGO (brique 2x4)
    color_id   4       quelle couleur (code LDraw)

Sans cette separation, aucune liste d'achat n'est calculable. Elle est tenue
ici, a cote du noyau, plutot que dans PlacedPart : la Section H.1 fige les
champs de PlacedPart, et l'identite commerciale d'une piece n'a aucune
influence sur la mecanique. L'oracle n'a pas a savoir qu'une brique est rouge.

Le catalogue couvre les 8 references rectangulaires de base. Toute extension
(pentes, brackets, Technic) suppose d'abord une geometrie non-AABB et de
nouveaux types de connecteurs : voir docs/ZONES_DOMBRE.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple

from .collision import CollisionGeometry
from .connectors import Connector
from .geometry import Orientation
from .lego import BRICK_HEIGHT_LDU, PLATE_HEIGHT_LDU, brick_connectors, brick_geometry
from .search import PlacedPart

__all__ = [
    "PartDefinition",
    "PartInstance",
    "BomLine",
    "CATALOG",
    "LDRAW_COLORS",
    "definition",
    "place",
    "bill_of_materials",
]


@dataclass(frozen=True)
class PartDefinition:
    """Reference de piece : identite commerciale + parametres geometriques."""

    design_id: str
    name: str
    studs_x: int
    studs_y: int
    body_height_ldu: int

    def geometry(self) -> CollisionGeometry:
        return brick_geometry(self.studs_x, self.studs_y, self.body_height_ldu)

    def connectors(self) -> Tuple[Connector, ...]:
        return brick_connectors(self.studs_x, self.studs_y, self.body_height_ldu)


@dataclass(frozen=True)
class PartInstance:
    """Identite d'une piece posee : instance -> reference + couleur."""

    part_id: str
    design_id: str
    color_id: int


@dataclass(frozen=True)
class BomLine:
    """Une ligne de nomenclature."""

    design_id: str
    name: str
    color_id: int
    quantity: int


_DEFINITIONS = (
    PartDefinition("3005", "Brick 1 x 1", 1, 1, BRICK_HEIGHT_LDU),
    PartDefinition("3004", "Brick 1 x 2", 1, 2, BRICK_HEIGHT_LDU),
    PartDefinition("3010", "Brick 1 x 4", 1, 4, BRICK_HEIGHT_LDU),
    PartDefinition("3003", "Brick 2 x 2", 2, 2, BRICK_HEIGHT_LDU),
    PartDefinition("3001", "Brick 2 x 4", 2, 4, BRICK_HEIGHT_LDU),
    PartDefinition("3023", "Plate 1 x 2", 1, 2, PLATE_HEIGHT_LDU),
    PartDefinition("3022", "Plate 2 x 2", 2, 2, PLATE_HEIGHT_LDU),
    PartDefinition("3021", "Plate 2 x 4", 2, 4, PLATE_HEIGHT_LDU),
)

CATALOG: Mapping[str, PartDefinition] = {
    part.design_id: part for part in _DEFINITIONS
}

LDRAW_COLORS: Mapping[int, str] = {
    0: "Black",
    1: "Blue",
    2: "Green",
    4: "Red",
    14: "Yellow",
    15: "White",
    70: "Reddish Brown",
    71: "Light Bluish Gray",
    72: "Dark Bluish Gray",
}
"""Sous-ensemble des codes couleur LDraw. La palette complete (~70 couleurs
actives, correspondances BrickLink et Element ID) est une donnee externe a
importer, pas a recopier a la main : voir docs/ZONES_DOMBRE.md."""


def definition(design_id: str) -> PartDefinition:
    """Reference du catalogue, ou KeyError explicite."""
    if design_id not in CATALOG:
        raise KeyError(
            f"reference absente du catalogue : {design_id!r} "
            f"(disponibles : {', '.join(sorted(CATALOG))})"
        )
    return CATALOG[design_id]


def place(
    part_id: str,
    design_id: str,
    translation: Tuple[int, int, int] = (0, 0, 0),
    orientation: Optional[Orientation] = None,
    color_id: int = 15,
) -> Tuple[PlacedPart, CollisionGeometry, PartInstance]:
    """Pose une piece du catalogue.

    Retourne le triplet que reclament les trois couches : la piece placee (pour
    le noyau), sa geometrie (pour l'autorite de collision), son identite (pour
    la nomenclature).
    """
    from .geometry import LDUVector, transform_aabb

    part = definition(design_id)
    pose = (
        LDUVector(*translation),
        Orientation.identity() if orientation is None else orientation,
    )
    geometry = part.geometry()
    placed = PlacedPart(
        part_id=part_id,
        pose=pose,
        aabb=transform_aabb(geometry.exterior, pose),
        connectors=part.connectors(),
    )
    return placed, geometry, PartInstance(part_id, design_id, color_id)


def bill_of_materials(
    instances: Mapping[str, PartInstance],
) -> Tuple[BomLine, ...]:
    """Nomenclature agregee par (reference, couleur), triee.

    Pur comptage : aucune substitution, aucun prix, aucune disponibilite. Ces
    decisions relevent d'une couche commerciale qui n'a rien a faire dans un
    noyau geometrique.
    """
    counts: Dict[Tuple[str, int], int] = {}
    for instance in instances.values():
        if not isinstance(instance, PartInstance):
            raise TypeError("bill_of_materials attend des PartInstance")
        key = (instance.design_id, instance.color_id)
        counts[key] = counts.get(key, 0) + 1

    return tuple(
        BomLine(
            design_id=design_id,
            name=CATALOG[design_id].name if design_id in CATALOG else design_id,
            color_id=color_id,
            quantity=quantity,
        )
        for (design_id, color_id), quantity in sorted(counts.items())
    )
