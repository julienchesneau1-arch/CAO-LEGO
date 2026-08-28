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

from bfk001.palette import PaletteRefusee, installer_palette
from bfk001.webapp import (DOSSIER_DEFAUT, Atelier, charger_installation,
                           creer_serveur)


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
    analyseur.add_argument(
        "--memoire", type=pathlib.Path, default=DOSSIER_DEFAUT,
        help=f"ou garder les catalogues d'une session a l'autre "
             f"(defaut : {DOSSIER_DEFAUT}). Ce qui y est ecrit n'est pas le "
             "catalogue d'origine mais ce qu'on en a retenu — quelques "
             "centaines de lignes verifiees.")
    analyseur.add_argument(
        "--sans-memoire", action="store_true",
        help="ne rien garder : les catalogues seront a redonner a chaque "
             "demarrage.")
    analyseur.add_argument(
        "--installer-palette", action="store_true",
        help="telecharge la palette officielle LDraw et l'installe une "
             "fois pour toutes, puis demarre.")
    analyseur.add_argument("--sans-navigateur", action="store_true")
    options = analyseur.parse_args()

    if options.installer_palette:
        try:
            chemin, installee = installer_palette()
            print(f"palette : {len(installee)} couleurs installees dans {chemin}")
        except PaletteRefusee as raison:
            print(raison, file=sys.stderr)
            return 3

    # Palette et catalogues sont ceux de l'INSTALLATION, et le lanceur heberge
    # les charge exactement de la meme facon : la lecture est donc ecrite une
    # seule fois, dans `webapp.charger_installation`.
    palette, complete, note, table, elements, lignes = charger_installation(
        options.ldconfig, options.bricklink, options.elements,
        options.elements_couleurs)
    for flux, texte in lignes:
        print(texte, file=sys.stderr if flux == "alerte" else sys.stdout)

    atelier = Atelier(palette=palette, palette_complete=complete,
                      note_palette=note,
                      table_bricklink=table, table_elements=elements,
                      dossier=None if options.sans_memoire else options.memoire)
    etat = atelier.etat_catalogues()
    if etat["elements"] or etat["bricklink"]:
        print("commande : "
              + ", ".join(filter(None, [
                  f"{etat['elements']['references']} references LEGO"
                  if etat["elements"] else None,
                  f"{etat['bricklink']['couleurs']} couleurs BrickLink"
                  if etat["bricklink"] else None])))
    else:
        print("commande : aucun catalogue — deposez-en un dans la page, "
              "« Catalogues de commande »")

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
