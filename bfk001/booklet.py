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
from .lego import BRICK_HEIGHT_LDU, ldu_to_mm
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
    """Une page : du texte, des aplats, et des images placees.

    Une page en portait plusieurs le jour ou la notice a voulu ressembler a
    une notice LEGO : la vue de l'etape, et le petit reperage de l'oeuvre
    entiere qui dit OU l'on en est. Une seule image obligeait a choisir.
    """

    texts: Tuple[TextLine, ...] = ()
    rects: Tuple[RectFill, ...] = ()
    # (image, (x, y, largeur, hauteur)) en points, coin bas-gauche
    images: Tuple[Tuple[Image, Tuple[float, float, float, float]], ...] = ()

    def __post_init__(self) -> None:
        for image, cadre in self.images:
            if image is None or cadre is None:
                raise ValueError("une image exige son cadre, et reciproquement")
            if len(cadre) != 4:
                raise ValueError("un cadre vaut (x, y, largeur, hauteur)")

    @property
    def image(self) -> Optional[Image]:
        """La premiere image. Commodite de lecture pour les tests."""
        return self.images[0][0] if self.images else None

    @property
    def image_rect(self):
        return self.images[0][1] if self.images else None


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
        xobjets = []
        for rang, (image, cadre) in enumerate(page.images):
            donnees = zlib.compress(image.data, 6)
            numero = ajouter(
                b"<< /Type /XObject /Subtype /Image /Width %d /Height %d "
                b"/ColorSpace /DeviceRGB /BitsPerComponent 8 "
                b"/Filter /FlateDecode /Length %d >>\nstream\n"
                % (image.width, image.height, len(donnees))
                + donnees
                + b"\nendstream"
            )
            x, y, largeur, hauteur = cadre
            flux.append(b"q %.2f 0 0 %.2f %.2f %.2f cm /Im%d Do Q"
                        % (largeur, hauteur, x, y, rang))
            xobjets.append(b"/Im%d %d 0 R" % (rang, numero))
        if xobjets:
            ressources.append(b"/XObject << %s >>" % b" ".join(xobjets))

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


def render_band(mosaic: Mosaic, rows: Sequence[int], scale: int) -> Image:
    """La bande SEULE, en grand, avec les joints reels entre pieces.

    `render_progress` montre l'oeuvre entiere pour situer ; elle est donc
    dominee par ce qui n'est pas encore pose. Pour POSER, il faut voir la
    bande, et la voir grande : c'est la difference entre une carte et un plan.

    Les joints sont ceux des pieces reelles, pas la grille des tenons. Une
    tuile 1x4 se lit alors comme une piece, et non comme quatre.
    """
    if not rows:
        raise ValueError("bande vide")
    if scale <= 0:
        raise ValueError("echelle invalide")
    premiere, derniere = rows[0], rows[-1]
    toile = _Canvas(mosaic.studs_x * scale, len(rows) * scale)
    for rang, row in enumerate(rows):
        for column, color in enumerate(mosaic.grid[row]):
            toile.fill(column * scale, rang * scale, scale, scale, color.rgb)

    table = bytes(round(valeur * 0.55) for valeur in range(256))

    def trait(x: int, y: int, w: int, h: int) -> None:
        for ligne in range(max(0, y), min(toile.height, y + h)):
            debut = (ligne * toile.width + max(0, x)) * 3
            fin = (ligne * toile.width + min(toile.width, x + w)) * 3
            toile.data[debut:fin] = toile.data[debut:fin].translate(table)

    epaisseur = max(1, scale // 12)
    for pose in mosaic.tiles:
        if not premiere <= pose.row <= derniere:
            continue
        rang = pose.row - premiere
        x0 = pose.column * scale
        largeur = pose.length * scale
        trait(x0, rang * scale, epaisseur, scale)
        trait(x0 + largeur - epaisseur, rang * scale, epaisseur, scale)
        trait(x0, rang * scale, largeur, epaisseur)
        trait(x0, (rang + 1) * scale - epaisseur, largeur, epaisseur)
    return toile.image()


def render_locator(mosaic: Mosaic, first_row: int, last_row: int,
                   scale: int = 2) -> Image:
    """L'oeuvre entiere en petit, la bande en cours marquee.

    Une notice LEGO montre toujours ou l'on en est. Ici l'oeuvre est plate et
    le montage se lit en lignes : le reperage doit donc dire A QUELLE HAUTEUR
    on pose, et rien d'autre. Deja pose en pale, bande en couleur pleine,
    reste en gris — les memes conventions que la vue d'ensemble, pour qu'on
    n'ait pas deux langages a apprendre.
    """
    if scale <= 0:
        raise ValueError("echelle invalide")
    toile = _Canvas(mosaic.studs_x * scale, mosaic.studs_y * scale)
    for row, colors in enumerate(mosaic.grid):
        for column, color in enumerate(colors):
            if row > last_row:
                rgb = GRIS_FUTUR if (row + column) % 2 else GRIS_FUTUR_BIS
            elif row < first_row:
                rgb = _paler(color.rgb, PALEUR_POSE)
            else:
                rgb = color.rgb
            toile.fill(column * scale, row * scale, scale, scale, rgb)
    epaisseur = max(1, scale)
    toile.fill(0, max(0, first_row * scale - epaisseur), toile.width,
               epaisseur, (0, 0, 0))
    toile.fill(0, min(toile.height - epaisseur, (last_row + 1) * scale),
               toile.width, epaisseur, (0, 0, 0))
    return toile.image()


def pieces_of_band(mosaic: Mosaic, rows: Sequence[int]):
    """Les pieces a prendre pour cette bande : (design, couleur, quantite).

    C'est l'encart de toute notice LEGO — la petite boite qui dit exactement
    quoi sortir du sachet avant de commencer. Sans elle, on cherche les pieces
    au fur et a mesure, et une notice qui fait chercher n'est pas une notice.

    Les pieces sont lues dans les tuiles REELLEMENT posees, jamais dans la
    grille : depuis la fusion, quatre tenons rouges peuvent etre une seule
    piece 1x4, et faire prendre quatre 1x1 serait une consigne fausse.
    """
    rangs = set(rows)
    compte: Dict[Tuple[str, int], int] = {}
    couleurs: Dict[int, LegoColor] = {}
    for pose in mosaic.tiles:
        if pose.row not in rangs:
            continue
        cle = (pose.design_id, pose.color.code)
        compte[cle] = compte.get(cle, 0) + 1
        couleurs[pose.color.code] = pose.color
    return tuple(
        (design, couleurs[code], quantite)
        for (design, code), quantite in sorted(
            compte.items(), key=lambda item: (-item[1], item[0][0], item[0][1])
        )
    ), couleurs


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


def row_runs(mosaic: Mosaic, row: int) -> Tuple[Tuple[int, LegoColor], ...]:
    """Une ligne de la mosaique -> les PIECES a poser, de gauche a droite.

    « 4A · 2B · 1B » se lit et se pointe ; quarante-huit cases se recomptent.

    Ce sont bien les pieces posees, lues dans le modele, et non des suites de
    couleurs lues dans la grille. Depuis la fusion, la difference est reelle :
    « 4 rouges » designe UNE tuile 1x4, et faire prendre quatre 1x1 serait une
    consigne fausse — le constructeur chercherait des pieces qui ne sont pas
    dans le sachet, et il en resterait quatre a la fin.
    """
    if not 0 <= row < mosaic.studs_y:
        raise IndexError(f"ligne {row} hors de la mosaique")
    return tuple(
        (pose.length, pose.color, pose.level)
        for pose in sorted(
            (p for p in mosaic.tiles if p.row == row), key=lambda p: p.column
        )
    )


def _lire_ligne(mosaic: Mosaic, row: int, codes: Mapping[int, str]) -> str:
    """Une ligne en toutes lettres, pieces identiques consecutives regroupees.

    Depuis la fusion, un ciel uni donne neuf tuiles 1x4 de suite, et la lecture
    brute repetait « 4B · 4B · 4B · 4B · 4B · 4B · 4B · 4B · 4B ». Personne ne
    compte neuf occurrences identiques sans se tromper : on ecrit « 9x4B ».
    """
    morceaux: List[Tuple[int, str]] = []
    for longueur, color, niveau in row_runs(mosaic, row):
        # L'etage n'est marque que s'il y en a un. La tuile se pose de toute
        # facon sur ce qui est deja la — les couches de relief sont montees
        # avant, et l'ordre est verifie contre le plan — mais le marquer
        # permet au constructeur de verifier qu'il est sur la bonne pile.
        piece = f"{longueur}{codes[color.code]}" + ("^" * niveau)
        if morceaux and morceaux[-1][1] == piece:
            morceaux[-1] = (morceaux[-1][0] + 1, piece)
        else:
            morceaux.append((1, piece))
    return " · ".join(
        piece if compte == 1 else f"{compte}x{piece}" for compte, piece in morceaux
    )


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
    premiere_ligne: int = 0,
) -> List[TextLine]:
    """Numeros de colonnes au-dessus, numeros de lignes de la bande a gauche.

    Ecrits en TEXTE PDF et non graves dans l'image : nets a l'impression quelle
    que soit la taille, et rien a embarquer comme fonte matricielle.

    `premiere_ligne` separe la POSITION dans l'image du NUMERO affiche : la vue
    d'une bande ne contient que ses propres lignes, mais le lecteur doit y lire
    les numeros de l'oeuvre entiere, sinon il compte a partir de un a chaque
    page et pose tout au meme endroit.
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
        lignes.append((x0 - 15.0, centre, CORPS_REGLETTE,
                       str(row + 1 + premiere_ligne), True))
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

    largeur_mm = ldu_to_mm(mosaic.outer_x * STUD_PITCH_LDU)
    hauteur_mm = ldu_to_mm(mosaic.outer_y * STUD_PITCH_LDU)
    # L'OEUVRE FINIE, en couleurs pleines. Pas une vue d'avancement : celle-ci
    # palit tout ce qui est deja pose, et la couverture montrerait une version
    # delavee de ce qu'on est en train de promettre.
    apercu = preview(mosaic, scale=max(3, min(12, 640 // max(1, mosaic.studs_x))))
    hauteur_liste = 44.0 + 16.0 * ((len(couleurs) + 3) // 4)
    cadre = _cadre_image(apercu, A4_HEIGHT - 140.0, BAS_TEXTE + hauteur_liste)

    textes: List[TextLine] = [
        (MARGE, A4_HEIGHT - 80, CORPS_TITRE, titre, True),
        (MARGE, A4_HEIGHT - 102, CORPS_SOUS_TITRE,
         (f"{mosaic.studs_x} x {mosaic.studs_y} tenons d'image  ·  "
          f"{mosaic.outer_x} x {mosaic.outer_y} hors cadre  "
          f"({largeur_mm / 10:.1f} x {hauteur_mm / 10:.1f} cm)")
         if mosaic.frame else
         (f"{mosaic.studs_x} x {mosaic.studs_y} tenons  "
          f"({largeur_mm / 10:.1f} x {hauteur_mm / 10:.1f} cm)"), False),
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
    return PdfPage(tuple(textes), tuple(rects), ((apercu, cadre),))


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
    altitude_des_tuiles: int = 0,
) -> List[Tuple[PdfPage, Sequence[str]]]:
    """Une page par couche posee sous les tuiles, fond puis relief.

    Fond et relief ne sont pas la meme chose et ne se nomment donc pas
    pareil. Les appeler tous « fond » faisait lire « couche 4 sur 4 » a
    quelqu'un qui posait en realite le deuxieme etage d'un bas-relief, et qui
    n'avait aucune raison de comprendre pourquoi ce fond-la ne couvrait qu'un
    quart de l'oeuvre.

    Rend la couche avec sa page : deduire l'index d'une page par un calcul sur
    la longueur de la liste marche tant que personne n'ajoute une page.
    """
    fonds = [c for c in couches
             if min(mosaic.placed_parts[p].aabb.min.z for p in c)
             < altitude_des_tuiles]
    reliefs = [c for c in couches if c not in fonds]
    pages: List[Tuple[PdfPage, Sequence[str]]] = []
    deja: List[str] = []
    for rang, couche in enumerate(couches, start=1):
        est_relief = couche in reliefs
        if est_relief:
            numero, total = reliefs.index(couche) + 1, len(reliefs)
            titre = f"Relief — etage {numero} sur {total}"
            consigne = ("Ces plates surelevent les tuiles qu'elles portent. "
                        "Elles ne couvrent qu'une partie de l'oeuvre.")
        else:
            numero, total = fonds.index(couche) + 1, len(fonds)
            titre = f"Fond — couche {numero} sur {total}"
            consigne = ("Poser toutes les plates de cette couche avant de "
                        "passer a la suivante.")
        vue = render_layer(mosaic, list(couche), list(deja), palette=palette)
        cadre = _cadre_image(vue, A4_HEIGHT - 130.0, 150.0)
        references: Dict[str, int] = {}
        for part_id in couche:
            design = mosaic.instances[part_id].design_id
            references[design] = references.get(design, 0) + 1
        # Trie par quantite decroissante et coupe : la liste des references
        # d'une couche de fond fusionnee tient rarement sur une ligne, et une
        # ligne qui deborde de la page est une ligne perdue.
        detail = " · ".join(
            f"{n} x {CATALOG[d].name if d in CATALOG else d}"
            for d, n in sorted(references.items(), key=lambda kv: (-kv[1], kv[0]))
        )
        textes: List[TextLine] = [
            (MARGE, A4_HEIGHT - 60, CORPS_TITRE * 0.75, titre, True),
            (MARGE, A4_HEIGHT - 82, CORPS_LIGNE, consigne, False),
            (MARGE, A4_HEIGHT - 93, CORPS_LIGNE,
             "Le decalage entre les couches est ce qui fait tenir le fond."
             if not est_relief else
             "Chaque etage repose sur le precedent : ne rien sauter.",
             False),
        ]
        y = 128.0
        largeur = A4_WIDTH - 2 * MARGE
        textes.append((MARGE, y, CORPS_TEXTE, f"{len(couche)} pieces :", True))
        for morceau in _couper(detail, CORPS_TEXTE, largeur):
            y -= INTERLIGNE + 1.0
            textes.append((MARGE, y, CORPS_TEXTE, morceau, False))
        if rang > 1 and not est_relief:
            textes.append((MARGE, y - INTERLIGNE - 4.0, CORPS_LIGNE,
                           "En clair : les joints de la couche precedente. Chaque "
                           "plate doit les enjamber.", False))
        pages.append((PdfPage(tuple(textes), (), ((vue, cadre),)), couche))
        deja = list(deja) + list(couche)
    return pages


def _page_cadre(mosaic: Mosaic, briques: Sequence[str],
                palette: Optional[Palette]) -> PdfPage:
    """Le cadre, en dernier — parce qu'on encadre un tableau une fois peint.

    Rien n'oblige physiquement a le poser apres : il ne recouvre aucune tuile.
    Mais une notice raconte un geste, et le geste est celui-la. Le montrer au
    milieu du fond, melange a ses plates, faisait poser une bordure noire
    autour d'un carre vide sans qu'on sache pourquoi.
    """
    vue = render_layer(mosaic, list(briques),
                       [p for p in mosaic.placed_parts if p not in set(briques)],
                       palette=palette)
    cadre = _cadre_image(vue, A4_HEIGHT - 130.0, 150.0)
    references: Dict[str, int] = {}
    for part_id in briques:
        design = mosaic.instances[part_id].design_id
        references[design] = references.get(design, 0) + 1
    detail = " · ".join(
        f"{n} x {CATALOG[d].name if d in CATALOG else d}"
        for d, n in sorted(references.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    assises = mosaic.frame_courses
    # Le lisere est ce qui DEPASSE, pas la hauteur du cadre : dire « 19,2 mm
    # au-dessus des tuiles » quand le cadre mesure 19,2 mm en tout et que les
    # tuiles en occupent la moitie, c'est doubler le relief promis.
    pied = min(mosaic.placed_parts[b].aabb.min.z for b in briques)
    sommet_cadre = pied + assises * BRICK_HEIGHT_LDU
    sommet_tuiles = max(
        (mosaic.placed_parts[mosaic.tile_id(t.row, t.column)].aabb.max.z
         for t in mosaic.tiles), default=pied)
    lisere_mm = ldu_to_mm(max(0, sommet_cadre - sommet_tuiles))
    textes: List[TextLine] = [
        (MARGE, A4_HEIGHT - 58, CORPS_TITRE, "Le cadre", True),
        (MARGE, A4_HEIGHT - 78, CORPS_SOUS_TITRE,
         f"{assises} assise(s) de briques tout autour. Il depasse la surface "
         f"de {lisere_mm:.1f} mm — c'est cette ombre qui fait le tableau.",
         False),
        (MARGE, A4_HEIGHT - 92, CORPS_LIGNE,
         "Les briques d'une assise sur l'autre ne tombent pas au meme endroit : "
         "c'est ce croisement qui fait un mur et non un empilement.", False),
    ]
    y = 128.0
    textes.append((MARGE, y, CORPS_TEXTE, f"{len(briques)} pieces :", True))
    for morceau in _couper(detail, CORPS_TEXTE, A4_WIDTH - 2 * MARGE):
        y -= INTERLIGNE + 1.0
        textes.append((MARGE, y, CORPS_TEXTE, morceau, False))
    textes.append((MARGE, y - INTERLIGNE - 4.0, CORPS_LIGNE,
                   "En clair : l'oeuvre terminee. Le cadre se pose tout autour, "
                   "sans jamais la recouvrir.", False))
    return PdfPage(tuple(textes), (), ((vue, cadre),))


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
            _couper(_lire_ligne(mosaic, row, codes), CORPS_LIGNE, largeur),
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


ENCART_FOND = (238, 238, 234)
ENCART_TRAIT = (196, 196, 190)
PASTILLE = 9.0
"""Cote de la pastille de couleur dans l'encart des pieces, en points."""
LETTRE_MINIMALE = 9.0
"""En dessous de cette largeur de case, on n'imprime plus la lettre du code.

Une lettre de trois points n'est pas une lettre, c'est une salissure qui cache
la couleur — la seule information que la case transmet vraiment. Au-dela de
cinquante tenons de large, l'encart et la couleur suffisent.
"""


def _encart_pieces(mosaic: Mosaic, rows: Sequence[int], codes: Mapping[int, str],
                   x: float, sommet: float, largeur: float):
    """L'encart « ce qu'il faut sortir du sachet ». (rects, textes, hauteur)."""
    pieces, _ = pieces_of_band(mosaic, rows)
    colonnes = max(1, int(largeur // 132))
    lignes = (len(pieces) + colonnes - 1) // colonnes
    pas_y = 13.0
    hauteur = 20.0 + lignes * pas_y
    rects = [
        (x, sommet - hauteur, largeur, hauteur, ENCART_FOND),
        (x, sommet - hauteur, largeur, 0.8, ENCART_TRAIT),
        (x, sommet - 0.8, largeur, 0.8, ENCART_TRAIT),
    ]
    textes: List[TextLine] = [
        (x + 8, sommet - 13, CORPS_TEXTE, "A sortir pour cette etape", True)
    ]
    pas_x = largeur / colonnes
    for index, (design, couleur, quantite) in enumerate(pieces):
        colonne, ligne = index % colonnes, index // colonnes
        cx = x + 8 + colonne * pas_x
        cy = sommet - 24 - ligne * pas_y
        rects.append((cx, cy - PASTILLE + 2.5, PASTILLE, PASTILLE, couleur.rgb))
        rects.append((cx, cy - PASTILLE + 2.5, PASTILLE, PASTILLE,
                      ENCART_TRAIT) if False else
                     (cx, cy - PASTILLE + 2.5, 0.6, PASTILLE, ENCART_TRAIT))
        etiquette = codes.get(couleur.code, "?")
        nom = CATALOG[design].name.replace(" with Groove", "")
        textes.append((cx + PASTILLE + 4, cy - 6, CORPS_TEXTE,
                       f"{quantite} x", True))
        textes.append((cx + PASTILLE + 26, cy - 6, CORPS_LIGNE,
                       f"{etiquette}  {nom}", False))
    return rects, textes, hauteur


def _lettres_sur_bande(mosaic: Mosaic, rows: Sequence[int],
                       codes: Mapping[int, str], cadre) -> List[TextLine]:
    """Une lettre au centre de chaque PIECE, jamais de chaque tenon.

    Le lecteur pose des pieces : lui imprimer quatre fois « A » sur une tuile
    1x4 lui ferait compter quatre pieces la ou il n'en prend qu'une.
    """
    x0, y0, largeur, hauteur = cadre
    case = largeur / mosaic.studs_x
    if case < LETTRE_MINIMALE:
        return []
    corps = min(9.0, case * 0.62)
    premiere, derniere = rows[0], rows[-1]
    textes: List[TextLine] = []
    for pose in mosaic.tiles:
        if not premiere <= pose.row <= derniere:
            continue
        rang = pose.row - premiere
        centre_x = x0 + (pose.column + pose.length / 2) * case
        centre_y = y0 + hauteur - (rang + 0.5) * case
        lettre = codes.get(pose.color.code, "?")
        # Le decalage horizontal approche le centrage : les polices de base du
        # PDF n'exposent pas leurs largeurs ici, et une lettre majuscule de
        # Helvetica-Bold fait environ 0,72 cadratin.
        textes.append((centre_x - corps * 0.36, centre_y - corps * 0.35,
                       corps, lettre, True))
    return textes


ECART_ETAPES = 18.0
"""Blanc entre deux etapes de la meme page. Assez pour qu'on ne les confonde
pas, pas assez pour qu'on croie a une page finie."""


def _hauteur_etape(mosaic: Mosaic, rows: Sequence[int], mise: _Mise,
                   largeur: float):
    """Hauteur d'une etape, encart compris. Sert a savoir combien tiennent."""
    _, _, hauteur_encart = _encart_pieces(mosaic, rows, mise.codes, 0, 0, largeur)
    hauteur_bande = (largeur - RESERVE_REGLETTE) * len(rows) / mosaic.studs_x
    return 22.0 + hauteur_encart + 10.0 + hauteur_bande


def _une_etape(mosaic: Mosaic, rows: Sequence[int], numero: int, total: int,
               mise: _Mise, sommet: float, largeur: float):
    """Une etape posee a partir de `sommet`. (rects, textes, images, bas)."""
    first_row, last_row = rows[0], rows[-1]
    rects, textes, hauteur_encart = _encart_pieces(
        mosaic, rows, mise.codes, MARGE, sommet - 22.0, largeur
    )
    textes = [
        (MARGE, sommet - 15.0, CORPS_TITRE * 0.85,
         f"Etape {numero} / {total}", True),
        (MARGE + 96.0, sommet - 15.0, CORPS_SOUS_TITRE,
         f"lignes {first_row + 1} a {last_row + 1}, de gauche a droite"
         + (" — un ^ par etage de relief"
            if any(p.level for p in mosaic.tiles) else ""), False),
    ] + textes

    largeur_bande = largeur - RESERVE_REGLETTE
    hauteur_bande = largeur_bande * len(rows) / mosaic.studs_x
    cadre_bande = (MARGE + RESERVE_REGLETTE,
                   sommet - 22.0 - hauteur_encart - 10.0 - hauteur_bande,
                   largeur_bande, hauteur_bande)
    echelle = max(6, min(24, int(600 / max(1, mosaic.studs_x)) + 6))
    bande = render_band(mosaic, rows, echelle)
    textes.extend(_reglette(cadre_bande, mosaic.studs_x, len(rows), 0,
                            len(rows) - 1, premiere_ligne=first_row))
    textes.extend(_lettres_sur_bande(mosaic, rows, mise.codes, cadre_bande))
    return rects, textes, [(bande, cadre_bande)], cadre_bande[1]


def _pages_etapes(mosaic: Mosaic, bandes: Sequence[Sequence[int]], mise: _Mise):
    """Les pages d'etapes, PLUSIEURS ETAPES PAR PAGE quand elles tiennent.

    Une notice LEGO met deux a quatre etapes numerotees par page ; c'est ce
    qui rend le fascicule mince et la progression visible. La version
    precedente en mettait une, et une bande de quatre lignes sur une oeuvre de
    trente-deux laissait les deux tiers de la feuille blancs.

    Rend (pages, index de page de chaque bande) : le controle d'ordre a besoin
    de savoir sur quelle page chaque tuile se pose, et le deduire de la
    longueur de la liste cesse d'etre vrai des qu'une page porte deux etapes.
    """
    largeur = A4_WIDTH - 2 * MARGE
    pages: List[PdfPage] = []
    page_de_bande: List[int] = []
    plancher = BAS_TEXTE + mise.reserve

    index = 0
    while index < len(bandes):
        sommet = A4_HEIGHT - 46.0
        rects: List[RectFill] = []
        textes: List[TextLine] = []
        images = []
        premiere = index
        while index < len(bandes):
            hauteur = _hauteur_etape(mosaic, bandes[index], mise, largeur)
            if images and sommet - hauteur < plancher + 96.0:
                break
            r, t, i, bas = _une_etape(
                mosaic, bandes[index], index + 1, len(bandes), mise,
                sommet, largeur,
            )
            rects.extend(r)
            textes.extend(t)
            images.extend(i)
            page_de_bande.append(len(pages))
            sommet = bas - ECART_ETAPES
            index += 1

        # Le reperage, une fois par page : il dit ou l'on en est arrive au
        # bout de la page, pas au bout de chaque etape.
        derniere = bandes[index - 1]
        reperage = render_locator(mosaic, bandes[premiere][0], derniere[-1])
        largeur_reperage = 96.0
        hauteur_reperage = largeur_reperage * mosaic.studs_y / mosaic.studs_x
        bas_reperage = max(plancher, sommet - 8.0 - hauteur_reperage)
        cadre_reperage = (MARGE, bas_reperage, largeur_reperage, hauteur_reperage)
        images.append((reperage, cadre_reperage))
        textes.append((MARGE + largeur_reperage + 12,
                       bas_reperage + hauteur_reperage - 9,
                       CORPS_TEXTE, "Ou l'on en est", True))
        textes.append((MARGE + largeur_reperage + 12,
                       bas_reperage + hauteur_reperage - 21, CORPS_LIGNE,
                       "En pale : deja pose. En gris : pas encore.", False))

        pages.append(PdfPage(tuple(textes) + mise.textes,
                             tuple(rects) + mise.rects, tuple(images)))
    return pages, page_de_bande


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

    # Les tuiles reellement posees, et pas un identifiant par tenon : depuis la
    # fusion, une tuile 1x4 couvre quatre tenons et n'existe qu'une fois.
    tuiles = set(mosaic.tile_ids)
    manquantes = tuiles - set(mosaic.placed_parts)
    if manquantes:  # pragma: no cover - la mosaique pose toutes ses tuiles
        raise KeyError(f"{len(manquantes)} tuiles absentes du modele")

    # Les couches de fond se lisent dans les altitudes, pas dans les noms.
    # Le cadre n'est pas une couche de fond : il ne porte rien et se pose en
    # dernier. Melange aux plates du substrat, il faisait poser une bordure
    # noire autour d'un carre vide.
    briques_de_cadre = sorted(
        part_id for part_id in mosaic.placed_parts
        if part_id.startswith("C") and part_id not in tuiles
    )
    par_altitude: Dict[int, List[str]] = {}
    for part_id in sorted(set(mosaic.placed_parts) - tuiles
                          - set(briques_de_cadre)):
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

    altitude_des_tuiles = min(
        (mosaic.placed_parts[t].aabb.min.z for t in tuiles), default=0)
    for page, couche in _pages_substrat(mosaic, couches, palette,
                                        altitude_des_tuiles):
        pages.append(page)
        for part_id in couche:
            page_de[part_id] = len(pages) - 1

    bandes = _decouper_bandes(mosaic, rows_per_page, mise)
    depart = len(pages)
    pages_etapes, page_de_bande = _pages_etapes(mosaic, bandes, mise)
    pages.extend(pages_etapes)
    for numero, rows in enumerate(bandes):
        rangs = set(rows)
        for pose in mosaic.tiles:
            if pose.row in rangs:
                page_de[mosaic.tile_id(pose.row, pose.column)] = (
                    depart + page_de_bande[numero])

    if briques_de_cadre:
        pages.append(_page_cadre(mosaic, briques_de_cadre, palette))
        for part_id in briques_de_cadre:
            page_de[part_id] = len(pages) - 1

    _verifier_ordre(plan, page_de)

    total = len(pages)
    finales = [
        PdfPage(
            page.texts + tuple(_pied(numero, total, title)),
            page.rects,
            page.images,
        )
        for numero, page in enumerate(pages, start=1)
    ]
    return write_pdf(finales)
