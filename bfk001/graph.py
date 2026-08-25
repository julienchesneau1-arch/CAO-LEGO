"""BFK-001 v3.3.2 — Section I : graphes.

Immutabilite profonde : Tuple uniquement, jamais List (regle 4 du brief).
`edges` porte TOUS les bonds, pas un arbre couvrant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Tuple

from .connectors import Connector
from .geometry import AABB
from .oracle import PhysicalBond

__all__ = ["ConstructionGraph", "BuildStep", "InstructionGraph"]


@dataclass(frozen=True)
class ConstructionGraph:
    """Graphe de construction, entierement en Tuple."""

    parts: Tuple[Tuple[str, AABB, Tuple[Connector, ...]], ...]
    edges: Tuple[Tuple[str, str, Tuple[PhysicalBond, ...]], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.parts, tuple):
            raise TypeError("ConstructionGraph.parts doit etre un Tuple, jamais une List")
        if not isinstance(self.edges, tuple):
            raise TypeError("ConstructionGraph.edges doit etre un Tuple, jamais une List")

        for part in self.parts:
            if not isinstance(part, tuple) or len(part) != 3:
                raise TypeError("chaque part est un Tuple[str, AABB, Tuple[Connector, ...]]")
            part_id, aabb, connectors = part
            if not isinstance(part_id, str) or not isinstance(aabb, AABB):
                raise TypeError("chaque part est un Tuple[str, AABB, Tuple[Connector, ...]]")
            if not isinstance(connectors, tuple):
                raise TypeError("les connecteurs d'une part sont un Tuple, jamais une List")
            for connector in connectors:
                if not isinstance(connector, Connector):
                    raise TypeError("les connecteurs d'une part sont des Connector")

        declared = tuple(part[0] for part in self.parts)
        if len(set(declared)) != len(declared):
            raise ValueError("identifiant de piece duplique dans ConstructionGraph.parts")

        known = set(declared)
        seen_edges = set()
        for edge in self.edges:
            if not isinstance(edge, tuple) or len(edge) != 3:
                raise TypeError("chaque edge est un Tuple[str, str, Tuple[PhysicalBond, ...]]")
            id_a, id_b, bonds = edge
            if not isinstance(id_a, str) or not isinstance(id_b, str):
                raise TypeError("les extremites d'une edge sont des identifiants str")
            if not isinstance(bonds, tuple):
                raise TypeError("les bonds d'une edge sont un Tuple, jamais une List")
            for bond in bonds:
                if not isinstance(bond, PhysicalBond):
                    raise TypeError("les bonds d'une edge sont des PhysicalBond")

            # Integrite structurelle : une arete relie deux pieces DECLAREES,
            # distinctes, une seule fois, et porte au moins une liaison. Sans
            # ces controles, un graphe peut affirmer une connexite qui repose
            # sur une piece inexistante ou sur une arete vide — et H4/H5
            # passeraient sur une fiction.
            if id_a not in known or id_b not in known:
                raise ValueError(
                    f"arete vers une piece non declaree : {id_a} <-> {id_b}"
                )
            if id_a == id_b:
                raise ValueError(f"arete d'une piece vers elle-meme : {id_a}")
            if not bonds:
                raise ValueError(
                    f"arete sans liaison : {id_a} <-> {id_b}. Une arete sans bond "
                    "ne connecte rien ; elle ne doit pas exister."
                )
            key = (id_a, id_b) if id_a <= id_b else (id_b, id_a)
            if key in seen_edges:
                raise ValueError(f"arete dupliquee : {key[0]} <-> {key[1]}")
            seen_edges.add(key)


class BuildStep(Protocol):
    """Forme minimale d'une etape d'instruction.

    Le BuildStep exact releve de BFK-001.1 (Section Q). BFK-001 ne suppose que
    ce qui est necessaire a validate_dag : une identite et des dependances.
    """

    step_id: str
    depends_on: Tuple[str, ...]


@dataclass(frozen=True)
class InstructionGraph:
    """Graphe d'instructions."""

    steps: Tuple[BuildStep, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.steps, tuple):
            raise TypeError("InstructionGraph.steps doit etre un Tuple, jamais une List")

    def validate_dag(self) -> bool:
        """True si les etapes forment un DAG : identites uniques, references
        connues, aucun cycle (tri topologique de Kahn).
        """
        steps = {}
        for step in self.steps:
            step_id = getattr(step, "step_id", None)
            depends_on = getattr(step, "depends_on", None)
            if not isinstance(step_id, str) or not isinstance(depends_on, tuple):
                raise TypeError(
                    "validate_dag exige des etapes exposant step_id: str et "
                    "depends_on: Tuple[str, ...] (BuildStep, BFK-001.1)"
                )
            if step_id in steps:
                return False
            steps[step_id] = depends_on

        for depends_on in steps.values():
            for dependency in depends_on:
                if dependency not in steps:
                    return False

        pending = dict(steps)
        resolved: set = set()
        while pending:
            ready = [
                step_id
                for step_id, depends_on in pending.items()
                if all(dependency in resolved for dependency in depends_on)
            ]
            if not ready:
                return False
            for step_id in ready:
                resolved.add(step_id)
                del pending[step_id]
        return True
