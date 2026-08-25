# BFK-001 — Registre des zones d'ombre

Ce document existe pour qu'il n'y ait **aucune ambiguïté résiduelle** : chaque
zone est soit fermée (avec la preuve), soit ouverte et nommée précisément, avec
la décision qui manque et qui doit la prendre. Rien n'est laissé implicite.

Version du noyau : **BFK-001 v3.3.2** — 50 tests verts.

---

## 0. Où s'arrête le noyau

La réflexion produit (BrickForge) décrit trois couches. Le noyau n'en occupe
qu'une, et c'est volontaire :

| Couche | Contenu | Statut |
|---|---|---|
| 1 — Perception | image → segmentation → depth → géométrie cible (voxels) | **Hors noyau.** Aucune ligne ici. |
| 2 — Construction | patterns, solveur, **validation**, source de vérité | **Le noyau EST la partie validation + autorités.** Le solveur reste à écrire. |
| 3 — Documentation | notice, LDraw/LPub3D, nomenclature, achat | **Hors noyau**, sauf la nomenclature dont le prérequis (identité de pièce) est fermé. |

Le noyau ne construit rien. Il dit ce qui est vrai : ces deux pièces sont-elles
liées, se pénètrent-elles, cette pièce est-elle fondée. Un solveur pose les
pièces ; le noyau refuse les poses fausses. Cette séparation est la raison
d'être du contrat, et c'est elle qui permet de changer de solveur sans
retoucher une seule autorité.

---

## 1. Trois pièges hérités de l'historique du projet

Ils sont documentés ici parce qu'ils ont déjà coûté cher, et qu'ils reviendront
si personne ne les écrit.

### 1.1 La numérotation des invariants a changé de sens

Le compilateur v0.1 numérotait : `H1` connectivité globale, `H2` pas de pièce
flottante, `H3` couverture ≥ 99 %, `H4` pas de collision.
**BFK-001 v3.3.2 numérote autrement** :

| Code v3.3.2 | Sens | Équivalent v0.1 |
|---|---|---|
| H1_SEARCH_COVERAGE | P ⊆ C : aucun bond valide omis par la recherche | *n'existait pas* |
| H2_COLLISION | aucune PENETRATION | H4 |
| H3_AUTHORITY_INTEGRITY | aucun bond fabriqué hors de l'oracle | *n'existait pas* |
| H4_FLOATING | chaîne de bonds vers une fondation | H2 |
| H5_DISCONNECTED | graphe connexe | H1 |
| H6_FOUNDATION | pièce au plan de fondation valide | *n'existait pas* |

Un document qui dit « H1 » sans préciser la version parle donc de deux choses
opposées. **Le code suit strictement v3.3.2.**

### 1.2 Couverture de recherche ≠ couverture physique

L'audit du projet avait déjà relevé le renommage `physical_coverage_ratio` →
`search_coverage_ratio`. La Section N du contrat le grave : `PHYSICAL_COVERAGE
= False, hors scope`. Autrement dit : **le noyau ne sait pas dire si une
construction ressemble à la cible.** Il sait dire qu'elle est légale.
Ce qu'il faudrait pour la couverture physique : comparer l'union des AABB
solides posées aux voxels cibles — donc une `TargetGeometry`, absente du
contrat v3.3.2.

### 1.3 La voxelisation à 4 LDU était fausse par construction

L'audit avait relevé qu'une brique 1×1 (3005, largeur 20 LDU) centrée produit
des voxels à x = 2, non divisible par 4 : toute grille à pas 4 LDU rate des
positions légales. **Le problème n'existe plus : BFK-001 v3.3.2 ne voxelise
pas.** La géométrie est exacte (AABB entiers, soustraction exacte des vides).
La Section Q le confirme : « Voxelisation interne — non requise pour AABB
exact ». Si une voxelisation revient un jour, ce sera pour la perception
(couche 1), jamais pour l'autorité géométrique.

---

## 2. Zones fermées

Chacune est fermée **par un test**, pas par une intention.

| # | Zone | Fermeture | Preuve |
|---|---|---|---|
| 1 | Isolation d'autorité de l'oracle | Package par section ; l'oracle n'importe et n'expose aucun symbole de recherche, d'état, de graphe ou de collision | T1a, T1b |
| 2 | Fabrication de bonds hors oracle | Jeton privé + sous-classement interdit + registre faible d'émission | H3, `test_h3_rejects_bond_not_issued_by_oracle` |
| 3 | Position vs direction | `transform_local_direction_to_world` n'accepte **pas** de `Pose` : la translation est hors de portée d'une normale | T11 |
| 4 | Exactitude arithmétique | Un seul flottant dans tout le noyau : `sqrt(...) <= tolérance` | grep + T11 |
| 5 | Valeur de la tolérance | 0,5 LDU, **prouvée** équivalente à la coïncidence dans ℤ³ | `test_tolerance_is_lattice_safe` |
| 6 | Repère de `part_exterior` | Repère local, transformé par la pose | T4, dont le cas brique retournée |
| 7 | Partition exacte de `solid_overlap` | Découpe en dalles d'intérieurs disjoints, volume exact | T12 |
| 8 | Accroche LEGO réelle | Tenons inclus dans l'`exterior` : extérieurs `OVERLAPPING`, pénétration absorbée par les vides → `CONTACT` | `test_real_clutch_is_contact_not_penetration` |
| 9 | Immutabilité profonde | `Tuple` partout, `List` rejetée, snapshot mutable refusé | T10, T13 |
| 10 | Inverse de pose, monde → local, composition | Exacts dans ℤ³ (transposée, aucune division) | `test_pose_inversion_round_trips_under_every_rotation` |
| 11 | Les 24 rotations | Énumérées, nommées, groupe fermé et inversible | `test_rotation_group_is_exactly_the_24_rotations` |
| 12 | Recherche O(n²) | `LatticeSearchApproximation` : rangement par position entière, **preuve** de complétude, repli documenté | `test_lattice_search_is_complete_and_far_smaller` |
| 13 | Collision O(n²) | `GridSpatialIndex` à requête exhaustive ; élagage sans perte car DISJOINT ⇒ CLEAR | H2 sur le mur croisé |
| 14 | Pose incrémentale | `add_part` / `remove_part` : bonds existants conservés **par identité** | `test_add_part_matches_full_assembly_and_preserves_bond_identity` |
| 15 | « Puis-je poser ici ? » | `evaluate_placement` : verdict pur, sans état produit, dérivé de H2/H4/H6 | `test_evaluate_placement_answers_the_cad_question` |
| 16 | Persistance | Un document ne porte **jamais** un bond ; l'oracle les ré-émet au chargement | `test_document_never_carries_a_bond` |
| 17 | Identité de pièce | `part_id` (instance) ≠ `design_id` (référence) ≠ `color_id` | `test_bill_of_materials_counts_by_reference_and_colour` |
| 18 | Nomenclature | `bill_of_materials` agrège par référence et couleur | idem |

---

## 3. Zones ouvertes — chacune avec la décision qui manque

Classées par ce qu'elles bloquent réellement.

### 3.1 Bloquant pour dépasser l'empilement de briques

| Zone | État | Décision requise | Cible |
|---|---|---|---|
| **Types de connecteurs** | Seul `stud_male ↔ stud_female` existe. Technic (pin, axe, trou), clips, barres, charnières : absents. | Où vit la table de compatibilité ? Elle ne peut pas être un registre mutable : l'oracle doit rester pur et la Section E lui interdit de connaître un `connector_registry`. **Proposition : table gelée au niveau `Connector` (Section D), comme `_compatible` aujourd'hui.** | BFK-002 |
| **Géométrie non-AABB** | Un tenon cylindrique est un prisme carré ; une pente est sa boîte englobante. Deux pentes adjacentes se rejettent à tort. | Passer à une union de primitives (AABB + cylindres + prismes obliques) ou à un maillage. Décision structurante : l'arithmétique exacte survit aux prismes obliques à 45°, pas aux courbes. | BFK-002 |
| **SNOT** | **Structurellement déjà possible** : les 24 rotations et les 6 normales axiales sont supportées. Ce qui manque, ce sont les pièces (brackets, headlight) — donc 3.1 et 3.2 ci-dessus. | Aucune décision de noyau. Catalogue + géométrie. | BFK-002 |
| **Rotations libres** | Le groupe est fini (24). Charnières, Technic à angle : hors modèle. | La plus lourde : sortir des 24 rotations, c'est sortir de ℤ³ et perdre l'exactitude. Alternative : quaternions entiers ou rationnels exacts. **À ne pas décider à la légère : c'est A.1 qui tombe.** | BFK-002+ |

### 3.2 Bloquant pour qu'un modèle soit réellement constructible

| Zone | État | Décision requise | Cible |
|---|---|---|---|
| **P0_B — trajectoire d'insertion** | `False`. Un modèle peut être valide et impossible à monter : la pièce n'a aucun chemin pour arriver à sa place. | Modèle de trajectoire (translation le long d'une normale de connecteur, sur quelle distance ?). | BFK-002 |
| **P0_C — volume balayé** | `False`. Corollaire du précédent : rien ne vérifie que le chemin est libre. | Balayage d'AABB = AABB étendu ; exact si la trajectoire est axiale. | BFK-002 |
| **P0_D — accessibilité** | `False`. Rien n'interdit d'enfermer une pièce dans une coque fermée. | Définition d'« accessible » : depuis l'extérieur du modèle, par quel axe ? | BFK-002 |
| **P0_E — stabilité** | `False`. Un porte-à-faux passe H1–H6 et s'effondre dans la vraie vie. | Modèle : proxy (ratio de support, centre de gravité par couche) ou solveur de forces. Le compilateur v0.1 proposait `S1`/`S2` en métriques molles — c'est la voie raisonnable. | BFK-002 |
| **Interférence élastique** | Le tube d'accroche n'est pas modélisé : une autorité exacte classerait l'ajustement serré en `PENETRATION`. | Introduire un jeu signé (interférence tolérée) ou une couche mécanique séparée. Aujourd'hui la cavité est un vide franc et l'accroche est portée par l'oracle, pas par la géométrie. | BFK-002 |

### 3.3 Bloquant pour la notice et l'achat

| Zone | État | Décision requise | Cible |
|---|---|---|---|
| **`BuildStep` concret** | `Protocol` structurel (`step_id`, `depends_on`) ; `validate_dag` opérationnel (Kahn). Le type concret manque. | Le compilateur v0.1 proposait `step_number`, `parts`, `subassembly_id`, `dependencies` — compatible avec le Protocol actuel. Reste à figer. | BFK-001.1 |
| **Export LDraw (.ldr)** | Absent, **délibérément**. LDraw place l'axe Y vers le bas et chaque pièce a une origine propre définie dans son `.dat`. | Deux données à importer, pas à deviner : la convention d'axes (kernel Z-haut → LDraw −Y-haut) et **la table des origines de pièces**. Écrire un exporteur sans les vraies origines produirait des fichiers faux : je ne l'ai pas fait. | BFK-001.1 |
| **Palette couleur complète** | 9 codes LDraw seulement, en dur. | Import de la table LDraw/BrickLink (~70 couleurs actives, correspondances Element ID, couleurs discontinuées). Donnée externe. | Couche 3 |
| **Catalogue complet** | 8 références rectangulaires générées paramétriquement. | Import LDraw `.dat` → `CollisionGeometry` + connecteurs. Dépend entièrement de 3.1 (géométrie non-AABB). | BFK-002 |
| **Prix, disponibilité, substitution** | Absents. | Hors noyau, et **doit le rester** : un noyau géométrique ne consulte pas un marchand. | Couche 3 |

### 3.4 Choisi, pas subi

| Zone | Position |
|---|---|
| **`max_angular_error_deg`** | Présent, jamais lu, et un test le prouve. Aura un sens quand les rotations libres arriveront ; d'ici là, valeur 0,0 dans le préréglage LEGO — dire la vérité du modèle plutôt que suggérer une souplesse inexistante. |
| **`validate()` reste O(n²)** | Assumé. P (l'ensemble des bonds réels) est calculé exhaustivement, **indépendamment** de la recherche auditée : c'est un harnais de conformité, pas un chemin d'exécution. L'accélérer en réutilisant la recherche testée rendrait l'audit circulaire. Le chemin d'exécution, lui, est `LatticeSearchApproximation` + `GridSpatialIndex`. |
| **Undo / redo** | Résolu par construction : `ConstructionState` est immuable et `add_part` retourne un nouvel état sans toucher l'ancien. Empiler les états suffit. Aucune API de pile n'est fournie — c'est trois lignes côté application. |
| **Orchestrateur** | Hors contrat par décision (Section J). `bfk001/orchestration.py` en fournit un minimal ; une application est libre du sien. |
| **`TargetGeometry`** | Absente du contrat v3.3.2. Elle appartient à la couche 1 (perception) et au solveur, pas aux autorités. |

---

## 4. Ce qu'un solveur devra respecter

Pour que la couche 2 se branche sans rouvrir le noyau :

1. Ne jamais construire un `PhysicalBond` — seul `evaluate_connector_pair` en émet, et H3 le vérifie.
2. Appeler `evaluate_placement` avant de poser, `add_part` pour poser : jamais reconstruire un `ConstructionGraph` à la main.
3. Passer une `ConnectorTolerance` explicite à chaque appel — il n'existe aucune valeur par défaut, et c'est voulu.
4. Utiliser `LatticeSearchApproximation` en production, la référence O(n²) en test de conformité — et vérifier P ⊆ C_fast, jamais C_ref ⊆ C_fast.
5. Ne pas sérialiser de liaisons : un document porte des pièces, l'oracle porte le jugement.
