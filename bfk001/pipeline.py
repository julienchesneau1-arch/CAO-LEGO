"""La chaine complete, en memoire : photo -> fichiers livrables.

Ce module existe pour une raison precise. La commande `demo_lego_art.py`
portait toute l'orchestration dans son `main()`, melangee a l'analyse des
arguments et aux impressions. Ajouter une deuxieme facade — une interface web —
aurait demande soit de la reecrire, soit de l'appeler comme un sous-processus.
Reecrire, c'est se donner deux chaines qui divergeront ; appeler un
sous-processus, c'est renoncer a tester.

Or les deux derniers defauts trouves dans ce depot (§ 5.48 du registre) etaient
tous deux des defauts de TRAJET : des parametres mal passes d'un composant
correct a un autre composant correct. Une chaine unique, appelable sans fichier
ni terminal, est exactement ce qui les rend testables.

Rien n'est imprime ici, et rien n'est ecrit sur le disque. Le journal est rendu
comme une suite de lignes etiquetees, a charge de l'appelant de les afficher.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from . import (bricklink, imaging, instructions, jpeg, ldraw, mosaic,
               pickabrick, palette as palette_module)
from .booklet import build_booklet
from .catalog import bill_of_materials
from .depth import NoEmbeddedDepth, embedded_depth, heights_from_depth, read_depth_map
from .panels import build_assembly
from .imaging import Image, crop_to_ratio, read_png, read_ppm, resample_box, write_png
from .lego import LEGO_TOLERANCE, ldu_to_mm
from .mosaic import FRAME_COLOR
from .palette import Palette, gap_report, load_best_palette
from .serialization import dumps_model
from .validation import (check_h2_collision, check_h3_authority_integrity,
                         check_h4_floating, check_h5_disconnected,
                         check_h6_foundation, founded_part_ids)
from .fast_search import LatticeSearchApproximation
from .orchestration import assemble

__all__ = [
    "Reglages",
    "Resultat",
    "ModeleRefuse",
    "JEUX_DE_TUILES",
    "lire_image",
    "palette_utilisable",
    "carte_de_relief",
    "RELIEF_PAR_CONVENTION",
    "PENTE_SUSPECTE",
    "run",
]

JEUX_DE_TUILES = {
    "minimal": mosaic.TILE_SET_MINIMAL,
    "standard": mosaic.TILE_SET_STANDARD,
    "large": mosaic.TILE_SET_LARGE,
    "art": mosaic.TILE_SET_ART,
}

TRAMAGES = {"auto": "auto", "adaptatif": "adaptive", "aucun": False, "complet": True}


class ModeleRefuse(Exception):
    """Le noyau a refuse le modele. Les violations sont dans `violations`."""

    def __init__(self, message: str, violations=()):
        super().__init__(message)
        self.violations = tuple(violations)


TENONS_MAXIMUM = 250_000
"""Surface au-dela de laquelle la chaine refuse plutot que de manquer de memoire.

500 x 500 tenons, soit quatre metres de cote : personne ne construit cela d'une
piece, et au-dela le calcul se termine par un MemoryError apres plusieurs
minutes. Mesure : 128 x 128 tenons donnent 5 657 pieces en 17 s ; le cout suit
le nombre de pieces, donc la surface.

Ce n'est pas une limite de qualite mais une limite de machine, et elle est dite
comme telle : une oeuvre plus grande se fait en plusieurs, cote a cote.
"""

TENONS_LENTS = 40_000
"""Surface au-dela de laquelle on previent que ce sera long.

200 x 200 tenons. En dessous, la fabrication tient dans le temps d'attente
normal d'une page web ; au-dessus, il faut le dire avant, pas apres.
"""

CADRE_MAXIMUM = 8
"""Epaisseur de cadre au-dela de laquelle ce n'est plus un cadre.

Les sets LEGO Art n'en ont pas ; deux tenons suffisent a lire un bord et a
ceinturer les sections. A huit, le cadre pese deja plus que l'oeuvre. Au-dela,
la fabrication part en heures de calcul pour un resultat que personne ne veut :
un cadre de 500 tenons autour d'une mosaique de 16 est une faute de frappe, pas
une intention.
"""

TITRE_MAXIMUM = 200
"""Longueur de titre au-dela de laquelle ce n'est plus un titre.

Il sert de nom sur la couverture de la notice et dans la liste de souhaits
BrickLink. Deux cents caracteres depassent deja tout nom de fichier ; au-dela
c'est un corps de texte, et il casserait la mise en page plutot que de la
remplir.
"""


RELIEF_MAXIMUM = 12
"""Etages de plates au-dela desquels le relief cesse d'etre un relief.

Douze etages font 38 mm de saillie sur une oeuvre de 8 mm de pas : les colonnes
sont plus hautes que larges et le montage devient fragile. La borne dit ou
s'arrete ce que cette chaine sait promettre.
"""


@dataclass(frozen=True)
class Reglages:
    """Tout ce qu'un utilisateur peut choisir. Les defauts sont ceux mesures."""

    studs: int = 48
    hauteur: Optional[int] = None
    relief: int = 0
    references: str = "standard"
    tramage: str = "auto"
    couleurs: Optional[str] = None
    tolerance: float = 1.0
    cadrage: str = "auto"
    seuils: str = "otsu"
    codes_couleur: Optional[str] = None
    profondeur_inversee: bool = False
    relief_inverse: bool = False
    """Convention du bas-relief quand aucune profondeur n'est mesuree.

    `False` : clair = haut, la convention du camee. `True` : sombre = haut.

    Ce n'est pas un reglage cosmetique, et l'absence de ce champ etait un
    defaut. Sans carte de profondeur, la chaine lit la CLARTE de la photo et
    en fait des etages ; la clarte n'est pas la profondeur, et sur un paysage
    les deux se contredisent franchement. Mesure sur la photo du lievre de
    bronze, 48x64 tenons, trois etages, moyenne des elevations sur le tiers
    haut et le tiers bas de l'image :

        convention        tiers haut (ciel)   tiers bas (sol)
        clair = haut                   2,25              0,40
        sombre = haut                  0,75              2,60

    Clair = haut fait SAILLIR LE CIEL de 5 mm devant le sol. Personne ne peut
    vouloir cela, et jusqu'ici personne ne pouvait l'eviter :
    `--profondeur-inversee` ne parle que de l'encodage d'une carte fournie et
    ne touchait pas ce chemin-la. Sur un portrait la convention du camee reste
    la bonne — le visage est plus clair que le fond — d'ou un defaut inchange
    et un interrupteur, plutot qu'un renversement.

    Aucun critere automatique ne les departage : les marches tombent aux memes
    endroits dans les deux cas (555 contre 559 tenons de marche sur la photo
    des chiens), donc `relief_edge_alignment` est aveugle a l'inversion. Le
    choix revient a l'oeil, et l'oeil a besoin de pouvoir le faire."""
    lignes_par_page: int = 4
    par_etape: int = 24
    titre: str = "mosaique"
    debruitage: float = mosaic.DENOISE_TOLERANCE
    """Ecart tolere pour effacer une tuile isolee. 0 : on n'efface rien.

    Le defaut n'est pas zero, et c'est une decision de produit mesuree : a 4
    delta E, on perd 0,02 delta E de fidelite moyenne et on gagne 5 a 6 % de
    pieces et jusqu'a 75 % de tuiles isolees. Une tuile qui ne ressemble a
    aucune de ses voisines n'etait pas dans la photo."""
    cadre: int = 2
    """Epaisseur du cadre, en tenons. Le defaut n'est pas zero, et c'est une
    decision de produit : un tableau se cadre. Le cadre ferme l'oeuvre sur ses
    quatre cotes, la fait lire comme un tableau plutot que comme un carrelage,
    et — quand l'oeuvre est decoupee — ceinture les sections. `0` le retire."""
    cadre_couleur: int = FRAME_COLOR
    sections: int = 0
    """Cote d'une section, en tenons. 0 : l'oeuvre est d'un seul tenant.

    Au-dela d'une cinquantaine de tenons, une mosaique ne passe plus ni sur une
    table, ni dans un carton. Decoupee, chaque section est un modele complet
    avec sa propre notice, et une couche de plates les reunit par-dessous."""

    def __post_init__(self) -> None:
        if self.studs < 1:
            raise ValueError("une mosaique fait au moins un tenon de cote")
        if self.hauteur is not None and self.hauteur < 1:
            raise ValueError("une mosaique fait au moins un tenon de haut")
        # Le plafond n'est pas un caprice : au-dela, la fabrication se termine
        # par une erreur de MEMOIRE apres plusieurs minutes de calcul. Refuser
        # tout de suite, en disant pourquoi, vaut mieux que partir dans le mur.
        surface = self.studs * (self.hauteur or self.studs)
        if surface > TENONS_MAXIMUM:
            raise ValueError(
                f"{self.studs} x {self.hauteur or self.studs} fait "
                f"{surface} tenons, au-dela des {TENONS_MAXIMUM} que cette "
                "chaine tient en memoire. Une oeuvre plus grande se fait en "
                "plusieurs, cote a cote."
            )
        if self.relief < 0:
            raise ValueError("un nombre d'etages est positif")
        if self.relief > RELIEF_MAXIMUM:
            raise ValueError(
                f"{self.relief} etages : au-dela de {RELIEF_MAXIMUM}, le "
                "relief ne se lit plus, il se casse. Un etage fait 3,2 mm."
            )
        if self.references not in JEUX_DE_TUILES:
            raise ValueError(f"references vaut {' ou '.join(JEUX_DE_TUILES)}")
        if self.tramage not in TRAMAGES:
            raise ValueError(f"tramage vaut {' ou '.join(TRAMAGES)}")
        if self.seuils not in ("otsu", "uniform"):
            raise ValueError("seuils vaut 'otsu' ou 'uniform'")
        if self.sections < 0:
            raise ValueError("un cote de section est positif")
        if self.cadre < 0:
            raise ValueError("une epaisseur de cadre est positive")
        # Un cadre plus large que l'oeuvre n'est plus un cadre : c'est un mur
        # de briques avec une vignette au milieu, et il coute des heures a
        # batir. La borne se lit dans les deux sens — elle protege l'atelier
        # d'une requete absurde et l'utilisateur d'une faute de frappe.
        if self.cadre > CADRE_MAXIMUM:
            raise ValueError(
                f"un cadre de {self.cadre} tenons n'entoure plus rien : "
                f"{CADRE_MAXIMUM} tenons au maximum"
            )
        if self.debruitage < 0:
            raise ValueError("une tolerance de debruitage est positive")
        if len(self.titre) > TITRE_MAXIMUM:
            raise ValueError(
                f"un titre de {len(self.titre)} caracteres ne tient ni sur la "
                f"couverture de la notice ni dans un nom de fichier : "
                f"{TITRE_MAXIMUM} au maximum"
            )


@dataclass(frozen=True)
class Resultat:
    """Ce que la chaine produit. Aucun fichier : des octets et des lignes."""

    fichiers: Mapping[str, bytes]
    journal: Tuple[Tuple[str, str], ...]
    """Suite de (flux, texte), dans l'ordre. `flux` vaut "info" ou "alerte" :
    une interface les affiche differemment, un terminal les envoie sur deux
    sorties. L'ordre est celui de la chaine, pas deux listes a recoller."""
    mesures: Mapping[str, object]

    @property
    def lignes(self) -> Tuple[str, ...]:
        return tuple(texte for _, texte in self.journal)


def lire_image(donnees: bytes) -> Image:
    """Octets -> image. JPEG, PNG ou PPM, reconnus a leur signature."""
    if donnees[:8] == b"\x89PNG\r\n\x1a\n":
        return read_png(donnees)
    if donnees[:2] == b"\xff\xd8":
        # Decodage au huitieme : pour une mosaique de 48 tenons, reconstruire
        # les douze millions de pixels d'origine serait du travail jete.
        return jpeg.read_jpeg_eighth(donnees)
    if donnees[:2] == b"P6":
        return read_ppm(donnees)
    raise ValueError("format non reconnu (JPEG, PNG ou PPM attendus)")


def palette_utilisable(chemins: Optional[Sequence[str]] = None):
    """(palette commandable, ligne de journal). Rien n'est imprime.

    Le fichier officiel contient les transparentes, les chromees, les nacrees,
    les caoutchouc et deux marqueurs internes au format. Une liste de course qui
    les contient est incommandable : elles sont filtrees.
    """
    complete, provenance = load_best_palette(chemins)
    if provenance.startswith("provisoire"):
        return complete, (
            "alerte",
            "  palette : PROVISOIRE (12 couleurs recopiees a la main).\n"
            "            LDConfig.ldr introuvable. Il est livre avec LDraw,\n"
            "            LeoCAD et BrickLink Studio ; --ldconfig CHEMIN sinon.\n"
            "            La palette officielle divise l'ecart par deux.",
        )
    commandables = complete.solids_only()
    return complete, (
        "info",
        f"  palette : {len(complete)} couleurs lues dans {provenance}, "
        f"{len(commandables)} commandables en tuile",
    )


RELIEF_PAR_CONVENTION = "CONVENTION du bas-relief"
"""Debut de la provenance quand le relief vient de la CLARTE et non d'une mesure.

Une constante et non une chaine recopiee : le journal doit pouvoir reconnaitre
ce cas — c'est le seul ou la convention peut sortir a l'envers — et deux
formulations qui divergent rendraient l'avertissement muet sans que rien
n'echoue.
"""


PENTE_SUSPECTE = 0.5
"""Ecart haut/bas, en etages, au-dela duquel le journal signale la pente.

Repere de lecture, pas constante mesuree — comme le 1 % de tours isolees juste
au-dessus. Un demi-etage de moyenne fait 1,6 mm : en dessous, la pente ne se
voit pas ; au-dessus, un haut d'image qui ressort se remarque. Trois photos ne
suffisent pas a etalonner un seuil, et c'est pourquoi le journal SIGNALE au
lieu de corriger.
"""


def carte_de_relief(image, origine, cadrage, brut, reglages, hauteur,
                    carte_fournie=None):
    """Les elevations, par la source la plus fiable disponible.

    Trois sources, dans cet ordre, et l'ordre n'est pas arbitraire : il va de
    la profondeur MESUREE a la convention.

    1. Une carte fournie. Un estimateur monoculaire (MiDaS, Depth Anything,
       Marigold) en produit d'excellentes, hors de ce depot, avec un reseau
       qu'il serait absurde d'embarquer ici.
    2. La carte EMBARQUEE dans le JPEG, si le telephone en a ecrit une. Le mode
       portrait mesure la profondeur et beaucoup d'appareils la deposent dans
       le fichier. C'est de la mesure, pas une convention.
    3. La clarte de la photo. La convention du camee, celle du bas-relief.
       Clair = haut par defaut, sombre = haut avec `relief_inverse` : sur un
       paysage la premiere fait saillir le ciel devant le sol, et il faut
       pouvoir la renverser (voir `Reglages.relief_inverse`).

    On dit toujours laquelle a servi : un relief juste et un relief plausible
    se ressemblent, et seule la provenance les distingue.

    `image` est la photo DEJA ROGNEE, `origine` celle d'avant le rognage, et
    `cadrage` la position de la fenetre. Les trois sont necessaires, et l'avoir
    oublie etait un defaut : une carte de profondeur doit subir EXACTEMENT le
    meme rognage que la photo (§ 5.48 du registre).
    """
    if carte_fournie is not None:
        carte = read_depth_map(carte_fournie)
        return heights_from_depth(
            carte, origine, reglages.studs, hauteur, reglages.relief,
            near_is_bright=not reglages.profondeur_inversee,
            fit="crop", offset=cadrage,
        ), (f"carte de profondeur fournie ({carte.width}x{carte.height}) — "
            "profondeur MESUREE")

    if brut[:2] == b"\xff\xd8":
        try:
            carte = embedded_depth(brut)
        except NoEmbeddedDepth:
            pass
        else:
            return heights_from_depth(
                carte, origine, reglages.studs, hauteur, reglages.relief,
                near_is_bright=not reglages.profondeur_inversee,
                fit="crop", offset=cadrage,
            ), (f"carte EMBARQUEE dans le JPEG ({carte.width}x{carte.height}) "
                "— profondeur MESUREE par l'appareil")

    # Le relief se lit sur la PHOTO, jamais sur la grille : ni palette, ni
    # tramage. Le tramage est un bruit que l'oeil fond dans les couleurs et
    # qu'il ne fond jamais dans les hauteurs (voir `relief_from_image`).
    sens = "sombre = haut" if reglages.relief_inverse else "clair = haut"
    return mosaic.relief_from_image(
        image, reglages.studs, hauteur, reglages.relief,
        invert=reglages.relief_inverse,
        thresholds=reglages.seuils, fit="stretch",
    ), f"{RELIEF_PAR_CONVENTION}, {sens} — aucune profondeur mesuree"


def grille_livree(image, palette, studs_x: int, studs_y: int, reglages):
    """La grille TELLE QUE LA CHAINE LA LIVRE : quantifiee, puis nettoyee.

    Existe pour une raison precise. Le conseil de format quantifiait de son
    cote, sans cadre, sans nettoyage et sans tramage automatique — et annoncait
    donc des nombres de pieces faux de -32 a +91 par rapport a ce que la chaine
    fabrique vraiment. Les ecarts se compensaient a moitie, ce qui est le pire
    des cas : les chiffres paraissaient justes.

    C'est exactement le defaut du § 5.61, refait un commit plus tard : evaluer
    une grille qui n'est pas celle qu'on livre. Deux fois la meme erreur veut
    dire que le probleme n'etait pas l'inattention mais la DUPLICATION. Une
    seule fonction, donc, appelee des deux cotes.
    """
    grille = mosaic.quantize(
        image, palette, studs_x, studs_y, TRAMAGES[reglages.tramage],
        "stretch", denoise_tolerance=reglages.debruitage,
    )
    if reglages.debruitage:
        grille = mosaic.denoise(grille, image, reglages.debruitage, "stretch")
    return grille


def mosaique_livree(grille, reglages, elevations=None):
    """L'oeuvre telle qu'elle sera batie, cadre compris."""
    return mosaic.build(
        grille, tiles=JEUX_DE_TUILES[reglages.references], heights=elevations,
        frame=reglages.cadre, frame_color=reglages.cadre_couleur,
    )


FORMATS_CONSEILLES = (0.67, 1.0, 1.5, 2.0)
"""Multiples de la taille demandee qu'on met en balance.

Un en dessous, celle qu'on a demandee, et deux au-dessus : assez pour voir ou
la courbe se casse, sans facturer six quantifications a qui pose la question.
"""


def conseil_de_format(image, studs_x: int, studs_y: int, palette,
                      reglages=None, cadrage=0.5,
                      multiples=FORMATS_CONSEILLES):
    """Ce que chaque format gagne en detail, et ce qu'il coute en pieces.

    L'arbitrage le plus consequent de toute la chaine — on engage des milliers
    de pieces — et rien n'aidait a le prendre. Il ne peut pas etre tranche une
    fois pour toutes dans la documentation : un portrait lisse et une facade
    ciselee n'ont pas le meme point de rupture. Il se calcule PAR PHOTO.

    L'ecart par tuile ne repond pas a la question : il est borne par la palette
    et reste quasiment plat quand on triple la resolution (6,79 -> 6,66 de 32 a
    96 tenons). C'est `detail_gap`, mesure sur une grille commune a tous les
    formats, qui voit ce qu'on gagne vraiment (10,0 -> 7,4 sur la meme plage).

    Rend une liste de dicts, du plus petit au plus grand.
    """
    tailles = []
    for facteur in sorted(multiples):
        cote = max(2, round(studs_x * facteur))
        hauteur = max(2, round(studs_y * facteur))
        if (cote, hauteur) not in tailles:
            tailles.append((cote, hauteur))
    # Une seule grille de mesure, celle de la plus grande : mesurer chaque
    # format sur sa propre echelle ne comparerait rien.
    mesure = mosaic.grille_de_mesure(*tailles[-1])

    if reglages is None:
        reglages = Reglages(studs=studs_x, hauteur=studs_y)

    conseils = []
    for cote, hauteur in tailles:
        cadree = mosaic._cadrer(image, cote, hauteur, "crop", cadrage)
        grille = grille_livree(cadree, palette, cote, hauteur, reglages)
        elevations = None
        if reglages.relief:
            # Le relief ajoute des plates, et il faut donc les compter. Un
            # conseil qui l'ignore annonce une oeuvre moins chere que celle
            # qu'on fabriquera.
            elevations = mosaic.relief_from_image(
                cadree, cote, hauteur, reglages.relief,
                invert=reglages.relief_inverse,
                thresholds=reglages.seuils, fit="stretch")
        oeuvre = mosaique_livree(grille, reglages, elevations)
        rvb_cadre = next(
            (c.rgb for c in palette if c.code == reglages.cadre_couleur), None)
        vue = mosaic.preview(oeuvre, scale=4, frame_rgb=rvb_cadre)
        # Le TIERS CENTRAL, et c'est le seul apercu qui prouve quelque chose.
        # Une vignette de l'oeuvre entiere a 56 pixels de large montre la meme
        # chose pour 32 et pour 96 tenons — elle decore, elle n'informe pas.
        # Le meme morceau de scene, affiche a la meme largeur, porte trois fois
        # plus de tuiles dans la version fine : la difference se VOIT.
        tiers = imaging.crop(
            vue, vue.width // 3, vue.height // 3,
            max(1, vue.width // 3), max(1, vue.height // 3))
        conseils.append({
            # Un apercu vaut mieux qu'un ecart de 0,61 delta E : personne ne
            # decide d'acheter cinq mille pieces sur un nombre abstrait.
            "apercu": write_png(vue),
            "detail_vu": write_png(tiers),
            "studs_x": cote,
            "studs_y": hauteur,
            "largeur_cm": round(oeuvre.outer_x * 0.8),
            "hauteur_cm": round(oeuvre.outer_y * 0.8),
            "pieces": oeuvre.part_count,
            "detail": mosaic.detail_gap(grille, cadree, cote, hauteur, mesure),
        })
    return conseils


def _nom_couleur(palette: Palette, code: int) -> str:
    for couleur in palette:
        if couleur.code == code:
            return couleur.name
    return f"code {code}"


def run(
    photo: bytes,
    reglages: Reglages = Reglages(),
    palette: Optional[Palette] = None,
    palette_complete: Optional[Palette] = None,
    carte_profondeur: Optional[bytes] = None,
    table_bricklink: Optional[Mapping[int, str]] = None,
    table_elements: Optional["pickabrick.TableElements"] = None,
    note_palette: Optional[Tuple[str, str]] = None,
) -> Resultat:
    """Photo -> fichiers livrables. Leve `ModeleRefuse` si ca ne tient pas.

    `palette` est celle qu'on emploie ; `palette_complete` sert a NOMMER les
    couleurs de la liste de course, y compris celles qu'une restriction a
    ecartees. Sans elles, la palette provisoire est chargee et le journal le
    dit. `note_palette` permet a un appelant qui a charge la palette lui-meme
    d'inserer sa ligne de journal au bon endroit.
    """
    journal: List[Tuple[str, str]] = []
    fichiers: Dict[str, bytes] = {}

    image = lire_image(photo)
    journal.append(("info", f"image   : {image.width} x {image.height} pixels"))
    if palette is None:
        complete, ligne = palette_utilisable()
        journal.append(ligne)
        palette = complete.solids_only() if ligne[0] == "info" else complete
        palette_complete = complete
    elif note_palette is not None:
        # L'appelant a charge la palette lui-meme : sa ligne de journal se
        # place ici, a l'endroit ou elle serait tombee.
        journal.append(note_palette)
    if palette_complete is None:
        palette_complete = palette

    # Sans consigne, la hauteur suit les PROPORTIONS DE LA PHOTO : rien n'est
    # rogne, rien n'est etire. Demander une hauteur, c'est demander un cadrage.
    if reglages.hauteur:
        hauteur = reglages.hauteur
    else:
        hauteur = max(1, round(reglages.studs * image.height / image.width))
        if hauteur != reglages.studs:
            journal.append((
                "info",
                f"  cadrage : {reglages.studs} x {hauteur} tenons, "
                f"proportions de la photo conservees "
                f"(--hauteur {reglages.studs} pour un carre, la photo sera rognee)",
            ))
    if reglages.studs * hauteur > TENONS_LENTS:
        journal.append((
            "alerte",
            f"  ATTENTION — {reglages.studs} x {hauteur} tenons : la "
            "fabrication et le controle des invariants prendront plusieurs "
            "minutes.\n            C'est dit avant, pas apres.",
        ))

    cadrage = reglages.cadrage
    if cadrage != "auto":
        cadrage = float(cadrage)
    if cadrage == "auto" and image.width / image.height != reglages.studs / hauteur:
        cadrage = imaging.attentional_offset(image, reglages.studs / hauteur)
        journal.append((
            "info", f"  cadrage : fenetre placee a {cadrage:.2f} (detail maximal)"
        ))
    if cadrage == "auto":
        # Les proportions coincident deja : le rognage ne fait rien et la
        # position de la fenetre n'a aucun effet. La fixer permet de la
        # transmettre telle quelle a la carte de profondeur.
        cadrage = 0.5
    # L'originale est conservee : une carte de profondeur doit subir le MEME
    # rognage, et le refaire depuis la photo deja rognee serait le refaire deux
    # fois.
    origine = image
    image = crop_to_ratio(image, reglages.studs / hauteur, cadrage)

    # En dessous de deux pixels par tenon, il n'y a plus de moyenne : chaque
    # tuile prend la couleur d'un pixel a peu pres au hasard dans sa zone.
    par_tenon = min(image.width / reglages.studs, image.height / hauteur)
    if par_tenon < 2.0:
        journal.append((
            "alerte",
            f"  ATTENTION — {par_tenon:.1f} pixel(s) par tenon seulement.\n"
            f"            L'image cadree fait {image.width} x {image.height} pour "
            f"une mosaique de {reglages.studs} x {hauteur} tenons.\n"
            f"            Sous 2 px/tenon il n'y a plus de moyenne : le rendu "
            f"sera bruite.\n"
            f"            Fournir une photo plus grande, ou reduire --studs a "
            f"{max(1, int(image.width // 2))}.",
        ))
    reduite = resample_box(image, reglages.studs, hauteur)
    pixels = [
        reduite.pixel(x, y) for y in range(hauteur) for x in range(reglages.studs)
    ]

    manques = gap_report(pixels, palette)
    if manques:
        lignes = ["  ATTENTION — couleurs que cette photo reclame et que la "
                  "palette n'a pas :"]
        for manque in manques[:4]:
            lignes.append(
                f"      {manque.hex}  {manque.share * 100:4.1f}% des tuiles  "
                f"-> {manque.best_available.name} a {manque.error:.0f} delta E"
            )
        if len(palette) < 40:
            lignes.append("      La palette officielle corrige la plus grande "
                          "part de l'ecart.")
        journal.append(("info", "\n".join(lignes)))

    if reglages.codes_couleur:
        voulus = [int(c) for c in reglages.codes_couleur.replace(" ", "").split(",")
                  if c]
        palette = palette.restricted_to(voulus)
        absents = set(voulus) - {c.code for c in palette}
        journal.append((
            "info",
            f"  palette restreinte a {len(palette)} couleurs imposees"
            + (f" ({len(absents)} codes inconnus ignores)" if absents else ""),
        ))

    if reglages.couleurs == "auto":
        avant = palette
        palette, retenu, meilleur = mosaic.cheapest_palette(
            image, palette, reglages.studs, hauteur, tolerance=reglages.tolerance
        )
        if len(palette) == len(avant):
            journal.append((
                "info",
                f"  palette gardee entiere ({len(avant)} couleurs) : aucune "
                "reduction ne coute moins cher a cette tolerance. Reduire la "
                "palette elargit les ecarts, ce qui declenche le tramage, ce "
                "qui brise les suites et multiplie les pieces.",
            ))
        else:
            journal.append((
                "info",
                f"  palette reduite a {len(palette)} couleurs sur {len(avant)} : "
                f"{retenu.tiles} tuiles et {retenu.lots} lots au lieu de "
                f"{meilleur.tiles} et {meilleur.lots}, en abandonnant "
                f"{max(0.0, retenu.tonal_mean - meilleur.tonal_mean):.2f} delta E "
                "de justesse tonale",
            ))
    elif reglages.couleurs:
        palette = palette.best_subset(pixels, int(reglages.couleurs))
        journal.append((
            "info",
            f"  palette reduite aux {len(palette)} meilleures couleurs pour "
            "cette image",
        ))

    depart = time.perf_counter()
    # L'image est deja au bon rapport : plus rien a rogner ici.
    arbitrage: dict = {}
    grille = mosaic.quantize(
        image, palette, reglages.studs, hauteur, TRAMAGES[reglages.tramage],
        "stretch", denoise_tolerance=reglages.debruitage, rapport=arbitrage,
    )   # meme appel que `grille_livree` ; le nettoyage suit plus bas, entoure
        # du journal qui compte les tuiles effacees.
    # Le tramage est un ARBITRAGE, pas un reglage technique : il achete de la
    # justesse tonale avec du grain visible. `blending_tiles` dit que l'oeil ne
    # fond jamais deux tuiles de 8 mm, a aucune distance — le grain se verra
    # donc. La decision doit etre visible, et reversible d'un drapeau.
    if reglages.tramage == "auto":
        nette = mosaic.quantize(image, palette, reglages.studs, hauteur,
                                False, "stretch")
        if nette != grille:
            isolees = sum(
                1 for y in range(hauteur) for x in range(reglages.studs)
                if all(grille[y][x].code != grille[vy][vx].code
                       for vy, vx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1))
                       if 0 <= vy < hauteur and 0 <= vx < reglages.studs)
            )
            # Le critere tranche sur la justesse tonale, qui se mesure sur la
            # MOYENNE de blocs de 4x4 tuiles — et une moyenne ne voit pas le
            # grain qu'elle moyenne. `detail_gap`, lui, compare aux memes points
            # physiques sans moyenner : il le voit. Les deux se contredisent
            # parfois, et sur une photo reelle c'est le grain qui avait raison.
            #
            # Aucun seuil ne separe le grain qui BRUITE (photographie) du grain
            # qui ADOUCIT (degrade pur) : meme perte de detail, verdict visuel
            # oppose. Plutot que de trancher a la place de qui regarde, on donne
            # le chiffre — et le mot pour l'annuler.
            mesure = mosaic.grille_de_mesure(reglages.studs, hauteur)
            perdu = (mosaic.detail_gap(grille, image, reglages.studs, hauteur,
                                       mesure)
                     - mosaic.detail_gap(nette, image, reglages.studs, hauteur,
                                         mesure))
            gagne = arbitrage.get("gain_tonal")
            journal.append((
                "info",
                "  tramage : applique — il gagne "
                + (f"{gagne:.2f} delta E sur le PIRE ecart tonal"
                   if gagne is not None else "de la justesse tonale")
                + f" et laisse {isolees} tuile(s) isolees de grain.",
            ))
            journal.append((
                "info" if perdu <= 0 else "alerte",
                f"            ce grain coute {perdu:+.2f} delta E de finesse "
                "locale" + (" — le gain tonal se mesure sur des moyennes qui "
                            "ne le voient pas.\n            "
                            "« --tramage aucun » si vous preferez la nettete."
                            if perdu > 0 else
                            ". Il ne coute rien ici."),
            ))
        else:
            gagne = arbitrage.get("gain_tonal")
            journal.append((
                "info",
                "  tramage : ecarte — il ne gagnait "
                + (f"que {gagne:.2f} delta E sur le pire ecart tonal, sous le "
                   f"seuil de {arbitrage.get('seuil', 0):.2f}"
                   if gagne is not None else "pas assez")
                + ", pour le grain qu'il aurait coute.",
            ))

    if reglages.debruitage:
        avant = grille
        grille = mosaic.denoise(grille, image, reglages.debruitage, "stretch")
        effacees = sum(1 for y in range(hauteur) for x in range(reglages.studs)
                       if avant[y][x].code != grille[y][x].code)
        if effacees:
            journal.append((
                "info",
                f"  nettoyage: {effacees} tuile(s) isolee(s) effacee(s) — "
                "elles ne ressemblaient a aucune de leurs voisines et "
                "coutaient une piece chacune",
            ))

    elevations, provenance = (
        carte_de_relief(image, origine, cadrage, photo, reglages, hauteur,
                        carte_profondeur)
        if reglages.relief else (None, "")
    )
    assemblage = None
    if reglages.sections:
        assemblage = build_assembly(
            grille, reglages.sections,
            tiles=JEUX_DE_TUILES[reglages.references], heights=elevations,
            frame=reglages.cadre, frame_color=reglages.cadre_couleur,
        )
        # L'oeuvre entiere reste construite : c'est elle qui porte la grille,
        # les apercus et la nomenclature globale. Les sections en sont la
        # decoupe, pas un autre modele.
        journal.append((
            "info",
            f"  sections: {assemblage.rows} x {assemblage.columns} de "
            f"{reglages.sections} tenons, chacune un modele complet, "
            f"{assemblage.join_count} plates de jonction par-dessous",
        ))
    # `mosaique` est l'oeuvre vue comme un tout : elle sert aux apercus, a la
    # couverture et aux vues de bande. Elle porte donc TOUJOURS le cadre, meme
    # quand l'oeuvre est decoupee — sinon la decoupe changerait l'image montree
    # a l'utilisateur, alors qu'elle ne change rien a l'oeuvre.
    mosaique = mosaique_livree(grille, reglages, elevations)
    # Ce qu'on LIVRE : l'assemblage quand l'oeuvre est decoupee, l'oeuvre
    # elle-meme sinon. Tout ce qui se compte — pieces, lots, etapes — se compte
    # ici, et non sur `mosaique`, qui ne serait alors qu'une vue de travail.
    a_controler = assemblage if assemblage is not None else mosaique
    if reglages.relief:
        plateaux = mosaic.relief_plateaus(elevations)
        clous = mosaic.relief_speckle(elevations)
        rendement = mosaic.relief_edge_alignment(elevations, image, fit="stretch")
        hauteurs = sorted({v for ligne in elevations for v in ligne})
        journal.append((
            "info",
            f"  relief  : {reglages.relief} etage(s), "
            f"{ldu_to_mm(reglages.relief * 8):.1f} mm d'epaisseur",
        ))
        journal.append(("info", f"            source : {provenance}"))
        # Le seuil est un repere de lecture, pas une constante mesuree : au-dela
        # de 1 % de tours isolees, les bandes de niveau sont devenues plus fines
        # qu'un tenon et le relief se lit comme du grain.
        taux = clous / (reglages.studs * hauteur)
        journal.append((
            "info",
            f"            {len(plateaux)} plateaux (le plus grand : "
            f"{plateaux[0]} tenons), {clous} case(s) isolee(s)"
            + (f" — {100 * taux:.1f} % de tours isolees : le relief se fragmente,"
               " moins d'etages ou plus de tenons" if taux > 0.01 else ""),
        ))
        journal.append((
            "info",
            f"            rendement des marches {rendement:.2f} sur 1 — part du "
            "contraste de la photo que les marches exploitent",
        ))
        # Le relief tire de la clarte n'est pas de la profondeur, et il peut
        # donc sortir a l'envers sans que rien ne proteste : le rendement des
        # marches, seul indicateur jusqu'ici, est AVEUGLE a l'inversion — les
        # marches tombent aux memes endroits dans les deux sens. Il fallait une
        # grandeur orientee. Elle est signalee, jamais corrigee : trois photos
        # ne suffisent pas a etalonner un critere (§ 5.66, § 5.67).
        pente = mosaic.relief_tilt(elevations)
        remarque = ""
        if pente > PENTE_SUSPECTE:
            remarque = (" — le haut de l'image RESSORT ; sur un paysage c'est "
                        "le ciel devant le sol")
            # Le remede depend de la source, et il n'y en a pas toujours un.
            # Le dire quand il n'existe pas serait pire que se taire.
            if provenance.startswith(RELIEF_PAR_CONVENTION):
                if not reglages.relief_inverse:
                    # Formulation NEUTRE : le meme journal s'affiche dans la
                    # page, ou le reglage est une case a cocher et non un
                    # drapeau. Nommer l'option de la commande y serait faux.
                    remarque += " — renversez la convention (sombre = haut)"
            else:
                remarque += ", verifiez le sens de la carte"
        journal.append((
            "info",
            f"            tiers haut {pente:+.2f} etage(s) par rapport au tiers "
            f"bas{remarque}",
        ))
        if len(hauteurs) < reglages.relief + 1:
            journal.append((
                "alerte",
                f"            ATTENTION : {reglages.relief} etages demandes mais "
                f"seules les hauteurs {hauteurs} servent. Les etages inutilises "
                "coutent leurs plates sans rien relever.",
            ))
    porteur = assemblage if assemblage is not None else mosaique
    if reglages.cadre:
        journal.append((
            "info",
            f"  cadre   : {reglages.cadre} tenons, "
            f"{porteur.frame_courses} assise(s) de briques, "
            f"{porteur.frame_count} pieces — hors tout "
            f"{ldu_to_mm(porteur.outer_x * 20) / 10:.0f} x "
            f"{ldu_to_mm(porteur.outer_y * 20) / 10:.0f} cm",
        ))
    sans_fusion = mosaique.stud_count
    economie = 100 * (1 - mosaique.tile_count / sans_fusion)
    journal.append((
        "info",
        f"modele  : {a_controler.part_count} pieces ({mosaique.tile_count} "
        f"tuiles + substrat) en {time.perf_counter() - depart:.2f}s",
    ))
    journal.append((
        "info",
        f"  fusion  : {mosaique.tile_count} tuiles au lieu de {sans_fusion} "
        f"({economie:.0f} % de pieces en moins), couleurs inchangees",
    ))
    if economie > 1:
        journal.append((
            "info",
            "            mais les joints changent : appareil decale au lieu de "
            "la grille uniforme des sets LEGO Art. Voir apercu_joints.png ; "
            "--references minimal rend la grille.",
        ))

    depart = time.perf_counter()
    etat = assemble(a_controler.placed_parts, LEGO_TOLERANCE,
                    search=LatticeSearchApproximation())
    liaisons = sum(len(bonds) for _, _, bonds in etat.graph.edges)
    violations = (
        check_h2_collision(a_controler.placed_parts, a_controler.geometries)
        + check_h3_authority_integrity(etat.graph)
        + check_h4_floating(
            etat.graph,
            founded_part_ids(a_controler.placed_parts, a_controler.geometries))
        + check_h5_disconnected(etat.graph)
        + check_h6_foundation(a_controler.placed_parts, a_controler.geometries)
    )
    journal.append((
        "info",
        f"controle: {liaisons} liaisons, {len(violations)} violations "
        f"en {time.perf_counter() - depart:.2f}s",
    ))
    if violations:
        raise ModeleRefuse("modele NON livre : il ne tiendrait pas ensemble.",
                           violations)

    rvb_cadre = next(
        (c.rgb for c in palette_complete if c.code == reglages.cadre_couleur),
        None,
    )
    if reglages.relief:
        fichiers["apercu_relief.png"] = write_png(
            mosaic.preview(mosaique, scale=8, relief=True, frame_rgb=rvb_cadre))
    fichiers["apercu_joints.png"] = write_png(
        mosaic.preview(mosaique, scale=12, seams=True, frame_rgb=rvb_cadre))
    fichiers["apercu.png"] = write_png(
        mosaic.preview(mosaique, scale=8, frame_rgb=rvb_cadre))
    # La photo telle que la mosaique l'a vue : meme cadrage, meme moyenne par
    # tenon, meme cadre. Elle se superpose au pixel pres a `apercu.png`, ce qui
    # est la seule facon de comparer honnetement — et elle montre au passage ce
    # que le cadrage a coupe, qui n'apparaissait nulle part ailleurs.
    fichiers["apercu_source.png"] = write_png(
        mosaic.source_preview(
            imaging.resample_box(image, reglages.studs, hauteur),
            mosaique, scale=8, frame_rgb=rvb_cadre))

    nomenclature = bill_of_materials(a_controler.instances,
                                     a_controler.placed_parts)

    # L'element id, quand on le connait, va aussi dans la liste LISIBLE. Le CSV
    # d'envoi ne porte que deux colonnes muettes ; celui-ci est celui qu'on
    # ouvre pour chercher une piece a la main, et c'est la qu'un numero sert.
    par_lot = {}
    if table_elements:
        par_code = {c.code: c for c in palette_complete}
        for ligne in nomenclature:
            element, _ = pickabrick.element_pour(
                ligne, table_elements, par_code.get(ligne.color_id))
            if element is not None:
                par_lot[(ligne.design_id, ligne.color_id)] = element

    entete = "design_id,nom,code_couleur,couleur,quantite"
    lignes = [entete + (",element_id" if par_lot else "")]
    for ligne in sorted(nomenclature, key=lambda l: -l.quantity):
        texte = (
            f'{ligne.design_id},"{ligne.name}",{ligne.color_id},'
            f'"{_nom_couleur(palette_complete, ligne.color_id)}",{ligne.quantity}'
        )
        if par_lot:
            texte += "," + par_lot.get((ligne.design_id, ligne.color_id), "")
        lignes.append(texte)
    fichiers["liste_de_course.csv"] = ("\n".join(lignes) + "\n").encode("utf-8")

    commande = {"commande_bricklink_lots": 0, "commande_lego_lots": 0,
                "commande_lego_pieces": 0, "commande_lego_envois": 0,
                "commande_lego_manquants": 0}

    if table_bricklink:
        try:
            fichiers["commande_bricklink.xml"] = bricklink.dumps_wanted_list(
                nomenclature, table_bricklink, name=reglages.titre
            ).encode("utf-8")
        except bricklink.UnmappedColors as manque:
            journal.append((
                "alerte", f"  commande BrickLink NON produite — {manque}"))
            # Un refus sec n'aide personne : on livre le gabarit de ce qui
            # manque, avec de quoi le retrouver. Une ligne remplie suffit.
            manquantes = [
                c for c in palette_complete
                if c.code in {l.color_id for l in nomenclature}
                and c.code not in table_bricklink
            ]
            fichiers["couleurs_a_completer.csv"] = bricklink.color_map_template(
                manquantes, table_bricklink).encode("utf-8")
            journal.append((
                "info",
                f"  gabarit : couleurs_a_completer.csv, {len(manquantes)} "
                "couleur(s) a renseigner puis a repasser en --bricklink",
            ))
        else:
            commande["commande_bricklink_lots"] = len(nomenclature)
            journal.append((
                "info",
                f"  commande BrickLink : {len(nomenclature)} lots, "
                f"{sum(l.quantity for l in nomenclature)} pieces, prete a l'envoi",
            ))

    if table_elements:
        # Pick a Brick ne veut pas le numero de moule mais l'ELEMENT ID, qui
        # designe un moule DANS UNE COULEUR. Ce numero est attribue, pas
        # calcule : il vient du catalogue que l'utilisateur a fourni.
        trouves, absents, replis = pickabrick.elements_for_bom(
            nomenclature, table_elements, palette_complete)
        if not trouves:
            journal.append((
                "alerte",
                "  commande LEGO NON produite — aucun des "
                f"{len(nomenclature)} lots n'a d'element id dans ce catalogue. "
                "Verifiez qu'il couvre bien les pieces et les couleurs employees",
            ))
        else:
            envois = pickabrick.dumps_upload(trouves)
            commande["commande_lego_lots"] = len(trouves)
            commande["commande_lego_pieces"] = sum(q for _, q in trouves)
            commande["commande_lego_envois"] = len(envois)
            for rang, envoi in enumerate(envois, start=1):
                nom = ("commande_lego.csv" if len(envois) == 1
                       else f"commande_lego_{rang}.csv")
                fichiers[nom] = envoi.encode("utf-8")
            journal.append((
                "info",
                f"  commande LEGO : {len(trouves)} lots, "
                f"{sum(q for _, q in trouves)} pieces, "
                + (f"{len(envois)} fichiers a televerser sur Pick a Brick "
                   f"(limite de {pickabrick.ELEMENTS_PAR_ENVOI} references par "
                   "envoi)" if len(envois) > 1
                   else "a televerser sur Pick a Brick"),
            ))
            if replis:
                journal.append((
                    "info",
                    f"  dont {replis} lot(s) apparies par la reference tronquee "
                    "(3070b -> 3070) : meme moule, ecriture differente",
                ))
        if absents:
            # Un lot introuvable est un lot ABSENT du fichier, pas un lot faux :
            # on le constate a l'upload, la liste a la main. C'est pourquoi on
            # livre quand meme, contrairement a la commande BrickLink.
            commande["commande_lego_manquants"] = len(absents)
            fichiers["pieces_sans_element.csv"] = pickabrick.missing_report(
                absents, palette_complete).encode("utf-8")
            journal.append((
                "alerte",
                f"  {len(absents)} lot(s) sans element id — "
                f"{sum(l.quantity for l in absents)} pieces a chercher a la "
                "main, voir pieces_sans_element.csv",
            ))
        journal.append((
            "info",
            "  la disponibilite reelle n'est pas connue ici : c'est Pick a "
            "Brick qui dira, a l'envoi, ce qui est vendable aujourd'hui",
        ))

    plan = instructions.plan_build(
        a_controler.placed_parts, etat.graph, a_controler.instances,
        reglages.par_etape,
    )
    if not plan.validate_dag():  # pragma: no cover - la portance l'interdit
        raise ModeleRefuse("plan de montage cyclique : non livre")
    fichiers["notice.txt"] = (instructions.render_text(plan) + "\n").encode("utf-8")

    fascicule = build_booklet(
        mosaique, plan, nomenclature,
        palette=palette_complete,
        title=reglages.titre.replace("_", " ").title(),
        rows_per_page=reglages.lignes_par_page,
    )
    fichiers["notice.pdf"] = fascicule

    if assemblage is not None:
        # Une notice PAR SECTION : c'est tout l'interet de la decoupe. Chacune
        # est batie et verifiee seule, donc chacune a son propre plan.
        for section in assemblage.sections:
            etat_section = assemble(
                section.mosaic.placed_parts, LEGO_TOLERANCE,
                search=LatticeSearchApproximation(),
            )
            plan_section = instructions.plan_build(
                section.mosaic.placed_parts, etat_section.graph,
                section.mosaic.instances, reglages.par_etape,
            )
            if not plan_section.validate_dag():  # pragma: no cover
                raise ModeleRefuse(f"{section.name} : plan cyclique")
            nomenclature_section = bill_of_materials(
                section.mosaic.instances, section.mosaic.placed_parts)
            fichiers[f"{section.name}/notice.pdf"] = build_booklet(
                section.mosaic, plan_section, nomenclature_section,
                palette=palette_complete,
                title=f"{reglages.titre.replace('_', ' ').title()} — "
                      f"section {section.row + 1}-{section.column + 1}",
                rows_per_page=reglages.lignes_par_page,
            )
            fichiers[f"{section.name}/apercu.png"] = write_png(
                mosaic.preview(section.mosaic, scale=8))

    fichiers["modele.ldr"] = ldraw.dumps_ldr(
        a_controler.placed_parts, a_controler.instances,
        reglages.titre).encode("utf-8")
    fichiers["modele.json"] = dumps_model(
        a_controler.placed_parts, a_controler.geometries, a_controler.instances
    ).encode("utf-8")

    par_tuile = mosaic.fidelity(mosaique.grid, image, 1)
    tonal = mosaic.fidelity(mosaique.grid, image, 4)
    # Le plancher : l'ecart si chaque tenon prenait la MEILLEURE couleur qui
    # existe. Il coute deux centiemes de seconde et il recadre tout le reste —
    # quand le resultat l'atteint, chercher un meilleur choix de couleur est
    # perdu d'avance, et la seule question qui reste est le nombre de tenons.
    plancher = mosaic.palette_floor(
        imaging.resample_box(image, reglages.studs, hauteur), palette)
    verdict = ("excellent" if par_tuile[0] < 6
               else "correct" if par_tuile[0] < 12 else "palette insuffisante")
    marge = par_tuile[0] - plancher
    journal.append((
        "info",
        f"  palette : plancher a {plancher:.1f} delta E — "
        + ("la quantification l'atteint, aucun choix de couleur ne fera mieux. "
           "Plus de finesse ne s'obtient qu'en augmentant le nombre de tenons"
           if marge < 0.25 else
           f"la quantification est a {marge:.1f} au-dessus"),
    ))
    journal.append((
        "info",
        f"fidelite: {par_tuile[0]:.1f} delta E par tuile ({verdict})"
        f" | {tonal[0]:.1f} moyen et {tonal[1]:.1f} au pire sur la justesse tonale",
    ))
    pages = fascicule.count(b"/Type /Page /Parent")
    journal.append((
        "info",
        f"livre   : {len(nomenclature)} lots a commander, {len(plan.steps)} etapes, "
        f"notice.pdf de {pages} pages ({len(fascicule) // 1024} Ko)",
    ))

    return Resultat(
        fichiers=fichiers,
        journal=tuple(journal),
        mesures={
            "studs_x": reglages.studs,
            "studs_y": hauteur,
            "pieces": a_controler.part_count,
            "tuiles": mosaique.tile_count,
            "tenons": mosaique.stud_count,
            "lots": len(nomenclature),
            "etapes": len(plan.steps),
            "pages": pages,
            "delta_e": par_tuile[0],
            "plancher": plancher,
            "verdict": verdict,
            "tonal_moyen": tonal[0],
            "tonal_pire": tonal[1],
            "liaisons": liaisons,
            "sections": (len(assemblage.sections) if assemblage else 0),
            "couleurs": len(palette),
            "relief": reglages.relief,
            "provenance_relief": provenance,
            "largeur_mm": ldu_to_mm(porteur.outer_x * 20),
            "hauteur_mm": ldu_to_mm(porteur.outer_y * 20),
            "image_largeur_mm": ldu_to_mm(reglages.studs * 20),
            "image_hauteur_mm": ldu_to_mm(hauteur * 20),
            "cadre": reglages.cadre,
            **commande,
            "cadre_pieces": porteur.frame_count,
        },
    )
