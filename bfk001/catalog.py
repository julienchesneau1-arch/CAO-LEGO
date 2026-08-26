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
    has_studs: bool = True

    def geometry(self) -> CollisionGeometry:
        return brick_geometry(
            self.studs_x, self.studs_y, self.body_height_ldu, self.has_studs
        )

    def connectors(self) -> Tuple[Connector, ...]:
        return brick_connectors(
            self.studs_x, self.studs_y, self.body_height_ldu, self.has_studs
        )


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
    PartDefinition("3024", "Plate 1 x 1", 1, 1, PLATE_HEIGHT_LDU),
    PartDefinition("3023", "Plate 1 x 2", 1, 2, PLATE_HEIGHT_LDU),
    PartDefinition("3022", "Plate 2 x 2", 2, 2, PLATE_HEIGHT_LDU),
    PartDefinition("3021", "Plate 2 x 3", 2, 3, PLATE_HEIGHT_LDU),
    PartDefinition("3020", "Plate 2 x 4", 2, 4, PLATE_HEIGHT_LDU),
    # Grandes plates de fond. Le substrat ne se voit pas : sa seule qualite est
    # de tenir. Le paver en 2x4 coutait 657 pieces sur une 48x48, soit un tiers
    # du modele pour quelque chose d'invisible. References verifiees une a une
    # contre parts.lst de la bibliotheque LDraw officielle.
    PartDefinition("3795", "Plate 2 x 6", 2, 6, PLATE_HEIGHT_LDU),
    PartDefinition("3034", "Plate 2 x 8", 2, 8, PLATE_HEIGHT_LDU),
    PartDefinition("3031", "Plate 4 x 4", 4, 4, PLATE_HEIGHT_LDU),
    PartDefinition("3032", "Plate 4 x 6", 4, 6, PLATE_HEIGHT_LDU),
    PartDefinition("3035", "Plate 4 x 8", 4, 8, PLATE_HEIGHT_LDU),
    PartDefinition("3958", "Plate 6 x 6", 6, 6, PLATE_HEIGHT_LDU),
    PartDefinition("3036", "Plate 6 x 8", 6, 8, PLATE_HEIGHT_LDU),
    PartDefinition("41539", "Plate 8 x 8", 8, 8, PLATE_HEIGHT_LDU),
    PartDefinition("3070b", "Tile 1 x 1 with Groove", 1, 1, PLATE_HEIGHT_LDU, False),
    # Tuiles longues : elles couvrent plusieurs tenons d'un coup. Le rendu est
    # identique au tenon pres — une 1x4 rouge montre les memes quatre tenons
    # rouges que quatre 1x1 —, donc la fusion ne coute AUCUNE fidelite. Elle
    # divise le nombre de pieces par deux. References verifiees une a une
    # contre parts.lst de la bibliotheque LDraw officielle, jamais de memoire.
    # La tuile RONDE : celle des mosaiques LEGO Art officielles. Meme emprise
    # qu'une 1x1 carree — le noyau la traite comme un prisme carre, comme il
    # traite deja les tenons cylindriques, ecart signale au README. Ce qui
    # change est l'ASPECT : les rondes laissent un interstice sombre entre
    # elles et donnent une trame de points ; les carrees donnent des aplats.
    # Elles n'existent qu'en 1x1, donc elles interdisent toute fusion.
    PartDefinition("98138", "Tile 1 x 1 Round with Groove", 1, 1, PLATE_HEIGHT_LDU, False),
    PartDefinition("3069b", "Tile 1 x 2 with Groove", 1, 2, PLATE_HEIGHT_LDU, False),
    PartDefinition("63864", "Tile 1 x 3 with Groove", 1, 3, PLATE_HEIGHT_LDU, False),
    PartDefinition("2431", "Tile 1 x 4 with Groove", 1, 4, PLATE_HEIGHT_LDU, False),
    PartDefinition("6636", "Tile 1 x 6", 1, 6, PLATE_HEIGHT_LDU, False),
    PartDefinition("4162", "Tile 1 x 8", 1, 8, PLATE_HEIGHT_LDU, False),
    PartDefinition("3068b", "Tile 2 x 2 with Groove", 2, 2, PLATE_HEIGHT_LDU, False),
    PartDefinition("91405", "Plate 16 x 16", 16, 16, PLATE_HEIGHT_LDU),
)
# ATTENTION — reference corrigee : le document de reflexion produit listait
# « 3021 Plate 2x4 ». C'est faux : 3021 est une Plate 2x3, et la Plate 2x4 porte
# la reference 3020. Une liste de course fondee sur cette erreur aurait fait
# livrer des plates 2x3. C'est exactement pourquoi les references doivent venir
# d'un import de catalogue reel et non d'une recopie a la main
# (docs/ZONES_DOMBRE.md, section 3.3).

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


def place_at(
    part_id: str,
    design_id: str,
    corner: Tuple[int, int, int],
    orientation: Optional[Orientation] = None,
    color_id: int = 15,
) -> Tuple[PlacedPart, CollisionGeometry, PartInstance]:
    """Pose une piece de sorte que le coin bas de son AABB tombe sur `corner`.

    `place` translate l'ORIGINE de la piece ; sous rotation, l'origine n'est
    plus le coin. Une tuile 1x4 tournee d'un quart de tour se retrouve a
    gauche de la ou on la voulait. Ici on vise le coin, ce qui est la seule
    chose dont un pavage a besoin, et la compensation se lit dans l'AABB de la
    piece tournee a l'origine — pas dans un calcul refait a la main.
    """
    repere, _, _ = place(part_id, design_id, (0, 0, 0), orientation, color_id)
    return place(
        part_id,
        design_id,
        (
            corner[0] - repere.aabb.min.x,
            corner[1] - repere.aabb.min.y,
            corner[2] - repere.aabb.min.z,
        ),
        orientation,
        color_id,
    )


def bill_of_materials(
    instances: Mapping[str, PartInstance],
    placed_parts: Optional[Mapping[str, object]] = None,
) -> Tuple[BomLine, ...]:
    """Nomenclature agregee par (reference, couleur), triee.

    Pur comptage : aucune substitution, aucun prix, aucune disponibilite. Ces
    decisions relevent d'une couche commerciale qui n'a rien a faire dans un
    noyau geometrique.

    `placed_parts` est un garde-fou optionnel mais recommande : une piece posee
    sans identite catalogue disparaitrait silencieusement de la liste de course.
    Une nomenclature incomplete se paie en pieces manquantes le jour du montage.
    """
    if placed_parts is not None:
        missing = sorted(set(placed_parts) - set(instances))
        if missing:
            raise KeyError(
                f"identite catalogue absente pour {', '.join(missing)} : "
                "ces pieces manqueraient a la liste de course."
            )

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
