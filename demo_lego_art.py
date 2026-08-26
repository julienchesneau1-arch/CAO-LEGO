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
    if donnees[:2] == b"P6":
        return bfk.read_ppm(donnees)
    raise SystemExit(f"format non reconnu : {chemin.name} (PNG ou PPM binaire attendus)")


def charger_palette(chemin: pathlib.Path | None) -> bfk.Palette:
    if chemin is None:
        print(
            "  palette : PROVISOIRE (12 couleurs recopiees a la main).\n"
            "            Fournir --ldconfig LDConfig.ldr pour la palette officielle.",
            file=sys.stderr,
        )
        return bfk.PROVISIONAL_PALETTE
    palette = bfk.load_ldconfig(chemin.read_text(encoding="utf-8", errors="replace"))
    print(f"  palette : {len(palette)} couleurs importees de {chemin.name}")
    return palette


def main() -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("image", type=pathlib.Path)
    analyseur.add_argument("--studs", type=int, default=48, help="cote en tenons")
    analyseur.add_argument("--sortie", type=pathlib.Path, default=pathlib.Path("resultat"))
    analyseur.add_argument("--ldconfig", type=pathlib.Path, default=None)
    analyseur.add_argument("--par-etape", type=int, default=24)
    options = analyseur.parse_args()

    image = charger_image(options.image)
    print(f"image   : {image.width} x {image.height} pixels")
    palette = charger_palette(options.ldconfig)

    depart = time.perf_counter()
    mosaique = bfk.mosaic.from_image(image, palette, options.studs, options.studs)
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
        nom_couleur = next(
            (c.name for c in palette if c.code == ligne.color_id), str(ligne.color_id)
        )
        lignes.append(
            f'{ligne.design_id},"{ligne.name}",{ligne.color_id},'
            f'"{nom_couleur}",{ligne.quantity}'
        )
    (options.sortie / "liste_de_course.csv").write_text("\n".join(lignes) + "\n")

    plan = bfk.plan_build(
        mosaique.placed_parts, etat.graph, mosaique.instances, options.par_etape
    )
    if not plan.validate_dag():  # pragma: no cover - la portance l'interdit
        print("plan de montage cyclique : non livre", file=sys.stderr)
        return 1
    (options.sortie / "notice.txt").write_text(bfk.render_text(plan) + "\n")

    (options.sortie / "modele.json").write_text(
        bfk.dumps_model(mosaique.placed_parts, mosaique.geometries, mosaique.instances)
    )

    print(f"livre   : {len(nomenclature)} references, {len(plan.steps)} etapes")
    print(f"          -> {options.sortie}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
