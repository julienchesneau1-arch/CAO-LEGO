"""BFK-001 v3.3.2 — Section D : connecteurs et tolerance.

Ce module porte le vocabulaire des types de connecteurs, y compris la relation
de compatibilite `_compatible`. Placement : le contrat ecrit `_compatible` dans
le bloc de code de la Section H, mais l'oracle (Section E) DOIT l'evaluer sans
importer le module de recherche (contrainte E : "ne connait PAS
SearchApproximation"). La relation est donc definie ici, au niveau Connector du
DAG (Section O), et importee par les deux consommateurs. Ecart signale dans
README.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from .geometry import LDUVector

__all__ = ["Connector", "ConnectorTolerance"]

CTYPE_STUD_MALE = "stud_male"
CTYPE_STUD_FEMALE = "stud_female"

_AXIAL_UNIT_NORMALS: Tuple[Tuple[int, int, int], ...] = (
    (1, 0, 0),
    (-1, 0, 0),
    (0, 1, 0),
    (0, -1, 0),
    (0, 0, 1),
    (0, 0, -1),
)


# `slots=True` n'est pas une micro-optimisation de confort : sans lui, chaque
# instance porte un `__dict__` vide de plus de cent octets, et ces classes se
# comptent par centaines de milliers. Mesure sur 200 000 boites : 523 octets
# l'une sans slots, 351 avec — un tiers de moins. Rien d'autre ne change :
# la classe reste gelee, l'egalite, la representation et `astuple` sont
# identiques. Aucun code de ce depot ne lit le `__dict__` de ces objets
# (verifie), et c'est precisement ce que slots retire.
@dataclass(frozen=True, slots=True)
class Connector:
    """Connecteur mecanique exprime dans le repere LOCAL de la piece.

    local_normal : exactement une composante non nulle, de valeur +1 ou -1
    (l'une des 6 directions axiales unitaires, contrainte D.1).
    """

    ctype: str
    local_pos: LDUVector
    local_normal: LDUVector

    def __post_init__(self) -> None:
        if not isinstance(self.ctype, str) or not self.ctype:
            raise TypeError("Connector.ctype doit etre une chaine non vide")
        if not isinstance(self.local_pos, LDUVector):
            raise TypeError("Connector.local_pos doit etre un LDUVector")
        if not isinstance(self.local_normal, LDUVector):
            raise TypeError("Connector.local_normal doit etre un LDUVector")
        if self.local_normal.as_tuple() not in _AXIAL_UNIT_NORMALS:
            raise ValueError(
                "Connector.local_normal doit etre l'une des 6 directions axiales "
                f"unitaires (recu : {self.local_normal.as_tuple()})"
            )


@dataclass(frozen=True)
class ConnectorTolerance:
    """Parametre d'entree de l'oracle mecanique. Aucune valeur par defaut (A.2).

    max_angular_error_deg est contractuellement present mais explicitement NON
    utilise par l'oracle en BFK-001 (reserve a BFK-002).
    """

    max_position_error_ldu: float
    max_angular_error_deg: float

    def __post_init__(self) -> None:
        for name in ("max_position_error_ldu", "max_angular_error_deg"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"ConnectorTolerance.{name} doit etre un reel")
            if not math.isfinite(value):
                raise ValueError(
                    f"ConnectorTolerance.{name} doit etre un reel fini "
                    "(ni NaN, ni infini : une tolerance infinie connecterait "
                    "tout a tout et viderait l'oracle de son role)"
                )
            if value < 0:
                raise ValueError(f"ConnectorTolerance.{name} ne peut pas etre negatif")


def _compatible(ctype_a: str, ctype_b: str) -> bool:
    """BFK-001 definit exactement : 'stud_male' <-> 'stud_female'.

    Tout autre couple est non compatible (rejete ou reserve a une version
    ulterieure).
    """
    return (ctype_a == CTYPE_STUD_MALE and ctype_b == CTYPE_STUD_FEMALE) or (
        ctype_a == CTYPE_STUD_FEMALE and ctype_b == CTYPE_STUD_MALE
    )
