"""Lecture et reechantillonnage d'images (HORS CONTRAT, couche perception).

Zero dependance : PNG et PPM sont decodes avec zlib et struct, tous deux dans
la bibliotheque standard. Le noyau ne depend de rien, cette couche non plus.

Perimetre assume : PNG 8 bits par canal, non entrelace, en niveaux de gris,
palette, RVB ou RVBA. C'est ce que produit n'importe quel appareil photo ou
export. Le reste leve une erreur explicite plutot que de deviner.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from typing import List, Tuple

__all__ = ["Image", "read_png", "read_ppm", "write_png", "resample_box"]

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
    return Image(width, height, bytes(output))
