"""Profondeur MESUREE : cartes de profondeur externes et embarquees.

Tout le relief livre jusqu'ici est une CONVENTION. Elever selon la clarte est
le parti du camee, il marche souvent, et il se trompe exactement la ou la photo
le contredit — un sujet sombre sur fond clair sort en creux. La raison est
simple : une photo en couleurs ne contient aucune information de profondeur.

Sauf que ce n'est pas tout a fait vrai, et c'est ce module.

Un telephone en mode portrait MESURE la profondeur — deux objectifs, un capteur
de temps de vol, ou un reseau embarque — et certains ECRIVENT cette mesure dans
le fichier JPEG lui-meme, a cote de l'image.

CE QUE CE MODULE LIT, EXACTEMENT : les deux conteneurs de Google, GDepth (Lens
Blur) et Dynamic Depth, tous deux portes par du XMP. Rien d'autre.

Et il faut dire la portee reelle de cette phrase, parce que la version
precedente promettait « le fichier que vous avez deja sur votre telephone » :
sur les cinq photographies reelles soumises a cette chaine, **aucune ne porte
de XMP** — quatre viennent d'un appareil Apple (profil ICC « appl »), une est
ressortie d'une messagerie sans la moindre metadonnee. Le chemin embarque n'a
donc jamais eu l'occasion de servir une seule fois.

Ce n'est pas un defaut du code, qui fait ce qu'il annonce et que ses tests
verifient contre des conteneurs conformes ; c'est un defaut de PORTEE, et le
taire serait laisser croire qu'il suffit d'envoyer une photo de portrait. Le
chemin fiable, quel que soit l'appareil, reste `--carte-profondeur` avec une
carte produite dehors.

Et pour tous les autres cas, un estimateur monoculaire (MiDaS, Depth Anything,
Marigold) produit une carte de profondeur excellente, en dehors de ce depot,
avec un reseau de neurones qu'il serait absurde d'embarquer ici. Ce module
l'accepte en entree.

Ce qu'il NE fait pas : deviner. Une carte de profondeur absente reste absente,
et la chaine retombe sur la convention en le disant.
"""

from __future__ import annotations

import base64
import re
from typing import List, Optional, Tuple

from .imaging import Image, read_png, read_ppm, resample_median
from .jpeg import apply_orientation, exif_orientation, read_jpeg_eighth
from .mosaic import _cadrer, etage_field, smooth_relief

__all__ = [
    "read_depth_map",
    "heights_from_depth",
    "embedded_depth",
    "DepthMismatch",
    "NoEmbeddedDepth",
]


class DepthMismatch(ValueError):
    """La carte de profondeur ne correspond pas a la photo."""


class NoEmbeddedDepth(LookupError):
    """Ce JPEG ne porte aucune carte de profondeur."""


RATIO_TOLERANCE = 0.02
"""Ecart de proportions tolere entre la photo et sa carte de profondeur.

Deux pour cent, soit environ un pixel sur cinquante. Au-dela, ce n'est plus
un arrondi de redimensionnement : c'est une carte qui vient d'un autre
recadrage, ou d'une autre photo. Elle produirait un relief parfaitement
propre et parfaitement faux — le pire des resultats, parce que rien ne le
signale a l'oeil.
"""


def read_depth_map(data: bytes) -> Image:
    """Lit une carte de profondeur : PNG, PPM ou JPEG. Meme lecteurs.

    Une carte de profondeur est une image en niveaux de gris. On la lit comme
    n'importe quelle image et on n'en garde que la valeur ; qu'elle soit
    encodee en gris ou en RVB ne change rien.
    """
    if data[:8] == b"\x89PNG\r\n\x1a\x0a":
        return read_png(data)
    if data[:2] == b"P6":
        return read_ppm(data)
    if data[:2] == b"\xff\xd8":
        return read_jpeg_eighth(data)
    raise ValueError(
        "carte de profondeur : format non reconnu (PNG, PPM ou JPEG attendu)"
    )


def heights_from_depth(
    depth: Image,
    photo: Image,
    studs_x: int,
    studs_y: int,
    levels: int = 2,
    near_is_bright: bool = True,
    passes: int = 1,
    thresholds: str = "otsu",
    fit: str = "crop",
    offset=0.5,
) -> List[List[int]]:
    """Carte de profondeur -> etages de plates, cadree comme la photo.

    `photo` n'entre pas dans le calcul des hauteurs : elle sert a VERIFIER que
    la carte lui correspond, et a la cadrer exactement comme elle. C'est le
    seul controle qui separe un relief juste d'un relief faux mais propre.

    `near_is_bright` : convention d'encodage de la carte. Les estimateurs
    monoculaires (MiDaS, Depth Anything) sortent une DISPARITE — proche = clair
    — et c'est le defaut. Les cartes metriques sortent une DISTANCE — proche =
    sombre — et demandent `near_is_bright=False`. Se tromper retourne l'oeuvre
    en creux ; l'apercu le montre immediatement.
    """
    if photo.height == 0 or depth.height == 0:
        raise DepthMismatch("image de hauteur nulle")
    rapport_photo = photo.width / photo.height
    rapport_carte = depth.width / depth.height
    ecart = abs(rapport_photo - rapport_carte) / rapport_photo
    if ecart > RATIO_TOLERANCE:
        raise DepthMismatch(
            f"proportions incompatibles : photo {photo.width}x{photo.height} "
            f"({rapport_photo:.3f}) contre carte {depth.width}x{depth.height} "
            f"({rapport_carte:.3f}). Une carte issue d'un autre recadrage "
            "donnerait un relief propre et faux."
        )
    # Mediane et non moyenne : moyenner deux distances de part et d'autre d'un
    # bord invente une distance qui n'existe nulle part (voir resample_median).
    valeurs = resample_median(
        _cadrer(depth, studs_x, studs_y, fit, offset), studs_x, studs_y
    )
    return etage_field(
        valeurs, levels, invert=not near_is_bright,
        thresholds=thresholds, passes=passes,
    )


def _segments_app1(data: bytes):
    """Parcourt les segments APP1 d'un JPEG. Rien d'autre ne nous interesse."""
    if data[:2] != b"\xff\xd8":
        raise ValueError("ce n'est pas un JPEG")
    i = 2
    fin = len(data)
    while i + 4 <= fin:
        if data[i] != 0xFF:
            i += 1
            continue
        marqueur = data[i + 1]
        if marqueur in (0xD8, 0x01) or 0xD0 <= marqueur <= 0xD7:
            i += 2
            continue
        if marqueur == 0xDA:      # debut du balayage : les entetes sont finis
            return
        longueur = int.from_bytes(data[i + 2:i + 4], "big")
        if longueur < 2 or i + 2 + longueur > fin:
            return
        if marqueur == 0xE1:
            yield data[i + 4:i + 2 + longueur]
        i += 2 + longueur


_XMP = b"http://ns.adobe.com/xap/1.0/\x00"
_XMP_ETENDU = b"http://ns.adobe.com/xmp/extension/\x00"


def embedded_depth(data: bytes) -> Image:
    """Carte de profondeur EMBARQUEE dans un JPEG de mode portrait.

    Deux formats coexistent chez Google, et les deux se lisent ici :

    GDepth (Lens Blur, 2014). La carte est encodee en base64 dans l'attribut
    `GDepth:Data` du XMP. Quand elle depasse la taille d'un segment APP1
    (65 533 octets), elle deborde dans des segments XMP etendus qu'il faut
    reassembler dans l'ordre.

    Dynamic Depth (2019, norme publique). Le XMP ne porte qu'un ANNUAIRE :
    `Container:Directory` liste les images concatenees a la suite du fichier,
    chacune avec sa longueur. La carte de profondeur est celle dont le
    `Item:Semantic` vaut `Depth`, et elle se trouve en suivant les longueurs
    depuis la fin de l'image primaire.

    La carte rendue est REDRESSEE comme la photo : elle est ecrite dans le
    repere des pixels stockes et ne porte pas d'EXIF a elle, alors que la photo
    decodee, elle, a deja subi sa rotation.

    Leve `NoEmbeddedDepth` quand il n'y en a pas — ce qui est le cas de la
    plupart des photos. C'est une absence, pas une erreur.
    """
    paquets = list(_segments_app1(data))
    xmp = b""
    etendus = {}
    for paquet in paquets:
        if paquet.startswith(_XMP):
            xmp += paquet[len(_XMP):]
        elif paquet.startswith(_XMP_ETENDU):
            # 32 octets d'empreinte, 4 de taille totale, 4 de decalage.
            corps = paquet[len(_XMP_ETENDU):]
            if len(corps) < 40:
                continue
            decalage = int.from_bytes(corps[36:40], "big")
            etendus[decalage] = corps[40:]
    if etendus:
        xmp += b"".join(etendus[k] for k in sorted(etendus))
    if not xmp:
        raise NoEmbeddedDepth("aucun XMP dans ce JPEG")

    charge = _gdepth(xmp) or _dynamic_depth(xmp, data)
    if charge is None:
        raise NoEmbeddedDepth(
            "XMP present mais sans carte de profondeur (ni GDepth:Data, ni "
            "un element Container de semantique Depth)"
        )
    # La carte est ecrite dans le repere des PIXELS STOCKES de l'image
    # primaire, pas dans celui de l'image redressee, et elle ne porte pas
    # d'EXIF a elle. Sans cette ligne, la fonctionnalite echouait sur le cas
    # le plus courant qui soit : toute photo de telephone prise en portrait,
    # ou l'appareil stocke des pixels couches et note Orientation = 6. La
    # photo sortait debout, la carte restait couchee, et `DepthMismatch`
    # refusait — echec sur, mais echec.
    return apply_orientation(read_depth_map(charge), exif_orientation(data))


def _gdepth(xmp: bytes) -> Optional[bytes]:
    """Format GDepth : la carte est en base64 dans l'attribut `GDepth:Data`."""
    trouve = re.search(rb"GDepth:Data\s*=\s*\"([^\"]*)\"", xmp, re.S)
    if trouve is None:
        trouve = re.search(
            rb"<GDepth:Data>(.*?)</GDepth:Data>", xmp, re.S
        )
    if trouve is None:
        return None
    brut = re.sub(rb"\s+", b"", trouve.group(1))
    try:
        return base64.b64decode(brut, validate=True)
    except Exception as raison:      # base64 tronque : on le dit, on ne devine pas
        raise NoEmbeddedDepth(f"GDepth:Data illisible : {raison}") from None


def _dynamic_depth(xmp: bytes, data: bytes) -> Optional[bytes]:
    """Format Dynamic Depth : le XMP est un annuaire, les images suivent."""
    elements = _annuaire(xmp)
    if not elements:
        return None
    fin_primaire = _fin_de_l_image_primaire(data)
    if fin_primaire is None:
        return None
    curseur = fin_primaire
    for semantique, longueur in elements:
        if semantique.lower() == b"depth":
            return data[curseur:curseur + longueur]
        curseur += longueur
    return None


def _annuaire(xmp: bytes) -> List[Tuple[bytes, int]]:
    """Les elements du Container, dans l'ordre, hors image primaire.

    L'annuaire s'ecrit indifferemment en attributs ou en balises selon
    l'appareil ; les deux ecritures sont du RDF valide et les deux existent
    dans la nature.
    """
    elements = []
    for bloc in re.findall(rb"<Container:Item\b(.*?)/?>", xmp, re.S):
        semantique = re.search(rb"Item:Semantic\s*=\s*\"([^\"]*)\"", bloc)
        longueur = re.search(rb"Item:Length\s*=\s*\"(\d+)\"", bloc)
        if semantique is None:
            continue
        elements.append((semantique.group(1),
                         int(longueur.group(1)) if longueur else 0))
    if not elements:
        for bloc in re.findall(rb"<rdf:li\b(.*?)(?:/>|</rdf:li>)", xmp, re.S):
            semantique = re.search(rb"Item:Semantic\s*=\s*\"([^\"]*)\"", bloc)
            longueur = re.search(rb"Item:Length\s*=\s*\"(\d+)\"", bloc)
            if semantique is None:
                continue
            elements.append((semantique.group(1),
                             int(longueur.group(1)) if longueur else 0))
    # Le premier element est l'image primaire elle-meme, de longueur nulle.
    return [e for e in elements if e[0].lower() != b"primary"]


def _fin_de_l_image_primaire(data: bytes) -> Optional[int]:
    """Position juste apres le marqueur EOI de la premiere image du fichier."""
    i = 2
    fin = len(data)
    while i + 2 <= fin:
        if data[i] != 0xFF:
            i += 1
            continue
        marqueur = data[i + 1]
        if marqueur == 0xD9:
            return i + 2
        if marqueur in (0x01, 0xD8) or 0xD0 <= marqueur <= 0xD7:
            i += 2
            continue
        if marqueur == 0xDA:
            # Le balayage n'annonce pas sa taille : on cherche le prochain
            # marqueur qui n'est ni un bourrage (FF00) ni un redemarrage.
            j = i + 2
            while j + 1 < fin:
                if data[j] == 0xFF and data[j + 1] not in (0x00,) and not (
                        0xD0 <= data[j + 1] <= 0xD7):
                    break
                j += 1
            i = j
            continue
        if i + 4 > fin:
            return None
        i += 2 + int.from_bytes(data[i + 2:i + 4], "big")
    return None
