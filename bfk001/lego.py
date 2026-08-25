"""Systeme LEGO : metrologie et pieces de reference (HORS CONTRAT).

Le contrat BFK-001 est agnostique du systeme de briques : il ne connait que des
entiers, des connecteurs et des tolerances. Ce module fournit la couche
metrologique manquante — les dimensions reelles du systeme LEGO exprimees en
LDU — et les fixtures de pieces qui en decoulent.

Unite : 1 LDU = 0,4 mm (standard LDraw). Le choix de cette unite n'est pas
arbitraire : c'est le plus grand diviseur commun des cotes du systeme, ce qui
rend TOUTES les dimensions ci-dessous exactement entieres. C'est precisement ce
qui autorise la decision A.1 (arithmetique exacte dans Z^3) : le systeme LEGO
est nativement un reseau entier au pas de 0,4 mm.

    grandeur                 LDU    mm
    pas de tenon             20     8,0
    demi-tenon (jumper)      10     4,0
    hauteur de brique        24     9,6
    hauteur de plate          8     3,2
    diametre de tenon        12     4,8
    hauteur de tenon          4     1,6
    epaisseur de paroi        4     1,6

Deux approximations assumees, toutes deux du cote sur :

1. Un tenon cylindrique est modelise par son AABB, donc par un prisme carre de
   12 x 12 LDU. Le modele est plus GROS que la piece reelle : il peut refuser
   un assemblage legal en diagonale, jamais accepter une penetration reelle.
2. Le tube d'accroche interne n'est PAS modelise. L'accroche LEGO est un
   ajustement serre : tenon et tube se penetrent physiquement de quelques
   centiemes de millimetre, et c'est cette interference qui tient la
   construction. Une autorite geometrique exacte classerait cela PENETRATION.
   L'elasticite ne fait pas partie du scope BFK-001 (cf. P0_E) : la cavite est
   donc modelisee comme un vide franc, et l'accroche est portee par l'oracle
   mecanique, pas par la geometrie.
"""

from __future__ import annotations

from typing import List, Tuple

from .collision import CollisionGeometry
from .connectors import CTYPE_STUD_FEMALE, CTYPE_STUD_MALE, Connector, ConnectorTolerance
from .geometry import AABB, LDUVector, Orientation, Pose
from .search import PlacedPart

__all__ = [
    "LDU_MM",
    "STUD_PITCH_LDU",
    "HALF_STUD_LDU",
    "BRICK_HEIGHT_LDU",
    "PLATE_HEIGHT_LDU",
    "STUD_DIAMETER_LDU",
    "STUD_HEIGHT_LDU",
    "WALL_THICKNESS_LDU",
    "MIN_LATTICE_SEPARATION_LDU",
    "LEGO_TOLERANCE",
    "ldu_to_mm",
    "mm_to_ldu",
    "brick_geometry",
    "brick_connectors",
    "place_brick",
]

# --- Metrologie du systeme -------------------------------------------------

LDU_MM = 0.4

STUD_PITCH_LDU = 20
HALF_STUD_LDU = 10
BRICK_HEIGHT_LDU = 24
PLATE_HEIGHT_LDU = 8
STUD_DIAMETER_LDU = 12
STUD_HEIGHT_LDU = 4
WALL_THICKNESS_LDU = 4

MIN_LATTICE_SEPARATION_LDU = 1
"""Plus petite distance non nulle entre deux points distincts de Z^3.

Propriete decisive pour la tolerance : toutes les positions de connecteurs
etant entieres, deux connecteurs sont soit exactement coincidents, soit
distants d'au moins 1 LDU. Aucune valeur intermediaire n'existe.
"""


LEGO_TOLERANCE = ConnectorTolerance(
    max_position_error_ldu=0.5,
    max_angular_error_deg=0.0,
)
"""Tolerance de connexion retenue pour le systeme LEGO : 0,5 LDU = 0,2 mm.

Justification, en trois bornes :

  borne haute  strictement < 1 LDU. Dans Z^3, deux sites de connexion distincts
               sont distants d'au moins 1 LDU (0,4 mm) ; l'ecart utile est meme
               d'au moins 8 LDU (hauteur de plate) sur l'axe vertical et 10 LDU
               (demi-tenon) dans le plan. Une tolerance sous 1 LDU est donc
               EXACTEMENT equivalente a exiger la coincidence : aucun faux bond
               n'est structurellement possible. C'est verifie par test, pas
               suppose.

  borne basse  strictement > 0. Le jeu d'accroche reel d'une piece LEGO est de
               l'ordre du centieme de millimetre (0,01 mm ~ 0,025 LDU). Une
               tolerance nulle serait juste pour un reseau parfait mais fausse
               des que BFK-002 introduira de la geometrie mesuree ou non alignee
               sur le reseau. 0,5 LDU laisse un facteur 20 au-dessus du jeu
               physique.

  choix        0,5 LDU = la moitie du quantum du modele. Toute position est a
               moins d'un demi-LDU d'au plus un site du reseau : c'est le rayon
               d'accrochage naturel du systeme.

max_angular_error_deg = 0.0 : BFK-001 statue sur l'egalite exacte des normales
opposees et n'utilise JAMAIS ce champ (Section D.2). La valeur nulle dit la
verite du modele plutot que de suggerer une souplesse inexistante.

Ce n'est PAS une valeur par defaut : la decision A.2 interdit tout defaut sur
ConnectorTolerance. C'est une constante nommee que l'appelant passe
explicitement.
"""


def ldu_to_mm(ldu: int) -> float:
    """Conversion vers le monde physique. Sortie flottante : hors geometrie.

    Le calcul passe par la fraction exacte 2/5 et non par la constante LDU_MM :
    0,4 n'est pas representable en binaire, si bien que 24 * 0.4 vaut
    9.600000000000001 alors que 24 * 2 / 5 vaut 9.6. Un seul arrondi au lieu de
    deux. C'est aussi la demonstration la plus courte de la decision A.1 : des
    que l'on quitte Z, l'exactitude se perd des la premiere multiplication.
    """
    return ldu * 2 / 5


def mm_to_ldu(mm: float) -> float:
    """Conversion depuis le monde physique. A arrondir avant tout usage en Z^3."""
    return mm * 5 / 2


# --- Pieces de reference ---------------------------------------------------


def _stud_centers(studs_x: int, studs_y: int) -> Tuple[Tuple[int, int], ...]:
    if studs_x < 1 or studs_y < 1:
        raise ValueError("une piece compte au moins un tenon dans chaque direction")
    half = STUD_PITCH_LDU // 2
    return tuple(
        (half + i * STUD_PITCH_LDU, half + j * STUD_PITCH_LDU)
        for i in range(studs_x)
        for j in range(studs_y)
    )


def _stud_grid_coords(studs: int) -> Tuple[int, ...]:
    """Bornes de decoupe d'un axe : bord, [tenon], entre-tenons, ..., bord.

    Les cellules d'indice impair sont exactement les emprises de tenon.
    """
    half_stud = STUD_DIAMETER_LDU // 2
    half_pitch = STUD_PITCH_LDU // 2
    coords: List[int] = [0]
    for i in range(studs):
        center = half_pitch + i * STUD_PITCH_LDU
        coords.append(center - half_stud)
        coords.append(center + half_stud)
    coords.append(studs * STUD_PITCH_LDU)
    return tuple(coords)


def brick_geometry(
    studs_x: int,
    studs_y: int,
    body_height_ldu: int = BRICK_HEIGHT_LDU,
) -> CollisionGeometry:
    """Geometrie de collision d'une piece rectangulaire, repere LOCAL.

    exterior : corps + tenons, soit [0, 20*sx] x [0, 20*sy] x [0, h + 4].
    voids    : la cavite inferieure, plus la couche des tenons privee des
               tenons eux-memes — decoupee en AABB d'interieurs disjoints, de
               sorte que la matiere restante soit exactement le corps plein et
               les quatre prismes de tenon.

    Une plate s'obtient avec body_height_ldu=PLATE_HEIGHT_LDU.
    """
    if body_height_ldu <= WALL_THICKNESS_LDU:
        raise ValueError(
            f"hauteur {body_height_ldu} LDU incompatible avec une paroi de "
            f"{WALL_THICKNESS_LDU} LDU"
        )

    width_x = studs_x * STUD_PITCH_LDU
    width_y = studs_y * STUD_PITCH_LDU
    top_of_studs = body_height_ldu + STUD_HEIGHT_LDU

    exterior = AABB(LDUVector(0, 0, 0), LDUVector(width_x, width_y, top_of_studs))

    voids: List[AABB] = [
        AABB(
            LDUVector(WALL_THICKNESS_LDU, WALL_THICKNESS_LDU, 0),
            LDUVector(
                width_x - WALL_THICKNESS_LDU,
                width_y - WALL_THICKNESS_LDU,
                body_height_ldu - WALL_THICKNESS_LDU,
            ),
        )
    ]

    xs = _stud_grid_coords(studs_x)
    ys = _stud_grid_coords(studs_y)
    for i in range(len(xs) - 1):
        if xs[i] == xs[i + 1]:
            continue
        for j in range(len(ys) - 1):
            if ys[j] == ys[j + 1]:
                continue
            if i % 2 == 1 and j % 2 == 1:
                continue  # emprise d'un tenon : matiere, pas vide
            voids.append(
                AABB(
                    LDUVector(xs[i], ys[j], body_height_ldu),
                    LDUVector(xs[i + 1], ys[j + 1], top_of_studs),
                )
            )

    return CollisionGeometry(exterior=exterior, voids=tuple(voids))


def brick_connectors(
    studs_x: int,
    studs_y: int,
    body_height_ldu: int = BRICK_HEIGHT_LDU,
) -> Tuple[Connector, ...]:
    """Tenons males sur la face superieure, femelles sur la face inferieure.

    Le point de reference d'un tenon male est la BASE du tenon (face superieure
    du corps), pas son sommet : c'est ce qui le fait coincider exactement avec
    le point de reference femelle de la piece posee dessus.
    """
    centers = _stud_centers(studs_x, studs_y)
    males = tuple(
        Connector(
            CTYPE_STUD_MALE,
            LDUVector(cx, cy, body_height_ldu),
            LDUVector(0, 0, 1),
        )
        for cx, cy in centers
    )
    females = tuple(
        Connector(CTYPE_STUD_FEMALE, LDUVector(cx, cy, 0), LDUVector(0, 0, -1))
        for cx, cy in centers
    )
    return males + females


def place_brick(
    part_id: str,
    translation: Tuple[int, int, int] = (0, 0, 0),
    orientation: Orientation | None = None,
    studs_x: int = 2,
    studs_y: int = 2,
    body_height_ldu: int = BRICK_HEIGHT_LDU,
) -> PlacedPart:
    """Fixture : PlacedPart d'une piece rectangulaire, AABB monde pre-calcule."""
    from .geometry import transform_aabb

    pose: Pose = (
        LDUVector(*translation),
        Orientation.identity() if orientation is None else orientation,
    )
    geometry = brick_geometry(studs_x, studs_y, body_height_ldu)
    return PlacedPart(
        part_id=part_id,
        pose=pose,
        aabb=transform_aabb(geometry.exterior, pose),
        connectors=brick_connectors(studs_x, studs_y, body_height_ldu),
    )
