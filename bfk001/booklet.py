"""Notice de montage imprimable (HORS CONTRAT, couche 3).

Produit un PDF complet : couverture, liste de course avec pastilles de
couleur, pose du substrat, puis la mosaique BANDE PAR BANDE.

Pourquoi pas une page par etape du plan ? Parce que ca ne marche pas. Le plan
de `instructions.plan_build` est physiquement juste, mais il regroupe par
COULEUR : pour une mosaique 48x48 il produit 733 etapes du genre « poser 4
tuiles rouges », dispersees dans toute l'image. Un fascicule de 733 pages qui
fait chercher quatre tuiles dans 2304 cases, cinq cents fois. Mesure faite sur
une 48x48 : 733 etapes, 2917 pieces.

Les notices LEGO Art officielles procedent autrement, et elles ont raison :
LIGNE PAR LIGNE, de haut en bas, avec le compte des tuiles consecutives de
chaque couleur. C'est ce que fait ce module. Le plan reste l'autorite sur ce
qui PEUT etre pose quand ; le fascicule choisit seulement dans quel ORDRE,
parmi les ordres permis — et `_verifier_ordre` refuse de produire le PDF si
l'ordre choisi violait une dependance du plan.

VUE DE DESSUS, et non isometrique : une mosaique est une oeuvre plate. Une vue
en perspective n'ajouterait aucune information et rendrait le reperage des
tuiles plus difficile — or c'est la seule chose que le constructeur cherche.

Le PDF est ecrit a la main. Aucune bibliotheque n'est disponible, mais le
format n'exige rien d'exotique ici : des objets numerotes, une table de
renvois, des images compressees par zlib — que la bibliotheque standard
fournit — et les polices de base que tout lecteur possede, donc rien a
embarquer. Les chiffres des reglettes sont du TEXTE PDF, pas des pixels : ils
restent nets a l'impression et evitent d'embarquer une fonte matricielle.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .catalog import CATALOG, BomLine
from .graph import InstructionGraph
from .imaging import Image
from .mosaic import Mosaic
from .palette import LegoColor, Palette

__all__ = [
    "TextLine",
    "color_codes",
    "RectFill",
    "PdfPage",
    "write_pdf",
    "render_progress",
    "render_layer",
    "row_runs",
    "build_booklet",
    "A4_WIDTH",
    "A4_HEIGHT",
]

# x, y, corps, texte, gras
TextLine = Tuple[float, float, float, str, bool]
# x, y, largeur, hauteur, (r, v, b)
RectFill = Tuple[float, float, float, float, Tuple[int, int, int]]

A4_WIDTH = 595.0   # points, soit 210 mm
A4_HEIGHT = 842.0  # points, soit 297 mm

MARGE = 40.0
# Largeur moyenne d'un caractere Helvetica, en fraction du corps. Approximation
# volontaire : la table exacte fait 95 valeurs qu'il faudrait recopier a la
# main, et une recopie a la main est exactement le genre d'erreur qu'on ne
# detecte pas. Surestimer fait couper les lignes un peu tot — sans consequence.
LARGEUR_CARACTERE = 0.55


@dataclass(frozen=True)
class PdfPage:
    """Une page : du texte, des aplats, et au plus une image placee."""

    texts: Tuple[TextLine, ...] = ()
    rects: Tuple[RectFill, ...] = ()
    image: Optional[Image] = None
    # x, y, largeur, hauteur en points, coin bas-gauche
    image_rect: Optional[Tuple[float, float, float, float]] = None

    def __post_init__(self) -> None:
        if (self.image is None) != (self.image_rect is None):
            raise ValueError("une image exige son cadre, et reciproquement")


# --------------------------------------------------------------------------
# Ecriture du PDF
# --------------------------------------------------------------------------


def _escape(texte: str) -> bytes:
    """Chaine PDF : parentheses echappees, texte encode en WinAnsi.

    WinAnsiEncoding est cp1252 : les accents francais et le tiret cadratin y
    sont, donc rien a translitterer. Ce qui n'y est pas devient '?', ce qui
    reste visible plutot que de casser le fichier.
    """
    brut = texte.encode("cp1252", "replace")
    return brut.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def write_pdf(
    pages: Sequence[PdfPage],
    width: float = A4_WIDTH,
    height: float = A4_HEIGHT,
) -> bytes:
    """Assemble les pages en un PDF valide (table de renvois exacte)."""
    if not pages:
        raise ValueError("un fascicule compte au moins une page")

    objets: List[bytes] = []

    def ajouter(corps: bytes) -> int:
        objets.append(corps)
        return len(objets)  # les numeros d'objet commencent a 1

    catalogue = ajouter(b"")  # rempli plus bas : il reference l'arbre des pages
    arbre = ajouter(b"")
    romain = ajouter(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>"
    )
    gras = ajouter(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
        b"/Encoding /WinAnsiEncoding >>"
    )

    numeros_pages: List[int] = []
    for page in pages:
        flux: List[bytes] = []

        for x, y, largeur, hauteur, (r, v, b) in page.rects:
            flux.append(
                b"%.3f %.3f %.3f rg %.2f %.2f %.2f %.2f re f"
                % (r / 255, v / 255, b / 255, x, y, largeur, hauteur)
            )

        ressources = [b"/Font << /F1 %d 0 R /F2 %d 0 R >>" % (romain, gras)]
        if page.image is not None and page.image_rect is not None:
            donnees = zlib.compress(page.image.data, 6)
            xobjet = ajouter(
                b"<< /Type /XObject /Subtype /Image /Width %d /Height %d "
                b"/ColorSpace /DeviceRGB /BitsPerComponent 8 "
                b"/Filter /FlateDecode /Length %d >>\nstream\n"
                % (page.image.width, page.image.height, len(donnees))
                + donnees
                + b"\nendstream"
            )
            x, y, largeur, hauteur = page.image_rect
            flux.append(b"q %.2f 0 0 %.2f %.2f %.2f cm /Im Do Q"
                        % (largeur, hauteur, x, y))
            ressources.append(b"/XObject << /Im %d 0 R >>" % xobjet)

        flux.append(b"0 0 0 rg")
        for x, y, corps, texte, en_gras in page.texts:
            flux.append(
                b"BT /%s %.1f Tf %.2f %.2f Td (%s) Tj ET"
                % (b"F2" if en_gras else b"F1", corps, x, y, _escape(texte))
            )

        contenu = zlib.compress(b"\n".join(flux), 6)
        flux_objet = ajouter(
            b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(contenu)
            + contenu
            + b"\nendstream"
        )
        numeros_pages.append(
            ajouter(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] "
                b"/Resources << %s >> /Contents %d 0 R >>"
                % (arbre, width, height, b" ".join(ressources), flux_objet)
            )
        )

    objets[catalogue - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % arbre
    objets[arbre - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % n for n in numeros_pages),
        len(numeros_pages),
    )

    sortie = bytearray(b"%PDF-1.4\n")
    decalages = []
    for numero, corps in enumerate(objets, start=1):
        decalages.append(len(sortie))
        sortie += b"%d 0 obj\n" % numero + corps + b"\nendobj\n"

    debut_table = len(sortie)
    sortie += b"xref\n0 %d\n" % (len(objets) + 1)
    sortie += b"0000000000 65535 f \n"
    for decalage in decalages:
        sortie += b"%010d 00000 n \n" % decalage
    sortie += (
        b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objets) + 1, catalogue, debut_table)
    )
    return bytes(sortie)


# --------------------------------------------------------------------------
# Rendu matriciel : vue de dessus de l'avancement
# --------------------------------------------------------------------------

# Ce qui reste a poser est damie, et pas seulement clair. Une simple teinte
# pale ne suffit pas : la ou l'oeuvre est grise, un gris pali et un gris « vide »
# se ressemblent, et le constructeur ne sait plus ou il en est. Un damier n'est
# la couleur d'aucune tuile, donc il ne peut pas etre pris pour une consigne.
GRIS_FUTUR = (226, 226, 226)
GRIS_FUTUR_BIS = (206, 206, 206)
PALEUR_POSE = 0.5              # fraction de blanc melee aux tuiles deja posees


def _paler(rgb: Tuple[int, int, int], fraction: float) -> Tuple[int, int, int]:
    """Melange vers le blanc. Le deja-pose recule, la bande en cours avance."""
    return tuple(int(round(c + (255 - c) * fraction)) for c in rgb)


def _assombrir(rgb: Tuple[int, int, int], fraction: float) -> Tuple[int, int, int]:
    return tuple(int(round(c * (1 - fraction))) for c in rgb)


class _Canvas:
    """Toile RVB minimale. Origine en haut a gauche, comme une image."""

    def __init__(self, width: int, height: int, fond=(255, 255, 255)) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("toile de dimension nulle")
        self.width = width
        self.height = height
        self.data = bytearray(bytes(fond) * (width * height))

    def fill(self, x: int, y: int, w: int, h: int, rgb) -> None:
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.width, x + w), min(self.height, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        motif = bytes(rgb) * (x1 - x0)
        for ligne in range(y0, y1):
            debut = (ligne * self.width + x0) * 3
            self.data[debut : debut + len(motif)] = motif

    def frame(self, x: int, y: int, w: int, h: int, rgb, epaisseur: int = 1) -> None:
        self.fill(x, y, w, epaisseur, rgb)
        self.fill(x, y + h - epaisseur, w, epaisseur, rgb)
        self.fill(x, y, epaisseur, h, rgb)
        self.fill(x + w - epaisseur, y, epaisseur, h, rgb)

    def image(self) -> Image:
        return Image(self.width, self.height, bytes(self.data))


def _echelle_auto(studs: int, cible: int = 640) -> int:
    """Pixels par tenon : assez pour rester net, pas assez pour peser."""
    return max(3, min(14, cible // max(1, studs)))


def render_progress(
    mosaic: Mosaic,
    first_row: int,
    last_row: int,
    scale: Optional[int] = None,
    grid: int = 8,
) -> Image:
    """Vue de dessus a l'etape « bande [first_row, last_row] ».

    Deja pose : couleur reelle mais pale, pour situer sans distraire.
    Bande en cours : couleur pleine, encadree de noir, reglee ligne a ligne.
    Reste : gris uniforme — il n'y a rien a y lire encore.
    """
    if not 0 <= first_row <= last_row < mosaic.studs_y:
        raise ValueError("bande hors de la mosaique")
    s = _echelle_auto(mosaic.studs_x) if scale is None else scale
    if s <= 0:
        raise ValueError("echelle invalide")

    toile = _Canvas(mosaic.studs_x * s, mosaic.studs_y * s)
    for row, colors in enumerate(mosaic.grid):
        if row > last_row:
            for column in range(mosaic.studs_x):
                toile.fill(column * s, row * s, s, s,
                           GRIS_FUTUR if (row + column) % 2 else GRIS_FUTUR_BIS)
            continue
        courante = row >= first_row
        for column, color in enumerate(colors):
            rgb = color.rgb if courante else _paler(color.rgb, PALEUR_POSE)
            toile.fill(column * s, row * s, s, s, rgb)

    # Toute reglure tracee DANS la mosaique est ASSOMBRIE, jamais peinte : un
    # trait opaque mentirait sur la teinte de la tuile qu'il recouvre, et cette
    # teinte est la seule information que la page transmet. Assombrie, la
    # couleur reste lisible dessous et le trait se compte quand meme.
    table = bytes(round(valeur * 0.65) for valeur in range(256))

    def assombrir_colonne(x: int) -> None:
        for ligne in range(toile.height):
            index = (ligne * toile.width + x) * 3
            toile.data[index : index + 3] = toile.data[index : index + 3].translate(
                table
            )

    def assombrir_ligne(y: int) -> None:
        debut = y * toile.width * 3
        fin = debut + toile.width * 3
        toile.data[debut:fin] = toile.data[debut:fin].translate(table)

    # Reperes tous les `grid` tenons, pour compter sans se perdre.
    if grid > 0 and s >= 3:
        for column in range(grid, mosaic.studs_x, grid):
            assombrir_colonne(column * s)
        for row in range(grid, mosaic.studs_y, grid):
            assombrir_ligne(row * s)

    # Reglure interne de la bande : sans elle, deux lignes voisines de teintes
    # proches se confondent et la suite se pose sur la mauvaise ligne.
    for row in range(first_row + 1, last_row + 1):
        assombrir_ligne(row * s)

    # Delimitation de la bande, posee HORS d'elle — sur du deja-pose ou du
    # pas-encore-pose, ou il n'y a rien a lire.
    epaisseur = 2 if s >= 6 else 1
    toile.fill(0, first_row * s - epaisseur, toile.width, epaisseur, (0, 0, 0))
    toile.fill(0, (last_row + 1) * s, toile.width, epaisseur, (0, 0, 0))
    return toile.image()


def _teinte(code: int, palette: Optional["Palette"]) -> Tuple[int, int, int]:
    """Code couleur -> RVB, par la palette et jamais par une table recopiee.

    Une valeur RVB recopiee a la main est une erreur qu'on ne voit pas : c'est
    ainsi qu'un vert LEGO s'etait retrouve faux dans ce depot. Faute de
    palette, on rend un gris neutre — visiblement provisoire, jamais faux.
    """
    if palette is not None:
        try:
            return palette.by_code(code).rgb
        except KeyError:
            pass
    return (160, 160, 160)


def render_layer(
    mosaic: Mosaic,
    part_ids: Sequence[str],
    done_ids: Sequence[str] = (),
    scale: Optional[int] = None,
    palette: Optional["Palette"] = None,
) -> Image:
    """Vue de dessus d'une couche de substrat : une empreinte par piece.

    Generique : l'empreinte se lit dans l'AABB de la piece posee, pas dans son
    nom. Le fascicule n'a donc rien a savoir de la maniere dont la mosaique
    nomme ses pieces.
    """
    from .lego import STUD_PITCH_LDU

    if not part_ids:
        raise ValueError("couche vide")
    interessantes = list(done_ids) + list(part_ids)
    boites = [mosaic.placed_parts[p].aabb for p in interessantes]
    x_min = min(min(b.min.x for b in boites), 0)
    y_min = min(min(b.min.y for b in boites), 0)
    x_max = max(max(b.max.x for b in boites), mosaic.studs_x * STUD_PITCH_LDU)
    y_max = max(max(b.max.y for b in boites), mosaic.studs_y * STUD_PITCH_LDU)

    largeur_studs = (x_max - x_min) / STUD_PITCH_LDU
    s = _echelle_auto(int(largeur_studs) + 1) if scale is None else scale
    par_ldu = s / STUD_PITCH_LDU
    toile = _Canvas(
        max(1, int(round((x_max - x_min) * par_ldu))),
        max(1, int(round((y_max - y_min) * par_ldu))),
        GRIS_FUTUR,
    )

    def rectangle(part_id: str) -> Tuple[int, int, int, int]:
        boite = mosaic.placed_parts[part_id].aabb
        # L'axe y du modele monte, celui de l'image descend.
        return (
            int(round((boite.min.x - x_min) * par_ldu)),
            int(round((y_max - boite.max.y) * par_ldu)),
            max(1, int(round((boite.max.x - boite.min.x) * par_ldu))),
            max(1, int(round((boite.max.y - boite.min.y) * par_ldu))),
        )

    trait = 2 if par_ldu * 20 >= 10 else 1
    for part_id in list(done_ids) + list(part_ids):
        rgb = _teinte(mosaic.instances[part_id].color_id, palette)
        x, y, w, h = rectangle(part_id)
        toile.fill(x, y, w, h, rgb)
        toile.frame(x, y, w, h, _assombrir(rgb, 0.7), trait)

    # Les joints de la couche precedente, RETRACES PAR-DESSUS en clair. Sans
    # ca la couche du dessus recouvre integralement celle du dessous et la page
    # ne montre plus rien — or ce qu'elle doit montrer, c'est justement le
    # DECALAGE entre les deux : chaque nouvelle plate doit enjamber les joints
    # d'en dessous, et c'est ce croisement, lui seul, qui fait tenir le fond.
    for part_id in done_ids:
        x, y, w, h = rectangle(part_id)
        toile.frame(x, y, w, h, _paler(rgb_ghost := _teinte(
            mosaic.instances[part_id].color_id, palette), 0.55))
    return toile.image()


# --------------------------------------------------------------------------
# Assemblage du fascicule
# --------------------------------------------------------------------------

CORPS_TITRE = 20.0
CORPS_SOUS_TITRE = 10.5
CORPS_TEXTE = 9.0
CORPS_LIGNE = 7.6
CORPS_REGLETTE = 5.4
INTERLIGNE = 10.5


def row_runs(colors: Sequence[LegoColor]) -> Tuple[Tuple[int, LegoColor], ...]:
    """Ligne de tuiles -> suites consecutives de meme couleur.

    C'est la seule forme sous laquelle une ligne de mosaique se pose sans se
    tromper : « 3 noir, 5 blanc, 2 rouge » se compte, alors que quarante-huit
    cases se recomptent.
    """
    runs: List[Tuple[int, LegoColor]] = []
    for color in colors:
        # Par CODE et non par identite : deux LegoColor egales mais distinctes
        # sont la meme brique dans le sachet, et couper la suite entre elles
        # ferait recompter le constructeur pour rien.
        if runs and runs[-1][1].code == color.code:
            runs[-1] = (runs[-1][0] + 1, color)
        else:
            runs.append((1, color))
    return tuple(runs)


def color_codes(mosaic: Mosaic) -> Dict[int, str]:
    """Couleur -> code court, la plus employee en premier.

    « 3A · 5B · 12C » se lit et se pointe ; « 3 Light Bluish Gray · 5 Dark
    Bluish Gray » se lit mal et se confond — les deux noms ne different que par
    leur premier mot. Les grilles de point de croix emploient des symboles pour
    exactement cette raison. Le nom complet reste dans la legende et dans la
    liste de course, la ou on commande.
    """
    compte: Dict[int, int] = {}
    for ligne in mosaic.grid:
        for color in ligne:
            compte[color.code] = compte.get(color.code, 0) + 1
    ordonnees = sorted(compte, key=lambda code: (-compte[code], code))
    codes: Dict[int, str] = {}
    for rang, code in enumerate(ordonnees):
        lettres = ""
        reste = rang
        while True:
            lettres = chr(ord("A") + reste % 26) + lettres
            reste = reste // 26 - 1
            if reste < 0:
                break
        codes[code] = lettres
    return codes


def _couleurs_employees(mosaic: Mosaic) -> List[LegoColor]:
    """Couleurs presentes dans l'oeuvre, dans l'ordre des codes."""
    vues: Dict[int, LegoColor] = {}
    for ligne in mosaic.grid:
        for color in ligne:
            vues.setdefault(color.code, color)
    codes = color_codes(mosaic)
    return [vues[code] for code in sorted(vues, key=lambda c: codes[c])]


def _legende(
    couleurs: Sequence[LegoColor], codes: Mapping[int, str], bas: float
) -> Tuple[List[TextLine], List[RectFill], float]:
    """Bloc de correspondance code -> pastille + nom. Rend aussi sa hauteur."""
    par_rang = 4
    pas_x = (A4_WIDTH - 2 * MARGE) / par_rang
    rangs = (len(couleurs) + par_rang - 1) // par_rang
    hauteur = rangs * LEGENDE_PAS + LEGENDE_TITRE
    textes: List[TextLine] = [
        (MARGE, bas + hauteur - LEGENDE_TITRE + 2.0, CORPS_LIGNE, "Couleurs", True)
    ]
    rects: List[RectFill] = []
    for index, color in enumerate(couleurs):
        x = MARGE + (index % par_rang) * pas_x
        y = bas + hauteur - LEGENDE_TITRE - (index // par_rang + 1) * LEGENDE_PAS + 2.0
        rects.append((x, y - 1.5, 8.0, 8.0, color.rgb))
        textes.append((x + 12.0, y, CORPS_LIGNE, codes[color.code], True))
        textes.append((x + 26.0, y, CORPS_LIGNE, color.name, False))
    return textes, rects, hauteur


@dataclass(frozen=True)
class _Mise:
    """Ce que toutes les pages doivent partager : codes, legende, sa hauteur.

    Calcule une fois. Deux pages qui ne s'accorderaient pas sur les codes
    rendraient la notice illisible, et une legende de hauteur variable ferait
    danser les vues d'une page a l'autre.
    """

    codes: Mapping[int, str]
    couleurs: Tuple[LegoColor, ...]
    textes: Tuple[TextLine, ...]
    rects: Tuple[RectFill, ...]
    hauteur: float

    @property
    def reserve(self) -> float:
        return self.hauteur + ECART_LEGENDE


def _mise_en_page(mosaic: Mosaic) -> _Mise:
    codes = color_codes(mosaic)
    couleurs = tuple(_couleurs_employees(mosaic))
    textes, rects, hauteur = _legende(couleurs, codes, BAS_TEXTE)
    return _Mise(codes, couleurs, tuple(textes), tuple(rects), hauteur)


def _couper(texte: str, corps: float, largeur: float) -> List[str]:
    """Decoupe sur les separateurs. Largeur estimee, donc coupe un peu tot."""
    par_ligne = max(8, int(largeur / (corps * LARGEUR_CARACTERE)))
    morceaux = texte.split(" · ")
    lignes: List[str] = []
    courante = ""
    for morceau in morceaux:
        candidat = morceau if not courante else courante + " · " + morceau
        if len(candidat) <= par_ligne or not courante:
            courante = candidat
        else:
            lignes.append(courante)
            courante = morceau
    if courante:
        lignes.append(courante)
    return lignes


PIED_Y = 30.0  # au-dessus des 10 mm qu'une imprimante de bureau ne rend pas


def _pied(page: int, total: int, titre: str) -> List[TextLine]:
    return [
        (MARGE, PIED_Y, CORPS_LIGNE, titre, False),
        (A4_WIDTH - MARGE - 40, PIED_Y, CORPS_LIGNE, f"{page} / {total}", False),
    ]


def _cadre_image(
    image: Image, haut: float, bas: float, reserve_gauche: float = 0.0
) -> Tuple[float, float, float, float]:
    """Place l'image entre deux ordonnees, centree, sans la deformer.

    `reserve_gauche` garde la place des numeros de lignes. Sans elle, une vue
    pleine largeur repousse la reglette dans la marge non imprimable — environ
    10 mm sur une imprimante de bureau —, et le constructeur perd les numeros
    de lignes, c'est-a-dire le seul reperage vertical de la page.
    """
    gauche = MARGE + reserve_gauche
    utile_l = A4_WIDTH - MARGE - gauche
    utile_h = haut - bas
    echelle = min(utile_l / image.width, utile_h / image.height)
    largeur = image.width * echelle
    hauteur = image.height * echelle
    return (gauche + (utile_l - largeur) / 2, haut - hauteur, largeur, hauteur)


def _reglette(
    cadre: Tuple[float, float, float, float],
    studs_x: int,
    studs_y: int,
    first_row: int,
    last_row: int,
    pas: int = 8,
) -> List[TextLine]:
    """Numeros de colonnes au-dessus, numeros de lignes de la bande a gauche.

    Ecrits en TEXTE PDF et non graves dans l'image : nets a l'impression quelle
    que soit la taille, et rien a embarquer comme fonte matricielle.
    """
    x0, y0, largeur, hauteur = cadre
    par_stud_x = largeur / studs_x
    par_stud_y = hauteur / studs_y
    lignes: List[TextLine] = []
    for column in range(0, studs_x, pas):
        lignes.append(
            (x0 + column * par_stud_x + 0.5, y0 + hauteur + 3.0,
             CORPS_REGLETTE, str(column + 1), False)
        )
    for row in range(first_row, last_row + 1):
        centre = y0 + hauteur - (row + 0.5) * par_stud_y - CORPS_REGLETTE * 0.35
        lignes.append((x0 - 15.0, centre, CORPS_REGLETTE, str(row + 1), True))
    return lignes


def _page_couverture(
    mosaic: Mosaic,
    titre: str,
    pieces: int,
    couleurs: Sequence[LegoColor],
    codes: Mapping[int, str],
) -> PdfPage:
    from .lego import ldu_to_mm, STUD_PITCH_LDU

    from .mosaic import preview

    largeur_mm = ldu_to_mm(mosaic.studs_x * STUD_PITCH_LDU)
    hauteur_mm = ldu_to_mm(mosaic.studs_y * STUD_PITCH_LDU)
    # L'OEUVRE FINIE, en couleurs pleines. Pas une vue d'avancement : celle-ci
    # palit tout ce qui est deja pose, et la couverture montrerait une version
    # delavee de ce qu'on est en train de promettre.
    apercu = preview(mosaic, scale=max(3, min(12, 640 // max(1, mosaic.studs_x))))
    hauteur_liste = 44.0 + 16.0 * ((len(couleurs) + 3) // 4)
    cadre = _cadre_image(apercu, A4_HEIGHT - 140.0, BAS_TEXTE + hauteur_liste)

    textes: List[TextLine] = [
        (MARGE, A4_HEIGHT - 80, CORPS_TITRE, titre, True),
        (MARGE, A4_HEIGHT - 102, CORPS_SOUS_TITRE,
         f"{mosaic.studs_x} x {mosaic.studs_y} tenons  "
         f"({largeur_mm / 10:.1f} x {hauteur_mm / 10:.1f} cm)", False),
        (MARGE, A4_HEIGHT - 118, CORPS_SOUS_TITRE,
         f"{mosaic.tile_count} tuiles  ·  {pieces} pieces au total  ·  "
         f"{len(couleurs)} couleurs", False),
        (MARGE, BAS_TEXTE + hauteur_liste - 14.0, CORPS_TEXTE,
         "Couleurs employees", True),
    ]
    rects: List[RectFill] = []
    x, y = MARGE, BAS_TEXTE + hauteur_liste - 30.0
    for color in couleurs:
        if x > A4_WIDTH - MARGE - 130:
            x, y = MARGE, y - 16.0
        if y < BAS_TEXTE:  # pragma: no cover - la hauteur est calculee dessus
            break
        rects.append((x, y - 2.0, 10.0, 10.0, color.rgb))
        textes.append((x + 14.0, y + 0.5, CORPS_LIGNE, codes[color.code], True))
        textes.append((x + 28.0, y + 0.5, CORPS_LIGNE, color.name, False))
        x += 130.0
    return PdfPage(tuple(textes), tuple(rects), apercu, cadre)


def _pages_liste(
    bom: Sequence[BomLine],
    palette: Optional[Palette],
    codes: Mapping[int, str],
) -> List[PdfPage]:
    """Liste de course : reference, pastille, couleur, quantite."""
    par_page = 34
    # Groupe par reference, et dans chaque reference le plus gros lot d'abord :
    # c'est l'ordre dans lequel on remplit un panier, pas l'ordre alphabetique.
    ordonnee = sorted(bom, key=lambda ligne: (ligne.design_id, -ligne.quantity))
    pages: List[PdfPage] = []
    for debut in range(0, len(ordonnee), par_page):
        tranche = ordonnee[debut : debut + par_page]
        textes: List[TextLine] = [
            (MARGE, A4_HEIGHT - 60, CORPS_TITRE * 0.75, "Liste de course", True),
            (MARGE, A4_HEIGHT - 82, CORPS_LIGNE,
             "A commander avant de commencer. Les quantites sont exactes, "
             "prevoyez quelques tuiles de rab.", False),
            (MARGE, A4_HEIGHT - 106, CORPS_TEXTE, "Qte", True),
            (MARGE + 34, A4_HEIGHT - 106, CORPS_TEXTE, "Reference", True),
            (MARGE + 92, A4_HEIGHT - 106, CORPS_TEXTE, "Piece", True),
            (MARGE + 270, A4_HEIGHT - 106, CORPS_TEXTE, "Couleur", True),
        ]
        rects: List[RectFill] = [
            (MARGE, A4_HEIGHT - 112, A4_WIDTH - 2 * MARGE, 0.7, (0, 0, 0))
        ]
        y = A4_HEIGHT - 128
        for ligne in tranche:
            couleur = None
            if palette is not None:
                try:
                    couleur = palette.by_code(ligne.color_id)
                except KeyError:
                    couleur = None
            textes.append((MARGE, y, CORPS_TEXTE, str(ligne.quantity), True))
            textes.append((MARGE + 34, y, CORPS_TEXTE, ligne.design_id, False))
            textes.append((MARGE + 92, y, CORPS_TEXTE, ligne.name, False))
            if couleur is not None:
                rects.append((MARGE + 270, y - 1.5, 9.0, 9.0, couleur.rgb))
                code = codes.get(ligne.color_id)
                if code:
                    textes.append((MARGE + 284, y, CORPS_TEXTE, code, True))
                textes.append((MARGE + 302, y, CORPS_TEXTE, couleur.name, False))
            else:
                textes.append((MARGE + 270, y, CORPS_TEXTE,
                               f"code {ligne.color_id}", False))
            y -= 15.0
        pages.append(PdfPage(tuple(textes), tuple(rects)))
    return pages


def _pages_substrat(
    mosaic: Mosaic,
    couches: Sequence[Sequence[str]],
    palette: Optional[Palette],
) -> List[Tuple[PdfPage, Sequence[str]]]:
    """Une page par couche de fond, avec l'empreinte des plates a poser.

    Rend la couche avec sa page : deduire l'index d'une page par un calcul sur
    la longueur de la liste marche tant que personne n'ajoute une page.
    """
    pages: List[Tuple[PdfPage, Sequence[str]]] = []
    deja: List[str] = []
    for rang, couche in enumerate(couches, start=1):
        vue = render_layer(mosaic, list(couche), list(deja), palette=palette)
        cadre = _cadre_image(vue, A4_HEIGHT - 130.0, 150.0)
        references: Dict[str, int] = {}
        for part_id in couche:
            design = mosaic.instances[part_id].design_id
            references[design] = references.get(design, 0) + 1
        detail = " · ".join(
            f"{n} x {CATALOG[d].name if d in CATALOG else d}"
            for d, n in sorted(references.items())
        )
        textes: List[TextLine] = [
            (MARGE, A4_HEIGHT - 60, CORPS_TITRE * 0.75,
             f"Fond — couche {rang} sur {len(couches)}", True),
            (MARGE, A4_HEIGHT - 82, CORPS_LIGNE,
             "Poser toutes les plates de cette couche avant de passer a la "
             "suivante.", False),
            (MARGE, A4_HEIGHT - 93, CORPS_LIGNE,
             "Le decalage entre les couches est ce qui fait tenir le fond.",
             False),
            (MARGE, 128.0, CORPS_TEXTE, f"{len(couche)} pieces : {detail}", False),
        ]
        if rang > 1:
            textes.append((MARGE, 112.0, CORPS_LIGNE,
                           "En pale : la couche precedente, deja posee.", False))
        pages.append((PdfPage(tuple(textes), (), vue, cadre), couche))
        deja = list(deja) + list(couche)
    return pages


IMAGE_HAUT = A4_HEIGHT - 116.0   # bord superieur de la vue
IMAGE_MIN = 200.0                # en dessous, la vue devient illisible
# Plafond volontairement plus haut que la largeur utile (515 pt) : c'est
# `_cadre_image` qui borne pour de bon, en respectant les proportions. Un
# plafond plus bas laissait un trou de 300 pt au milieu de la page des que la
# lecture etait courte — et une lecture courte, c'est le cas d'une photo.
IMAGE_MAX = 620.0
BAS_TEXTE = 44.0                 # au-dessus du pied de page
ECART_VUE_TEXTE = 26.0
RETRAIT_LECTURE = 34.0           # apres l'etiquette « L12 »
RESERVE_REGLETTE = 20.0          # a gauche de la vue, pour les numeros de lignes
ECART_LIGNES = 3.5               # respiration entre deux lignes de mosaique
LEGENDE_PAS = 11.0               # hauteur d'un rang de legende
LEGENDE_TITRE = 14.0
ECART_LEGENDE = 8.0


def _lecture(
    mosaic: Mosaic, rows: Sequence[int], codes: Mapping[int, str]
) -> List[Tuple[int, List[str]]]:
    """Lecture des lignes demandees : par ligne, ses morceaux deja coupes.

    Produite AVANT la mise en page, parce que c'est elle qui la commande : une
    image bruitee donne quarante-huit suites sur une ligne, un ciel en donne
    trois. Dimensionner la vue sans connaitre ce volume, c'est deborder de la
    page — et une ligne de notice qui deborde est une ligne perdue.
    """
    largeur = A4_WIDTH - 2 * MARGE - RETRAIT_LECTURE
    return [
        (
            row,
            _couper(
                " · ".join(
                    f"{compte}{codes[color.code]}"
                    for compte, color in row_runs(mosaic.grid[row])
                ),
                CORPS_LIGNE,
                largeur,
            ),
        )
        for row in rows
    ]


def _hauteur_lecture(lecture: Sequence[Tuple[int, List[str]]]) -> float:
    """Hauteur qu'occupera la lecture, interlignes et respirations comprises."""
    lignes = sum(len(morceaux) for _, morceaux in lecture)
    return lignes * INTERLIGNE + len(lecture) * ECART_LIGNES


def _hauteur_vue(
    hauteur_lecture: float, hauteur_legende: float = 0.0
) -> Optional[float]:
    """Hauteur de vue laissant la place a la lecture et a la legende.

    None si meme la vue minimale ne suffit pas : c'est le signal qu'il faut
    mettre moins de lignes de mosaique sur cette page.
    """
    disponible = (
        IMAGE_HAUT - BAS_TEXTE - ECART_VUE_TEXTE - hauteur_lecture - hauteur_legende
    )
    if disponible < IMAGE_MIN:
        return None
    return min(IMAGE_MAX, disponible)


def _pages_bande(
    mosaic: Mosaic, rows: Sequence[int], numero: int, total: int, mise: _Mise
) -> List[PdfPage]:
    """La page d'une bande, et ses pages de suite si la lecture deborde.

    Le decoupage en bandes evite normalement le debordement. Mais une mosaique
    tres large et tres bruitee peut produire une seule ligne dont la lecture ne
    tient pas sous la vue : plutot que de refuser ou de tronquer — c'est-a-dire
    de perdre des tuiles —, on continue sur une page de suite sans vue.
    """
    first_row, last_row = rows[0], rows[-1]
    lecture = _lecture(mosaic, rows, mise.codes)
    bas_lecture = BAS_TEXTE + mise.reserve
    hauteur = _hauteur_vue(_hauteur_lecture(lecture), mise.reserve)
    vue = render_progress(mosaic, first_row, last_row)
    cadre = _cadre_image(
        vue, IMAGE_HAUT, IMAGE_HAUT - (hauteur or IMAGE_MIN), RESERVE_REGLETTE
    )

    entete = [
        (MARGE, A4_HEIGHT - 60, CORPS_TITRE * 0.75,
         f"Mosaique — bande {numero} sur {total}", True),
        (MARGE, A4_HEIGHT - 80, CORPS_LIGNE,
         f"Lignes {first_row + 1} a {last_row + 1}, de gauche a droite. "
         "En pale : deja pose. En gris : pas encore.", False),
    ]
    textes: List[TextLine] = list(entete)
    textes.extend(
        _reglette(cadre, mosaic.studs_x, mosaic.studs_y, first_row, last_row)
    )

    pages: List[PdfPage] = []

    def fermer(courantes: List[TextLine]) -> None:
        premiere = not pages
        pages.append(
            PdfPage(
                tuple(courantes) + mise.textes,
                mise.rects,
                vue if premiere else None,
                cadre if premiere else None,
            )
        )

    y = cadre[1] - ECART_VUE_TEXTE
    for row, morceaux in lecture:
        etiquette = f"L{row + 1}"
        for index, morceau in enumerate(morceaux):
            if y < bas_lecture:
                fermer(textes)
                textes = list(entete)
                textes.append(
                    (MARGE, A4_HEIGHT - 104, CORPS_LIGNE, "(suite)", False)
                )
                y = A4_HEIGHT - 124
            if index == 0:
                textes.append((MARGE, y, CORPS_TEXTE, etiquette, True))
            textes.append((MARGE + RETRAIT_LECTURE, y, CORPS_LIGNE, morceau, False))
            y -= INTERLIGNE
        y -= ECART_LIGNES

    fermer(textes)
    return pages


def _decouper_bandes(
    mosaic: Mosaic, maximum: int, mise: _Mise
) -> List[Tuple[int, ...]]:
    """Regroupe les lignes en bandes qui TIENNENT sur une page.

    Au plus `maximum` lignes, et toujours au moins une : une ligne seule tient
    forcement, sa lecture ne peut pas depasser une page entiere.
    """
    bandes: List[Tuple[int, ...]] = []
    courante: List[int] = []
    for row in range(mosaic.studs_y):
        candidate = courante + [row]
        tient = _hauteur_vue(
            _hauteur_lecture(_lecture(mosaic, candidate, mise.codes)), mise.reserve
        )
        if len(candidate) <= maximum and tient is not None:
            courante = candidate
        else:
            if courante:
                bandes.append(tuple(courante))
            courante = [row]
    if courante:
        bandes.append(tuple(courante))
    return bandes


def _verifier_ordre(
    plan: InstructionGraph, page_de: Mapping[str, int]
) -> None:
    """Refuse un fascicule qui ferait poser une piece avant son support.

    Le fascicule reordonne librement ce que le plan autorise ; encore faut-il
    le prouver. Pour chaque dependance du plan, toute piece du prerequis doit
    figurer sur une page au plus tard aussi ancienne que la premiere piece de
    l'etape dependante. C'est la seule chose que le rendu ne doit jamais
    casser : le reste n'est que confort.
    """
    pages_de_etape: Dict[str, Tuple[int, int]] = {}
    for step in plan.steps:
        numeros = [page_de[p] for p in step.part_ids if p in page_de]
        if numeros:
            pages_de_etape[step.step_id] = (min(numeros), max(numeros))
    for step in plan.steps:
        if step.step_id not in pages_de_etape:
            continue
        premiere = pages_de_etape[step.step_id][0]
        for prerequis in step.depends_on:
            if prerequis not in pages_de_etape:
                continue
            derniere = pages_de_etape[prerequis][1]
            if derniere > premiere:
                raise ValueError(
                    f"ordre du fascicule invalide : l'etape {step.step_id} "
                    f"commence page {premiere} alors que son prerequis "
                    f"{prerequis} finit page {derniere}"
                )


def build_booklet(
    mosaic: Mosaic,
    plan: InstructionGraph,
    bom: Sequence[BomLine],
    palette: Optional[Palette] = None,
    title: str = "Mosaique LEGO",
    rows_per_page: int = 4,
) -> bytes:
    """Fascicule complet : couverture, liste de course, fond, puis les bandes.

    `plan` n'est pas decoratif : il sert d'arbitre. L'ordre choisi ici est
    verifie contre ses dependances, et le PDF n'est pas produit s'il les viole.
    """
    if rows_per_page < 1:
        raise ValueError("une bande compte au moins une ligne")

    tuiles = {
        mosaic.tile_id(row, column)
        for row in range(mosaic.studs_y)
        for column in range(mosaic.studs_x)
    }
    manquantes = tuiles - set(mosaic.placed_parts)
    if manquantes:  # pragma: no cover - la mosaique pose toutes ses tuiles
        raise KeyError(f"{len(manquantes)} tuiles absentes du modele")

    # Les couches de fond se lisent dans les altitudes, pas dans les noms.
    par_altitude: Dict[int, List[str]] = {}
    for part_id in sorted(set(mosaic.placed_parts) - tuiles):
        par_altitude.setdefault(mosaic.placed_parts[part_id].aabb.min.z, []).append(
            part_id
        )
    couches = [par_altitude[z] for z in sorted(par_altitude)]

    mise = _mise_en_page(mosaic)

    pages: List[PdfPage] = [
        _page_couverture(mosaic, title, mosaic.part_count, mise.couleurs, mise.codes)
    ]
    pages.extend(_pages_liste(bom, palette, mise.codes))
    page_de: Dict[str, int] = {}

    for page, couche in _pages_substrat(mosaic, couches, palette):
        pages.append(page)
        for part_id in couche:
            page_de[part_id] = len(pages) - 1

    bandes = _decouper_bandes(mosaic, rows_per_page, mise)
    for index, rows in enumerate(bandes, start=1):
        pages.extend(_pages_bande(mosaic, rows, index, len(bandes), mise))
        for row in rows:
            for column in range(mosaic.studs_x):
                page_de[mosaic.tile_id(row, column)] = len(pages) - 1

    _verifier_ordre(plan, page_de)

    total = len(pages)
    finales = [
        PdfPage(
            page.texts + tuple(_pied(numero, total, title)),
            page.rects,
            page.image,
            page.image_rect,
        )
        for numero, page in enumerate(pages, start=1)
    ]
    return write_pdf(finales)
