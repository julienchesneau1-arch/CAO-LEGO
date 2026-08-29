"""Le meme atelier, mais ouvert a des gens qu'on ne connait pas.

`webapp` sert un atelier sur la boucle locale. Trois hypotheses y tiennent
sans etre ecrites : il n'y a qu'un utilisateur, il repond de la machine, et ce
qu'il demande, il a le droit de le demander. Heberger casse les trois d'un
coup, et aucune ne se rattrape par un reglage.

Ce module ne refait pas l'atelier : c'est une POLITIQUE posee devant lui.
Sans lui, `webapp` se comporte exactement comme avant ; avec lui, chaque
requete passe par trois questions — qui, combien, et pour qui.

Ce qui a ete MESURE, parce que tout le reste en decoule
-------------------------------------------------------
Chaine complete, photo synthetique 512 x 512, du carre de 32 tenons a celui
de 200, temps processeur et pointe de memoire du processus :

    32 x 32      1 024 tenons     0,7 s      31 Mo     0,8 Mo de sortie
    64 x 64      4 096 tenons     2,2 s      50 Mo     2,7 Mo
    96 x 96      9 216 tenons     5,4 s      81 Mo     5,8 Mo
   128 x 128    16 384 tenons     9,8 s     127 Mo     9,4 Mo
   200 x 200    40 000 tenons    23,6 s     254 Mo    19,9 Mo
   500 x 500   250 000 tenons   278,2 s   2 315 Mo   104,2 Mo

La derniere ligne est le PLAFOND que la chaine accepte aujourd'hui, et elle a
ete mesuree, pas extrapolee. Il fallait la mesurer : une droite ajustee sur les
cinq premieres lignes annonce 163 s et 1,6 Go, et la mesure donne 278 s et
2,3 Go. Le cout n'est pas lineaire, il est lineaire PLUS quelque chose, et ce
quelque chose se paie au moment ou l'on a le moins de marge. Les pentes
retenues plus bas sont donc celles du HAUT du tableau, pas la moyenne.

Et ce que ces chiffres decident
-------------------------------
Une seule requete de quelques kilo-octets peut demander six minutes et demie de
calcul et trois giga-octets et demi de memoire. Un visiteur, une requete, et la
machine est prise pour tout le monde.

C'est la raison d'etre de ce module. C'est aussi ce qui exclut le sans-serveur
avant meme d'essayer : aucune fonction hebergee ne tient quatre minutes ni deux
giga-octets et demi. Un conteneur, oui ; une fonction, non. Le plafond local n'est donc
pas transposable — il est recalcule ici sur la memoire que le conteneur a
REELLEMENT le droit de prendre.

Ce que la parallelisation n'apporte pas
---------------------------------------
Trois carres de 96 tenons fabriques en meme temps, sur quatre coeurs :

    1 a la fois    8,3 s chacune     0,120 mosaique/s
    2 a la fois   17,8 s chacune     0,112 mosaique/s
    4 a la fois   37,2 s chacune     0,107 mosaique/s

Le debit BAISSE. La chaine est du Python pur : le verrou global la serialise,
et les fils n'ajoutent que du changement de contexte. Deux places de
fabrication ne serviraient donc pas deux visiteurs deux fois plus vite — elles
tiendraient deux pointes de memoire en meme temps pour rendre les deux
reponses deux fois plus tard. Une seule place, et un refus immediat et dit
plutot qu'une attente muette.

Ce que ce module ne fait pas
----------------------------
Il ne chiffre rien. Le lien qui porte la cle doit etre en HTTPS, et c'est
l'hebergeur qui le termine : `Secure` sur le temoin le dit au navigateur, mais
un serveur ne peut pas se proteger d'etre expose en clair par qui l'installe.
"""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional, Tuple
from urllib.parse import unquote_plus

__all__ = [
    "CPU_PAR_TENON", "MEMOIRE_PAR_TENON", "MEMOIRE_DE_BASE", "SORTIE_PAR_TENON",
    "TENONS_PLANCHER", "PART_DE_MEMOIRE", "DUREE_ACCEPTABLE",
    "CPU_ETALON_TENONS", "CPU_ETALON_SECONDES", "RAPPORT_HAUT_SUR_ETALON",
    "calibrer", "memoire_du_conteneur", "plafond_de_tenons",
    "plafond_par_memoire", "plafond_par_duree", "duree_annoncee",
    "adresse_du_visiteur",
    "Debit", "Occupe", "Visite", "Accueil", "Hebergement", "PAGE_CLE",
]


# --------------------------------------------------------------------- #
# Les constantes mesurees. Elles ne sont pas des reglages : les changer
# sans refaire la mesure ci-dessus rend le plafond faux, et un plafond faux
# se paie par un processus tue en plein calcul, sans message.
# --------------------------------------------------------------------- #

CPU_PAR_TENON = 1.15e-3
"""Secondes de calcul par tenon, au taux le PIRE du tableau (278,2 s / 250 000),
SUR LA MACHINE DE MESURE.

Le taux varie de 0,54 ms au milieu du tableau a 1,11 ms au plafond. Prendre la
moyenne donnerait un plafond de duree trop genereux exactement la ou la marge
manque. Prendre le pire donne une annonce trop longue sur les petites
mosaiques, ce que personne ne reproche jamais a un logiciel.

Mais surtout : contrairement a la memoire, CE CHIFFRE N'EST PAS UNE PROPRIETE
DU LOGICIEL. Les memes mesures refaites sur une seconde machine du meme
environnement ont donne la colonne memoire a l'octet pres — 135 Mo, 217 Mo,
identiques — et la colonne temps multipliee par 1,8. Le plafond de duree
calcule avec la constante ci-dessous y serait donc faux de 80 %.

C'est pourquoi `calibrer()` existe et pourquoi le lanceur heberge l'appelle :
cette valeur n'est que le DEFAUT, celui de la machine de mesure.
"""

CPU_ETALON_TENONS = 1024
"""Taille de la mosaique d'etalonnage : 32 x 32.

Assez pour que la chaine entiere soit parcourue — quantification, substrat,
collision, notice, PDF —, assez petite pour que le demarrage n'en souffre pas :
1,2 s sur la machine de mesure, 1,9 s sur la seconde.
"""

CPU_ETALON_SECONDES = 0.7
"""Ce que l'etalon a coute sur la machine de mesure."""

RAPPORT_HAUT_SUR_ETALON = 1.7
"""De combien le cout par tenon monte entre l'etalon et le plafond.

1,113 ms au plafond contre 0,684 ms a l'etalon, soit 1,63 ; arrondi au-dessus.

Ce rapport AUGMENTE a chaque optimisation : 1,33 au depart, 1,45 apres le memo
de verdicts, 1,63 apres le partage des formes. C'est logique et c'est meme le
signe que les optimisations portent — chacune retire de la chaine une part
quasi lineaire (des paires a juger, des objets a construire une fois par piece)
et laisse peser davantage ce qui croit plus vite. Un rapport sous-estime rend le plafond de duree trop genereux,
donc il est arrondi vers le haut, jamais vers le bas.

Ce rapport-la, lui, EST une propriete du logiciel : c'est la forme de la
courbe, pas sa hauteur. On mesure donc la hauteur sur la machine qui heberge,
et on lui applique la forme mesuree une fois ici.
"""


def calibrer(fabriquer: Optional[Callable[[int], float]] = None) -> float:
    """Secondes par tenon SUR CETTE MACHINE, au taux du haut de la gamme.

    Fabrique une petite mosaique, la chronometre, et corrige par le rapport
    mesure entre ce regime et celui du plafond. Deux secondes au demarrage,
    une fois, contre un plafond de duree faux pendant toute la vie du service.

    `fabriquer` est injectable pour que ce mecanisme se teste sans fabriquer.
    """
    if fabriquer is None:                    # pragma: no cover - fabrication
        def fabriquer(cote):
            import time as _t
            from . import write_png, Image
            from .pipeline import Reglages, run
            pixels = bytearray()
            for y in range(128):
                for x in range(128):
                    pixels += bytes(((x * 2) % 256, (y * 2) % 256,
                                     (x + y) % 256))
            photo = write_png(Image(128, 128, bytes(pixels)))
            depart = _t.process_time()
            run(photo, Reglages(studs=cote, hauteur=cote, titre="etalon"))
            return _t.process_time() - depart

    cote = int(CPU_ETALON_TENONS ** 0.5)
    mesure = fabriquer(cote)
    if mesure <= 0:
        return CPU_PAR_TENON
    return (mesure / CPU_ETALON_TENONS) * RAPPORT_HAUT_SUR_ETALON

MEMOIRE_PAR_TENON = 10240
"""Octets de pointe par tenon (10 ko), pente du HAUT du tableau.

Entre 16 384 et 40 000 tenons : 5,4 ko. Entre 40 000 et 250 000 : 9,8 ko.
C'est la seconde qui est retenue, et l'ecart entre les deux est precisement la
raison d'avoir mesure le plafond au lieu de le deduire — un plafond calcule
avec 10,7 ko autoriserait un tiers de tenons de trop, et un tiers de trop ne
donne pas une erreur : il donne un processus tue au milieu du calcul.

C'est une POINTE et non une moyenne : le maximum simultane du modele, de la
collision et de la notice. C'est bien ce chiffre-la qu'il faut, parce que c'est
celui que regarde le tueur de processus.
"""

MEMOIRE_DE_BASE = 64 * 1024 * 1024
"""Octets que le processus occupe avant toute fabrication.

Le tableau extrapole a zero tenon donne quarante mega-octets. Il en faut plus :
la palette, la page, les tampons du serveur et le decodage de la photo — qui,
elle, peut faire douze mega-pixels — vivent en dehors de la fabrication.
"""

SORTIE_PAR_TENON = 512
"""Octets de fichiers livres par tenon (19,9 Mo / 40 000 = 0,50 ko ;
104,2 Mo / 250 000 = 0,42 ko ; on garde le plus grand des deux).

Ce qui sort est GARDE en memoire pour le telechargement : c'est un cout qui
survit a la fabrication, et c'est lui qui borne le magasin de resultats.
"""

DUREE_ACCEPTABLE = 60.0
"""Secondes qu'une fabrication a le droit de prendre, hebergee.

Ce n'est pas une limite de calcul mais de PATIENCE, et elle a deux sources qui
tombent au meme endroit. Le visiteur : au-dela d'une minute devant une page qui
ne dit rien, il recharge — et recharger lance une seconde fabrication, ce qui
empire exactement ce qu'il fuyait. L'hebergeur : les passerelles coupent une
requete restee muette, souvent a trente ou soixante secondes, et la
fabrication continue alors pour personne.

C'est cette borne, et non la memoire, qui decide sur un conteneur d'un ou deux
giga-octets. En dessous, c'est la memoire.
"""

TENONS_PLANCHER = 1024
"""32 x 32. En dessous, ce n'est plus une mosaique mais une vignette.

Si la memoire du conteneur ne permet pas ce plafond-la, l'atelier ne demarre
pas : servir une application qui refuse tout ce qu'on lui demande est pire que
ne pas la servir.
"""

PART_DE_MEMOIRE = 0.55
"""Fraction de la memoire du conteneur allouee aux fabrications.

Le reste n'est pas de la marge de confort : c'est le socle d'interprete, les
resultats gardes pour le telechargement, les tampons du serveur, et le fait
qu'une pointe mesuree sur une photo synthetique n'est pas la pire des photos.
Un depassement ne donne pas une erreur : il donne un processus tue.
"""

DUREE_DE_SESSION = 4 * 3600.0
"""Secondes d'inactivite au bout desquelles un visiteur est oublie.

Assez pour fabriquer, regarder, refabriquer autrement et telecharger ; pas
assez pour qu'une journee d'ouverture accumule les ateliers d'inconnus.
"""

SESSIONS_MAXIMUM = 64
"""Visiteurs suivis simultanement. Au-dela, le plus ancien est oublie.

Une borne, pas une capacite d'accueil : elle existe pour qu'un flot de temoins
fabriques ne fasse pas grossir la memoire indefiniment.
"""


class Occupe(Exception):
    """Toutes les places de fabrication sont prises. Porte le delai a attendre."""

    def __init__(self, message: str, delai: int = 30):
        super().__init__(message)
        self.delai = delai


# --------------------------------------------------------------------- #
# La memoire dont on dispose vraiment
# --------------------------------------------------------------------- #

CHEMINS_CGROUP = (
    "/sys/fs/cgroup/memory.max",                        # cgroup v2
    "/sys/fs/cgroup/memory/memory.limit_in_bytes",      # cgroup v1
)

_SENTINELLE_CGROUP = 1 << 50
"""Au-dela, cgroup v1 ne dit pas une limite mais « aucune ».

Le fichier contient alors un nombre astronomique (2^63 arrondi a la page), et
le lire comme une limite ferait croire a un pentaoctet de memoire.
"""


def memoire_du_conteneur(lire: Optional[Callable[[str], str]] = None
                         ) -> Optional[int]:
    """Octets que ce processus a le droit d'employer, ou None si on l'ignore.

    `/proc/meminfo` et `free` disent la memoire de la MACHINE, pas celle que le
    conteneur a le droit de prendre. Sur un hebergeur, le premier chiffre est
    faux d'un facteur dix, et ce n'est pas une erreur qu'on lit : c'est un
    processus tue au milieu d'une fabrication, sans trace ni message. La limite
    vraie est celle du cgroup ; `/proc/meminfo` n'est qu'un dernier recours.

    `lire` est injectable pour que ce mecanisme se teste sans conteneur.
    """
    if lire is None:                                    # pragma: no cover - E/S
        def lire(chemin):
            with open(chemin, "r", encoding="utf-8") as fichier:
                return fichier.read()

    for chemin in CHEMINS_CGROUP:
        try:
            brut = lire(chemin).strip()
        except OSError:
            continue
        if brut == "max":                # v2, aucune limite posee
            break
        try:
            valeur = int(brut)
        except ValueError:
            continue
        if 0 < valeur < _SENTINELLE_CGROUP:
            return valeur
        break

    try:
        for ligne in lire("/proc/meminfo").splitlines():
            if ligne.startswith("MemTotal:"):
                return int(ligne.split()[1]) * 1024
    except (OSError, IndexError, ValueError):
        pass
    return None


def plafond_par_memoire(memoire: int, simultanees: int = 1,
                        part: float = PART_DE_MEMOIRE) -> int:
    """Surface au-dela de laquelle le conteneur manquerait de memoire.

    La division par `simultanees` n'est pas de la prudence : deux fabrications
    en cours occupent leur pointe EN MEME TEMPS. Un plafond calcule pour une
    seule et servi a deux est un plafond faux.
    """
    if simultanees < 1:
        raise ValueError("au moins une fabrication a la fois")
    disponible = memoire * part - MEMOIRE_DE_BASE
    if disponible <= 0:
        return 0
    return max(0, int(disponible / simultanees / MEMOIRE_PAR_TENON))


def plafond_par_duree(duree: float = DUREE_ACCEPTABLE,
                      simultanees: int = 1,
                      cpu_par_tenon: float = CPU_PAR_TENON) -> int:
    """Surface au-dela de laquelle la reponse arriverait trop tard.

    `cpu_par_tenon` vient de `calibrer()` chez qui heberge, et non de la
    constante : la vitesse est la seule chose mesuree ici qui change d'une
    machine a l'autre.

    `simultanees` divise, et pour une raison mesuree : le calcul est du Python
    pur, deux fabrications en parallele prennent chacune deux fois plus
    longtemps. Autoriser deux places ne double pas le service, il double
    l'attente.
    """
    if simultanees < 1:
        raise ValueError("au moins une fabrication a la fois")
    if cpu_par_tenon <= 0:
        raise ValueError("un cout par tenon est positif")
    return max(0, int(duree / simultanees / cpu_par_tenon))


def plafond_de_tenons(memoire: int, simultanees: int = 1,
                      part: float = PART_DE_MEMOIRE,
                      duree: float = DUREE_ACCEPTABLE,
                      cpu_par_tenon: float = CPU_PAR_TENON) -> int:
    """Le plus petit des deux plafonds : celui qui mord vraiment."""
    return min(plafond_par_memoire(memoire, simultanees, part),
               plafond_par_duree(duree, simultanees, cpu_par_tenon))


def duree_annoncee(tenons: int,
                   cpu_par_tenon: float = CPU_PAR_TENON) -> float:
    """Secondes a annoncer avant de lancer une fabrication de cette taille."""
    return tenons * cpu_par_tenon


# --------------------------------------------------------------------- #
# Qui appelle
# --------------------------------------------------------------------- #

def adresse_du_visiteur(entetes: Mapping[str, str], pair: str,
                        relais: int = 0) -> str:
    """L'adresse a laquelle imputer une requete.

    `X-Forwarded-For` est ecrit par le client autant que par les relais : le
    croire sans condition, c'est offrir a n'importe qui une adresse neuve a
    chaque requete, donc un compteur de debit remis a zero a volonte. On ne le
    lit que si l'on sait COMBIEN de relais se trouvent devant, et on prend
    alors le n-ieme en partant de la fin — les precedents viennent du client.

    `relais = 0` par defaut : sans configuration explicite, seule l'adresse du
    pair, celle que la pile TCP a constatee, fait foi.
    """
    if relais > 0:
        brut = entetes.get("X-Forwarded-For") or ""
        maillons = [m.strip() for m in brut.split(",") if m.strip()]
        if len(maillons) >= relais:
            return maillons[-relais]
    return pair


class Debit:
    """Seau a jetons : un visiteur peut lancer une rafale, pas un flot.

    Le compteur est borne en NOMBRE DE CLES autant qu'en jetons : sans cela,
    un visiteur qui change d'adresse a chaque requete ferait grossir le
    dictionnaire jusqu'a la memoire — le limiteur deviendrait l'attaque.
    """

    def __init__(self, jetons: int = 5, recharge: float = 30.0,
                 cles_maximum: int = 4096,
                 horloge: Callable[[], float] = time.monotonic):
        if jetons < 1:
            raise ValueError("au moins un jeton")
        if recharge <= 0:
            raise ValueError("une recharge dure un temps positif")
        self.jetons = jetons
        self.recharge = recharge
        self.cles_maximum = cles_maximum
        self._horloge = horloge
        self._seaux: "OrderedDict[str, Tuple[float, float]]" = OrderedDict()
        self._verrou = threading.Lock()

    def prendre(self, cle: str) -> Optional[float]:
        """None si le jeton est accorde, sinon les secondes a attendre."""
        maintenant = self._horloge()
        with self._verrou:
            reste, vu = self._seaux.get(cle, (float(self.jetons), maintenant))
            reste = min(float(self.jetons),
                        reste + (maintenant - vu) / self.recharge)
            refuse = reste < 1.0
            self._seaux[cle] = (reste if refuse else reste - 1.0, maintenant)
            self._seaux.move_to_end(cle)
            # La purge est faite dans LES DEUX cas. Ne la faire qu'au succes
            # laissait grossir le dictionnaire sans borne des lors que tout
            # etait refuse — c'est-a-dire exactement pendant une attaque.
            while len(self._seaux) > self.cles_maximum:
                self._seaux.popitem(last=False)
            return (1.0 - reste) * self.recharge if refuse else None


# --------------------------------------------------------------------- #
# Une requete, telle que la politique a besoin de la voir
# --------------------------------------------------------------------- #

@dataclass(frozen=True)
class Visite:
    """Ce qu'une requete apporte, sans le socket.

    Le gestionnaire HTTP fabrique cet objet et rien d'autre ne traverse : la
    politique se teste donc entierement sans ouvrir de port, comme l'atelier.
    """

    chemin: str
    methode: str
    pair: str
    entetes: Mapping[str, str] = field(default_factory=dict)
    requete: str = ""
    """La partie apres « ? », telle quelle."""


@dataclass
class Accueil:
    """Verdict : soit un atelier et des entetes, soit un refus."""

    atelier: object = None
    entetes: Tuple[Tuple[str, str], ...] = ()
    code: Optional[int] = None
    message: str = ""
    corps_html: Optional[str] = None
    """Present quand le refus doit se LIRE dans un navigateur plutot que se
    deserialiser : personne ne comprend un JSON affiche brut."""

    @property
    def termine(self) -> bool:
        """Vrai quand le gestionnaire doit repondre ceci et s'arreter.

        Un 303 qui pose le temoin n'est pas un refus, mais il termine la
        requete tout autant qu'un 401 : c'est la meme question pour qui repond.
        """
        return self.code is not None


# L'en-tete `Host` n'est PAS recopie ici. Il vient du client, et une page qui
# le reflete offre au premier venu d'injecter ce qu'il veut dans ce que lit le
# visiteur suivant. Le lien, celui qui le detient l'a deja.
PAGE_CLE = """<!doctype html><html lang="fr"><meta charset="utf-8">
<title>BrickForge — atelier prive</title>
<style>
 body{background:#12151a;color:#e8eaee;font:16px/1.6 system-ui,sans-serif;
      margin:0;display:grid;place-items:center;min-height:100vh}
 main{max-width:34rem;padding:2rem}
 h1{font-size:1.3rem;margin:0 0 1rem}
 p{color:#aab}
 code{background:#1c2029;padding:.1rem .4rem;border-radius:.3rem}
</style>
<main>
<h1>Cet atelier est prive.</h1>
<p>Il faut le lien complet, celui qui porte la cle&nbsp;:
<code>…/?cle=VOTRE_CLE</code></p>
<p>Ce n'est pas une formalite. Fabriquer une mosaique demande plusieurs
secondes de calcul et plusieurs centaines de mega-octets&nbsp;; sans cette
cle, n'importe qui pourrait prendre la machine a lui seul.</p>
</main></html>"""


class Hebergement:
    """La politique. Un objet, trois questions, aucune connaissance du reseau.

    - QUI : la cle ouvre une session, le temoin la porte ensuite.
    - COMBIEN : un plafond de tenons calcule sur la memoire reelle, un nombre
      de fabrications simultanees, un debit par visiteur.
    - POUR QUI : un atelier par session, pour que le catalogue depose par l'un
      ne change pas la liste de course de l'autre.
    """

    TEMOIN = "bfk_session"

    def __init__(self, cle: str, fabrique_atelier: Callable[[], object],
                 plafond_tenons: int, simultanees: int = 1,
                 debit: Optional[Debit] = None,
                 debit_cle: Optional[Debit] = None,
                 relais: int = 0, securise: bool = True,
                 attente_maximale: float = 0.0,
                 horloge: Callable[[], float] = time.monotonic):
        if not cle or len(cle) < 16:
            raise ValueError(
                "une cle d'atelier fait au moins seize caracteres : "
                "en dessous, elle se devine plus vite qu'elle ne se tape")
        if plafond_tenons < TENONS_PLANCHER:
            raise ValueError(
                f"{plafond_tenons} tenons de plafond : en dessous de "
                f"{TENONS_PLANCHER} l'atelier refuserait tout ce qu'on lui "
                "demande. Il faut plus de memoire, ou moins de fabrications "
                "simultanees.")
        self.cle = cle
        self.fabrique_atelier = fabrique_atelier
        self.plafond_tenons = plafond_tenons
        self.simultanees = max(1, simultanees)
        self.relais = relais
        self.securise = securise
        self.attente_maximale = attente_maximale
        self._horloge = horloge
        # Le debit n'est PAS la borne de charge : c'est le chantier qui l'est,
        # et il n'a qu'une place. Un visiteur ne peut donc pas faire calculer
        # deux choses a la fois quoi qu'il envoie. Ce seau-ci sert a autre
        # chose : empecher qu'on remplisse la file de requetes qui attendent
        # leur refus. Il peut donc etre large — cinq d'affilee, puis une toutes
        # les trente secondes — sans gener un visiteur qui compare des formats
        # avant de fabriquer.
        self.debit = debit or Debit()
        # Un seau distinct, plus severe, pour les cles fausses : le debit des
        # fabrications se recharge en secondes, ce qui suffirait a essayer des
        # milliers de cles par jour.
        self.debit_cle = debit_cle or Debit(jetons=5, recharge=300.0)
        self._places = threading.BoundedSemaphore(self.simultanees)
        self._sessions: "OrderedDict[str, list]" = OrderedDict()
        self._verrou = threading.Lock()

    # ------------------------------------------------------------ #
    # Les sessions
    # ------------------------------------------------------------ #

    def _oublier_les_vieilles(self, maintenant: float) -> None:
        """A appeler sous verrou."""
        morts = [jeton for jeton, (_, vu) in self._sessions.items()
                 if maintenant - vu > DUREE_DE_SESSION]
        for jeton in morts:
            del self._sessions[jeton]
        while len(self._sessions) > SESSIONS_MAXIMUM:
            self._sessions.popitem(last=False)

    def ouvrir_session(self) -> str:
        """Cree un atelier pour un visiteur et rend son jeton."""
        jeton = secrets.token_urlsafe(24)
        maintenant = self._horloge()
        atelier = self.fabrique_atelier()
        with self._verrou:
            self._sessions[jeton] = [atelier, maintenant]
            # Purger AVANT d'inserer laissait toujours une session de trop :
            # la borne annoncee etait alors SESSIONS_MAXIMUM + 1.
            self._oublier_les_vieilles(maintenant)
        return jeton

    def session(self, jeton: Optional[str]):
        """L'atelier de ce jeton, ou None. Rafraichit la date de derniere vue."""
        if not jeton:
            return None
        maintenant = self._horloge()
        with self._verrou:
            entree = self._sessions.get(jeton)
            if entree is None:
                return None
            if maintenant - entree[1] > DUREE_DE_SESSION:
                del self._sessions[jeton]
                return None
            entree[1] = maintenant
            self._sessions.move_to_end(jeton)
            return entree[0]

    def _temoin(self, entetes: Mapping[str, str]) -> Optional[str]:
        """Lit notre temoin, sans dependre de `http.cookies`.

        Un en-tete `Cookie` abime ne doit pas lever : il doit ne rien donner.
        """
        brut = entetes.get("Cookie") or ""
        for morceau in brut.split(";"):
            nom, _, valeur = morceau.strip().partition("=")
            if nom == self.TEMOIN and valeur:
                return valeur
        return None

    def _pose_le_temoin(self, jeton: str) -> Tuple[str, str]:
        parts = [f"{self.TEMOIN}={jeton}", "Path=/", "HttpOnly",
                 # Lax et non Strict : le temoin est pose par un lien suivi
                 # depuis un courriel ou une conversation, ce que Strict
                 # bloquerait — le visiteur tournerait en rond sur la page
                 # « atelier prive » avec le bon lien en main.
                 "SameSite=Lax", f"Max-Age={int(DUREE_DE_SESSION)}"]
        if self.securise:
            parts.append("Secure")
        return ("Set-Cookie", "; ".join(parts))

    # ------------------------------------------------------------ #
    # L'accueil
    # ------------------------------------------------------------ #

    def _cle_presentee(self, requete: str) -> Optional[str]:
        for morceau in requete.split("&"):
            nom, _, valeur = morceau.partition("=")
            if nom == "cle":
                return unquote_plus(valeur)
        return None

    def accueillir(self, visite: Visite) -> Accueil:
        """Le seul point d'entree. Rend l'atelier du visiteur, ou un refus."""
        adresse = adresse_du_visiteur(visite.entetes, visite.pair, self.relais)

        atelier = self.session(self._temoin(visite.entetes))
        if atelier is not None:
            return Accueil(atelier=atelier)

        presentee = self._cle_presentee(visite.requete)
        if presentee is not None:
            # La comparaison vient AVANT le seau, et le seau ne compte que les
            # echecs. Compter aussi les reussites verrouillait dehors une
            # famille ou un bureau — une seule adresse pour tout le monde —
            # des le sixieme visiteur muni du bon lien, ce qui n'a rien a voir
            # avec ce que ce seau est cense arreter. La comparaison est a temps
            # constant : la faire d'abord ne dit rien de plus a l'attaquant.
            if secrets.compare_digest(presentee, self.cle):
                jeton = self.ouvrir_session()
                # 303 et non 302 : la cle ne doit pas rester dans la barre
                # d'adresse, ni partir dans le prochain lien copie-colle.
                return Accueil(
                    code=303, message="",
                    entetes=(self._pose_le_temoin(jeton), ("Location", "/")))
            attente = self.debit_cle.prendre(adresse)
            if attente is not None:
                return Accueil(
                    code=429,
                    message="trop d'essais de cle. Reessayez plus tard.",
                    entetes=(("Retry-After", str(int(attente) + 1)),))

        # Une page se lit, un appel de la page se deserialise. Rendre du HTML a
        # un `fetch` lui fait lever sur l'analyse JSON, et le visiteur voit
        # « SyntaxError » la ou il fallait lire « votre session a expire ».
        if visite.chemin in ("/", "/index.html"):
            return Accueil(code=401, message="atelier prive",
                           corps_html=PAGE_CLE)
        return Accueil(
            code=401,
            message="session expiree ou absente : rouvrez le lien de "
                    "l'atelier, celui qui porte la cle.")

    def autoriser_fabrication(self, visite: Visite) -> Optional[Accueil]:
        """Refus si ce visiteur va trop vite, sinon None."""
        adresse = adresse_du_visiteur(visite.entetes, visite.pair, self.relais)
        attente = self.debit.prendre(adresse)
        if attente is None:
            return None
        return Accueil(
            code=429,
            message=f"une fabrication a la fois et par visiteur : encore "
                    f"{int(attente) + 1} s.",
            entetes=(("Retry-After", str(int(attente) + 1)),))

    class _Chantier:
        def __init__(self, places, attente):
            self._places, self._attente = places, attente
            self._pris = False

        def __enter__(self):
            if self._attente > 0:
                self._pris = self._places.acquire(timeout=self._attente)
            else:
                self._pris = self._places.acquire(blocking=False)
            if not self._pris:
                raise Occupe(
                    "l'atelier fabrique deja autant de mosaiques qu'il en "
                    "tient. Reessayez dans une minute.")
            return self

        def __exit__(self, *_):
            if self._pris:
                self._places.release()
            return False

    def chantier(self):
        """Une place de fabrication, ou `Occupe`.

        Le nombre de places n'est pas un debit : c'est la borne qui rend le
        plafond de tenons vrai. Il est calcule AVEC lui — deux fabrications de
        la taille maximale doivent tenir ensemble dans la memoire du conteneur.
        """
        return self._Chantier(self._places, self.attente_maximale)
