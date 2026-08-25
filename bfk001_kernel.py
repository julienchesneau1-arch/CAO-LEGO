"""BFK-001 KERNEL v3.3.2 — facade publique du BrickForge Kernel.

Ce fichier est le point d'entree nomme par le brief d'implementation
(Partie 2). Il ne contient AUCUNE logique : l'implementation vit dans le
package `bfk001/`, decoupe module par module selon les sections du contrat.

Pourquoi un package et non un fichier unique (ecart signale, regle 1) :
le test adversarial T1b audite le module dans lequel vit reellement l'oracle
(`inspect.getmodule(evaluate_connector_pair)`). Dans un fichier unique, ce
module expose SearchApproximation, SpatialCandidateIndex, ConstructionState et
les symboles de collision : l'isolation d'autorite exigee par la Section E
n'est alors ni reelle ni verifiable. Le decoupage rend T1b mecaniquement vrai
plutot que declaratif. Voir README.md, section "Ecarts signales".

Rappels non negociables :
  1. transform_local_to_world()           -> POSITION uniquement.
     transform_local_direction_to_world() -> DIRECTION / NORMALE uniquement.
  2. Arithmetique exacte dans Z^3. Seule operation flottante autorisee :
     la comparaison distance euclidienne <= max_position_error_ldu, dans l'oracle.
  3. Tuple partout, jamais List, dans ConstructionGraph et ConstructionState.
  4. PhysicalBond est opaque : seul evaluate_connector_pair() peut en creer un.
"""

from __future__ import annotations

from bfk001 import *  # noqa: F401,F403
from bfk001 import __all__ as _KERNEL_ALL
from bfk001 import __version__

__all__ = list(_KERNEL_ALL)
