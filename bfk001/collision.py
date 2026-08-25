"""BFK-001 v3.3.2 — Section F : collision et geometrie solide.

Autorite collisionnelle complete. Ce module ne connait ni Connector, ni
PhysicalBond, ni SearchApproximation, ni SpatialCandidateIndex, ni
ConstructionState, ni evaluate_connector_pair : il n'importe que les primitives
geometriques exactes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple

from .geometry import (
    AABB,
    GeometricRelation,
    LDUVector,
    Pose,
    geometric_relation,
    intersection_aabb,
    transform_aabb,
)

__all__ = [
    "CollisionStatus",
    "CollisionGeometry",
    "solid_overlap",
    "collision_status",
    "collide",
]


# =============================================================================
# Section F.1 — CollisionStatus
# =============================================================================


class CollisionStatus(Enum):
    """Autorite de classification collisionnelle."""

    CLEAR = auto()
    CONTACT = auto()
    PENETRATION = auto()


# =============================================================================
# Section F.2 — CollisionGeometry
# =============================================================================


@dataclass(frozen=True)
class CollisionGeometry:
    """Geometrie solide d'une piece dans son repere LOCAL.

    `exterior` et `voids` sont exprimes dans le repere local de la piece ;
    collide() les transforme en coordonnees monde avant toute comparaison.
    """

    exterior: AABB
    voids: Tuple[AABB, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.exterior, AABB):
            raise TypeError("CollisionGeometry.exterior doit etre un AABB")
        if not isinstance(self.voids, tuple):
            raise TypeError(
                "CollisionGeometry.voids doit etre un Tuple[AABB, ...], jamais une List"
            )
        for void in self.voids:
            if not isinstance(void, AABB):
                raise TypeError("CollisionGeometry.voids ne contient que des AABB")


# =============================================================================
# Section F.3 — solid_overlap : autorite geometrique exacte
# =============================================================================


def _subtract_box(box: AABB, cutter: AABB) -> Tuple[AABB, ...]:
    """box prive de cutter, decompose en au plus 6 dalles d'interieurs disjoints.

    Si le recouvrement est de volume nul, `box` est retourne inchange : retirer
    une tranche d'epaisseur nulle ne retire aucune matiere.
    """
    clipped = intersection_aabb(box, cutter)
    if clipped is None:
        return (box,)

    pieces: List[AABB] = []

    if box.min.x < clipped.min.x:
        pieces.append(
            AABB(box.min, LDUVector(clipped.min.x, box.max.y, box.max.z))
        )
    if clipped.max.x < box.max.x:
        pieces.append(
            AABB(LDUVector(clipped.max.x, box.min.y, box.min.z), box.max)
        )
    if box.min.y < clipped.min.y:
        pieces.append(
            AABB(
                LDUVector(clipped.min.x, box.min.y, box.min.z),
                LDUVector(clipped.max.x, clipped.min.y, box.max.z),
            )
        )
    if clipped.max.y < box.max.y:
        pieces.append(
            AABB(
                LDUVector(clipped.min.x, clipped.max.y, box.min.z),
                LDUVector(clipped.max.x, box.max.y, box.max.z),
            )
        )
    if box.min.z < clipped.min.z:
        pieces.append(
            AABB(
                LDUVector(clipped.min.x, clipped.min.y, box.min.z),
                LDUVector(clipped.max.x, clipped.max.y, clipped.min.z),
            )
        )
    if clipped.max.z < box.max.z:
        pieces.append(
            AABB(
                LDUVector(clipped.min.x, clipped.min.y, clipped.max.z),
                LDUVector(clipped.max.x, clipped.max.y, box.max.z),
            )
        )
    return tuple(pieces)


def _require_void_tuple(voids: Tuple[AABB, ...], name: str) -> Tuple[AABB, ...]:
    if not isinstance(voids, tuple):
        raise TypeError(f"{name} doit etre un Tuple[AABB, ...], jamais une List")
    for void in voids:
        if not isinstance(void, AABB):
            raise TypeError(f"{name} ne contient que des AABB")
    return voids


def solid_overlap(
    intersection: AABB,
    solid_a: AABB,
    voids_a: Tuple[AABB, ...],
    solid_b: AABB,
    voids_b: Tuple[AABB, ...],
) -> Optional[Tuple[AABB, ...]]:
    """Region de matiere solide effectivement penetree, apres retrait des voids.

    R = (intersection inter solid_a inter solid_b) prive de (voids_a union voids_b).
    Un point de cette base appartient a la matiere de A s'il n'est dans aucun
    void de A, et a la matiere de B s'il n'est dans aucun void de B : la region
    de conflit est donc exactement la base privee de l'union des voids.

    Retourne None si R est de volume nul.
    Retourne sinon une partition exacte P = (r1, ..., rn) :
      - Union(P) = R exactement (ni sur-approximation, ni sous-approximation) ;
      - interieurs deux a deux disjoints (les rI peuvent se toucher) ;
      - aucun rI de volume nul.
    Aucune canonicalisation n'est imposee.
    """
    for name, value in (
        ("intersection", intersection),
        ("solid_a", solid_a),
        ("solid_b", solid_b),
    ):
        if not isinstance(value, AABB):
            raise TypeError(f"solid_overlap : {name} doit etre un AABB")
    _require_void_tuple(voids_a, "voids_a")
    _require_void_tuple(voids_b, "voids_b")

    base = intersection_aabb(intersection, solid_a)
    if base is None:
        return None
    base = intersection_aabb(base, solid_b)
    if base is None:
        return None

    pieces: Tuple[AABB, ...] = (base,)
    for cutter in voids_a + voids_b:
        if not pieces:
            break
        carved: List[AABB] = []
        for piece in pieces:
            carved.extend(_subtract_box(piece, cutter))
        pieces = tuple(carved)

    return pieces if pieces else None


# =============================================================================
# Section F.4 — Derivation du CollisionStatus
# =============================================================================


def collision_status(
    relation: GeometricRelation,
    overlap: Optional[Tuple[AABB, ...]],
) -> CollisionStatus:
    """Traduit la relation geometrique et le resultat de solid_overlap en statut.

    - DISJOINT    -> CLEAR        (overlap doit etre None)
    - TOUCHING    -> CONTACT      (overlap doit etre None)
    - OVERLAPPING + overlap is None     -> CONTACT     (engagement dans les voids)
    - OVERLAPPING + overlap non vide    -> PENETRATION (matiere solide en conflit)

    Une partition vide `()` est une violation de precondition : solid_overlap
    retourne None pour une region de volume nul.
    """
    if not isinstance(relation, GeometricRelation):
        raise TypeError("collision_status attend une GeometricRelation")
    if overlap is not None:
        if not isinstance(overlap, tuple):
            raise TypeError("overlap doit etre None ou un Tuple[AABB, ...]")
        if not overlap:
            raise ValueError(
                "partition vide interdite : une region de volume nul vaut None"
            )
        for piece in overlap:
            if not isinstance(piece, AABB):
                raise TypeError("overlap ne contient que des AABB")

    if relation is GeometricRelation.DISJOINT:
        if overlap is not None:
            raise ValueError("DISJOINT impose overlap is None")
        return CollisionStatus.CLEAR

    if relation is GeometricRelation.TOUCHING:
        if overlap is not None:
            raise ValueError("TOUCHING impose overlap is None")
        return CollisionStatus.CONTACT

    return CollisionStatus.CONTACT if overlap is None else CollisionStatus.PENETRATION


# =============================================================================
# Section F.5 — collide : autorite collisionnelle complete
# =============================================================================


def collide(
    geometry_a: CollisionGeometry,
    pose_a: Pose,
    geometry_b: CollisionGeometry,
    pose_b: Pose,
) -> CollisionStatus:
    """Evalue le statut collisionnel entre deux pieces placees dans l'espace.

    Chaine contractuelle :
      transform_aabb -> geometric_relation -> intersection_aabb
                     -> solid_overlap -> collision_status

    La derivation finale passe toujours par collision_status(), unique autorite
    de traduction relation/overlap -> statut (Section F.4).
    """
    if not isinstance(geometry_a, CollisionGeometry) or not isinstance(
        geometry_b, CollisionGeometry
    ):
        raise TypeError("collide attend deux CollisionGeometry")

    aabb_a = transform_aabb(geometry_a.exterior, pose_a)
    voids_a_m = tuple(transform_aabb(void, pose_a) for void in geometry_a.voids)
    aabb_b = transform_aabb(geometry_b.exterior, pose_b)
    voids_b_m = tuple(transform_aabb(void, pose_b) for void in geometry_b.voids)

    relation = geometric_relation(aabb_a, aabb_b)
    if relation is not GeometricRelation.OVERLAPPING:
        return collision_status(relation, None)

    intersection = intersection_aabb(aabb_a, aabb_b)
    if intersection is None:  # pragma: no cover - OVERLAPPING garantit le contraire
        raise AssertionError("OVERLAPPING sans intersection de volume positif")

    overlap = solid_overlap(intersection, aabb_a, voids_a_m, aabb_b, voids_b_m)
    return collision_status(relation, overlap)
