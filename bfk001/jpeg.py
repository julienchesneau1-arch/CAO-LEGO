"""Decodeur JPEG au huitieme (HORS CONTRAT, couche perception).

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

LE PROGRESSIF EST LU AUSSI, et pour la meme raison qui rend le reste simple.
Un JPEG progressif range ses coefficients en plusieurs balayages : d'abord les
DC de toute l'image, puis les AC par tranches, avec un raffinement bit a bit.
Comme seul le DC nous interesse, les balayages AC — la grande majorite du
fichier — se SAUTENT sans etre decodes. Il ne reste que le balayage DC initial
et ses raffinements, qui tiennent en trente lignes.

Ce n'est pas academique : une photo passee par une messagerie ressort en
progressif, sans EXIF, et c'est exactement ce qu'un utilisateur depose dans
l'application. Le refus explicite valait mieux que du n'importe quoi, mais il
refusait quand meme la photo.

Ce decodeur reste DELIBEREMENT partiel, et c'est une qualite :
  - sortie au huitieme de la resolution. Pour une mosaique c'est encore dix
    fois trop fin.
  - sans perte (SOF3), arithmetique (SOF9+) et hierarchique restent refuses,
    explicitement : ils ne sortent d'aucun appareil photo.
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
    """Table de Huffman canonique, a partir du compte par longueur.

    Le controle de coherence n'est pas decoratif : un fichier tronque ou
    corrompu annonce plus de symboles qu'il n'en porte, et la construction
    sortait alors par un `IndexError` sec, a huit appels de profondeur. Ce
    module refuse explicitement tout ce qu'il ne sait pas lire ; une table
    incoherente ne fait pas exception.
    """
    if len(counts) < 16 or sum(counts[:16]) > len(symbols):
        raise ValueError(
            "table de Huffman incoherente : le fichier annonce plus de "
            "symboles qu'il n'en porte. JPEG tronque ou corrompu."
        )
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
    raise ValueError("code de Huffman invalide : fichier corrompu")


def _prochain_marqueur(data: bytes, position: int) -> int:
    """Position du premier VRAI marqueur a partir de `position`.

    Un flux entropique contient des 0xFF qui n'en sont pas : 0xFF00 est
    l'echappement d'un 0xFF de donnees, et 0xFFD0-0xFFD7 sont les marqueurs de
    reprise, qui ponctuent le flux sans le terminer. Sans cette distinction, on
    ne peut pas passer d'un balayage au suivant — et le progressif en compte
    une dizaine.
    """
    while position < len(data) - 1:
        if data[position] == 0xFF:
            suivant = data[position + 1]
            if suivant not in (0x00, 0xFF) and not 0xD0 <= suivant <= 0xD7:
                return position
        position += 1
    return len(data)


def _balayage_baseline(reader, composantes, plans, huff_dc, huff_ac,
                       reprise: int, mcus_x: int, mcus_y: int) -> None:
    """Decode l'unique balayage d'un JPEG baseline.

    Les coefficients AC sont PARCOURUS sans etre conserves : il faut avancer
    dans le flux pour atteindre le DC du bloc suivant, mais eux ne servent a
    rien ici. Extrait de `read_jpeg_eighth` quand le progressif a impose d'y
    voir plusieurs balayages plutot qu'un seul.
    """
    predictions = {composante["id"]: 0 for composante in composantes}
    depuis_reprise = 0
    for mcu_y in range(mcus_y):
        for mcu_x in range(mcus_x):
            if reprise and depuis_reprise == reprise:
                reader.restart()
                predictions = {c["id"]: 0 for c in composantes}
                depuis_reprise = 0
            depuis_reprise += 1

            for composante in composantes:
                table_dc = huff_dc[composante["dc"]]
                table_ac = huff_ac[composante["ac"]]
                plan = plans[composante["id"]]
                for v in range(composante["v"]):
                    for h in range(composante["h"]):
                        longueur = _decode_symbol(reader, table_dc)
                        difference = _extend(reader.receive(longueur), longueur)
                        predictions[composante["id"]] += difference

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

                        plan[mcu_y * composante["v"] + v][
                            mcu_x * composante["h"] + h
                        ] = predictions[composante["id"]]


def _balayage_dc(reader, composantes, plans, huff_dc, reprise,
                 approximation_haute: int, approximation_basse: int,
                 mcus_x: int, mcus_y: int, blocs) -> None:
    """Decode UN balayage DC, initial ou de raffinement.

    C'est tout ce que le progressif demande ici. Le DC d'un bloc y arrive en
    deux temps : un balayage initial pose les bits de poids fort (decales de
    `Al`), des balayages de raffinement ajoutent un bit chacun. Les balayages
    AC, qui font l'essentiel du fichier, ne sont jamais lus.

    Un balayage peut etre entrelace — tous les plans, dans l'ordre des MCU — ou
    porter sur un seul plan, et l'ordre des blocs n'est alors plus le meme.
    Les deux se rencontrent dans des fichiers reels.
    """
    entrelace = len(composantes) > 1
    if entrelace:
        unites = [(y, x) for y in range(mcus_y) for x in range(mcus_x)]
    else:
        large, haut = blocs[composantes[0]["id"]]
        unites = [(y, x) for y in range(haut) for x in range(large)]

    predictions = {composante["id"]: 0 for composante in composantes}
    depuis_reprise = 0
    for unite_y, unite_x in unites:
        if reprise and depuis_reprise == reprise:
            reader.restart()
            predictions = {composante["id"]: 0 for composante in composantes}
            depuis_reprise = 0
        depuis_reprise += 1

        for composante in composantes:
            plan = plans[composante["id"]]
            hauteur_bloc = composante["v"] if entrelace else 1
            largeur_bloc = composante["h"] if entrelace else 1
            for v in range(hauteur_bloc):
                for h in range(largeur_bloc):
                    if entrelace:
                        ligne = unite_y * composante["v"] + v
                        colonne = unite_x * composante["h"] + h
                    else:
                        ligne, colonne = unite_y, unite_x
                    if approximation_haute:
                        # Raffinement : un bit, a la position Al.
                        if reader.read_bit():
                            plan[ligne][colonne] |= 1 << approximation_basse
                        continue
                    longueur = _decode_symbol(reader, huff_dc[composante["dc"]])
                    difference = _extend(reader.receive(longueur), longueur)
                    predictions[composante["id"]] += difference
                    plan[ligne][colonne] = (
                        predictions[composante["id"]] << approximation_basse
                    )


def read_jpeg_eighth(data: bytes) -> Image:
    """Decode un JPEG au huitieme de sa resolution, baseline ou progressif.

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
    progressif = False
    planes: Dict[int, List[List[int]]] = {}
    blocs: Dict[int, Tuple[int, int]] = {}
    mcus_x = mcus_y = 0
    h_max = v_max = 1
    balayages = 0

    def preparer_les_plans() -> None:
        """Alloue un echantillon par bloc 8x8, une fois le cadre connu.

        En baseline le cadre precede toujours l'unique balayage ; en progressif
        il precede une dizaine de balayages qui ecrivent tous dans les MEMES
        plans. L'allocation ne peut donc plus vivre dans la boucle de decodage.
        """
        nonlocal mcus_x, mcus_y, h_max, v_max
        h_max = max(composante["h"] for composante in components)
        v_max = max(composante["v"] for composante in components)
        mcus_x = -(-width // (8 * h_max))
        mcus_y = -(-height // (8 * v_max))
        for composante in components:
            planes[composante["id"]] = [
                [0] * (mcus_x * composante["h"])
                for _ in range(mcus_y * composante["v"])
            ]
            # Grille propre au plan : c'est elle qui ordonne les blocs d'un
            # balayage non entrelace, et elle est plus petite que la grille des
            # MCU des que la taille n'est pas un multiple exact.
            blocs[composante["id"]] = (
                -(-width * composante["h"] // (8 * h_max)),
                -(-height * composante["v"] // (8 * v_max)),
            )

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
        elif marker in (0xC0, 0xC1, 0xC2):  # baseline, etendu, progressif
            progressif = marker == 0xC2
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
            if not width or not height or not components:
                raise ValueError("JPEG invalide : cadre vide")
            preparer_les_plans()
        elif marker in (0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD,
                        0xCE, 0xCF):
            raise ValueError(
                "JPEG sans perte, arithmetique ou hierarchique non supporte : "
                "ce decodeur lit le baseline (SOF0/SOF1) et le progressif "
                "(SOF2). Reenregistrer la photo, ou la fournir en PNG."
            )
        elif marker == 0xDD:  # intervalle de reprise
            restart_interval = struct.unpack(">H", payload[:2])[0]
        elif marker == 0xDA:  # debut d'un balayage
            if not components:
                raise ValueError("JPEG invalide : balayage avant le cadre")
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
            spectre_debut = payload[1 + count * 2]
            approximation = payload[3 + count * 2]
            scan_start = position + 2 + length
            reader = _BitReader(data, scan_start)
            if not progressif:
                _balayage_baseline(
                    reader, scan_components, planes, huff_dc, huff_ac,
                    restart_interval, mcus_x, mcus_y)
                balayages += 1
            elif spectre_debut == 0:
                _balayage_dc(
                    reader, scan_components, planes, huff_dc,
                    restart_interval, approximation >> 4, approximation & 15,
                    mcus_x, mcus_y, blocs)
                balayages += 1
            # Un balayage AC ne porte aucun DC : on le SAUTE sans le decoder.
            # C'est ce qui rend le progressif bon marche ici — ces balayages
            # font l'essentiel du fichier.
            position = _prochain_marqueur(data, scan_start)
            continue
        position += 2 + length

    if not components or not balayages:
        raise ValueError("JPEG incomplet : aucun balayage exploitable")

    # Les plans portent le coefficient DC BRUT ; la moyenne du bloc s'en
    # deduit ici, une seule fois, quel que soit le nombre de balayages qui l'ont
    # ecrit. Le faire au fil du decodage empechait tout raffinement.
    for component in components:
        quantification = quant[component["q"]][_ZIGZAG_FIRST]
        plan = planes[component["id"]]
        for ligne in plan:
            for index, coefficient in enumerate(ligne):
                ligne[index] = min(
                    255, max(0, (coefficient * quantification) // 8 + 128))

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
