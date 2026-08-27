"""Export de commande LEGO Pick a Brick — HORS CONTRAT, couche 3.

BrickLink accepte notre liste de course depuis longtemps. LEGO aussi, depuis
que Pick a Brick a gagne un bouton « Upload list » : un CSV a deux colonnes,
`elementId,quantity`, jusqu'a 400 references differentes par envoi.

Une seule chose separe notre nomenclature de ce fichier, et elle est de taille :
Pick a Brick ne veut PAS le numero de moule (3024, 3020, 2431...) mais
l'ELEMENT ID, le numero qui designe un moule DANS UNE COULEUR. 6141... c'est
« Plate 1x1 en rouge », pas « Plate 1x1 ». Ce numero est ATTRIBUE, pas calcule :
il n'existe aucune fonction de (moule, couleur) vers element, et deux couleurs
voisines d'un meme moule ont des numeros sans rapport.

Donc la meme regle que pour BrickLink, pour la meme raison : cette table n'est
pas inventee ici, elle est IMPORTEE. L'utilisateur telecharge un catalogue
d'elements — Rebrickable en publie un librement, BrickLink en publie un autre —
et on le lit.

Ce que ce module refuse
-----------------------
Une colonne « color id » NUE est refusee. Le numero 71 vaut « Light Bluish
Gray » chez LDraw, « 86 » chez BrickLink, autre chose ailleurs : un identifiant
de couleur ne veut rien dire tant qu'on ne sait pas de quel systeme il vient.
L'interpreter au hasard, ce n'est pas une liste incomplete, c'est une liste
FAUSSE — des pieces de la mauvaise couleur, livrees, payees, inutilisables. Il
faut donc soit une colonne d'identifiants LEGO (que LDConfig nous donne aussi,
via son LEGOID), soit des NOMS de couleur, soit un second fichier qui dise a
quoi les numeros correspondent.

Ce que ce module tolere, et ou il differe de `bricklink`
-------------------------------------------------------
`dumps_wanted_list` REFUSE d'ecrire une commande BrickLink incomplete. Ici on
ecrit quand meme, et on livre a cote la liste de ce qui manque. Ce n'est pas
une inconsequence, c'est une difference de mode de panne : chez BrickLink, une
couleur non appariee obligerait a DEVINER un code, et l'erreur ne se voit qu'a
la livraison ; ici, un lot introuvable est un lot ABSENT du fichier, qu'on
constate a l'upload, la liste des manquants a la main. Rien de faux n'est
commande. Refuser tout un envoi pour un lot exotique ferait perdre les 45
autres sans rien proteger.

Et ce que ce module ne saura jamais
-----------------------------------
Qu'un element existe au catalogue ne dit RIEN de sa disponibilite a la vente.
Pick a Brick a son propre stock, variable selon le pays et le jour. Aucune
donnee de disponibilite ni de prix n'est inventee ici ; c'est l'upload lui-meme
qui dira ce qui est vendable aujourd'hui.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

# Ces deux-la viennent de `bricklink` a dessein, plutot que d'etre recopies.
# Un nom de couleur doit se normaliser EXACTEMENT pareil des deux cotes : si
# les deux normalisations divergeaient un jour, la meme couleur s'apparierait
# ici et pas la, sans qu'aucun test de l'un ou l'autre module ne le voie.
from .bricklink import _decouper, _normaliser
from .catalog import BomLine

__all__ = ["TableElements", "ELEMENTS_PAR_ENVOI", "read_elements",
           "read_color_names", "elements_for_bom", "dumps_upload",
           "missing_report", "ElementsIllisibles"]


ELEMENTS_PAR_ENVOI = 400
"""Nombre de references differentes qu'un envoi Pick a Brick accepte.

Ce n'est pas un nombre de pieces : c'est un nombre de LOTS. Une mosaique de
mille pieces en quarante couleurs tient largement ; c'est en multipliant les
couleurs qu'on s'en approche. Au-dela, on decoupe en plusieurs fichiers plutot
que de laisser l'upload echouer sans expliquer pourquoi.
"""


class ElementsIllisibles(ValueError):
    """Le catalogue d'elements ne se laisse pas lire, et on dit pourquoi."""


# --------------------------------------------------------------------------
# Lecture du catalogue
# --------------------------------------------------------------------------

_ENTETES_ELEMENT = ("element id", "elementid", "element", "lego element id",
                    "part color code", "pcc", "code")
_ENTETES_PIECE = ("design id", "designid", "part num", "partnum",
                  "part number", "item no", "itemno", "item number",
                  "part", "piece")
# Volontairement PAS « no » ni « number » tout seuls : cherches par prefixe, ils
# attraperaient « notes » ou « number of sets ». Un en-tete de deux lettres ne
# designe rien de facon fiable.
_ENTETES_LEGO = ("lego color id", "legoid", "lego id", "lego color")
_ENTETES_NOM = ("color name", "colorname", "colour name", "color", "colour",
                "name")
_ENTETES_COULEUR_NUE = ("color id", "colorid", "colour id", "colourid", "id")


def _entete(champ: str) -> str:
    """En-tete reduit a ce qui se compare : casse, tirets, orthographes."""
    return _normaliser(champ).replace("colour", "color").replace("#", "").strip()


def _colonne(entetes: Sequence[str], candidats: Sequence[str],
             exclure: Sequence[str] = ()) -> Optional[int]:
    """Colonne reconnue a son en-tete, jamais a sa position.

    L'ordre des colonnes n'est promis par aucun de ces catalogues. On cherche
    l'egalite d'abord, le prefixe ensuite, et les candidats sont essayes du plus
    specifique au moins specifique.

    `exclure` liste les en-tetes qu'une autre colonne revendique EXACTEMENT.
    Sans lui, chercher un nom de couleur par le prefixe « color » attraperait
    « color id » : on lirait un numero la ou on veut un nom, et toutes les
    correspondances tomberaient a cote sans qu'aucune erreur ne se leve. C'est
    le genre de defaut qui ne se voit qu'a la livraison.
    """
    interdits = set(exclure)
    for candidat in candidats:
        for rang, entete in enumerate(entetes):
            if entete == candidat:
                return rang
    for candidat in candidats:
        for rang, entete in enumerate(entetes):
            if entete not in interdits and entete.startswith(candidat):
                return rang
    return None


@dataclass(frozen=True)
class TableElements:
    """Catalogue (piece, couleur) -> element id, tel qu'il a ete importe.

    `cle` dit COMMENT la couleur est designee dans ce catalogue — « lego » pour
    un identifiant de couleur LEGO, « nom » pour un nom. C'est ce qui decide de
    la facon dont on interrogera la table, et c'est enregistre plutot que
    redevine a chaque appel.
    """

    entrees: Mapping[Tuple[str, str], str]
    cle: str
    lignes_lues: int = 0
    lignes_ignorees: int = 0

    def __len__(self) -> int:
        return len(self.entrees)

    def __bool__(self) -> bool:
        return bool(self.entrees)


def read_color_names(text: str) -> Dict[str, str]:
    """Lit un « id, nom » de couleurs — le second fichier qui debloque le reste.

    Rebrickable publie `elements.csv` (element, piece, id de couleur) et
    `colors.csv` (id, nom, RVB) sur la meme page. Le premier seul est
    inexploitable : ses numeros de couleur sont les SIENS. Les deux ensemble
    suffisent, et personne n'a rien recopie a la main.
    """
    lignes = [l for l in text.splitlines() if l.strip()]
    if not lignes:
        raise ElementsIllisibles("table de couleurs vide")
    entetes = [_entete(c) for c in _decouper(lignes[0])]
    col_id = _colonne(entetes, _ENTETES_COULEUR_NUE)
    col_nom = _colonne(entetes, _ENTETES_NOM,
                       exclure=_ENTETES_COULEUR_NUE + _ENTETES_LEGO)
    if col_id is None or col_nom is None:
        raise ElementsIllisibles(
            f"table de couleurs : il faut une colonne d'identifiant et une "
            f"colonne de nom ; en-tetes lus : {entetes}"
        )
    noms: Dict[str, str] = {}
    for ligne in lignes[1:]:
        champs = _decouper(ligne)
        if len(champs) <= max(col_id, col_nom):
            continue
        identifiant, nom = champs[col_id].strip(), champs[col_nom].strip()
        if identifiant and nom:
            noms.setdefault(identifiant, _normaliser(nom))
    if not noms:
        raise ElementsIllisibles("aucune couleur exploitable dans cette table")
    return noms


def read_elements(text: str,
                  color_names: Optional[Mapping[str, str]] = None
                  ) -> TableElements:
    """Lit un catalogue d'elements, quelle qu'en soit la provenance.

    Trois colonnes sont necessaires : l'element, la piece, la couleur. Elles
    sont reconnues a leur en-tete. La colonne couleur decide du reste :

    * un identifiant LEGO (`lego color id`) : exact, et LDConfig porte le meme
      numero — rien d'autre a fournir ;
    * un nom (`color name`) : apparie par nom normalise, comme la table
      BrickLink ;
    * un identifiant nu (`color id`) : REFUSE seul, accepte avec `color_names`,
      qui dit de quel systeme viennent ces numeros.

    Les lignes qu'on ne sait pas lire sont comptees, pas ignorees en silence :
    un catalogue a moitie lu doit se voir.
    """
    lignes = [l for l in text.splitlines() if l.strip()]
    if not lignes:
        raise ElementsIllisibles("catalogue d'elements vide")
    entetes = [_entete(c) for c in _decouper(lignes[0])]

    col_element = _colonne(entetes, _ENTETES_ELEMENT)
    col_piece = _colonne(entetes, _ENTETES_PIECE,
                         exclure=_ENTETES_ELEMENT + _ENTETES_NOM)
    if col_element is None or col_piece is None:
        raise ElementsIllisibles(
            "catalogue d'elements : il faut une colonne d'element id et une "
            f"colonne de piece ; en-tetes lus : {entetes}"
        )

    # Trois facons de designer une couleur, par ordre de confiance. Un
    # identifiant LEGO est exact et LDConfig porte le meme ; un nom se compare ;
    # un identifiant nu ne veut rien dire tout seul.
    col_couleur = _colonne(entetes, _ENTETES_LEGO)
    cle, via_noms = "lego", False
    if col_couleur is None:
        col_couleur = _colonne(entetes, _ENTETES_NOM,
                               exclure=_ENTETES_COULEUR_NUE + _ENTETES_LEGO)
        cle = "nom"
    if col_couleur is None:
        col_couleur = _colonne(entetes, _ENTETES_COULEUR_NUE)
        cle, via_noms = "nom", True
        if col_couleur is None:
            raise ElementsIllisibles(
                "catalogue d'elements : aucune colonne de couleur ; en-tetes "
                f"lus : {entetes}"
            )
        if color_names is None:
            raise ElementsIllisibles(
                "ce catalogue designe les couleurs par un identifiant nu "
                f"({entetes[col_couleur]}), sans dire de quel systeme il vient. "
                "Le numero 71 n'est pas la meme couleur chez LDraw, chez "
                "BrickLink et chez Rebrickable ; l'interpreter au hasard ferait "
                "commander de la mauvaise couleur. Fournissez la table de "
                "couleurs qui accompagne ce catalogue (chez Rebrickable, "
                "colors.csv a cote de elements.csv)."
            )

    entrees: Dict[Tuple[str, str], str] = {}
    lues = ignorees = 0
    dernier = max(col_element, col_piece, col_couleur)
    for ligne in lignes[1:]:
        champs = _decouper(ligne)
        if len(champs) <= dernier:
            ignorees += 1
            continue
        element = champs[col_element].strip()
        piece = champs[col_piece].strip()
        couleur = champs[col_couleur].strip()
        if not element or not piece or not couleur:
            ignorees += 1
            continue
        if not _element_ecrivable(element):
            # Un element id est un jeton simple. S'il contient une virgule, une
            # guillemet ou un espace, ce n'est pas un element id : c'est une
            # colonne mal decoupee. L'ecrire produirait un CSV casse que Pick a
            # Brick refuserait sans dire ou.
            ignorees += 1
            continue
        if via_noms:
            # La colonne ne porte qu'un numero : c'est le second fichier qui
            # dit de quelle couleur il s'agit. Un numero qu'il ne connait pas
            # est compte comme illisible, jamais devine.
            resolu = color_names.get(couleur) if color_names else None
            if resolu is None:
                ignorees += 1
                continue
            couleur = resolu
        elif cle == "nom":
            couleur = _normaliser(couleur)
        lues += 1
        entrees.setdefault((_piece_normalisee(piece), couleur), element)
    if not entrees:
        raise ElementsIllisibles(
            "aucun element exploitable dans ce catalogue "
            f"({ignorees} ligne(s) illisible(s))"
        )
    return TableElements(entrees, cle, lues, ignorees)


def _piece_normalisee(reference: str) -> str:
    return reference.strip().lower()


def _element_ecrivable(element: str) -> bool:
    """Un element id s'ecrit tel quel dans un CSV, ou n'en est pas un."""
    return all(c.isalnum() or c == "-" for c in element)


def _variantes(design_id: str) -> Tuple[str, ...]:
    """Les ecritures sous lesquelles un meme moule peut figurer.

    LDraw ecrit `3070b` la tuile 1x1 a rainure, pour la distinguer de `3070a`
    qui n'en avait pas. LEGO ne fabrique plus que la rainuree et lui donne le
    numero de moule `3070` tout court. Les deux ecritures designent aujourd'hui
    la meme piece, et un catalogue emploie l'une OU l'autre selon la colonne
    qu'on lit.

    L'ecriture exacte est essayee EN PREMIER ; la troncature n'est qu'un
    recours, et `elements_for_bom` compte combien de lots en ont eu besoin pour
    qu'on puisse le verifier plutot que le supposer.
    """
    exact = _piece_normalisee(design_id)
    if len(exact) > 1 and exact[-1].isalpha() and exact[:-1].isdigit():
        return (exact, exact[:-1])
    return (exact,)


# --------------------------------------------------------------------------
# De la nomenclature au fichier
# --------------------------------------------------------------------------

def elements_for_bom(bom: Iterable[BomLine], table: TableElements, palette
                     ) -> Tuple[List[Tuple[str, int]], List[BomLine], int]:
    """Nomenclature -> [(element, quantite)], lots introuvables, replis.

    Le troisieme renvoi est le nombre de lots resolus par troncature de la
    reference (voir `_variantes`) : une information a surveiller, pas un detail.
    """
    par_code = {couleur.code: couleur for couleur in palette}
    trouves: List[Tuple[str, int]] = []
    manquants: List[BomLine] = []
    replis = 0
    for ligne in sorted(bom, key=lambda l: (-l.quantity, l.design_id,
                                            l.color_id)):
        couleur = par_code.get(ligne.color_id)
        cles: Tuple[str, ...] = ()
        if couleur is not None:
            if table.cle == "lego":
                if couleur.lego_id is not None:
                    cles = (str(couleur.lego_id),)
            else:
                cles = (_normaliser(couleur.name),)
        element = None
        replie = False
        for rang, reference in enumerate(_variantes(ligne.design_id)):
            for cle in cles:
                element = table.entrees.get((reference, cle))
                if element is not None:
                    replie = rang > 0
                    break
            if element is not None:
                break
        if element is None:
            manquants.append(ligne)
        else:
            trouves.append((element, ligne.quantity))
            replis += 1 if replie else 0
    return trouves, manquants, replis


def dumps_upload(lots: Sequence[Tuple[str, int]],
                 par_envoi: int = ELEMENTS_PAR_ENVOI) -> List[str]:
    """[(element, quantite)] -> un ou plusieurs CSV `elementId,quantity`.

    Un fichier tant que l'envoi tient dans la limite, plusieurs sinon. Decouper
    n'est pas une elegance : au-dela de la limite l'upload echoue en bloc, et
    l'utilisateur n'a aucun moyen de savoir que c'est le NOMBRE DE LOTS, et non
    son fichier, qui pose probleme.
    """
    if par_envoi < 1:
        raise ValueError("un envoi contient au moins une reference")
    fusionnes: Dict[str, int] = {}
    for element, quantite in lots:
        if quantite > 0:
            fusionnes[element] = fusionnes.get(element, 0) + quantite
    ordonnes = sorted(fusionnes.items(), key=lambda p: (-p[1], p[0]))
    if not ordonnes:
        return ["elementId,quantity\n"]
    envois: List[str] = []
    for debut in range(0, len(ordonnes), par_envoi):
        tranche = ordonnes[debut:debut + par_envoi]
        lignes = ["elementId,quantity"]
        lignes.extend(f"{element},{quantite}" for element, quantite in tranche)
        envois.append("\n".join(lignes) + "\n")
    return envois


def missing_report(manquants: Sequence[BomLine], palette) -> str:
    """Ce que le fichier ne contient pas, avec de quoi le retrouver a la main.

    Une ligne absente n'est pas une erreur silencieuse tant qu'on sait laquelle.
    Le nom de couleur et le LEGOID suffisent a chercher l'element sur n'importe
    quel catalogue.
    """
    par_code = {couleur.code: couleur for couleur in palette}
    lignes = ["design_id,nom,code_couleur,couleur,lego_color_id,quantite"]
    for ligne in sorted(manquants, key=lambda l: (-l.quantity, l.design_id)):
        couleur = par_code.get(ligne.color_id)
        nom = couleur.name if couleur is not None else f"code {ligne.color_id}"
        lego = "" if couleur is None or couleur.lego_id is None \
            else str(couleur.lego_id)
        lignes.append(
            f'{ligne.design_id},"{ligne.name}",{ligne.color_id},"{nom}",'
            f'{lego},{ligne.quantity}'
        )
    return "\n".join(lignes) + "\n"
