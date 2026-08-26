"""Plan de montage (HORS CONTRAT, couche 3).

Produit un InstructionGraph a partir d'un assemblage valide : quelles pieces
poser, dans quel ordre, et de quoi chaque etape depend.

La regle physique est la seule contrainte dure : une piece ne peut etre posee
que si ce qui la porte est deja en place. Elle se lit directement dans le
graphe de construction — une liaison entre deux pieces de hauteurs differentes
est une relation de portance — et elle garantit a elle seule l'acyclicite du
plan (une piece ne peut pas porter ce qui la porte).

Le reste releve du confort de montage, pas de la physique : regrouper par
couleur evite de fouiller le sachet vingt fois, decouper en etapes courtes evite
de perdre le fil. Ces choix sont parametres, pas graves.

Ce module produit la STRUCTURE de la notice. Son rendu — vues isometriques,
fleches, callouts, PDF — est un travail de rendu 3D qui n'a pas sa place ici.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

from .catalog import CATALOG, PartInstance
from .graph import ConstructionGraph, InstructionGraph
from .search import PlacedPart

__all__ = ["BuildStep", "plan_build", "render_text"]


@dataclass(frozen=True)
class BuildStep:
    """Une etape de montage. Conforme au protocole BuildStep (Section I.2)."""

    step_id: str
    part_ids: Tuple[str, ...]
    depends_on: Tuple[str, ...]
    description: str

    def __post_init__(self) -> None:
        if not self.part_ids:
            raise ValueError("une etape sans piece n'est pas une etape")


def _support_levels(
    placed_parts: Mapping[str, PlacedPart],
    graph: ConstructionGraph,
) -> Tuple[Dict[str, int], Dict[str, Tuple[str, ...]]]:
    """Niveau de chaque piece et liste de ce qui la porte.

    Porte = liee a une piece dont la base est strictement plus basse. Une
    liaison entre deux pieces de meme hauteur (assemblage lateral) ne cree
    aucune dependance : elle ne pourrait qu'introduire un cycle.
    """
    supports: Dict[str, List[str]] = {part_id: [] for part_id in placed_parts}
    for id_a, id_b, bonds in graph.edges:
        if not bonds:
            continue
        z_a = placed_parts[id_a].aabb.min.z
        z_b = placed_parts[id_b].aabb.min.z
        if z_a < z_b:
            supports[id_b].append(id_a)
        elif z_b < z_a:
            supports[id_a].append(id_b)

    levels: Dict[str, int] = {}
    remaining = set(placed_parts)
    while remaining:
        progressed = False
        for part_id in sorted(remaining):
            below = supports[part_id]
            if all(other in levels for other in below):
                levels[part_id] = 1 + max((levels[o] for o in below), default=-1)
                remaining.discard(part_id)
                progressed = True
        if not progressed:  # pragma: no cover - impossible : la portance est stricte
            raise AssertionError("cycle de portance detecte")

    return levels, {k: tuple(sorted(v)) for k, v in supports.items()}


def plan_build(
    placed_parts: Mapping[str, PlacedPart],
    graph: ConstructionGraph,
    instances: Optional[Mapping[str, PartInstance]] = None,
    max_parts_per_step: int = 4,
) -> InstructionGraph:
    """Assemblage valide -> plan de montage acyclique.

    `instances` permet de regrouper par reference et couleur : c'est la
    difference entre une notice qui fait poser vingt pieces identiques d'un
    coup et une notice qui fait changer de sachet a chaque piece.
    """
    if max_parts_per_step < 1:
        raise ValueError("une etape contient au moins une piece")

    levels, supports = _support_levels(placed_parts, graph)

    groups: Dict[Tuple[int, str, int], List[str]] = {}
    for part_id in sorted(placed_parts):
        instance = None if instances is None else instances.get(part_id)
        key = (
            levels[part_id],
            "" if instance is None else instance.design_id,
            -1 if instance is None else instance.color_id,
        )
        groups.setdefault(key, []).append(part_id)

    steps: List[BuildStep] = []
    step_of_part: Dict[str, str] = {}
    for key in sorted(groups):
        level, design_id, color_id = key
        batch = groups[key]
        for start in range(0, len(batch), max_parts_per_step):
            part_ids = tuple(batch[start : start + max_parts_per_step])
            step_id = f"E{len(steps) + 1:04d}"
            for part_id in part_ids:
                step_of_part[part_id] = step_id
            label = CATALOG[design_id].name if design_id in CATALOG else design_id
            steps.append(
                BuildStep(
                    step_id=step_id,
                    part_ids=part_ids,
                    depends_on=(),  # complete ci-dessous, une fois tout affecte
                    description=(
                        f"Niveau {level} : poser {len(part_ids)} x {label}"
                        + ("" if color_id < 0 else f" (couleur {color_id})")
                    ),
                )
            )

    resolved: List[BuildStep] = []
    for step in steps:
        needed = {
            step_of_part[support]
            for part_id in step.part_ids
            for support in supports[part_id]
            if step_of_part[support] != step.step_id
        }
        resolved.append(
            BuildStep(
                step_id=step.step_id,
                part_ids=step.part_ids,
                depends_on=tuple(sorted(needed)),
                description=step.description,
            )
        )

    return InstructionGraph(steps=tuple(resolved))


def render_text(plan: InstructionGraph, width: int = 78) -> str:
    """Notice lisible en texte. Le rendu graphique est un autre metier."""
    lines = [
        "NOTICE DE MONTAGE".center(width),
        "=" * width,
        f"{len(plan.steps)} etapes, "
        f"{sum(len(step.part_ids) for step in plan.steps)} pieces",
        "",
    ]
    for index, step in enumerate(plan.steps, start=1):
        prerequisites = (
            "" if not step.depends_on else f"  [apres {', '.join(step.depends_on)}]"
        )
        lines.append(f"{index:4d}. {step.description}{prerequisites}")
    return "\n".join(lines)
