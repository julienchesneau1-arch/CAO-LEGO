"""BFK-001 v3.3.2 — Section L : support et fondation.

Arithmetique exacte, entiere. Aucun epsilon : min.z est contractuellement un
entier.

INTERPRETATION (signalee dans README.md) : `part_exterior` est exprime dans le
repere LOCAL de la piece, comme CollisionGeometry.exterior, et transforme par
`part_pose`. C'est la seule lecture qui justifie de recevoir une Pose complete
plutot qu'une simple Orientation (la normale, elle, n'utilise que part_pose[1]).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Tuple

from .connectors import CTYPE_STUD_FEMALE, Connector
from .geometry import (
    AABB,
    LDUVector,
    Pose,
    transform_aabb,
    transform_local_direction_to_world,
)

__all__ = ["FoundationStatus", "FoundationCheck", "check_foundation"]

_DOWNWARD = LDUVector(0, 0, -1)


class FoundationStatus(Enum):
    """Statut d'une piece vis-a-vis du plan de fondation."""

    INVALID = auto()    # penetre le sol
    UNFOUNDED = auto()  # non fondee : doit posseder une chaine de bonds (H4)
    FOUNDED = auto()    # fondee geometriquement


@dataclass(frozen=True)
class FoundationCheck:
    """Resultat de check_foundation."""

    status: FoundationStatus
    world_min_z: int

    def __post_init__(self) -> None:
        if not isinstance(self.status, FoundationStatus):
            raise TypeError("FoundationCheck.status doit etre un FoundationStatus")
        if isinstance(self.world_min_z, bool) or not isinstance(self.world_min_z, int):
            raise TypeError("FoundationCheck.world_min_z doit etre un entier")

    @property
    def is_founded(self) -> bool:
        return self.status is FoundationStatus.FOUNDED

    @property
    def is_valid(self) -> bool:
        return self.status is not FoundationStatus.INVALID


def check_foundation(
    part_exterior: AABB,
    part_connectors: Tuple[Connector, ...],
    part_pose: Pose,
    foundation_plane_z: int = 0,
) -> FoundationCheck:
    """Regles exactes (Section L) :

    - min.z < foundation_plane_z  -> INVALIDE (la piece penetre le sol)
    - min.z > foundation_plane_z  -> NON fondee (elle doit avoir un bond)
    - min.z == foundation_plane_z -> Fondee si et seulement si la piece possede
      au moins un Connector de ctype 'stud_female' dont la normale transformee
      vaut exactement (0, 0, -1) ; sinon NON fondee.
    """
    if not isinstance(part_exterior, AABB):
        raise TypeError("check_foundation attend un AABB pour part_exterior")
    if not isinstance(part_connectors, tuple):
        raise TypeError(
            "check_foundation attend un Tuple[Connector, ...], jamais une List"
        )
    if isinstance(foundation_plane_z, bool) or not isinstance(foundation_plane_z, int):
        raise TypeError("foundation_plane_z doit etre un entier (aucun epsilon)")

    world_exterior = transform_aabb(part_exterior, part_pose)
    world_min_z = world_exterior.min.z

    if world_min_z < foundation_plane_z:
        return FoundationCheck(FoundationStatus.INVALID, world_min_z)
    if world_min_z > foundation_plane_z:
        return FoundationCheck(FoundationStatus.UNFOUNDED, world_min_z)

    for connector in part_connectors:
        if not isinstance(connector, Connector):
            raise TypeError("part_connectors ne contient que des Connector")
        if connector.ctype != CTYPE_STUD_FEMALE:
            continue
        if transform_local_direction_to_world(
            connector.local_normal, part_pose[1]
        ) == _DOWNWARD:
            return FoundationCheck(FoundationStatus.FOUNDED, world_min_z)

    return FoundationCheck(FoundationStatus.UNFOUNDED, world_min_z)
