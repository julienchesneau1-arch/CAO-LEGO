"""Recherche acceleree conforme H1 (HORS CONTRAT, Section H.4).

La recherche de reference est O(n^2) sur les paires de connecteurs : a l'echelle
d'un modele de CAO (des milliers de pieces, des dizaines de milliers de
connecteurs), elle est inutilisable. Le contrat anticipe explicitement un index
rapide et fixe sa regle de conformite : P inclus dans C_fast, et NON
C_ref inclus dans C_fast (Section H.4).

PREUVE DE COMPLETUDE, et non simple esperance :

  Soit une paire (a, b) pour laquelle l'oracle emet un PhysicalBond. Alors
  distance_euclidienne(pos_a, pos_b) <= tolerance.max_position_error_ldu = t.
  Or |pos_a.k - pos_b.k| <= distance pour chaque axe k, et ces ecarts sont
  ENTIERS (decision A.1). Donc |pos_a.k - pos_b.k| <= floor(t) = marge.
  En rangeant chaque connecteur dans la cellule de son unique position monde
  entiere, le partenaire d'un bond se trouve donc necessairement dans l'une des
  (2*marge + 1)^3 cellules voisines. Les balayer toutes est exhaustif.
  L'oracle exigeant par ailleurs la compatibilite des ctype, filtrer dessus ne
  peut retirer aucun bond.

Cas LEGO : la tolerance du systeme vaut 0,5 LDU, donc marge = 0. Le partenaire
est dans la MEME cellule : la recherche devient lineaire en nombre de
connecteurs. C'est la traduction algorithmique du fait que, dans un reseau
entier, se connecter veut dire coincider.

Repli : si (2*marge + 1)^3 depasse le nombre total de connecteurs, le balayage
de cellules coute plus cher que la reference — on rend la main a la reference,
qui est complete par construction. Aucune tolerance, si large soit-elle, ne
peut donc casser H1.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Mapping, Set, Tuple

from .connectors import Connector, ConnectorTolerance, _compatible
from .geometry import transform_local_to_world
from .search import PlacedPart, ReferenceSearchApproximation
from .spatial import SpatialCandidateIndex

__all__ = ["LatticeSearchApproximation"]

_Cell = Tuple[int, int, int]
_Entry = Tuple[str, Connector]


class LatticeSearchApproximation:
    """SearchApproximation en O(nombre de connecteurs) sur un reseau entier.

    L'index spatial recu est ignore : il indexe des pieces par AABB, ce qui est
    trop grossier ici. Le rangement par position exacte de connecteur est a la
    fois plus fin et demontrablement complet. La Section G autorise ce choix
    (l'index est un accelerateur, l'obligation H1 incombe a la recherche).
    """

    def find_candidate_pairs(
        self,
        index: SpatialCandidateIndex,
        placed_parts: Mapping[str, PlacedPart],
        tolerance: ConnectorTolerance,
    ) -> Iterable[Tuple[str, str, Connector, Connector]]:
        if not isinstance(tolerance, ConnectorTolerance):
            raise TypeError("find_candidate_pairs attend une ConnectorTolerance")

        margin = int(math.floor(tolerance.max_position_error_ldu))

        buckets: Dict[_Cell, List[_Entry]] = {}
        connector_count = 0
        for part_id, part in placed_parts.items():
            for connector in part.connectors:
                position = transform_local_to_world(connector.local_pos, part.pose)
                buckets.setdefault(position.as_tuple(), []).append((part_id, connector))
                connector_count += 1

        scanned_cells = (2 * margin + 1) ** 3
        if connector_count == 0:
            return
        if scanned_cells >= connector_count:
            # Repli documente : la reference n'est pas plus couteuse ici, et
            # elle est complete par construction.
            yield from ReferenceSearchApproximation().find_candidate_pairs(
                index, placed_parts, tolerance
            )
            return

        offsets = tuple(
            (dx, dy, dz)
            for dx in range(-margin, margin + 1)
            for dy in range(-margin, margin + 1)
            for dz in range(-margin, margin + 1)
        )

        emitted: Set[Tuple[str, str, Connector, Connector]] = set()
        for (x, y, z), entries in buckets.items():
            for dx, dy, dz in offsets:
                neighbours = buckets.get((x + dx, y + dy, z + dz))
                if not neighbours:
                    continue
                for id_a, conn_a in entries:
                    for id_b, conn_b in neighbours:
                        if id_a == id_b:
                            continue
                        if not _compatible(conn_a.ctype, conn_b.ctype):
                            continue
                        pair = (
                            (id_a, id_b, conn_a, conn_b)
                            if id_a < id_b
                            else (id_b, id_a, conn_b, conn_a)
                        )
                        if pair in emitted:
                            continue
                        emitted.add(pair)
                        yield pair
