"""Lecture et reechantillonnage d'images (HORS CONTRAT, couche perception).

Zero dependance : PNG et PPM sont decodes avec zlib et struct, tous deux dans
la bibliotheque standard. Le noyau ne depend de rien, cette couche non plus.

Perimetre assume : PNG 8 bits par canal, non entrelace, en niveaux de gris,
palette, RVB ou RVBA. C'est ce que produit n'importe quel appareil photo ou
export. Le reste leve une erreur explicite plutot que de deviner.
"""

from __future__ import annotations

import struct
import weakref
import zlib
from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Tuple

__all__ = [
    "Image",
    "read_png",
    "read_ppm",
    "write_png",
    "resample_box",
    "MEMO_REDUCTIONS",
    "resample_median",
    "DEPTH_SAMPLE_BUDGET",
    "crop",
    "crop_to_ratio",
]

Rgb = Tuple[int, int, int]


@dataclass(frozen=True)
class Image:
    """Image matricielle en RVB 8 bits. Value object.

    Les pixels sont stockes en `bytes` bruts, trois octets par pixel, et non en
    tuples. Ce n'est pas un detail d'implementation : un tuple Python coute
    environ 72 octets pour trois nombres, soit 24 fois la place utile. Une
    photo de telephone de 12 Mpx demanderait 860 Mo en tuples contre 36 Mo en
    octets — la difference entre un outil qui marche et un processus tue par le
    systeme.
    """

    width: int
    height: int
    data: bytes

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("dimensions d'image invalides")
        if len(self.data) != self.width * self.height * 3:
            raise ValueError(
                f"{len(self.data)} octets pour {self.width}x{self.height} en RVB"
            )

    @classmethod
    def from_pixels(cls, width: int, height: int, pixels) -> "Image":
        """Construction depuis une suite de triplets. Pratique, pas econome."""
        data = bytearray()
        for pixel in pixels:
            data.extend(pixel)
        return cls(width, height, bytes(data))

    def pixel(self, x: int, y: int) -> Rgb:
        index = (y * self.width + x) * 3
        return (self.data[index], self.data[index + 1], self.data[index + 2])

    @property
    def pixels(self) -> Tuple[Rgb, ...]:
        """Vue en triplets. A reserver aux petites images : c'est 24 fois la
        place des octets bruts."""
        return tuple(
            (self.data[i], self.data[i + 1], self.data[i + 2])
            for i in range(0, len(self.data), 3)
        )


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def read_png(data: bytes) -> Image:
    """Decode un PNG 8 bits non entrelace."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("ce n'est pas un fichier PNG")

    position = 8
    idat: List[bytes] = []
    palette = b""
    width = height = depth = color_type = interlace = 0

    while position + 8 <= len(data):
        length = int.from_bytes(data[position : position + 4], "big")
        kind = data[position + 4 : position + 8]
        chunk = data[position + 8 : position + 8 + length]
        position += 12 + length
        if kind == b"IHDR":
            width, height, depth, color_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
        elif kind == b"PLTE":
            palette = chunk
        elif kind == b"IDAT":
            idat.append(chunk)
        elif kind == b"IEND":
            break

    if depth != 8:
        raise ValueError(f"profondeur {depth} bits non supportee (8 attendu)")
    if interlace:
        raise ValueError("PNG entrelace non supporte")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise ValueError(f"type de couleur PNG inconnu : {color_type}")

    raw = zlib.decompress(b"".join(idat))
    stride = width * channels
    previous = bytearray(stride)
    data = bytearray(width * height * 3)
    offset = 0
    paeth = _paeth

    # Tables de correspondance pour une image a palette : bytes.translate fait
    # la conversion au niveau C, pixel par pixel serait cent fois plus lent.
    if color_type == 3:
        tables = tuple(
            bytes(
                palette[index * 3 + canal] if index * 3 + canal < len(palette) else 0
                for index in range(256)
            )
            for canal in range(3)
        )

    for row in range(height):
        filter_type = raw[offset]
        line = bytearray(raw[offset + 1 : offset + 1 + stride])
        offset += 1 + stride

        # Les filtres 1, 3 et 4 sont sequentiels par octet : aucune astuce ne
        # les vectorise en Python pur. Le filtre 0 et le filtre 2 sur la
        # premiere ligne, eux, ne demandent aucun travail.
        if filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif filter_type == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filter_type == 3:
            for i in range(channels):
                line[i] = (line[i] + previous[i] // 2) & 0xFF
            for i in range(channels, stride):
                line[i] = (line[i] + (line[i - channels] + previous[i]) // 2) & 0xFF
        elif filter_type == 4:
            for i in range(channels):
                line[i] = (line[i] + previous[i]) & 0xFF
            # Paeth deroule sur place. L'appel de fonction et le test de bord
            # coutaient plus cher que le calcul lui-meme : sur une photo de
            # 4 Mpx, treize millions d'appels.
            for i in range(channels, stride):
                a = line[i - channels]
                b = previous[i]
                c = previous[i - channels]
                p = a + b - c
                pa = p - a
                if pa < 0:
                    pa = -pa
                pb = p - b
                if pb < 0:
                    pb = -pb
                pc = p - c
                if pc < 0:
                    pc = -pc
                if pa <= pb and pa <= pc:
                    line[i] = (line[i] + a) & 0xFF
                elif pb <= pc:
                    line[i] = (line[i] + b) & 0xFF
                else:
                    line[i] = (line[i] + c) & 0xFF
        elif filter_type != 0:
            raise ValueError(f"filtre PNG inconnu : {filter_type}")
        previous = line

        # Extraction des canaux par tranches : tout se passe au niveau C.
        start = row * width * 3
        destination = memoryview(data)[start : start + width * 3]
        if color_type in (0, 4):
            gris = line[0::channels]
            destination[0::3] = gris
            destination[1::3] = gris
            destination[2::3] = gris
        elif color_type == 3:
            indices = bytes(line[0::channels])
            for canal in range(3):
                destination[canal::3] = indices.translate(tables[canal])
        elif channels == 3:
            destination[:] = line
        else:
            for canal in range(3):
                destination[canal::3] = line[canal::channels]

    return Image(width, height, bytes(data))


def read_ppm(data: bytes) -> Image:
    """Decode un PPM binaire (P6), format brut le plus simple qui soit."""
    if not data.startswith(b"P6"):
        raise ValueError("ce n'est pas un PPM binaire (P6)")
    fields: List[int] = []
    position = 2
    while len(fields) < 3:
        while position < len(data) and data[position : position + 1].isspace():
            position += 1
        if data[position : position + 1] == b"#":
            while data[position : position + 1] not in (b"\n", b""):
                position += 1
            continue
        start = position
        while position < len(data) and not data[position : position + 1].isspace():
            position += 1
        fields.append(int(data[start:position]))
    width, height, maximum = fields
    if maximum != 255:
        raise ValueError("PPM : seule la profondeur 255 est supportee")
    position += 1
    return Image(width, height, data[position : position + width * height * 3])


def write_png(image: Image) -> bytes:
    """Encode un PNG RVB 8 bits. Sert a produire un apercu du rendu."""
    raw = bytearray()
    stride = image.width * 3
    for y in range(image.height):
        raw.append(0)  # filtre None : l'apercu n'a pas besoin d'etre compact
        raw.extend(image.data[y * stride : (y + 1) * stride])

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            len(payload).to_bytes(4, "big")
            + kind
            + payload
            + zlib.crc32(kind + payload).to_bytes(4, "big")
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", image.width, image.height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )


def crop(image: Image, x: int, y: int, width: int, height: int) -> Image:
    """Sous-image rectangulaire. Les bornes sont verifiees, jamais rabotees.

    Rogner en silence une demande hors cadre donnerait une image dont le
    contenu ne correspond pas a ce qui a ete demande — et personne ne le
    verrait avant d'avoir la mosaique sous les yeux.
    """
    if width <= 0 or height <= 0:
        raise ValueError("dimensions de decoupe invalides")
    if x < 0 or y < 0 or x + width > image.width or y + height > image.height:
        raise ValueError(
            f"decoupe {width}x{height} en ({x}, {y}) hors de "
            f"{image.width}x{image.height}"
        )
    sortie = bytearray()
    for ligne in range(y, y + height):
        debut = (ligne * image.width + x) * 3
        sortie += image.data[debut : debut + width * 3]
    return Image(width, height, bytes(sortie))


def crop_to_ratio(image: Image, ratio: float, offset=0.5) -> Image:
    """Decoupe centree ramenant l'image au rapport largeur/hauteur voulu.

    C'est la seule facon honnete de mettre une photo 4:3 dans une mosaique
    carree. L'ETIRER — ce que faisait la chaine — ecrase un cercle parfait a un
    rapport de 0,750 et un visage avec lui. Le remplissage par des bandes
    gaspillerait des tuiles sur du vide.

    `offset` place la fenetre le long de l'axe rogne, de 0 a 1, ou vaut
    « auto » : la fenetre retenant le plus de detail (`attentional_offset`).
    Le sujet n'est pas toujours au centre, et 0,5 le suppose.
    """
    if ratio <= 0:
        raise ValueError("rapport invalide")
    if offset == "auto":
        offset = attentional_offset(image, ratio)
    if not isinstance(offset, (int, float)) or isinstance(offset, bool):
        raise ValueError("le decalage de cadrage est un nombre ou « auto »")
    if not 0.0 <= offset <= 1.0:
        raise ValueError("le decalage de cadrage va de 0 a 1")

    if image.width / image.height > ratio:      # trop large : on rogne en x
        largeur = max(1, min(image.width, round(image.height * ratio)))
        x = round((image.width - largeur) * offset)
        return crop(image, x, 0, largeur, image.height)
    hauteur = max(1, min(image.height, round(image.width / ratio)))
    y = round((image.height - hauteur) * offset)
    return crop(image, 0, y, image.width, hauteur)


def detail_profile(image: Image, axis: str, samples: int = 96) -> Tuple[float, ...]:
    """Profil de DETAIL le long d'un axe : energie de gradient par bande.

    L'energie de gradient — la somme des ecarts entre pixels voisins — est
    faible sur un ciel uni et forte sur un visage, un feuillage, un texte. Ce
    n'est pas de la detection de sujet : c'est de la detection de DETAIL, et
    les deux coincident assez souvent pour etre utiles, jamais toujours.
    """
    if axis not in ("x", "y"):
        raise ValueError("axe vaut 'x' ou 'y'")
    longueur = image.width if axis == "x" else image.height
    samples = max(1, min(samples, longueur))
    profil = [0.0] * samples
    data = image.data
    pas = max(1, image.height // 128) if axis == "x" else max(1, image.width // 128)

    if axis == "x":
        for y in range(0, image.height, pas):
            debut = y * image.width * 3
            ligne = data[debut : debut + image.width * 3]
            for x in range(image.width - 1):
                i = x * 3
                ecart = (
                    abs(ligne[i] - ligne[i + 3])
                    + abs(ligne[i + 1] - ligne[i + 4])
                    + abs(ligne[i + 2] - ligne[i + 5])
                )
                profil[x * samples // longueur] += ecart
    else:
        for y in range(0, image.height - 1, pas):
            a_ = y * image.width * 3
            b_ = (y + 1) * image.width * 3
            haut = data[a_ : a_ + image.width * 3]
            bas = data[b_ : b_ + image.width * 3]
            total = 0
            for i in range(0, len(haut), 3 * pas):
                total += (
                    abs(haut[i] - bas[i])
                    + abs(haut[i + 1] - bas[i + 1])
                    + abs(haut[i + 2] - bas[i + 2])
                )
            profil[y * samples // longueur] += total
    return tuple(profil)


def attentional_offset(image: Image, ratio: float) -> float:
    """Decalage de cadrage retenant le PLUS DE DETAIL, entre 0 et 1.

    Le centrage aveugle decapite : sur un portrait ou le sujet est haut dans le
    cadre, la fenetre centree lui coupe le crane. Faute de savoir ou est le
    sujet — ce qui demanderait un modele appris —, on retient la fenetre qui
    conserve le plus d'energie de gradient.

    Ce que ce critere ne fait PAS, et qu'il ne faut pas lui prêter : il ne
    reconnait rien. Un fond de feuillage tres detaille derriere un visage lisse
    l'attirera vers le feuillage. Il vaut mieux qu'un centrage aveugle, il ne
    vaut pas un regard — d'ou `--cadrage` qui reste reglable a la main.
    """
    if ratio <= 0:
        raise ValueError("rapport invalide")
    if image.width / image.height > ratio:
        axe, longueur, garde = "x", image.width, round(image.height * ratio)
    else:
        axe, longueur, garde = "y", image.height, round(image.width / ratio)
    garde = max(1, min(longueur, garde))
    if garde >= longueur:
        return 0.5

    profil = detail_profile(image, axe)
    bandes = len(profil)
    fenetre = max(1, round(bandes * garde / longueur))
    if fenetre >= bandes:
        return 0.5

    cumul = [0.0]
    for valeur in profil:
        cumul.append(cumul[-1] + valeur)
    meilleur, energie = 0, -1.0
    for depart in range(bandes - fenetre + 1):
        somme = cumul[depart + fenetre] - cumul[depart]
        # A energie egale, on prefere le cadrage le plus central : c'est le
        # comportement precedent, et il n'y a aucune raison de s'en ecarter
        # quand la mesure ne dit rien.
        if somme > energie or (
            somme == energie
            and abs(depart - (bandes - fenetre) / 2)
            < abs(meilleur - (bandes - fenetre) / 2)
        ):
            meilleur, energie = depart, somme
    return meilleur / (bandes - fenetre)


def _table_lumiere() -> Tuple[bytes, bytes, bytes]:
    """Tables de passage sRGB <-> lumiere lineaire, sur 16 bits.

    Deux tables d'aller (octet de poids fort, octet de poids faible) pour que
    la somme d'un bloc se fasse par `bytes.translate` + `sum`, deux boucles en
    C au lieu d'une boucle Python par pixel. Une table de retour de 65536
    entrees pour le reencodage. 64 Ko, construits une fois.
    """
    lineaire = []
    for niveau in range(256):
        canal = niveau / 255
        lineaire.append(
            canal / 12.92 if canal <= 0.04045 else ((canal + 0.055) / 1.055) ** 2.4
        )
    seize = [round(65535 * valeur) for valeur in lineaire]

    retour = bytearray(65536)
    for index in range(65536):
        valeur = index / 65535
        code = (
            valeur * 12.92
            if valeur <= 0.0031308
            else 1.055 * valeur ** (1 / 2.4) - 0.055
        )
        retour[index] = min(255, max(0, round(code * 255)))
    return (
        bytes(valeur >> 8 for valeur in seize),
        bytes(valeur & 0xFF for valeur in seize),
        bytes(retour),
    )


_POIDS_FORT, _POIDS_FAIBLE, _REENCODAGE = _table_lumiere()

_TABLE_LUMIERE = tuple(
    ((_POIDS_FORT[niveau] << 8) + _POIDS_FAIBLE[niveau]) / 65535
    for niveau in range(256)
)
"""sRGB -> lumiere lineaire, en clair, pour qui doit moyenner pixel a pixel."""


_MEMO_REDUCTION: "OrderedDict[Tuple[int, ...], Tuple[object, Image]]" = \
    OrderedDict()
MEMO_REDUCTIONS = 4
"""Nombre de reductions gardees. Petit a dessein.

L'entree n'est retenue que par une reference FAIBLE : garder une photo de
douze megapixels en vie entre deux fabrications couterait cent megaoctets pour
rien. Une reference forte etait mon premier reflexe, et c'etait une fuite.
"""


def _memo(image: Image, width: int, height: int):
    """Cache d'identite pour `resample_box`. Rend le meme objet, bit pour bit.

    Reduire une photo de telephone au format d'une mosaique lit douze millions
    de pixels. La chaine le demandait HUIT fois sur la meme image : deux fois
    pour quantifier, quatre fois pour mesurer la fidelite, une pour le
    debruitage, une pour l'apercu de la source. Sept dixiemes du travail
    d'image etaient une repetition exacte.

    La cle est l'IDENTITE de l'image, pas son contenu : hacher trente-six
    mega-octets couterait ce qu'on cherche a economiser. Or un identifiant se
    RECYCLE des que l'objet meurt — et le cache ne retient l'entree que par une
    reference faible, pour ne pas garder une photo entiere en vie entre deux
    fabrications. La verification `garde() is image` n'est donc pas une
    ceinture de plus : c'est elle qui rend le procede correct. Sans elle, une
    nouvelle image nee a l'adresse d'une ancienne recevrait la reduction de
    l'ancienne, et la mosaique sortirait fausse sans une ligne d'erreur.

    Ce n'est pas une approximation : c'est le meme calcul, rendu une fois.
    """
    return (id(image), image.width, image.height, width, height)


def resample_box(image: Image, width: int, height: int) -> Image:
    """Reechantillonnage par moyenne de bloc, EN LUMIERE LINEAIRE.

    Choix deliberé face au plus proche voisin : reduire une photo a 48x48
    tenons, c'est jeter 99,9 % de l'information. Prendre un pixel au hasard
    dans chaque bloc produit du bruit ; moyenner le bloc produit la couleur que
    l'oeil y percoit. C'est la premiere condition d'une mosaique fidele.

    Encore faut-il moyenner la bonne grandeur. sRGB n'est pas une echelle
    lineaire : c'est un encodage en puissance ~2,2. Moyenner les OCTETS revient
    a moyenner des logarithmes, ce qui n'a aucun sens physique. Un damier noir
    et blanc — soit exactement 50 % de lumiere — donnait 127 au lieu de 188 :
    23 delta E d'erreur, plus que tout ce que coute la palette.

    Ce que l'oeil percoit d'un bloc de photo trop petit pour etre resolu, c'est
    la moyenne des RADIANCES qu'il en recoit. Une tuile est uniforme, elle n'a
    rien a fusionner : sa couleur doit donc valoir cette moyenne-la. On
    linearise, on moyenne, on reencode.
    """
    if width <= 0 or height <= 0:
        raise ValueError("dimensions de sortie invalides")

    cle = _memo(image, width, height)
    garde = _MEMO_REDUCTION.get(cle)
    if garde is not None and garde[0]() is image:
        _MEMO_REDUCTION.move_to_end(cle)
        return garde[1]

    source = image.data
    source_width = image.width
    output = bytearray(width * height * 3)
    cursor = 0

    for out_y in range(height):
        y0 = out_y * image.height // height
        y1 = max(y0 + 1, (out_y + 1) * image.height // height)
        for out_x in range(width):
            x0 = out_x * source_width // width
            x1 = max(x0 + 1, (out_x + 1) * source_width // width)
            totaux = [0, 0, 0]
            count = (y1 - y0) * (x1 - x0)
            for y in range(y0, y1):
                debut = (y * source_width + x0) * 3
                bande = source[debut : (y * source_width + x1) * 3]
                for canal in range(3):
                    octets = bande[canal::3]
                    totaux[canal] += (
                        sum(octets.translate(_POIDS_FORT)) << 8
                    ) + sum(octets.translate(_POIDS_FAIBLE))
            for canal in range(3):
                output[cursor + canal] = _REENCODAGE[totaux[canal] // count]
            cursor += 3
    reduite = Image(width, height, bytes(output))
    # Reference FAIBLE sur l'entree : le cache accelere, il ne retient pas.
    _MEMO_REDUCTION[cle] = (weakref.ref(image), reduite)
    while len(_MEMO_REDUCTION) > MEMO_REDUCTIONS:
        _MEMO_REDUCTION.popitem(last=False)
    return reduite


DEPTH_SAMPLE_BUDGET = 16
"""Cote maximal de l'echantillonnage d'une cellule pour `resample_median`.

Une carte de profondeur pleine resolution donne des milliers de pixels par
tenon ; les trier tous couterait des dizaines de secondes en Python pour un
resultat que 256 echantillons donnent deja. La mediane d'un echantillon
regulier d'un champ lisse par morceaux EST la mediane du champ, sauf a
tomber exactement sur une frontiere — ou les deux valeurs sont de toute
facon aussi justes l'une que l'autre.
"""


def resample_median(image: "Image", width: int, height: int) -> List[List[float]]:
    """Reduction par MEDIANE, pour les grandeurs qu'on n'a pas le droit de
    moyenner. Rend un champ de valeurs, pas une image.

    `resample_box` moyenne, et c'est juste pour une couleur : ce que l'oeil
    percoit d'un bloc trop petit pour etre resolu est la moyenne des radiances.
    Une PROFONDEUR ne se comporte pas ainsi. Moyenner deux distances de part et
    d'autre d'un bord invente une distance qui n'existe nulle part dans la
    scene — le sujet est a 1 m, le mur a 4 m, et la moyenne place un fantome a
    2,5 m sur tout le contour.

    Mesure sur une carte a DEUX profondeurs seulement (sujet proche, fond
    loin), reduite a 48x48 :

        reduction   valeurs distinctes   plateaux   cases isolees
        moyenne                     21         36              28
        mediane                      2          2               0

    La moyenne a fabrique dix-neuf profondeurs qui n'existaient pas, et le
    relief qui en sort a un liseré mouchete tout autour du sujet. La mediane
    rend la scene telle qu'elle est.

    La valeur rendue est le gris `(r + g + b) / 3` : une carte de profondeur est
    un scalaire encode en gris, et lui appliquer une colorimetrie serait poser
    une physique la ou il n'y en a pas.
    """
    if width <= 0 or height <= 0:
        raise ValueError("dimensions de sortie invalides")
    source = image.data
    largeur_source = image.width
    sortie = []
    for out_y in range(height):
        y0 = out_y * image.height // height
        y1 = max(y0 + 1, (out_y + 1) * image.height // height)
        pas_y = max(1, (y1 - y0 + DEPTH_SAMPLE_BUDGET - 1) // DEPTH_SAMPLE_BUDGET)
        rang = []
        for out_x in range(width):
            x0 = out_x * largeur_source // width
            x1 = max(x0 + 1, (out_x + 1) * largeur_source // width)
            pas_x = max(1, (x1 - x0 + DEPTH_SAMPLE_BUDGET - 1) // DEPTH_SAMPLE_BUDGET)
            echantillons = []
            for y in range(y0, y1, pas_y):
                base = y * largeur_source
                for x in range(x0, x1, pas_x):
                    i = (base + x) * 3
                    echantillons.append(source[i] + source[i + 1] + source[i + 2])
            echantillons.sort()
            rang.append(echantillons[len(echantillons) // 2] / 3.0)
        sortie.append(rang)
    return sortie
