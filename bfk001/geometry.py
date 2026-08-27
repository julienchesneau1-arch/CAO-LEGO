"""BFK-001 v3.3.2 — Sections B et C : primitives geometriques exactes.

Autorite : arithmetique exacte dans Z^3 (decision A.1).
Aucun flottant n'apparait dans ce module. Toute transformation est une
composition de translations entieres et de rotations a 90 degres.

Ce module est la racine du DAG (Section O) : il n'importe aucun autre module
du noyau.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Tuple, TypeAlias

__all__ = [
    "LDUVector",
    "AABB",
    "GeometricRelation",
    "Orientation",
    "Pose",
    "geometric_relation",
    "intersection_aabb",
    "transform_aabb",
    "transform_local_to_world",
    "transform_local_direction_to_world",
    "transform_world_to_local",
    "invert_pose",
    "compose_poses",
]

_ALLOWED_COEFFICIENTS = (-1, 0, 1)


def _require_int(value: object, name: str) -> None:
    """Rejette tout ce qui n'est pas un element de Z (bool exclu).

    Le premier test n'est pas une simplification du second : c'est le MEME
    verdict pris plus vite. `type(value) is int` accepte exactement les entiers
    natifs — donc jamais `bool`, dont le type est `bool` et non `int` — et ce
    cas represente la quasi-totalite des appels. Une sous-classe d'entier
    (`IntEnum`) retombe sur le test complet, qui l'accepte comme avant.

    Mesure, parce que le profileur m'a menti ici. Il attribuait a cette
    fonction 4,3 s sur 50 — elle est appelee onze millions de fois pour une
    mosaique de 96 tenons, et cProfile facture son propre cout PAR APPEL : ce
    sont les fonctions les plus appelees qu'il gonfle le plus. Le gain reel
    est de 40 % sur la fonction et de moins de 2 % sur la chaine.

    On le garde — deux lignes, verdict prouve identique — mais sans se
    raconter d'histoire : ce n'est pas la qu'etait le temps. Il etait dans un
    parcours de graphe quadratique (§ 5.58).
    """
    if type(value) is int:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            f"{name} doit etre un entier de Z (recu : {type(value).__name__})"
        )


# =============================================================================
# Section B.1 — LDUVector
# =============================================================================


@dataclass(frozen=True)
class LDUVector:
    """Element de Z^3. Aucune operation ne produit de coordonnee non entiere."""

    x: int
    y: int
    z: int

    def __post_init__(self) -> None:
        _require_int(self.x, "x")
        _require_int(self.y, "y")
        _require_int(self.z, "z")

    def __neg__(self) -> "LDUVector":
        return LDUVector(-self.x, -self.y, -self.z)

    def __add__(self, other: object) -> "LDUVector":
        if not isinstance(other, LDUVector):
            return NotImplemented
        return LDUVector(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: object) -> "LDUVector":
        if not isinstance(other, LDUVector):
            return NotImplemented
        return LDUVector(self.x - other.x, self.y - other.y, self.z - other.z)

    def as_tuple(self) -> Tuple[int, int, int]:
        return (self.x, self.y, self.z)


# =============================================================================
# Section B.2 — AABB
# =============================================================================


@dataclass(frozen=True)
class AABB:
    """Axis-Aligned Bounding Box.

    Precondition : min.x <= max.x, min.y <= max.y, min.z <= max.z.
    """

    min: LDUVector
    max: LDUVector

    def __post_init__(self) -> None:
        if not isinstance(self.min, LDUVector) or not isinstance(self.max, LDUVector):
            raise TypeError("AABB.min et AABB.max doivent etre des LDUVector")
        if self.min.x > self.max.x or self.min.y > self.max.y or self.min.z > self.max.z:
            raise ValueError(f"AABB invalide : min={self.min} > max={self.max}")


# =============================================================================
# Section C.1 — Orientation
# =============================================================================


@dataclass(frozen=True)
class Orientation:
    """Matrice de rotation 3x3 entiere.

    Coefficients dans {-1, 0, 1}, M^T M = I, det(M) = +1 : exactement les 24
    rotations du groupe des rotations a 90 degres (Partie 3, regle 6).
    """

    m00: int
    m01: int
    m02: int
    m10: int
    m11: int
    m12: int
    m20: int
    m21: int
    m22: int

    def __post_init__(self) -> None:
        for name in (
            "m00", "m01", "m02",
            "m10", "m11", "m12",
            "m20", "m21", "m22",
        ):
            value = getattr(self, name)
            _require_int(value, name)
            if value not in _ALLOWED_COEFFICIENTS:
                raise ValueError(
                    f"{name}={value} hors de {{-1, 0, 1}} (contrainte C.1)"
                )

        rows = self.rows()
        for i in range(3):
            for j in range(3):
                expected = 1 if i == j else 0
                dot = sum(rows[k][i] * rows[k][j] for k in range(3))
                if dot != expected:
                    raise ValueError(
                        "Orientation non orthogonale : M^T M != I (contrainte C.1)"
                    )
        if self.determinant() != 1:
            raise ValueError(
                f"determinant = {self.determinant()} != +1 : reflexion interdite (C.1)"
            )

    @classmethod
    def identity(cls) -> "Orientation":
        return cls(1, 0, 0, 0, 1, 0, 0, 0, 1)

    def rows(self) -> Tuple[Tuple[int, int, int], ...]:
        return (
            (self.m00, self.m01, self.m02),
            (self.m10, self.m11, self.m12),
            (self.m20, self.m21, self.m22),
        )

    def determinant(self) -> int:
        (a, b, c), (d, e, f), (g, h, i) = self.rows()
        return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)

    def apply(self, vector: LDUVector) -> LDUVector:
        """Produit matrice-vecteur exact dans Z^3."""
        if not isinstance(vector, LDUVector):
            raise TypeError("Orientation.apply attend un LDUVector")
        x, y, z = vector.x, vector.y, vector.z
        return LDUVector(
            self.m00 * x + self.m01 * y + self.m02 * z,
            self.m10 * x + self.m11 * y + self.m12 * z,
            self.m20 * x + self.m21 * y + self.m22 * z,
        )

    def inverse(self) -> "Orientation":
        """Rotation inverse = transposee (la matrice est orthogonale).

        Exacte dans Z : aucune division. Ajout hors contrat, indispensable au
        passage monde -> local (selection, ancrage, repositionnement).
        """
        return Orientation(
            self.m00, self.m10, self.m20,
            self.m01, self.m11, self.m21,
            self.m02, self.m12, self.m22,
        )

    def compose(self, other: "Orientation") -> "Orientation":
        """Composition exacte : (self o other).apply(v) == self.apply(other.apply(v))."""
        if not isinstance(other, Orientation):
            raise TypeError("Orientation.compose attend une Orientation")
        left = self.rows()
        right = other.rows()
        product = tuple(
            tuple(sum(left[i][k] * right[k][j] for k in range(3)) for j in range(3))
            for i in range(3)
        )
        return Orientation(*(value for row in product for value in row))


# =============================================================================
# Section C.2 — Pose
# =============================================================================

Pose: TypeAlias = Tuple[LDUVector, Orientation]
"""Donnee d'une translation entiere et d'une rotation discrete."""


def _validate_pose(pose: Pose) -> Pose:
    if not isinstance(pose, tuple) or len(pose) != 2:
        raise TypeError("Pose doit etre un Tuple[LDUVector, Orientation]")
    translation, orientation = pose
    if not isinstance(translation, LDUVector):
        raise TypeError("pose[0] doit etre un LDUVector (translation)")
    if not isinstance(orientation, Orientation):
        raise TypeError("pose[1] doit etre une Orientation")
    return pose


# =============================================================================
# Section B.3 — Relations geometriques entre AABB
# =============================================================================


class GeometricRelation(Enum):
    """Relation topologique entre deux AABB. Arithmetique exacte sur les entiers."""

    DISJOINT = auto()
    TOUCHING = auto()
    OVERLAPPING = auto()


def _overlap_intervals(a: AABB, b: AABB) -> Tuple[Tuple[int, int], ...]:
    """Intervalle de recouvrement [max(min), min(max)] sur chaque axe."""
    return (
        (max(a.min.x, b.min.x), min(a.max.x, b.max.x)),
        (max(a.min.y, b.min.y), min(a.max.y, b.max.y)),
        (max(a.min.z, b.min.z), min(a.max.z, b.max.z)),
    )


def geometric_relation(a: AABB, b: AABB) -> GeometricRelation:
    """Determine la relation topologique entre deux AABB.

    DISJOINT     : separation stricte sur au moins un axe.
    OVERLAPPING  : recouvrement de longueur strictement positive sur les 3 axes
                   (donc volume d'intersection strictement positif).
    TOUCHING     : intersection non vide mais de volume nul (face, arete, sommet).
    """
    if not isinstance(a, AABB) or not isinstance(b, AABB):
        raise TypeError("geometric_relation attend deux AABB")

    intervals = _overlap_intervals(a, b)
    if any(low > high for low, high in intervals):
        return GeometricRelation.DISJOINT
    if all(low < high for low, high in intervals):
        return GeometricRelation.OVERLAPPING
    return GeometricRelation.TOUCHING


# =============================================================================
# Section B.4 — Intersection AABB
# =============================================================================


def intersection_aabb(a: AABB, b: AABB) -> Optional[AABB]:
    """Retourne l'AABB d'intersection si son volume est strictement positif.

    Un contact de volume nul (face, arete, sommet) retourne None.
    """
    if geometric_relation(a, b) is not GeometricRelation.OVERLAPPING:
        return None
    (x0, x1), (y0, y1), (z0, z1) = _overlap_intervals(a, b)
    return AABB(LDUVector(x0, y0, z0), LDUVector(x1, y1, z1))


# =============================================================================
# Section B.5 — Transformation d'AABB
# =============================================================================


def transform_aabb(aabb: AABB, pose: Pose) -> AABB:
    """Transforme les 8 coins de l'AABB par la pose et retourne l'AABB englobant.

    Sous une rotation a 90 degres, l'image d'une boite axis-aligned est une boite
    axis-aligned : le resultat est donc EXACT, jamais une sur-approximation.
    """
    if not isinstance(aabb, AABB):
        raise TypeError("transform_aabb attend un AABB")
    _validate_pose(pose)

    corners = tuple(
        transform_local_to_world(LDUVector(x, y, z), pose)
        for x in (aabb.min.x, aabb.max.x)
        for y in (aabb.min.y, aabb.max.y)
        for z in (aabb.min.z, aabb.max.z)
    )
    return AABB(
        LDUVector(
            min(c.x for c in corners),
            min(c.y for c in corners),
            min(c.z for c in corners),
        ),
        LDUVector(
            max(c.x for c in corners),
            max(c.y for c in corners),
            max(c.z for c in corners),
        ),
    )


# =============================================================================
# Section C.3 — Transformation d'une POSITION local -> monde
# =============================================================================


def transform_local_to_world(local: LDUVector, pose: Pose) -> LDUVector:
    """Transformation d'une POSITION du repere local au repere monde.

    world = orientation @ local + translation. Resultat garanti dans Z^3.
    INTERDIT d'utiliser cette fonction pour une normale / direction :
    utiliser transform_local_direction_to_world().
    """
    if not isinstance(local, LDUVector):
        raise TypeError("transform_local_to_world attend un LDUVector")
    translation, orientation = _validate_pose(pose)
    return orientation.apply(local) + translation


def transform_world_to_local(world: LDUVector, pose: Pose) -> LDUVector:
    """Transformation inverse d'une POSITION : monde -> local.

    local = orientation^-1 @ (world - translation). Exacte dans Z^3.
    Ajout hors contrat : sans elle, un logiciel de CAO ne peut ni convertir un
    clic en coordonnee de piece, ni reposer une piece sur un nouvel ancrage.
    Propriete garantie et testee : transform_world_to_local(
    transform_local_to_world(v, pose), pose) == v pour toute pose.
    """
    if not isinstance(world, LDUVector):
        raise TypeError("transform_world_to_local attend un LDUVector")
    translation, orientation = _validate_pose(pose)
    return orientation.inverse().apply(world - translation)


def invert_pose(pose: Pose) -> Pose:
    """Pose inverse : (t, R)^-1 = (-R^-1 t, R^-1). Exacte dans Z^3."""
    translation, orientation = _validate_pose(pose)
    inverse_orientation = orientation.inverse()
    return (-inverse_orientation.apply(translation), inverse_orientation)


def compose_poses(outer: Pose, inner: Pose) -> Pose:
    """Composition de poses : appliquer inner puis outer.

    Necessaire des qu'un assemblage devient une sous-piece (groupes, modeles
    imbriques facon LDraw). Exacte dans Z^3.
    """
    outer_translation, outer_orientation = _validate_pose(outer)
    inner_translation, inner_orientation = _validate_pose(inner)
    return (
        outer_orientation.apply(inner_translation) + outer_translation,
        outer_orientation.compose(inner_orientation),
    )


# =============================================================================
# Section C.4 — Transformation d'une DIRECTION / NORMALE local -> monde
# =============================================================================


def transform_local_direction_to_world(
    local_direction: LDUVector,
    orientation: Orientation,
) -> LDUVector:
    """Transformation d'une DIRECTION / NORMALE du repere local au repere monde.

    world_direction = orientation @ local_direction. Aucune translation.
    OBLIGATOIRE pour les normales de connecteurs et les vecteurs directeurs.
    La signature n'accepte PAS de Pose : la translation est structurellement
    hors de portee de cette fonction.
    """
    if not isinstance(local_direction, LDUVector):
        raise TypeError("transform_local_direction_to_world attend un LDUVector")
    if not isinstance(orientation, Orientation):
        raise TypeError(
            "transform_local_direction_to_world attend une Orientation, pas une Pose"
        )
    return orientation.apply(local_direction)
