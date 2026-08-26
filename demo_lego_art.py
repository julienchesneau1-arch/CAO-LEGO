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
    analyseur.add_argument("--tramage", choices=("adaptatif", "aucun", "complet"),
                           default="adaptatif",
                           help="melange de tuiles voisines la ou la palette manque")
    analyseur.add_argument("--lignes-par-page", type=int, default=4,
                           help="lignes de mosaique par page de la notice PDF")
    analyseur.add_argument("--hauteur", type=int, default=None,
                           help="hauteur en tenons (defaut : carre)")
    analyseur.add_argument("--couleurs", type=int, default=None,
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
    if options.couleurs:
        palette = palette.best_subset(pixels, options.couleurs)
        print(f"  palette reduite aux {len(palette)} meilleures couleurs pour cette image")

    depart = time.perf_counter()
    tramage = {"adaptatif": "adaptive", "aucun": False, "complet": True}[options.tramage]
    # L'image est deja au bon rapport : plus rien a rogner ici.
    mosaique = bfk.mosaic.from_image(
        image, palette, options.studs, hauteur, dither=tramage, fit="stretch"
    )
    print(
        f"modele  : {mosaique.part_count} pieces "
        f"({mosaique.tile_count} tuiles + substrat) en {time.perf_counter() - depart:.2f}s"
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
        f"livre   : {len(nomenclature)} references, {len(plan.steps)} etapes, "
        f"notice.pdf de {fascicule.count(b'/Type /Page /Parent')} pages "
        f"({len(fascicule) // 1024} Ko)"
    )
    print(f"          -> {options.sortie}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
