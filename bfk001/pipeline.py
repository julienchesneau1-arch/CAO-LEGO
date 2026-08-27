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

from . import (bricklink, imaging, instructions, jpeg, ldraw, mosaic, palette
               as palette_module)
from .booklet import build_booklet
from .catalog import bill_of_materials
from .depth import NoEmbeddedDepth, embedded_depth, heights_from_depth, read_depth_map
from .panels import build_assembly
from .imaging import Image, crop_to_ratio, read_png, read_ppm, resample_box, write_png
from .lego import LEGO_TOLERANCE, ldu_to_mm
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
    lignes_par_page: int = 4
    par_etape: int = 24
    titre: str = "mosaique"
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
        if self.relief < 0:
            raise ValueError("un nombre d'etages est positif")
        if self.references not in JEUX_DE_TUILES:
            raise ValueError(f"references vaut {' ou '.join(JEUX_DE_TUILES)}")
        if self.tramage not in TRAMAGES:
            raise ValueError(f"tramage vaut {' ou '.join(TRAMAGES)}")
        if self.seuils not in ("otsu", "uniform"):
            raise ValueError("seuils vaut 'otsu' ou 'uniform'")
        if self.sections < 0:
            raise ValueError("un cote de section est positif")


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
    return mosaic.relief_from_image(
        image, reglages.studs, hauteur, reglages.relief,
        thresholds=reglages.seuils, fit="stretch",
    ), "CONVENTION du bas-relief, clair = haut — aucune profondeur mesuree"


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
    grille = mosaic.quantize(
        image, palette, reglages.studs, hauteur, TRAMAGES[reglages.tramage],
        "stretch",
    )
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
    mosaique = mosaic.build(
        grille, tiles=JEUX_DE_TUILES[reglages.references], heights=elevations
    )
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
        if len(hauteurs) < reglages.relief + 1:
            journal.append((
                "alerte",
                f"            ATTENTION : {reglages.relief} etages demandes mais "
                f"seules les hauteurs {hauteurs} servent. Les etages inutilises "
                "coutent leurs plates sans rien relever.",
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

    if reglages.relief:
        fichiers["apercu_relief.png"] = write_png(
            mosaic.preview(mosaique, scale=8, relief=True))
    fichiers["apercu_joints.png"] = write_png(
        mosaic.preview(mosaique, scale=12, seams=True))
    fichiers["apercu.png"] = write_png(mosaic.preview(mosaique, scale=8))

    nomenclature = bill_of_materials(a_controler.instances,
                                     a_controler.placed_parts)
    lignes = ["design_id,nom,code_couleur,couleur,quantite"]
    for ligne in sorted(nomenclature, key=lambda l: -l.quantity):
        lignes.append(
            f'{ligne.design_id},"{ligne.name}",{ligne.color_id},'
            f'"{_nom_couleur(palette_complete, ligne.color_id)}",{ligne.quantity}'
        )
    fichiers["liste_de_course.csv"] = ("\n".join(lignes) + "\n").encode("utf-8")

    if table_bricklink:
        try:
            fichiers["commande_bricklink.xml"] = bricklink.dumps_wanted_list(
                nomenclature, table_bricklink, name=reglages.titre
            ).encode("utf-8")
        except bricklink.UnmappedColors as manque:
            journal.append((
                "alerte", f"  commande BrickLink NON produite — {manque}"))
        else:
            journal.append((
                "info",
                f"  commande BrickLink : {len(nomenclature)} lots, "
                f"{sum(l.quantity for l in nomenclature)} pieces, prete a l'envoi",
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
    verdict = ("excellent" if par_tuile[0] < 6
               else "correct" if par_tuile[0] < 12 else "palette insuffisante")
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
            "verdict": verdict,
            "tonal_moyen": tonal[0],
            "tonal_pire": tonal[1],
            "liaisons": liaisons,
            "sections": (len(assemblage.sections) if assemblage else 0),
            "couleurs": len(palette),
            "relief": reglages.relief,
            "provenance_relief": provenance,
            "largeur_mm": ldu_to_mm(reglages.studs * 20),
            "hauteur_mm": ldu_to_mm(hauteur * 20),
        },
    )
