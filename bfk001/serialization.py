"""Persistance d'un modele (HORS CONTRAT).

Regle d'or, qui decoule directement de la decision A.8 : **un PhysicalBond ne
se serialise jamais**. Un document ne contient que des pieces — identifiant,
pose, geometrie, connecteurs. Les liaisons sont RE-EMISES par l'oracle au
chargement, a partir de la geometrie relue.

C'est la seule facon de garder H3 vrai apres un aller-retour disque : si les
bonds etaient relus depuis un fichier, ils proviendraient d'une source externe a
l'oracle et le graphe serait, litteralement, fabrique. Un fichier de sauvegarde
n'a aucune autorite mecanique — pas plus qu'un index spatial.

Corollaire pratique : rouvrir un modele ne peut pas ressusciter une liaison
devenue invalide entre-temps (tolerance modifiee, piece deplacee a la main dans
le fichier). Le document porte les faits geometriques, l'oracle porte le
jugement.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional, Tuple

from .catalog import PartInstance
from .collision import CollisionGeometry
from .connectors import Connector
from .geometry import AABB, LDUVector, Orientation, Pose
from .search import PlacedPart

__all__ = [
    "DOCUMENT_VERSION",
    "to_document",
    "from_document",
    "dumps_model",
    "loads_model",
]

DOCUMENT_VERSION = "BFK-001/3.3.2"


def _vector_to_json(vector: LDUVector) -> list:
    return [vector.x, vector.y, vector.z]


def _vector_from_json(data: Any) -> LDUVector:
    if not isinstance(data, (list, tuple)) or len(data) != 3:
        raise ValueError(f"vecteur invalide : {data!r}")
    return LDUVector(*(int(value) for value in data))


def _aabb_to_json(aabb: AABB) -> dict:
    return {"min": _vector_to_json(aabb.min), "max": _vector_to_json(aabb.max)}


def _aabb_from_json(data: Any) -> AABB:
    if not isinstance(data, dict):
        raise ValueError(f"AABB invalide : {data!r}")
    return AABB(_vector_from_json(data["min"]), _vector_from_json(data["max"]))


def _pose_to_json(pose: Pose) -> dict:
    translation, orientation = pose
    return {
        "translation": _vector_to_json(translation),
        "orientation": list(
            value for row in orientation.rows() for value in row
        ),
    }


def _pose_from_json(data: Any) -> Pose:
    if not isinstance(data, dict):
        raise ValueError(f"pose invalide : {data!r}")
    coefficients = data["orientation"]
    if not isinstance(coefficients, (list, tuple)) or len(coefficients) != 9:
        raise ValueError("une orientation compte exactement 9 coefficients")
    return (
        _vector_from_json(data["translation"]),
        Orientation(*(int(value) for value in coefficients)),
    )


def to_document(
    placed_parts: Mapping[str, PlacedPart],
    geometries: Mapping[str, CollisionGeometry],
    instances: Optional[Mapping[str, PartInstance]] = None,
) -> Dict[str, Any]:
    """Document JSON-able. Ne contient AUCUN bond, par construction.

    `instances` porte l'identite commerciale (reference catalogue, couleur) :
    sans elle un document est constructible mais pas achetable.
    """
    instances = {} if instances is None else instances
    parts = []
    for part_id, part in sorted(placed_parts.items()):
        geometry = geometries.get(part_id)
        instance = instances.get(part_id)
        parts.append(
            {
                "part_id": part_id,
                "design_id": None if instance is None else instance.design_id,
                "color_id": None if instance is None else instance.color_id,
                "pose": _pose_to_json(part.pose),
                "connectors": [
                    {
                        "ctype": connector.ctype,
                        "local_pos": _vector_to_json(connector.local_pos),
                        "local_normal": _vector_to_json(connector.local_normal),
                    }
                    for connector in part.connectors
                ],
                "geometry": None
                if geometry is None
                else {
                    "exterior": _aabb_to_json(geometry.exterior),
                    "voids": [_aabb_to_json(void) for void in geometry.voids],
                },
            }
        )
    return {"version": DOCUMENT_VERSION, "parts": parts}


def from_document(
    document: Mapping[str, Any],
) -> Tuple[Dict[str, PlacedPart], Dict[str, CollisionGeometry], Dict[str, PartInstance]]:
    """Relit un document. Les bonds sont absents : l'oracle les re-emettra.

    Toute donnee relue repasse par les constructeurs du noyau, donc par leurs
    validations : une orientation de determinant -1 ou une normale non axiale
    presente dans le fichier est refusee ici, pas plus loin.
    """
    if document.get("version") != DOCUMENT_VERSION:
        raise ValueError(
            f"version de document non supportee : {document.get('version')!r}"
        )

    placed_parts: Dict[str, PlacedPart] = {}
    geometries: Dict[str, CollisionGeometry] = {}
    instances: Dict[str, PartInstance] = {}
    for entry in document["parts"]:
        part_id = entry["part_id"]
        if not isinstance(part_id, str) or not part_id:
            raise ValueError("part_id invalide")
        if part_id in placed_parts:
            raise ValueError(f"identifiant duplique dans le document : {part_id}")

        pose = _pose_from_json(entry["pose"])
        connectors = tuple(
            Connector(
                connector["ctype"],
                _vector_from_json(connector["local_pos"]),
                _vector_from_json(connector["local_normal"]),
            )
            for connector in entry["connectors"]
        )

        geometry_data = entry.get("geometry")
        if geometry_data is None:
            raise ValueError(
                f"{part_id} : geometrie absente, l'AABB monde ne peut etre recalcule"
            )
        geometry = CollisionGeometry(
            exterior=_aabb_from_json(geometry_data["exterior"]),
            voids=tuple(_aabb_from_json(void) for void in geometry_data["voids"]),
        )

        from .geometry import transform_aabb

        design_id = entry.get("design_id")
        if design_id is not None:
            color_id = entry.get("color_id")
            if not isinstance(color_id, int) or isinstance(color_id, bool):
                raise ValueError(f"{part_id} : couleur invalide pour {design_id!r}")
            instances[part_id] = PartInstance(part_id, str(design_id), color_id)

        geometries[part_id] = geometry
        placed_parts[part_id] = PlacedPart(
            part_id=part_id,
            pose=pose,
            aabb=transform_aabb(geometry.exterior, pose),
            connectors=connectors,
        )
    return placed_parts, geometries, instances


def dumps_model(
    placed_parts: Mapping[str, PlacedPart],
    geometries: Mapping[str, CollisionGeometry],
    instances: Optional[Mapping[str, PartInstance]] = None,
    indent: int = 2,
) -> str:
    """Serialise le modele en JSON. Aucun bond n'y figure."""
    return json.dumps(
        to_document(placed_parts, geometries, instances), indent=indent, sort_keys=True
    )


def loads_model(
    payload: str,
) -> Tuple[Dict[str, PlacedPart], Dict[str, CollisionGeometry], Dict[str, PartInstance]]:
    """Relit un modele JSON. Les liaisons seront re-emises par l'oracle."""
    return from_document(json.loads(payload))
