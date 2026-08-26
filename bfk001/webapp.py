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
import secrets
import threading
import zipfile
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional, Tuple

from .palette import Palette
from .pipeline import ModeleRefuse, Reglages, palette_utilisable, run

__all__ = ["PAGE", "Atelier", "servir", "creer_serveur", "TAILLE_MAXIMALE"]

TAILLE_MAXIMALE = 64 * 1024 * 1024
"""Corps de requete accepte, en octets. Une photo de telephone en base64 pese
environ 7 Mo ; soixante-quatre laissent de la marge pour une photo d'appareil
et sa carte de profondeur, et bornent ce qu'un client peut faire allouer."""

RESULTATS_GARDES = 8
"""Nombre de resultats gardes en memoire pour le telechargement. Au-dela, le
plus ancien est oublie : un atelier ouvert une journee ne doit pas accumuler
des dizaines de mosaiques de plusieurs mega-octets."""


PAGE = r"""<!doctype html>
<html lang="fr">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BrickForge — une photo, une mosaique LEGO Art</title>
<style>
  :root {
    --encre: #16181d; --papier: #f7f7f5; --carte: #ffffff;
    --trait: #dcdcd6; --doux: #6b6f76; --vif: #b4361c; --ok: #1f7a4d;
  }
  @media (prefers-color-scheme: dark) {
    :root { --encre:#e9e9e6; --papier:#15171b; --carte:#1d2026;
            --trait:#31353d; --doux:#9aa0a8; --vif:#e2704f; --ok:#5fbb8a; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--papier); color:var(--encre);
         font:15px/1.55 ui-sans-serif, system-ui, -apple-system, Segoe UI,
              Roboto, Helvetica, Arial, sans-serif; }
  header { padding:28px 24px 8px; max-width:1180px; margin:0 auto; }
  h1 { font-size:22px; margin:0 0 4px; letter-spacing:-.01em; }
  header p { margin:0; color:var(--doux); font-size:14px; }
  main { display:grid; grid-template-columns:340px 1fr; gap:22px;
         max-width:1180px; margin:0 auto; padding:18px 24px 60px; }
  @media (max-width: 900px) { main { grid-template-columns:1fr; } }
  .carte { background:var(--carte); border:1px solid var(--trait);
           border-radius:10px; padding:16px; }
  #zone { border:2px dashed var(--trait); border-radius:10px; padding:26px 14px;
          text-align:center; cursor:pointer; transition:border-color .15s; }
  #zone.actif { border-color:var(--vif); }
  #zone strong { display:block; margin-bottom:4px; }
  #zone span { color:var(--doux); font-size:13px; }
  #vignette { max-width:100%; max-height:160px; border-radius:6px; margin-top:12px; }
  label { display:block; margin:14px 0 4px; font-size:13px; font-weight:600; }
  .aide { font-weight:400; color:var(--doux); display:block; font-size:12px;
          margin-top:2px; }
  input[type=number], select, input[type=text] {
    width:100%; padding:7px 9px; border:1px solid var(--trait); border-radius:6px;
    background:var(--papier); color:var(--encre); font:inherit; font-size:14px; }
  .ligne { display:flex; gap:8px; align-items:center; }
  .ligne input[type=checkbox] { width:auto; }
  button { width:100%; margin-top:18px; padding:11px; border:0; border-radius:8px;
           background:var(--encre); color:var(--papier); font:inherit;
           font-weight:600; cursor:pointer; }
  button:disabled { opacity:.5; cursor:default; }
  .secondaire { background:var(--ok); }
  #resultat { display:none; }
  #onglets { display:flex; gap:6px; margin-bottom:10px; flex-wrap:wrap; }
  #onglets button { width:auto; margin:0; padding:6px 12px; font-size:13px;
                    font-weight:500; background:transparent; color:var(--doux);
                    border:1px solid var(--trait); }
  #onglets button[aria-selected=true] { background:var(--encre);
                    color:var(--papier); border-color:var(--encre); }
  #rendu { width:100%; image-rendering:pixelated; border-radius:8px;
           border:1px solid var(--trait); background:var(--papier); }
  .chiffres { display:grid; grid-template-columns:repeat(auto-fit,minmax(132px,1fr));
              gap:10px; margin:16px 0; }
  .chiffre { border:1px solid var(--trait); border-radius:8px; padding:9px 11px; }
  .chiffre b { display:block; font-size:18px; letter-spacing:-.02em;
               white-space:nowrap; }
  .chiffre span { color:var(--doux); font-size:12px; }
  pre { white-space:pre-wrap; word-break:break-word; font-size:12.5px;
        line-height:1.5; margin:0; font-family:ui-monospace, SFMono-Regular,
        Menlo, Consolas, monospace; }
  pre .alerte { color:var(--vif); }
  #etat { margin-top:12px; font-size:13px; color:var(--doux); min-height:20px; }
  #etat.erreur { color:var(--vif); }
  details { margin-top:14px; }
  summary { cursor:pointer; font-size:13px; color:var(--doux); }
</style>

<header>
  <h1>BrickForge</h1>
  <p>Une photo, une mosaique LEGO Art : le modele, la liste de courses et la
     notice de montage. Rien n'est livre qui ne tienne debout.</p>
</header>

<main>
  <form class="carte" id="formulaire">
    <div id="zone">
      <strong>Deposez une photo</strong>
      <span>ou cliquez — JPEG, PNG ou PPM</span>
      <img id="vignette" hidden alt="">
    </div>
    <input type="file" id="fichier" accept="image/*" hidden>

    <label>Taille en tenons
      <span class="aide">48 est le format des sets LEGO Art (38 cm).</span>
      <input type="number" id="studs" value="48" min="2" max="192" step="1">
    </label>

    <label>Hauteur
      <span class="aide">Vide : les proportions de la photo sont gardees.</span>
      <input type="number" id="hauteur" placeholder="auto" min="2" max="192">
    </label>

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
      <label>Carte de profondeur (facultatif)
        <span class="aide">Une carte mesuree — MiDaS, Depth Anything — remplace
          la convention « clair = haut ». Sans elle, une carte deja presente
          dans le JPEG est lue automatiquement.</span>
      </label>
      <input type="file" id="carte" accept="image/*">
      <div class="ligne" style="margin-top:8px">
        <input type="checkbox" id="inversee">
        <label for="inversee" style="margin:0; font-weight:400">
          la carte encode une distance (proche = sombre)</label>
      </div>
    </div>

    <label>Jeu de tuiles
      <select id="references">
        <option value="standard">standard — 1x1, 1x2, 1x4</option>
        <option value="minimal">minimal — 1x1 seule, grille reguliere</option>
        <option value="large">large — jusqu'a 1x8, moins de pieces</option>
        <option value="art">art — tuiles rondes, prix plein</option>
      </select>
    </label>

    <details>
      <summary>Reglages fins</summary>
      <label>Tramage
        <select id="tramage">
          <option value="auto">auto — decide par image</option>
          <option value="aucun">aucun</option>
          <option value="complet">complet</option>
          <option value="adaptatif">adaptatif</option>
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
      <label>Seuils du relief
        <select id="seuils">
          <option value="otsu">Otsu — sur les contours</option>
          <option value="uniform">uniforme — en parts egales</option>
        </select>
      </label>
    </details>

    <button type="submit" id="lancer" disabled>Fabriquer la mosaique</button>
    <div id="etat"></div>
  </form>

  <section>
    <div class="carte" id="resultat">
      <div id="onglets"></div>
      <img id="rendu" alt="Apercu de la mosaique">
      <div class="chiffres" id="chiffres"></div>
      <a id="telecharger" download><button type="button" class="secondaire">
        Telecharger le dossier complet (ZIP)</button></a>
      <details open style="margin-top:16px">
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

  function montrer(nom) {
    onglet = nom;
    document.getElementById('rendu').src = apercus[nom];
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

  document.getElementById('formulaire').addEventListener('submit', function (e) {
    e.preventDefault();
    if (!photo) return;
    lancer.disabled = true;
    etat.className = '';
    etat.textContent = 'Fabrication en cours — quelques secondes a une minute '
      + 'selon la taille. Les six invariants du noyau sont verifies avant '
      + 'toute livraison.';
    var debut = Date.now();

    fetch('/fabriquer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        photo: photo,
        carte_profondeur: carte,
        reglages: {
          studs: valeur('studs'),
          hauteur: valeur('hauteur'),
          relief: valeur('relief'),
          references: valeur('references'),
          tramage: valeur('tramage'),
          couleurs: valeur('couleurs'),
          cadrage: valeur('cadrage'),
          seuils: valeur('seuils'),
          profondeur_inversee: document.getElementById('inversee').checked,
          titre: (champ.files[0] || {}).name || 'mosaique'
        }
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
      Object.keys(apercus).sort().forEach(function (nom) {
        var b = document.createElement('button');
        b.type = 'button'; b.dataset.nom = nom;
        b.textContent = TITRES[nom] || nom;
        b.addEventListener('click', function () { montrer(nom); });
        onglets.appendChild(b);
      });
      montrer(apercus['apercu.png'] ? 'apercu.png' : Object.keys(apercus)[0]);

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

      document.getElementById('telecharger').href =
        '/telecharger/' + reponse.jeton + '.zip';
      document.getElementById('resultat').style.display = 'block';
      etat.textContent = 'Termine en '
        + ((Date.now() - debut) / 1000).toFixed(1) + ' s.';
    }).catch(function (raison) {
      etat.className = 'erreur';
      etat.textContent = String(raison.message || raison);
    }).finally(function () {
      lancer.disabled = false;
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
                 note_palette: Optional[Tuple[str, str]] = None):
        if palette is None:
            complete, note_palette = palette_utilisable()
            palette_complete = complete
            palette = (complete if note_palette[0] == "alerte"
                       else complete.solids_only())
        self.palette = palette
        self.palette_complete = palette_complete or palette
        self.note_palette = note_palette
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

        resultat = run(
            photo, reglages,
            palette=self.palette,
            palette_complete=self.palette_complete,
            carte_profondeur=carte,
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
            tramage=texte("tramage", "auto"),
            couleurs=texte("couleurs", None),
            tolerance=float(brut.get("tolerance") or 1.0),
            cadrage=texte("cadrage", "auto"),
            seuils=texte("seuils", "otsu"),
            codes_couleur=texte("codes_couleur", None),
            profondeur_inversee=bool(brut.get("profondeur_inversee")),
            lignes_par_page=entier("lignes_par_page", 4),
            titre=texte("titre", "mosaique"),
        )
    except (TypeError, ValueError) as raison:
        raise ValueError(str(raison)) from None


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
        if self.path.split("?", 1)[0] != "/fabriquer":
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
