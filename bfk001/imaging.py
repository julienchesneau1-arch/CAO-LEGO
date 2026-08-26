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
    """Image matricielle en RVB 8 bits. Value object."""

    width: int
    height: int
    pixels: Tuple[Rgb, ...]

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("dimensions d'image invalides")
        if len(self.pixels) != self.width * self.height:
            raise ValueError(
                f"{len(self.pixels)} pixels pour {self.width}x{self.height}"
            )

    def pixel(self, x: int, y: int) -> Rgb:
        return self.pixels[y * self.width + x]


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
    pixels: List[Rgb] = []
    offset = 0

    for _ in range(height):
        filter_type = raw[offset]
        line = bytearray(raw[offset + 1 : offset + 1 + stride])
        offset += 1 + stride
        for i in range(stride):
            left = line[i - channels] if i >= channels else 0
            up = previous[i]
            up_left = previous[i - channels] if i >= channels else 0
            if filter_type == 1:
                line[i] = (line[i] + left) & 0xFF
            elif filter_type == 2:
                line[i] = (line[i] + up) & 0xFF
            elif filter_type == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif filter_type == 4:
                line[i] = (line[i] + _paeth(left, up, up_left)) & 0xFF
            elif filter_type != 0:
                raise ValueError(f"filtre PNG inconnu : {filter_type}")
        previous = line

        for x in range(width):
            base = x * channels
            if color_type in (0, 4):
                value = line[base]
                pixels.append((value, value, value))
            elif color_type == 3:
                index = line[base] * 3
                pixels.append(
                    (palette[index], palette[index + 1], palette[index + 2])
                )
            else:
                pixels.append((line[base], line[base + 1], line[base + 2]))

    return Image(width, height, tuple(pixels))


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
    body = data[position : position + width * height * 3]
    pixels = tuple(
        (body[i], body[i + 1], body[i + 2]) for i in range(0, len(body), 3)
    )
    return Image(width, height, pixels)


def write_png(image: Image) -> bytes:
    """Encode un PNG RVB 8 bits. Sert a produire un apercu du rendu."""
    raw = bytearray()
    for y in range(image.height):
        raw.append(0)  # filtre None : l'apercu n'a pas besoin d'etre compact
        for x in range(image.width):
            raw.extend(image.pixel(x, y))

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


def resample_box(image: Image, width: int, height: int) -> Image:
    """Reechantillonnage par moyenne de bloc.

    Choix deliberé face au plus proche voisin : reduire une photo a 48x48
    tenons, c'est jeter 99,9 % de l'information. Prendre un pixel au hasard
    dans chaque bloc produit du bruit ; moyenner le bloc produit la couleur que
    l'oeil y percoit. C'est la premiere condition d'une mosaique fidele.
    """
    if width <= 0 or height <= 0:
        raise ValueError("dimensions de sortie invalides")

    pixels: List[Rgb] = []
    for out_y in range(height):
        y0 = out_y * image.height // height
        y1 = max(y0 + 1, (out_y + 1) * image.height // height)
        for out_x in range(width):
            x0 = out_x * image.width // width
            x1 = max(x0 + 1, (out_x + 1) * image.width // width)
            red = green = blue = count = 0
            for y in range(y0, y1):
                row = y * image.width
                for x in range(x0, x1):
                    r, g, b = image.pixels[row + x]
                    red += r
                    green += g
                    blue += b
                    count += 1
            pixels.append((red // count, green // count, blue // count))
    return Image(width, height, tuple(pixels))
