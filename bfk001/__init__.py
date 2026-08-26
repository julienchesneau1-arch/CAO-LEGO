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
    catalog       --     references, couleurs, nomenclature (hors contrat)
    imaging       --     lecture et reechantillonnage d'images (hors contrat)
    jpeg          --     decodeur JPEG baseline au huitieme (hors contrat)
    palette       --     palette LEGO et quantification perceptuelle (hors contrat)
    mosaic        --     solveur LEGO Art : image -> modele (hors contrat)
    instructions  --     plan de montage acyclique (hors contrat)
    rotations     --     les 24 rotations discretes, nommees (hors contrat)
    fast_search   --     recherche O(n) conforme H1 (hors contrat, H.4)
    serialization --     persistance sans bond (hors contrat)

`bfk001_kernel.py`, a la racine du depot, est la facade nommee par le brief :
elle reexporte l'integralite de cette API publique.
"""

from __future__ import annotations

from . import booklet, imaging, instructions, jpeg, mosaic, palette
from .catalog import (
    CATALOG,
    LDRAW_COLORS,
    BomLine,
    PartDefinition,
    PartInstance,
    bill_of_materials,
    definition,
    place,
)
from .collision import (
    CollisionGeometry,
    CollisionStatus,
    collide,
    collide_world,
    collision_status,
    solid_overlap,
    world_geometry,
)
from .connectors import Connector, ConnectorTolerance
from .foundation import FoundationCheck, FoundationStatus, check_foundation
from .fast_search import LatticeSearchApproximation
from .geometry import (
    AABB,
    GeometricRelation,
    LDUVector,
    Orientation,
    Pose,
    geometric_relation,
    intersection_aabb,
    transform_aabb,
    compose_poses,
    invert_pose,
    transform_local_direction_to_world,
    transform_local_to_world,
    transform_world_to_local,
)
from .graph import ConstructionGraph, InstructionGraph
from .imaging import crop, crop_to_ratio, Image, read_png, read_ppm, resample_box, write_png
from .jpeg import apply_orientation, exif_orientation, read_jpeg_eighth
from .instructions import BuildStep, plan_build, render_text
from .booklet import build_booklet, render_progress, render_layer, row_runs, write_pdf
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
from .mosaic import Mosaic
from .oracle import PhysicalBond, evaluate_connector_pair, is_oracle_issued
from .palette import (
    PROVISIONAL_PALETTE,
    LegoColor,
    Palette,
    PaletteGap,
    delta_e,
    delta_e76,
    delta_e2000,
    find_ldconfig,
    load_best_palette,
    dominant_colors,
    gap_report,
    load_ldconfig,
    srgb_to_lab,
)
from .orchestration import (
    PlacementVerdict,
    add_part,
    assemble,
    build_index,
    evaluate_placement,
    remove_part,
    with_part,
    without_part,
)
from .rotations import (
    ROT_X_90,
    ROT_X_180,
    ROT_X_270,
    ROT_Y_90,
    ROT_Y_180,
    ROT_Y_270,
    ROT_Z_90,
    ROT_Z_180,
    ROT_Z_270,
    all_rotations,
    rotation_x,
    rotation_y,
    rotation_z,
)
from .serialization import (
    DOCUMENT_VERSION,
    dumps_model,
    from_document,
    loads_model,
    to_document,
)
from .search import PlacedPart, ReferenceSearchApproximation, SearchApproximation
from .spatial import (
    DEFAULT_CELL_SIZE_LDU,
    FrozenSpatialSnapshot,
    GridSpatialIndex,
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
    "transform_world_to_local",
    "invert_pose",
    "compose_poses",
    "all_rotations",
    "rotation_x",
    "rotation_y",
    "rotation_z",
    "ROT_X_90",
    "ROT_X_180",
    "ROT_X_270",
    "ROT_Y_90",
    "ROT_Y_180",
    "ROT_Y_270",
    "ROT_Z_90",
    "ROT_Z_180",
    "ROT_Z_270",
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
    "world_geometry",
    "collide_world",
    # Section G
    "SpatialCandidateIndex",
    "ReferenceSpatialIndex",
    "GridSpatialIndex",
    "DEFAULT_CELL_SIZE_LDU",
    "FrozenSpatialSnapshot",
    # Section H
    "PlacedPart",
    "SearchApproximation",
    "ReferenceSearchApproximation",
    "LatticeSearchApproximation",
    # Section I
    "ConstructionGraph",
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
    # Catalogue et nomenclature (hors contrat)
    "PartDefinition",
    "PartInstance",
    "BomLine",
    "CATALOG",
    "LDRAW_COLORS",
    "definition",
    "place",
    "bill_of_materials",
    # Perception, solveur mosaique et notice (hors contrat)
    "imaging",
    "jpeg",
    "palette",
    "mosaic",
    "booklet",
    "instructions",
    "Image",
    "read_png",
    "read_ppm",
    "read_jpeg_eighth",
    "exif_orientation",
    "apply_orientation",
    "write_png",
    "resample_box",
    "crop",
    "crop_to_ratio",
    "LegoColor",
    "Palette",
    "PROVISIONAL_PALETTE",
    "load_ldconfig",
    "srgb_to_lab",
    "delta_e",
    "delta_e76",
    "delta_e2000",
    "find_ldconfig",
    "load_best_palette",
    "dominant_colors",
    "PaletteGap",
    "gap_report",
    "Mosaic",
    "BuildStep",
    "plan_build",
    "render_text",
    "build_booklet",
    "render_progress",
    "render_layer",
    "row_runs",
    "write_pdf",
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
    "add_part",
    "remove_part",
    "PlacementVerdict",
    "evaluate_placement",
    # Persistance (hors contrat)
    "DOCUMENT_VERSION",
    "to_document",
    "from_document",
    "dumps_model",
    "loads_model",
    "__version__",
]
