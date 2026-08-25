"""
BFK-001 KERNEL v3.3.2
BrickForge Kernel — Implémentation Python
Statut : ZERO logique comportementale initiale. Remplacer les '...' par l'implémentation.
Version : 3.3.2
Date : 2026-08-25
Principe directeur : séparation stricte des autorités — géométrie → collision → mécanique
Consigne CLAUDE CODE :
  1. Implémenter les tests adversariaux T1a–T14 D'ABORD.
  2. Remplacer chaque '...' par la logique conforme au contrat v3.3.2.
  3. NE JAMAIS utiliser transform_local_to_world() pour une normale.
  4. NE JAMAIS introduire de List dans ConstructionGraph ou ConstructionState.
  5. PhysicalBond reste opaque : seul evaluate_connector_pair() le construit.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterable, Mapping, Optional, Protocol, Tuple, TypeAlias

# =============================================================================
# Section B — Primitives géométriques et arithmétique exacte
# =============================================================================

@dataclass(frozen=True)
class LDUVector:
    """Élément de ℤ³. Aucune opération ne produit de coordonnée non entière."""
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class AABB:
    """Axis-Aligned Bounding Box.
    Précondition : min.x <= max.x, min.y <= max.y, min.z <= max.z."""
    min: LDUVector
    max: LDUVector


class GeometricRelation(Enum):
    """Relation topologique entre deux AABB. Arithmétique exacte sur les entiers."""
    DISJOINT = auto()
    TOUCHING = auto()
    OVERLAPPING = auto()


def geometric_relation(a: AABB, b: AABB) -> GeometricRelation:
    """Détermine la relation topologique entre deux AABB. Arithmétique exacte."""
    ...


def intersection_aabb(a: AABB, b: AABB) -> Optional[AABB]:
    """Retourne l'AABB de l'intersection si OVERLAPPING, sinon None.
    Un contact de face nul ne produit pas d'AABB."""
    ...


def transform_aabb(aabb: AABB, pose: Pose) -> AABB:
    """Transforme les 8 coins de l'AABB par la pose.
    Retourne l'AABB englobant exact (min/max composante par composante).
    Toutes les opérations sont exactes dans ℤ³."""
    ...


# =============================================================================
# Section C — Orientation
# =============================================================================

@dataclass(frozen=True)
class Orientation:
    """Matrice de rotation 3×3 entière.
    Coefficients ∈ {−1,0,1}, orthogonalité, déterminant +1."""
    m00: int; m01: int; m02: int
    m10: int; m11: int; m12: int
    m20: int; m21: int; m22: int


Pose: TypeAlias = Tuple[LDUVector, Orientation]
"""Donnée d'une translation entière et d'une rotation discrète."""


def transform_local_to_world(local: LDUVector, pose: Pose) -> LDUVector:
    """Transformation d'une POSITION du repère local au repère monde.
    world = orientation @ local + translation
    Résultat garanti dans ℤ³.
    INTERDIT d'utiliser cette fonction pour une normale / direction.
    """
    ...


def transform_local_direction_to_world(
    local_direction: LDUVector,
    orientation: Orientation,
) -> LDUVector:
    """Transformation d'une DIRECTION / NORMALE du repère local au repère monde.
    Seule la rotation est appliquée ; aucune translation n'est ajoutée.
    world_direction = orientation @ local_direction
    Résultat garanti dans ℤ³.
    OBLIGATOIRE pour les normales de connecteurs et les vecteurs directeurs.
    """
    ...


# =============================================================================
# Section D — Connecteurs et tolérance
# =============================================================================

@dataclass(frozen=True)
class Connector:
    """Connecteur mécanique dans le repère local de la pièce.
    local_normal : exactement une composante non-nulle parmi les 6 directions axiales."""
    ctype: str
    local_pos: LDUVector
    local_normal: LDUVector


@dataclass(frozen=True)
class ConnectorTolerance:
    """Paramètre d'entrée de l'oracle mécanique.
    max_angular_error_deg est contractuellement présent mais explicitement
    NON utilisé par l'oracle en BFK-001 (réservé à BFK-002)."""
    max_position_error_ldu: float
    max_angular_error_deg: float


# =============================================================================
# Section E — Oracle mécanique indépendant
# =============================================================================

@dataclass(frozen=True)
class PhysicalBond:
    """Type opaque. Autorité de création EXCLUSIVE de evaluate_connector_pair.
    Aucune API publique de BFK-001 ne permet sa construction directe.
    L'implémentation DOIT utiliser un mécanisme privé de construction
    (factory interne, constructeur privé conventionnel, ou équivalent).
    """
    pass


def evaluate_connector_pair(
    connector_a: Connector,
    pose_a: Pose,
    connector_b: Connector,
    pose_b: Pose,
    tolerance: ConnectorTolerance,
) -> Optional[PhysicalBond]:
    """Évalue si deux connecteurs forment un bond mécanique valide.

    Critères BFK-001 (non exhaustif, l'oracle conserve l'autorité ultime) :
    • Compatibilité ctype : _compatible(ctype_a, ctype_b) doit être vrai.
      BFK-001 définit : 'stud_male' ↔ 'stud_female' uniquement.
    • Normales opposées EXACTES :
      transform_local_direction_to_world(connector_a.local_normal, pose_a[1])
      ==
      -transform_local_direction_to_world(connector_b.local_normal, pose_b[1])
    • max_angular_error_deg est IGNORE en BFK-001.
    • Distance euclidienne entre positions monde :
      pos_a = transform_local_to_world(connector_a.local_pos, pose_a)
      pos_b = transform_local_to_world(connector_b.local_pos, pose_b)
      dx, dy, dz = pos_a.x - pos_b.x, pos_a.y - pos_b.y, pos_a.z - pos_b.z
      distance = sqrt(dx² + dy² + dz²)
      Bond valide ssi distance <= tolerance.max_position_error_ldu

    Contraintes contractuelles :
    • Ne connaît PAS SearchApproximation, SpatialCandidateIndex,
      connector_registry, voxel, solver, ConstructionState, graphe.
    • Fonction pure.
    """
    ...


# =============================================================================
# Section F — Collision et géométrie solide
# =============================================================================

class CollisionStatus(Enum):
    """Autorité de classification collisionnelle."""
    CLEAR = auto()
    CONTACT = auto()
    PENETRATION = auto()


@dataclass(frozen=True)
class CollisionGeometry:
    """Géométrie solide d'une pièce dans son repère LOCAL.
    exterior et voids sont exprimés dans le repère local de la pièce.
    collide() transforme l'exterior et tous les voids en coordonnées monde
    avant toute comparaison ou soustraction géométrique."""
    exterior: AABB
    voids: Tuple[AABB, ...]


def solid_overlap(
    intersection: AABB,
    solid_a: AABB,
    voids_a: Tuple[AABB, ...],
    solid_b: AABB,
    voids_b: Tuple[AABB, ...],
) -> Optional[Tuple[AABB, ...]]:
    """Autorité géométrique exacte.
    Calcule la région de matière solide effectivement pénétrée après
    soustraction des voids.

    Retourne None si la région est vide.
    Retourne Tuple[AABB, ...] représentant une partition exacte sinon.
    Union exacte = R, intérieurs deux à deux disjoints.
    Aucune sur-approximation n'est autorisée.
    """
    ...


def collision_status(
    relation: GeometricRelation,
    overlap: Optional[Tuple[AABB, ...]],
) -> CollisionStatus:
    """Traduit la relation géométrique et le résultat de solid_overlap en statut.

    Règles :
    • DISJOINT → CLEAR
    • TOUCHING → CONTACT
    • OVERLAPPING + overlap is None → CONTACT (engagement dans voids)
    • OVERLAPPING + overlap is not None → PENETRATION
    """
    ...


def collide(
    geometry_a: CollisionGeometry,
    pose_a: Pose,
    geometry_b: CollisionGeometry,
    pose_b: Pose,
) -> CollisionStatus:
    """Autorité collisionnelle complète.
    Évalue le statut collisionnel entre deux pièces placées dans l'espace.

    Algorithme contractuel :
    1. Transforme exterior et tous les voids en coordonnées monde :
       aabb_a = transform_aabb(geometry_a.exterior, pose_a)
       voids_a_m = tuple(transform_aabb(v, pose_a) for v in geometry_a.voids)
       aabb_b = transform_aabb(geometry_b.exterior, pose_b)
       voids_b_m = tuple(transform_aabb(v, pose_b) for v in geometry_b.voids)
    2. relation = geometric_relation(aabb_a, aabb_b)
    3. DISJOINT → CLEAR ; TOUCHING → CONTACT
    4. OVERLAPPING → intersection_aabb() → solid_overlap() → collision_status()

    Contraintes :
    • Ne connaît PAS Connector, PhysicalBond, SearchApproximation,
      SpatialCandidateIndex, ConstructionState, evaluate_connector_pair.
    """
    ...


# =============================================================================
# Section G — SpatialCandidateIndex (Protocol)
# =============================================================================

class SpatialCandidateIndex(Protocol):
    """Accélérateur spatial. Peut dire 'regarde ici'.
    Ne peut JAMAIS dire 'connectés' ou 'pas connectés'."""
    def query(self, region: AABB) -> Iterable[str]:
        """Retourne les identifiants candidats. AUCUNE garantie d'exhaustivité."""
        ...

    def insert(self, part_id: str, aabb: AABB) -> None:
        """Indexe une nouvelle pièce."""
        ...

    def remove(self, part_id: str) -> None:
        """Désindexe une pièce."""
        ...


# =============================================================================
# Section H — SearchApproximation (Protocol)
# =============================================================================

@dataclass(frozen=True)
class PlacedPart:
    """Value object de référence spatiale. Aucune autorité mécanique."""
    part_id: str
    pose: Pose
    aabb: AABB
    connectors: Tuple[Connector, ...]


class SearchApproximation(Protocol):
    """Responsabilité : générer l'ensemble des paires à soumettre à l'oracle.
    AUCUNE garantie mécanique sur les paires retournées.
    Porte l'obligation H1 (P ⊆ C)."""
    def find_candidate_pairs(
        self,
        index: SpatialCandidateIndex,
        placed_parts: Mapping[str, PlacedPart],
        tolerance: ConnectorTolerance,
    ) -> Iterable[Tuple[str, str, Connector, Connector]]:
        """Retourne des tuples (part_id_a, part_id_b, connector_a, connector_b).
        Les Connector sont en coordonnées LOCALES."""
        ...


class ReferenceSearchApproximation:
    """Implémentation de référence O(n²).
    Triviale, exhaustive, lente, démontrable."""
    def find_candidate_pairs(
        self,
        index: SpatialCandidateIndex,
        placed_parts: Mapping[str, PlacedPart],
        tolerance: ConnectorTolerance,
    ) -> Iterable[Tuple[str, str, Connector, Connector]]:
        """Ignore l'index (inutile en O(n²) exhaustive)."""
        ...


def _compatible(ctype_a: str, ctype_b: str) -> bool:
    """BFK-001 définit exactement :
    'stud_male' est compatible avec 'stud_female' et réciproquement.
    Tout autre couple est non compatible (rejeté ou réservé)."""
    ...


# =============================================================================
# Section I — Graphes
# =============================================================================

@dataclass(frozen=True)
class ConstructionGraph:
    """Graphe de construction. Utilise Tuple pour l'immutabilité profonde.
    edges = tous les bonds, pas un arbre couvrant."""
    parts: Tuple[Tuple[str, AABB, Tuple[Connector, ...]], ...]
    edges: Tuple[Tuple[str, str, Tuple[PhysicalBond, ...]], ...]


# BuildStep sera défini dans BFK-001.1
BuildStep = object


@dataclass(frozen=True)
class InstructionGraph:
    """Graphe d'instructions."""
    steps: Tuple[BuildStep, ...]

    def validate_dag(self) -> bool:
        """Vérifie que le graphe d'instructions est un DAG."""
        ...


# =============================================================================
# Section J — ConstructionState
# =============================================================================

class SpatialSnapshot(Protocol):
    """Vue de lecture seule d'un index spatial.
    Protocole query uniquement, sans insert/remove."""
    def query(self, region: AABB) -> Iterable[str]:
        """Même sémantique que SpatialCandidateIndex.query."""
        ...


@dataclass(frozen=True)
class ConstructionState:
    """Pur conteneur immuable. Ne calcule pas, ne stocke que.
    Aucune méthode de mutation. Aucune référence vers un objet mutable."""
    graph: ConstructionGraph
    spatial_snapshot: SpatialSnapshot


# =============================================================================
# Section L — Support et fondation
# =============================================================================

# FoundationCheck sera défini lors de l'implémentation
FoundationCheck = object


def check_foundation(
    part_exterior: AABB,
    part_connectors: Tuple[Connector, ...],
    part_pose: Pose,
    foundation_plane_z: int = 0,
) -> FoundationCheck:
    """Règles (arithmétique exacte, entiers) :
    • min.z < foundation_plane_z → INVALIDE (pénètre le sol)
    • min.z > foundation_plane_z → NON fondée (doit avoir un bond)
    • min.z == foundation_plane_z → Fondée ssi la pièce possède au moins un
      Connector de ctype 'stud_female' dont la normale transformée est (0,0,-1) :
      transform_local_direction_to_world(connector.local_normal, part_pose[1]) == (0,0,-1)
      Sinon → NON fondée.
    Aucun epsilon. min.z est contractuellement un entier.
    """
    ...
