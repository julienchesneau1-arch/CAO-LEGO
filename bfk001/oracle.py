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

    POURQUOI CE N'EST PAS UN @dataclass(frozen=True), contrairement au stub du
    contrat : un dataclass gele SANS CHAMP donne a toutes ses instances la meme
    valeur et le meme hash. Deux bonds quelconques seraient alors egaux, et un
    bond fabrique hors oracle appartiendrait au registre d'emission des qu'un
    seul vrai bond y figure — H3 deviendrait vide de sens tout en paraissant
    passer. L'identite d'objet n'est donc pas une preference d'implementation :
    c'est la condition pour que H3 morde. Verifie par
    test_bond_identity_is_required_for_h3.

    Consequence assumee : un bond est un JETON, pas une valeur. Deux appels a
    l'oracle sur la meme entree rendent le meme verdict mais deux jetons
    distincts. La purete de l'oracle porte sur le verdict, pas sur l'identite
    de l'objet emis.
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

    def __copy__(self) -> "PhysicalBond":
        """Un jeton immuable se copie en lui-meme.

        Sans cela, copier un ConstructionState — reflexe naturel pour du
        backtracking — transformerait chaque bond en contrefacon et ferait
        echouer H3 sur un etat pourtant legitime.
        """
        return self

    def __deepcopy__(self, memo: object) -> "PhysicalBond":
        return self

    def __reduce__(self):
        raise TypeError(
            "un PhysicalBond ne se serialise pas : il serait ressuscite hors de "
            "l'oracle et violerait H3. Serialiser les pieces (bfk001.serialization) "
            "et laisser l'oracle re-emettre les liaisons au chargement."
        )

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

    Purete : le VERDICT est une fonction pure de l'entree — memes connecteurs,
    memes poses, meme tolerance donnent toujours la meme reponse (liaison ou
    absence de liaison). Chaque verdict positif frappe en revanche un jeton
    neuf, inscrit au registre d'emission : c'est ce qui rend H3 verifiable.
    L'oracle ne lit ni n'ecrit aucun autre etat.
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
    squared_distance = dx * dx + dy * dy + dz * dz

    # Ecartement EXACT avant tout flottant. Z^3 n'est pas borne : au-dela
    # d'environ 1e154 LDU, math.sqrt() leve OverflowError alors que le contrat
    # promet une arithmetique exacte sur des entiers arbitraires. math.isqrt
    # calcule floor(racine) sur n'importe quel entier ; si ce plancher depasse
    # deja ceil(tolerance), alors la distance reelle depasse la tolerance, sans
    # la moindre ambiguite. Le verdict est identique, la portee est totale.
    if math.isqrt(squared_distance) > math.ceil(tolerance.max_position_error_ldu):
        return None

    distance = math.sqrt(squared_distance)
    if distance > tolerance.max_position_error_ldu:
        return None

    return _issue_bond()
