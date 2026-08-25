"""BFK-001 v3.3.2 — Section E : oracle mecanique independant.

Autorite exclusive de creation des PhysicalBond (decision A.8).

Isolation contractuelle (verifiee par T1a / T1b) : ce module n'importe et
n'expose AUCUN symbole de recherche, d'accelerateur spatial, d'etat, de graphe,
de collision, de solveur ou de voxel. Ses seules dependances sont les
primitives geometriques (Section B/C) et le vocabulaire des connecteurs
(Section D).
"""

from __future__ import annotations

import math
import weakref
from typing import Optional

from .connectors import Connector, ConnectorTolerance, _compatible
from .geometry import (
    Pose,
    transform_local_direction_to_world,
    transform_local_to_world,
)

__all__ = ["PhysicalBond", "evaluate_connector_pair", "is_oracle_issued"]

# Jeton prive : seule `_issue_bond` le detient, donc seul l'oracle peut
# construire un PhysicalBond par la voie normale (Partie 3, regle 3).
_ORACLE_CREATION_TOKEN = object()

# Registre faible des bonds reellement emis par l'oracle. Il fonde H3 :
# un objet fabrique par contournement (object.__new__, sous-classe, pickle)
# n'y figure pas et sera rejete par le controle d'integrite d'autorite.
_ISSUED_BONDS: "weakref.WeakSet[PhysicalBond]" = weakref.WeakSet()


class PhysicalBond:
    """Type opaque. Autorite de creation EXCLUSIVE de evaluate_connector_pair.

    Aucune API publique de BFK-001 ne permet sa construction directe et le type
    n'expose aucun champ : un PhysicalBond ne se lit pas, il s'obtient.
    """

    __slots__ = ("__weakref__",)

    def __init__(self, _oracle_token: object = None) -> None:
        if _oracle_token is not _ORACLE_CREATION_TOKEN:
            raise TypeError(
                "PhysicalBond est opaque : seul evaluate_connector_pair() peut "
                "en creer un (contrat BFK-001, decision A.8)"
            )

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("PhysicalBond ne peut pas etre sous-classe (decision A.8)")

    def __repr__(self) -> str:
        return "<PhysicalBond emis par l'oracle>"


def _issue_bond() -> PhysicalBond:
    """Fabrique privee : unique point d'emission d'un PhysicalBond."""
    bond = PhysicalBond(_ORACLE_CREATION_TOKEN)
    _ISSUED_BONDS.add(bond)
    return bond


def is_oracle_issued(bond: object) -> bool:
    """Predicat d'integrite d'autorite (support de l'invariant H3).

    Retourne True si et seulement si l'objet a ete emis par cet oracle.
    """
    if type(bond) is not PhysicalBond:
        return False
    return bond in _ISSUED_BONDS


def evaluate_connector_pair(
    connector_a: Connector,
    pose_a: Pose,
    connector_b: Connector,
    pose_b: Pose,
    tolerance: ConnectorTolerance,
) -> Optional[PhysicalBond]:
    """Evalue si deux connecteurs forment un bond mecanique valide.

    Criteres BFK-001 (l'oracle conserve l'autorite ultime) :
    - compatibilite ctype : 'stud_male' <-> 'stud_female' uniquement ;
    - normales monde exactement opposees (egalite entiere, aucun epsilon) ;
    - max_angular_error_deg IGNORE (Section D.2) ;
    - distance euclidienne des positions monde <= max_position_error_ldu.

    La comparaison `sqrt(dx^2 + dy^2 + dz^2) <= max_position_error_ldu` est la
    SEULE operation flottante autorisee dans BFK-001 : dx, dy, dz et leur somme
    de carres restent entiers.

    Fonction pure : aucun etat lu ni ecrit hors du registre d'emission.
    """
    if not isinstance(connector_a, Connector) or not isinstance(connector_b, Connector):
        raise TypeError("evaluate_connector_pair attend deux Connector")
    if not isinstance(tolerance, ConnectorTolerance):
        raise TypeError("evaluate_connector_pair attend une ConnectorTolerance")

    if not _compatible(connector_a.ctype, connector_b.ctype):
        return None

    normal_a = transform_local_direction_to_world(connector_a.local_normal, pose_a[1])
    normal_b = transform_local_direction_to_world(connector_b.local_normal, pose_b[1])
    if normal_a != -normal_b:
        return None

    position_a = transform_local_to_world(connector_a.local_pos, pose_a)
    position_b = transform_local_to_world(connector_b.local_pos, pose_b)
    dx = position_a.x - position_b.x
    dy = position_a.y - position_b.y
    dz = position_a.z - position_b.z
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    if distance > tolerance.max_position_error_ldu:
        return None

    return _issue_bond()
