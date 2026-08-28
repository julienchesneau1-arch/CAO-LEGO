"""Interface web locale : deposer une photo, recuperer la mosaique.

Le dernier point de la demande d'origine qui restait ouvert etait « mettre une
photo dans l'app ». Il n'y avait pas d'app : il y avait une commande.

Ce module en fait une, sans rien ajouter aux dependances — `http.server` et
`zipfile` sont dans la bibliotheque standard, la page est un seul fichier sans
ressource externe. Et surtout, il n'y a pas deux chaines : l'interface appelle
`pipeline.run`, exactement comme la commande. Deux facades, un seul calcul.

Choix de protocole. Le corps des requetes est du JSON, la photo en base64,
plutot que du multipart. Deux raisons : le module `cgi` qui savait analyser le
multipart est retire de Python 3.13, et un corps JSON se fabrique en trois
lignes dans un test — ce qui rend le trajet complet testable sans navigateur.
Le cout est un tiers de volume en plus, sans importance sur une boucle locale.

Le serveur ecoute sur 127.0.0.1 par defaut. Rien n'est servi depuis le disque :
tout ce qui sort d'ici a ete fabrique en memoire pendant la requete, ce qui
retire d'un coup toute la famille des traversees de chemin.
"""

from __future__ import annotations

import base64
import io
import json
import pathlib
import secrets
import threading
import zipfile
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote
from typing import Dict, Mapping, Optional, Tuple

from . import bricklink, pickabrick
from . import palette as palette_module
from .palette import Palette
from .pipeline import (ModeleRefuse, Reglages, conseil_de_format,
                       lire_image, palette_utilisable, run)

__all__ = ["PAGE", "Atelier", "servir", "creer_serveur", "TAILLE_MAXIMALE",
           "DOSSIER_DEFAUT", "CATALOGUES"]

TAILLE_MAXIMALE = 64 * 1024 * 1024
"""Corps de requete accepte, en octets. Une photo de telephone en base64 pese
environ 7 Mo ; soixante-quatre laissent de la marge pour une photo d'appareil
et sa carte de profondeur, et bornent ce qu'un client peut faire allouer."""

RESULTATS_GARDES = 8
"""Nombre de resultats gardes en memoire pour le telechargement. Au-dela, le
plus ancien est oublie : un atelier ouvert une journee ne doit pas accumuler
des dizaines de mosaiques de plusieurs mega-octets."""


DOSSIER_DEFAUT = pathlib.Path.home() / ".brickforge"
"""Ou l'atelier garde les catalogues de commande, d'une session a l'autre.

« Donnez-le une fois » ne veut rien dire si le fichier repart a chaque
redemarrage. Ce qui est ecrit la n'est pas le catalogue brut mais ce qu'on en a
RETENU — quelques centaines de lignes verifiees, relisibles par le meme lecteur
que le fichier d'origine. Rien d'autre n'est ecrit hors du dossier de sortie.
"""

CATALOGUES = ("elements", "elements_couleurs", "bricklink")


PAGE = r"""<!doctype html>
<html lang="fr">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BrickForge — une photo, une mosaique LEGO Art</title>
<style>
  :root {
    --encre:#15171c; --papier:#f4f1ea; --carte:#ffffff; --creux:#ebe6dc;
    --trait:#ddd6c8; --doux:#6e6a62; --vif:#d0342c; --sombre:#9d2620;
    --tenon:#f2b705; --ok:#0f7a4e; --ombre:0 1px 2px rgba(20,18,14,.06),
                                        0 8px 24px -12px rgba(20,18,14,.18);
  }
  @media (prefers-color-scheme: dark) {
    :root { --encre:#eeeae2; --papier:#111318; --carte:#1a1d23; --creux:#15181d;
            --trait:#2e323a; --doux:#98948c; --vif:#ef6a52; --sombre:#b8412f;
            --tenon:#f2b705; --ok:#4fbd8b;
            --ombre:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.7); }
  }
  * { box-sizing:border-box; }
  html { -webkit-text-size-adjust:100%; }
  body { margin:0; background:var(--papier); color:var(--encre);
         font:16px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI",
              Roboto, Helvetica, Arial, sans-serif;
         -webkit-font-smoothing:antialiased; }

  /* La frise de tenons. Trois cercles par brique, en degrade radial : aucune
     image, aucune requete — la page doit rester utilisable hors ligne. */
  .tenons { height:14px; background-repeat:repeat-x; background-size:28px 14px;
            background-image:radial-gradient(circle at 14px 3px,
              var(--tenon) 0 5px, transparent 5.5px); opacity:.9; }

  header { max-width:1220px; margin:0 auto; padding:26px 24px 0; }
  .marque { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; }
  h1 { font-size:34px; line-height:1.05; margin:0; letter-spacing:-.035em;
       font-weight:800; }
  h1 em { font-style:normal; color:var(--vif); }
  header p { margin:8px 0 0; color:var(--doux); font-size:15px; max-width:62ch; }

  main { display:grid; grid-template-columns:360px 1fr; gap:24px;
         max-width:1220px; margin:0 auto; padding:20px 24px 72px;
         align-items:start; }
  @media (max-width:940px) { main { grid-template-columns:1fr; } }

  .carte { background:var(--carte); border:1px solid var(--trait);
           border-radius:16px; padding:20px; box-shadow:var(--ombre); }

  /* Les etapes numerotees. Trois gestes, pas huit reglages. */
  .etape { display:flex; align-items:center; gap:9px; margin:22px 0 10px;
           font-size:13px; font-weight:700; letter-spacing:.06em;
           text-transform:uppercase; color:var(--doux); }
  .etape:first-child { margin-top:0; }
  .etape b { width:22px; height:22px; border-radius:50%; flex:none;
             display:grid; place-items:center; background:var(--encre);
             color:var(--papier); font-size:12px; letter-spacing:0; }

  #zone { border:2px dashed var(--trait); border-radius:14px;
          padding:26px 14px; text-align:center; cursor:pointer;
          background:var(--creux); transition:border-color .15s, transform .15s; }
  #zone:hover { border-color:var(--vif); }
  #zone.actif { border-color:var(--vif); transform:scale(1.01); }
  #zone strong { display:block; font-size:15px; margin-bottom:2px; }
  #zone span { color:var(--doux); font-size:13px; }
  #vignette { max-width:100%; max-height:170px; border-radius:10px;
              margin-top:12px; box-shadow:var(--ombre); }

  label { display:block; margin:14px 0 5px; font-size:13.5px; font-weight:650; }
  .aide { font-weight:400; color:var(--doux); display:block; font-size:12.5px;
          line-height:1.45; margin-top:2px; }
  input[type=number], select, input[type=text] {
    width:100%; padding:9px 11px; border:1px solid var(--trait);
    border-radius:10px; background:var(--carte); color:var(--encre);
    font:inherit; font-size:14.5px; }
  select { appearance:none; cursor:pointer;
           background-image:linear-gradient(45deg,transparent 50%,var(--doux) 50%),
                            linear-gradient(135deg,var(--doux) 50%,transparent 50%);
           background-position:calc(100% - 17px) 50%, calc(100% - 12px) 50%;
           background-size:5px 5px, 5px 5px; background-repeat:no-repeat;
           padding-right:34px; }
  input:focus-visible, select:focus-visible, button:focus-visible,
  a:focus-visible, summary:focus-visible {
    outline:2px solid var(--vif); outline-offset:2px; }
  .ligne { display:flex; gap:9px; align-items:center; }
  .ligne input[type=checkbox] { width:auto; accent-color:var(--vif); }
  .duo { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .duo label { margin-top:10px; }

  /* Les puces de format : on clique une taille, on ne la tape pas. */
  .puces { display:flex; flex-wrap:wrap; gap:7px; }
  .puces button { flex:1 1 auto; padding:8px 4px; border-radius:10px;
                  border:1px solid var(--trait); background:var(--carte);
                  color:var(--encre); font:inherit; font-size:13.5px;
                  font-weight:650; cursor:pointer; line-height:1.15;
                  transition:background .12s, border-color .12s; }
  .puces button small { display:block; font-weight:400; font-size:11px;
                        color:var(--doux); margin-top:1px; }
  .puces button:hover { border-color:var(--vif); }
  .puces button[aria-pressed=true] { background:var(--encre);
    color:var(--papier); border-color:var(--encre); }
  /* PAS `rgba(255,255,255,.7)` : en theme sombre le fond enfonce est CLAIR,
     et du blanc translucide dessus disparait. La couleur du papier suit le
     theme, l'opacite fait le reste. */
  .puces button[aria-pressed=true] small { color:var(--papier); opacity:.72; }

  /* Les couleurs de cadre se choisissent a l'oeil, pas dans une liste. */
  .teintes { display:flex; gap:8px; flex-wrap:wrap; }
  .teintes button { width:38px; height:38px; border-radius:10px; padding:0;
                    border:2px solid var(--trait); cursor:pointer;
                    position:relative; transition:transform .12s; }
  .teintes button:hover { transform:translateY(-2px); }
  .teintes button[aria-pressed=true] { border-color:var(--vif); }
  .teintes button[aria-pressed=true]::after { content:""; position:absolute;
    inset:auto 0 -9px 0; height:3px; border-radius:2px; background:var(--vif); }
  .teintes .sans { background:var(--carte); color:var(--doux); font-size:11px;
                   font-weight:700; width:auto; padding:0 10px; }

  /* Un bouton se presse comme une brique : il descend sur son epaisseur. */
  button.brique { width:100%; margin-top:20px; padding:14px; border:0;
    border-radius:12px; background:var(--vif); color:#fff; font:inherit;
    font-size:16px; font-weight:750; cursor:pointer;
    box-shadow:0 4px 0 var(--sombre); transition:transform .06s, box-shadow .06s; }
  button.brique:active:not(:disabled) { transform:translateY(3px);
    box-shadow:0 1px 0 var(--sombre); }
  button.brique:disabled { opacity:.45; cursor:default; box-shadow:0 4px 0 var(--trait); }
  button.brique.verte { background:var(--ok); box-shadow:0 4px 0 #0a5c3a; }
  @media (prefers-reduced-motion:reduce) {
    button.brique, .teintes button, #zone { transition:none; }
  }

  #conseil { display:none; margin-top:12px; }
  #conseil.montre { display:block; }
  #conseil .choix { display:flex; gap:10px; align-items:center;
                    padding:8px; border-radius:10px; cursor:pointer;
                    border:1px solid transparent; }
  #conseil .choix:hover { border-color:var(--trait); background:var(--creux); }
  #conseil .choix[aria-current=true] { border-color:var(--vif);
                                       background:var(--creux); }
  #conseil img { width:74px; border-radius:5px; flex:none;
                 image-rendering:pixelated; border:1px solid var(--trait); }
  #conseil b { display:block; font-size:13.5px; }
  #conseil span { color:var(--doux); font-size:12px; line-height:1.35; }
  #conseil .note { color:var(--doux); font-size:12px; margin:8px 0 0;
                   display:block; }

  #resultat { display:none; }
  #resultat.montre { display:block; animation:apparait .35s ease-out; }
  @keyframes apparait { from { opacity:0; transform:translateY(10px); } }
  @media (prefers-reduced-motion:reduce) { #resultat.montre { animation:none; } }

  #onglets { display:flex; gap:7px; margin-bottom:12px; flex-wrap:wrap; }
  #onglets button { padding:7px 14px; font-size:13px; font-weight:600;
    background:transparent; color:var(--doux); border:1px solid var(--trait);
    border-radius:999px; cursor:pointer; font-family:inherit; }
  #onglets button[aria-selected=true] { background:var(--encre);
    color:var(--papier); border-color:var(--encre); }

  /* Le comparateur. La photo est rognee, moyennee par tenon et encadree
     exactement comme l'oeuvre : les deux images se superposent au pixel pres,
     sans quoi on croirait juger la quantification en regardant un decalage. */
  #scene { position:relative; border-radius:12px; overflow:hidden;
           border:1px solid var(--trait); background:var(--creux);
           touch-action:none; }
  #rendu { display:block; width:100%; image-rendering:pixelated; }
  #avant { position:absolute; inset:0; clip-path:inset(0 50% 0 0); }
  #avant img { display:block; width:100%; height:100%; image-rendering:pixelated; }
  #poignee { position:absolute; top:0; bottom:0; left:50%; width:2px;
             background:#fff; box-shadow:0 0 0 1px rgba(0,0,0,.35);
             cursor:ew-resize; }
  #poignee::after { content:"⇄"; position:absolute; top:50%; left:50%;
    transform:translate(-50%,-50%); width:38px; height:38px; border-radius:50%;
    background:#fff; color:#15171c; display:grid; place-items:center;
    font-size:16px; box-shadow:0 2px 10px rgba(0,0,0,.35); }
  .etiquette { position:absolute; top:10px; font-size:11px; font-weight:700;
    letter-spacing:.08em; text-transform:uppercase; padding:4px 9px;
    border-radius:999px; background:rgba(0,0,0,.55); color:#fff;
    pointer-events:none; }
  .etiquette.g { left:10px; } .etiquette.d { right:10px; }
  #scene.simple #avant, #scene.simple #poignee, #scene.simple .etiquette {
    display:none; }

  .chiffres { display:grid; gap:10px; margin:18px 0 4px;
              grid-template-columns:repeat(auto-fit,minmax(142px,1fr)); }
  .chiffre { border:1px solid var(--trait); border-radius:12px; padding:11px 13px;
             background:var(--creux); }
  /* `clamp` plutot qu'une taille fixe : « 29×29 cm » depasse la tuile a 23px
     et se faisait rogner. Le nombre doit tenir, pas le contraire. */
  .chiffre b { display:block; font-size:clamp(18px,1.7vw,23px); font-weight:750;
               letter-spacing:-.03em; white-space:nowrap; }
  .chiffre span { color:var(--doux); font-size:12px; }

  h2 { font-size:17px; margin:22px 0 10px; letter-spacing:-.015em; }
  pre { white-space:pre-wrap; word-break:break-word; font-size:12.5px;
        line-height:1.5; margin:0; font-family:ui-monospace, SFMono-Regular,
        Menlo, Consolas, monospace; }
  pre .alerte { color:var(--vif); }
  #etat { margin-top:14px; font-size:13.5px; color:var(--doux); min-height:20px; }
  #etat.erreur { color:var(--vif); font-weight:600; }

  /* Pendant la fabrication : des tenons qui se posent l'un apres l'autre.
     Indetermine et assume — la chaine ne rend pas d'avancement, et une barre
     qui progresserait toute seule mentirait. */
  #chantier { display:none; gap:6px; margin-top:12px; }
  #chantier.tourne { display:flex; }
  #chantier i { width:11px; height:11px; border-radius:3px; background:var(--vif);
                opacity:.25; animation:pose 1.1s infinite ease-in-out; }
  #chantier i:nth-child(2) { animation-delay:.13s; }
  #chantier i:nth-child(3) { animation-delay:.26s; }
  #chantier i:nth-child(4) { animation-delay:.39s; }
  #chantier i:nth-child(5) { animation-delay:.52s; }
  @keyframes pose { 0%,70%,100% { opacity:.22; transform:translateY(0); }
                    35% { opacity:1; transform:translateY(-5px); } }

  details { margin-top:16px; border-top:1px solid var(--trait); padding-top:12px; }
  summary { cursor:pointer; font-size:13.5px; font-weight:650; color:var(--doux);
            list-style:none; display:flex; align-items:center; gap:7px; }
  summary::-webkit-details-marker { display:none; }
  summary::before { content:"›"; display:inline-block; transition:transform .15s;
                    font-size:17px; line-height:1; }
  details[open] > summary::before { transform:rotate(90deg); }

  /* Les deux fichiers qu'on veut vraiment : la notice, et la liste. Ils
     etaient au fond d'un ZIP qu'il fallait telecharger en entier puis ouvrir
     pour trouver le bon nom. */
  .emporter { display:grid; gap:10px; margin:4px 0 16px;
              grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); }
  .emporter a { display:block; padding:13px 14px; border-radius:12px;
                border:1px solid var(--trait); background:var(--creux);
                color:var(--encre); text-decoration:none;
                box-shadow:0 3px 0 var(--trait);
                transition:transform .06s, box-shadow .06s; }
  .emporter a:active { transform:translateY(2px); box-shadow:0 1px 0 var(--trait); }
  .emporter b { display:block; font-size:14.5px; }
  .emporter span { color:var(--doux); font-size:12.5px; }

  .commande { display:grid; gap:12px; margin:4px 0 18px;
              grid-template-columns:repeat(auto-fit,minmax(276px,1fr)); }
  .boutique { border:1px solid var(--trait); border-radius:14px;
              padding:15px 16px; background:var(--creux); }
  .boutique h3 { margin:0 0 2px; font-size:15px; }
  .boutique p { margin:0 0 11px; color:var(--doux); font-size:12.5px; }
  .boutique a.action, .boutique button.action {
    display:block; width:100%; margin:0 0 9px; padding:11px 10px; border:0;
    border-radius:10px; background:var(--encre); color:var(--papier);
    font:inherit; font-size:13.5px; font-weight:700; text-align:center;
    text-decoration:none; cursor:pointer; box-shadow:0 3px 0 rgba(0,0,0,.25);
    transition:transform .06s, box-shadow .06s; }
  .boutique a.action:active, .boutique button.action:active {
    transform:translateY(2px); box-shadow:0 1px 0 rgba(0,0,0,.25); }
  .boutique a.suite { display:inline-block; font-size:12.5px; color:var(--doux); }
  .boutique .manque { color:var(--vif); font-size:12.5px; margin:6px 0 0;
                      font-weight:600; }
  .boutique.vide { border-style:dashed; background:transparent; }

  #catalogues p { margin:7px 0 0; font-size:12.5px; color:var(--doux); }
  #etat_palette { border-left:3px solid var(--vif); padding-left:10px; }
  #etat_palette .etat { color:var(--ok); }
  #catalogues .etat { color:var(--ok); font-weight:650; }
  #catalogues input[type=file] { font-size:12px; margin-top:4px; width:100%; }
  #catalogues button.brique { margin-top:14px; padding:11px; font-size:14px; }
  #catalogues button.mineur { background:transparent; color:var(--doux);
    border:1px solid var(--trait); font-weight:500; padding:9px;
    font-size:12.5px; box-shadow:none; margin-top:8px; }
  #xml { width:100%; height:84px; margin-top:7px; font-size:11px;
         font-family:ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
         border:1px solid var(--trait); border-radius:8px; padding:7px;
         background:var(--carte); color:var(--encre); }
  a { color:var(--vif); }
</style>

<div class="tenons"></div>
<header>
  <div class="marque">
    <h1>Brick<em>Forge</em></h1>
  </div>
  <p>Une photo, une mosaique LEGO Art : le modele, la liste de courses et la
     notice de montage. Rien n'est livre qui ne tienne debout.</p>
</header>

<main>
  <form class="carte" id="formulaire">
    <div class="etape"><b>1</b> La photo</div>
    <div id="zone">
      <strong>Deposez une photo</strong>
      <span>ou cliquez — JPEG, PNG ou PPM</span>
      <img id="vignette" hidden alt="">
    </div>
    <input type="file" id="fichier" accept="image/*" hidden>

    <div class="etape"><b>2</b> Le format</div>
    <div class="puces" id="formats">
      <button type="button" data-studs="32">32<small>26 cm</small></button>
      <button type="button" data-studs="48">48<small>38 cm</small></button>
      <button type="button" data-studs="64">64<small>51 cm</small></button>
      <button type="button" data-studs="96">96<small>77 cm</small></button>
    </div>
    <div class="duo">
      <label>Largeur en tenons
        <input type="number" id="studs" value="48" min="2" max="192" step="1">
      </label>
      <label>Hauteur
        <input type="number" id="hauteur" placeholder="auto" min="2" max="192">
      </label>
    </div>
    <span class="aide">48 tenons est le format des sets LEGO Art. Hauteur vide :
      les proportions de la photo sont gardees.</span>
    <button type="button" class="brique mineur" id="demander_conseil" disabled>
      Quel format choisir ?</button>
    <div id="conseil"></div>

    <label>Cadre
      <span class="aide">Un tableau se cadre. Le cadre depasse la surface et
        porte son ombre dessus ; il ceinture aussi les sections.</span>
    </label>
    <div class="teintes" id="teintes">
      <button type="button" data-cadre="2|0" style="background:#1b2a34"
              title="noir"></button>
      <button type="button" data-cadre="2|72" style="background:#6c6e68"
              title="gris fonce"></button>
      <button type="button" data-cadre="2|71" style="background:#a0a5a9"
              title="gris clair"></button>
      <button type="button" data-cadre="2|70" style="background:#583927"
              title="brun rougeatre"></button>
      <button type="button" data-cadre="2|15" style="background:#f4f4f4"
              title="blanc"></button>
      <button type="button" class="sans" data-cadre="0">sans</button>
    </div>
    <input type="hidden" id="cadre" value="2|0">
    <div class="ligne" style="margin-top:11px">
      <input type="checkbox" id="cadre_large">
      <label for="cadre_large" style="margin:0; font-weight:400">
        cadre large — 3 tenons</label>
    </div>

    <label>Relief
      <span class="aide">Etages de plates sous les tuiles. Ne coute aucune
        precision, seulement des pieces.</span>
      <select id="relief">
        <option value="0">aucun — oeuvre plate</option>
        <option value="1">1 etage — 3,2 mm</option>
        <option value="2">2 etages — 6,4 mm</option>
        <option value="3">3 etages — 9,6 mm</option>
        <option value="4">4 etages — 12,8 mm</option>
      </select>
    </label>

    <div id="bloc_profondeur" hidden>
      <div class="ligne" style="margin-bottom:9px">
        <input type="checkbox" id="relief_inverse">
        <label for="relief_inverse" style="margin:0; font-weight:400">
          sombre = haut — a cocher pour un paysage</label>
      </div>
      <span class="aide">Sans carte de profondeur, les etages se lisent sur la
        CLARTE de la photo : clair = haut, la convention du camee. Elle va au
        portrait, ou le visage est plus clair que le fond. Sur un paysage elle
        fait ressortir le ciel devant le sol — cette case la renverse.</span>

      <label style="margin-top:12px">Carte de profondeur (facultatif)
        <span class="aide">Une carte mesuree — MiDaS, Depth Anything — remplace
          la convention de clarte, quel que soit son sens. Sans elle, une carte
          deja presente dans le JPEG est lue automatiquement.</span>
      </label>
      <input type="file" id="carte" accept="image/*">
      <div class="ligne" style="margin-top:9px">
        <input type="checkbox" id="inversee">
        <label for="inversee" style="margin:0; font-weight:400">
          la carte encode une distance (proche = sombre)</label>
      </div>
    </div>

    <div class="etape"><b>3</b> Fabriquer</div>
    <button type="submit" class="brique" id="lancer" disabled>
      Fabriquer la mosaique</button>
    <div id="chantier" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>
    <div id="etat"></div>

    <details id="fins">
      <summary>Reglages fins</summary>
      <label>Jeu de tuiles
        <select id="references">
          <option value="standard">standard — 1x1, 1x2, 1x4</option>
          <option value="minimal">minimal — 1x1 seule, grille reguliere</option>
          <option value="large">large — jusqu'a 1x8, moins de pieces</option>
          <option value="art">art — tuiles rondes, prix plein</option>
        </select>
      </label>
      <label>Decouper en sections
        <span class="aide">Au-dela d'une cinquantaine de tenons, une mosaique ne
          passe plus sur une table. Chaque section est un modele complet avec sa
          propre notice ; une couche de plates les reunit par-dessous.</span>
        <select id="sections">
          <option value="0">non — d'un seul tenant</option>
          <option value="16">sections de 16 tenons (13 cm)</option>
          <option value="24">sections de 24 tenons (19 cm)</option>
          <option value="32">sections de 32 tenons (26 cm)</option>
          <option value="48">sections de 48 tenons (38 cm)</option>
        </select>
      </label>
      <label>Tramage
        <span class="aide">Melange des tuiles voisines la ou la palette manque.
          « aucun » par defaut : sur six photographies reelles, la version nette
          a toujours ete jugee meilleure ou equivalente. Le journal dit ce que
          le tramage aurait gagne et coute.</span>
        <select id="tramage">
          <option value="aucun">aucun — net (defaut)</option>
          <option value="auto">auto — laisse le critere decider</option>
          <option value="adaptatif">adaptatif</option>
          <option value="complet">complet</option>
        </select>
      </label>
      <label>Nombre de couleurs
        <span class="aide">Vide : toutes. « auto » : la palette la moins chere.</span>
        <input type="text" id="couleurs" placeholder="toutes">
      </label>
      <label>Cadrage
        <span class="aide">0 a 1, ou « auto » (fenetre au detail maximal).</span>
        <input type="text" id="cadrage" value="auto">
      </label>
      <label>Nettoyage des tuiles isolees
        <span class="aide">Ecart tolere pour effacer une tuile qui ne
          ressemble a aucune de ses voisines. 0 : aucune.</span>
        <select id="debruitage">
          <option value="4">4 delta E — defaut</option>
          <option value="8">8 delta E — plus agressif</option>
          <option value="2">2 delta E — prudent</option>
          <option value="0">aucun nettoyage</option>
        </select>
      </label>
      <label>Seuils du relief
        <select id="seuils">
          <option value="otsu">Otsu — sur les contours</option>
          <option value="uniform">uniforme — en parts egales</option>
        </select>
      </label>
    </details>

    <details id="catalogues">
      <summary>Palette et catalogues</summary>
      <p id="etat_palette">Chargement...</p>
      <button type="button" class="brique" id="poser_palette" hidden>
        Installer la palette officielle LEGO</button>
      <p id="etat_catalogues">Chargement...</p>
      <p>A donner <strong>une seule fois</strong> : ils sont gardes sur cette
         machine et servent a toutes les oeuvres suivantes. Sans eux, la liste
         de courses reste un simple CSV a recopier a la main.</p>

      <label style="margin-top:12px">Catalogue d'elements LEGO
        <span class="aide">Le numero d'une piece <em>dans une couleur</em>.
          <a href="https://rebrickable.com/downloads/" target="_blank"
             rel="noopener noreferrer">elements.csv chez Rebrickable</a> —
          le .gz se depose tel quel.</span>
      </label>
      <input type="file" id="cat_elements" accept=".csv,.tsv,.txt,.gz,.zip">

      <label>Couleurs de ce catalogue
        <span class="aide">Necessaire seulement si le catalogue designe ses
          couleurs par un numero : chez Rebrickable, colors.csv.</span>
      </label>
      <input type="file" id="cat_couleurs" accept=".csv,.tsv,.txt,.gz,.zip">

      <label>Couleurs BrickLink
        <span class="aide">L'export de couleurs BrickLink, ou une table a deux
          colonnes. Pour la liste de souhaits BrickLink.</span>
      </label>
      <input type="file" id="cat_bricklink" accept=".csv,.tsv,.txt,.gz,.zip">

      <button type="button" class="brique" id="poser_catalogues">
        Enregistrer les catalogues</button>
      <button type="button" class="brique mineur" id="oublier_catalogues">
        Tout oublier</button>
    </details>
  </form>

  <section>
    <div class="carte" id="resultat">
      <div id="onglets"></div>
      <div id="scene">
        <img id="rendu" alt="Apercu de la mosaique">
        <div id="avant"><img id="avant_img" alt="La photo, vue par la mosaique"></div>
        <span class="etiquette g">photo</span>
        <span class="etiquette d">LEGO</span>
        <div id="poignee" role="separator" aria-label="Comparer"></div>
      </div>
      <div class="chiffres" id="chiffres"></div>
      <h2>Commander</h2>
      <div class="commande" id="commander"></div>
      <h2>Emporter</h2>
      <div class="emporter" id="emporter"></div>
      <a id="telecharger" download><button type="button" class="brique verte">
        Telecharger le dossier complet (ZIP)</button></a>
      <details open>
        <summary>Journal de fabrication</summary>
        <pre id="journal"></pre>
      </details>
    </div>
  </section>
</main>

<script>
(function () {
  var photo = null, carte = null, apercus = {}, onglet = null;
  var zone = document.getElementById('zone');
  var champ = document.getElementById('fichier');
  var lancer = document.getElementById('lancer');
  var etat = document.getElementById('etat');
  var chantier = document.getElementById('chantier');

  function lire(fichier, suite) {
    var lecteur = new FileReader();
    lecteur.onload = function () { suite(lecteur.result); };
    lecteur.readAsDataURL(fichier);
  }

  function accepter(fichier) {
    if (!fichier) return;
    lire(fichier, function (uri) {
      photo = uri;
      var vignette = document.getElementById('vignette');
      vignette.src = uri; vignette.hidden = false;
      zone.querySelector('strong').textContent = fichier.name;
      zone.querySelector('span').textContent =
        Math.round(fichier.size / 1024) + ' Ko — cliquez pour changer';
      lancer.disabled = false;
      demander.disabled = false;
    });
  }

  zone.addEventListener('click', function () { champ.click(); });
  champ.addEventListener('change', function () { accepter(champ.files[0]); });
  ['dragenter', 'dragover'].forEach(function (nom) {
    zone.addEventListener(nom, function (e) {
      e.preventDefault(); zone.classList.add('actif');
    });
  });
  ['dragleave', 'drop'].forEach(function (nom) {
    zone.addEventListener(nom, function (e) {
      e.preventDefault(); zone.classList.remove('actif');
    });
  });
  zone.addEventListener('drop', function (e) {
    accepter(e.dataTransfer.files[0]);
  });

  document.getElementById('relief').addEventListener('change', function () {
    document.getElementById('bloc_profondeur').hidden = this.value === '0';
  });
  document.getElementById('carte').addEventListener('change', function () {
    if (this.files[0]) lire(this.files[0], function (uri) { carte = uri; });
    else carte = null;
  });

  function valeur(id) { return document.getElementById(id).value.trim(); }

  // Une seule lecture du formulaire. Le conseil de format et la fabrication
  // doivent porter sur les MEMES reglages : un conseil calcule avec un autre
  // cadre ou un autre jeu de tuiles ne conseille rien.
  function reglagesActuels() {
    return {
      studs: valeur('studs'),
      hauteur: valeur('hauteur'),
      relief: valeur('relief'),
      references: valeur('references'),
      tramage: valeur('tramage'),
      couleurs: valeur('couleurs'),
      cadrage: valeur('cadrage'),
      seuils: valeur('seuils'),
      debruitage: valeur('debruitage'),
      sections: valeur('sections'),
      cadre: valeur('cadre').split('|')[0],
      cadre_couleur: valeur('cadre').split('|')[1] || '0',
      profondeur_inversee: document.getElementById('inversee').checked,
      relief_inverse: document.getElementById('relief_inverse').checked,
      titre: (champ.files[0] || {}).name || 'mosaique'
    };
  }

  // Un groupe de boutons qui se comportent comme des radios : un seul enfonce,
  // et c'est le champ cache ou le champ nombre qui porte la valeur reelle.
  function groupe(conteneur, choisir, correspond) {
    var boutons = Array.prototype.slice.call(conteneur.children);
    function peindre() {
      boutons.forEach(function (b) {
        b.setAttribute('aria-pressed', correspond(b) ? 'true' : 'false');
      });
    }
    boutons.forEach(function (b) {
      b.addEventListener('click', function () { choisir(b); peindre(); });
    });
    peindre();
    return peindre;
  }

  var studs = document.getElementById('studs');
  var peindreFormats = groupe(
    document.getElementById('formats'),
    function (b) { studs.value = b.dataset.studs; },
    function (b) { return b.dataset.studs === studs.value; });
  studs.addEventListener('input', peindreFormats);

  var cadre = document.getElementById('cadre');
  var large = document.getElementById('cadre_large');
  function epaisseur() {
    // Le champ cache porte « epaisseur|couleur » ; les pastilles ne changent
    // que la couleur, la case ne change que l'epaisseur.
    var part = cadre.value.split('|');
    if (part[0] === '0') return;
    cadre.value = (large.checked ? '3' : '2') + '|' + (part[1] || '0');
  }
  groupe(document.getElementById('teintes'),
    function (b) { cadre.value = b.dataset.cadre; epaisseur(); },
    function (b) {
      return b.dataset.cadre.split('|')[1] === cadre.value.split('|')[1]
             && (b.dataset.cadre === '0') === (cadre.value === '0');
    });
  large.addEventListener('change', epaisseur);

  // ---------------------------------------------------------------- //
  // Le comparateur photo / LEGO
  // ---------------------------------------------------------------- //
  var scene = document.getElementById('scene');
  var avant = document.getElementById('avant');
  var poignee = document.getElementById('poignee');
  var tire = false;

  function placer(part) {
    part = Math.max(0, Math.min(100, part));
    avant.style.clipPath = 'inset(0 ' + (100 - part) + '% 0 0)';
    poignee.style.left = part + '%';
  }

  function depuis(e) {
    var boite = scene.getBoundingClientRect();
    if (!boite.width) return;
    placer(((e.clientX - boite.left) / boite.width) * 100);
  }

  scene.addEventListener('pointerdown', function (e) {
    if (scene.classList.contains('simple')) return;
    tire = true; scene.setPointerCapture(e.pointerId); depuis(e);
  });
  scene.addEventListener('pointermove', function (e) { if (tire) depuis(e); });
  ['pointerup', 'pointercancel'].forEach(function (nom) {
    scene.addEventListener(nom, function () { tire = false; });
  });

  function montrer(nom) {
    onglet = nom;
    document.getElementById('rendu').src = apercus[nom];
    // Le comparateur n'a de sens que sur le rendu : superposer la photo a la
    // vue des joints ou du relief comparerait deux choses differentes.
    var comparable = nom === 'apercu.png' && !!apercus['apercu_source.png'];
    scene.classList.toggle('simple', !comparable);
    if (comparable) {
      document.getElementById('avant_img').src = apercus['apercu_source.png'];
      placer(50);
    }
    Array.prototype.forEach.call(
      document.getElementById('onglets').children, function (b) {
        b.setAttribute('aria-selected', b.dataset.nom === nom);
      });
  }

  var TITRES = {
    'apercu.png': 'Rendu',
    'apercu_joints.png': 'Joints reels',
    'apercu_relief.png': 'Relief eclaire'
  };

  function titre(nom) {
    if (TITRES[nom]) return TITRES[nom];
    var section = nom.match(/^section_(\d+)_(\d+)\//);
    if (section) return 'Section ' + section[1] + '-' + section[2];
    return nom;
  }

  // ---------------------------------------------------------------- //
  // Les catalogues de commande : donnes une fois, gardes ensuite.
  // ---------------------------------------------------------------- //
  var etatCat = document.getElementById('etat_catalogues');
  var etatPal = document.getElementById('etat_palette');
  var poserPal = document.getElementById('poser_palette');

  function direPalette(p) {
    if (!p) return;
    etatPal.textContent = '';
    var n = document.createElement('span');
    if (p.provisoire) {
      n.textContent = 'Palette de secours : ' + p.couleurs + ' couleurs '
        + 'recopiees a la main. L\'officielle en compte 159, dont 80 '
        + 'commandables en tuile — c\'est elle qui fait la difference entre '
        + 'un rendu correct et un rendu propre.';
      poserPal.hidden = false;
    } else {
      n.className = 'etat';
      n.textContent = 'Palette officielle : ' + p.couleurs + ' couleurs, '
        + p.commandables + ' commandables en tuile.';
      poserPal.hidden = true;
    }
    etatPal.appendChild(n);
  }

  poserPal.addEventListener('click', function () {
    var bouton = this;
    bouton.disabled = true;
    etatPal.textContent = 'Telechargement depuis LDraw.org...';
    fetch('/palette', { method: 'POST' }).then(function (r) {
      return r.json().then(function (corps) {
        if (!r.ok) throw new Error(corps.erreur || ('erreur ' + r.status));
        return corps;
      });
    }).then(function (p) {
      direPalette(p);
      if (document.getElementById('resultat').classList.contains('montre')) {
        etat.className = '';
        etat.textContent = 'Palette installee — refabriquez la mosaique pour '
          + 'en profiter.';
      }
    }).catch(function (raison) {
      etatPal.textContent = String(raison.message || raison);
      bouton.disabled = false;
    });
  });

  function direCatalogues(etat_) {
    direPalette(etat_.palette);
    etatCat.textContent = '';
    var lignes = [];
    if (etat_.elements) {
      lignes.push('Elements LEGO : ' + etat_.elements.references
                  + ' references — ' + etat_.elements.note);
    }
    if (etat_.bricklink) {
      lignes.push('BrickLink : ' + etat_.bricklink.couleurs
                  + ' couleurs — ' + etat_.bricklink.note);
    }
    if (!lignes.length) {
      etatCat.textContent = 'Aucun catalogue : la liste de courses sortira en '
        + 'CSV, sans commande prete a envoyer.';
      return;
    }
    lignes.forEach(function (texte) {
      var n = document.createElement('span');
      n.className = 'etat';
      n.textContent = texte;
      etatCat.appendChild(n);
      etatCat.appendChild(document.createElement('br'));
    });
    if (etat_.dossier) {
      var d = document.createElement('span');
      d.textContent = 'Gardes dans ' + etat_.dossier + ' sur cette machine.';
      etatCat.appendChild(d);
    }
    // Un resultat deja affiche a ete fabrique SANS ces catalogues : sa carte
    // « Commander » est perimee, et rien ne le dirait autrement.
    if (document.getElementById('resultat').classList.contains('montre')) {
      etat.className = '';
      etat.textContent = 'Catalogues enregistres — refabriquez la mosaique '
        + 'pour en obtenir la commande.';
    }
  }

  fetch('/catalogues').then(function (r) { return r.json(); })
    .then(direCatalogues).catch(function () {
      etatCat.textContent = 'Etat des catalogues indisponible.';
    });

  function lireOuRien(id, suite) {
    var f = document.getElementById(id).files[0];
    if (!f) { suite(null); return; }
    lire(f, suite);
  }

  document.getElementById('poser_catalogues')
    .addEventListener('click', function () {
      var bouton = this;
      bouton.disabled = true;
      etatCat.textContent = 'Lecture...';
      lireOuRien('cat_elements', function (a) {
        lireOuRien('cat_couleurs', function (b) {
          lireOuRien('cat_bricklink', function (c) {
            fetch('/catalogues', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                elements: a, elements_couleurs: b, bricklink: c
              })
            }).then(function (r) {
              return r.json().then(function (corps) {
                if (!r.ok) throw new Error(corps.erreur || ('erreur ' + r.status));
                return corps;
              });
            }).then(direCatalogues).catch(function (raison) {
              etatCat.textContent = String(raison.message || raison);
            }).finally(function () { bouton.disabled = false; });
          });
        });
      });
    });

  document.getElementById('oublier_catalogues')
    .addEventListener('click', function () {
      fetch('/catalogues', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ oublier: true })
      }).then(function (r) { return r.json(); }).then(direCatalogues);
    });

  // ---------------------------------------------------------------- //
  // La carte « Commander »
  // ---------------------------------------------------------------- //
  var PICK_A_BRICK = 'https://www.lego.com/pick-and-build/pick-a-brick';
  var BRICKLINK_IMPORT = 'https://www.bricklink.com/v2/wanted/upload.page';

  function boite(titre_, sous) {
    var d = document.createElement('div');
    d.className = 'boutique';
    var h = document.createElement('h3'); h.textContent = titre_;
    var p = document.createElement('p'); p.textContent = sous;
    d.appendChild(h); d.appendChild(p);
    return d;
  }

  function bouton(texte, action) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'action'; b.textContent = texte;
    b.addEventListener('click', action);
    return b;
  }

  function lienFichier(jeton, nom, texte) {
    var a = document.createElement('a');
    a.className = 'action';
    a.href = '/fichier/' + encodeURIComponent(jeton) + '/'
             + nom.split('/').map(encodeURIComponent).join('/');
    a.setAttribute('download', nom.replace(/\//g, '_'));
    a.textContent = texte;
    return a;
  }

  function lienDehors(url, texte) {
    var a = document.createElement('a');
    a.className = 'suite'; a.href = url;
    a.target = '_blank'; a.rel = 'noopener noreferrer';
    a.textContent = texte;
    return a;
  }

  function note(parent, texte, classe) {
    var p = document.createElement('p');
    if (classe) p.className = classe;
    else { p.style.margin = '6px 0 0'; p.style.fontSize = '12.5px';
           p.style.color = 'var(--doux)'; }
    p.textContent = texte;
    parent.appendChild(p);
    return p;
  }

  function copierLeXml(jeton, retour) {
    fetch('/fichier/' + encodeURIComponent(jeton) + '/commande_bricklink.xml')
      .then(function (r) { return r.text(); })
      .then(function (texte) {
        // BrickLink veut un COLLAGE, pas un fichier : son formulaire d'import
        // ne prend pas de piece jointe. Le presse-papier direct n'existe que
        // sur une origine sure — 127.0.0.1 en est une, pas une adresse de
        // reseau local. D'ou la zone de texte en secours, deja selectionnee.
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(texte).then(function () {
            retour('XML copie — collez-le dans la page BrickLink.');
          }).catch(function () { secours(texte, retour); });
        } else { secours(texte, retour); }
      }).catch(function () { retour('Fichier indisponible : refabriquez.'); });
  }

  function secours(texte, retour) {
    var zone_ = document.getElementById('xml');
    zone_.hidden = false;
    zone_.value = texte;
    zone_.focus(); zone_.select();
    var copie = false;
    try { copie = document.execCommand('copy'); } catch (e) { copie = false; }
    retour(copie ? 'XML copie — collez-le dans la page BrickLink.'
                 : 'XML selectionne ci-dessous : Ctrl-C pour le copier.');
  }

  // Ce qu'on emporte vraiment. Le ZIP reste, mais il ne doit plus etre le
  // SEUL chemin vers la notice : personne ne telecharge une archive pour en
  // extraire un fichier dont il ignore le nom.
  var EMPORTABLES = [
    ['notice.pdf', 'La notice', function (m) {
      return m.pages + ' pages, ' + m.etapes + ' etapes'; }],
    ['liste_de_course.csv', 'La liste de courses', function (m) {
      return m.lots + ' references, ' + m.pieces + ' pieces'; }],
    ['modele.ldr', 'Le modele 3D', function () {
      return 'LDraw — Studio, LeoCAD, LDView'; }]
  ];

  function emporter(jeton, m, fichiers) {
    var zone = document.getElementById('emporter');
    zone.textContent = '';
    EMPORTABLES.forEach(function (item) {
      if (fichiers.indexOf(item[0]) < 0) return;
      var a = document.createElement('a');
      a.href = '/fichier/' + encodeURIComponent(jeton) + '/'
               + encodeURIComponent(item[0]);
      a.setAttribute('download', item[0]);
      var b = document.createElement('b'); b.textContent = item[1];
      var s = document.createElement('span'); s.textContent = item[2](m);
      a.appendChild(b); a.appendChild(s);
      zone.appendChild(a);
    });
  }

  function commander(jeton, m, fichiers) {
    var zone_ = document.getElementById('commander');
    zone_.textContent = '';
    var eu = false;

    if (m.commande_lego_lots) {
      var d = boite('LEGO Pick a Brick',
        m.commande_lego_lots + ' references, ' + m.commande_lego_pieces
        + ' pieces');
      fichiers.filter(function (n) {
        return /^commande_lego(_\d+)?\.csv$/.test(n);
      }).forEach(function (n) {
        d.appendChild(lienFichier(jeton, n, 'Telecharger ' + n));
      });
      d.appendChild(lienDehors(PICK_A_BRICK,
        'Ouvrir Pick a Brick, puis le bouton « Upload list » →'));
      if (m.commande_lego_envois > 1) {
        note(d, 'Plus de 400 references : ' + m.commande_lego_envois
                + ' envois separes, la limite de Pick a Brick.');
      }
      if (m.commande_lego_manquants) {
        note(d, m.commande_lego_manquants + ' lot(s) sans element id — a '
                + 'chercher a la main.', 'manque');
        d.appendChild(lienFichier(jeton, 'pieces_sans_element.csv',
                                  'Telecharger la liste des manquants'));
      }
      note(d, 'La disponibilite reelle n\'est pas connue ici : Pick a Brick la '
              + 'dira a l\'envoi.');
      zone_.appendChild(d); eu = true;
    }

    if (m.commande_bricklink_lots) {
      var b = boite('BrickLink',
        m.commande_bricklink_lots + ' lots, liste de souhaits complete');
      var dit = null;
      b.appendChild(bouton('Copier le XML pour BrickLink', function () {
        copierLeXml(jeton, function (texte) { dit.textContent = texte; });
      }));
      b.appendChild(lienDehors(BRICKLINK_IMPORT,
        'Ouvrir la page d\'import BrickLink →'));
      dit = note(b, 'BrickLink importe par copier-coller, pas par fichier : '
                    + 'le bouton met le XML dans le presse-papier.');
      var aire = document.createElement('textarea');
      aire.id = 'xml'; aire.readOnly = true; aire.hidden = true;
      b.appendChild(aire);
      zone_.appendChild(b); eu = true;
    }

    if (!eu) {
      var v = boite('Aucune commande prete',
        'La liste de courses est la, mais en CSV a recopier.');
      v.className = 'boutique vide';
      note(v, 'Ouvrez « Catalogues de commande » a gauche et deposez-y le '
              + 'catalogue d\'elements : le numero d\'une piece dans une '
              + 'couleur est attribue par LEGO, il ne se calcule pas.');
      v.appendChild(lienDehors('https://rebrickable.com/downloads/',
        'Ou telecharger elements.csv et colors.csv →'));
      zone_.appendChild(v);
      document.getElementById('catalogues').open = true;
    }
  }

  // ---------------------------------------------------------------- //
  // Quel format ? La question la plus chere de la chaine.
  // ---------------------------------------------------------------- //
  var demander = document.getElementById('demander_conseil');
  var zoneConseil = document.getElementById('conseil');

  demander.addEventListener('click', function () {
    if (!photo) return;
    var bouton = this;
    bouton.disabled = true;
    zoneConseil.textContent = 'Quatre formats mis en balance, une dizaine '
      + 'de secondes...';
    zoneConseil.classList.add('montre');
    fetch('/conseil', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ photo: photo, reglages: reglagesActuels() })
    }).then(function (r) {
      return r.json().then(function (corps) {
        if (!r.ok) throw new Error(corps.erreur || ('erreur ' + r.status));
        return corps;
      });
    }).then(function (reponse) {
      zoneConseil.textContent = '';
      var precedent = null;
      reponse.formats.forEach(function (f) {
        var ligne = document.createElement('div');
        ligne.className = 'choix';
        ligne.setAttribute('aria-current',
          String(f.studs_x === parseInt(valeur('studs'), 10)));
        // Le tiers central, affiche a largeur constante : c'est la seule
        // vignette qui montre la difference. L'oeuvre entiere a 56 pixels de
        // large est identique pour 32 et pour 96 tenons.
        var vue = document.createElement('img');
        vue.src = f.detail_vu; vue.alt = '';
        var texte = document.createElement('div');
        var titre_ = document.createElement('b');
        titre_.textContent = f.studs_x + '\u00d7' + f.studs_y + ' — '
          + f.largeur_cm + '\u00d7' + f.hauteur_cm + ' cm';
        var sous = document.createElement('span');
        var mots = f.pieces + ' pieces';
        if (precedent) {
          var gain = precedent.detail - f.detail;
          mots += ' \u00b7 +' + (f.pieces - precedent.pieces) + ' pour '
            + gain.toFixed(2) + ' de detail gagne';
        }
        sous.textContent = mots;
        texte.appendChild(titre_); texte.appendChild(sous);
        ligne.appendChild(vue); ligne.appendChild(texte);
        // Cliquer une ligne choisit ce format : le conseil doit pouvoir etre
        // suivi sans retaper le nombre.
        ligne.addEventListener('click', function () {
          document.getElementById('studs').value = f.studs_x;
          document.getElementById('hauteur').value = f.studs_y;
          peindreFormats();
          Array.prototype.forEach.call(zoneConseil.children, function (c) {
            if (c.classList.contains('choix')) {
              c.setAttribute('aria-current', String(c === ligne));
            }
          });
        });
        zoneConseil.appendChild(ligne);
        precedent = f;
      });
      var note = document.createElement('span');
      note.className = 'note';
      note.textContent = 'Les vignettes montrent le MEME morceau de la scene, '
        + 'a la meme largeur : la version fine y met plus de tuiles, et la '
        + 'difference se voit. Le detail est l\'ecart a la photo mesure a '
        + 'finesse constante ; l\'ecart par tuile, lui, est borne par la '
        + 'palette et ne bouge presque pas avec la taille.';
      zoneConseil.appendChild(note);
    }).catch(function (raison) {
      zoneConseil.textContent = String(raison.message || raison);
    }).finally(function () { bouton.disabled = false; });
  });

  document.getElementById('formulaire').addEventListener('submit', function (e) {
    e.preventDefault();
    if (!photo) return;
    lancer.disabled = true;
    etat.className = '';
    etat.textContent = 'Fabrication en cours — les six invariants du noyau '
      + 'sont verifies avant toute livraison.';
    chantier.classList.add('tourne');
    var debut = Date.now();

    fetch('/fabriquer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        photo: photo,
        carte_profondeur: carte,
        reglages: reglagesActuels()
      })
    }).then(function (r) {
      return r.json().then(function (corps) {
        if (!r.ok) throw new Error(corps.erreur || ('erreur ' + r.status));
        return corps;
      });
    }).then(function (reponse) {
      apercus = reponse.apercus;
      var onglets = document.getElementById('onglets');
      onglets.textContent = '';
      Object.keys(apercus).sort().filter(function (nom) {
        // La source n'est pas un onglet : c'est la moitie gauche du
        // comparateur, et elle n'a aucun sens seule.
        return nom !== 'apercu_source.png';
      }).forEach(function (nom) {
        var b = document.createElement('button');
        b.type = 'button'; b.dataset.nom = nom;
        b.textContent = titre(nom);
        b.addEventListener('click', function () { montrer(nom); });
        onglets.appendChild(b);
      });
      montrer(apercus['apercu.png'] ? 'apercu.png'
              : Object.keys(apercus).filter(function (n) {
                  return n !== 'apercu_source.png'; })[0]);

      var m = reponse.mesures;
      var cases = [
        [m.pieces, 'pieces'],
        [m.lots, 'references a commander'],
        [m.tuiles, 'tuiles sur ' + m.tenons + ' tenons'],
        [m.delta_e.toFixed(1) + ' ΔE', m.verdict],
        [Math.round(m.largeur_mm / 10) + '×'
         + Math.round(m.hauteur_mm / 10) + ' cm', 'dimensions'],
        [m.etapes, 'etapes'],
        [m.pages, 'pages de notice']
      ];
      var chiffres = document.getElementById('chiffres');
      chiffres.textContent = '';
      cases.forEach(function (c) {
        var d = document.createElement('div');
        d.className = 'chiffre';
        var b = document.createElement('b'); b.textContent = c[0];
        var s = document.createElement('span'); s.textContent = c[1];
        d.appendChild(b); d.appendChild(s); chiffres.appendChild(d);
      });

      var journal = document.getElementById('journal');
      journal.textContent = '';
      reponse.journal.forEach(function (l) {
        var n = document.createElement('span');
        if (l.flux === 'alerte') n.className = 'alerte';
        n.textContent = l.texte + '\n';
        journal.appendChild(n);
      });

      emporter(reponse.jeton, reponse.mesures, reponse.fichiers);
      commander(reponse.jeton, reponse.mesures, reponse.fichiers);

      document.getElementById('telecharger').href =
        '/telecharger/' + reponse.jeton + '.zip';
      document.getElementById('resultat').classList.add('montre');
      etat.textContent = 'Termine en '
        + ((Date.now() - debut) / 1000).toFixed(1) + ' s.';
    }).catch(function (raison) {
      etat.className = 'erreur';
      etat.textContent = String(raison.message || raison);
    }).finally(function () {
      lancer.disabled = false;
      chantier.classList.remove('tourne');
    });
  });
})();
</script>
</html>
"""

class Atelier:
    """L'etat du serveur : la palette chargee une fois, les resultats recents.

    Separe du gestionnaire HTTP pour une raison simple : tout ce qui est
    testable est ici, et il se teste sans ouvrir de socket.
    """

    def __init__(self, palette: Optional[Palette] = None,
                 palette_complete: Optional[Palette] = None,
                 note_palette: Optional[Tuple[str, str]] = None,
                 table_bricklink: Optional[Mapping[int, int]] = None,
                 table_elements=None,
                 dossier: Optional[pathlib.Path] = None,
                 memoire: Optional[bool] = None):
        if palette is None:
            complete, note_palette = palette_utilisable()
            palette_complete = complete
            palette = (complete if note_palette[0] == "alerte"
                       else complete.solids_only())
        self.palette = palette
        self.palette_complete = palette_complete or palette
        self.note_palette = note_palette
        # Les catalogues de commande sont une propriete de l'INSTALLATION, pas
        # de l'oeuvre : on les donne une fois et chaque fabrication en profite.
        # Les redemander a chaque photo alourdirait la page sans rien apporter.
        #
        # Mais « une fois » ne veut rien dire si le fichier repart au
        # redemarrage : ils sont donc RELUS du dossier au demarrage, et une
        # nouvelle depuis la page y est ecrite. Le lanceur garde ses options,
        # qui l'emportent sur ce qui est en memoire.
        # Donner un dossier, c'est demander qu'on s'en souvienne ; n'en donner
        # aucun, c'est un atelier qui n'ecrit RIEN hors de ce qu'on lui demande.
        # Une bibliotheque n'a pas a toucher au dossier personnel de qui
        # l'importe parce que c'est pratique pour l'application.
        self.dossier = pathlib.Path(dossier) if dossier else DOSSIER_DEFAUT
        self.memoire = bool(dossier) if memoire is None else bool(memoire)
        self.table_bricklink = table_bricklink
        self.table_elements = table_elements
        self._notes: Dict[str, str] = {}
        if self.memoire:
            self._relire()
        self._resultats: "OrderedDict[str, Dict[str, bytes]]" = OrderedDict()
        self._verrou = threading.Lock()

    def fabriquer(self, requete: dict) -> dict:
        """Corps de requete decode -> reponse a serialiser. Leve ValueError.

        Aucune entree n'est reputee valide : la requete vient du reseau, meme
        sur une boucle locale.
        """
        photo = _decoder(requete.get("photo"), "photo")
        if photo is None:
            raise ValueError("aucune photo")
        carte = _decoder(requete.get("carte_profondeur"), "carte de profondeur")
        reglages = _reglages(requete.get("reglages") or {})

        # Les deux catalogues sont pris ENSEMBLE : sans cela, une fabrication
        # qui tombe pile pendant un remplacement pourrait employer le nouveau
        # catalogue d'elements avec l'ancienne table de couleurs.
        with self._verrou:
            table_bricklink = self.table_bricklink
            table_elements = self.table_elements

        resultat = run(
            photo, reglages,
            palette=self.palette,
            palette_complete=self.palette_complete,
            carte_profondeur=carte,
            table_bricklink=table_bricklink,
            table_elements=table_elements,
            note_palette=self.note_palette,
        )

        jeton = secrets.token_urlsafe(16)
        with self._verrou:
            self._resultats[jeton] = dict(resultat.fichiers)
            while len(self._resultats) > RESULTATS_GARDES:
                self._resultats.popitem(last=False)

        apercus = {
            nom: "data:image/png;base64," + base64.b64encode(contenu).decode()
            for nom, contenu in resultat.fichiers.items()
            if nom.endswith(".png")
        }
        return {
            "jeton": jeton,
            "journal": [{"flux": flux, "texte": texte}
                        for flux, texte in resultat.journal],
            "mesures": dict(resultat.mesures),
            "apercus": apercus,
            "fichiers": sorted(resultat.fichiers),
        }

    # ---------------------------------------------------------------- #
    # Les catalogues de commande
    # ---------------------------------------------------------------- #

    def etat_palette(self) -> dict:
        """Combien de couleurs, et d'ou elles viennent."""
        return {
            "couleurs": len(self.palette_complete),
            "commandables": len(self.palette),
            "provisoire": self.note_palette is not None
                          and self.note_palette[0] == "alerte",
        }

    def installer_palette(self) -> dict:
        """Telecharge la palette officielle et l'adopte, sans redemarrer.

        L'adresse n'est jamais fournie par la page : elle est fixee ici. Une
        URL qui viendrait du reseau ferait de ce serveur un relais pour aller
        chercher n'importe quoi a la place de qui l'heberge.
        """
        chemin, complete = palette_module.installer_palette()
        with self._verrou:
            self.palette_complete = complete
            self.palette = complete.solids_only()
            self.note_palette = (
                "info",
                f"  palette : {len(complete)} couleurs lues dans {chemin}, "
                f"{len(self.palette)} commandables en tuile")
        return self.etat_palette()

    def etat_catalogues(self) -> dict:
        """Ce que la page doit savoir pour dire ou en est la commande."""
        etat = {
            "palette": self.etat_palette(),
            "dossier": str(self.dossier) if self.memoire else None,
            "elements": None,
            "bricklink": None,
        }
        if self.table_elements:
            etat["elements"] = {
                "references": len(self.table_elements),
                "cle": self.table_elements.cle,
                "note": self._notes.get("elements", ""),
            }
        if self.table_bricklink:
            etat["bricklink"] = {
                "couleurs": len(self.table_bricklink),
                "note": self._notes.get("bricklink", ""),
            }
        return etat

    def definir_catalogues(self, requete: dict) -> dict:
        """Lit les catalogues deposes dans la page. Leve ValueError.

        Tout ou rien : si la lecture echoue, l'etat precedent est intact. Un
        catalogue a moitie remplace serait pire que pas de catalogue du tout —
        on croirait pouvoir commander.
        """
        brut = {}
        for nom in CATALOGUES:
            octets = _decoder(requete.get(nom), nom)
            if octets is not None:
                brut[nom] = pickabrick.decompresser(octets)
        if not brut:
            raise ValueError("aucun catalogue depose")

        if "elements_couleurs" in brut and "elements" not in brut:
            raise ValueError(
                "la table de couleurs accompagne un catalogue d'elements : "
                "deposez les deux ensemble"
            )

        table_elements, note_elements = self.table_elements, None
        if "elements" in brut:
            noms = (pickabrick.read_color_names(brut["elements_couleurs"])
                    if "elements_couleurs" in brut else None)
            table_elements = pickabrick.read_elements(
                brut["elements"], noms, pieces=pickabrick.PIECES_UTILES)
            # La note ne repete pas le nombre, qui est deja rendu a part :
            # elle ne porte que ce que le nombre ne dit pas.
            ecartees = table_elements.lignes_ecartees
            note_elements = (
                f"{ecartees} ligne{'s' if ecartees > 1 else ''} "
                f"ecartee{'s' if ecartees > 1 else ''}, hors des pieces "
                "employees ici" if ecartees else "catalogue lu en entier"
            )

        table_bricklink, note_bricklink = self.table_bricklink, None
        if "bricklink" in brut:
            table_bricklink, orphelines = bricklink.read_color_map(
                brut["bricklink"], self.palette_complete)
            note_bricklink = (
                f"{len(orphelines)} couleur"
                f"{'s' if len(orphelines) > 1 else ''} sans equivalent"
                if orphelines else "toute la palette est couverte"
            )

        # Rien n'est pose avant que TOUT ait ete lu sans erreur. Sous verrou :
        # le serveur est multi-fil, et une fabrication en cours doit voir les
        # anciens catalogues ou les nouveaux, jamais un melange des deux.
        with self._verrou:
            self.table_elements = table_elements
            self.table_bricklink = table_bricklink
            if note_elements:
                self._notes["elements"] = note_elements
            if note_bricklink:
                self._notes["bricklink"] = note_bricklink
        if self.memoire:
            self._ecrire()
        return self.etat_catalogues()

    def oublier_catalogues(self) -> dict:
        """Efface ce qui est retenu, memoire et disque."""
        with self._verrou:
            self.table_elements = None
            self.table_bricklink = None
            self._notes.clear()
        if self.memoire:
            for nom in ("elements.tsv", "bricklink.csv"):
                try:
                    (self.dossier / nom).unlink()
                except OSError:
                    pass
        return self.etat_catalogues()

    def _ecrire(self) -> None:
        """Ecrit ce qu'on a RETENU, pas le catalogue d'origine.

        Deux raisons, et la seconde compte plus que la premiere. La taille :
        un catalogue complet fait des megaoctets dont on garde trente
        references. Et la forme : ce qu'on ecrit designe ses couleurs par leur
        NOM ou par leur identifiant LEGO, jamais par un numero de systeme — le
        second fichier n'est donc plus necessaire au redemarrage, et le fichier
        garde se relit par le meme lecteur que n'importe quel autre catalogue.
        """
        try:
            self.dossier.mkdir(parents=True, exist_ok=True)
            if self.table_elements:
                colonne = ("lego_color_id" if self.table_elements.cle == "lego"
                           else "color_name")
                lignes = [f"element_id\tdesign_id\t{colonne}"]
                for (piece, couleur), element in sorted(
                        self.table_elements.entrees.items()):
                    lignes.append(f"{element}\t{piece}\t{couleur}")
                (self.dossier / "elements.tsv").write_text(
                    "\n".join(lignes) + "\n", encoding="utf-8")
            if self.table_bricklink:
                lignes = [f"{ldraw},{bl}" for ldraw, bl
                          in sorted(self.table_bricklink.items())]
                (self.dossier / "bricklink.csv").write_text(
                    "\n".join(lignes) + "\n", encoding="utf-8")
        except OSError:
            # Ne pas pouvoir ecrire n'empeche pas de travailler : la session en
            # cours garde ses catalogues, seule la prochaine les redemandera.
            self.memoire = False

    def _relire(self) -> None:
        """Reprend ce qui avait ete retenu. Un fichier abime est ignore."""
        chemin = self.dossier / "elements.tsv"
        if self.table_elements is None and chemin.is_file():
            try:
                self.table_elements = pickabrick.read_elements(
                    chemin.read_text(encoding="utf-8"))
                self._notes["elements"] = "retenues d'une session precedente"
            except (OSError, ValueError):
                pass
        chemin = self.dossier / "bricklink.csv"
        if self.table_bricklink is None and chemin.is_file():
            try:
                self.table_bricklink, _ = bricklink.read_color_map(
                    chemin.read_text(encoding="utf-8"))
                self._notes["bricklink"] = "retenues d'une session precedente"
            except (OSError, ValueError):
                pass

    def fichier(self, jeton: str, nom: str) -> bytes:
        """Un seul fichier d'un resultat. Leve KeyError.

        Le nom est cherche dans le dictionnaire du resultat, jamais employe
        comme chemin : il ne peut designer que ce qui a ete fabrique.
        """
        with self._verrou:
            return self._resultats[jeton][nom]

    def conseiller(self, requete: dict) -> dict:
        """Met quatre formats en balance sur CETTE photo. Leve ValueError.

        La reponse porte un apercu par format : un ecart de 0,61 delta E ne dit
        rien a personne, une vignette si.
        """
        photo = _decoder(requete.get("photo"), "photo")
        if photo is None:
            raise ValueError("aucune photo")
        reglages = _reglages(requete.get("reglages") or {})
        image = lire_image(photo)
        hauteur = reglages.hauteur or max(
            1, round(reglages.studs * image.height / image.width))
        with self._verrou:
            palette = self.palette
        conseils = conseil_de_format(image, reglages.studs, hauteur, palette,
                                     reglages)
        return {"formats": [
            {"studs_x": c["studs_x"], "studs_y": c["studs_y"],
             "largeur_cm": c["largeur_cm"], "hauteur_cm": c["hauteur_cm"],
             "pieces": c["pieces"], "detail": round(c["detail"], 2),
             "apercu": "data:image/png;base64,"
                       + base64.b64encode(c["apercu"]).decode(),
             "detail_vu": "data:image/png;base64,"
                          + base64.b64encode(c["detail_vu"]).decode()}
            for c in conseils]}

    def archive(self, jeton: str) -> bytes:
        """Le dossier complet, en ZIP. Leve KeyError si le jeton a expire."""
        with self._verrou:
            fichiers = self._resultats[jeton]
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
            for nom, contenu in sorted(fichiers.items()):
                archive.writestr(nom, contenu)
        return tampon.getvalue()


def _decoder(valeur, quoi: str) -> Optional[bytes]:
    if not valeur:
        return None
    if not isinstance(valeur, str):
        raise ValueError(f"{quoi} : chaine base64 attendue")
    # Le navigateur envoie une data-URI complete ; on n'en garde que la charge.
    if "," in valeur[:64] and valeur.startswith("data:"):
        valeur = valeur.split(",", 1)[1]
    try:
        return base64.b64decode(valeur, validate=True)
    except Exception:
        raise ValueError(f"{quoi} : base64 illisible") from None


def _reglages(brut: dict) -> Reglages:
    """Construit des `Reglages` a partir de JSON. Refuse plutot que corriger.

    `Reglages.__post_init__` valide les valeurs ; ici on ne s'occupe que des
    TYPES, parce qu'un navigateur envoie tout en chaine et qu'une chaine vide
    ne veut pas dire zero.
    """
    if not isinstance(brut, dict):
        raise ValueError("reglages : objet attendu")
    def entier(nom, defaut):
        valeur = brut.get(nom)
        if valeur in (None, ""):
            return defaut
        try:
            return int(valeur)
        except (TypeError, ValueError):
            raise ValueError(f"{nom} : nombre entier attendu") from None
    def texte(nom, defaut):
        valeur = brut.get(nom)
        return defaut if valeur in (None, "") else str(valeur)
    try:
        return Reglages(
            studs=entier("studs", 48),
            hauteur=entier("hauteur", None),
            relief=entier("relief", 0),
            references=texte("references", "standard"),
            tramage=texte("tramage", "aucun"),
            couleurs=texte("couleurs", None),
            tolerance=float(brut.get("tolerance") or 1.0),
            cadrage=texte("cadrage", "auto"),
            seuils=texte("seuils", "otsu"),
            codes_couleur=texte("codes_couleur", None),
            profondeur_inversee=bool(brut.get("profondeur_inversee")),
            relief_inverse=bool(brut.get("relief_inverse")),
            lignes_par_page=entier("lignes_par_page", 4),
            sections=entier("sections", 0),
            cadre=entier("cadre", 2),
            debruitage=float(brut.get("debruitage") or 4.0),
            cadre_couleur=entier("cadre_couleur", 0),
            titre=texte("titre", "mosaique"),
        )
    except (TypeError, ValueError) as raison:
        raise ValueError(str(raison)) from None


_TYPES = {
    ".csv": "text/csv; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".json": "application/json; charset=utf-8",
    ".ldr": "text/plain; charset=utf-8",
}


def _type_mime(nom: str) -> str:
    for extension, type_mime in _TYPES.items():
        if nom.endswith(extension):
            return type_mime
    return "application/octet-stream"


class _Gestionnaire(BaseHTTPRequestHandler):
    """Le transport, et rien d'autre. Toute la logique est dans `Atelier`."""

    atelier: Atelier = None  # pose par `creer_serveur`
    server_version = "BrickForge"
    sys_version = ""

    def log_message(self, format, *args):  # pragma: no cover - bruit
        pass

    def _repondre(self, code: int, type_mime: str, corps: bytes,
                  entetes: Tuple[Tuple[str, str], ...] = ()):
        self.send_response(code)
        self.send_header("Content-Type", type_mime)
        self.send_header("Content-Length", str(len(corps)))
        # La page n'a aucune ressource externe : on l'interdit explicitement,
        # de sorte qu'une modification distraite ne puisse pas en introduire.
        #
        # `connect-src 'self'` n'est pas une concession : sans lui, la page ne
        # peut pas appeler SON PROPRE serveur, et le bouton ne fait rien. Le
        # defaut etait present et invisible — vingt tests passaient, parce
        # qu'aucun n'executait le JavaScript de la page.
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; img-src data:; "
                         "connect-src 'self'; form-action 'none'; "
                         "style-src 'unsafe-inline'; script-src 'unsafe-inline'")
        for nom, valeur in entetes:
            self.send_header(nom, valeur)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corps)

    def _erreur(self, code: int, message: str):
        self._repondre(code, "application/json; charset=utf-8",
                       json.dumps({"erreur": message}).encode("utf-8"))

    def do_GET(self):
        chemin = self.path.split("?", 1)[0]
        if chemin in ("/", "/index.html"):
            self._repondre(200, "text/html; charset=utf-8", PAGE.encode("utf-8"))
            return
        if chemin == "/catalogues":
            self._repondre(200, "application/json; charset=utf-8",
                           json.dumps(self.atelier.etat_catalogues())
                           .encode("utf-8"))
            return
        if chemin.startswith("/fichier/"):
            reste = unquote(chemin[len("/fichier/"):])
            jeton, _, nom = reste.partition("/")
            try:
                contenu = self.atelier.fichier(jeton, nom)
            except KeyError:
                self._erreur(404, "fichier inconnu ou resultat expire")
                return
            self._repondre(
                200, _type_mime(nom), contenu,
                (("Content-Disposition",
                  'attachment; filename="%s"' % nom.replace("/", "_")),),
            )
            return
        if chemin.startswith("/telecharger/") and chemin.endswith(".zip"):
            jeton = chemin[len("/telecharger/"):-len(".zip")]
            try:
                archive = self.atelier.archive(jeton)
            except KeyError:
                self._erreur(404, "resultat expire : refabriquez la mosaique")
                return
            self._repondre(
                200, "application/zip", archive,
                (("Content-Disposition",
                  'attachment; filename="mosaique_lego.zip"'),),
            )
            return
        self._erreur(404, "page inconnue")

    do_HEAD = do_GET

    def do_POST(self):
        chemin = self.path.split("?", 1)[0]
        if chemin == "/palette":
            try:
                reponse = self.atelier.installer_palette()
            except Exception as raison:
                self._erreur(502, str(raison).splitlines()[0])
                return
            self._repondre(200, "application/json; charset=utf-8",
                           json.dumps(reponse).encode("utf-8"))
            return
        if chemin not in ("/fabriquer", "/catalogues", "/conseil"):
            self._erreur(404, "page inconnue")
            return
        try:
            taille = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._erreur(400, "longueur illisible")
            return
        if taille <= 0:
            self._erreur(400, "corps vide")
            return
        if taille > TAILLE_MAXIMALE:
            self._erreur(413, f"corps trop grand ({taille} octets, maximum "
                              f"{TAILLE_MAXIMALE})")
            return
        corps = self.rfile.read(taille)
        try:
            requete = json.loads(corps.decode("utf-8"))
        except Exception:
            self._erreur(400, "JSON illisible")
            return
        if not isinstance(requete, dict):
            self._erreur(400, "objet JSON attendu")
            return
        if chemin == "/catalogues":
            try:
                if requete.get("oublier"):
                    reponse = self.atelier.oublier_catalogues()
                else:
                    reponse = self.atelier.definir_catalogues(requete)
            except ValueError as raison:
                self._erreur(400, str(raison))
                return
            self._repondre(200, "application/json; charset=utf-8",
                           json.dumps(reponse).encode("utf-8"))
            return
        if chemin == "/conseil":
            try:
                reponse = self.atelier.conseiller(requete)
            except ValueError as raison:
                self._erreur(400, str(raison))
                return
            self._repondre(200, "application/json; charset=utf-8",
                           json.dumps(reponse).encode("utf-8"))
            return
        try:
            reponse = self.atelier.fabriquer(requete)
        except ModeleRefuse as refus:
            self._erreur(422, str(refus) + "".join(
                f"\n   {v.invariant} : {v.detail}" for v in refus.violations[:6]))
            return
        except ValueError as raison:
            self._erreur(400, str(raison))
            return
        except MemoryError:  # pragma: no cover - depend de la machine
            self._erreur(507, "memoire insuffisante : reduisez la taille")
            return
        self._repondre(200, "application/json; charset=utf-8",
                       json.dumps(reponse).encode("utf-8"))


def creer_serveur(adresse: str = "127.0.0.1", port: int = 8000,
                  atelier: Optional[Atelier] = None) -> ThreadingHTTPServer:
    """Serveur pret a servir. `port=0` en attribue un libre — pratique en test."""
    gestionnaire = type("_GestionnaireLie", (_Gestionnaire,),
                        {"atelier": atelier or Atelier()})
    return ThreadingHTTPServer((adresse, port), gestionnaire)


def servir(adresse: str = "127.0.0.1", port: int = 8000,
           atelier: Optional[Atelier] = None) -> None:  # pragma: no cover
    serveur = creer_serveur(adresse, port, atelier)
    try:
        serveur.serve_forever()
    finally:
        serveur.server_close()
