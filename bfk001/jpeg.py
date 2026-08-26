"""Decodeur JPEG baseline au huitieme (HORS CONTRAT, couche perception).

Une application LEGO Art qui ne lit pas un JPEG n'est pas une application : les
photos viennent d'appareils, et les appareils produisent du JPEG. Aucune
bibliotheque n'etant disponible, le format est decode ici, en Python pur.

L'IDEE QUI REND LA CHOSE RAISONNABLE : un JPEG code l'image par blocs de 8x8
pixels, et le tout premier coefficient de chaque bloc — le DC — n'est rien
d'autre que la moyenne du bloc. Or une mosaique de 48 tenons a partir d'une
photo de 4000 pixels ne demande que des moyennes. Il est donc inutile de
reconstruire les pixels : on decode les coefficients, on ne garde que le DC, et
on obtient directement une image au huitieme. Pas de transformee inverse, pas
de 12 millions de pixels a fabriquer pour en jeter 99,99 %.

Ce decodeur est donc DELIBEREMENT partiel, et c'est une qualite :
  - baseline sequentiel uniquement (SOF0). Le progressif (SOF2) leve une erreur
    explicite plutot que de rendre n'importe quoi.
  - sortie au huitieme de la resolution. Pour une mosaique c'est encore dix
    fois trop fin.
  - gere le sous-echantillonnage de la chrominance, les marqueurs de reprise et
    l'orientation EXIF, parce que toute photo de telephone en a besoin.
"""

from __future__ import annotations

import struct
from typing import Dict, List, Tuple

from .imaging import Image

__all__ = ["read_jpeg_eighth", "exif_orientation", "apply_orientation"]

_ZIGZAG_FIRST = 0  # le DC est toujours le premier coefficient


class _BitReader:
    """Lecteur de bits MSB d'abord, avec desechappement des octets 0xFF00."""

    def __init__(self, data: bytes, position: int) -> None:
        self._data = data
        self._position = position
        self._bits = 0
        self._count = 0

    def read_bit(self) -> int:
        if self._count == 0:
            if self._position >= len(self._data):
                return 0
            octet = self._data[self._position]
            self._position += 1
            if octet == 0xFF:
                suivant = (
                    self._data[self._position]
                    if self._position < len(self._data)
                    else 0
                )
                if suivant == 0x00:
                    self._position += 1
                elif 0xD0 <= suivant <= 0xD7:
                    # Marqueur de reprise : traite par restart(), pas ici.
                    self._position += 1
                    return self.read_bit()
                else:
                    return 0
            self._bits = octet
            self._count = 8
        self._count -= 1
        return (self._bits >> self._count) & 1

    def receive(self, length: int) -> int:
        value = 0
        for _ in range(length):
            value = (value << 1) | self.read_bit()
        return value

    def restart(self) -> None:
        """Se recale sur l'octet suivant le prochain marqueur de reprise."""
        self._count = 0
        data = self._data
        while self._position < len(data) - 1:
            if data[self._position] == 0xFF and 0xD0 <= data[self._position + 1] <= 0xD7:
                self._position += 2
                return
            self._position += 1


def _extend(value: int, length: int) -> int:
    """Conversion de l'amplitude JPEG en entier signe."""
    if length == 0:
        return 0
    return value if value >= (1 << (length - 1)) else value - (1 << length) + 1


def _build_huffman(counts: bytes, symbols: bytes) -> Dict[Tuple[int, int], int]:
    table: Dict[Tuple[int, int], int] = {}
    code = 0
    index = 0
    for length in range(1, 17):
        for _ in range(counts[length - 1]):
            table[(length, code)] = symbols[index]
            code += 1
            index += 1
        code <<= 1
    return table


def _decode_symbol(reader: _BitReader, table: Dict[Tuple[int, int], int]) -> int:
    code = 0
    for length in range(1, 17):
        code = (code << 1) | reader.read_bit()
        if (length, code) in table:
            return table[(length, code)]
    raise ValueError("code de Huffman invalide : fichier corrompu ou non baseline")


def read_jpeg_eighth(data: bytes) -> Image:
    """Decode un JPEG baseline au huitieme de sa resolution.

    Retourne une Image RVB de ceil(largeur/8) x ceil(hauteur/8) pixels, chacun
    valant la moyenne d'un bloc 8x8 de l'original. L'orientation EXIF est
    appliquee.
    """
    if data[:2] != b"\xff\xd8":
        raise ValueError("ce n'est pas un fichier JPEG")

    quant: Dict[int, List[int]] = {}
    huff_dc: Dict[int, Dict[Tuple[int, int], int]] = {}
    huff_ac: Dict[int, Dict[Tuple[int, int], int]] = {}
    components: List[dict] = []
    width = height = 0
    restart_interval = 0
    position = 2
    scan_start = None
    scan_components: List[dict] = []

    while position < len(data) - 1:
        if data[position] != 0xFF:
            position += 1
            continue
        marker = data[position + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            position += 2
            continue
        if marker == 0xD9:
            break
        length = struct.unpack(">H", data[position + 2 : position + 4])[0]
        payload = data[position + 4 : position + 2 + length]

        if marker == 0xDB:  # tables de quantification
            index = 0
            while index < len(payload):
                precision, identifier = payload[index] >> 4, payload[index] & 15
                index += 1
                if precision:
                    quant[identifier] = list(
                        struct.unpack(">64H", payload[index : index + 128])
                    )
                    index += 128
                else:
                    quant[identifier] = list(payload[index : index + 64])
                    index += 64
        elif marker == 0xC4:  # tables de Huffman
            index = 0
            while index < len(payload):
                classe, identifier = payload[index] >> 4, payload[index] & 15
                counts = payload[index + 1 : index + 17]
                total = sum(counts)
                symbols = payload[index + 17 : index + 17 + total]
                table = _build_huffman(counts, symbols)
                (huff_ac if classe else huff_dc)[identifier] = table
                index += 17 + total
        elif marker == 0xC0 or marker == 0xC1:  # baseline
            height, width = struct.unpack(">HH", payload[1:5])
            count = payload[5]
            components = []
            for c in range(count):
                identifier = payload[6 + c * 3]
                sampling = payload[7 + c * 3]
                components.append(
                    {
                        "id": identifier,
                        "h": sampling >> 4,
                        "v": sampling & 15,
                        "q": payload[8 + c * 3],
                    }
                )
        elif marker in (0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB):
            raise ValueError(
                "JPEG progressif ou etendu non supporte : ce decodeur ne lit que "
                "le baseline sequentiel (SOF0/SOF1). Reenregistrer la photo en "
                "baseline, ou en PNG."
            )
        elif marker == 0xDD:  # intervalle de reprise
            restart_interval = struct.unpack(">H", payload[:2])[0]
        elif marker == 0xDA:  # debut du balayage
            count = payload[0]
            scan_components = []
            for c in range(count):
                identifier = payload[1 + c * 2]
                tables = payload[2 + c * 2]
                for component in components:
                    if component["id"] == identifier:
                        component["dc"] = tables >> 4
                        component["ac"] = tables & 15
                        scan_components.append(component)
            scan_start = position + 2 + length
            break
        position += 2 + length

    if not components or scan_start is None:
        raise ValueError("JPEG incomplet : aucun balayage exploitable")

    h_max = max(component["h"] for component in components)
    v_max = max(component["v"] for component in components)
    mcus_x = -(-width // (8 * h_max))
    mcus_y = -(-height // (8 * v_max))

    # Un plan par composante, un echantillon par bloc 8x8 : c'est l'image au
    # huitieme, obtenue sans aucune transformee inverse.
    planes = {
        component["id"]: [
            [0] * (mcus_x * component["h"]) for _ in range(mcus_y * component["v"])
        ]
        for component in components
    }

    reader = _BitReader(data, scan_start)
    predictions = {component["id"]: 0 for component in components}
    depuis_reprise = 0

    for mcu_y in range(mcus_y):
        for mcu_x in range(mcus_x):
            if restart_interval and depuis_reprise == restart_interval:
                reader.restart()
                predictions = {component["id"]: 0 for component in components}
                depuis_reprise = 0
            depuis_reprise += 1

            for component in scan_components:
                table_dc = huff_dc[component["dc"]]
                table_ac = huff_ac[component["ac"]]
                quantification = quant[component["q"]]
                plane = planes[component["id"]]
                for v in range(component["v"]):
                    for h in range(component["h"]):
                        longueur = _decode_symbol(reader, table_dc)
                        difference = _extend(reader.receive(longueur), longueur)
                        predictions[component["id"]] += difference

                        # Les coefficients AC doivent etre parcourus pour
                        # avancer dans le flux, mais ils ne sont pas conserves :
                        # seul le DC nous interesse.
                        k = 1
                        while k < 64:
                            symbole = _decode_symbol(reader, table_ac)
                            if symbole == 0:
                                break
                            course, taille = symbole >> 4, symbole & 15
                            if taille == 0:
                                if course != 15:
                                    break
                                k += 16
                                continue
                            k += course + 1
                            reader.receive(taille)

                        moyenne = (
                            predictions[component["id"]]
                            * quantification[_ZIGZAG_FIRST]
                        ) // 8 + 128
                        ligne = mcu_y * component["v"] + v
                        colonne = mcu_x * component["h"] + h
                        plane[ligne][colonne] = min(255, max(0, moyenne))

    out_width = -(-width // 8)
    out_height = -(-height // 8)
    sortie = bytearray(out_width * out_height * 3)
    luminance = planes[components[0]["id"]]
    chroma = [planes[component["id"]] for component in components[1:]]
    facteurs = [(component["h"], component["v"]) for component in components[1:]]

    for y in range(out_height):
        for x in range(out_width):
            Y = luminance[min(y, len(luminance) - 1)][
                min(x, len(luminance[0]) - 1)
            ]
            if len(chroma) == 2:
                cb_plane, cr_plane = chroma
                (hb, vb), (hr, vr) = facteurs
                cb = cb_plane[min(y * vb // v_max, len(cb_plane) - 1)][
                    min(x * hb // h_max, len(cb_plane[0]) - 1)
                ] - 128
                cr = cr_plane[min(y * vr // v_max, len(cr_plane) - 1)][
                    min(x * hr // h_max, len(cr_plane[0]) - 1)
                ] - 128
            else:
                cb = cr = 0
            index = (y * out_width + x) * 3
            sortie[index] = min(255, max(0, int(Y + 1.402 * cr)))
            sortie[index + 1] = min(
                255, max(0, int(Y - 0.344136 * cb - 0.714136 * cr))
            )
            sortie[index + 2] = min(255, max(0, int(Y + 1.772 * cb)))

    return apply_orientation(
        Image(out_width, out_height, bytes(sortie)), exif_orientation(data)
    )


def exif_orientation(data: bytes) -> int:
    """Valeur du champ EXIF Orientation, ou 1 si absent.

    Sans lui, une photo prise en portrait sort couchee. Aucun utilisateur ne
    pardonne ca, et aucun appareil n'ecrit les pixels dans le bon sens.
    """
    position = 2
    while position < len(data) - 1:
        if data[position] != 0xFF:
            position += 1
            continue
        marker = data[position + 1]
        if marker == 0xDA or marker == 0xD9:
            return 1
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            position += 2
            continue
        length = struct.unpack(">H", data[position + 2 : position + 4])[0]
        if marker == 0xE1 and data[position + 4 : position + 10] == b"Exif\x00\x00":
            tiff = position + 10
            ordre = "<" if data[tiff : tiff + 2] == b"II" else ">"
            offset = struct.unpack(ordre + "I", data[tiff + 4 : tiff + 8])[0]
            entrees = struct.unpack(
                ordre + "H", data[tiff + offset : tiff + offset + 2]
            )[0]
            for i in range(entrees):
                debut = tiff + offset + 2 + i * 12
                tag = struct.unpack(ordre + "H", data[debut : debut + 2])[0]
                if tag == 0x0112:
                    return struct.unpack(
                        ordre + "H", data[debut + 8 : debut + 10]
                    )[0]
            return 1
        position += 2 + length
    return 1


def apply_orientation(image: Image, orientation: int) -> Image:
    """Redresse l'image selon la valeur EXIF (1 a 8)."""
    if orientation in (0, 1):
        return image

    largeur, hauteur = image.width, image.height
    transpose = orientation in (5, 6, 7, 8)
    sortie_l, sortie_h = (hauteur, largeur) if transpose else (largeur, hauteur)
    donnees = bytearray(largeur * hauteur * 3)
    source = image.data

    for y in range(hauteur):
        for x in range(largeur):
            if orientation == 2:
                nx, ny = largeur - 1 - x, y
            elif orientation == 3:
                nx, ny = largeur - 1 - x, hauteur - 1 - y
            elif orientation == 4:
                nx, ny = x, hauteur - 1 - y
            elif orientation == 5:
                nx, ny = y, x
            elif orientation == 6:
                nx, ny = hauteur - 1 - y, x
            elif orientation == 7:
                nx, ny = hauteur - 1 - y, largeur - 1 - x
            elif orientation == 8:
                nx, ny = y, largeur - 1 - x
            else:
                nx, ny = x, y
            source_index = (y * largeur + x) * 3
            cible = (ny * sortie_l + nx) * 3
            donnees[cible : cible + 3] = source[source_index : source_index + 3]

    return Image(sortie_l, sortie_h, bytes(donnees))
