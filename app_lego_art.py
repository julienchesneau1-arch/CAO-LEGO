#!/usr/bin/env python3
"""BrickForge — l'atelier, dans le navigateur.

    python3 app_lego_art.py

Puis ouvrir http://127.0.0.1:8000 et deposer une photo.

Cette commande n'est qu'un lanceur. L'interface est dans `bfk001/webapp.py`, et
elle appelle exactement la meme chaine que `demo_lego_art.py` — il n'y a qu'un
seul calcul dans ce depot, deux facades le presentent.

Le serveur ecoute sur la boucle locale. Ce n'est pas un reglage timide : rien
ici n'authentifie qui que ce soit, et la fabrication d'une mosaique consomme
plusieurs secondes de calcul par requete. `--adresse 0.0.0.0` existe pour un
reseau domestique dont vous repondez, pas pour l'Internet.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import webbrowser

from bfk001 import bricklink, pickabrick
from bfk001.pipeline import palette_utilisable
from bfk001.webapp import Atelier, creer_serveur


def main() -> int:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--port", type=int, default=8000)
    analyseur.add_argument("--adresse", default="127.0.0.1",
                           help="boucle locale par defaut, et c'est voulu")
    analyseur.add_argument("--ldconfig", type=pathlib.Path, default=None,
                           help="palette officielle LDraw ; cherchee toute "
                                "seule aux emplacements usuels sans cela")
    analyseur.add_argument(
        "--bricklink", type=pathlib.Path, default=None,
        help="table ou export de couleurs BrickLink. Donnee ici une fois pour "
             "toutes, chaque oeuvre fabriquee repart avec sa commande.")
    analyseur.add_argument(
        "--elements", type=pathlib.Path, default=None,
        help="catalogue d'element ids, pour la commande LEGO Pick a Brick.")
    analyseur.add_argument(
        "--elements-couleurs", type=pathlib.Path, default=None,
        help="table « id, nom » des couleurs de ce catalogue, quand il ne "
             "designe les siennes que par un numero.")
    analyseur.add_argument("--sans-navigateur", action="store_true")
    options = analyseur.parse_args()

    complete, note = palette_utilisable(
        [str(options.ldconfig)] if options.ldconfig else None
    )
    print(note[1], file=sys.stderr if note[0] == "alerte" else sys.stdout)
    palette = complete if note[0] == "alerte" else complete.solids_only()
    # Les catalogues de commande sont ceux de l'installation. Une erreur ici
    # arrete le lanceur : mieux vaut la voir au demarrage que decouvrir, apres
    # avoir fabrique une oeuvre, qu'aucune commande n'en sort.
    table = None
    if options.bricklink:
        table, orphelines = bricklink.read_color_map(
            options.bricklink.read_text(), complete)
        print(f"couleurs : {len(table)} correspondances BrickLink"
              + (f", {len(orphelines)} sans equivalent" if orphelines else ""))
    elements = None
    if options.elements:
        noms = (pickabrick.read_color_names(
            options.elements_couleurs.read_text())
            if options.elements_couleurs else None)
        elements = pickabrick.read_elements(options.elements.read_text(), noms)
        print(f"elements : {len(elements)} references LEGO")

    atelier = Atelier(palette=palette, palette_complete=complete,
                      note_palette=note,
                      table_bricklink=table, table_elements=elements)

    serveur = creer_serveur(options.adresse, options.port, atelier)
    adresse = f"http://{options.adresse}:{serveur.server_address[1]}"
    print(f"atelier : {adresse}")
    print("          Ctrl-C pour arreter.")
    if not options.sans_navigateur:
        try:
            webbrowser.open(adresse)
        except Exception:  # pragma: no cover - depend du poste
            pass
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\narrete.")
    finally:
        serveur.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
