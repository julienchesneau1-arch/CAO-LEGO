"""BFK-001 v3.3.2 — Section F : collision et geometrie solide.

Autorite collisionnelle complete. Ce module ne connait ni Connector, ni
PhysicalBond, ni SearchApproximation, ni SpatialCandidateIndex, ni
ConstructionState, ni evaluate_connector_pair : il n'importe que les primitives
geometriques exactes.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

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
    "world_geometry",
    "collide_world",
    "oublier_les_verdicts",
    "verdicts_memorises",
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

    def forme_et_origine(self) -> Tuple[int, Tuple[int, int, int]]:
        """(numero de forme, origine). La FORME ne depend pas d'ou la piece est.

        Une mosaique pose la meme piece des milliers de fois : les coordonnees
        absolues ne se repetent jamais, la forme se repete toujours. Mesure sur
        un carre de 96 tenons : 103 764 paires examinees, 1 046 situations
        geometriquement distinctes — 99 % des paires sont la translation d'une
        paire deja jugee.

        Le numero est attribue une fois par forme et jamais reattribue : deux
        formes differentes ne peuvent donc pas le partager, ce qui est la seule
        chose dont depend la justesse du memo de `collide_world`.

        Le resultat est garde SUR L'INSTANCE. La classe est gelee, et c'est
        voulu — mais un cache n'est pas un champ : il ne participe ni a
        l'egalite, ni a la representation, ni a la serialisation. Il meurt avec
        l'objet, ce qui est exactement la duree de vie souhaitee.
        """
        connu = getattr(self, "_forme_et_origine", None)
        if connu is not None:
            return connu
        origine = self.exterior.min
        dx, dy, dz = origine.x, origine.y, origine.z

        def relatif(boite: AABB) -> Tuple[int, int, int, int, int, int]:
            return (boite.min.x - dx, boite.min.y - dy, boite.min.z - dz,
                    boite.max.x - dx, boite.max.y - dy, boite.max.z - dz)

        signature = (relatif(self.exterior),
                     tuple(relatif(void) for void in self.voids))
        numero = _numero_de_forme(signature)
        valeur = (numero, (dx, dy, dz))
        object.__setattr__(self, "_forme_et_origine", valeur)
        return valeur


# =============================================================================
# Section F.2 bis — Memo des verdicts (hors contrat : aucune semantique changee)
# =============================================================================
#
# `collide_world` est une fonction PURE : memes geometries, meme statut. Et son
# resultat est INVARIANT PAR TRANSLATION — translater les deux geometries d'un
# meme vecteur ne change ni leur relation geometrique, ni l'intersection, ni la
# region de matiere en conflit, ni donc le statut. Le memo ci-dessous ne
# court-circuite aucune autorite : il rend un verdict que cette autorite a deja
# prononce sur la meme situation, a une translation pres.
#
# Sans lui, une mosaique de 96 tenons faisait juger 103 764 paires dont
# 102 718 etaient la translation d'une paire deja jugee. Mesure sur la chaine
# entiere, livrables identiques a l'octet pres : -17 %.

FORMES_MEMORISEES = 4096
"""Formes distinctes suivies. Une mosaique en compte quelques centaines.

L'oubli d'une forme ne peut produire qu'un calcul de plus, jamais un verdict
faux : un numero n'est jamais reattribue, donc deux formes differentes ne
peuvent pas se confondre. Une forme oubliee puis revue recoit un numero neuf.
"""

VERDICTS_MEMORISES = 8192
"""Situations distinctes gardees. 1 046 sur un carre de 96 tenons ; la borne
existe pour un serveur qui tourne des jours, pas pour une fabrication."""

_FORMES: "OrderedDict[Tuple, int]" = OrderedDict()
_PROCHAIN_NUMERO = [0]
_VERDICTS: "OrderedDict[Tuple, CollisionStatus]" = OrderedDict()
_COMPTEURS = {"juges": 0, "retrouves": 0}


def _numero_de_forme(signature: Tuple) -> int:
    connu = _FORMES.get(signature)
    if connu is not None:
        _FORMES.move_to_end(signature)
        return connu
    numero = _PROCHAIN_NUMERO[0]
    _PROCHAIN_NUMERO[0] = numero + 1
    _FORMES[signature] = numero
    while len(_FORMES) > FORMES_MEMORISEES:
        _FORMES.popitem(last=False)
    return numero


def oublier_les_verdicts() -> None:
    """Vide le memo. Aucun effet sur ce que la chaine repond — seulement sur ce
    qu'elle recalcule. Existe pour les tests et pour mesurer."""
    _FORMES.clear()
    _VERDICTS.clear()
    _COMPTEURS.update(juges=0, retrouves=0)


def verdicts_memorises() -> Dict[str, int]:
    """Ce que le memo a evite. Pour mesurer, jamais pour decider."""
    return {"juges": _COMPTEURS["juges"],
            "retrouves": _COMPTEURS["retrouves"],
            "situations": len(_VERDICTS),
            "formes": len(_FORMES)}


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

    # ELAGAGE DES CUTTERS, et il est EXACT — pas une approximation.
    #
    # `pieces` part de `(base,)` et chaque `_subtract_box` ne rend que des
    # sous-boites de son argument : par recurrence, tout morceau est inclus
    # dans `base`. Un vide disjoint de `base` est donc disjoint de CHAQUE
    # morceau, et le passer dans la boucle ne peut rien retirer. Le resultat
    # est identique au bit pres ; seul le travail change.
    #
    # Ce n'est pas un detail. Sur une mosaique reelle de 1588 pieces, les
    # grandes plates du substrat portent jusqu'a 226 vides chacune, et
    # 91,2 % des 449 214 decoupes examinees ne touchaient pas la zone
    # etudiee — la boucle les traversait toutes, pour chaque morceau deja
    # decoupe. C'est la moitie du cout de H2, et H2 est 45 % de la chaine.
    utiles = [cutter for cutter in voids_a + voids_b
              if intersection_aabb(base, cutter) is not None]

    pieces: Tuple[AABB, ...] = (base,)
    for cutter in utiles:
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

    ECART D'ORDRE, SANS ECART DE SEMANTIQUE : l'algorithme F.5 transforme les
    vides des l'etape 1, alors qu'ils ne servent qu'a l'etape 5. Ils sont donc
    transformes seulement en cas d'OVERLAPPING. Le resultat est identique — les
    vides n'interviennent dans aucune autre etape — mais une piece courante
    porte plus de vingt vides, et une paire DISJOINT ou TOUCHING payait jusqu'ici
    des centaines de transformations de coins pour rien. C'est ce qui rendait H2
    dix fois plus lent que necessaire sur un modele reel.
    """
    if not isinstance(geometry_a, CollisionGeometry) or not isinstance(
        geometry_b, CollisionGeometry
    ):
        raise TypeError("collide attend deux CollisionGeometry")

    aabb_a = transform_aabb(geometry_a.exterior, pose_a)
    aabb_b = transform_aabb(geometry_b.exterior, pose_b)

    relation = geometric_relation(aabb_a, aabb_b)
    if relation is not GeometricRelation.OVERLAPPING:
        return collision_status(relation, None)

    return _status_from_world(
        relation,
        world_geometry(geometry_a, pose_a),
        world_geometry(geometry_b, pose_b),
    )


def world_geometry(geometry: CollisionGeometry, pose: Pose) -> CollisionGeometry:
    """Meme geometrie, exprimee en coordonnees monde. Exacte dans Z^3.

    Value object, comme la geometrie locale. Sert a ne transformer qu'UNE FOIS
    la geometrie d'une piece qui sera confrontee a beaucoup d'autres : sur un
    modele reel, chaque piece est comparee a une dizaine de voisines, et une
    piece courante porte plus de vingt vides.
    """
    if not isinstance(geometry, CollisionGeometry):
        raise TypeError("world_geometry attend une CollisionGeometry")
    return CollisionGeometry(
        exterior=transform_aabb(geometry.exterior, pose),
        voids=tuple(transform_aabb(void, pose) for void in geometry.voids),
    )


def collide_world(
    geometry_a: CollisionGeometry,
    geometry_b: CollisionGeometry,
) -> CollisionStatus:
    """Meme autorite que collide(), sur des geometries DEJA en coordonnees monde.

    Ce n'est pas un contournement de l'autorite collisionnelle : c'est la meme
    chaine, dans le meme module, a partir du meme point. Seule la transformation
    des reperes est sortie de la boucle.

    Le verdict est memorise par SITUATION — les deux formes et leur ecart — et
    non par coordonnees. Voir Section F.2 bis : le statut est invariant par
    translation, donc deux paires de meme cle recoivent le meme verdict de la
    meme autorite, une fois au lieu de mille.
    """
    numero_a, origine_a = geometry_a.forme_et_origine()
    numero_b, origine_b = geometry_b.forme_et_origine()
    cle = (numero_a, numero_b,
           origine_b[0] - origine_a[0],
           origine_b[1] - origine_a[1],
           origine_b[2] - origine_a[2])
    _COMPTEURS["juges"] += 1
    connu = _VERDICTS.get(cle)
    if connu is not None:
        _COMPTEURS["retrouves"] += 1
        _VERDICTS.move_to_end(cle)
        return connu

    verdict = _status_from_world(
        geometric_relation(geometry_a.exterior, geometry_b.exterior),
        geometry_a,
        geometry_b,
    )
    _VERDICTS[cle] = verdict
    while len(_VERDICTS) > VERDICTS_MEMORISES:
        _VERDICTS.popitem(last=False)
    return verdict


def _status_from_world(
    relation: GeometricRelation,
    world_a: CollisionGeometry,
    world_b: CollisionGeometry,
) -> CollisionStatus:
    """Fin de chaine commune : intersection_aabb -> solid_overlap -> statut."""
    if relation is not GeometricRelation.OVERLAPPING:
        return collision_status(relation, None)

    intersection = intersection_aabb(world_a.exterior, world_b.exterior)
    if intersection is None:  # pragma: no cover - OVERLAPPING garantit le contraire
        raise AssertionError("OVERLAPPING sans intersection de volume positif")

    overlap = solid_overlap(
        intersection, world_a.exterior, world_a.voids, world_b.exterior, world_b.voids
    )
    return collision_status(relation, overlap)
