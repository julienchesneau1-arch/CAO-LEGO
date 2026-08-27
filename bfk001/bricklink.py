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

from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from .catalog import BomLine

__all__ = ["load_color_map", "color_map_from_catalog",
           "color_map_template", "read_color_map", "dumps_wanted_list",
           "UnmappedColors"]


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

    Une ligne dont la deuxieme colonne est VIDE est ignoree : c'est une ligne
    de gabarit qu'on n'a pas encore remplie, et la couleur ressortira comme non
    appariee — ce qui est exactement ce qu'il faut dire.

    Un commentaire EN FIN DE LIGNE est ignore aussi. Ce n'est pas de la
    complaisance : c'est exactement ce que produit `color_map_template`, qui
    rappelle en marge le nom et la valeur de chaque couleur pour qu'on sache
    laquelle on renseigne. Une table qu'on remplit a la main s'annote.
    """
    table: Dict[int, int] = {}
    for numero, ligne in enumerate(text.splitlines(), start=1):
        nue = ligne.split("#", 1)[0].strip() if not ligne.lstrip().startswith("#") \
            else ""
        if not nue:
            continue
        morceaux = [m.strip() for m in nue.replace(";", ",").split(",")[:2]]
        if len(morceaux) < 2:
            raise ValueError(f"ligne {numero} : deux colonnes attendues, « {nue} »")
        if not morceaux[1]:
            # Ligne de gabarit pas encore remplie. Ce n'est pas une erreur,
            # c'est une absence : la couleur ressortira comme non appariee, ce
            # qui est exactement ce qu'il faut dire.
            continue
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


# --------------------------------------------------------------------------
# Importer la table plutot que la recopier
# --------------------------------------------------------------------------

_ENTETES_ID = ("color id", "colorid", "id", "bricklink color id", "bl id")
_ENTETES_NOM = ("color name", "colorname", "name", "color")
_ENTETES_LEGO = ("lego color id", "lego id", "legoid", "lego color",
                 "lego element color")


def _normaliser(nom: str) -> str:
    """Nom de couleur reduit a ce qui se compare.

    LDraw ecrit « Dark_Bluish_Grey », BrickLink « Dark Bluish Gray ». La
    difference tient a un tiret bas et a une orthographe ; ce n'est pas une
    difference de couleur.
    """
    plat = nom.lower().replace("_", " ").replace("-", " ")
    plat = plat.replace("grey", "gray")
    return " ".join(plat.split())


def _decouper(ligne: str) -> List[str]:
    for separateur in ("\t", ";", ","):
        if separateur in ligne:
            return [champ.strip().strip('"') for champ in ligne.split(separateur)]
    return [ligne.strip()]


def color_map_from_catalog(text: str, palette) -> Tuple[Dict[int, int],
                                                        Tuple[str, ...]]:
    """Table LDraw -> BrickLink, IMPORTEE d'un export de couleurs BrickLink.

    Rend (table, couleurs non appariees).

    Le principe est celui de tout ce depot : on importe, on ne recopie pas. La
    table de correspondance etait la derniere donnee que je ne pouvais pas
    fournir sans l'inventer — jusqu'a ce que je regarde ce que LDConfig
    contient vraiment. Il porte le LEGOID, l'identifiant de couleur du systeme
    LEGO, pour 131 de ses 162 couleurs. BrickLink publie le meme identifiant
    dans son export. La correspondance se DEDUIT, elle ne se devine pas.

    Deux appariements, dans cet ordre, et l'ordre est celui de la confiance :

    1. par LEGOID. Exact : c'est le meme numero des deux cotes.
    2. par NOM normalise. « Dark_Bluish_Grey » et « Dark Bluish Gray »
       designent la meme couleur ; le tiret bas et l'orthographe ne sont pas
       des differences de couleur. Employe seulement quand le LEGOID manque.

    Ce qui ne s'apparie ni par l'un ni par l'autre est RENDU, pas devine. Une
    liste de course avec une couleur inventee est pire qu'une liste incomplete.

    L'export attendu est celui que BrickLink laisse telecharger depuis son
    catalogue de couleurs : une ligne d'en-tetes, puis une ligne par couleur,
    separees par des tabulations, des points-virgules ou des virgules. Les
    colonnes sont reconnues a leur en-tete et non a leur position, parce que
    l'ordre des colonnes n'est promis nulle part.
    """
    lignes = [l for l in text.splitlines() if l.strip()]
    if not lignes:
        raise ValueError("export de couleurs vide")
    entetes = [_normaliser(champ) for champ in _decouper(lignes[0])]

    def colonne(candidats, obligatoire=True):
        for rang, entete in enumerate(entetes):
            if entete in candidats:
                return rang
        for rang, entete in enumerate(entetes):
            if any(entete.startswith(c) for c in candidats):
                return rang
        if obligatoire:
            raise ValueError(
                f"colonne introuvable parmi {entetes} : il faut au moins un "
                f"identifiant ({' ou '.join(candidats[:3])}) et un nom"
            )
        return None

    col_id = colonne(_ENTETES_ID)
    col_nom = colonne(_ENTETES_NOM)
    col_lego = colonne(_ENTETES_LEGO, obligatoire=False)

    par_lego: Dict[int, int] = {}
    par_nom: Dict[str, int] = {}
    for ligne in lignes[1:]:
        champs = _decouper(ligne)
        if len(champs) <= max(col_id, col_nom):
            continue
        try:
            identifiant = int(champs[col_id])
        except ValueError:
            continue
        par_nom.setdefault(_normaliser(champs[col_nom]), identifiant)
        if col_lego is not None and len(champs) > col_lego:
            try:
                par_lego.setdefault(int(champs[col_lego]), identifiant)
            except ValueError:
                pass

    table: Dict[int, int] = {}
    orphelines: List[str] = []
    for couleur in palette:
        trouve = None
        if couleur.lego_id is not None:
            trouve = par_lego.get(couleur.lego_id)
        if trouve is None:
            trouve = par_nom.get(_normaliser(couleur.name))
        if trouve is None:
            orphelines.append(f"{couleur.code} {couleur.name}")
        else:
            table[couleur.code] = trouve
    return table, tuple(orphelines)


def color_map_template(palette, table: Mapping[int, int] = {}) -> str:
    """Un gabarit a completer, pour les couleurs qu'aucun import n'apparie.

    Rendre une erreur et s'arreter la n'aide personne : le gabarit liste
    exactement ce qui manque, avec de quoi le retrouver — le nom, la valeur
    RVB et le LEGOID quand il existe. Une ligne remplie, et `load_color_map`
    la relit.
    """
    lignes = ["# code LDraw, code BrickLink   (nom, RVB, LEGOID en commentaire)"]
    for couleur in palette:
        connu = table.get(couleur.code)
        commentaire = (f"  # {couleur.name} #%02X%02X%02X" % couleur.rgb)
        if couleur.lego_id is not None:
            commentaire += f" LEGOID {couleur.lego_id}"
        lignes.append(
            f"{couleur.code},{connu if connu is not None else ''}{commentaire}"
        )
    return "\n".join(lignes) + "\n"


def read_color_map(text: str, palette=None) -> Tuple[Dict[int, int],
                                                     Tuple[str, ...]]:
    """Lit une table de couleurs, quel que soit ce qu'on lui donne.

    Deux formats circulent et l'utilisateur n'a aucune raison de savoir lequel
    il tient : la table a deux colonnes qu'il a peut-etre remplie a la main, et
    l'export de couleurs que BrickLink laisse telecharger. On reconnait le
    second a sa ligne d'en-tetes, et on retombe sur le premier sinon.

    Rend (table, orphelines). Sans palette, l'export ne peut pas etre apparie
    et seule la table a deux colonnes est acceptee.
    """
    lignes = [l for l in text.splitlines() if l.strip()]
    premiere = _normaliser(_decouper(lignes[0])[0]) if lignes else ""
    ressemble_a_un_export = any(
        premiere.startswith(candidat) for candidat in _ENTETES_ID + _ENTETES_NOM
    )
    if ressemble_a_un_export:
        if palette is None:
            raise ValueError(
                "cet export BrickLink demande une palette pour s'apparier : "
                "c'est le LEGOID de LDConfig qui fait le lien"
            )
        return color_map_from_catalog(text, palette)
    return load_color_map(text), ()
