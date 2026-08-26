"""Export LDraw (.ldr) — HORS CONTRAT, couche 3.

Le registre notait cet export comme « absent, DELIBEREMENT » : ecrire un
exporteur sans les vraies origines de pieces produirait des fichiers faux, et
deviner ne vaut pas mieux que ne rien livrer. Deux donnees manquaient. Les
voici, toutes deux etablies sur un fichier de piece officiel et non de memoire.

CONVENTION D'AXES. LDraw pointe Y vers le BAS ; le noyau pointe Z vers le haut.
Le passage retenu est

    x_ldraw = x_noyau     y_ldraw = -z_noyau     z_ldraw = y_noyau

dont le determinant vaut +1. Ce n'est pas un detail : un determinant -1 serait
une REFLEXION, et une mosaique exportee en miroir serait fausse sans que rien
ne le signale — un visage inverse, un texte a l'envers. `_verifier_axes()` le
verifie a l'import du module.

ORIGINE DES PIECES. Lue dans 3001.dat (Brick 2 x 4) de la bibliotheque LDraw
officielle, redistribuable sous CCAL 2.0 :

    corps      x de -40 a 40, z de -20 a 20, y de 0 a 24
    tubes      descendent jusqu'a y = 24

Donc l'origine est au CENTRE de l'empreinte en x et z, et a la FACE SUPERIEURE
du corps en y — le corps pend en dessous, les tenons depassent au-dessus.

Ce que cette lecture ne prouve pas : que toutes les pieces rectangulaires
suivent la meme convention. Un seul fichier de piece etait disponible. Elle
vaut donc pour la famille des briques, plates et tuiles rectangulaires, qui est
exactement ce que ce depot emploie — et l'en-tete du fichier produit le dit.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence, Tuple

from .catalog import CATALOG, PartInstance
from .geometry import (
    LDUVector,
    Orientation,
    transform_local_direction_to_world,
)
from .search import PlacedPart

__all__ = ["dumps_ldr", "to_ldraw_point", "part_origin_offset"]


def to_ldraw_point(x: int, y: int, z: int) -> Tuple[int, int, int]:
    """Point du noyau -> point LDraw. Rotation propre, jamais une reflexion."""
    return (x, -z, y)


def _verifier_axes() -> None:
    """Le changement d'axes doit etre une rotation (determinant +1).

    Verifie a l'import, sur les images des trois vecteurs de base. Un
    determinant -1 exporterait toute mosaique en miroir.
    """
    colonnes = [to_ldraw_point(*base) for base in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    (a, b, c), (d, e, f), (g, h, i) = zip(*colonnes)
    determinant = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if determinant != 1:  # pragma: no cover - garde-fou d'import
        raise AssertionError(
            f"le changement d'axes a un determinant de {determinant} : ce n'est "
            "pas une rotation, la mosaique sortirait en miroir"
        )


_verifier_axes()


def part_origin_offset(design_id: str) -> Tuple[int, int, int]:
    """Decalage, en LDU du noyau, du coin bas de l'AABB vers l'origine LDraw.

    L'origine LDraw est au centre de l'empreinte et a la face superieure du
    CORPS — hauteur du corps, sans les tenons, qui depassent au-dessus.
    """
    piece = CATALOG[design_id]
    from .lego import STUD_PITCH_LDU

    return (
        piece.studs_x * STUD_PITCH_LDU // 2,
        piece.studs_y * STUD_PITCH_LDU // 2,
        piece.body_height_ldu,
    )


def _matrice_ldraw(orientation: Orientation) -> Tuple[int, ...]:
    """Orientation du noyau -> matrice 3x3 LDraw, en ordre ligne par ligne.

    Conjugaison par le changement d'axes : M_ldraw = C . M_noyau . C^-1. On la
    calcule en transportant les images des vecteurs de base, ce qui evite
    d'ecrire C a la main et de se tromper de signe.
    """
    colonnes = []
    for base in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
        # C^-1 de la base LDraw, puis M du noyau, puis C.
        noyau = (base[0], base[2], -base[1])
        tourne = orientation.apply(LDUVector(*noyau))
        colonnes.append(to_ldraw_point(tourne.x, tourne.y, tourne.z))
    return tuple(colonnes[colonne][ligne] for ligne in range(3) for colonne in range(3))


def dumps_ldr(
    placed_parts: Mapping[str, PlacedPart],
    instances: Mapping[str, PartInstance],
    name: str = "Mosaique",
) -> str:
    """Modele du noyau -> fichier LDraw, lisible par LeoCAD, Studio, LDView.

    Chaque piece devient une ligne de type 1 : couleur, position, matrice,
    fichier. Les identifiants de reference du noyau SONT ceux de LDraw — c'est
    de la que le catalogue les tient, verifies contre `parts.lst`.
    """
    manquantes = sorted(set(placed_parts) - set(instances))
    if manquantes:
        raise KeyError(
            f"identite catalogue absente pour {', '.join(manquantes[:5])} : "
            "un export LDraw sans reference produirait un fichier illisible."
        )

    lignes = [
        f"0 {name}",
        "0 Name: modele.ldr",
        "0 Author: BFK-001",
        "0 !LDRAW_ORG Unofficial_Model",
        "0 // Axes : x_ldraw = x_noyau, y_ldraw = -z_noyau, z_ldraw = y_noyau",
        "0 // Origines : centre de l'empreinte, face superieure du corps.",
        "0 // Convention lue dans 3001.dat officiel ; vaut pour les pieces",
        "0 // rectangulaires (briques, plates, tuiles), seules employees ici.",
    ]
    for part_id in sorted(placed_parts):
        piece = placed_parts[part_id]
        instance = instances[part_id]
        # L'origine LDraw se deduit de la POSE, jamais de l'AABB. Le decalage
        # du coin local vers l'origine LDraw est un VECTEUR LOCAL : il subit la
        # rotation seule, puis on ajoute la translation. Le calculer depuis
        # l'AABB marchait tant qu'aucune piece n'etait tournee, et se decalait
        # de 20 LDU des qu'une piece l'etait — c'est la regle position/direction
        # du contrat, et elle se venge ici comme ailleurs.
        translation, orientation = piece.pose
        decalage = transform_local_direction_to_world(
            LDUVector(*part_origin_offset(instance.design_id)), orientation
        )
        x, y, z = to_ldraw_point(
            translation.x + decalage.x,
            translation.y + decalage.y,
            translation.z + decalage.z,
        )
        matrice = " ".join(str(v) for v in _matrice_ldraw(piece.pose[1]))
        lignes.append(
            f"1 {instance.color_id} {x} {y} {z} {matrice} {instance.design_id}.dat"
        )
    lignes.append("0")
    return "\n".join(lignes) + "\n"
