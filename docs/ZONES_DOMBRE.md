# BFK-001 — Registre des zones d'ombre

Ce document existe pour qu'il n'y ait **aucune ambiguïté résiduelle** : chaque
zone est soit fermée (avec la preuve), soit ouverte et nommée précisément, avec
la décision qui manque et qui doit la prendre. Rien n'est laissé implicite.

Version du noyau : **BFK-001 v3.3.2** — 74 tests verts, chaîne complète photo → notice.

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
| 19 | H3 réellement vérifiable | Identité d'objet imposée ; copie stable, sérialisation refusée | `test_bond_identity_is_required_for_h3`, `test_bond_copies_to_itself_and_refuses_serialization` |
| 20 | Intégrité structurelle du graphe | Arête fantôme, boucle, doublon, arête sans liaison, id dupliqué : tous rejetés | `test_graph_rejects_structural_fictions` |
| 21 | Invariants sans angle mort | H2/H4/H6 refusent de juger une pièce sans géométrie | `test_invariants_refuse_to_judge_without_geometry` |
| 22 | Exactitude non bornée | Écartement entier exact avant tout flottant | `test_oracle_holds_on_unbounded_coordinates` |

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

## 4. Traçabilité de la revue : v3 → v3.3.2

Le contrat implémenté est l'aboutissement d'une revue en sept passes. Plusieurs
décisions y ont été **prises puis renversées**. Quiconque relit une version
intermédiaire risque d'implémenter une règle abandonnée — d'où ce tableau.

### 4.1 Décisions renversées (ne jamais réintroduire)

| Proposé dans une version antérieure | Décision finale v3.3.2 | Pourquoi c'est important |
|---|---|---|
| `BFK001_GEOMETRIC_EPSILON_LDU = 1e-6` et comparaisons à epsilon près | **Aucun epsilon.** Arithmétique exacte ℤ (A.1) | Un epsilon en géométrie entière n'absorbe rien : il n'y a pas d'erreur d'arrondi à absorber. Il ne ferait qu'introduire une zone grise entre CONTACT et PENETRATION. |
| Tolérance figée à **1,0 LDU** / 5°, « alignée sur la grille voxel » | Laissée ouverte en v3.3.2, **fixée à 0,5 LDU** ici | L'argument de la grille voxel est mort avec la voxelisation. Surtout, 1,0 LDU est exactement la valeur limite : deux connecteurs distants d'un LDU sur un axe sont à distance 1,0, donc `<= 1.0` les accepte. La tolérance cesse d'être équivalente à la coïncidence et légitime silencieusement une pièce mal posée. 0,5 reste strictement en deçà. |
| `solid_overlap` peut **sur-approximer** (AABB englobante, faux positifs acceptés) | **Interdit.** Partition exacte, aucune sur-approximation (A.6) | Un faux positif de pénétration rejette des assemblages légaux. La partition exacte est vérifiée cellule par cellule sur 300 configurations tirées au sort. |
| `ConstructionState.add_part()` — mise à jour immuable **portée par l'état** | **Supprimé.** Pur conteneur, orchestration extérieure (J.2) | Attention au faux ami : `bfk001/orchestration.py` expose bien une fonction `add_part`, mais c'est une **fonction libre hors contrat** qui retourne un nouvel état — pas une méthode de `ConstructionState`, qui n'en a aucune. |
| `ConstructionState.spatial_index: SpatialCandidateIndex` | **`SpatialSnapshot`, query-only** (J.1) | Un index mutable dans un état « immuable » est une fuite. Le code va plus loin que le contrat : `ConstructionState` **refuse** un snapshot exposant `insert`/`remove`. |
| `ConstructionGraph` en `List` | **`Tuple` partout** (I.1) | Rejeté par `TypeError` à la construction, récursivement. |
| `H3_INVALID_BOND` (« aucun bond ne viole les contraintes ») | **`H3_AUTHORITY_INTEGRITY`** (« aucun bond fabriqué hors de l'oracle ») | Formulation bien plus forte, et la seule vérifiable : un bond émis par l'oracle est valide **par définition**. |
| T9 : `C_fast ⊇ C_reference` | **`P ⊆ C_fast`**, et `C_ref ⊆ C_fast` explicitement **non exigé** (H.4) | La référence est un oracle de complétude *physique*, pas un canon de candidats. Le test l'exerce : il vérifie `P ⊆ C_fast` **et** que `C_fast` est strictement inclus dans `C_ref`. |
| T1 unique (introspection du frame d'appel) | **T1a signature + T1b dépendances de module** | L'introspection de frame était fragile ; l'audit statique du module, lui, mord. |

### 4.2 Les six consignes du GO, vérifiées dans le code

| Consigne | Où elle est tenue | Vérification |
|---|---|---|
| 1. Ne pas modifier l'architecture sans signaler | README « Écarts signalés » : 9 écarts, chacun motivé | — |
| 2. Position vs normale | `transform_local_direction_to_world` n'accepte **pas** de `Pose` | `oracle.py:106-107`, `foundation.py:99` : les seuls appels sur une normale, tous via `pose[1]` |
| 3. `PhysicalBond` opaque, mécanisme privé au choix | Jeton privé + `__init_subclass__` interdit + registre faible | `oracle.py` — c'est ce registre qui rend H3 vérifiable, pas seulement déclaré |
| 4. `_compatible` / référence O(n²) implémentés **littéralement** | Expression du contrat recopiée ; la référence ignore l'index et la tolérance | La recherche accélérée est une **classe séparée** (H.4 l'anticipe) ; la référence n'a pas été touchée |
| 5. Tests adversariaux d'abord | Commit `4f59320` : 18 tests, 16 rouges, **avant** toute implémentation | `git log --reverse` |
| 6. Aucun `List` dans le graphe ni l'état | Zéro occurrence dans `graph.py` / `state.py` | `TypeError` à la construction |

### 4.3 Une préconisation du contrat volontairement non suivie

`solid_overlap` porte en v3.3.1/v3.3.2 la précondition « `intersection ⊆ solid_a`
et `intersection ⊆ solid_b`, sinon comportement indéfini ». L'implémentation ne
s'y fie pas : elle recalcule `base = intersection ∩ solid_a ∩ solid_b`. Sous la
précondition, le résultat est identique ; hors précondition, il reste défini au
lieu d'être arbitraire. Aucun comportement contractuel n'est modifié — un
« comportement indéfini » de moins.

---

## 5. Revue adversariale du noyau par lui-même

Le code a été relu contre lui-même, en cherchant activement à le mettre en
défaut plutôt qu'à le confirmer. Huit défauts réels ont été trouvés et corrigés.
Ils sont listés ici parce qu'ils sont instructifs, pas parce qu'ils sont
résolus.

### 5.1 La spécification littérale de `PhysicalBond` rend H3 vide de sens

Le contrat écrit `@dataclass(frozen=True) class PhysicalBond: pass`. Un
dataclass gelé **sans champ** donne à toutes ses instances la même valeur et le
même hash :

```python
ContractStubBond() == ContractStubBond()   # True
forgerie in registre_des_bonds_emis        # True dès qu'un seul vrai bond y figure
```

Autrement dit, avec le stub tel qu'écrit, H3 passerait au vert **sans rien
vérifier**. L'identité d'objet n'est donc pas une préférence d'implémentation :
c'est la condition pour que l'invariant morde. `test_bond_identity_is_required_for_h3`
démontre les deux comportements côte à côte.

Conséquence assumée : un bond est un **jeton**, pas une valeur. La pureté de
l'oracle porte sur le verdict — mêmes entrées, même réponse — pas sur l'identité
de l'objet émis.

### 5.2 `deepcopy` transformait les liaisons en contrefaçons

Copier un `ConstructionState` — le réflexe même du backtracking, que le contrat
encourage — recréait chaque bond hors du registre : H3 échouait sur un état
pourtant légitime. Corrigé : `__copy__` et `__deepcopy__` d'un jeton immuable
retournent l'objet lui-même.

### 5.3 `pickle` ressuscitait un bond hors oracle, silencieusement

Corrigé : `__reduce__` refuse, avec un message qui renvoie vers
`bfk001.serialization` — sérialiser les pièces, laisser l'oracle ré-émettre les
liaisons.

### 5.4 Le graphe acceptait des fictions structurelles

`ConstructionGraph` acceptait une arête vers une pièce **non déclarée**, une
boucle d'une pièce sur elle-même, une arête dupliquée, une arête **sans aucune
liaison**, et des identifiants de pièces dupliqués. H4 et H5 pouvaient donc se
prononcer sur une connexité qui n'existait pas. Corrigé : les cinq cas lèvent à
la construction.

### 5.5 Les invariants ignoraient silencieusement une pièce sans géométrie

`check_h2_collision` et `check_h6_foundation` sautaient les pièces absentes de
`geometries` : un oubli de l'appelant produisait un invariant **vert qui ne
voulait rien dire**. C'est exactement ainsi qu'un validateur cesse d'être utile.
Corrigé : `KeyError` explicite nommant les pièces manquantes.

### 5.6 L'oracle échouait au-delà de ~1e154 LDU

ℤ³ n'est pas borné, mais `math.sqrt()` sur un entier Python trop grand lève
`OverflowError` — le contrat promettait une exactitude que l'implémentation ne
tenait pas à grande échelle. Corrigé par un écartement **entier exact** avant
tout flottant : si `isqrt(d²) > ceil(tolérance)`, la distance dépasse la
tolérance sans ambiguïté. Verdict identique, portée totale.

### 5.7 Une tolérance infinie était acceptée

Elle connecterait tout à tout et faisait exploser `ceil(inf)` dans la recherche
accélérée. Corrigé : `ConnectorTolerance` exige des réels finis.

### 5.8 H2 payait la transformation de tous les vides pour rien — 17× trop lent

L'algorithme F.5 transforme les vides dès l'étape 1, alors qu'ils ne servent
qu'à l'étape 5. Une paire `DISJOINT` ou `TOUCHING` — l'immense majorité dans un
modèle réel — payait donc des centaines de transformations de coins inutiles.
Les vides sont désormais transformés **à la demande**, uniquement en cas
d'`OVERLAPPING`. Écart d'ordre, aucun écart de sémantique : les 63 tests sont
inchangés.

| Mur de briques 2×2 | H2 avant | H2 après |
|---|---:|---:|
| 36 pièces | 0,184 s | 0,010 s |
| 144 pièces | 0,858 s | 0,040 s |
| 400 pièces | 2,477 s | **0,144 s** |

### 5.9 Mesures actuelles et limite restante

Sur un mur de 400 briques 2×2 : assemblage complet 14 ms, recherche accélérée
26 ms, H2 144 ms. **La recherche n'est plus le facteur limitant.**

Ce qui l'est : la **pose incrémentale**, à 4,7 ms par pose sur 154 pièces, soit
un coût linéaire en taille du modèle — donc quadratique pour construire un
modèle entier. `add_part` relance la recherche sur tout l'assemblage puis filtre
sur la pièce ajoutée. Le correctif nommé : un index persistant **au niveau des
connecteurs** (survivant d'une pose à l'autre), et une extension du protocole
`SearchApproximation` du type `pairs_involving(part_id, …)`. Ce n'est pas une
optimisation à bricoler dans un coin : elle touche une frontière d'autorité, et
mérite d'être décidée, pas improvisée.

### 5.10 Seconde passe adversariale — cinq défauts de plus

| Défaut | Conséquence réelle | Correction |
|---|---|---|
| Une pièce démesurée **figeait** `GridSpatialIndex` (insertion > 60 s, non terminée) | H2 se bloque sur un modèle contenant une pièce anormale | Au-delà de 4096 cellules, la pièce est tenue hors grille et testée exactement à chaque requête. Exhaustivité préservée dans les deux branches. |
| `PlacedPart` acceptait deux **connecteurs identiques** | La même liaison comptée deux fois dans le graphe | Rejeté à la construction |
| `bill_of_materials` omettait silencieusement une pièce sans identité | Liste de course incomplète — se paie en pièces manquantes le jour du montage | Garde-fou `placed_parts` : `KeyError` nommant les pièces sans référence |
| **Référence catalogue fausse** : `3021` étiquetée « Plate 2 x 4 » | On commande 3021, on reçoit des plates 2×3 | 3021 = Plate 2×3, ajout de 3020 = Plate 2×4 et 3024 = Plate 1×1. Erreur héritée du document de réflexion produit, qui inversait les deux. |
| H2 retransformait la géométrie monde de chaque pièce **à chaque paire** | 11 s pour valider un LEGO Art 48×48 | `world_geometry()` + `collide_world()` : la transformation sort de la boucle, sans quitter l'autorité collisionnelle. **10,97 s → 2,76 s** |

Le tirage aléatoire de conformité a également été rendu réaliste : deux tiers
des pièces sont désormais posées sur la face supérieure d'une pièce déjà
placée. Un générateur uniforme ne produisait presque aucune liaison — il
testait H1 sur des états sans bond, donc sur rien.

---

## 6. Où en est-on de la demande produit

> photo → modélisation LEGO Art hyper précise → liste de course → notice de montage

La chaîne **existe et tourne** : `python3 demo_lego_art.py photo.png --studs 48`.

| Étape | État | Ce qui manque |
|---|---:|---|
| Photo → analyse | **~70 %** | Lecture PNG/PPM et rééchantillonnage par moyenne de bloc, quantification en CIE L\*a\*b\*. Manquent : tramage (dithering), cadrage assisté. |
| → modélisation LEGO Art | **~70 %** | Solveur mosaïque + substrat croisé, validé H1–H6 à l'échelle officielle. Manquent : fusion des tuiles en plates plus grandes (coût), découpe multi-plaques, et tout le volume 3D. |
| → liste de course | **~55 %** | Nomenclature agrégée, export CSV, garde-fou anti-omission. Manquent : import catalogue réel, palette complète, export BrickLink, prix. |
| → notice de montage | **~30 %** | Plan acyclique, ordre physiquement exécutable, regroupement par couleur, rendu texte. Manquent : vues isométriques, PDF, ligne graphique LEGO. |

**Environ 55 % de la demande.** Le bond depuis les ~15 % precedents n'est pas un
tour de passe-passe : la demande est du LEGO **Art**, donc un probleme 2D. Le
volume 3D — de loin le plus lourd — n'en fait pas partie.

Ce qui reste est domine par deux choses tres differentes : du **rendu
graphique** pour la notice, et de la **donnee reelle** (palette officielle,
catalogue, prix). Aucune des deux n'est un probleme d'architecture.

### 6.1 Mesures de bout en bout

Photo 256×256 → mosaïque 48×48 (format LEGO Art officiel) :

| Étape | Résultat |
|---|---|
| Modèle | 2917 pièces (2304 tuiles + substrat), 4608 liaisons |
| Génération | 0,40 s |
| Validation H1–H6 | 4,90 s, **0 violation** |
| Liste de course | 10 références, instantanée |
| Notice | 126 étapes, DAG validé |
| Document `.json` | 1,15 Mo (9,6 Mo avant mise en facteur des géométries) |

Le modèle n'est **écrit que s'il passe les six invariants**. Une mosaïque qui ne
tiendrait pas ensemble n'est pas livrée — c'est tout l'intérêt d'avoir bâti le
noyau d'abord.

### 6.2 Ce que la mosaïque a révélé sur la demande elle-même

Une mosaïque naïve — les tuiles posées côte à côte sur le plan, exactement ce
que produit un « pixel art → briques » — passe H2, H4 et H6 sans un seul
défaut, **et n'est pas un objet** : 64 tuiles, 64 composants séparés. Seul H5
le voit. Le solveur impose donc un substrat de deux couches de plates croisées,
et c'est vérifié à chaque génération.

### 6.3 Les limites honnêtes de ce qui est livré

- **Palette provisoire de 12 couleurs**, recopiées à la main — le même geste qui
  avait produit l'erreur 3021. `load_ldconfig()` importe la palette officielle
  en une ligne ; tant qu'elle n'est pas fournie, la finesse du rendu est
  plafonnée par la palette, pas par l'algorithme.
- **Pas de tramage** : les dégradés se posterisent. C'est visible sur l'aperçu.
- **Substrat non optimisé** : un pavage plein de plates 2×4. Un solveur de coût
  choisirait mieux.
- **Notice sans images.** La structure est juste, le rendu graphique reste à faire.

### 6.4 Le chemin le plus court pour la suite

1. **Importer LDConfig.ldr et un vrai catalogue** — débloque d'un coup la qualité du rendu et la justesse de la liste de course.
2. **Tramage Floyd-Steinberg** contraint à la palette — le plus gros gain visuel pour le plus petit effort.
3. **Rendu de la notice** — vues isométriques par étape ; c'est du rendu 3D, pas de la CAO.

---

## 7. Ce qu'un solveur devra respecter

Pour que la couche 2 se branche sans rouvrir le noyau :

1. Ne jamais construire un `PhysicalBond` — seul `evaluate_connector_pair` en émet, et H3 le vérifie.
2. Appeler `evaluate_placement` avant de poser, `add_part` pour poser : jamais reconstruire un `ConstructionGraph` à la main.
3. Passer une `ConnectorTolerance` explicite à chaque appel — il n'existe aucune valeur par défaut, et c'est voulu.
4. Utiliser `LatticeSearchApproximation` en production, la référence O(n²) en test de conformité — et vérifier P ⊆ C_fast, jamais C_ref ⊆ C_fast.
5. Ne pas sérialiser de liaisons : un document porte des pièces, l'oracle porte le jugement.
