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


def charger_image(chemin: pathlib.Path) -> bfk.Image:
    donnees = chemin.read_bytes()
    if donnees[:8] == b"\x89PNG\r\n\x1a\n":
        return bfk.read_png(donnees)
    if donnees[:2] == b"\xff\xd8":
        # Decodage au huitieme : pour une mosaique de 48 tenons, reconstruire
        # les douze millions de pixels d'origine serait du travail jete.
        return bfk.read_jpeg_eighth(donnees)
    if donnees[:2] == b"P6":
        return bfk.read_ppm(donnees)
    raise SystemExit(f"format non reconnu : {chemin.name} (JPEG, PNG ou PPM)")


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
    analyseur.add_argument("--cadrage", type=float, default=0.5,
                           help="position de la fenetre de recadrage, de 0 a 1")
    analyseur.add_argument("--tramage",
                           choices=("auto", "adaptatif", "aucun", "complet"),
                           default="auto",
                           help="melange de tuiles voisines la ou la palette manque")
    analyseur.add_argument("--lignes-par-page", type=int, default=4,
                           help="lignes de mosaique par page de la notice PDF")
    analyseur.add_argument("--hauteur", type=int, default=None,
                           help="hauteur en tenons (defaut : carre)")
    analyseur.add_argument(
        "--references", choices=("minimal", "standard", "large"), default="standard",
        help="jeu de tuiles : minimal = 1x1 seule ; standard = 1x1, 1x2, 1x4 ; "
             "large = jusqu'a 1x8. Fusionner ne change rien au rendu et divise "
             "le nombre de pieces, mais multiplie les lots a commander.")
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

    image = charger_image(options.image)
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
    image = bfk.crop_to_ratio(image, options.studs / hauteur, options.cadrage)

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
    }
    mosaique = bfk.mosaic.from_image(
        image, palette, options.studs, hauteur, dither=tramage, fit="stretch",
        tiles=jeux[options.references],
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
