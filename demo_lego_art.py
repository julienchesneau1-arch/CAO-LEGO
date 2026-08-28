#!/usr/bin/env python3
"""BrickForge — photo vers mosaique LEGO Art, en une commande.

    python3 demo_lego_art.py photo.png --studs 48 --sortie resultat/

Produit, dans le dossier de sortie :
    apercu.png            le rendu, une case par tuile
    liste_de_course.csv   la nomenclature, prete a importer
    notice.txt            le plan de montage, etape par etape
    notice.pdf            le fascicule imprimable
    modele.ldr            le modele, ouvrable dans LDraw ou Studio
    modele.json           le modele, sans aucune liaison (l'oracle les re-emet)

Et surtout : le modele n'est ecrit QUE s'il passe les six invariants du noyau.
Une mosaique qui ne tiendrait pas ensemble n'est pas livree.

Cette commande n'est qu'une FACADE. Toute la chaine est dans
`bfk001/pipeline.py`, que l'interface web appelle a l'identique : deux facades,
une seule chaine, aucune divergence possible.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import bfk001_kernel as bfk
from bfk001.pipeline import (ModeleRefuse, Reglages, conseil_de_format,
                             lire_image, palette_utilisable, run)


def _installer() -> bool:
    """Installe la palette officielle. Rend False si ca n'a pas marche.

    Le depot n'embarque pas `LDConfig.ldr` — il appartient a LDraw.org et ne
    porte aucune mention de licence verifiable. L'installer sur la machine de
    qui le demande est autre chose que le redistribuer.
    """
    try:
        chemin, palette = bfk.installer_palette()
    except bfk.PaletteRefusee as raison:
        print(raison, file=sys.stderr)
        return False
    solides = sum(1 for couleur in palette if couleur.is_solid)
    print(f"palette : {len(palette)} couleurs installees dans {chemin}, "
          f"{solides} commandables en tuile")
    return True


def construire_analyseur() -> argparse.ArgumentParser:
    """Les options de la commande, isolees pour qu'un test puisse les lire.

    Elles vivaient dans `main`, ou rien ne pouvait les atteindre sans lancer
    une fabrication complete. Un drapeau qui n'arrive pas jusqu'aux `Reglages`
    n'existe pas pour l'utilisateur, et c'est exactement ce qui etait arrive a
    la convention du bas-relief.
    """
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("image", type=pathlib.Path)
    analyseur.add_argument("--studs", type=int, default=48, help="cote en tenons")
    analyseur.add_argument("--sortie", type=pathlib.Path, default=pathlib.Path("resultat"))
    analyseur.add_argument("--ldconfig", type=pathlib.Path, default=None)
    analyseur.add_argument(
        "--conseil-format", action="store_true",
        help="met quatre formats en balance avant de fabriquer : ce que chacun "
             "gagne en detail et ce qu'il coute en pieces. L'ecart par tuile ne "
             "repond pas a la question — il est borne par la palette et reste "
             "plat quand on triple la resolution. Compte une dizaine de "
             "secondes.")
    analyseur.add_argument(
        "--installer-palette", action="store_true",
        help="telecharge la palette officielle LDraw (159 couleurs, 80 "
             "commandables en tuile) et l'installe une fois pour toutes. "
             "Ce depot ne l'embarque pas : le fichier appartient a "
             "LDraw.org. Sans elle, la palette de secours en compte 12.")
    analyseur.add_argument("--par-etape", type=int, default=24)
    analyseur.add_argument("--cadrage", default="auto",
                           help="position de la fenetre de recadrage : un nombre "
                                "de 0 a 1, ou « auto » — la fenetre retenant le "
                                "plus de detail. « auto » vaut mieux qu'un "
                                "centrage aveugle, il ne vaut pas un regard.")
    analyseur.add_argument(
        "--tramage", choices=("auto", "adaptatif", "aucun", "complet"),
        default="aucun",
        help="melange de tuiles voisines la ou la palette manque. « aucun » "
             "par defaut, et c'est une decision MESUREE : sur six photos "
             "reelles, la version nette a toujours ete jugee meilleure ou "
             "equivalente. « auto » laisse le critere decider comme avant, "
             "« adaptatif » et « complet » l'imposent. La chaine dit toujours "
             "ce que le tramage aurait gagne et coute.")
    analyseur.add_argument("--lignes-par-page", type=int, default=4,
                           help="lignes de mosaique par page de la notice PDF")
    analyseur.add_argument("--hauteur", type=int, default=None,
                           help="hauteur en tenons (defaut : carre)")
    analyseur.add_argument(
        "--relief", type=int, default=0,
        help="etages de relief tires de la clarte (0 = oeuvre plate). Une "
             "CONVENTION de bas-relief : clair = haut. Une photo ne contient "
             "aucune profondeur ; un sujet sombre sur fond clair sortira en creux. "
             "Les hauteurs sont lues sur une grille NON tramee : un relief trame "
             "est un lit de clous. Au-dela de deux etages, augmentez --studs "
             "plutot que les etages.")
    analyseur.add_argument(
        "--carte-profondeur", default=None,
        help="carte de profondeur (PNG, PPM ou JPEG) a la place de la "
             "convention clair = haut. C'est la seule facon d'avoir un relief "
             "MESURE : une photo en couleurs ne contient aucune profondeur.")
    analyseur.add_argument(
        "--profondeur-inversee", action="store_true",
        help="la carte encode une DISTANCE (proche = sombre) et non une "
             "disparite. MiDaS et Depth Anything sortent une disparite : "
             "n'employez ce drapeau que si le relief sort en creux. Ne "
             "concerne QUE --carte-profondeur ; sans carte, voyez "
             "--relief-inverse.")
    analyseur.add_argument(
        "--relief-inverse", action="store_true",
        help="renverse la convention du bas-relief : sombre = haut. Sans "
             "carte de profondeur, le relief se lit sur la clarte, et sur un "
             "paysage la convention du camee fait SAILLIR LE CIEL devant le "
             "sol. Ce drapeau remet le ciel au fond. Sur un portrait, ne "
             "l'employez pas : le visage y est plus clair que le fond.")
    analyseur.add_argument(
        "--seuils", choices=("otsu", "uniform"), default="otsu",
        help="ou tombent les marches du relief : otsu = dans les creux de "
             "l'histogramme, la ou l'image se separe en regions ; uniform = "
             "en parts egales de clarte, ce qui pose les marches au milieu "
             "des degrades et peut payer des etages pour rien.")
    analyseur.add_argument(
        "--references", choices=("minimal", "standard", "large", "art"),
        default="standard",
        help="jeu de tuiles : minimal = 1x1 seule ; standard = 1x1, 1x2, 1x4 ; "
             "large = jusqu'a 1x8 ; art = tuiles RONDES comme les mosaiques "
             "LEGO Art, sans fusion possible donc au prix plein. Fusionner ne "
             "change aucune couleur mais change les joints.")
    analyseur.add_argument(
        "--bricklink", type=pathlib.Path, default=None,
        help="table « code LDraw, code BrickLink » (deux colonnes). Produit "
             "commande_bricklink.xml, uploadable tel quel. Sans elle la liste "
             "reste en CSV. Deux formats acceptes : la table a deux colonnes, "
             "ou l'export de couleurs telecharge depuis BrickLink — la "
             "correspondance se deduit alors du LEGOID que porte LDConfig.")
    analyseur.add_argument(
        "--elements", type=pathlib.Path, default=None,
        help="catalogue d'element ids — le numero qui designe un moule DANS "
             "UNE COULEUR. Produit commande_lego.csv, le CSV que le bouton "
             "« Upload list » de Pick a Brick attend. Ce numero est attribue, "
             "pas calcule : il faut un catalogue (celui de Rebrickable, celui "
             "de BrickLink, ou tout fichier portant element, piece et couleur).")
    analyseur.add_argument(
        "--elements-couleurs", type=pathlib.Path, default=None,
        help="table « id, nom » des couleurs de ce catalogue, quand il ne "
             "designe les siennes que par un numero (chez Rebrickable, "
             "colors.csv a cote de elements.csv). Sans elle un tel catalogue "
             "est refuse : un numero de couleur ne veut rien dire tant qu'on "
             "ignore de quel systeme il vient.")
    analyseur.add_argument(
        "--codes-couleur", default=None,
        help="restreindre a ces codes LDraw, separes par des virgules. Le "
             "programme ne connait ni les prix ni les stocks : si vous savez "
             "ce que votre fournisseur a en tuile, dites-le ici et toute "
             "l'optimisation se fera a l'interieur de cette contrainte.")
    analyseur.add_argument(
        "--debruitage", type=float, default=4.0,
        help="ecart en delta E tolere pour effacer une tuile isolee (0 pour "
             "n'en effacer aucune). Une tuile qui ne ressemble a aucune de ses "
             "voisines vient de la quantification, pas de la photo : elle coute "
             "une piece et brise la suite qui la traverse.")
    analyseur.add_argument(
        "--cadre", type=int, default=2,
        help="epaisseur du cadre en tenons (0 pour aucun). Le cadre ferme "
             "l'oeuvre, la fait lire comme un tableau, ceinture les sections "
             "quand elle est decoupee, et rend constructibles des formats "
             "etroits qui ne l'etaient pas.")
    analyseur.add_argument(
        "--cadre-couleur", type=int, default=0,
        help="code LDraw du cadre : 0 noir (defaut), 15 blanc, 70 brun "
             "rougeatre, 71 gris clair, 72 gris fonce.")
    analyseur.add_argument(
        "--sections", type=int, default=0,
        help="decouper l'oeuvre en sections de N tenons de cote. Chacune est "
             "un modele complet avec sa propre notice, batissable seule ; une "
             "couche de plates les reunit par-dessous. 0 : d'un seul tenant.")
    analyseur.add_argument("--tolerance", type=float, default=1.0,
                           help="avec --couleurs auto : ecart en delta E qu'on "
                                "accepte de perdre pour economiser un sachet")
    analyseur.add_argument("--couleurs", default=None,
                           help="limiter la mosaique aux N meilleures couleurs")
    return analyseur


def main() -> int:
    options = construire_analyseur().parse_args()

    if options.installer_palette and not _installer():
        return 3

    reglages = Reglages(
        studs=options.studs,
        hauteur=options.hauteur,
        relief=options.relief,
        references=options.references,
        tramage=options.tramage,
        couleurs=options.couleurs,
        tolerance=options.tolerance,
        cadrage=options.cadrage,
        seuils=options.seuils,
        codes_couleur=options.codes_couleur,
        profondeur_inversee=options.profondeur_inversee,
        relief_inverse=options.relief_inverse,
        lignes_par_page=options.lignes_par_page,
        par_etape=options.par_etape,
        titre=options.image.stem,
        sections=options.sections,
        debruitage=options.debruitage,
        cadre=options.cadre,
        cadre_couleur=options.cadre_couleur,
    )

    complete, ligne_palette = palette_utilisable(
        [str(options.ldconfig)] if options.ldconfig else None
    )
    palette = (complete if ligne_palette[0] == "alerte"
               else complete.solids_only())

    table = None
    if options.bricklink:
        # Deux formats circulent, et l'utilisateur n'a pas a savoir lequel il
        # tient : la table a deux colonnes, ou l'export de couleurs BrickLink.
        table, orphelines = bfk.bricklink.read_color_map(
            options.bricklink.read_text(), complete)
        print(f"  couleurs : {len(table)} correspondances BrickLink importees"
              + (f", {len(orphelines)} sans equivalent" if orphelines else ""))

    elements = None
    if options.elements:
        # `decompresser` : Rebrickable publie ses catalogues en .csv.gz, et
        # demander de decompresser avant de s'en servir est une etape de trop.
        noms = (bfk.pickabrick.read_color_names(bfk.pickabrick.decompresser(
            options.elements_couleurs.read_bytes()))
            if options.elements_couleurs else None)
        elements = bfk.pickabrick.read_elements(
            bfk.pickabrick.decompresser(options.elements.read_bytes()), noms,
            pieces=bfk.pickabrick.PIECES_UTILES)
        print(f"  elements : {len(elements)} references retenues"
              + (f", {elements.lignes_ecartees} hors des pieces employees ici"
                 if elements.lignes_ecartees else "")
              + (f", {elements.lignes_ignorees} ligne(s) illisible(s)"
                 if elements.lignes_ignorees else ""))

    if options.conseil_format:
        image = bfk.read_png(options.image.read_bytes()) \
            if options.image.suffix.lower() == ".png" \
            else lire_image(options.image.read_bytes())
        hauteur = options.hauteur or max(
            1, round(options.studs * image.height / image.width))
        print(f"  format        pieces   detail   gain   pieces par 0,1 de gain")
        precedent = None
        for etape in conseil_de_format(image, options.studs, hauteur,
                                       palette, reglages):
            if precedent is None:
                gain, cout = "", ""
            else:
                ecart = precedent["detail"] - etape["detail"]
                gain = f"{ecart:+5.2f}"
                cout = (f"{(etape['pieces'] - precedent['pieces']) / (ecart * 10):8.0f}"
                        if ecart > 0.001 else "       -")
            marque = " <-" if etape["studs_x"] == options.studs else "   "
            print(f"  {etape['studs_x']:3d}x{etape['studs_y']:<3d} "
                  f"{etape['largeur_cm']:3d}x{etape['hauteur_cm']:<3d}cm "
                  f"{etape['pieces']:6d}   {etape['detail']:5.2f}  {gain}  {cout}{marque}")
            precedent = etape
        print("  (detail : ecart a la photo mesure a finesse constante ; "
              "plus bas = plus fidele)")

    try:
        resultat = run(
            options.image.read_bytes(),
            reglages,
            palette=palette,
            palette_complete=complete,
            carte_profondeur=(pathlib.Path(options.carte_profondeur).read_bytes()
                              if options.carte_profondeur else None),
            table_bricklink=table,
            table_elements=elements,
            note_palette=ligne_palette,
        )
    except ValueError as raison:
        print(f"{options.image.name} : {raison}", file=sys.stderr)
        return 2
    except ModeleRefuse as refus:
        for violation in refus.violations[:10]:
            print(f"   {violation.invariant} : {violation.detail}", file=sys.stderr)
        print(refus, file=sys.stderr)
        return 1

    for flux, texte in resultat.journal:
        print(texte, file=sys.stderr if flux == "alerte" else sys.stdout)

    options.sortie.mkdir(parents=True, exist_ok=True)
    for nom, contenu in resultat.fichiers.items():
        chemin = options.sortie / nom
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_bytes(contenu)
    print(f"          -> {options.sortie}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
