"""BFK-001 — BrickForge Kernel v3.3.2.

Package d'implementation du contrat BFK-001 v3.3.2.
Principe directeur : separation stricte des autorites — geometrie -> collision
-> mecanique.

Decoupage (Section O, DAG acyclique) :

    geometry      B, C   primitives exactes dans Z^3
    connectors    D      Connector, ConnectorTolerance, compatibilite ctype
    oracle        E      PhysicalBond opaque, evaluate_connector_pair
    collision     F      solid_overlap, collision_status, collide
    spatial       G      SpatialCandidateIndex, vue de lecture seule
    search        H      PlacedPart, SearchApproximation, reference O(n^2)
    graph         I      ConstructionGraph, InstructionGraph
    state         J      SpatialSnapshot, ConstructionState
    foundation    L      check_foundation
    validation    K      invariants H1 a H6
    orchestration --     composition d'etats (hors contrat)
    lego          --     metrologie du systeme LEGO et pieces (hors contrat)

`bfk001_kernel.py`, a la racine du depot, est la facade nommee par le brief :
elle reexporte l'integralite de cette API publique.
"""

from __future__ import annotations

from .collision import (
    CollisionGeometry,
    CollisionStatus,
    collide,
    collision_status,
    solid_overlap,
)
from .connectors import Connector, ConnectorTolerance
from .foundation import FoundationCheck, FoundationStatus, check_foundation
from .geometry import (
    AABB,
    GeometricRelation,
    LDUVector,
    Orientation,
    Pose,
    geometric_relation,
    intersection_aabb,
    transform_aabb,
    transform_local_direction_to_world,
    transform_local_to_world,
)
from .graph import BuildStep, ConstructionGraph, InstructionGraph
from .lego import (
    BRICK_HEIGHT_LDU,
    HALF_STUD_LDU,
    LDU_MM,
    LEGO_TOLERANCE,
    MIN_LATTICE_SEPARATION_LDU,
    PLATE_HEIGHT_LDU,
    STUD_DIAMETER_LDU,
    STUD_HEIGHT_LDU,
    STUD_PITCH_LDU,
    WALL_THICKNESS_LDU,
    brick_connectors,
    brick_geometry,
    ldu_to_mm,
    mm_to_ldu,
    place_brick,
)
from .oracle import PhysicalBond, evaluate_connector_pair, is_oracle_issued
from .orchestration import assemble, build_index, with_part, without_part
from .search import PlacedPart, ReferenceSearchApproximation, SearchApproximation
from .spatial import (
    FrozenSpatialSnapshot,
    ReferenceSpatialIndex,
    SpatialCandidateIndex,
)
from .state import ConstructionState, SpatialSnapshot
from .validation import (
    InvariantViolation,
    ValidationReport,
    check_h1_search_coverage,
    check_h2_collision,
    check_h3_authority_integrity,
    check_h4_floating,
    check_h5_disconnected,
    check_h6_foundation,
    founded_part_ids,
    physical_pairs,
    validate,
)

__version__ = "3.3.2"

__all__ = [
    # Section B / C
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
    # Section D
    "Connector",
    "ConnectorTolerance",
    # Section E
    "PhysicalBond",
    "evaluate_connector_pair",
    "is_oracle_issued",
    # Section F
    "CollisionStatus",
    "CollisionGeometry",
    "solid_overlap",
    "collision_status",
    "collide",
    # Section G
    "SpatialCandidateIndex",
    "ReferenceSpatialIndex",
    "FrozenSpatialSnapshot",
    # Section H
    "PlacedPart",
    "SearchApproximation",
    "ReferenceSearchApproximation",
    # Section I
    "ConstructionGraph",
    "BuildStep",
    "InstructionGraph",
    # Section J
    "SpatialSnapshot",
    "ConstructionState",
    # Section L
    "FoundationStatus",
    "FoundationCheck",
    "check_foundation",
    # Section K
    "InvariantViolation",
    "ValidationReport",
    "physical_pairs",
    "founded_part_ids",
    "check_h1_search_coverage",
    "check_h2_collision",
    "check_h3_authority_integrity",
    "check_h4_floating",
    "check_h5_disconnected",
    "check_h6_foundation",
    "validate",
    # Systeme LEGO (hors contrat)
    "LDU_MM",
    "STUD_PITCH_LDU",
    "HALF_STUD_LDU",
    "BRICK_HEIGHT_LDU",
    "PLATE_HEIGHT_LDU",
    "STUD_DIAMETER_LDU",
    "STUD_HEIGHT_LDU",
    "WALL_THICKNESS_LDU",
    "MIN_LATTICE_SEPARATION_LDU",
    "LEGO_TOLERANCE",
    "ldu_to_mm",
    "mm_to_ldu",
    "brick_geometry",
    "brick_connectors",
    "place_brick",
    # Orchestration (hors contrat)
    "with_part",
    "without_part",
    "build_index",
    "assemble",
    "__version__",
]
