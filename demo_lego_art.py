#!/usr/bin/env python3
"""BrickForge — photo vers mosaique LEGO Art, en une commande.

    python3 demo_lego_art.py photo.png --studs 48 --sortie resultat/

Produit, dans le dossier de sortie :
    apercu.png            le rendu, une case par tuile
    liste_de_course.csv   la nomenclature, prete a importer
    notice.txt            le plan de montage, etape par etape
    modele.json           le modele, sans aucune liaison (l'oracle les re-emet)

Et surtout : le modele n'est ecrit QUE s'il passe les six invariants du noyau.
Une mosaique qui ne tiendrait pas ensemble n'est pas livree.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

import bfk001_kernel as bfk


def charger_image(chemin: pathlib.Path):
    """Rend l'image ET les octets d'origine.

    Les octets servent apres coup : un JPEG de mode portrait porte souvent la
    carte de profondeur mesuree par l'appareil, et elle n'est pas dans les
    pixels — elle est dans les entetes que le decodage jette.
    """
    donnees = chemin.read_bytes()
    if donnees[:8] == b"\x89PNG\r\n\x1a\n":
        return bfk.read_png(donnees), donnees
    if donnees[:2] == b"\xff\xd8":
        # Decodage au huitieme : pour une mosaique de 48 tenons, reconstruire
        # les douze millions de pixels d'origine serait du travail jete.
        return bfk.read_jpeg_eighth(donnees), donnees
    if donnees[:2] == b"P6":
        return bfk.read_ppm(donnees), donnees
    raise SystemExit(f"format non reconnu : {chemin.name} (JPEG, PNG ou PPM)")


def carte_de_relief(image, origine, cadrage, brut, options, hauteur):
    """Les elevations, par la source la plus fiable disponible.

    Trois sources, dans cet ordre, et l'ordre n'est pas arbitraire : il va de
    la profondeur MESUREE a la convention.

    1. `--carte-profondeur` : une carte fournie. Un estimateur monoculaire
       (MiDaS, Depth Anything, Marigold) en produit d'excellentes, hors de ce
       depot, avec un reseau qu'il serait absurde d'embarquer ici.
    2. La carte EMBARQUEE dans le JPEG, si le telephone en a ecrit une. Le mode
       portrait mesure la profondeur et beaucoup d'appareils la deposent dans
       le fichier. C'est de la mesure, pas une convention.
    3. La clarte de la photo. La convention du camee, celle du bas-relief.

    On dit toujours laquelle a servi : un relief juste et un relief plausible
    se ressemblent, et seule la provenance les distingue.

    `image` est la photo DEJA ROGNEE, `origine` celle d'avant le rognage, et
    `cadrage` la position de la fenetre. Les trois sont necessaires, et l'avoir
    oublie etait un defaut : une carte de profondeur doit subir EXACTEMENT le
    meme rognage que la photo. Cablee sur la photo rognee et etiree, elle
    decrivait une autre scene — le controle de proportions refusait toute photo
    qui n'etait pas deja au format de l'oeuvre, c'est-a-dire presque toutes.
    """
    if options.carte_profondeur:
        carte = bfk.read_depth_map(
            pathlib.Path(options.carte_profondeur).read_bytes())
        return bfk.heights_from_depth(
            carte, origine, options.studs, hauteur, options.relief,
            near_is_bright=not options.profondeur_inversee,
            fit="crop", offset=cadrage,
        ), (f"carte de profondeur fournie ({carte.width}x{carte.height}) — "
            "profondeur MESUREE")

    if brut[:2] == b"\xff\xd8":
        try:
            carte = bfk.embedded_depth(brut)
        except bfk.NoEmbeddedDepth:
            pass
        else:
            return bfk.heights_from_depth(
                carte, origine, options.studs, hauteur, options.relief,
                near_is_bright=not options.profondeur_inversee,
                fit="crop", offset=cadrage,
            ), (f"carte EMBARQUEE dans le JPEG ({carte.width}x{carte.height}) "
                "— profondeur MESUREE par l'appareil")

    # Le relief se lit sur la PHOTO, jamais sur la grille : ni palette, ni
    # tramage. Le tramage est un bruit que l'oeil fond dans les couleurs et
    # qu'il ne fond jamais dans les hauteurs (voir `relief_from_image`).
    return bfk.mosaic.relief_from_image(
        image, options.studs, hauteur, options.relief,
        thresholds=options.seuils, fit="stretch"
    ), "CONVENTION du bas-relief, clair = haut — aucune profondeur mesuree"


def charger_palette(chemin: pathlib.Path | None) -> bfk.Palette:
    """Palette officielle si on la trouve, provisoire sinon — et on le dit.

    Le fichier est cherche aux emplacements ou LDraw, LeoCAD et BrickLink
    Studio le deposent : quiconque construit vraiment en LEGO l'a deja sur son
    disque, et n'a donc aucun drapeau a fournir.
    """
    complete, provenance = bfk.load_best_palette(
        [str(chemin)] if chemin is not None else None
    )
    if provenance.startswith("provisoire"):
        print(
            "  palette : PROVISOIRE (12 couleurs recopiees a la main).\n"
            "            LDConfig.ldr introuvable. Il est livre avec LDraw,\n"
            "            LeoCAD et BrickLink Studio ; --ldconfig CHEMIN sinon.\n"
            "            La palette officielle divise l'ecart par deux.",
            file=sys.stderr,
        )
        return complete
    # Filtre indispensable : le fichier officiel contient les transparentes, les
    # chromees, les nacrees, les caoutchouc et deux marqueurs internes au format.
    # Une liste de course qui les contient est incommandable.
    commandables = complete.solids_only()
    print(
        f"  palette : {len(complete)} couleurs lues dans {provenance}, "
        f"{len(commandables)} commandables en tuile"
    )
    return commandables


def nom_couleur(palette, code: int) -> str:
    for couleur in palette:
        if couleur.code == code:
            return couleur.name
    return str(code)


def main() -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("image", type=pathlib.Path)
    analyseur.add_argument("--studs", type=int, default=48, help="cote en tenons")
    analyseur.add_argument("--sortie", type=pathlib.Path, default=pathlib.Path("resultat"))
    analyseur.add_argument("--ldconfig", type=pathlib.Path, default=None)
    analyseur.add_argument("--par-etape", type=int, default=24)
    analyseur.add_argument("--cadrage", default="auto",
                           help="position de la fenetre de recadrage : un nombre "
                                "de 0 a 1, ou « auto » — la fenetre retenant le "
                                "plus de detail. « auto » vaut mieux qu'un "
                                "centrage aveugle, il ne vaut pas un regard.")
    analyseur.add_argument("--tramage",
                           choices=("auto", "adaptatif", "aucun", "complet"),
                           default="auto",
                           help="melange de tuiles voisines la ou la palette manque")
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
             "n'employez ce drapeau que si le relief sort en creux.")
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
             "reste en CSV : les codes couleur BrickLink ne se devinent pas.")
    analyseur.add_argument(
        "--codes-couleur", default=None,
        help="restreindre a ces codes LDraw, separes par des virgules. Le "
             "programme ne connait ni les prix ni les stocks : si vous savez "
             "ce que votre fournisseur a en tuile, dites-le ici et toute "
             "l'optimisation se fera a l'interieur de cette contrainte.")
    analyseur.add_argument("--tolerance", type=float, default=1.0,
                           help="avec --couleurs auto : ecart en delta E qu'on "
                                "accepte de perdre pour economiser un sachet")
    analyseur.add_argument("--couleurs", default=None,
                           help="limiter la mosaique aux N meilleures couleurs")
    options = analyseur.parse_args()

    image, brut = charger_image(options.image)
    print(f"image   : {image.width} x {image.height} pixels")
    palette = charger_palette(options.ldconfig)

    # Sans consigne, la hauteur suit les PROPORTIONS DE LA PHOTO : rien n'est
    # rogne, rien n'est etire. Demander une hauteur, c'est demander un cadrage.
    if options.hauteur:
        hauteur = options.hauteur
    else:
        hauteur = max(1, round(options.studs * image.height / image.width))
        if hauteur != options.studs:
            print(
                f"  cadrage : {options.studs} x {hauteur} tenons, "
                f"proportions de la photo conservees "
                f"(--hauteur {options.studs} pour un carre, la photo sera rognee)"
            )
    cadrage = options.cadrage
    if cadrage != "auto":
        try:
            cadrage = float(cadrage)
        except ValueError:
            print("--cadrage attend un nombre de 0 a 1 ou « auto »", file=sys.stderr)
            return 2
    if cadrage == "auto" and image.width / image.height != options.studs / hauteur:
        cadrage = bfk.imaging.attentional_offset(image, options.studs / hauteur)
        print(f"  cadrage : fenetre placee a {cadrage:.2f} (detail maximal)")
    if cadrage == "auto":
        # Les proportions coincident deja : le rognage ne fait rien et la
        # position de la fenetre n'a aucun effet. La fixer permet de la
        # transmettre telle quelle a la carte de profondeur.
        cadrage = 0.5
    # L'originale est conservee : une carte de profondeur doit subir le MEME
    # rognage, et le refaire depuis la photo deja rognee serait le refaire deux
    # fois.
    origine = image
    image = bfk.crop_to_ratio(image, options.studs / hauteur, cadrage)

    # En dessous de deux pixels par tenon, il n'y a plus de moyenne : chaque
    # tuile prend la couleur d'un pixel a peu pres au hasard dans sa zone. Le
    # rendu devient bruite, et aucun reglage de palette n'y changera rien.
    # Mesure : le decodage JPEG au huitieme ne coute que ~0,5 delta E tant
    # qu'on reste au-dessus de ce seuil (docs/ZONES_DOMBRE.md, section 5.31).
    par_tenon = min(image.width / options.studs, image.height / hauteur)
    if par_tenon < 2.0:
        print(
            f"  ATTENTION — {par_tenon:.1f} pixel(s) par tenon seulement.\n"
            f"            L'image cadree fait {image.width} x {image.height} pour "
            f"une mosaique de {options.studs} x {hauteur} tenons.\n"
            f"            Sous 2 px/tenon il n'y a plus de moyenne : le rendu "
            f"sera bruite.\n"
            f"            Fournir une photo plus grande, ou reduire --studs a "
            f"{max(1, int(image.width // 2))}.",
            file=sys.stderr,
        )
    reduite = bfk.resample_box(image, options.studs, hauteur)
    pixels = [
        reduite.pixel(x, y) for y in range(hauteur) for x in range(options.studs)
    ]

    manques = bfk.gap_report(pixels, palette)
    if manques:
        print("  ATTENTION — couleurs que cette photo reclame et que la palette n'a pas :")
        for manque in manques[:4]:
            print(
                f"      {manque.hex}  {manque.share * 100:4.1f}% des tuiles  "
                f"-> {manque.best_available.name} a {manque.error:.0f} delta E"
            )
        if len(palette) < 40:
            print("      La palette officielle corrige la plus grande part de l'ecart.")

    palette_complete = palette
    if options.codes_couleur:
        voulus = [int(c) for c in options.codes_couleur.replace(" ", "").split(",") if c]
        palette = palette.restricted_to(voulus)
        absents = set(voulus) - {c.code for c in palette}
        print(f"  palette restreinte a {len(palette)} couleurs imposees"
              + (f" ({len(absents)} codes inconnus ignores)" if absents else ""))

    if options.couleurs == "auto":
        complete = palette
        palette, retenu, meilleur = bfk.mosaic.cheapest_palette(
            image, palette, options.studs, hauteur, tolerance=options.tolerance
        )
        if len(palette) == len(complete):
            print(
                f"  palette gardee entiere ({len(complete)} couleurs) : aucune "
                "reduction ne coute moins cher a cette tolerance. Reduire la "
                "palette elargit les ecarts, ce qui declenche le tramage, ce "
                "qui brise les suites et multiplie les pieces."
            )
        else:
            print(
                f"  palette reduite a {len(palette)} couleurs sur {len(complete)} : "
                f"{retenu.tiles} tuiles et {retenu.lots} lots au lieu de "
                f"{meilleur.tiles} et {meilleur.lots}, en abandonnant "
                f"{max(0.0, retenu.tonal_mean - meilleur.tonal_mean):.2f} delta E "
                "de justesse tonale"
            )
    elif options.couleurs:
        palette = palette.best_subset(pixels, int(options.couleurs))
        print(f"  palette reduite aux {len(palette)} meilleures couleurs pour cette image")

    depart = time.perf_counter()
    tramage = {"auto": "auto", "adaptatif": "adaptive",
               "aucun": False, "complet": True}[options.tramage]
    # L'image est deja au bon rapport : plus rien a rogner ici.
    jeux = {
        "minimal": bfk.mosaic.TILE_SET_MINIMAL,
        "standard": bfk.mosaic.TILE_SET_STANDARD,
        "large": bfk.mosaic.TILE_SET_LARGE,
        "art": bfk.mosaic.TILE_SET_ART,
    }
    grille = bfk.mosaic.quantize(
        image, palette, options.studs, hauteur, tramage, "stretch"
    )
    # Le relief se lit sur la PHOTO, jamais sur `grille` : ni palette, ni
    # tramage. Le tramage est un bruit que l'oeil fond dans les couleurs et
    # qu'il ne fond jamais dans les hauteurs (voir `relief_from_image`).
    elevations, provenance = (
        carte_de_relief(image, origine, cadrage, brut, options, hauteur)
        if options.relief else (None, "")
    )
    mosaique = bfk.mosaic.build(
        grille, tiles=jeux[options.references], heights=elevations
    )
    if options.relief:
        plateaux = bfk.mosaic.relief_plateaus(elevations)
        clous = bfk.mosaic.relief_speckle(elevations)
        rendement = bfk.mosaic.relief_edge_alignment(
            elevations, image, fit="stretch")
        hauteurs = sorted({v for ligne in elevations for v in ligne})
        print(
            f"  relief  : {options.relief} etage(s), "
            f"{bfk.ldu_to_mm(options.relief * 8):.1f} mm d'epaisseur"
        )
        print(f"            source : {provenance}")
        # Le seuil est un repere de lecture, pas une constante mesuree : au-dela
        # de 1 % de tours isolees, les bandes de niveau sont devenues plus fines
        # qu'un tenon et le relief se lit comme du grain. Il se compte en PART
        # des tenons et non des plateaux : a resolution double, quatre etages
        # donnent deux fois plus de plateaux pour moitie moins de bruit.
        taux = clous / (options.studs * hauteur)
        print(
            f"            {len(plateaux)} plateaux (le plus grand : "
            f"{plateaux[0]} tenons), {clous} case(s) isolee(s)"
            + (f" — {100 * taux:.1f} % de tours isolees : le relief se fragmente,"
               " moins d'etages ou plus de tenons" if taux > 0.01 else "")
        )
        print(
            f"            rendement des marches {rendement:.2f} sur 1 — part du "
            "contraste de la photo que les marches exploitent"
        )
        if len(hauteurs) < options.relief + 1:
            print(
                f"            ATTENTION : {options.relief} etages demandes mais "
                f"seules les hauteurs {hauteurs} servent. Les etages inutilises "
                "coutent leurs plates sans rien relever."
            )
    sans_fusion = mosaique.stud_count
    economie = 100 * (1 - mosaique.tile_count / sans_fusion)
    print(
        f"modele  : {mosaique.part_count} pieces "
        f"({mosaique.tile_count} tuiles + substrat) en {time.perf_counter() - depart:.2f}s"
    )
    print(
        f"  fusion  : {mosaique.tile_count} tuiles au lieu de {sans_fusion} "
        f"({economie:.0f} % de pieces en moins), couleurs inchangees"
    )
    if economie > 1:
        print(
            "            mais les joints changent : appareil decale au lieu de "
            "la grille uniforme des sets LEGO Art. Voir apercu_joints.png ; "
            "--references minimal rend la grille."
        )

    tolerance = bfk.LEGO_TOLERANCE
    recherche = bfk.LatticeSearchApproximation()
    depart = time.perf_counter()
    etat = bfk.assemble(mosaique.placed_parts, tolerance, search=recherche)
    liaisons = sum(len(bonds) for _, _, bonds in etat.graph.edges)

    violations = (
        bfk.check_h2_collision(mosaique.placed_parts, mosaique.geometries)
        + bfk.check_h3_authority_integrity(etat.graph)
        + bfk.check_h4_floating(
            etat.graph,
            bfk.founded_part_ids(mosaique.placed_parts, mosaique.geometries),
        )
        + bfk.check_h5_disconnected(etat.graph)
        + bfk.check_h6_foundation(mosaique.placed_parts, mosaique.geometries)
    )
    print(
        f"controle: {liaisons} liaisons, {len(violations)} violations "
        f"en {time.perf_counter() - depart:.2f}s"
    )
    if violations:
        for violation in violations[:10]:
            print(f"   {violation.invariant} : {violation.detail}", file=sys.stderr)
        print("modele NON livre : il ne tiendrait pas ensemble.", file=sys.stderr)
        return 1

    options.sortie.mkdir(parents=True, exist_ok=True)
    if options.relief:
        (options.sortie / "apercu_relief.png").write_bytes(
            bfk.write_png(bfk.mosaic.preview(mosaique, scale=8, relief=True))
        )
    (options.sortie / "apercu_joints.png").write_bytes(
        bfk.write_png(bfk.mosaic.preview(mosaique, scale=12, seams=True))
    )
    (options.sortie / "apercu.png").write_bytes(
        bfk.write_png(bfk.mosaic.preview(mosaique, scale=8))
    )

    nomenclature = bfk.bill_of_materials(mosaique.instances, mosaique.placed_parts)
    lignes = ["design_id,nom,code_couleur,couleur,quantite"]
    for ligne in sorted(nomenclature, key=lambda l: -l.quantity):
        lignes.append(
            f'{ligne.design_id},"{ligne.name}",{ligne.color_id},'
            f'"{nom_couleur(palette_complete, ligne.color_id)}",{ligne.quantity}'
        )
    (options.sortie / "liste_de_course.csv").write_text("\n".join(lignes) + "\n")

    if options.bricklink:
        table = bfk.load_color_map(options.bricklink.read_text())
        try:
            (options.sortie / "commande_bricklink.xml").write_text(
                bfk.dumps_wanted_list(nomenclature, table, name=options.image.stem)
            )
            print(
                f"  commande BrickLink : {len(nomenclature)} lots, "
                f"{sum(l.quantity for l in nomenclature)} pieces, prete a l'envoi"
            )
        except bfk.UnmappedColors as manque:
            print(f"  commande BrickLink NON produite — {manque}", file=sys.stderr)

    plan = bfk.plan_build(
        mosaique.placed_parts, etat.graph, mosaique.instances, options.par_etape
    )
    if not plan.validate_dag():  # pragma: no cover - la portance l'interdit
        print("plan de montage cyclique : non livre", file=sys.stderr)
        return 1
    (options.sortie / "notice.txt").write_text(bfk.render_text(plan) + "\n")

    fascicule = bfk.build_booklet(
        mosaique,
        plan,
        nomenclature,
        palette=palette_complete,
        title=options.image.stem.replace("_", " ").title(),
        rows_per_page=options.lignes_par_page,
    )
    (options.sortie / "notice.pdf").write_bytes(fascicule)

    (options.sortie / "modele.ldr").write_text(
        bfk.dumps_ldr(
            mosaique.placed_parts, mosaique.instances, options.image.stem
        )
    )
    (options.sortie / "modele.json").write_text(
        bfk.dumps_model(mosaique.placed_parts, mosaique.geometries, mosaique.instances)
    )

    par_tuile = bfk.mosaic.fidelity(mosaique.grid, image, 1)
    tonal = bfk.mosaic.fidelity(mosaique.grid, image, 4)
    print(
        f"fidelite: {par_tuile[0]:.1f} delta E par tuile "
        f"({'excellent' if par_tuile[0] < 6 else 'correct' if par_tuile[0] < 12 else 'palette insuffisante'})"
        f" | {tonal[0]:.1f} moyen et {tonal[1]:.1f} au pire sur la justesse tonale"
    )
    print(
        f"livre   : {len(nomenclature)} lots a commander, {len(plan.steps)} etapes, "
        f"notice.pdf de {fascicule.count(b'/Type /Page /Parent')} pages "
        f"({len(fascicule) // 1024} Ko)"
    )
    print(f"          -> {options.sortie}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
