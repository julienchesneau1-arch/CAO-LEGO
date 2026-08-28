#!/usr/bin/env python3
"""BrickForge — le meme atelier, mais heberge.

    BFK_CLE=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))") \
      python3 heberger_lego_art.py

Le lanceur local (`app_lego_art.py`) sert un atelier sur la boucle locale :
un utilisateur, qui repond de sa machine, et rien a authentifier. Celui-ci
sert le meme atelier a des gens qu'on ne connait pas, ce qui n'est pas le
meme programme et ne s'obtient pas en changeant `--adresse`.

Ce qui change, et pourquoi
--------------------------
Une CLE. Sans elle l'atelier ne demarre pas. Le lien a partager la porte une
fois — `https://…/?cle=…` — le serveur pose un temoin, et la cle disparait de
la barre d'adresse. Ce n'est pas une formalite : au plafond, une seule requete
de quelques kilo-octets demande six minutes et demie de calcul et trois
giga-octets et demi de memoire. Sans cle, le premier venu prend la machine.

Un PLAFOND calcule, pas recopie. Celui du noyau — 250 000 tenons — dit ce que
la chaine tient sur une machine de developpement. Ici il est recalcule sur la
memoire que le conteneur a le droit de prendre et sur le temps qu'une page web
a le droit de mettre a repondre. Sur un giga-octet il tombe vers 190 tenons de
cote, ce qui reste quatre fois la surface d'un set LEGO Art officiel.

UN ATELIER PAR VISITEUR. Les catalogues de commande sont une propriete de
l'installation quand il n'y a qu'un utilisateur ; des qu'il y en a deux, le
catalogue depose par l'un changerait la liste de course de l'autre, et un
catalogue partiel la degraderait sans que personne comprenne pourquoi. Chaque
session a donc le sien, parti de celui de l'exploitant.

UNE SEULE FABRICATION A LA FOIS. Mesure : deux mosaiques fabriquees en
parallele prennent chacune deux fois plus longtemps et le debit total BAISSE —
la chaine est du Python pur. Une deuxieme place n'ajouterait donc rien qu'une
seconde pointe de memoire. Le deuxieme visiteur recoit un refus immediat et
dit, ce qui vaut mieux qu'une attente muette.

Reglages, par variable d'environnement — c'est ainsi que se configure un
conteneur, et cela evite d'ecrire une cle dans une ligne de commande que le
systeme garde :

    BFK_CLE            la cle. Obligatoire, seize caracteres au moins.
    PORT               pose par la plupart des hebergeurs. 8000 sinon.
    BFK_MEMOIRE_MO     force la memoire supposee, quand le cgroup ment.
    BFK_DUREE          secondes qu'une fabrication a le droit de prendre (60).
    BFK_CPU_PAR_TENON  secondes de calcul par tenon. Mesure au demarrage, en
                       deux secondes, si elle n'est pas donnee : la vitesse est
                       la seule chose qui change vraiment d'une machine a
                       l'autre — la memoire, elle, se reproduit a l'octet pres.
    BFK_SIMULTANEES    places de fabrication (1 — la mesure le dit).
    BFK_RELAIS         nombre de relais devant le serveur. 0 par defaut, et
                       tant qu'il vaut 0 `X-Forwarded-For` n'est PAS cru.
    BFK_SANS_TLS       met le temoin sans `Secure` : pour essayer en local,
                       jamais sur l'Internet.
    BFK_LDCONFIG       palette officielle LDraw, si elle n'est pas a sa place.
    BFK_BRICKLINK      table de couleurs BrickLink de l'installation.
    BFK_ELEMENTS       catalogue d'element ids de l'installation.
    BFK_ELEMENTS_COULEURS   sa table « id, nom », si besoin.

Ce que ce lanceur ne fait pas : le chiffrement. Le lien doit etre en HTTPS et
c'est l'hebergeur qui le termine.
"""

from __future__ import annotations

import os
import secrets
import sys
import time

from bfk001 import heberge
from bfk001.webapp import (Atelier, Resultats, charger_installation,
                           creer_serveur)


def _entier(nom: str, defaut: int) -> int:
    brut = os.environ.get(nom)
    if not brut:
        return defaut
    try:
        return int(brut)
    except ValueError:
        raise SystemExit(f"{nom} : nombre entier attendu, « {brut} » recu")


def _reel(nom: str, defaut: float) -> float:
    brut = os.environ.get(nom)
    if not brut:
        return defaut
    try:
        return float(brut)
    except ValueError:
        raise SystemExit(f"{nom} : nombre attendu, « {brut} » recu")


def main() -> int:
    cle = os.environ.get("BFK_CLE") or ""
    if len(cle) < 16:
        propose = secrets.token_urlsafe(24)
        print(
            "BFK_CLE manquante ou trop courte.\n\n"
            "Cet atelier ne s'ouvre pas sans cle, et ce n'est pas un exces de\n"
            "prudence : une seule requete peut y demander plusieurs minutes de\n"
            "calcul et plusieurs giga-octets de memoire. Posez celle-ci dans la\n"
            "configuration de l'hebergeur, une fois pour toutes :\n\n"
            f"    BFK_CLE={propose}\n\n"
            "Gardez-la : c'est elle qui est dans le lien a partager. La changer\n"
            "invalide les liens deja envoyes.",
            file=sys.stderr)
        return 2

    simultanees = _entier("BFK_SIMULTANEES", 1)
    duree = _reel("BFK_DUREE", heberge.DUREE_ACCEPTABLE)

    # La memoire par tenon est une propriete du LOGICIEL : refaite sur une
    # seconde machine, la mesure a rendu la meme colonne a l'octet pres. La
    # vitesse, non : la meme mesure y a ete 1,8 fois plus lente. Un plafond de
    # duree pose sur une constante serait donc faux de 80 % chez qui heberge.
    # On mesure ici, une fois, en deux secondes.
    cpu = _reel("BFK_CPU_PAR_TENON", 0.0)
    if cpu > 0:
        etalonnage = f"{cpu * 1000:.2f} ms/tenon (BFK_CPU_PAR_TENON)"
    else:
        depart = time.time()
        cpu = heberge.calibrer()
        etalonnage = (f"{cpu * 1000:.2f} ms/tenon, mesure ici en "
                      f"{time.time() - depart:.1f} s "
                      f"({cpu / heberge.CPU_PAR_TENON:.2f} x la machine de "
                      f"reference)")

    memoire_mo = _entier("BFK_MEMOIRE_MO", 0)
    if memoire_mo:
        memoire = memoire_mo * 1024 * 1024
        provenance = f"{memoire_mo} Mo (BFK_MEMOIRE_MO)"
    else:
        memoire = heberge.memoire_du_conteneur()
        if memoire is None:
            print("memoire du conteneur inconnue : posez BFK_MEMOIRE_MO.",
                  file=sys.stderr)
            return 2
        provenance = f"{memoire // (1024 * 1024)} Mo (cgroup)"

    par_memoire = heberge.plafond_par_memoire(memoire, simultanees)
    par_duree = heberge.plafond_par_duree(duree, simultanees, cpu)
    plafond = min(par_memoire, par_duree)
    if plafond < heberge.TENONS_PLANCHER:
        print(
            f"memoire : {provenance}\n"
            f"plafond calcule : {plafond} tenons, en dessous du plancher de "
            f"{heberge.TENONS_PLANCHER} ({int(heberge.TENONS_PLANCHER ** 0.5)} "
            "de cote).\n\n"
            "Cet atelier refuserait tout ce qu'on lui demande. Il faut un "
            "conteneur\nde plus de memoire — environ 512 Mo pour une mosaique "
            "de 126 de cote,\nun giga-octet pour 190 — ou moins de "
            "fabrications simultanees.",
            file=sys.stderr)
        return 2

    palette, complete, note, table, elements, lignes = charger_installation(
        os.environ.get("BFK_LDCONFIG"),
        os.environ.get("BFK_BRICKLINK"),
        os.environ.get("BFK_ELEMENTS"),
        os.environ.get("BFK_ELEMENTS_COULEURS"))
    for flux, texte in lignes:
        print(texte, file=sys.stderr if flux == "alerte" else sys.stdout)
    if note[0] == "alerte":
        print("          Hebergee, cette palette ne se rattrape pas depuis la "
              "page : installez\n          LDConfig.ldr en construisant "
              "l'image.", file=sys.stderr)

    # Un seul magasin de resultats pour tout le monde. Les jetons sont
    # imprevisibles, donc partager le magasin ne partage pas la lecture — mais
    # un magasin par visiteur multiplierait la borne par le nombre de
    # visiteurs, c'est-a-dire ne bornerait plus rien.
    magasin = Resultats(octets=max(64 * 1024 * 1024, int(memoire * 0.15)))

    def atelier_de_session() -> Atelier:
        """L'atelier d'un visiteur : la palette de l'exploitant, ses catalogues
        pour commencer, et AUCUN acces au disque — ce qu'il deposera ne changera
        que sa propre liste de course, et ne survivra pas a sa session."""
        return Atelier(palette=palette, palette_complete=complete,
                       note_palette=note, table_bricklink=table,
                       table_elements=elements, dossier=None, memoire=False,
                       plafond_tenons=plafond, resultats=magasin)

    hebergement = heberge.Hebergement(
        cle=cle,
        fabrique_atelier=atelier_de_session,
        plafond_tenons=plafond,
        simultanees=simultanees,
        relais=_entier("BFK_RELAIS", 0),
        securise=not os.environ.get("BFK_SANS_TLS"),
    )

    port = _entier("PORT", 8000)
    cote = int(plafond ** 0.5)
    print(f"memoire  : {provenance}")
    print(f"vitesse  : {etalonnage}")
    print(f"plafond  : {plafond} tenons (~{cote} x {cote}) — "
          f"{'la memoire' if par_memoire < par_duree else 'le temps de reponse'}"
          f" borne, {min(par_memoire, par_duree)} contre "
          f"{max(par_memoire, par_duree)}")
    print(f"chantier : {simultanees} fabrication"
          f"{'s' if simultanees > 1 else ''} a la fois")
    if not hebergement.securise:
        print("temoin   : SANS Secure (BFK_SANS_TLS) — essais locaux "
              "uniquement", file=sys.stderr)

    serveur = creer_serveur("0.0.0.0", port, atelier_de_session(), hebergement)
    print(f"atelier  : port {serveur.server_address[1]}, "
          f"lien a partager  https://VOTRE-DOMAINE/?cle={cle}")
    sys.stdout.flush()
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:      # pragma: no cover - depend du poste
        print("\narrete.")
    finally:
        serveur.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
