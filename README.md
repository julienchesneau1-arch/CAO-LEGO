# BFK-001 — BrickForge Kernel v3.3.2

Implémentation Python du contrat **BFK-001 v3.3.2**
(`docs/BFK001_IMPLEMENTATION_BRIEF_v3_3_2.md`).

Principe directeur : **séparation stricte des autorités — géométrie → collision
→ mécanique**. Arithmétique exacte dans ℤ³, immutabilité profonde, `PhysicalBond`
opaque.

État : **29 tests verts** (T1a–T14 + compléments + intégration H1–H6).

---

## Exécution

```bash
pytest                                  # toute la suite
pytest test_bfk001_adversarial.py       # T1a–T14 (Section M)
pytest test_bfk001_integration.py       # Phase 7, invariants H1–H6
```

Aucune dépendance hors `pytest` (bibliothèque standard uniquement).

---

## Arborescence

| Fichier | Section du contrat | Contenu |
|---|---|---|
| `bfk001_kernel.py` | — | **Façade** nommée par le brief. Aucune logique : réexporte l'API publique. |
| `bfk001/geometry.py` | B, C | `LDUVector`, `AABB`, `Orientation`, `Pose`, `geometric_relation`, `intersection_aabb`, `transform_aabb`, `transform_local_to_world`, `transform_local_direction_to_world` |
| `bfk001/connectors.py` | D | `Connector`, `ConnectorTolerance`, `_compatible` |
| `bfk001/oracle.py` | E | `PhysicalBond` (opaque), `evaluate_connector_pair`, `is_oracle_issued` |
| `bfk001/collision.py` | F | `CollisionStatus`, `CollisionGeometry`, `solid_overlap`, `collision_status`, `collide` |
| `bfk001/spatial.py` | G | `SpatialCandidateIndex`, `ReferenceSpatialIndex`, `FrozenSpatialSnapshot` |
| `bfk001/search.py` | H | `PlacedPart`, `SearchApproximation`, `ReferenceSearchApproximation` |
| `bfk001/graph.py` | I | `ConstructionGraph`, `BuildStep`, `InstructionGraph` |
| `bfk001/state.py` | J | `SpatialSnapshot`, `ConstructionState` |
| `bfk001/foundation.py` | L | `FoundationStatus`, `FoundationCheck`, `check_foundation` |
| `bfk001/validation.py` | K | H1 à H6, `validate` |
| `bfk001/orchestration.py` | — | `assemble`, `with_part` (**hors contrat**, Section J) |

DAG des imports (Section O) : `geometry → connectors → {oracle, collision,
spatial} → search → graph → state → validation → orchestration`. Aucun cycle.

---

## Les quatre règles tenues par le code

1. **Position vs direction.** `transform_local_direction_to_world()` n'accepte
   pas de `Pose` — seulement une `Orientation`. La translation est
   *structurellement* hors de portée d'une normale, pas seulement interdite par
   convention.
2. **Arithmétique exacte.** Aucun flottant hors de `ConnectorTolerance` (type
   contractuel) et de l'unique `math.sqrt(...) <= max_position_error_ldu` de
   l'oracle. `grep -rn "float\|sqrt" bfk001/` le vérifie en une commande.
3. **`Tuple` partout.** `ConstructionGraph` et `CollisionGeometry` rejettent une
   `List` à la construction (`TypeError`), récursivement.
4. **`PhysicalBond` opaque.** Constructeur verrouillé par jeton privé,
   sous-classement interdit, aucun champ public. Un objet fabriqué par
   contournement (`object.__new__`) n'est pas dans le registre d'émission et
   `is_oracle_issued()` le rejette : c'est ce qui donne des dents à H3.

---

## Écarts signalés (règle absolue n°1)

Aucun écart n'a été pris sans nécessité. Les voici tous.

### 1. Package `bfk001/` plutôt qu'un fichier unique

Le brief (Partie 2) décrit un `bfk001_kernel.py` unique. **T1b audite le module
dans lequel l'oracle vit réellement** (`inspect.getmodule(evaluate_connector_pair)`).
Dans un fichier unique, ce module expose `SearchApproximation`,
`SpatialCandidateIndex`, `ConstructionState` et les symboles de collision :
l'isolation d'autorité de la Section E devient déclarative et invérifiable —
T1b échoue, et il a raison d'échouer (voir le commit de Phase 0).

`bfk001_kernel.py` est conservé tel quel comme **façade** : tout code écrit
contre le brief (`import bfk001_kernel`) fonctionne sans modification.

### 2. `_compatible` défini dans `connectors.py` (Section D), pas dans `search.py`

Le contrat écrit `_compatible` dans le bloc de code de la Section H, mais la
Section E impose que l'oracle l'évalue **sans connaître `SearchApproximation`**.
La relation est donc définie au niveau `Connector` du DAG et importée par ses
deux consommateurs (oracle et recherche). Source unique, DAG acyclique.

### 3. `PhysicalBond` : classe à `__slots__`, pas `@dataclass(frozen=True)`

Un `dataclass` génère un constructeur public — incompatible avec l'autorité de
création exclusive (A.8). Le brief autorise explicitement « constructeur privé
conventionnel, ou équivalent » (Partie 3, règle 3). Retenu : jeton privé +
`__init_subclass__` interdit + registre faible des bonds émis.

### 4. `check_foundation(part_exterior=…)` — repère **LOCAL**

Le contrat ne tranche pas. Retenu : `part_exterior` est exprimé dans le repère
local (comme `CollisionGeometry.exterior`, et par contraste avec
`PlacedPart.aabb` documenté « AABB monde »), puis transformé par `part_pose`.
Argument décisif : si seule l'orientation était utile, la signature prendrait
une `Orientation` — comme `transform_local_direction_to_world` — et non une
`Pose` complète.

**Si l'intention était « AABB monde »**, un seul point change :
`bfk001/foundation.py`, remplacer
`world_exterior = transform_aabb(part_exterior, part_pose)` par
`world_exterior = part_exterior`. Le cas « brique retournée » de T4 devra être
réécrit en conséquence.

### 5. `collide()` fait passer *tous* les cas par `collision_status()`

L'algorithme F.5 retourne `CLEAR`/`CONTACT` directement aux étapes 3 et 4. Le
code appelle `collision_status(relation, None)` : comportement identique, mais
la traduction relation → statut reste concentrée dans son unique autorité (F.4).

### 6. Types laissés ouverts par le contrat

- `FoundationCheck` : dataclass gelée `(status: FoundationStatus, world_min_z: int)`.
  Le `world_min_z` est retourné parce que H6 doit distinguer « au plan » de
  « au-dessus du plan » sans recalculer la géométrie.
- `BuildStep` : `Protocol` structurel `(step_id: str, depends_on: Tuple[str, ...])`,
  le type concret relevant de BFK-001.1 (Section Q). `validate_dag()` =
  unicité des identités + références connues + tri topologique de Kahn.

### 7. Ajouts hors contrat, nécessaires à l'orchestration et aux tests

`ReferenceSpatialIndex`, `FrozenSpatialSnapshot`, `is_oracle_issued`,
`bfk001/validation.py` (H1–H6) et `bfk001/orchestration.py`. Aucun n'émet de
jugement mécanique ou géométrique : ils appellent les autorités.

### 8. Validations défensives à la construction

`Orientation` vérifie {−1,0,1}, MᵀM = I et det = +1 ; `AABB` vérifie
min ≤ max ; `Connector` vérifie que la normale est l'une des 6 directions
axiales unitaires ; `ConstructionState` refuse un `spatial_snapshot` exposant
`insert`/`remove`. Ces contrôles dérivent du contrat mais n'y sont pas écrits
comme obligations d'implémentation.

### 9. T14 — assertion affinée

`solid_overlap()` réutilise légitimement `intersection_aabb()` en interne. T14
vérifie donc l'**ordre de première entrée** dans chaque autorité de la chaîne,
et qu'aucune n'est franchie deux fois (`geometric_relation`, `solid_overlap`,
`collision_status` : exactement un appel chacune).

---

## Points restés ouverts (Sections N et Q)

| Point | État |
|---|---|
| Valeur numérique de `ConnectorTolerance` | **Ouverte.** Les tests utilisent `0.5 LDU` comme valeur de fixture, sans portée contractuelle. Aucune valeur par défaut n'existe dans le code. |
| `max_angular_error_deg` | Accepté, jamais lu. Vérifié par `test_angular_tolerance_is_ignored`. |
| P0-B/C/D/E (trajectoire, volume balayé, accessibilité, stabilité) | Hors scope BFK-001. |
| `BuildStep` exact, langage d'instruction | BFK-001.1. |
| Index spatial rapide | Non implémenté. La règle de conformité (P ⊆ C_fast, *et non* C_ref ⊆ C_fast) est déjà testée par T9 avec une implémentation rapide jouet. |

---

## Checklist Section R

| Item | État |
|---|---|
| Aucune comparaison flottante en géométrie fondamentale | ✅ |
| `solid_overlap` exact avec partition formelle | ✅ T12 (volume exact 1200, morceaux d'intérieurs disjoints) |
| Orientation = matrice 3×3 entière | ✅ det = +1 vérifié à la construction |
| `ConnectorTolerance` sans défaut ; angle non utilisé | ✅ |
| H1 = P ⊆ C | ✅ T2, T8, T9, `check_h1_search_coverage` |
| `ReferenceSearchApproximation` O(n²) exhaustive | ✅ |
| `ConstructionState` réellement immuable | ✅ T10, T13 |
| `ConstructionGraph` en Tuple | ✅ `List` rejetée par `TypeError` |
| DAG acyclique | ✅ imports vérifiables module par module |
| 14 tests adversariaux spécifiés | ✅ T1a–T14 + 5 compléments |
| `PhysicalBond` opaque, création exclusive oracle | ✅ T1a compl., H3 |
| Compatibilité `stud_male ↔ stud_female` exacte | ✅ |
| Fondation formalisée géométriquement | ✅ T4 (5 cas, dont brique retournée) |
| Distance euclidienne dans l'oracle | ✅ unique opération flottante |
| `collide()` isolé de la mécanique | ✅ n'importe que `geometry` |
| `transform_aabb()` défini et exact | ✅ T11 |
| `CollisionGeometry` en repère local, transformé par `collide()` | ✅ T5, T6, T14 |
| Distinction position / direction | ✅ signature incompatible par construction |
| Aucun stub Python dans le contrat | ✅ contrat archivé dans `docs/` |
