# BFK-001 — Registre des zones d'ombre

Ce document existe pour qu'il n'y ait **aucune ambiguïté résiduelle** : chaque
zone est soit fermée (avec la preuve), soit ouverte et nommée précisément, avec
la décision qui manque et qui doit la prendre. Rien n'est laissé implicite.

Version du noyau : **BFK-001 v3.3.2** — 87 tests verts, chaîne complète photo → notice.

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

### 5.11 Troisième passe — la qualité du rendu, mesurée puis corrigée

Cette passe portait sur ce qui plafonne le résultat : la fidélité. Elle a
produit un instrument, une erreur de méthode, et une réfutation par la physique.

**L'instrument.** `fidelity()` mesure l'écart perçu en ΔE CIE76 entre la
mosaïque et l'image. Sans lui, « rendu fidèle » n'est qu'une opinion.

**L'erreur de méthode.** L'instrument a d'abord condamné le tramage : ΔE 33,3
sans, 45,5 avec. Normal — je mesurais tuile à tuile, or le tramage rend chaque
tuile *délibérément* fausse pour que le voisinage soit juste. J'ai donc ajouté
une distance de regard, et le verdict s'est inversé : sur un visage, à trois
tuiles de distance, 21,7 → **6,1**. Tout indiquait qu'il fallait l'activer.

**La réfutation.** Un tenon fait 8 mm ; l'œil sépare une minute d'arc. Deux
tuiles voisines ne se confondent qu'à **55 mètres** — une toile de 38 cm vue
depuis l'autre bout d'un terrain de football. La distance de regard qui rendait
le tramage gagnant n'existe pas. À distance humaine (`blending_tiles(1,5 m) = 1`),
la quantification directe gagne partout : 13,4 contre 16,1 ΔE. Et l'image le
confirme sans appel — le tramage damier le fond et mouchette le visage.

Le défaut est donc `dither=False`, et la raison est écrite dans le code sous
forme exécutable (`blending_tiles`), pas en commentaire. Le tramage reste
disponible : il redevient juste dès que la maille passe sous le pouvoir
séparateur de l'œil.

**Un critère adaptatif réfuté en chemin.** La première version pondérait le
tramage par le contraste local de l'image. La mesure l'a réfutée : un aplat
gris-vert parfaitement uniforme gagnait énormément au tramage. La raison est
évidente après coup — ce qui appelle le tramage n'est pas que l'image varie,
c'est que la couleur voulue **n'existe pas dans la palette**. Le critère est
donc l'erreur de quantification. Corrigé, l'adaptatif devient le meilleur ou à
égalité partout à distance de fusion, et bat les deux stratégies pures sur une
image mixte (5,9 contre 8,4 et 12,3).

### 5.12 Quatrième passe — l'échelle d'une vraie photo

| Défaut | Mesure | Correction |
|---|---|---|
| Un tuple par pixel : **24× la place utile** | Une photo de 12 Mpx demandait ~860 Mo | `Image` stocke des `bytes` : **36 Mo**. C'est la différence entre un outil qui marche et un processus tué par le système. |
| Décodage PNG pixel par pixel | 5,9 s pour 4,3 Mpx | Extraction des canaux par tranches (niveau C), `bytes.translate` pour les palettes, Paeth déroulé sur place : **0,04 s** sur filtre 0, **3,35 s** sur Paeth |
| **Trou de couverture** : mon encodeur n'émet que le filtre 0 | Je testais mon décodeur sur un cinquième du format — et pas celui des appareils photo | Test des cinq filtres, au bit près |
| Le catalogue enrichi a rendu la suite **6× plus lente** | Une plate 16×16 apporte 512 connecteurs, et l'audit H1 est quadratique en connecteurs, par conception | Le tirage aléatoire est borné en connecteurs. L'audit garde sa rigueur ; c'est l'état tiré qui est borné. |

**Plancher assumé** : décoder une photo de 12 Mpx filtrée en Paeth coûte ~9 s en
Python pur. C'est incompressible sans extension C. Je n'ai pas ajouté de chemin
rapide optionnel via Pillow : je ne peux pas le tester ici, et livrer du code
non vérifié serait contraire à tout le reste.

### 5.13 Le substrat : le noyau arbitre, il ne suggère pas

| Substrat | Pièces de fond (48×48) | Verdict du noyau |
|---|---:|---|
| `crossed` — deux couches de plates 2×4 croisées, rognées | 657 | **0 violation** : l'objet tient tout seul |
| `panels` — plates 16×16, celles des sets officiels | 9 | **2056 violations H5** : neuf îlots séparés |

Soixante-huit fois moins de pièces, et un objet en neuf morceaux. Les sets LEGO
Art officiels tiennent par leur **cadre**, qui n'est pas une pièce structurelle
et n'est pas modélisé. Le noyau refuse de certifier ce qu'un cadre absent est
censé tenir — c'est exactement son rôle.

### 5.14 Cinquième passe — l'épreuve d'une vraie photo

Une photo réelle a fait tomber trois hypothèses d'un coup.

**Le format.** Les appareils produisent du JPEG, pas du PNG. Aucune
bibliothèque n'étant disponible, le format est décodé en Python pur — mais avec
une idée qui change l'échelle du problème : **le premier coefficient de chaque
bloc 8×8, le DC, est déjà la moyenne du bloc.** Une mosaïque de 48 tenons à
partir d'une photo de 4000 pixels ne demande que des moyennes. Le décodeur ne
reconstruit donc aucun pixel : il lit les coefficients, ne garde que le DC, et
sort directement une image au huitième. Pas de transformée inverse, pas de
12 millions de pixels fabriqués pour en jeter 99,99 %.

**L'orientation.** La photo était en portrait, stockée couchée, redressée par
un champ EXIF. Sans lui, la mosaïque sort à 90°. Aucun utilisateur ne pardonne
ça, et aucun appareil n'écrit les pixels dans le bon sens.

**Le test.** Le décodeur est vérifié contre un encodeur JPEG minimal écrit pour
l'occasion, qui ne produit que des blocs unis — précisément le domaine où un
décodeur DC doit être exact au bit près. Il l'est. La photo personnelle de
l'utilisateur n'a pas été versée au dépôt comme fixture.

### 5.15 Le diagnostic qui réordonne toute la feuille de route

Sur cette photo, le rendu était méconnaissable : ciel gris, phare brun. Trois
causes possibles se confondaient — palette, résolution, cadrage. Elles ont été
**séparées par la mesure**, en comparant la palette LEGO disponible à la
meilleure palette de 12 couleurs *possible* pour cette image (k-moyennes) :

| Résolution | Palette LEGO (12) | Palette idéale (12) |
|---|---:|---:|
| 48 × 64 | 17,8 ΔE | **4,6 ΔE** |
| 96 × 128 | 17,9 ΔE | 4,7 ΔE |
| 144 × 192 | 18,0 ΔE | 4,9 ΔE |

**Sur 17,8 d'écart, 13,2 viennent de la palette et 4,6 de la résolution.** Et
tripler la résolution ne change rien — strictement rien. Ajouter des tuiles est
inutile tant que les couleurs sont fausses.

Ce n'était pas une intuition : c'était vérifiable, et ça réordonne la feuille de
route. Le rendu final le montre à l'œil — mêmes 48×64 tenons, même algorithme,
même nombre de couleurs, seul le choix des douze change.

**Ce que le produit en fait.** `gap_report()` nomme désormais ce qui manque :
« 12,3 % des tuiles veulent #A6C2E5 ; votre palette n'a que du Light Bluish Gray
à 20 ΔE ». La CLI l'affiche **avant** de construire, et qualifie le résultat
(« palette insuffisante »). `Palette.best_subset()` choisit, dans une palette
riche, les N couleurs qui servent le mieux une image donnée — car une mosaïque
ne se commande pas en soixante-dix couleurs.

**Ce que je n'ai pas fait, et pourquoi.** Je n'ai pas ajouté à la main les
couleurs manquantes. J'ai les valeurs de plusieurs d'entre elles en tête, et
c'est exactement le geste qui avait fait étiqueter la référence 3021 « Plate
2×4 ». `load_ldconfig()` importe la palette officielle en une ligne ; c'est la
seule voie que je certifie.

### 5.16 La palette était accessible — je ne l'avais jamais vérifié

J'avais déclaré la palette officielle hors d'atteinte et refusé de la recopier
de mémoire. La deuxième moitié était juste ; la première était une **hypothèse
non testée**. `ldraw.org` est bien bloqué par le proxy, mais PyPI est
directement accessible — l'environnement l'autorise explicitement — et le
paquet `pyldraw` embarque le `LDConfig.ldr` officiel. **162 couleurs obtenues
de la source, pas de la mémoire.**

**Contre-vérification de mes douze valeurs recopiées :** onze exactes au bit
près, une fausse — Green valait #237841 au lieu de #257A3E, soit 2,8 ΔE. Ma
prudence était donc proportionnée, et la discipline a payé : j'avais une
supposition à 92 %, j'ai maintenant la donnée.

**Un bug attrapé dans la foulée.** `solids_only()` laissait passer les codes 16
et 24. Ce ne sont pas des couleurs mais des marqueurs du format LDraw —
« couleur courante » et « couleur des arêtes ». Rien dans le fichier ne les
distingue, et la sélection automatique avait retenu « Edge Colour » pour la
mosaïque. Une liste de course incommandable.

**Le gain, mesuré :**

| Palette | Couleurs | Fidélité |
|---|---:|---:|
| Mes 12 recopiées à la main | 12 | 17,8 ΔE |
| Officielle, commandables | 80 | 9,7 ΔE |
| Officielle, **12 mieux choisies** | 12 | **9,7 ΔE** |

Douze couleurs bien choisies valent les quatre-vingts. Ce n'est pas une
économie marginale : c'est douze sachets au lieu de quatre-vingts.

### 5.17 Le phare rose : deux hypothèses réfutées, et une leçon

Sur le rendu officiel, le phare ressortait rose. J'ai formulé deux explications
et je les ai testées toutes les deux.

**Hypothèse 1 — le critère sacrifie les petits sujets.** La sélection minimise
l'écart *moyen* ; le ciel occupe 40 % des tuiles, le phare 2 %. J'ai donc ajouté
un critère minimax, qui minimise le *pire* écart. Résultat mesuré : **13,1 ΔE
contre 9,7**, et le pire écart strictement inchangé. Le réglage a été **retiré**
— un critère qui ne gagne nulle part ne mérite pas d'exister.

**Hypothèse 2 — c'est la résolution.** Testé à 96×128 et sur un recadrage serré
du sujet : **aucune tuile rouge dans les deux cas**, et le rouge n'entre même
pas dans la palette sélectionnée.

**La réalité.** Les pixels les plus rouges de la photo valent (186, 88, 99) —
un rose poussiéreux. Les pixels franchement rouges représentent **0,16 % de
l'image, soit 4,8 tuiles sur 3072**. Le phare est contre-jour, sa bande rouge
est dans l'ombre, et à 48 tenons de large elle occupe cinq tuiles roses.
**La mosaïque est fidèle. C'est mon souvenir de la scène qui ne l'était pas.**

C'est la leçon la plus utile de la session : j'étais à un pas de biaiser
l'algorithme vers ce que je *croyais* voir plutôt que vers ce que la photo
contient. C'est exactement ainsi qu'un outil se met à mentir.

### 5.18 Un filtre écrit, testé — et jamais branché

La liste de course finale contenait 592 tuiles de « Chrome Antique Brass »,
249 de « Rubber Black » et 486 de « Trans Light Blue Violet ». `solids_only()`
existait, passait ses tests, et n'avait jamais été appelé par la CLI.

Le genre de défaut que seul l'usage révèle : chaque pièce fonctionnait, et la
chaîne était fausse. Corrigé, la liste ne contient plus que des couleurs
opaques réellement disponibles en tuile 1×1.

---

### 5.19 La notice : une page par étape aurait donné 733 pages

`plan_build` regroupe les pièces par **couleur** à chaque niveau. C'est le bon
regroupement pour un assemblage : on ne change pas de sachet vingt fois. Pour
une mosaïque, c'est catastrophique, et la mesure le dit sans appel :

| Mosaïque 48×48 | Mesure |
|---|---:|
| Pièces | 2917 |
| Étapes produites par `plan_build` | **733** |
| Étapes du type « poser 4 tuiles rouges » | la quasi-totalité |

Ces quatre tuiles rouges sont dispersées dans une grille de 2304 cases. Une
notice d'une page par étape ferait chercher quatre cases parmi 2304, cinq cents
fois de suite. Le plan est **physiquement juste** et **pratiquement inutilisable
tel quel comme mise en page**.

Les notices LEGO Art officielles procèdent autrement, et elles ont raison :
**ligne par ligne**, de haut en bas, avec le compte des tuiles consécutives de
chaque couleur — « 5 gris foncé, 9 vert, 4 gris foncé ». Une suite se compte,
quarante-huit cases se recomptent.

`booklet.py` sépare donc les deux autorités :

- le **plan** reste l'autorité sur ce qui *peut* être posé quand ;
- le **fascicule** choisit seulement dans quel *ordre*, parmi les ordres permis ;
- `_verifier_ordre` confronte l'ordre choisi aux dépendances du plan et **refuse
  de produire le PDF** s'il en viole une. Le rendu n'a pas le droit de casser la
  physique, et ce n'est pas une intention : c'est vérifié.

Résultat mesuré sur la même mosaïque : **16 pages, 125 Ko, 0,5 s** — contre 733.

### 5.20 Trois défauts trouvés en regardant les pages, pas le code

Le PDF passait toutes les vérifications structurelles avant qu'aucune de ces
trois erreurs ne soit visible. Elles ne sont sorties qu'en **regardant les
images produites**.

1. **La page « couche 2 » du fond ne montrait rien.** La seconde couche de
   plates recouvre intégralement la première ; la dessiner par-dessus effaçait
   exactement ce que la page devait transmettre — le **décalage** entre les deux
   couches, qui est la seule raison pour laquelle le fond tient. Corrigé en
   retraçant les *joints* de la couche du dessous par-dessus la couche du
   dessus.

2. **Le cadre de la bande en cours mangeait les tuiles de bord.** Un trait noir
   de 2 px tracé *dans* la bande recouvrait 15 % de la première et de la
   dernière ligne — c'est-à-dire la couleur à poser. Les traits de délimitation
   sont désormais posés **hors** de la bande, et toute réglure tracée *dans* la
   mosaïque **assombrit** au lieu de peindre : la couleur reste lisible dessous.
   Un test vérifie l'invariant — dans la bande en cours, tout pixel est la
   couleur exacte de sa tuile, ou cette couleur assombrie par une ou deux
   réglures, jamais autre chose.

3. **« Déjà posé » et « reste à poser » se confondaient.** Le déjà-posé était
   rendu en couleur pâlie, le reste en gris clair uniforme. Là où l'œuvre est
   grise — un ciel couvert, une façade — les deux étaient indiscernables. La
   pâleur seule ne peut pas porter cette distinction. Ce qui reste à poser est
   maintenant **damié**, motif qui n'est la couleur d'aucune tuile et ne peut
   donc pas être lu comme une consigne.

### 5.21 La mise en page ne peut pas être fixée d'avance

Une bande de 4 lignes tient sur une page pour une photo (« 48 Blue » : une
suite), pas pour une image bruitée (48 suites par ligne, ~9 lignes de texte).
Fixer 4 lignes par page fait déborder la lecture hors de la feuille — et une
ligne de notice qui déborde est une ligne de tuiles perdue.

La lecture est donc produite **avant** la mise en page, et c'est elle qui
commande : `_decouper_bandes` n'ajoute une ligne à la bande que si la lecture
tient encore, et la vue se dimensionne sur la place restante. Pour le cas
extrême où une seule ligne ne tiendrait pas — mosaïque très large et très
bruitée —, la lecture continue sur une page de suite plutôt que d'être tronquée.
Tronquer aurait perdu des tuiles silencieusement.

### 5.22 Le substrat débordait de l'œuvre — et le corriger a cassé le fond

Rendre la couche de fond a révélé autre chose. Pour une mosaïque 48×48 :

| Couche | Emprise (LDU) | Emprise de la mosaïque |
|---|---|---|
| z = 0 | x 0…960, y 0…960 | x 0…960, y 0…960 |
| z = 8 | **x −20…980, y −40…1000** | idem |

La seconde couche, décalée d'un tenon en x et de deux en y pour croiser la
première, **dépasse de 1 tenon en x et de 2 en y sur chaque bord**. L'œuvre finie
porte donc un liseré de plate grise nue tout autour — visible, et payé en
pièces. Le décalage est nécessaire ; le débordement ne l'est pas : les cellules
de bord peuvent être remplies par des plates plus courtes (2×2, 2×3, 1×2, 1×1),
toutes au catalogue.

**Corrigé — mais pas du premier coup, et l'échec est plus instructif que le
correctif.**

Premier essai : rogner les cellules qui débordent et remplir le rectangle
restant de plates plus courtes. Emprise exacte, et **H5 refuse le modèle pour
toutes les tailles impaires**. Cause : au coin, les deux couches se réduisent
chacune à une plate 1×1, superposées ; une 1×1 ne chevauche rien, donc elle ne
relie rien, et les trois pièces — plate du bas, plate du haut, tuile — forment
une tour détachée du reste.

Deuxième essai : fondre un reste d'un seul tenon dans la cellule voisine, pour
n'avoir plus aucune cellule de largeur 1. **Pire : H5 refuse *toutes* les
tailles.** Fondre replace les plates sur la phase de la couche du dessous. Or
c'est le **décalage** qui fait tenir le fond : sans lui, chaque colonne de la
couche 0 n'est reliée qu'à elle-même, et le fond se scinde en bandes
indépendantes. On ne touche pas à la phase du décalage.

Correctif retenu : garder le réseau nu, et **phaser la décomposition des
colonnes d'un tenon de large**. Une plate 1×2 n'enjambe un joint de la couche
du dessous — aux multiples de 4 tenons — que si elle commence sur un tenon
**impair**. Les cellules de la couche décalée commencent à 4k+2, donc toujours
sur un tenon pair : leurs 1×2 s'arrêtent pile sur les joints au lieu de les
enjamber. Une 1×1 en tête re-phase la colonne, et tout le reste enjambe.

| Variante | Échecs sur 1521 formats (2×2 à 40×40) |
|---|---:|
| Réseau nu, 1×1 en fin de colonne | 507 |
| Réseau nu, 1×1 en tête si profondeur impaire | 59 |
| Fusion des restes | 1222 |
| **Réseau nu, 1×1 en tête selon la phase absolue** | **0** |

Vérifié ensuite sur les six invariants du noyau pour toutes les tailles de 2×2
à 33×33, plus 40×40 et 48×48 : emprise exacte, zéro violation. Coût : 657
pièces de fond au lieu de 625 à emprise égale — et plus de liséré.

C'est une vérification **exhaustive sur le domaine praticable**, pas une preuve.
Elle est écrite comme telle.

---

## 6. Où en est-on de la demande produit

> photo → modélisation LEGO Art hyper précise → liste de course → notice de montage

La chaîne **existe et tourne** : `python3 demo_lego_art.py photo.png --studs 48`.

| Étape | État | Ce qui manque |
|---|---:|---|
| Photo → analyse | **~85 %** | JPEG (décodé au huitième), PNG, PPM, orientation EXIF, rééchantillonnage par moyenne, quantification CIE L\*a\*b\*. Manque : cadrage assisté. |
| → modélisation LEGO Art | **~80 %** | Solveur + substrat validé H1–H6, palette officielle importable, sélection des N meilleures couleurs, diagnostic des manques. Manque : découpe multi-panneaux, fusion de tuiles, volume 3D. |
| → liste de course | **~75 %** | Nomenclature exacte, filtrée aux couleurs commandables, garde-fou anti-omission, export CSV. Manque : export BrickLink, prix, disponibilité. |
| → notice de montage | **~75 %** | Plan acyclique, PDF autonome (couverture, liste de course avec pastilles, pose du fond, mosaïque bande par bande avec réglettes et comptage des suites), ordre vérifié contre le plan. Manque : ligne graphique LEGO, repérage de la pièce de départ. |

**Environ 79 % de la demande.** Le bond depuis les ~15 % initiaux n'est pas un
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
- **Notice en vue de dessus seulement.** C'est le bon choix pour une mosaïque
  — une perspective n'ajouterait rien à une œuvre plate — mais un assemblage
  en volume demanderait autre chose.

### 6.4 Le chemin le plus court pour la suite

1. **Importer LDConfig.ldr et un vrai catalogue** — débloque d'un coup la qualité du rendu et la justesse de la liste de course.
2. **Tramage Floyd-Steinberg** contraint à la palette — le plus gros gain visuel pour le plus petit effort.
3. **Export BrickLink / Pick-a-Brick** — la liste de course devient commandable en un clic.

---

## 7. Ce qu'un solveur devra respecter

Pour que la couche 2 se branche sans rouvrir le noyau :

1. Ne jamais construire un `PhysicalBond` — seul `evaluate_connector_pair` en émet, et H3 le vérifie.
2. Appeler `evaluate_placement` avant de poser, `add_part` pour poser : jamais reconstruire un `ConstructionGraph` à la main.
3. Passer une `ConnectorTolerance` explicite à chaque appel — il n'existe aucune valeur par défaut, et c'est voulu.
4. Utiliser `LatticeSearchApproximation` en production, la référence O(n²) en test de conformité — et vérifier P ⊆ C_fast, jamais C_ref ⊆ C_fast.
5. Ne pas sérialiser de liaisons : un document porte des pièces, l'oracle porte le jugement.
