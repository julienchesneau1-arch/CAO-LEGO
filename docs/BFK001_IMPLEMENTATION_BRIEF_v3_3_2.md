# BFK-001 IMPLEMENTATION BRIEF v3.3.2
# Document de travail pour Claude Code — BrickForge Kernel
# Statut : PRÊT POUR IMPLÉMENTATION
# Version : 3.3.2
# Date : 2026-08-25
# Langage : Français (contrat) / Python (implémentation)
# Principe directeur : séparation stricte des autorités — géométrie → collision → mécanique

---

## CONSIGNES GÉNÉRALES POUR CLAUDE CODE (LIRE EN PREMIER)

### Règles absolues
1. **Ne jamais modifier l'architecture** sans signaler l'écart au contrat.
2. **Distinction position / direction** :
   - `transform_local_to_world()` → POSITION uniquement (rotation + translation).
   - `transform_local_direction_to_world()` → DIRECTION / NORMALE uniquement (rotation seule).
   - **INTERDIT** d'utiliser `transform_local_to_world()` pour une normale.
3. **Arithmétique exacte ℤ³** : aucun `float` dans la géométrie fondamentale. Seule exception : la comparaison `distance_euclidienne <= tolerance.max_position_error_ldu` dans l'oracle.
4. **Immutabilité profonde** : `Tuple` partout, jamais `List` dans `ConstructionGraph` ni `ConstructionState`.
5. **PhysicalBond opaque** : aucun constructeur public. Seul `evaluate_connector_pair()` peut créer des `PhysicalBond`.
6. **Zero logique cachée** dans les stubs : implémenter exactement le contrat, pas "améliorer".
7. **Tests adversariaux d'abord** : implémenter T1a–T14 AVANT toute logique métier.

### Ordre de travail recommandé
| Phase | Contenu | Validation |
|-------|---------|------------|
| 1 | Tests adversariaux T1a–T14 (fichier `test_bfk001_adversarial.py`) | Doivent échouer initialement (pas d'implémentation) |
| 2 | Primitives géométriques (B, C) : `LDUVector`, `AABB`, `Orientation`, `transform_*` | T11 |
| 3 | Collision (F) : `solid_overlap`, `collision_status`, `collide` | T5, T6, T12, T14 |
| 4 | Oracle mécanique (E) : `evaluate_connector_pair` | T1a, T1b, T3, T7 |
| 5 | SearchApproximation (H) : `ReferenceSearchApproximation`, `_compatible` | T2, T8 |
| 6 | Graphe + État (I, J) : `ConstructionGraph`, `ConstructionState` | T10, T13 |
| 7 | Fondation (L) : `check_foundation` | T4 |
| 8 | Intégration et validation H1–H6 | T9 (futur index rapide) |

---

# PARTIE 1 — CONTRAT BFK-001 v3.3.2

## Section A — Décisions figées (non négociables)

| # | Décision | Valeur / Règle | Justification |
|---|----------|----------------|---------------|
| A.1 | Arithmétique | Exacte sur les entiers (ℤ). Aucun epsilon, aucun flottant dans la géométrie fondamentale. | `LDUVector` et `Orientation` sont entiers. Transformations = compositions de translations et rotations à 90°. |
| A.2 | Tolérance connecteur | `ConnectorTolerance` obligatoire sans valeur par défaut. `max_angular_error_deg` présent mais **non utilisé** en BFK-001. | Séparation perception/mécanique. Angle réservé à BFK-002. |
| A.3 | Orientation | Matrice 3×3 entière. Coefficients ∈ {−1,0,1}, orthogonalité, déterminant +1. | Représentation explicite, composition exacte en ℤ, transformation directe. |
| A.4 | SearchApproximation de référence | O(n²), exhaustive, triviale. | Oracle de complétude physique. Tout index rapide futur validé contre elle. |
| A.5 | ConstructionState | Réellement immuable. Tous membres = value objects ou snapshots de lecture. Aucune méthode de mutation. | Snapshots d'audit fiables, backtracking pur. |
| A.6 | solid_overlap | `Optional[Tuple[AABB, ...]]` représentant une partition exacte. | Autorité géométrique exacte. Aucun faux positif de pénétration. |
| A.7 | H1_SEARCH_COVERAGE | P ⊆ C pour tout état de construction et toute implémentation conforme. | Un bond valide ne peut jamais être omis. |
| A.8 | PhysicalBond | Type opaque. Autorité de création exclusive de `evaluate_connector_pair`. | Tout bond retourné par l'oracle est valide par définition. H3 vérifie l'absence de fabrication externe. |
| A.9 | P0-B/C/D/E | Hors scope BFK-001. | BFK-002 ou ultérieur. |

---

## Section B — Primitives géométriques et arithmétique exacte

### B.1 LDUVector

```python
@dataclass(frozen=True)
class LDUVector:
    x: int
    y: int
    z: int
```
Invariant : élément de ℤ³. Aucune opération ne produit de coordonnée non entière.

### B.2 AABB

```python
@dataclass(frozen=True)
class AABB:
    min: LDUVector
    max: LDUVector
```
Précondition : `min.x <= max.x`, `min.y <= max.y`, `min.z <= max.z`.

### B.3 Relations géométriques entre AABB

```python
class GeometricRelation(Enum):
    DISJOINT = auto()
    TOUCHING = auto()
    OVERLAPPING = auto()

def geometric_relation(a: AABB, b: AABB) -> GeometricRelation: ...
```
Arithmétique exacte sur les entiers.

### B.4 Intersection AABB

```python
def intersection_aabb(a: AABB, b: AABB) -> Optional[AABB]: ...
```
Règle : retourne un `AABB` uniquement si le volume d'intersection est strictement positif. Contact nul → `None`.

### B.5 Transformation d'AABB

```python
def transform_aabb(aabb: AABB, pose: Pose) -> AABB: ...
```
Sémantique : transforme les 8 coins par la pose, puis retourne l'AABB englobant exact (`min`/`max` composante par composante). Garanti dans ℤ³.

---

## Section C — Orientation

### C.1 Représentation

```python
@dataclass(frozen=True)
class Orientation:
    m00: int; m01: int; m02: int
    m10: int; m11: int; m12: int
    m20: int; m21: int; m22: int
```
Contraintes : coefficients ∈ {−1,0,1}, Mᵀ×M = I, det(M) = +1.

### C.2 Pose

```python
Pose = Tuple[LDUVector, Orientation]
```

### C.3 Transformation d'une POSITION local → monde

```python
def transform_local_to_world(local: LDUVector, pose: Pose) -> LDUVector:
    # world = orientation @ local + translation
    # Résultat garanti dans ℤ³.
    # USAGE : positions de points, positions de connecteurs.
```

### C.4 Transformation d'une DIRECTION / NORMALE local → monde

```python
def transform_local_direction_to_world(
    local_direction: LDUVector,
    orientation: Orientation,
) -> LDUVector:
    # world_direction = orientation @ local_direction
    # Aucune translation n'est appliquée.
    # Résultat garanti dans ℤ³.
    # USAGE : normales, vecteurs directeurs.
    # INTERDIT d'utiliser transform_local_to_world() pour une normale.
```

---

## Section D — Connecteurs et tolérance

### D.1 Connector

```python
@dataclass(frozen=True)
class Connector:
    ctype: str                    # "stud_male" | "stud_female" | extensible
    local_pos: LDUVector          # Position dans le repère local
    local_normal: LDUVector       # Direction de connexion dans le repère local
```
Contrainte : `local_normal` a exactement une composante non-nulle parmi les 6 directions axiales unitaires.

### D.2 ConnectorTolerance

```python
@dataclass(frozen=True)
class ConnectorTolerance:
    max_position_error_ldu: float   # OBLIGATOIRE, pas de défaut
    max_angular_error_deg: float    # OBLIGATOIRE, mais IGNORE en BFK-001
```
Règle angulaire BFK-001 : `max_angular_error_deg` est contractuellement présent mais **explicitement NON utilisé** par l'oracle. L'oracle vérifie l'égalité exacte des normales opposées.

---

## Section E — Oracle mécanique indépendant

### E.1 PhysicalBond — Type opaque

```python
@dataclass(frozen=True)
class PhysicalBond:
    pass  # Type opaque. Autorité de création EXCLUSIVE de evaluate_connector_pair.
```
Règle d'intégrité (H3) : aucun `PhysicalBond` dans `ConstructionGraph` ne peut provenir d'une construction externe à l'oracle.

### E.2 Signature de l'oracle

```python
def evaluate_connector_pair(
    connector_a: Connector,
    pose_a: Pose,
    connector_b: Connector,
    pose_b: Pose,
    tolerance: ConnectorTolerance,
) -> Optional[PhysicalBond]:
    """
    Critères BFK-001 (non exhaustif, l'oracle conserve l'autorité ultime) :
    • Compatibilité ctype : _compatible(ctype_a, ctype_b) doit être vrai.
      BFK-001 définit : "stud_male" ↔ "stud_female" uniquement.
    • Normales opposées EXACTES :
      transform_local_direction_to_world(connector_a.local_normal, pose_a[1])
      ==
      -transform_local_direction_to_world(connector_b.local_normal, pose_b[1])
    • max_angular_error_deg est IGNORE (Section D.2).
    • Distance euclidienne entre positions monde :
      pos_a = transform_local_to_world(connector_a.local_pos, pose_a)
      pos_b = transform_local_to_world(connector_b.local_pos, pose_b)
      dx, dy, dz = pos_a.x - pos_b.x, pos_a.y - pos_b.y, pos_a.z - pos_b.z
      distance = sqrt(dx² + dy² + dz²)
      Bond valide ssi distance <= tolerance.max_position_error_ldu
      Note : dx²+dy²+dz² est entier. La comparaison avec le float est la SEULE
      opération flottante autorisée dans BFK-001.

    Contraintes contractuelles :
    • Ne connaît PAS SearchApproximation, SpatialCandidateIndex,
      connector_registry, voxel, solver, ConstructionState, graphe.
    • Fonction pure.
    """
```

---

## Section F — Collision et géométrie solide

### F.1 CollisionStatus

```python
class CollisionStatus(Enum):
    CLEAR = auto()
    CONTACT = auto()
    PENETRATION = auto()
```

### F.2 CollisionGeometry

```python
@dataclass(frozen=True)
class CollisionGeometry:
    exterior: AABB
    voids: Tuple[AABB, ...]
```
Règle de repère : `exterior` et `voids` sont exprimés dans le repère **LOCAL** de la pièce. `collide()` les transforme en monde avant comparaison.

### F.3 solid_overlap — Autorité géométrique exacte

```python
def solid_overlap(
    intersection: AABB,
    solid_a: AABB,
    voids_a: Tuple[AABB, ...],
    solid_b: AABB,
    voids_b: Tuple[AABB, ...],
) -> Optional[Tuple[AABB, ...]]: ...
```
Définition formelle de la partition retournée :
- `P = (r₁, ..., rₙ)` avec chaque `rᵢ` un `AABB`.
- `Union(P) = R` exactement (pas de sur-approximation, pas de sous-approximation).
- `∀ i≠j : interior(rᵢ) ∩ interior(rⱼ) = ∅` (intérieurs deux à deux disjoints).
- Les `rᵢ` peuvent se toucher (faces, arêtes, sommets communs).
- Toute décomposition exacte valide est acceptable. Aucune canonicalisation imposée.

### F.4 Dérivation du CollisionStatus

```python
def collision_status(
    relation: GeometricRelation,
    overlap: Optional[Tuple[AABB, ...]],
) -> CollisionStatus: ...
```
Règles :
- `DISJOINT` → `CLEAR` (`overlap` doit être `None`)
- `TOUCHING` → `CONTACT` (`overlap` doit être `None`)
- `OVERLAPPING` + `overlap is None` → `CONTACT` (engagement dans voids)
- `OVERLAPPING` + `overlap is not None` → `PENETRATION` (matière solide en conflit)

### F.5 collide — Autorité collisionnelle complète

```python
def collide(
    geometry_a: CollisionGeometry,
    pose_a: Pose,
    geometry_b: CollisionGeometry,
    pose_b: Pose,
) -> CollisionStatus: ...
```
Algorithme contractuel :
1. Transforme `exterior` et **tous les `voids`** en coordonnées monde :
   ```
   aabb_a = transform_aabb(geometry_a.exterior, pose_a)
   voids_a_m = tuple(transform_aabb(v, pose_a) for v in geometry_a.voids)
   aabb_b = transform_aabb(geometry_b.exterior, pose_b)
   voids_b_m = tuple(transform_aabb(v, pose_b) for v in geometry_b.voids)
   ```
2. `relation = geometric_relation(aabb_a, aabb_b)`
3. `DISJOINT` → `CLEAR`
4. `TOUCHING` → `CONTACT`
5. `OVERLAPPING` → `intersection_aabb()` → `solid_overlap()` → `collision_status()`

Contraintes : ne connaît pas `Connector`, `PhysicalBond`, `SearchApproximation`, `SpatialCandidateIndex`, `ConstructionState`, `evaluate_connector_pair`.

---

## Section G — SpatialCandidateIndex (Protocol)

```python
class SpatialCandidateIndex(Protocol):
    def query(self, region: AABB) -> Iterable[str]: ...
    def insert(self, part_id: str, aabb: AABB) -> None: ...
    def remove(self, part_id: str) -> None: ...
```
Frontière d'autorité : peut dire "regarde ici". Ne peut **jamais** dire "connectés" ou "pas connectés".
Note sur H1 : l'index est un accélérateur. L'obligation H1 incombe à `SearchApproximation`.

---

## Section H — SearchApproximation (Protocol)

### H.1 PlacedPart

```python
@dataclass(frozen=True)
class PlacedPart:
    part_id: str
    pose: Pose
    aabb: AABB                    # AABB monde pré-calculé
    connectors: Tuple[Connector, ...]
```

### H.2 Protocole SearchApproximation

```python
class SearchApproximation(Protocol):
    def find_candidate_pairs(
        self,
        index: SpatialCandidateIndex,
        placed_parts: Mapping[str, PlacedPart],
        tolerance: ConnectorTolerance,
    ) -> Iterable[Tuple[str, str, Connector, Connector]]: ...
```
Garantie H1 : pour tout état de construction et toute paire de connecteurs, si `evaluate_connector_pair()` retourne un `PhysicalBond`, alors cette paire doit appartenir aux candidats produits.

### H.3 Implémentation de référence O(n²)

```python
class ReferenceSearchApproximation:
    def find_candidate_pairs(self, index, placed_parts, tolerance):
        # Ignore l'index
        for id_a, part_a in placed_parts.items():
            for id_b, part_b in placed_parts.items():
                if id_a >= id_b:
                    continue
                for conn_a in part_a.connectors:
                    for conn_b in part_b.connectors:
                        if not _compatible(conn_a.ctype, conn_b.ctype):
                            continue
                        yield (id_a, id_b, conn_a, conn_b)

def _compatible(ctype_a: str, ctype_b: str) -> bool:
    return (ctype_a == "stud_male" and ctype_b == "stud_female") or \
           (ctype_a == "stud_female" and ctype_b == "stud_male")
```

### H.4 Validation d'un index rapide futur

Règle : `FastSearchApproximation` est conforme ssi P ⊆ C_fast pour tout état.
Non-règle : C_ref ⊆ C_fast **n'est PAS exigé**.

---

## Section I — Graphes

### I.1 ConstructionGraph

```python
@dataclass(frozen=True)
class ConstructionGraph:
    parts: Tuple[Tuple[str, AABB, Tuple[Connector, ...]], ...]
    edges: Tuple[Tuple[str, str, Tuple[PhysicalBond, ...]], ...]
```
`Tuple` uniquement — jamais `List`. `edges` = tous les bonds, pas un arbre couvrant.

### I.2 InstructionGraph

```python
@dataclass(frozen=True)
class InstructionGraph:
    steps: Tuple[BuildStep, ...]
    def validate_dag(self) -> bool: ...
```

---

## Section J — ConstructionState

### J.1 SpatialSnapshot (Protocol query-only)

```python
class SpatialSnapshot(Protocol):
    def query(self, region: AABB) -> Iterable[str]: ...
```
Aucune méthode `insert`/`remove`. Lecture seule.

### J.2 ConstructionState — Pur conteneur immuable

```python
@dataclass(frozen=True)
class ConstructionState:
    graph: ConstructionGraph
    spatial_snapshot: SpatialSnapshot
```
Aucune méthode `add_part()` ou de mutation. La construction d'un nouvel état est effectuée par une **fonction d'orchestration extérieure** (hors contrat BFK-001).

---

## Section K — Validation (HARD invariants)

| Invariant | Définition formelle | Niveau |
|-----------|---------------------|--------|
| H1_SEARCH_COVERAGE | P ⊆ C : tout bond valide doit être produit par le pipeline de recherche. | Pipeline |
| H2_COLLISION | `penetration_count == 0` — aucun `PENETRATION`. | Géométrie |
| H3_AUTHORITY_INTEGRITY | Aucun `PhysicalBond` externe à l'oracle dans le graphe. | Mécanique |
| H4_FLOATING | Toute pièce non fondée possède une chaîne de bonds vers une fondation. | Graphe |
| H5_DISCONNECTED | Le graphe de construction est connexe. | Graphe |
| H6_FOUNDATION | Toute pièce au plan de fondation satisfait `check_foundation`. | Fondation |

---

## Section L — Support et fondation

```python
def check_foundation(
    part_exterior: AABB,
    part_connectors: Tuple[Connector, ...],
    part_pose: Pose,
    foundation_plane_z: int = 0,
) -> FoundationCheck: ...
```
Règles (arithmétique exacte, entiers) :
- `min.z < foundation_plane_z` → **INVALIDE** (pénètre le sol)
- `min.z > foundation_plane_z` → **NON fondée** (doit avoir un bond)
- `min.z == foundation_plane_z` → **Fondée** ssi la pièce possède au moins un `Connector` de `ctype == "stud_female"` dont la normale transformée est `(0, 0, -1)` :
  ```
  transform_local_direction_to_world(connector.local_normal, part_pose[1]) == (0, 0, -1)
  ```
  Sinon → **NON fondée**.

Aucun epsilon. `min.z` est contractuellement un entier.

---

## Section M — Tests adversariaux requis

Règle absolue : aucun test ne doit reconstruire l'état interne qu'il prétend auditer.

| ID | Nom | Principe | Fixture | Assertion |
|----|-----|----------|---------|-----------|
| T1a | `test_oracle_signature_isolation` | L'oracle ne reçoit que des primitives | Signature `evaluate_connector_pair` | Aucun paramètre ni retour ne dépend de `SearchApproximation`, `SpatialCandidateIndex`, `ConstructionState`, solver, voxel |
| T1b | `test_oracle_dependency_isolation` | L'oracle n'importe pas les modules interdits | Module de l'oracle | Aucun import interdit |
| T2 | `test_search_coverage_completeness` | H1 : tout bond est un candidat | Deux pièces avec bond valide connu | La paire est dans `ReferenceSearchApproximation` |
| T3 | `test_search_no_false_mechanical_claim` | Frontière G/H | Index qui retourne tout | L'oracle rejette les paires non valides |
| T4 | `test_foundation_exact_integer` | Section L | `min.z = 0` vs `1` vs `-1` | `0` + femelle vers le bas → fondée ; `0` sans → non fondée ; `1` → non fondée ; `-1` → invalide |
| T5 | `test_collision_void_contact` | Section F | `OVERLAPPING` mais `solid_overlap` retourne `None` | `CONTACT`, pas `PENETRATION` |
| T6 | `test_collision_exact_penetration` | Section F | `solid_overlap` retourne `Tuple[AABB, ...]` non vide | `PENETRATION` |
| T7 | `test_candidate_implies_nothing` | Un candidat n'est pas un bond | Deux pièces lointaines | `evaluate_connector_pair` retourne `None` |
| T8 | `test_bond_implies_candidate` | H1 | Deux pièces avec bond valide | La paire est dans `ReferenceSearchApproximation` |
| T9 | `test_fast_subset_physical` | Validation futur index rapide | Même fixture que T8 | P ⊆ C_fast (pas C_ref ⊆ C_fast) |
| T10 | `test_immutable_state_snapshot` | Section J | Ajouter une pièce, vérifier l'ancien état | Ancien état inchangé |
| T11 | `test_exact_arithmetic_rotation` | Section C | Rotation de `(3,4,5)` par 90° sur Z | Résultat dans ℤ³, pas de `float` |
| T12 | `test_solid_overlap_exact_decomposition` | Section F | Intersection avec voids partiels | `Tuple[AABB, ...]` exact ou `None`, jamais AABB englobant approximatif |
| T13 | `test_state_deep_immutability` | Section J | Tentative de mutation via `graph.parts` | Échec silencieux ou exception |
| T14 | `test_collide_chain_completeness` | Section F | Deux pièces avec collision connue | `collide()` suit la chaîne `geometric_relation → intersection_aabb → solid_overlap → collision_status` |

---

## Section N — Limitations explicites (P0)

| Limitation | Scope BFK-001 | Futur |
|------------|---------------|-------|
| P0_B_INSERTION_TRAJECTORY | False | BFK-002 |
| P0_C_SWEPT_VOLUME | False | BFK-002 |
| P0_D_ACCESSIBILITY | False | BFK-002 |
| P0_E_INCREMENTAL_STABILITY | False | BFK-002 |
| PHYSICAL_COVERAGE | False | Hors scope |
| TOLERANCE_VALUE | False (ouverte) | BFK-001.2 ou BFK-002 |
| TOLERANCE_ANGULAR_USED | False | BFK-002 |

---

## Section O — Matrice de dépendances (DAG valide)

```
LDUVector, Orientation, AABB (entiers)
    ↓
Connector
    ↓
GeometricRelation, CollisionStatus, Optional[Tuple[AABB, ...]]
    ↓
ConnectorTolerance
    ↓
PhysicalBond
    ↓
PlacedPart
    ↓
SpatialCandidateIndex
    ↓
SearchApproximation
    ↓
ReferenceSearchApproximation
    ↓
ConstructionGraph
    ↓
ConstructionState
    ↓
Validation H1-H6
```

Vérifications d'acyclicité :
- `SearchApproximation` ne connaît pas `PhysicalBond` ✓
- `SpatialCandidateIndex` ne connaît pas `ConnectorTolerance` ✓
- `ConstructionState` ne recalcule pas de bonds ✓
- `ConnectorTolerance` n'a pas de valeur par défaut ✓
- `solid_overlap` ne sur-approxime pas ✓
- `ConstructionState` ne contient pas d'objet mutable ✓
- `collide()` ne connaît pas `Connector` ni `PhysicalBond` ✓

---

## Section P — Glossaire

- **Autorité** : fonction ou protocole avec droit exclusif de décision dans son domaine.
- **Frontière d'autorité** : limite au-delà de laquelle une entité ne peut pas émettre de jugement.
- **Arithmétique exacte** : tout calcul géométrique dans ℤ. Seule exception : comparaison distance/tolérance dans l'oracle.
- **Value object** : objet immuable sans identité propre.
- **Partition exacte d'AABB** : union exacte = R, intérieurs deux à deux disjoints.
- **SpatialSnapshot** : vue de lecture seule d'un index spatial (query uniquement).
- **Orchestrateur** : entité extérieure au contrat qui coordonne les appels aux autorités.

---

## Section Q — Hors scope BFK-001 v3.3.2

| Élément | Raison | Version cible |
|---------|--------|---------------|
| Valeur numérique de `ConnectorTolerance` | Attente justification métrologique | BFK-001.2 / BFK-002 |
| `BuildStep` exact | Dépend du langage d'instruction | BFK-001.1 |
| Solver de stabilité | P0_E = False | BFK-002 |
| Trajectoire d'insertion | P0_B = False | BFK-002 |
| Volume balayé | P0_C = False | BFK-002 |
| Accessibilité | P0_D = False | BFK-002 |
| Voxelisation interne | Non requise pour AABB exact | Futur |
| Physical coverage ratio | Non défini | Hors scope |
| `max_angular_error_deg` utilisé | BFK-001 = égalité exacte | BFK-002 |
| Orchestrateur | Coordination extérieure | Hors scope |

---

## Section R — Checklist de revue avant GO

- [ ] Aucune comparaison flottante en géométrie fondamentale
- [ ] `solid_overlap` exact avec partition formelle
- [ ] Orientation = matrice 3×3 entière
- [ ] `ConnectorTolerance` sans défaut ; angle non utilisé
- [ ] H1 = P ⊆ C
- [ ] `ReferenceSearchApproximation` O(n²) exhaustive
- [ ] `ConstructionState` réellement immuable (Tuple, pas List ; `SpatialSnapshot` query-only)
- [ ] `ConstructionGraph` en Tuple
- [ ] DAG acyclique
- [ ] 14 tests adversariaux spécifiés
- [ ] `PhysicalBond` opaque, création exclusive oracle
- [ ] Compatibilité `stud_male ↔ stud_female` exacte
- [ ] Fondation formalisée géométriquement (`stud_female` + normale `(0,0,-1)`)
- [ ] Distance euclidienne dans l'oracle
- [ ] `collide()` isolé de la mécanique
- [ ] `transform_aabb()` défini et exact
- [ ] `CollisionGeometry` en repère local, transformé par `collide()`
- [ ] **Distinction position/direction** : `transform_local_to_world` (position) vs `transform_local_direction_to_world` (normale)
- [ ] Aucun stub Python dans le contrat

---

# PARTIE 2 — STUBS PYTHON BFK-001 v3.3.2

**Fichier : `bfk001_kernel.py`**

```python
"""
BFK-001 KERNEL v3.3.2
BrickForge Kernel — Implémentation Python
Statut : ZERO logique comportementale initiale. Remplacer les '...' par l'implémentation.
Version : 3.3.2
Date : 2026-08-25
Principe directeur : séparation stricte des autorités — géométrie → collision → mécanique
Consigne CLAUDE CODE :
  1. Implémenter les tests adversariaux T1a–T14 D'ABORD.
  2. Remplacer chaque '...' par la logique conforme au contrat v3.3.2.
  3. NE JAMAIS utiliser transform_local_to_world() pour une normale.
  4. NE JAMAIS introduire de List dans ConstructionGraph ou ConstructionState.
  5. PhysicalBond reste opaque : seul evaluate_connector_pair() le construit.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterable, Mapping, Optional, Protocol, Tuple, TypeAlias

# =============================================================================
# Section B — Primitives géométriques et arithmétique exacte
# =============================================================================

@dataclass(frozen=True)
class LDUVector:
    """Élément de ℤ³. Aucune opération ne produit de coordonnée non entière."""
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class AABB:
    """Axis-Aligned Bounding Box.
    Précondition : min.x <= max.x, min.y <= max.y, min.z <= max.z."""
    min: LDUVector
    max: LDUVector


class GeometricRelation(Enum):
    """Relation topologique entre deux AABB. Arithmétique exacte sur les entiers."""
    DISJOINT = auto()
    TOUCHING = auto()
    OVERLAPPING = auto()


def geometric_relation(a: AABB, b: AABB) -> GeometricRelation:
    """Détermine la relation topologique entre deux AABB. Arithmétique exacte."""
    ...


def intersection_aabb(a: AABB, b: AABB) -> Optional[AABB]:
    """Retourne l'AABB de l'intersection si OVERLAPPING, sinon None.
    Un contact de face nul ne produit pas d'AABB."""
    ...


def transform_aabb(aabb: AABB, pose: Pose) -> AABB:
    """Transforme les 8 coins de l'AABB par la pose.
    Retourne l'AABB englobant exact (min/max composante par composante).
    Toutes les opérations sont exactes dans ℤ³."""
    ...


# =============================================================================
# Section C — Orientation
# =============================================================================

@dataclass(frozen=True)
class Orientation:
    """Matrice de rotation 3×3 entière.
    Coefficients ∈ {−1,0,1}, orthogonalité, déterminant +1."""
    m00: int; m01: int; m02: int
    m10: int; m11: int; m12: int
    m20: int; m21: int; m22: int


Pose: TypeAlias = Tuple[LDUVector, Orientation]
"""Donnée d'une translation entière et d'une rotation discrète."""


def transform_local_to_world(local: LDUVector, pose: Pose) -> LDUVector:
    """Transformation d'une POSITION du repère local au repère monde.
    world = orientation @ local + translation
    Résultat garanti dans ℤ³.
    INTERDIT d'utiliser cette fonction pour une normale / direction.
    """
    ...


def transform_local_direction_to_world(
    local_direction: LDUVector,
    orientation: Orientation,
) -> LDUVector:
    """Transformation d'une DIRECTION / NORMALE du repère local au repère monde.
    Seule la rotation est appliquée ; aucune translation n'est ajoutée.
    world_direction = orientation @ local_direction
    Résultat garanti dans ℤ³.
    OBLIGATOIRE pour les normales de connecteurs et les vecteurs directeurs.
    """
    ...


# =============================================================================
# Section D — Connecteurs et tolérance
# =============================================================================

@dataclass(frozen=True)
class Connector:
    """Connecteur mécanique dans le repère local de la pièce.
    local_normal : exactement une composante non-nulle parmi les 6 directions axiales."""
    ctype: str
    local_pos: LDUVector
    local_normal: LDUVector


@dataclass(frozen=True)
class ConnectorTolerance:
    """Paramètre d'entrée de l'oracle mécanique.
    max_angular_error_deg est contractuellement présent mais explicitement
    NON utilisé par l'oracle en BFK-001 (réservé à BFK-002)."""
    max_position_error_ldu: float
    max_angular_error_deg: float


# =============================================================================
# Section E — Oracle mécanique indépendant
# =============================================================================

@dataclass(frozen=True)
class PhysicalBond:
    """Type opaque. Autorité de création EXCLUSIVE de evaluate_connector_pair.
    Aucune API publique de BFK-001 ne permet sa construction directe.
    L'implémentation DOIT utiliser un mécanisme privé de construction
    (factory interne, constructeur privé conventionnel, ou équivalent).
    """
    pass


def evaluate_connector_pair(
    connector_a: Connector,
    pose_a: Pose,
    connector_b: Connector,
    pose_b: Pose,
    tolerance: ConnectorTolerance,
) -> Optional[PhysicalBond]:
    """Évalue si deux connecteurs forment un bond mécanique valide.

    Critères BFK-001 (non exhaustif, l'oracle conserve l'autorité ultime) :
    • Compatibilité ctype : _compatible(ctype_a, ctype_b) doit être vrai.
      BFK-001 définit : 'stud_male' ↔ 'stud_female' uniquement.
    • Normales opposées EXACTES :
      transform_local_direction_to_world(connector_a.local_normal, pose_a[1])
      ==
      -transform_local_direction_to_world(connector_b.local_normal, pose_b[1])
    • max_angular_error_deg est IGNORE en BFK-001.
    • Distance euclidienne entre positions monde :
      pos_a = transform_local_to_world(connector_a.local_pos, pose_a)
      pos_b = transform_local_to_world(connector_b.local_pos, pose_b)
      dx, dy, dz = pos_a.x - pos_b.x, pos_a.y - pos_b.y, pos_a.z - pos_b.z
      distance = sqrt(dx² + dy² + dz²)
      Bond valide ssi distance <= tolerance.max_position_error_ldu

    Contraintes contractuelles :
    • Ne connaît PAS SearchApproximation, SpatialCandidateIndex,
      connector_registry, voxel, solver, ConstructionState, graphe.
    • Fonction pure.
    """
    ...


# =============================================================================
# Section F — Collision et géométrie solide
# =============================================================================

class CollisionStatus(Enum):
    """Autorité de classification collisionnelle."""
    CLEAR = auto()
    CONTACT = auto()
    PENETRATION = auto()


@dataclass(frozen=True)
class CollisionGeometry:
    """Géométrie solide d'une pièce dans son repère LOCAL.
    exterior et voids sont exprimés dans le repère local de la pièce.
    collide() transforme l'exterior et tous les voids en coordonnées monde
    avant toute comparaison ou soustraction géométrique."""
    exterior: AABB
    voids: Tuple[AABB, ...]


def solid_overlap(
    intersection: AABB,
    solid_a: AABB,
    voids_a: Tuple[AABB, ...],
    solid_b: AABB,
    voids_b: Tuple[AABB, ...],
) -> Optional[Tuple[AABB, ...]]:
    """Autorité géométrique exacte.
    Calcule la région de matière solide effectivement pénétrée après
    soustraction des voids.

    Retourne None si la région est vide.
    Retourne Tuple[AABB, ...] représentant une partition exacte sinon.
    Union exacte = R, intérieurs deux à deux disjoints.
    Aucune sur-approximation n'est autorisée.
    """
    ...


def collision_status(
    relation: GeometricRelation,
    overlap: Optional[Tuple[AABB, ...]],
) -> CollisionStatus:
    """Traduit la relation géométrique et le résultat de solid_overlap en statut.

    Règles :
    • DISJOINT → CLEAR
    • TOUCHING → CONTACT
    • OVERLAPPING + overlap is None → CONTACT (engagement dans voids)
    • OVERLAPPING + overlap is not None → PENETRATION
    """
    ...


def collide(
    geometry_a: CollisionGeometry,
    pose_a: Pose,
    geometry_b: CollisionGeometry,
    pose_b: Pose,
) -> CollisionStatus:
    """Autorité collisionnelle complète.
    Évalue le statut collisionnel entre deux pièces placées dans l'espace.

    Algorithme contractuel :
    1. Transforme exterior et tous les voids en coordonnées monde :
       aabb_a = transform_aabb(geometry_a.exterior, pose_a)
       voids_a_m = tuple(transform_aabb(v, pose_a) for v in geometry_a.voids)
       aabb_b = transform_aabb(geometry_b.exterior, pose_b)
       voids_b_m = tuple(transform_aabb(v, pose_b) for v in geometry_b.voids)
    2. relation = geometric_relation(aabb_a, aabb_b)
    3. DISJOINT → CLEAR ; TOUCHING → CONTACT
    4. OVERLAPPING → intersection_aabb() → solid_overlap() → collision_status()

    Contraintes :
    • Ne connaît PAS Connector, PhysicalBond, SearchApproximation,
      SpatialCandidateIndex, ConstructionState, evaluate_connector_pair.
    """
    ...


# =============================================================================
# Section G — SpatialCandidateIndex (Protocol)
# =============================================================================

class SpatialCandidateIndex(Protocol):
    """Accélérateur spatial. Peut dire 'regarde ici'.
    Ne peut JAMAIS dire 'connectés' ou 'pas connectés'."""
    def query(self, region: AABB) -> Iterable[str]:
        """Retourne les identifiants candidats. AUCUNE garantie d'exhaustivité."""
        ...

    def insert(self, part_id: str, aabb: AABB) -> None:
        """Indexe une nouvelle pièce."""
        ...

    def remove(self, part_id: str) -> None:
        """Désindexe une pièce."""
        ...


# =============================================================================
# Section H — SearchApproximation (Protocol)
# =============================================================================

@dataclass(frozen=True)
class PlacedPart:
    """Value object de référence spatiale. Aucune autorité mécanique."""
    part_id: str
    pose: Pose
    aabb: AABB
    connectors: Tuple[Connector, ...]


class SearchApproximation(Protocol):
    """Responsabilité : générer l'ensemble des paires à soumettre à l'oracle.
    AUCUNE garantie mécanique sur les paires retournées.
    Porte l'obligation H1 (P ⊆ C)."""
    def find_candidate_pairs(
        self,
        index: SpatialCandidateIndex,
        placed_parts: Mapping[str, PlacedPart],
        tolerance: ConnectorTolerance,
    ) -> Iterable[Tuple[str, str, Connector, Connector]]:
        """Retourne des tuples (part_id_a, part_id_b, connector_a, connector_b).
        Les Connector sont en coordonnées LOCALES."""
        ...


class ReferenceSearchApproximation:
    """Implémentation de référence O(n²).
    Triviale, exhaustive, lente, démontrable."""
    def find_candidate_pairs(
        self,
        index: SpatialCandidateIndex,
        placed_parts: Mapping[str, PlacedPart],
        tolerance: ConnectorTolerance,
    ) -> Iterable[Tuple[str, str, Connector, Connector]]:
        """Ignore l'index (inutile en O(n²) exhaustive)."""
        ...


def _compatible(ctype_a: str, ctype_b: str) -> bool:
    """BFK-001 définit exactement :
    'stud_male' est compatible avec 'stud_female' et réciproquement.
    Tout autre couple est non compatible (rejeté ou réservé)."""
    ...


# =============================================================================
# Section I — Graphes
# =============================================================================

@dataclass(frozen=True)
class ConstructionGraph:
    """Graphe de construction. Utilise Tuple pour l'immutabilité profonde.
    edges = tous les bonds, pas un arbre couvrant."""
    parts: Tuple[Tuple[str, AABB, Tuple[Connector, ...]], ...]
    edges: Tuple[Tuple[str, str, Tuple[PhysicalBond, ...]], ...]


# BuildStep sera défini dans BFK-001.1
BuildStep = object


@dataclass(frozen=True)
class InstructionGraph:
    """Graphe d'instructions."""
    steps: Tuple[BuildStep, ...]

    def validate_dag(self) -> bool:
        """Vérifie que le graphe d'instructions est un DAG."""
        ...


# =============================================================================
# Section J — ConstructionState
# =============================================================================

class SpatialSnapshot(Protocol):
    """Vue de lecture seule d'un index spatial.
    Protocole query uniquement, sans insert/remove."""
    def query(self, region: AABB) -> Iterable[str]:
        """Même sémantique que SpatialCandidateIndex.query."""
        ...


@dataclass(frozen=True)
class ConstructionState:
    """Pur conteneur immuable. Ne calcule pas, ne stocke que.
    Aucune méthode de mutation. Aucune référence vers un objet mutable."""
    graph: ConstructionGraph
    spatial_snapshot: SpatialSnapshot


# =============================================================================
# Section L — Support et fondation
# =============================================================================

# FoundationCheck sera défini lors de l'implémentation
FoundationCheck = object


def check_foundation(
    part_exterior: AABB,
    part_connectors: Tuple[Connector, ...],
    part_pose: Pose,
    foundation_plane_z: int = 0,
) -> FoundationCheck:
    """Règles (arithmétique exacte, entiers) :
    • min.z < foundation_plane_z → INVALIDE (pénètre le sol)
    • min.z > foundation_plane_z → NON fondée (doit avoir un bond)
    • min.z == foundation_plane_z → Fondée ssi la pièce possède au moins un
      Connector de ctype 'stud_female' dont la normale transformée est (0,0,-1) :
      transform_local_direction_to_world(connector.local_normal, part_pose[1]) == (0,0,-1)
      Sinon → NON fondée.
    Aucun epsilon. min.z est contractuellement un entier.
    """
    ...
```

---

# PARTIE 3 — Consignes supplémentaires pour Claude Code

## Règles d'or non négociables

1. **Tests d'abord** : `test_bfk001_adversarial.py` doit être écrit et exécuté AVANT toute implémentation métier. Les tests doivent échouer initialement (red/green/refactor).
2. **Distinction position/direction** :
   - Position de connecteur : `transform_local_to_world(connector.local_pos, pose)`
   - Normale de connecteur : `transform_local_direction_to_world(connector.local_normal, pose[1])`
   - Fondation : `transform_local_direction_to_world(connector.local_normal, part_pose[1])`
3. **PhysicalBond** : utiliser un mécanisme privé (ex: `_PhysicalBondFactory` interne au module, ou `__init__` avec convention underscore) pour empêcher la construction externe. Les tests T1a/T1b doivent vérifier cette isolation.
4. **Aucune mutation** : si une fonction doit "modifier" l'état, elle retourne un **nouveau** `ConstructionState` avec les champs mis à jour. `ConstructionState` reste `frozen=True`.
5. **Solid overlap exact** : la soustraction d'AABB n'est pas fermée. Le retour doit être un `Tuple[AABB, ...]` représentant une partition exacte. Option d'implémentation : découper par plans des voids et retourner les AABB résiduels.
6. **Orientation** : les 24 rotations du groupe de Cayley (rotations à 90°) sont les seules valides. L'implémentation peut valider `det(M) == 1` et `M.T @ M == I` à la construction.
7. **Pas de valeur par défaut** : `ConnectorTolerance` n'a pas de valeurs par défaut. Tout appel à l'oracle ou au pipeline de recherche doit fournir une instance explicite.
8. **Immutabilité profonde** : vérifier que `ConstructionGraph.parts` et `.edges` sont bien des `Tuple` (et non des `List` converties). T13 vérifie cela.

## Ordre d'implémentation recommandé (détaillé)

### Phase 0 — Fondation du projet
- Créer `bfk001_kernel.py` avec les stubs ci-dessus.
- Créer `test_bfk001_adversarial.py` avec T1a–T14 (tous doivent échouer ou être `skip` initialement).

### Phase 1 — Géométrie (Sections B, C)
- `LDUVector`, `AABB`, `Orientation` (avec validation des contraintes).
- `geometric_relation()`, `intersection_aabb()`, `transform_aabb()`.
- `transform_local_to_world()`, `transform_local_direction_to_world()`.
- Valider avec T11 (arithmétique exacte).

### Phase 2 — Collision (Section F)
- `CollisionGeometry`, `solid_overlap()` (implémentation exacte).
- `collision_status()`, `collide()`.
- Valider avec T5, T6, T12, T14.

### Phase 3 — Oracle mécanique (Section E)
- `PhysicalBond` (opaque, mécanisme privé).
- `evaluate_connector_pair()` avec la distance euclidienne et la vérification des normales exactes.
- Valider avec T1a, T1b, T3, T7.

### Phase 4 — Recherche (Section H)
- `PlacedPart`, `ReferenceSearchApproximation`, `_compatible()`.
- Valider avec T2, T8.

### Phase 5 — État et graphe (Sections I, J)
- `ConstructionGraph`, `ConstructionState`, `SpatialSnapshot`.
- Valider avec T10, T13.

### Phase 6 — Fondation (Section L)
- `check_foundation()`.
- Valider avec T4.

### Phase 7 — Intégration
- Orchestrateur extérieur (hors contrat, mais nécessaire pour les tests d'intégration).
- Validation H1–H6.

---

# FIN DU DOCUMENT BFK-001 IMPLEMENTATION BRIEF v3.3.2
