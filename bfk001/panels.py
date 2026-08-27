"""Decouper une grande oeuvre en sections que l'on batit separement.

Une mosaique de 96 tenons fait 77 cm de cote et pese pres de quatre mille
pieces. D'un seul tenant, elle ne passe ni sur une table ordinaire, ni dans un
carton, ni entre deux mains. Les sets LEGO Art officiels ne s'y risquent pas :
ils sont faits de panneaux 16x16 montes separement.

Ce module fait la meme chose, avec une difference qui compte. Les panneaux
officiels ne se lient pas entre eux — c'est le CADRE qui les tient, et un cadre
n'est pas une piece LEGO. Le noyau refuse cet arrangement, et il a raison : le
substrat « panels » de `mosaic.build` produit 454 violations de H5 sur une
oeuvre de 32 tenons.

Ici, chaque section est une mosaique COMPLETE — son propre fond croise, ses
tuiles — donc un modele valide a elle seule, batissable et verifiable sans les
autres. Les sections sont ensuite reunies par une couche de plates posee
DESSOUS, a cheval sur les joints.

Ce que ce module promet, et ce qu'il ne promet pas :

  - chaque section passe H1 a H6 toute seule. Verifie.
  - l'assemblage complet, jonction comprise, passe H1 a H6. Verifie.
  - la RIGIDITE de l'ensemble n'est pas modelisee. H5 dit « d'un seul tenant »,
    pas « ne plie pas ». Une jonction par-dessous est une charniere : deux
    sections liees ainsi tiennent ensemble et flechissent. Le noyau ne sait pas
    mesurer cela — c'est du ressort de BFK-002 — et je ne vais pas pretendre le
    contraire. Pour une oeuvre a accrocher, un cadre reste la bonne reponse.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .catalog import PartInstance, place
from .collision import CollisionGeometry
from .geometry import LDUVector
from .lego import PLATE_HEIGHT_LDU, STUD_PITCH_LDU
from .mosaic import (Mosaic, SUBSTRATE_COLOR, TILE_SET_STANDARD, build,
                     _paver, _verifier_relief)
from .search import PlacedPart

__all__ = [
    "Section",
    "Assembly",
    "split_grid",
    "build_assembly",
    "JOIN_DESIGN",
]

JOIN_DESIGN = "3020"
"""Plate 2x4 de jonction. La meme que le fond croise : une reference de plus
serait un lot de plus a commander pour rien."""

JOIN_ANCHOR = (-1, -2)
"""Ancrage de la couche de jonction, en tenons.

Le meme decalage que la couche haute du fond croise, et pour la meme raison :
un reseau ancre ailleurs produit des plates a cheval. Ici elles doivent
enjamber les JOINTS entre sections, ce que `_verifier_jonction` controle sur
les poses reelles plutot que de le supposer.
"""


@dataclass(frozen=True)
class Section:
    """Une section : un modele complet, et sa place dans l'oeuvre entiere."""

    row: int
    column: int
    x0: int
    """Colonne du coin gauche de la section, en tenons de l'oeuvre entiere."""
    y0: int
    """Ligne du coin HAUT de la section, en lignes de la grille (0 = haut)."""
    mosaic: Mosaic

    @property
    def studs_x(self) -> int:
        return self.mosaic.studs_x

    @property
    def studs_y(self) -> int:
        return self.mosaic.studs_y

    @property
    def name(self) -> str:
        return f"section_{self.row + 1}_{self.column + 1}"


@dataclass(frozen=True)
class Assembly:
    """L'oeuvre entiere : ses sections, et la couche qui les reunit."""

    studs_x: int
    studs_y: int
    section_side: int
    sections: Tuple[Section, ...]
    placed_parts: Mapping[str, PlacedPart]
    geometries: Mapping[str, CollisionGeometry]
    instances: Mapping[str, PartInstance]
    join_count: int

    @property
    def part_count(self) -> int:
        return len(self.placed_parts)

    @property
    def rows(self) -> int:
        return max(s.row for s in self.sections) + 1

    @property
    def columns(self) -> int:
        return max(s.column for s in self.sections) + 1


def split_grid(grid, section_side: int):
    """Grille -> sections, en (ligne, colonne, x0, y0, sous-grille).

    Le decoupage est REGULIER et la derniere section de chaque rangee peut
    etre plus petite : une oeuvre de 100 tenons en sections de 48 donne 48, 48
    et 4. Une section de 4 tenons de large tiendrait, mais ne se transporte pas
    mieux qu'un morceau de la precedente — `build_assembly` refuse plutot que
    de livrer un ruban.
    """
    if section_side < 2:
        raise ValueError("une section fait au moins deux tenons de cote")
    if not grid or not grid[0]:
        raise ValueError("grille vide")
    hauteur, largeur = len(grid), len(grid[0])
    sections = []
    for ligne, y0 in enumerate(range(0, hauteur, section_side)):
        for colonne, x0 in enumerate(range(0, largeur, section_side)):
            morceau = tuple(
                tuple(rang[x0:x0 + section_side])
                for rang in grid[y0:y0 + section_side]
            )
            sections.append((ligne, colonne, x0, y0, morceau))
    return tuple(sections)


def _decaler(parts, geometries, instances, prefixe: str, decalage):
    """Re-pose un modele entier a un autre endroit.

    On ne translate pas les AABB a la main : on RE-POSE chaque piece par
    `place`, qui recalcule l'AABB monde depuis la pose. Deplacer une boite en
    esperant qu'elle reste juste est exactement le genre de raccourci qui a
    casse l'export LDraw (§ 5.39 du registre).
    """
    dx, dy, dz = decalage
    sortie_parts: Dict[str, PlacedPart] = {}
    sortie_geo: Dict[str, CollisionGeometry] = {}
    sortie_inst: Dict[str, PartInstance] = {}
    for identifiant, piece in parts.items():
        instance = instances[identifiant]
        translation, orientation = piece.pose
        nouveau = f"{prefixe}_{identifiant}"
        place_, geo, inst = place(
            nouveau,
            instance.design_id,
            (translation.x + dx, translation.y + dy, translation.z + dz),
            orientation=orientation,
            color_id=instance.color_id,
        )
        sortie_parts[nouveau] = place_
        sortie_geo[nouveau] = geo
        sortie_inst[nouveau] = inst
    return sortie_parts, sortie_geo, sortie_inst


def _verifier_jonction(poses, studs_x, studs_y, section_side):
    """Chaque joint interne est-il enjambe par au moins une plate ?

    C'est la seule chose qui rende l'assemblage connexe : deux sections
    posees cote a cote ne se lient pas plus que deux panneaux 16x16
    officiels. Le controle est exact et se fait sur les poses reelles, apres
    fusion — pas sur le reseau theorique, dont le § 5.44 a montre qu'il ment.
    """
    manquants = []
    for x in range(section_side, studs_x, section_side):
        if not any(px < x < px + largeur
                   for px, _, largeur, _, _ in poses):
            manquants.append(f"x={x}")
    for y in range(section_side, studs_y, section_side):
        if not any(py < y < py + profondeur
                   for _, py, _, profondeur, _ in poses):
            manquants.append(f"y={y}")
    if manquants:
        raise ValueError(
            f"la couche de jonction n'enjambe pas {', '.join(manquants)} : "
            f"des sections de {section_side} tenons laissent un joint sur le "
            "reseau des plates. Choisissez un cote de section multiple de 4."
        )


def build_assembly(
    grid,
    section_side: int = 48,
    substrate_color: int = SUBSTRATE_COLOR,
    tiles: Sequence[str] = TILE_SET_STANDARD,
    heights: Optional[Sequence[Sequence[int]]] = None,
) -> Assembly:
    """Grille -> sections independantes + couche de jonction.

    Chaque section est batie par `mosaic.build`, donc avec son propre fond
    croise et ses propres verifications. Elle est ensuite re-posee a sa place,
    surelevee d'une epaisseur de plate : la couche de jonction passe dessous.
    """
    if not grid or not grid[0]:
        raise ValueError("grille vide")
    studs_y, studs_x = len(grid), len(grid[0])
    if section_side >= max(studs_x, studs_y):
        raise ValueError(
            f"une section de {section_side} tenons couvre deja l'oeuvre "
            f"({studs_x}x{studs_y}) : il n'y a rien a decouper"
        )
    reste_x = studs_x % section_side
    reste_y = studs_y % section_side
    for reste, axe, total in ((reste_x, "largeur", studs_x),
                              (reste_y, "hauteur", studs_y)):
        # Un tiers de section : en dessous, la derniere bande est plus longue
        # que large et ne se transporte pas mieux qu'un morceau de sa voisine.
        # Le seuil est un choix de bon sens, pas une mesure — mais il vaut
        # mieux qu'aucun seuil, qui livrerait des rubans de deux tenons.
        if reste and reste * 3 < section_side:
            raise ValueError(
                f"decoupe en {section_side} : la derniere section ne ferait que "
                f"{reste} tenons de {axe} sur {total}. Un ruban ne se transporte "
                f"pas mieux qu'un morceau du voisin — choisissez un cote qui "
                f"divise mieux {total}."
            )

    elevations = _verifier_relief(heights, studs_x, studs_y)

    parts: Dict[str, PlacedPart] = {}
    geometries: Dict[str, CollisionGeometry] = {}
    instances: Dict[str, PartInstance] = {}
    sections: List[Section] = []

    for ligne, colonne, x0, y0, morceau in split_grid(grid, section_side):
        hauteur_section = len(morceau)
        relief_section = [
            list(elevations[y0 + j][x0:x0 + section_side])
            for j in range(hauteur_section)
        ]
        modele = build(
            morceau, substrate_color, "crossed", tiles,
            heights=relief_section if any(
                v for rang in relief_section for v in rang) else None,
        )
        # y0 compte les LIGNES depuis le haut ; le modele compte les tenons
        # depuis le bas. La section la plus basse de la grille est celle dont
        # y0 est le plus grand, et c'est elle qui touche y = 0 dans le monde.
        bas = studs_y - y0 - hauteur_section
        deplaces = _decaler(
            modele.placed_parts, modele.geometries, modele.instances,
            f"S{ligne}{colonne}",
            (x0 * STUD_PITCH_LDU, bas * STUD_PITCH_LDU, PLATE_HEIGHT_LDU),
        )
        parts.update(deplaces[0])
        geometries.update(deplaces[1])
        instances.update(deplaces[2])
        sections.append(Section(ligne, colonne, x0, y0, modele))

    # La couche de jonction : UN pavage complet de plates, a z = 0, ancre
    # de facon que ses plates enjambent les joints. C'est le meme mecanisme
    # que la couche haute du fond croise — ancrer ailleurs et laisser les
    # plates chevaucher — et c'est du code deja eprouve sur 1521 formats.
    #
    # J'avais d'abord pose des ponts isoles sous les seuls joints, pour
    # economiser des pieces. Deux defauts, tous deux vus par le noyau : les
    # ponts se percutaient au croisement de deux joints (H2), et les sections
    # ne reposaient sur rien ailleurs (H4). Une couche pleine coute environ
    # 5 % du modele et supprime les deux.
    jonction = _paver(
        lambda placed, geo, inst: (
            parts.__setitem__(placed.part_id, placed),
            geometries.__setitem__(placed.part_id, geo),
            instances.__setitem__(placed.part_id, inst),
        ),
        "J", -1, -2, studs_x, studs_y, 0, substrate_color,
    )
    _verifier_jonction(jonction, studs_x, studs_y, section_side)

    return Assembly(
        studs_x=studs_x, studs_y=studs_y, section_side=section_side,
        sections=tuple(sections), placed_parts=parts, geometries=geometries,
        instances=instances, join_count=len(jonction),
    )
