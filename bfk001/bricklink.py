"""Export de liste de course BrickLink — HORS CONTRAT, couche 3.

Le registre notait « on ne peut pas commander » comme le dernier ecart entre
« j'ai un modele » et « j'ai les briques ». Il tenait a UNE donnee : les codes
couleur. Les references de PIECES sont communes aux deux systemes — celles
employees ici (3070b, 2431, 3020, 41539...) sont verifiees identiques dans
`parts.lst` de LDraw et dans le catalogue BrickLink. Les codes COULEUR, eux,
sont propres a chaque systeme et la correspondance n'est derivable de rien :
ni la valeur RVB ni le nom ne l'etablissent de facon fiable.

Cette correspondance n'a pas ete inventee ici. Elle est FOURNIE par l'appelant,
sous la forme la plus simple possible — deux colonnes, code LDraw et code
BrickLink — pour qu'elle puisse venir de n'importe quelle source que
l'utilisateur juge fiable.

Et ce qui n'est pas dans la table n'est pas devine : `dumps_wanted_list` refuse
plutot que de livrer une commande dont certaines lignes seraient fausses. Une
liste de course incomplete se paie en pieces manquantes le jour du montage ;
une liste de course FAUSSE se paie en pieces inutilisables.
"""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Sequence, Tuple

from .catalog import BomLine

__all__ = ["load_color_map", "dumps_wanted_list", "UnmappedColors"]


class UnmappedColors(KeyError):
    """Des couleurs du modele n'ont pas de code BrickLink connu."""

    def __init__(self, codes: Sequence[int]) -> None:
        self.codes = tuple(sorted(codes))
        super().__init__(
            f"{len(self.codes)} couleurs sans correspondance BrickLink : "
            + ", ".join(str(code) for code in self.codes[:10])
            + ("..." if len(self.codes) > 10 else "")
            + ". Completez la table, ou restreignez la palette a ce qu'elle "
            "couvre — ces couleurs ne seront pas devinees."
        )


def load_color_map(text: str) -> Dict[int, int]:
    """Lit une table « code LDraw, code BrickLink ».

    Deux colonnes separees par une virgule ou un point-virgule, une par ligne.
    Les lignes vides, les commentaires (`#`) et un eventuel en-tete sont
    ignores. Format volontairement pauvre : la table doit pouvoir venir de
    n'importe quelle source, y compris d'un tableur rempli a la main.
    """
    table: Dict[int, int] = {}
    for numero, ligne in enumerate(text.splitlines(), start=1):
        nue = ligne.strip()
        if not nue or nue.startswith("#"):
            continue
        morceaux = [m.strip() for m in nue.replace(";", ",").split(",")[:2]]
        if len(morceaux) < 2:
            raise ValueError(f"ligne {numero} : deux colonnes attendues, « {nue} »")
        try:
            ldraw, bricklink = int(morceaux[0]), int(morceaux[1])
        except ValueError:
            if not table:      # tres probablement l'en-tete
                continue
            raise ValueError(
                f"ligne {numero} : deux entiers attendus, « {nue} »"
            ) from None
        if ldraw in table and table[ldraw] != bricklink:
            raise ValueError(
                f"ligne {numero} : le code LDraw {ldraw} est deja associe a "
                f"{table[ldraw]}, on ne peut pas aussi l'associer a {bricklink}"
            )
        table[ldraw] = bricklink
    if not table:
        raise ValueError("aucune correspondance exploitable dans cette table")
    return table


def dumps_wanted_list(
    bom: Iterable[BomLine],
    color_map: Mapping[int, int],
    part_map: Mapping[str, str] = {},
    name: str = "Mosaique",
) -> str:
    """Nomenclature -> liste de souhaits BrickLink, au format XML documente.

    `part_map` permet de corriger une reference au cas par cas ; par defaut la
    reference LDraw est employee telle quelle, ce qui est exact pour toutes
    celles de ce depot.

    Leve `UnmappedColors` si une couleur manque a la table. C'est voulu : une
    liste partiellement fausse est pire qu'une absence de liste, parce qu'on ne
    s'en apercoit qu'a la livraison.
    """
    lignes = list(bom)
    manquantes = {l.color_id for l in lignes if l.color_id not in color_map}
    if manquantes:
        raise UnmappedColors(manquantes)

    sortie = [
        "<!-- Liste de souhaits BrickLink produite par BFK-001 -->",
        f"<!-- {name} : {len(lignes)} lots, "
        f"{sum(l.quantity for l in lignes)} pieces -->",
        "<INVENTORY>",
    ]
    for ligne in sorted(lignes, key=lambda l: (l.design_id, -l.quantity)):
        sortie.extend([
            " <ITEM>",
            "  <ITEMTYPE>P</ITEMTYPE>",
            f"  <ITEMID>{_echapper(part_map.get(ligne.design_id, ligne.design_id))}</ITEMID>",
            f"  <COLOR>{color_map[ligne.color_id]}</COLOR>",
            f"  <MINQTY>{ligne.quantity}</MINQTY>",
            " </ITEM>",
        ])
    sortie.append("</INVENTORY>")
    return "\n".join(sortie) + "\n"


def _echapper(texte: str) -> str:
    """Une reference n'a rien d'exotique, mais un XML casse ne se voit pas."""
    return (
        texte.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
