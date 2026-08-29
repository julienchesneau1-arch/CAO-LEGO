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
| **`BuildStep` concret** | **FERMÉE** — dataclass gelée dans `instructions.py` (`step_id`, `part_ids`, `depends_on`, `description`), conforme au Protocol, refusant une étape sans pièce. | — | Fait |
| **Export LDraw (.ldr)** | **FERMÉE** — `bfk001/ldraw.py`. Les deux données manquantes ont été lues dans `3001.dat` officiel, pas devinées (§ 5.39). | — | Fait |
| **Palette couleur complète** | **FERMÉE côté LDraw** — `load_ldconfig()` importe les 162 couleurs officielles, dont 80 solides commandables, avec détection de finition ; recherche automatique dans les emplacements d'installation usuels. Reste ouverte côté **BrickLink** : la correspondance des codes couleur exige une clé d'API Rebrickable, non vérifiable ici (§ 5.40). | Fournir la table de correspondance, ou une clé. | Couche 3 |
| **Catalogue complet** | 8 références rectangulaires générées paramétriquement. | Import LDraw `.dat` → `CollisionGeometry` + connecteurs. Dépend entièrement de 3.1 (géométrie non-AABB). | BFK-002 |
| **Prix, disponibilité, substitution** | Absents. | Hors noyau, et **doit le rester** : un noyau géométrique ne consulte pas un marchand. La contrainte d'approvisionnement, elle, est exprimable : `--codes-couleur` impose la liste réellement en stock. | Couche 3 |
| **Commander la liste** | **FERMÉE côté code** — `bricklink.py` produit la liste de souhaits XML, et refuse plutôt que de deviner une couleur absente de la table (§ 5.40). Ouverte côté **donnée** : la table de correspondance des couleurs n'est pas fournie, aucune n'ayant pu être vérifiée ici. | Fournir la table. | Couche 3 |

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

### 5.23 Quatre défauts de plus, tous trouvés en regardant les pages

Le PDF passait toutes les vérifications structurelles et tous les tests de
débordement. Ces quatre-là ne sont sortis qu'en **rendant les pages en image** —
un aperçu grossier où le texte est figuré par une barre grise, ce qui suffit à
voir les collisions, les trous et l'équilibre.

1. **La couverture montrait l'œuvre délavée.** Elle appelait la vue
   d'avancement avec « toutes les lignes sauf la dernière déjà posées » — or
   cette vue *pâlit* le déjà-posé. La couverture promettait donc une version
   décolorée de ce qu'on allait construire. Elle emploie maintenant
   `mosaic.preview`, qui rend les couleurs pleines.

2. **Un trou de 300 points au milieu des pages de bande.** Le plafond de la vue
   était fixé à 430 pt. Dès que la lecture est courte — c'est-à-dire dès qu'il
   s'agit d'une photo, où « 48 A » tient sur une ligne — le reste de la page
   restait blanc. Le plafond est maintenant plus haut que la largeur utile :
   c'est le rapport de forme qui borne, plus une constante arbitraire.

3. **La réglette des numéros de lignes tombait dans la marge non imprimable.**
   Vue pleine largeur, les numéros se retrouvaient à 25 pt du bord, sous les
   10 mm qu'une imprimante de bureau ne rend pas. Le constructeur aurait perdu
   son seul repère vertical. La vue réserve désormais 20 pt à sa gauche.

4. **Le pied de page et un sous-titre débordaient de la même zone sûre.** Le
   test ne vérifiait que « dans la page », ce qui ne veut rien dire pour un
   document destiné à être imprimé. Il vérifie maintenant les 28 pt (10 mm)
   de marge sûre sur les quatre côtés — et c'est ce durcissement qui a révélé
   les deux défauts.

Au passage, la lecture est passée des noms complets à des **codes courts avec
légende** : « 3 Light Bluish Gray · 5 Dark Bluish Gray » devient « 3A · 5B ».
Les deux noms ne diffèrent que par leur premier mot et se confondent à la
lecture ; les grilles de point de croix emploient des symboles pour exactement
cette raison. Le nom complet reste dans la légende, présente sur **chaque**
page, et dans la liste de course — là où l'on commande. Effet de bord mesuré :
la lecture d'une photo passe de deux lignes à une, ce qui rend la place à la
vue.

---

### 5.24 L'échantillonnage moyennait des logarithmes

La plus grosse erreur systématique de toute la chaîne, présente depuis le
premier jour, invisible à tous les tests.

`resample_box` moyennait les **octets sRGB**. Or sRGB n'est pas une échelle
linéaire : c'est un encodage en puissance ≈ 2,2. Moyenner des octets sRGB
revient à moyenner des logarithmes, ce qui n'a aucun sens physique.

Cas d'école à réponse connue : un damier noir et blanc renvoie exactement 50 %
de la lumière incidente. La valeur sRGB correspondante est **188**. Le code en
donnait **127**, dont la luminance vaut 21 %.

| Bloc | Ancien | Correct | Écart |
|---|---:|---:|---:|
| noir + blanc | 127 | **188** | 23,1 ΔE |
| 0 + 128 | 64 | **92** | 12,0 ΔE |
| 64 + 192 | 128 | **146** | 7,0 ΔE |
| 100 + 160 | 130 | **134** | 1,6 ΔE |

L'erreur est nulle sur les aplats et maximale sur le détail fin à fort
contraste — feuillage, tissu, eau, cheveux, exactement ce qu'une photo contient
en abondance. Elle assombrit **systématiquement** toutes les zones texturées.

Corrigé : on linéarise, on moyenne, on réencode. Deux tables de 256 entrées
(octet fort, octet faible d'une valeur 16 bits) permettent de faire la somme
d'un bloc par `bytes.translate` + `sum`, deux boucles en C ; une table de
retour de 65 536 entrées réencode. Coût mesuré : 0,06 s pour 600×450 → 48×48.

**Le piège qu'il a fallu éviter.** Le centroïde dans L\*a\*b\* minimise l'écart
moyen par tuile — c'est démontrable : Σ‖lab_i − p‖² = Σ‖lab_i − μ‖² + n‖μ − p‖².
Il est donc *optimal* pour ce critère-là. Mais il répond à la mauvaise
question : une grande zone de texture noire et blanche renvoie 50 % de la
lumière, et une tuile à L\*=50 n'en renvoie que 19 %. L'œil ne juge pas une
tuile isolée, il intègre les grandes surfaces — un biais de luminance s'y voit
à toute distance. Mesuré sur les trois méthodes, palette officielle :

| Cible de la tuile | écart/tuile | justesse tonale | tonale au pire |
|---|---:|---:|---:|
| moyenne des octets sRGB | 23,63 | 14,14 | 27,46 |
| **moyenne des radiances** | 24,28 | **7,95** | **15,41** |
| centroïde L\*a\*b\* (optimal par tuile) | 23,68 | 13,87 | 27,46 |

0,65 ΔE de perdu par tuile contre 6,2 ΔE de gagné en justesse tonale, et le
pire cas divisé par deux. Le choix n'est pas discutable.

Noter au passage que la moyenne des octets sRGB et le centroïde L\*a\*b\* donnent
presque le même résultat : les deux sont des compressions en puissance ~1/2,2
et ~1/3. L'ancien code n'était pas « un choix perceptif », c'était un accident
qui ressemblait à un choix.

### 5.25 CIELAB choisissait un violet pour un bleu

`Palette.nearest` utilisait la distance euclidienne dans L\*a\*b\* (ΔE 1976).
L\*a\*b\* n'est pas aussi uniforme qu'annoncé, et sa **région bleue** est
notoirement distordue.

Mesure sur la palette officielle, pour `#005AB4` — un bleu franc :

| Choix | ΔE76 | Lab |
|---|---:|---|
| Violet `#4354A3` | **10,13** ← choisi | (38,2 · 18,0 · −44,9) |
| Blue `#0055BF` | 10,81 | (38,3 · 21,2 · −61,3) |

`#005AB4` et `#0055BF` sont quasiment la même couleur. CIE76 préférait le
violet, de 0,68 ΔE. Sur quatorze bleus testés, **aucun** n'obtenait une couleur
nommée « Blue ». Pour une photo, où le ciel est la plus grande surface bleue,
c'est le pire endroit possible pour se tromper.

Corrigé en passant à **CIEDE2000**, la métrique recommandée par la CIE. Son
terme de rotation `RT` est centré sur H = 275°, c'est-à-dire exactement sur les
bleus : la CIE avait constaté la même distorsion.

**Le piège de circularité.** Juger ΔE76 avec ΔE76 ne prouve rien. J'ai donc
essayé OKLab (conçu pour les grands écarts et la linéarité des teintes) et pris
CIEDE2000 comme **arbitre** — elle n'est ni l'une ni l'autre :

| Métrique de choix | ΔE2000 moyen, RVB uniforme | sur les tuiles d'une photo |
|---|---:|---:|
| CIELAB ΔE76 | 9,77 | **7,24** |
| OKLab | **9,18** | 8,52 |
| CIEDE2000 | 8,43 | 7,08 |

Les deux jeux se contredisent sur OKLab : impossible de trancher entre ΔE76 et
OKLab honnêtement. CIEDE2000 domine les deux sur la moyenne **et** sur le pire
cas (30,0 → 16,7 en RVB uniforme), et c'est le standard. C'est elle.

**Ce qu'elle n'apporte pas.** En agrégat sur une vraie image, le gain est
marginal : 17,00 → 16,97 ΔE par tuile. Sa valeur est ailleurs — dans les échecs
ponctuels et visibles, un bleu de ciel rendu violet. Une tuile franchement
fausse dans un visage coûte plus cher que dix tuiles légèrement décalées.

**Le coût est nul.** 0,71 s pour 2304 tuiles × 80 couleurs, contre 0,76 s pour
l'ancienne implémentation de CIE76 : la conversion sRGB → L\*a\*b\* de la cible,
sortie de la boucle et mise en cache, payait déjà plus cher que la formule.

### 5.26 Effet des deux corrections, bout en bout

Mesuré en CIEDE2000, palette officielle 80 solides, mosaïque 48×48 :

| | écart/tuile | tonale moyenne | tonale au pire |
|---|---:|---:|---:|
| avant (octets sRGB + CIE76) | 17,00 | 11,19 | 24,35 |
| + lumière linéaire | 17,84 | 5,36 | 9,12 |
| + CIEDE2000 seul | 16,97 | 11,05 | 24,35 |
| **après (les deux)** | 17,80 | **6,02** | **9,12** |

**Erreur tonale au pire divisée par 2,7.** À l'œil, sur une bande de test :
le tissu rayé noir/blanc passait d'un gris-olive sombre à un gris clair juste ;
le feuillage d'un vert plat trop sombre à un vert lumineux texturé ; l'eau d'un
indigo plat à un bleu avec ses reflets.

### 5.27 La palette officielle est cherchée, pas embarquée

`LDConfig.ldr` — 162 couleurs, dont 80 solides commandables — divise l'écart
par deux : 14,2 → 7,7 ΔE par tuile sur la même photo.

Le fichier **n'est pas** dans ce dépôt. Il appartient à LDraw.org et se
distribue sous CCAL 2.0, qui autorise la redistribution avec attribution — mais
qui définit l'œuvre par une ligne `0 !LICENSE Redistributable under CCAL
version 2.0` que **LDConfig.ldr ne porte pas**. L'ambiguïté n'est pas
tranchable ici, et redistribuer un fichier dont on ne peut pas établir la
licence est une décision qui appartient au propriétaire du dépôt, pas à moi.

`find_ldconfig()` le cherche donc aux douze emplacements où LDraw, LeoCAD et
BrickLink Studio le déposent. Quiconque construit vraiment en LEGO l'a déjà sur
son disque et n'a aucun drapeau à fournir. À défaut, la palette provisoire sert,
et le dit — une palette silencieusement dégradée est pire qu'une palette
absente.

**Limite honnête restante.** Les 80 couleurs « solides » du fichier officiel ne
sont pas toutes disponibles en **tuile 1×1 (3070b)**. Le fichier ne contient
aucun signal exploitable : les 80 portent toutes un `LEGOID` — vérifié, il n'en
manque aucune. La disponibilité par référence est une donnée commerciale que ce
dépôt n'a pas, et elle n'est pas devinée.

### 5.28 Le tramage : une décision renversée, puis re-renversée

Le registre notait le tramage comme **rejeté**, sur un argument de physique :
un tenon fait 8 mm, deux tuiles ne fusionnent qu'à 55 m, donc à toute distance
réelle l'œil voit le damier et le rendu se dégrade.

Ayant établi en § 5.42 que **la justesse tonale prime sur l'écart par tuile**,
la cohérence obligeait à rouvrir la question avec le bon critère.

| image | variante | par tuile | tonal | tonal pire | couleurs |
|---|---|---:|---:|---:|---:|
| ciel | aucun | 6,17 | 5,64 | 7,29 | 6 |
| ciel | adaptatif | 6,40 | **4,71** | **6,69** | 7 |
| ciel | Floyd-S complet | 9,15 | **1,99** | 5,49 | 19 |
| paysage | aucun | 7,68 | 5,55 | 12,42 | 13 |
| paysage | adaptatif | 8,32 | **3,76** | **7,77** | 15 |
| paysage | Floyd-S complet | 11,29 | **2,76** | 10,11 | 28 |

**Floyd-Steinberg complet donne le meilleur chiffre tonal de la table et perd à
l'œil, sans appel** : il transforme un ciel en neige, avec des tuiles roses,
beiges et grises éparpillées dans du bleu, et il criblait le cercle rouge du
paysage de points roses. C'est le rappel qu'aucune de ces mesures ne remplace le
fait de regarder. Rejeté.

**L'argument de physique était juste, mais il comparait au mauvais témoin.** Il
opposait le tramage à « rien ». L'alternative réelle n'est pas « rien », c'est
une **bande à bord franc** — et l'œil est plus sensible à un bord qu'à du grain,
la détection de contours étant son opération de base. Le tramage adaptatif
n'échange donc pas « propre » contre « bruité » : il échange un bord saillant
contre une transition diffuse, et seulement là où la palette ne sait vraiment
pas produire la couleur.

Défaut changé en `"adaptive"`. Bout en bout, palette officielle, même photo :
erreur tonale au pire **12,4 → 7,8**, pour **+2 références** à acheter. Floyd
complet, lui, en aurait coûté **+17**.

**Serpentin.** La diffusion parcourt désormais un rang sur deux à l'envers.
Floyd-Steinberg toujours parcouru dans le même sens produit des vermicules
diagonaux, visibles à l'échelle de la tuile. Trois lignes de code : transitions
resserrées, et le nombre de références tombe de 18 à 15 sur le paysage. Jamais
pire, mesuré sur les trois images.

**Piste réfutée.** Pondérer aussi par la **douceur locale**, pour ne tramer que
les dégradés et laisser tranquilles les zones déjà texturées. L'idée paraissait
juste — c'est exactement le critère du tout premier essai, avec le signe
inversé, ce qui expliquait pourquoi il avait échoué. Mesure : **0,1 ΔE d'écart,
dans le bruit**, sur les trois images. Seul effet réel, une liste de course un
peu plus courte (21 → 18 références). Pas assez pour justifier le code.

### 5.29 La chaîne écrasait toute photo non carrée

Le défaut le plus grave trouvé dans cette passe, et le plus simple à voir une
fois qu'on pose la bonne question : **que devient un cercle ?**

Un cercle parfait dans une photo 400×300, quantifié en 48×48 :

| Cadrage | Cercle obtenu | Rapport |
|---|---|---:|
| étirement (ce que faisait la chaîne) | 24 × 32 tenons | **0,750** |
| découpe au bon rapport | 32 × 32 tenons | **1,000** |

`resample_box(image, studs_x, studs_y)` applique le rectangle source au
rectangle cible : il **étire**. Or presque toute photo est en 4:3 ou 3:2, et
presque toute mosaïque LEGO Art est carrée — 48×48, le format des plaques
officielles. La chaîne écrasait donc d'un quart, horizontalement, à peu près
toute photo réelle. Sur un portrait, c'est fatal ; et aucun ΔE ne le voit,
puisque les couleurs, elles, restent justes.

Deux corrections, indépendantes :

- `quantize(..., fit="crop")`, désormais le défaut, découpe la photo au rapport
  de la mosaïque avant de moyenner. `fit="stretch"` reste disponible pour qui
  le veut vraiment. Le remplissage par bandes noires a été écarté : il
  gaspillerait des tuiles sur du vide.
- Le CLI, **sans `--hauteur`, suit maintenant les proportions de la photo** :
  `--studs 48` sur une photo 4:3 donne 48 × 36 tenons, rien n'est rogné ni
  étiré. Demander `--hauteur 48`, c'est demander un carré — et donc un
  recadrage, annoncé comme tel.
- `--cadrage 0..1` déplace la fenêtre de découpe. Le sujet n'est pas toujours
  au centre, et rien ici ne sait où il est : le dire vaut mieux que le deviner.
  Un recadrage attentionnel (détection de saillance) reste hors périmètre.

### 5.30 La sélection des N meilleures couleurs était bridée par son propre proxy

`best_subset` optimise contre un résumé de l'image — `dominant_colors(pixels,
min(24, max(8, count * 2)))`, des k-moyennes en L\*a\*b\*. Ce **plafond de 24
grappes** bridait tout le reste : au-delà de 24 couleurs demandées, le proxy ne
savait plus les distinguer, et le résultat cessait de s'améliorer.

Mesuré sur un dégradé riche (2304 teintes distinctes après réduction) :

| Budget | avant | après |
|---:|---:|---:|
| 8 | 9,08 | 8,94 |
| 16 | 7,34 | 7,30 |
| 24 | 7,26 | **6,89** |
| 32 | 7,26 (aucun gain) | **6,87** |
| 48 | 7,16 | **6,86** |
| 80 (toute la palette) | 6,85 | 6,85 |

**Vingt-quatre couleurs atteignent désormais ce qui en demandait quatre-vingts.**
C'est une liste de course trois fois plus courte à qualité égale — le gain le
plus concret de cette passe pour qui doit vraiment acheter les pièces.

Le glouton était aussi **quadratique en `count`** : à chaque candidat il
recalculait le minimum sur tout l'ensemble déjà retenu. Or ajouter une couleur
ne peut que *rapprocher* une grappe, donc un minimum courant suffit :

    cout(R + [c]) = Σᵢ partᵢ · min( min_{r ∈ R} d(i,r) , d(i,c) )

L'optimisation est **exacte**, pas approchée, et un test le vérifie contre un
recalcul naïf plutôt que de le croire. N=48 passe de **12,4 s à 4,4 s**.

**Piste réfutée.** Une recherche locale par échanges 1-pour-1 après le glouton :
N=8 gagnait 0,14 ΔE (2 %), N=12 et N=20 ne gagnaient **rien du tout**. Le
glouton est déjà à l'optimum pratique. Pas de code pour ça.

### 5.31 Le décodage JPEG au huitième : question posée, question close

Le décodeur ne lit que les coefficients DC, donc rend l'image **au huitième**.
Une photo de 4000 px devient 500 px, soit 10 pixels par tenon pour une mosaïque
de 48 — confortable. Mais une photo de 800 px n'en laisse que 2, et une de
400 px, un seul. Fallait-il un décodeur au quart, c'est-à-dire une IDCT 2×2 et
le décodage des coefficients AC ?

Mesuré, sur une image de bandes puis sur une mire d'anneaux concentriques — le
pire cas pour le sous-échantillonnage, celui qui produit du moiré :

| Photo d'origine | Décodée | px/tenon | ΔE par tuile | pire |
|---:|---:|---:|---:|---:|
| 6000 px | 750 | 15,6 | 6,65 | 12,01 |
| 2000 px | 250 | 5,2 | 7,27 | 15,64 |
| 800 px | 100 | 2,1 | 8,04 | 17,41 |
| 384 px | 48 | 1,0 | 6,47 | 8,38 |

**Le coût est de l'ordre de 0,5 ΔE en moyenne.** La raison est structurelle : la
mosaïque elle-même réduit à 48 tenons, et cette réduction-là domine largement
celle du décodeur. Un décodeur au quart serait un gros morceau de code — IDCT
2×2, décodage des AC, table de zigzag — pour un gain que la mesure ne trouve
pas. **Question close, pas ajournée.**

Reste un cas réel : quand la photo décodée est plus petite que la mosaïque
demandée. Sous **2 pixels par tenon** il n'y a plus de moyenne du tout — chaque
tuile prend la couleur d'un pixel à peu près au hasard dans sa zone. Le CLI
l'annonce désormais, avec la taille à laquelle il faudrait descendre.

### 5.32 Le tramage adaptatif inventait du grain, et un plafond mesuré le borne

En regardant le rendu final, un défaut restait : le coin de ciel lavande — là où
la palette a son plus grand trou — se criblait de tuiles blanches et roses. La
diffusion travaillait à pleine force et pulvérisait un écart énorme sur les
voisins.

Pour trancher sans juger à l'œil, il fallait une mesure de ce que le tramage
peut **abîmer**, et non seulement de ce qu'il améliore. C'est le **grain
inventé** : la variation d'une tuile à sa voisine que la photo ne contient pas
au même pas.

| Plafond de force | tonal moyen | tonal pire | grain inventé |
|---:|---:|---:|---:|
| 0,00 (pas de tramage) | 5,72 | 13,12 | +0,52 |
| 0,25 | 5,12 | 12,79 | +2,95 |
| 0,35 | 4,79 | 11,00 | +4,01 |
| **0,50** | **4,25** | **8,54** | +5,52 |
| 0,70 | 4,09 | 8,54 | +6,01 |
| 1,00 (avant) | 4,08 | 8,54 | +6,06 |

Le genou est net et il ne se discute pas : **à 0,50, le pire écart tonal a déjà
rejoint celui du tramage plein**. Passer à 1,00 gagne 0,17 ΔE et coûte un
demi-point de grain — du grain qui se voit. `DITHER_MAX_STRENGTH = 0.5` est
donc le plus petit plafond qui conserve la totalité du bénéfice, pas un réglage
au jugement.

C'est aussi ce qui manquait à toutes les décisions précédentes sur le tramage :
un critère qui mesure le **coût**. La fidélité par tuile ne le voit pas — elle
mélange l'erreur de palette et le grain. La justesse tonale ne le voit pas non
plus, puisque le grain s'y annule par construction.

---

### 5.33 Le tramage n'a pas de bon réglage universel — il en faut un par image

Le § 5.32 avait calé `DITHER_MAX_STRENGTH = 0.5` sur un genou mesuré. Le genou
était réel — **sur une image**. Testé sur une seconde, il se retourne :

| Scène | Sans : tonal / pire | Adaptatif : tonal / pire | Grain inventé |
|---|---|---|---:|
| Paysage | 5,55 / 12,42 | 3,73 / **7,48** | +6,67 |
| Portrait | 7,01 / **10,17** | 4,49 / **11,52** | +8,09 |

Sur le paysage le tramage améliore le pire écart tonal ; sur le portrait il
l'**aggrave**, tout en ajoutant huit points de grain. Un défaut fixe se trompe
forcément sur l'une des deux, et le rendu du portrait le montrait sans
ambiguïté : un visage criblé de damier.

Deux hypothèses essayées puis **réfutées par la mesure**, notées ici pour
qu'elles ne soient pas retentées :

1. *Ne tramer qu'aux gradients* (moduler par le contraste local). Argument : à
   distance humaine les tuiles ne fusionnent pas, donc mélanger deux tuiles
   dans un aplat ne rend pas la couleur voulue, il montre un damier. Mesure :
   le critère combiné abandonne presque tout le gain du paysage (5,30 contre
   3,73) pour ne récupérer que du grain. Réfuté.
2. *Ne jamais tramer*. Le rendu du ciel dégradé tranche : sans tramage, deux
   faux contours horizontaux traversent le ciel ; avec, la progression est
   continue. Le tramage a raison là.

Ce qui marche est une décision **par image**, sur le PIRE écart tonal :

> Tramer si et seulement si le tramage améliore le pire écart tonal d'au moins
> 1 ΔE — le seuil de perception.

Le pire et non le moyen : le travail du tramage est de supprimer les échecs
francs — bandes, faux contours —, pas de grappiller une moyenne. S'il n'y
arrive pas, il n'ajoute que du grain. Vérifié sur six scènes : aplats sur
palette → non ; portrait → non ; texture fine (gain 0,28) → non ; paysage, ciel
dégradé, dégradé diagonal → oui.

**Effet secondaire mesuré et non anticipé** : ne pas tramer allonge les suites
de même couleur, donc la fusion des tuiles rend davantage. Le portrait passe de
1567 à **776 tuiles** — le bon réglage de tramage divise aussi le coût par deux.

### 5.34 Deux hypothèses spatiales de plus sur le tramage, réfutées

Après avoir établi la décision par image (§ 5.33), j'ai cherché à faire mieux :
un critère **spatial**, qui tramerait certaines zones et pas d'autres. Deux
tentatives, deux réfutations par la mesure. Consignées pour qu'on ne les
retente pas.

1. **Moduler par le contraste local de la photo.** Première implémentation
   mal orientée : dans un dégradé lisse, la variation d'une tuile à sa voisine
   est *minuscule*, donc le critère supprimait le tramage exactement là où le
   bandage apparaît. Corrigé, il abandonne quand même presque tout le gain du
   paysage (5,30 contre 3,73 de justesse tonale) pour ne récupérer que du grain.

2. **Moduler par l'écart entre les deux couleurs mélangées.** L'idée : mélanger
   deux couleurs proches donne un fondu, mélanger deux couleurs éloignées donne
   du poivre et sel. Mesure des zones réelles :

   | Zone | Écart palette | Écart entre les deux | Rendu observé |
   |---|---:|---:|---|
   | Ciel dégradé (haut) | 8,4 | 16,0 | **bon** |
   | Fond portrait (haut) | 7,1 | 11,9 | **mauvais** |
   | Peau à l'ombre | 9,7 | 15,3 | mauvais |

   Le critère ne sépare pas les cas : la zone au plus grand écart est celle qui
   rend le mieux. Réfuté.

La décision par image reste donc la meilleure connue. Ce n'est pas une preuve
qu'aucun critère spatial ne marche — c'est le constat que les deux plus
évidents ne marchent pas, et qu'il faudra une hypothèse qui prédise ces
mesures-là pour prétendre faire mieux.

### 5.35 `build` livrait des modèles qu'il savait invalides

Le balayage adverse a trouvé deux formats — 1×12 et 12×1 — pour lesquels
`build` rendait un modèle que les invariants du noyau refusaient ensuite. Une
mosaïque d'un seul tenon de large ne peut pas être tenue par un substrat
croisé : il n'y a pas de place pour croiser.

La règle exacte est biscornue — un tenon de large tient jusqu'à 4 de long, deux
de haut tient jusqu'à 2 de large — et l'écrire en dur serait une devinette à
maintenir. `build` **constate** donc, par union-find sur les tenons : le fond
est connexe si et seulement si le graphe biparti « couche 0 ↔ couche 1, arête
dès qu'elles partagent un tenon » l'est. Linéaire, exact.

Vérifié sur les 64 formats de 1×1 à 8×8 : le refus coïncide exactement avec la
connexité réelle, 10 refusés et 54 acceptés. Le test ne compare pas à une liste
écrite à la main, il compare à la mesure.

L'information était disponible dans `build`, et gratuite. La livrer quand même
et laisser le noyau la refuser trois étapes plus loin, c'était perdre le
message utile en chemin.

### 5.36 « La fusion ne coûte aucune fidélité » était faux

Je l'ai écrit dans le code, dans le README, dans le registre et dans un message
de commit. Un test le « prouvait » en comparant les aperçus octet par octet.

Le test comparait des aperçus **sans joints**. Or sur du vrai LEGO les pièces
ont des joints, et une tuile 1×4 n'a pas de joint interne là où quatre 1×1 en
ont trois. En traçant les joints réels, la différence saute aux yeux : la
version 1×1 donne la **grille régulière** des sets LEGO Art officiels, la
version fusionnée donne un **appareil à joints décalés**, comme un mur de
briques.

Ce n'est pas forcément moins beau. Mais ce n'est pas identique, et le dire
l'était encore moins.

Indice que j'aurais dû relever plus tôt : **les sets LEGO Art officiels
n'emploient que des 1×1**, malgré un coût par pièce bien supérieur. Ils
achètent l'uniformité de la surface. Je l'avais noté dans le code — « celles
des sets LEGO Art officiels » — sans en tirer la conséquence.

Corrections :

- `preview(mosaic, scale, seams=True)` trace les joints réels. Le concepteur
  peut **voir** ce qu'il commande avant de le commander, et la commande émet
  désormais `apercu_joints.png` en plus de `apercu.png`.
- Le test n'affirme plus « rendu identique ». Il affirme deux choses séparées et
  toutes deux vraies : *aucune couleur ne change*, et *la surface change*.
- Le CLI dit la contrepartie au lieu de vanter un gain gratuit, et rappelle que
  `--references minimal` rend la grille uniforme.

La leçon porte au-delà de ce défaut : un test qui compare deux sorties d'une
même fonction ne prouve que ce que cette fonction représente. `preview` ne
représentait pas les joints, donc le test ne pouvait rien dire des joints — et
il a servi quatre fois à affirmer le contraire.

### 5.37 CIEDE2000 coûtait 83 % du temps — une borne exacte l'a réduit

Le profil de la quantification d'une photo de 1,7 Mpx : **6,1 s sur 7,4** dans
`_delta_e2000_lab`, 555 000 évaluations. La formule est chère, et `nearest` la
lançait sur les quatre-vingts couleurs de la palette pour chaque tenon.

**Première idée, réfutée par la mesure.** Présélectionner les *k* plus proches
au sens de CIE76 — bien plus simple à calculer — puis n'évaluer CIEDE2000 que
sur celles-là. Sur 4000 cibles :

| k | Désaccords avec la réponse exacte |
|---:|---:|
| 4 | 8,12 % |
| 8 | 1,48 % |
| 16 | 0,33 % |

Elle ne converge pas, et c'est logique : si CIE76 classait comme CIEDE2000, il
n'y aurait eu aucune raison de changer de métrique. Cette présélection
réintroduisait exactement le biais qu'on venait de corriger. **Rejetée.**

**Ce qui marche est une borne inférieure démontrable**, pas une heuristique :

> ΔE2000² = t_L² + t_C² + t_H² + R_T·t_C·t_H, avec R_T ∈ [−2, 0]
>
> or t_C² + t_H² + R_T·t_C·t_H ≥ t_C² + t_H² − 2|t_C||t_H| = (|t_C| − |t_H|)² ≥ 0
>
> donc **ΔE2000 ≥ |ΔL| / S_L**, et S_L = 1 + 0,015(L̄−50)²/√(20+(L̄−50)²) ≤ 1,748

En parcourant la palette par clarté croissante autour de la cible, dès que
|ΔL|/1,748 dépasse le meilleur écart trouvé, aucune couleur plus éloignée en
clarté ne peut faire mieux. La recherche s'arrête, et le résultat est **exact**.

Vérifié sur 6000 cibles aléatoires et trois palettes : zéro désaccord avec la
recherche exhaustive. Un test vérifie aussi l'inégalité elle-même sur 3000
paires — si elle tombait, la coupure écarterait la bonne couleur en silence.

S'y ajoute un cache des résultats : le mode « auto » interroge trois fois les
mêmes tenons — version sans tramage, mesure de l'écart à la palette, version
tramée — et deux tiers de ce travail étaient identiques.

**2,17 s → 0,89 s**, à résultat identique.

### 5.38 `cheapest_palette` ne minimisait pas le coût

Sur le portrait, `--couleurs auto` retenait 7 couleurs et **1458 tuiles** — alors
que la palette entière n'en demandait que **776**. La fonction censée réduire le
coût le doublait.

La chaîne causale, mesurée : moins de couleurs ⟹ écarts à la palette plus grands
⟹ le tramage automatique se déclenche ⟹ la diffusion d'erreur brise les suites
de même couleur ⟹ la fusion des tuiles ne rend plus rien ⟹ deux fois plus de
pièces. Trois décisions correctes prises séparément, un résultat absurde une
fois enchaînées.

| Couleurs | ΔE/tuile | Ton moyen | Tuiles | Lots |
|---:|---:|---:|---:|---:|
| 4 | 9,04 | 8,42 | 687 | 19 |
| 7 | 8,58 | 4,75 | 1458 | 28 |
| 10 | 8,49 | 4,65 | 1491 | 34 |
| **80** | **7,89** | 7,01 | **776** | 43 |

Trois défauts distincts, chacun révélé par une mesure qui contredisait le code :

1. **La palette entière n'était pas candidate.** Elle est ici la plus fidèle
   *et* la moins chère en pièces. Une fonction qui promet le meilleur coût ne
   peut pas ignorer ce candidat-là.
2. **Le critère était la taille de la palette, pas le coût.** L'hypothèse
   implicite — « plus petite palette = moins cher » — est fausse dès que le
   tramage entre en jeu.
3. **La référence était le meilleur de chaque critère pris séparément.** Or les
   deux critères sont optimisés par des palettes différentes (80 couleurs pour
   l'écart par tuile, 10 pour la justesse tonale) : exiger d'être à 0,5 ΔE du
   meilleur des deux ne laissait, sur ce portrait, **aucune candidate
   admissible**.

Corrigé : la référence est la palette entière, une candidate est admissible si
elle ne dégrade ni l'un ni l'autre critère de plus que la tolérance, et parmi
les admissibles on prend la **moins chère** — pièces d'abord, lots ensuite.

Résultat, tolérance 1,0 : le paysage descend à 12 couleurs (−10 % de pièces,
−19 % de lots, 0,61 ΔE tonal abandonné), le portrait **garde la palette
entière** parce que rien de moins cher ne vaut le coup. Une fonction
d'optimisation qui répond « ne changez rien » quand c'est vrai vaut mieux
qu'une qui trouve toujours quelque chose à couper.

*(Rectificatif : le message du commit précédent annonçait 193 tests verts, il y
en avait 192.)*

### 5.39 L'export LDraw : la zone déclarée « délibérément absente » est fermée

Le registre disait : *« Écrire un exporteur sans les vraies origines produirait
des fichiers faux : je ne l'ai pas fait. »* C'était la bonne décision — un
`.ldr` faux s'ouvre normalement et ne signale rien. Les deux données manquantes
sont maintenant **lues**, pas devinées.

**Origine des pièces**, établie sur `3001.dat` (Brick 2×4) de la bibliothèque
LDraw officielle — fichier qui porte, lui, le marqueur
`!LICENSE Redistributable under CCAL version 2.0` :

| Ce que dit le fichier | Conséquence |
|---|---|
| Corps : x ∈ [−40, 40], z ∈ [−20, 20] | Origine au **centre** de l'empreinte |
| Corps : y ∈ [0, 24] | |
| Tubes de dessous descendant jusqu'à y = 24 | Origine à la **face supérieure** du corps |

**Convention d'axes** : `x_ldraw = x_noyau`, `y_ldraw = −z_noyau`,
`z_ldraw = y_noyau`. Le déterminant vaut **+1**, et le module le vérifie à
l'import. Ce n'est pas une précaution de principe : un déterminant −1 serait une
réflexion, et une mosaïque exportée en miroir — un visage inversé, un texte à
l'envers — ne se signalerait par rien.

**Un défaut trouvé par le test, et c'est la règle du contrat qui se venge.**
Je calculais d'abord l'origine LDraw depuis l'**AABB** de la pièce posée. Ça
marchait tant qu'aucune pièce n'était tournée, et se décalait de 20 LDU dès
qu'une l'était : l'AABB bouge avec la rotation, pas l'origine. Le décalage du
coin local vers l'origine LDraw est un **vecteur local** — il subit R seul, puis
on ajoute t. C'est exactement `transform_local_direction_to_world`, la première
des quatre règles non négociables du contrat, et elle se venge ici comme
ailleurs.

Le test relit le fichier produit, reconstruit les empreintes indépendamment et
les compare à celles du noyau : **exact sur les 24 rotations et quatre
références**. Ce qu'il ne prouve pas, et qui est écrit dans l'en-tête du fichier
produit : qu'une seule pièce officielle était disponible pour établir la
convention. Elle vaut pour la famille rectangulaire — briques, plates, tuiles —
qui est exactement ce que ce dépôt emploie.

### 5.40 « On ne peut pas commander » : le blocage réduit à un téléchargement

Le dernier écart entre « j'ai un modèle » et « j'ai les briques ». Il tenait à
**une** donnée, et il fallait la nommer précisément avant de conclure quoi que
ce soit :

- Les références de **pièces** sont communes aux deux systèmes. Celles employées
  ici — 3070b, 2431, 3020, 41539… — sont vérifiées identiques dans `parts.lst`
  de LDraw et dans le catalogue BrickLink. Rien à traduire.
- Les codes **couleur** sont propres à chaque système, et la correspondance
  n'est dérivable de rien : ni la valeur RVB ni le nom ne l'établissent de façon
  fiable. Vérifié : elle exige une clé d'API Rebrickable, que je ne peux ni
  obtenir ni valider ici.

Conclusion tentante : « bloqué ». Elle est fausse. Ce qui manquait n'était pas
la table — c'était le **code qui s'en sert**. `bfk001/bricklink.py` écrit la
liste de souhaits au format XML documenté ; la table vient de l'appelant, sous
la forme la plus pauvre possible — deux colonnes, code LDraw et code BrickLink —
pour qu'elle puisse venir de n'importe quelle source jugée fiable, y compris
d'un tableur rempli à la main.

**Ce qui n'est pas dans la table n'est pas deviné.** `dumps_wanted_list` lève
`UnmappedColors` et ne produit rien. Une liste de course incomplète se paie en
pièces manquantes le jour du montage ; une liste **fausse** se paie en pièces
inutilisables, et on ne s'en aperçoit qu'à la livraison. Le refus s'est déclenché
au premier essai réel : ma table d'exemple oubliait le code 6, la commande n'a
pas été produite, et le message a nommé la couleur manquante.

La lecture de la table refuse aussi une **contradiction** — deux codes BrickLink
pour un même code LDraw. Silencieusement, le dernier gagnerait et une partie de
la commande serait fausse.

Reste ouvert, et c'est une donnée et non du code : **la table elle-même**. Le
dépôt n'en fournit aucune, parce qu'aucune n'a pu être vérifiée ici.

### 5.41 Le centrage aveugle décapitait

Dernière zone déclarée du côté perception : *« Manque : recadrage attentionnel —
sur un portrait, le centrage peut décapiter. »* Elle était exacte. Mesure sur
une photo 300×500 dont le sujet est haut dans le cadre, ramenée au carré :

| Cadrage | Fenêtre retenue | Tête (y 20…160) |
|---|---|---|
| Centré, 0,50 | y 100…400 | **coupée** |
| Automatique, 0,08 | y 16…316 | entière |

Le critère est l'**énergie de gradient** : la somme des écarts entre pixels
voisins, faible sur un ciel uni, forte sur un visage, un feuillage, un texte. On
retient la fenêtre qui en conserve le plus.

**Ce que ce critère ne fait pas**, et qu'il ne faut pas lui prêter : il ne
reconnaît rien. Un fond de feuillage très texturé derrière un visage lisse
l'attire vers le feuillage. Un test le démontre au lieu de le taire — un critère
qu'on ne sait pas mettre en défaut est un critère qu'on n'a pas compris. D'où
`--cadrage`, qui reste réglable à la main.

**Un détail de conception que le test a validé par accident.** La première
version cherchait le *pic* du profil de détail. Sur cette image, le pic tombe sur
l'arête sol/ciel : un seul rang, gradient énorme. Une ligne d'horizon n'est pas
un sujet. La fenêtre **intégrée**, elle, suit la zone texturée — un damier
contribue sur des dizaines de rangs là où une arête ne contribue que sur un.
C'est pour cela que la fonction somme au lieu de chercher un maximum, et un test
fixe désormais cette distinction.

Le défaut de la commande passe donc à `--cadrage auto`.

### 5.42 Le coût : moitié moins de pièces, sans toucher au rendu

Une tuile 1×4 rouge montre exactement les mêmes quatre tenons rouges que quatre
tuiles 1×1. Fusionner les tuiles voisines de même couleur ne coûte donc
**aucune fidélité** — c'est vérifié par un test qui compare les aperçus octet
par octet — et divise le nombre de pièces.

Mesure sur un paysage 48×48, palette officielle :

| Références employées | Pièces | Lots à commander | Gain |
|---|---:|---:|---:|
| 1×1 seule | 2304 | 15 | — |
| 1×1, 1×2 | 1571 | 23 | −32 % |
| **1×1, 1×2, 1×4** | **1283** | **30** | **−44 %** |
| + 1×3 | 1234 | 37 | −46 % |
| + 1×6, 1×8 | 1105 | 50 | −52 % |

Le défaut s'arrête à trois références. Au-delà, chaque point de pièces gagné
coûte plusieurs lots de plus à trouver — le 1×3 coûte sept lots pour deux
points — et les tuiles longues sont rares dans beaucoup de couleurs.

Deux choix de conception, tous deux mesurés :

- **Découpe par programmation dynamique, pas glouton.** « La plus longue
  d'abord » n'est pas optimal : avec des tuiles de 1, 3 et 4, un run de 6 se
  découpe en 3+3 et non en 4+1+1. Un test compare la DP à une recherche
  exhaustive sur toutes les longueurs jusqu'à 24.
- **Fusion en lignes, jamais en colonnes.** La rotation existe et fonctionne
  (`place_at` vise le coin de l'AABB, pas l'origine de la pièce, parce que sous
  rotation les deux diffèrent). Mais la notice se lit ligne par ligne, et une
  tuile à cheval sur deux lignes obligerait à la poser depuis deux pages.

Le gain n'est pas une propriété du code mais de l'**image** : sur du bruit pur,
aucune suite à fusionner, gain quasi nul ; sur une image structurée, massif. Le
test vérifie les deux cas.

### 5.43 Le proxy de choix de palette optimisait le mauvais critère

`Palette.cheapest_subset` choisit la plus petite palette dont l'écart **par
tuile** reste dans une tolérance. Il conclut « huit couleurs suffisent » : au-delà,
l'écart par tuile ne bouge plus (8,09 → 8,06 puis 8,38).

C'est faux, et la mesure sur la mosaïque réelle le montre :

| Couleurs | ΔE/tuile | Ton moyen | Ton pire | Tuiles | Lots |
|---:|---:|---:|---:|---:|---:|
| 8 | 8,09 | 5,01 | 12,29 | 1117 | 26 |
| 13 | 8,39 | 4,35 | 8,54 | 1172 | 29 |
| 80 | 8,27 | **3,73** | **7,48** | 1283 | 34 |

**L'écart par tuile plafonne à huit couleurs ; la justesse tonale continue de
s'améliorer jusqu'à quatre-vingts.** Or c'est la justesse tonale qui gouverne la
lecture d'ensemble du tableau — c'est déjà elle qui avait tranché le choix de
moyenner en lumière linéaire (§ 5.23bis). Le proxy aurait fait perdre un tiers
de justesse tonale en annonçant que ça ne coûtait rien.

`mosaic.palette_cost_curve` construit donc la mosaïque pour chaque taille de
palette et mesure les deux critères. `mosaic.cheapest_palette` arbitre sur les
deux, et **rend ce qu'il abandonne** au lieu de l'affirmer : à 0,5 ΔE de
tolérance, 13 couleurs au lieu de 80, soit 1172 tuiles et 29 lots au lieu de
1283 et 34, pour 0,09 ΔE de justesse tonale perdue — très au-dessous du seuil
de perception.

Défaut trouvé en écrivant le test : `best_subset` fait varier son nombre de
grappes avec `count`, donc sa réponse pour N n'est **pas** le préfixe de la
courbe. Choisir N sur la courbe puis rappeler `best_subset(N)` livrait une
palette autre que celle qu'on venait de mesurer. La courbe rend maintenant la
suite de couleurs elle-même.

---

### 5.44 Le fond coûtait un tiers du modèle pour quelque chose d'invisible

657 plates 2×4 sur une 48×48, soit 36 % des pièces — pour un substrat que
personne ne verra jamais. Sa seule qualité est de tenir.

Premier réflexe : repaver en grandes plates. Un réseau 8×8 décalé de moitié
donne 85 pièces au lieu de 613, couvre exactement… et **scinde le fond sur 992
formats sur 1521**. Même piège qu'au § 5.22.

La mesure dit précisément où est le piège, et ce n'est pas où je l'avais dit
d'abord. Au niveau du **réseau**, le pavage grossier tient toujours : zéro
échec sur 441 formats. Mais une cellule rognée du bord n'est pas une pièce
réelle — un rectangle 3×7 n'existe pas — et il faut la découper en plates du
catalogue. **C'est cette découpe qui réaligne les joints** sur ceux de la
couche du dessous : 294 formats sur 441 se scindent alors. La première version
de ce paragraphe accusait le réseau ; le test l'a démentie.

D'où la solution, qui repose sur un théorème et non sur un balayage :

> Contracter deux sommets d'un graphe connexe laisse un graphe connexe.

Fusionner des plates **déjà posées** est exactement une contraction du graphe
de liaison. Le fond ne peut donc pas se scinder, quelle que soit la taille de
l'œuvre — ce n'est plus une vérification empirique, c'est une garantie. Et la
fusion ne crée jamais de joint nouveau, donc elle ne peut rien réaligner.

| Côté | Fond avant | Fond après |
|---:|---:|---:|
| 16×16 | 105 | 28 |
| 32×32 | 325 | 70 |
| 48×48 | **657** | **128** |
| 64×64 | 1105 | 202 |

Vérifié sur tous les formats de 2×2 à 48×48 plus 56 et 64 : emprise exacte,
fond d'un seul tenant, zéro violation sur les six invariants.

### 5.45 Bilan de la passe d'optimisation

Sur la même photo, en 48×48 :

| | Avant | Après |
|---|---:|---:|
| Pièces totales | 2961 | **1300** |
| Tuiles de mosaïque | 2304 | 1172 |
| Plates de fond | 657 | 128 |
| Écart par tuile | 23,9 ΔE | **8,4 ΔE** |
| Justesse tonale | — | 4,4 moyen, 8,5 au pire |

**−56 % de pièces et un écart divisé par près de trois**, sans qu'aucun tenon
de l'œuvre ne change de couleur par rapport à ce que la palette permet.

Trois défauts trouvés en écrivant les tests de cette passe, tous des
affirmations de ma part que la mesure a démenties : le réseau accusé à la place
de la découpe (§ 5.44), le proxy de palette qui optimisait le mauvais critère
(§ 5.43), et le générateur aléatoire du test de conformité qui tirait à
l'aveugle puis renonçait — inoffensif tant que le catalogue ne contenait que
de petites pièces, muet dès qu'on y a ajouté des plates 8×8.

---

### 5.46 Le relief héritait du tramage : un tiers de l'œuvre en clous

Le relief venait d'être branché (§ 6.9) et je l'avais mesuré sur la fidélité :
zéro coût, les couleurs ne bougent pas d'un iota. C'était vrai, et c'était la
mauvaise question. La bonne : **est-ce que ça ressemble à une sculpture ?**

`relief_from_luminance` lit la grille qu'on lui donne. La chaîne lui donnait la
grille **tramée**. Or le tramage est un marché : il échange de la justesse
tonale contre du bruit spatial, et il est gagnant parce que l'œil fond ce bruit
dans les couleurs. Une élévation ne se fond jamais. Une marche de 3,2 mm porte
une ombre, accroche la lumière rasante, se voit de côté. Tramer le relief, c'est
transformer le damier que l'œil devait ignorer en un lit de clous.

Deux mesures nommées pour le voir sans regarder l'image — `relief_speckle`
(cases dont aucun voisin ne partage la hauteur) et `relief_plateaus` (tailles
des régions connexes de même hauteur) :

Portrait 48×80, deux étages, palette officielle, image tramée :

| Source des élévations | Cases isolées | Plateaux | Pièces |
|---|---:|---:|---:|
| grille tramée (l'ancien) | 1473 | 1748 | 5138 |
| grille non tramée | 0 | 3 | 4003 |
| grille non tramée + médiane | 0 | 3 | 4002 |

**1473 des 3840 cases** — 38 % de l'œuvre — étaient des tours isolées d'une
plate. Elles coûtaient **1136 pièces, 22 % du modèle**, pour fabriquer du grain.

Le remède est structurel et non cosmétique : `relief_from_image` quantifie une
**seconde fois sans tramage**, uniquement pour lire les hauteurs. La grille
qu'on pose reste la grille tramée — les couleurs sont identiques au ΔE près
(10,60 avant, 10,60 après) — seule la carte des élévations change de source.
La fonction **refuse** un argument `dither` : ce serait redemander le défaut.

Une passe de médiane 3×3 (`smooth_relief`) suit, pour les cas où la grille nette
mouchette quand même. La médiane et non la moyenne : elle n'invente aucune
hauteur intermédiaire — sa sortie est toujours une hauteur déjà présente dans la
fenêtre, ce qui compte quand la seule marche disponible est une plate entière —
et elle préserve les marches franches au lieu de les biseauter.

Son effet est réel mais second, et je le note tel quel plutôt que de le
survendre. Sur les Tournesols (image non tramée, donc déjà propre) : 16 → 8
plateaux, 5 → 0 cases isolées, 1123 → 1113 pièces. Sur cette même image à trois
étages, une passe **dégrade** légèrement le compte (18 → 21 isolées) : déplacer
une frontière peut orpheliner une case. C'est un lissage, pas une garantie.

Ce que la mesure dit aussi, et qui n'était pas prévu : **le relief se fragmente
au-delà de deux étages**, parce que les bandes de niveau deviennent plus fines
qu'un tenon.

Tournesols 48×48, chemin corrigé :

| Étages | Plateaux | Isolées | Pièces | Épaisseur |
|---:|---:|---:|---:|---:|
| 0 | 1 | 0 | 962 | 0,0 mm |
| 1 | 7 | 0 | 1056 | 3,2 mm |
| 2 | 8 | 0 | 1130 | 6,4 mm |
| 3 | 35 | 21 | 1204 | 9,6 mm |
| 4 | 53 | 36 | 1277 | 12,8 mm |

La sortie de la commande affiche désormais ces deux chiffres et prévient quand
le relief mouchette. Et la fragmentation se corrige par la **résolution**, pas
par des passes de filtre : à 96×96, quatre étages donnent 112 plateaux pour
0,7 % de cases isolées, contre 53 plateaux pour 1,6 % à 48×48. Deux fois plus de
relief pour deux fois moins de bruit.

Ce que je retiens : j'avais mesuré le coût du relief sur le seul axe où il était
gratuit. « Zéro ΔE » répondait à une question que personne n'avait posée.

---

### 5.47 Les marches du relief tombaient au hasard — et ma première mesure récompensait le fait d'en faire moins

Un relief ne se voit que par ses **marches**. Une marche porte une ombre, le
reste est plat. La question n'est donc pas « quelle hauteur » mais « où tombent
les frontières ». Au milieu d'un dégradé, on obtient une carte d'état-major :
des courbes de niveau qui ne désignent rien. Sur les contours du sujet, on
obtient une sculpture.

Le découpage était **uniforme** : la plage de clarté tranchée en parts égales.
Rien ne garantit qu'une part corresponde à quoi que ce soit dans la photo.

**La mesure, d'abord — et je l'ai ratée.** Première version : contraste de la
photo sous les marches ÷ contraste moyen. Elle donnait 103 sur un portrait,
6,2 sur les Tournesols, et elle était **fausse**. Un relief à une seule marche,
posée sur le contour le plus fort, obtenait le meilleur score possible ; tout
étage supplémentaire le dégradait mécaniquement. Elle récompensait le fait d'en
faire moins.

Version corrigée, `relief_edge_alignment`, normalisée par le NOMBRE de marches :
contraste sous les K marches posées ÷ contraste des K frontières les plus
contrastées qu'offre la photo. **1,0 = on ne pouvait pas mieux placer K
marches.** La mesure ne récompense plus l'abstention.

**Ce qu'elle a révélé.** Le découpage uniforme, à trois étages sur un portrait,
n'emploie que les hauteurs **0 et 3** : trois couches de relief pour la
silhouette qu'une seule donnait, 144 pièces pour rien. La commande le signale
désormais.

**Le remède : les seuils d'Otsu**, calculés par programmation dynamique — les
seuils tombent dans les creux de l'histogramme, là où l'image se sépare en
régions.

Et une deuxième correction que j'ai failli publier surévaluée. J'ai d'abord
écrit qu'Otsu valait 0,85 contre 0,70. C'était vrai — mais pas dans le chemin
que j'avais câblé. Mesure complète, Tournesols 48×48, deux étages :

| Source des seuils | Rendement | Plateaux | Isolées | Pièces |
|---|---:|---:|---:|---:|
| grille quantifiée + uniforme | 0,76 | 8 | 0 | 1128 |
| grille quantifiée + Otsu | 0,76 | 8 | 0 | 1108 |
| clarté continue + uniforme | 0,70 | 30 | 17 | 1145 |
| clarté continue + Otsu | **0,85** | **9** | **0** | 1114 |

Sur une grille **déjà quantifiée**, Otsu ne change presque rien : la
quantification a déjà séparé l'image en régions, elle faisait une part de son
travail. Lire la clarté continue **sans** Otsu est le pire des quatre. Les deux
corrections sont complémentaires et aucune ne suffit seule.

`relief_from_image` lit donc directement la clarté de la photo — **plus aucune
quantification, ni palette, ni tramage** — et découpe aux seuils d'Otsu. La
passe de quantification supplémentaire du § 5.46 disparaît : le vrai remède au
tramage n'était pas de quantifier sans tramer, c'était de ne pas quantifier.

Conséquence d'API : `palette` n'est plus un paramètre. Le relief décrit la
**structure** de la photo, pas les briques disponibles ; deux palettes donnent
le même relief.

---

### 5.48 Deux défauts dans mon propre câblage de la profondeur, trouvés en relisant

La lecture des cartes de profondeur (§ 6.10) était livrée, testée, poussée. En
la relisant, deux défauts — tous deux sur le trajet entre la photo et la carte,
aucun dans les algorithmes.

**La carte embarquée restait couchée sous une photo debout.** Une photo de
téléphone prise en portrait stocke des pixels *couchés* et note
`Orientation = 6` ; `read_jpeg_eighth` la redresse. La carte de profondeur, elle,
est écrite dans le repère des pixels stockés et ne porte aucun EXIF à elle —
elle sortait couchée. Proportions 0,75 contre 1,33 : `DepthMismatch` refusait.
La fonctionnalité n'aurait donc **jamais servi sur une photo de portrait**,
c'est-à-dire sur presque toutes celles qui portent une carte.

**La carte n'était pas rognée comme la photo.** La commande rogne la photo au
format de l'œuvre (une 4:3 dans une mosaïque carrée perd un quart de sa
largeur), puis passait à `heights_from_depth` la photo *déjà rognée* et la carte
*entière*, en mode `stretch`. Deux traitements différents sur deux descriptions
de la même scène. Là encore la garde refusait — toute photo qui n'était pas déjà
au format de l'œuvre.

Les deux fois, **la garde a fait son travail** : elle a refusé au lieu de livrer
un relief propre et faux. C'est la bonne défaillance, et c'est elle qui a rendu
les défauts visibles. Mais un refus systématique est un refus, et je n'avais
essayé la chaîne que sur une photo déjà carrée, sans EXIF — le seul cas où les
deux défauts sont invisibles.

Ce que je retiens : mes tests couvraient les *composants* (conteneur XMP,
médiane, garde de proportions) et pas le *trajet*. Les deux défauts sont dans
les paramètres passés d'un composant correct à un autre composant correct.
Quatre tests de câblage ont été ajoutés, dont un qui appelle la fonction de la
commande elle-même.

---

### 5.49 La même photo donnait deux listes de courses différentes

Trouvé en factorisant la chaîne pour l'interface : le résultat du refactor ne
correspondait pas à celui de la commande. J'ai d'abord cherché l'erreur dans mon
refactor. Elle n'y était pas — **la chaîne n'était pas déterministe.**

Trois exécutions de la *même* commande sur la *même* photo :

```
5d7c2c0a719c6888c019d7564f2f9860  liste_de_course.csv
da12b4039865a333eba3a5005ca8143d  liste_de_course.csv
5d7c2c0a719c6888c019d7564f2f9860  liste_de_course.csv
```

Ce n'est pas un défaut de confort. Une liste de courses qui change d'une
exécution à l'autre ne correspond plus à la notice qu'on a imprimée ni au
fichier LDraw qu'on a ouvert. **On commande des pièces qui ne sont pas celles
du plan.**

**La cause.** `_formes_de_fond` triait un `set` avec une clé *non totale* :
« aire décroissante, puis plus petit côté ». Les deux orientations d'une même
plate — une 2×4 et une 4×2 — ont la même aire et le même petit côté. Huit des
vingt-et-une formes étaient à égalité. Python départage alors par l'ordre
d'itération de l'ensemble, et cet ordre dépend du hachage des **chaînes** (les
références de pièces), donc de `PYTHONHASHSEED`, donc du lancement.

```
seed 0 : b0dc16b6d72b723f      seed 2 : 4f633cb0a187cfb3
seed 1 : 0ba194e8b8978106      seed 3 : c2a9dcca61aebe24
```

Le défaut ne se voyait **qu'avec du relief** : c'est le seul chemin qui appelle
cette fonction sur des formes de tailles variées. Le substrat plat, lui, était
stable — ce qui explique qu'il ait survécu à tout le reste du développement.

**Le remède** est d'une ligne : rendre l'ordre total. Les deux termes ajoutés
n'ont aucune signification esthétique, ils ne sont là que pour cela. La clé est
désormais une fonction nommée, `_cle_de_forme`, et non une lambda — pour qu'un
test puisse vérifier son injectivité sur le catalogue réel. Un test qui
recopierait la clé ne vérifierait que sa propre copie.

**Ce que je retiens.** Aucun de mes 280 tests ne pouvait voir ce défaut :
`PYTHONHASHSEED` est fixé au démarrage du processus, donc tout ce qui tourne
dans un seul processus est parfaitement reproductible. Le test ajouté lance
donc de vrais sous-processus avec des graines différentes. Vérifié dans les
deux sens : il échoue quand on remet l'ancienne clé, il passe avec la nouvelle.

Et une leçon de méthode : c'est le refactor qui a révélé le défaut, en
produisant deux fois le même calcul par deux chemins. Comparer deux
implémentations est un détecteur que la relecture ne remplace pas.

---

### 5.50 L'app : une chaîne unique, et deux défauts que les tests ne pouvaient pas voir

Le dernier point de la demande d'origine — « mettre une photo dans l'app » —
n'avait pas d'app : il avait une commande. `app_lego_art.py` en fait une, sans
ajouter la moindre dépendance.

**Le refactor d'abord.** Toute l'orchestration vivait dans le `main()` de la
commande, mêlée à l'analyse des arguments et aux impressions. Deux façades sur
ce code auraient signifié soit deux chaînes qui divergent, soit un
sous-processus qu'on ne peut pas tester. `bfk001/pipeline.py` porte désormais la
chaîne entière — photo en octets, fichiers en octets, aucun disque, aucune
impression — et les deux façades l'appellent à l'identique.

Vérification du refactor : sortie **octet pour octet identique** sur les huit
fichiers livrés. C'est aussi ce refactor qui a révélé le § 5.49.

**Puis deux défauts, trouvés en regardant la page dans un navigateur.**

Le premier : `PAGE` était une chaîne Python **non brute**. Le `\n` du script y
devenait un saut de ligne réel, ce qui coupait un littéral JavaScript en deux et
empêchait la page entière de se parser. Le serveur la servait parfaitement ;
elle ne faisait rien.

Le second : ma propre politique de sécurité. `default-src 'none'` est le bon
réflexe pour une page qui n'a aucune ressource externe — mais `connect-src`
retombe sur `default-src`, et la page ne pouvait donc pas appeler **son propre
serveur**. Le bouton restait muet.

Les deux sont des défauts de trajet, comme ceux du § 5.48. Et surtout : **vingt
tests passaient**, dont un aller-retour HTTP complet. Aucun n'exécutait le
JavaScript.

`test_bfk001_page.py` le fait maintenant, dans un vrai Chromium. Playwright
n'est pas une dépendance du projet — rien de ce qui est livré n'en a besoin — et
le fichier se saute proprement sans lui, en le disant, pour qu'un saut ne passe
pas pour un succès.

Un dernier détail qui dit quelque chose : le test d'erreur employait d'abord
`wait_for_function`, que la politique de sécurité refuse parce qu'elle évalue
une chaîne. J'ai changé le test, pas la politique.

---

### 5.51 La découpe multi-panneaux : deux conceptions refusées par le noyau avant la bonne

Dernière limite d'ingénierie de la liste : une œuvre de 96 tenons fait 77 cm et
ne se transporte pas. Les sets officiels sont faits de panneaux 16×16 — mais
leurs panneaux **ne se lient pas entre eux**, c'est le cadre qui les tient, et
le cadre n'est pas une pièce LEGO. Mesure : le substrat `panels` produit **454
violations de H5** sur une œuvre de 32 tenons. Le noyau a raison.

Et il n'a même pas d'intérêt économique. Le fond croisé, une fois fusionné, ne
coûte presque rien :

| Œuvre | Fond croisé | Panneaux 16×16 | Part du modèle |
|---|---:|---:|---:|
| 48×48 | 128 plates | 9 | 6 % |
| 96×96 | 398 plates | 36 | 4 % |

Économiser 362 pièces sur 8573 ne justifie pas de livrer un modèle qui tombe en
morceaux. **Le vrai besoin n'est pas le prix, c'est l'ergonomie** : bâtir en
plusieurs fois, transporter, ranger.

**Première conception, refusée.** Sections indépendantes, surélevées d'une
plate, reliées par des *ponts* isolés sous les seuls joints — pour économiser.
Le noyau a répondu par 122 violations, de deux natures :

- `H2_COLLISION` : deux ponts se percutent au croisement d'un joint vertical et
  d'un joint horizontal. Je ne l'avais pas prévu.
- `H4_FLOATING` : ailleurs qu'aux joints, les sections ne reposent sur rien.

Et avant cela, une erreur plus bête que le noyau a aussi attrapée : mes ponts
« à cheval sur un joint vertical » étaient posés **sans rotation**, alors que la
3020 est définie 2 en x sur 4 en y. Ils tenaient entièrement dans une seule
section — huit liaisons chacun, toutes du même côté.

**Conception retenue.** Une couche de jonction **pleine**, à z = 0, pavée par
`_paver` — le code du fond croisé, éprouvé sur 1521 formats — ancrée en (−1, −2)
de sorte que ses plates enjambent les joints. Les deux défauts disparaissent
d'un coup : c'est un pavage, donc sans collision, et il porte tout.

Le contrôle `_verifier_jonction` vérifie que chaque joint est réellement
enjambé, **sur les poses réelles et après fusion**, jamais sur le réseau
théorique — le § 5.44 a montré que le réseau ment. Bien lui en a pris : un
découpage en sections de 6 tenons tombe pile sur une frontière du réseau et
devrait échouer, alors qu'il passe, parce que la fusion produit des plates à
cheval que le réseau ne laissait pas prévoir.

Surcoût mesuré, et il baisse quand l'œuvre grandit :

| Œuvre | Sections | Entier | Découpée | Surcoût |
|---|---|---:|---:|---:|
| 32×32 | 2×2 de 16 | 984 | 1081 | +9,9 % |
| 96×96 | 2×2 de 48 | 8466 | 8843 | +4,5 % |

**Ce que je ne promets pas.** La rigidité. H5 dit « d'un seul tenant », pas « ne
plie pas ». Une jonction par-dessous est une charnière. Le noyau ne modélise pas
la raideur mécanique — c'est BFK-002 — et l'écrire noir sur blanc vaut mieux que
de laisser croire qu'un modèle validé est un modèle solide.

---

### 5.52 Le cadre, et la notice qui cesse de demander qu'on décode

Deux demandes en une : « pour chaque œuvre il faut un cadre comme les LEGO Art »
et « quelque chose de simple à comprendre comme une notice LEGO standard ».

#### Le cadre

Un mur de briques autour de l'image, sur un substrat élargi de deux tenons de
chaque côté. Sa hauteur n'est pas un réglage : `frame_courses` compte les assises
jusqu'à ce que le cadre **dépasse** la surface — une sans relief, deux avec deux
étages, parce qu'à deux étages la première assise arriverait pile à fleur.

Deux appareils croisés, et j'ai dû écrire les deux avant que ça tienne : en plan
(les bandes horizontales pleines une assise sur deux, sinon les quatre angles
sont quatre joints traversants) et en élévation (départ décalé, sinon le mur se
fend le long de ses joints).

**Deux conséquences que je n'avais pas prévues.**

La première répond à une réserve que j'avais écrite noir sur blanc au § 5.51 :
« une jonction par-dessous est une charnière ». Un cadre fermé sur les quatre
côtés est une ceinture. Le noyau ne mesure toujours pas la raideur — je ne
prétends pas le contraire — mais l'arrangement est celui des sets officiels.

La seconde est mesurée : **le cadre rend constructibles des formats que le noyau
refusait**. Une bande d'un tenon de large se scinde en dix-neuf morceaux sans
cadre ; avec, zéro violation. L'emprise que le cadre ajoute suffit à paver un
fond d'un seul tenant. Un test l'exige désormais dans les deux sens.

Et une décision de couche : `build(frame=0)` par défaut, `Reglages(cadre=2)` par
défaut. Le solveur propose, le produit décide. Les preuves du substrat sur 1521
formats gardent leur sens, et l'utilisateur reçoit un tableau.

#### La notice

Elle lisait chaque ligne en clair : `2x4A^ · 1G^ · 2C^^`. Exact, compact,
illisible. Une notice LEGO ne demande jamais de décoder.

| | Avant | Après |
|---|---|---|
| Ce qu'on lit | une ligne de codes par rangée | un encart de pièces, puis une bande dessinée |
| Étapes par page | 1 | 2 à 4 |
| Pages (Tournesols 32×32) | 15 | **10** |
| Pages de suite | possibles | impossibles — une image ne déborde pas |

Trois blocs par étape, dans l'ordre du geste : l'encart « à sortir », la bande en
grand avec **une lettre par pièce** (jamais par tenon — quatre « A » sur une 1×4
feraient prendre quatre pièces), et le repérage.

Il a fallu que `PdfPage` porte **plusieurs images** : une seule obligeait à
choisir entre montrer et situer.

Trois défauts trouvés en regardant les pages, comme toujours :

- les étages de relief s'annonçaient « Fond — couche 4 sur 4 », ce qui faisait
  lire un fond à quelqu'un qui posait un bas-relief ;
- la page du cadre annonçait « 19,2 mm au-dessus des tuiles » alors que le cadre
  mesure 19,2 mm **en tout** et que les tuiles en occupent la moitié : le relief
  promis était doublé ;
- le cadre apparaissait au milieu des couches de fond, faisant poser une bordure
  noire autour d'un carré vide. Il a désormais sa page, en dernier.

#### Les pièces, dessinées

Il restait ce que j'avais écrit comme la dernière différence : « les vraies
notices dessinent chaque pièce en perspective, avec ses tenons ». `render_piece`
le fait — projection isométrique, trois faces à trois éclairements, tenons en
cylindres — dans l'encart des étapes **et** dans la liste de course, avec le même
dessin, pour n'avoir qu'un langage à apprendre.

Deux choix qui ont évité d'écrire du code inutile :

- **L'anticrénelage est gratuit.** Les arêtes d'une pièce isométrique sont toutes
  obliques, donc un dessin de vingt points tracé directement est un escalier. On
  trace quatre fois plus grand et on réduit par `resample_box` — le
  rééchantillonnage en lumière linéaire écrit pour les photos (§ 5.24) est
  exactement l'anticrénelage qu'il faut.
- **Rien n'est recopié.** L'emprise, la hauteur du corps et `has_studs` viennent
  du catalogue. Une tuile n'a pas de tenons parce que le catalogue le dit.

Un défaut trouvé en regardant la page, une fois de plus : les grandes plates
débordaient sur les lignes voisines de la liste. Je ne bornais que la LARGEUR du
dessin — or en projection isométrique une plate 8×8 est aussi haute que large,
alors qu'une 1×8 est plate. Ne borner que la largeur laissait donc passer
exactement les pièces les plus encombrantes. Un test balaie désormais tout le
catalogue et vérifie les deux bornes.

---

### 5.53 La première vraie photo, et le défaut qu'elle a trouvé en dix minutes

Tout ce dépôt avait été mesuré sur des images que j'avais fabriquées moi-même.
La première photographie réelle — un vélo noir devant une porte noire — a
produit des dizaines de tuiles **magenta** sur la porte.

#### Le défaut

`Palette.nearest` renvoyait bien le minimum de CIEDE2000. Le problème était
CIEDE2000. Pour un gris sombre neutre, RVB(62, 68, 70) :

| couleur | tL | tC | tH | RT·tC·tH | ΔE2000 |
|---|---:|---:|---:|---:|---:|
| Purple (129,0,123) | 0,97 | 25,16 | 17,62 | **−731,03** | **14,61** |
| Dark Bluish Grey | 15,00 | 0,55 | −4,79 | 0,00 | 15,76 |

Le terme de rotation retire 77 % du carré de la distance : un violet saturé à
30,7 ΔE devient un « bon candidat » à 14,6 et bat le gris.

Ce terme modélise une interaction observée dans la région bleue **pour de
petits écarts** — la CIE borne explicitement la formule aux écarts faibles.
Choisir dans une palette de quatre-vingts teintes, c'est comparer des écarts de
5 à 40 : le terme y agit hors de son domaine de validité.

#### Le remède : séparer choisir de mesurer

`delta_e_selection` — CIEDE2000 sans le terme croisé — sert à **choisir**.
`delta_e` garde la formule standard et sert à **mesurer**. Vérifiée exacte à
quatre décimales sur les quinze paires de contrôle de Sharma, Wu et Dalal
(2005), publiées précisément pour cet usage.

Effet mesuré, vélo 48×48 :

| | ΔE/tuile | tonal | **pire** | isolées | couleurs |
|---|---:|---:|---:|---:|---:|
| CIEDE2000 complet | 7,81 | 5,83 | **18,18** | 154 | 19 |
| sans rotation | 7,82 | 5,26 | **10,84** | 142 | 17 |

Le pire écart tonal est divisé par près de deux. Sur les Tournesols et le
portrait : **strictement aucun changement**. Le défaut ne se manifestait que là
où mes fixtures n'allaient jamais — de grandes régions sombres et désaturées.

#### Trois erreurs de ma part en cours de route

**J'ai accusé le mauvais coupable.** Mon premier diagnostic annonçait « 213
désaccords sur 400 » entre `nearest` et la force brute. C'était mon erreur :
`delta_e` prend du **RVB** et je lui passais du **Lab**. Vérifié correctement :
zéro désaccord sur 400. J'ai failli publier un rapport de bug faux.

**J'ai jugé une correction sur une image mal comparée.** Le rendu corrigé
paraissait pire — moucheté brun partout — et j'ai bien failli revenir en
arrière. Les deux rendus ne différaient pas que par la métrique : la décision
automatique de tramage avait basculé. Le moucheté était du **tramage**, pas la
métrique.

**J'ai écrit une justification fausse.** « Retirer un terme négatif ne peut
qu'augmenter l'écart » : RT est négatif, mais le produit RT·tC·tH change de
signe avec tC et tH. Un test que j'écrivais pour cette affirmation l'a
démentie. La vraie raison est plus simple : sans terme croisé, l'écart vaut
√(tL²+tC²+tH²) ≥ |tL| par construction, donc la coupure de `nearest` reste
exacte sans rien supposer d'aucun signe.

#### Ce que la photo dit d'autre, et qui n'est pas un défaut

Le vélo est un cas difficile, et la chaîne le dit d'elle-même avant de
commencer : deux teintes de la porte n'existent pas dans la palette (16 et 12
ΔE du plus proche). La palette LEGO n'a **aucun** neutre sombre entre Black
(L\*=5) et Dark Bluish Grey (L\*=46) : toute la porte tombe dans ce trou.
Aucune métrique ne comble un trou de palette.

Et le tramage y est un mauvais marché : +42 % de pièces et 431 tuiles isolées
de grain pour 2,3 ΔE de pire cas. La chaîne l'annonce désormais au lieu de le
décider en silence — `blending_tiles` dit que l'œil ne fond jamais deux tuiles
de 8 mm à aucune distance, donc ce grain se verra.

---

### 5.54 Ce que la photo réelle a ouvert d'autre : le trou de palette et les tuiles isolées

Deux mesures faites dans la foulée du § 5.53, l'une qui ferme une question,
l'autre qui gagne partout.

#### Le trou de palette est réel, et il n'est pas de mon fait

La porte du vélo tombe entre L\*=5 (Black) et L\*=46 (Dark Grey). Dans cette
bande, **les seuls solides quasi neutres sont Black (chroma 8,5) et Dark Brown
(22,6)** — tout le reste est saturé. Les vrais neutres qui rempliraient le trou
existent, et mon filtre les écarte à juste titre :

| couleur | L\* | chroma | finition |
|---|---:|---:|---|
| Rubber Black | 12,7 | **0,0** | caoutchouc |
| Pearl Dark Grey | 37,3 | **0,7** | nacrée |
| Metallic Black | 15,3 | 8,3 | métallisée |

Mesure de ce que coûte le filtre sur cette photo :

| palette | couleurs | ΔE/tuile | pire tonal |
|---|---:|---:|---:|
| solides seules (actuel) | 80 | 7,82 | 10,84 |
| + nacrées | 93 | 7,39 | 10,84 |
| tout sauf transparent | 127 | **4,25** | **5,59** |

Le filtre coûte 3,6 ΔE — mais l'essentiel du gain vient de couleurs qu'on ne
peut pas commander en tuile 1×1 (caoutchouc, chrome). **Aucune métrique ne
comble un trou de palette**, et l'ouvrir en grand produirait une liste de course
incommandable. Question fermée : le filtre reste, et la chaîne prévient déjà
quand une photo tombe dans le trou.

#### Les tuiles isolées : un gain qui va dans les deux sens

Une tuile dont aucune des quatre voisines ne partage la couleur est presque
toujours un artefact de quantification. Elle coûte une pièce et brise la suite
qui la traverse. `denoise` lui donne la couleur dominante de ses voisines, sous
deux conditions — au moins deux voisines d'accord, et pas plus de 4 ΔE de
dégradation par rapport à la photo.

| Image | Pièces | Tuiles isolées | ΔE par tuile |
|---|---|---|---|
| vélo | 1124 → **1069** | 142 → **91** | 7,82 → 7,84 |
| tournesols | 1091 → **1047** | 66 → **14** | 6,16 → 6,19 |
| portrait | 1401 → 1395 | 31 → **20** | 10,55 → 10,56 |

La deuxième condition n'est pas décorative : c'est elle qui protège un œil
sombre au milieu d'une joue — isolé, mais dont l'effacement coûterait bien plus
que quatre ΔE. Un test l'exige.

---

### 5.55 Les deux dernières décisions, prises — et la table qui s'importe

Il restait deux « décisions du propriétaire ». Elles m'ont été déléguées. Voici
ce que j'ai décidé, et pourquoi.

#### `LDConfig.ldr` : NON, on ne le redistribue pas

La licence CC BY 2.0 fournie avec LDraw définit l'Œuvre comme les pièces portant
`0 !LICENSE Redistributable under CCAL version 2.0`. `3001.dat` la porte —
c'est ce qui a permis d'en tirer les conventions d'axes pour l'export LDraw
(§ 5.39). **`LDConfig.ldr` ne la porte pas.**

Une délégation de décision technique n'est pas un consentement éclairé à un
risque juridique sur le dépôt de quelqu'un d'autre. Je ne commets pas un fichier
dont je n'ai pas pu confirmer la licence. C'est aussi la discipline du projet
appliquée à elle-même : ne jamais recopier une donnée qu'on n'a pas vérifiée.

Ce que j'ai fait à la place, pour que l'absence cesse de coûter : la recherche
lit désormais **`LDRAWDIR`**, la variable que la distribution LDraw pose
elle-même et que tous ses outils lisent — demander à l'installation où elle est
plutôt que de le supposer. Plus quatre emplacements d'installation de plus
(Stud.io sous Windows, la bibliothèque de pièces de Studio sous macOS,
`~/Documents/LDraw`).

#### La table BrickLink : elle s'IMPORTE, elle ne se recopie pas

Je disais depuis le début ne pas pouvoir la fournir sans l'inventer. C'était
vrai, et j'avais arrêté de chercher trop tôt. **LDConfig contient le LEGOID** —
l'identifiant de couleur du système LEGO — en commentaire au-dessus de chaque
couleur, pour 131 de ses 162 entrées. BrickLink publie le même identifiant dans
son export de couleurs.

La correspondance se **déduit** donc, en deux passes ordonnées par la confiance :

1. **par LEGOID** — exact, c'est le même numéro des deux côtés ;
2. **par nom normalisé** — `Dark_Bluish_Grey` et `Dark Bluish Gray` désignent la
   même couleur ; le tiret bas et l'orthographe ne sont pas des différences de
   couleur. Employé seulement quand le LEGOID manque.

Ce qui ne s'apparie ni par l'un ni par l'autre est **rendu, pas deviné**.

Et un refus sec n'aide personne : la chaîne écrit `couleurs_a_completer.csv`,
un gabarit qui liste exactement ce qui manque avec le nom, la valeur RVB et le
LEGOID de chaque couleur. Une ligne remplie, on repasse le fichier en
`--bricklink`, et c'est fini. Le lecteur accepte les deux formats sans qu'on ait
à lui dire lequel on tient, ignore les commentaires en fin de ligne — c'est ce
que le gabarit produit — et traite une ligne vide comme une absence et non
comme une erreur.

**Ce que je n'ai pas fait, et ne ferai pas** : recopier une seule correspondance
de mémoire. Une liste de course avec une couleur inventée est pire qu'une liste
incomplète : la seconde se voit, la première se paie à la livraison.

---

### 5.56 « Peut-on commander directement chez LEGO ? » — oui, et ce que ça exige

La question était factuelle et portait sur un service extérieur qui change. Je
suis allé vérifier plutôt que de répondre de mémoire, et la réponse a une moitié
que je n'attendais pas.

#### Ce qui existe

Pick a Brick a un bouton **« Upload list »** : un CSV à deux colonnes,
`elementId,quantity`, jusqu'à **400 références différentes** par envoi. Ce n'est
pas un projet ni une rumeur, c'est en service.

#### Le mur, et il est réel

Le fichier ne veut pas le numéro de **moule** — 3024, 3020, 2431, ceux que
notre nomenclature porte — mais l'**element id** : le numéro qui désigne un
moule **dans une couleur**. Et ce numéro est **attribué, pas calculé**. Il
n'existe aucune fonction de (moule, couleur) vers element ; deux couleurs
voisines d'une même pièce ont des numéros sans rapport. On ne le déduit pas de
ce qu'on a.

C'était exactement la situation de la table BrickLink en § 5.55, à un détail
près qui la rend plus dure : là-bas il fallait apparier **162 couleurs**, ici il
faudrait connaître un numéro par **combinaison** moule × couleur. Le recopier de
mémoire n'était pas envisageable ; ça ne l'est pas davantage ici, et à plus
grande échelle.

#### Ce que j'ai fait

La même chose qu'en § 5.55, pour la même raison : **on importe.**
`bfk001/pickabrick.py` lit un catalogue d'elements fourni par l'utilisateur —
celui que publie Rebrickable, celui que publie BrickLink, ou n'importe quel
fichier portant les trois colonnes utiles — et écrit `commande_lego.csv`. Les
colonnes sont reconnues **à leur en-tête**, jamais à leur position : aucun de
ces catalogues ne promet un ordre, et l'un d'eux l'a déjà changé.

#### Le refus qui est le cœur du module

Une colonne `color id` **nue** est refusée. Le numéro 71 vaut `Light Bluish
Gray` chez LDraw, un tout autre gris chez BrickLink, autre chose encore
ailleurs. L'interpréter au hasard ne donnerait pas une liste incomplète mais une
liste **fausse** : des pièces de la mauvaise couleur, livrées, payées,
inutilisables — et personne ne s'en apercevrait avant le colis. Il faut donc
soit une colonne d'identifiants LEGO (que LDConfig nous donne aussi, par son
LEGOID), soit des **noms** de couleur, soit le second fichier qui dit à quoi les
numéros correspondent. Chez Rebrickable, c'est `colors.csv`, à côté de
`elements.csv`, sur la même page.

#### Le défaut que ce refus a failli laisser passer

En écrivant la reconnaissance des colonnes, j'ai cherché la colonne de nom par
préfixe : `color`. Sur un export dont les en-têtes sont `Item No, Color ID,
Color Name, Code`, ce préfixe attrape **`Color ID`** avant `Color Name`. On
aurait alors lu « 86 » comme un *nom* de couleur, aucune correspondance ne
serait tombée juste — et **aucune erreur ne se serait levée** : le fichier
produit aurait simplement été vide ou faux, sans rien dire. C'est le mode de
panne que tout ce module existe pour empêcher, et je venais de l'introduire dans
son propre lecteur.

La correction est une liste d'en-têtes qu'une autre colonne revendique
exactement, exclue de la recherche par préfixe. Le test qui la garde ne vérifie
pas un cas particulier : il vérifie qu'**aucune clé de couleur de la table lue
n'est un nombre**. Une clé numérique dans une table indexée par nom est
impossible ; c'est la propriété, pas l'exemple.

#### Une différence assumée avec l'export BrickLink

`dumps_wanted_list` **refuse** d'écrire une commande BrickLink incomplète.
`dumps_upload` écrit quand même, et livre à côté la liste de ce qui manque. Ce
n'est pas une inconséquence : le mode de panne n'est pas le même.

| | BrickLink | Pick a Brick |
|---|---|---|
| Un lot non apparié obligerait à… | **deviner un code couleur** | rien : la ligne est **absente** |
| L'erreur se constate… | à la **livraison** | à l'**upload**, liste en main |
| Donc | refuser tout | écrire, et nommer les manquants |

Perdre les 45 autres lots pour un lot exotique ne protégerait de rien.
`pieces_sans_element.csv` nomme chaque manquant avec son LEGOID, de quoi le
chercher à la main en trente secondes.

#### Deux détails qui ne sont pas des détails

**`3070b` et `3070`.** LDraw écrit `3070b` la tuile 1×1 à rainure, pour la
distinguer de `3070a` qui n'en avait pas ; LEGO ne fabrique plus que la
rainurée et lui donne le numéro de moule `3070` tout court. Selon la colonne
qu'on lit dans le catalogue, on tombe sur l'une ou sur l'autre. L'écriture
exacte est donc essayée **en premier**, la troncature n'est qu'un recours — et
le nombre de lots qui en ont eu besoin est **compté et affiché**. C'est la seule
correspondance de ce module qui ne soit pas littérale ; elle se déclare.

**La limite de 400.** Au-delà, l'envoi échoue en bloc, et rien ne dit que c'est
le *nombre de références* qui gêne. La chaîne découpe donc en
`commande_lego_1.csv`, `commande_lego_2.csv`… Le test ne vérifie pas le
découpage ligne à ligne : il vérifie que **rien n'est perdu et rien n'est en
double**, ce qui est tout ce qu'un découpage doit promettre.

#### Ce que ce dépôt ne saura jamais

Qu'un element **existe** au catalogue ne dit rien de sa **disponibilité**. Pick
a Brick a son propre stock, variable selon le pays et le jour. Aucun prix,
aucune disponibilité n'est inventé ici — la chaîne le dit dans son journal à
chaque fois. C'est l'envoi lui-même qui tranchera.

#### Une décision d'interface, prise sans demander

Dans l'atelier, ces catalogues se donnent **au lanceur**, pas à chaque photo :
`app_lego_art.py --elements … --elements-couleurs …`. Un catalogue d'elements
est une propriété de l'**installation**, pas de l'œuvre ; c'est toujours le même
fichier. Le demander à chaque fabrication alourdirait la page sans rien
apporter. Et une erreur de lecture arrête le lanceur au démarrage plutôt que de
se découvrir après avoir fabriqué une mosaïque.

---

### 5.57 « Il faut qu'on puisse commander facilement » — et ma décision d'hier était à moitié fausse

Hier (§ 5.56) j'ai décidé que les catalogues de commande se donnent **au
lanceur**, parce qu'ils sont une propriété de l'installation et pas de l'œuvre.
La moitié « une fois, pas à chaque photo » était juste. **La moitié « au
lanceur » était fausse** : le lanceur est une ligne de commande, et tout
l'intérêt de l'atelier est qu'on n'y touche pas. J'avais raisonné sur la
*portée* et conclu sur l'*endroit*. Ce ne sont pas la même question.

#### Ce que « facilement » exigeait vraiment

Compté depuis la photo, commander demandait : trouver trois fichiers, les
décompresser, retenir trois options de ligne de commande, relancer le serveur,
fabriquer, télécharger un ZIP, l'ouvrir, y trouver le bon fichier, aller sur le
bon site, trouver le bon bouton. Dix étapes dont sept hors de l'app.

Ce qu'il en reste : déposer les fichiers **dans la page** (une fois, jamais
plus), fabriquer, cliquer sur le bouton de la boutique. Trois.

#### Le fait extérieur qui décide de la forme des deux boutons

Les deux boutiques n'importent **pas** de la même façon, et je l'ai vérifié
plutôt que de le supposer :

| | Ce qu'elle accepte | Donc le bouton |
|---|---|---|
| **LEGO Pick a Brick** | un **fichier** CSV `elementId,quantity` | télécharge le fichier |
| **BrickLink** | un **collage** — son formulaire ne prend pas de pièce jointe | met le XML dans le presse-papier |

Faire deux boutons identiques aurait été plus propre à écrire et faux à
l'usage : sur BrickLink, un fichier téléchargé ne sert à rien.

Le presse-papier direct n'existe que sur une **origine sûre**. `127.0.0.1` en
est une par définition ; une adresse de réseau local (`--adresse 0.0.0.0`) n'en
est pas une. D'où la zone de texte de secours, déjà sélectionnée, et un test
qui accepte les deux issues — parce que les deux sont des succès.

#### Ce qu'on garde sur le disque, et pourquoi ce n'est pas le catalogue

« Une fois » ne veut rien dire si le fichier repart au redémarrage. Mais écrire
un `elements.csv` complet (des mégaoctets, des centaines de milliers de lignes)
pour en relire trente références serait absurde.

Ce qui est écrit est donc ce qu'on a **retenu** : les entrées gardées, avec
leurs couleurs désignées par leur **nom**. Deux conséquences, et la seconde ne
m'était pas venue tout de suite — le fichier gardé est **auto-suffisant** : il
se relit par le même lecteur que n'importe quel catalogue, et le second fichier
(`colors.csv`) n'est plus nécessaire au redémarrage suivant.

#### Le défaut que je venais d'introduire dans mon propre garde-fou

Un test disait depuis longtemps : *aucune adresse absolue dans la page*. Mes
trois liens de commande le faisaient échouer.

La tentation était d'assouplir le test. Ce qu'il protégeait est pourtant réel —
la page ne doit charger **aucune ressource** extérieure. Mais un **lien qu'un
humain clique** n'est pas une ressource : il ne part que s'il le décide. Le
test disait « aucune adresse » là où il voulait dire « aucune ressource ».

Il dit maintenant les deux choses séparément : aucun `src=`, `<link>`,
`@import` ni `url(http)` — et la liste **exhaustive** des trois destinations
autorisées, qu'une quatrième ajoutée distraitement ferait échouer. Plus strict
qu'avant, pas moins.

Et comme deux des trois liens sont **fabriqués par le script**, ils n'existent
pas dans le HTML servi : leur `target` et leur `rel=noopener` se vérifient dans
le vrai navigateur, seul endroit d'où on peut les regarder.

#### Deux défauts trouvés en relisant, dont un que je m'apprêtais à écrire

**Un verrou qui ne tenait pas ce qu'il annonçait.** J'avais mis les deux
catalogues sous verrou au moment du remplacement, en écrivant en commentaire
qu'une fabrication verrait « les anciens ou les nouveaux, jamais un mélange ».
C'était faux : `fabriquer` les lisait **hors** du verrou, un à un. Une
fabrication tombant pile entre les deux lectures aurait employé le nouveau
catalogue d'elements avec l'ancienne table de couleurs. Le commentaire
promettait ce que le code ne faisait pas — la pire des deux situations, parce
qu'il décourage de vérifier. Corrigé en prenant les deux ensemble.

**Une bombe de décompression.** Accepter un `.csv.gz` déposé dans la page était
le bon choix : demander de décompresser d'abord, c'est perdre la moitié des
gens. Mais `gzip.decompress` alloue tout ce que le fichier contient avant qu'on
puisse dire non. Un `.gz` de 200 Ko en produit 200 Mo. On lit maintenant par
morceaux avec un plafond, et le test construit vraiment la bombe.

#### Ce qu'un test a attrapé dans la documentation

Le contrôle des options documentées ne lisait que `demo_lego_art.py`. Il a
signalé `--memoire` et `--sans-m` comme inexistantes. Deux vrais défauts d'un
coup : il ne regardait pas le lanceur de l'atelier, et j'avais écrit
`--sans-mémoire` **avec un accent** dans le README quand l'option s'écrit
`--sans-memoire`. Une option documentée qui n'existe pas envoie l'utilisateur
dans le mur ; le contrôle lit maintenant les deux façades.

#### Une décision revue, dite ici parce qu'elle contredit § 5.56

`Atelier()` sans dossier n'écrit **rien** hors de ce qu'on lui demande. Donner
un dossier, c'est demander qu'on s'en souvienne. Une bibliothèque n'a pas à
toucher au dossier personnel de qui l'importe parce que c'est pratique pour
l'application — et c'est le lanceur, pas le module, qui décide.

#### Et un ajout minuscule qui change l'usage

`liste_de_course.csv` — la liste **lisible**, celle qu'on ouvre pour chercher
une pièce à la main — gagne une colonne `element_id` dès qu'un catalogue est
chargé. Le fichier d'envoi ne porte que deux colonnes muettes ; celui-ci est
celui qu'on lit.

Les deux sortent de la **même fonction**, `element_pour`. Deux implémentations
divergeraient un jour, et le désaccord passerait inaperçu : personne ne compare
un CSV à deux colonnes avec une liste de courses. Un test le fait.

---

### 5.58 Un parcours de graphe quadratique, et un profileur qui m'a menti

« Vois-tu des choses à optimiser ? » — j'ai mesuré plutôt que de supposer, et
la mesure a donné une réponse que je n'attendais pas, plus une leçon sur
l'outil de mesure lui-même.

#### Où passait vraiment le temps

Sur une mosaïque de 96 tenons (3 450 pièces), **les deux tiers du temps
étaient dans la validation**, pas dans le solveur. C'est normal et voulu — le
noyau refuse de livrer ce qu'il n'a pas vérifié. Mais un tiers de cette
validation partait dans une bêtise.

`check_h4_floating` demandait, **pour chaque pièce non fondée** : « la
composante connexe de cette pièce contient-elle une fondation ? » Et chaque
question refaisait le parcours entier du graphe. Or H5 exige que tout se
tienne : la composante est donc unique et contient tout. On refaisait *n*
parcours de *n* pièces.

Les composantes ne dépendent pas de la pièce par laquelle on interroge. Une
seule passe suffit.

| Format | Pièces | H4 avant | H4 après | |
|---|---|---|---|---|
| 48 tenons | 951 | 0,13 s | 0,001 s | **225×** |
| 96 tenons | 3 201 | 2,03 s | 0,003 s | **632×** |
| 128 tenons | 5 328 | 9,80 s | 0,006 s | **1 532×** |

Le rapport grandit avec la taille, parce que c'est un changement d'ordre de
grandeur et non un réglage : *O(n·(n+e))* devient *O(n+e)*. Sur la chaîne
complète, 128 tenons passe d'environ 27 s à **17 s**.

Le remplacement ne vaut que s'il rend **exactement** la même chose, ordre des
violations compris. Un tirage de 300 graphes aléatoires — composantes
multiples, pièces isolées, fondations absentes ou partout — le vérifie, et
refuse de passer si le tirage ne produit jamais de violation.

#### Le profileur m'a menti, et voici comment

Après cette correction, `cProfile` désignait un nouveau coupable :
`_require_int`, la vérification que chaque coordonnée est un entier de ℤ.
11,4 millions d'appels, 4,3 s sur 50 — 8,6 % du temps.

J'ai écrit le chemin rapide (`type(value) is int` d'abord, le test complet
ensuite pour les sous-classes), prouvé le verdict identique sur tous les cas
qui peuvent passer par là, et mesuré : **40 % de gain sur la fonction, moins
de 2 % sur la chaîne.**

L'écart n'est pas une erreur de mesure, c'est la nature de l'outil.
`cProfile` facture son propre coût **par appel** : plus une fonction est
appelée, plus il la gonfle. Une fonction de trois lignes appelée onze millions
de fois est exactement le pire cas. Le profileur ne m'a pas montré où était le
temps — il m'a montré où étaient les **appels**.

Ce qui l'a démasqué : `check_h4_floating`, lui, n'apparaissait pas comme un
point chaud par temps propre — son coût était *cumulé*, dans `_component`.
Deux lectures du même rapport, deux conclusions opposées. La bonne était celle
qu'un chronomètre sur la fonction entière confirmait.

Le chemin rapide est gardé — deux lignes, verdict prouvé identique — mais son
commentaire dit maintenant le chiffre vrai, pas celui du profileur.

#### Ce que je n'ai pas fait

`check_h2_collision` reste le premier poste. Il décompose exactement les
solides, boîte par boîte, et c'est ce qui rend le contrôle exact plutôt
qu'approché. Je n'y touche pas pour grappiller : le gain est incertain, le
risque porte sur le cœur du contrat, et la chaîne est maintenant assez rapide
pour qu'un utilisateur n'attende jamais.

Je n'ai pas non plus fait ruisseler le journal en direct dans la page. Ce
serait la bonne réponse à une longue attente — mais l'attente réelle est de
1,5 s sur les formats courants. On n'anime pas ce qu'on ne voit pas.

---

### 5.59 « Ça fait très ancien » — la page refaite, et le comparateur

Le reproche était juste. La page était un formulaire d'outil interne : huit
contrôles empilés, du gris 13 px sous chacun, un aplat de cartes sans identité,
et l'image — la seule chose que l'utilisateur veut voir — traitée comme une
donnée parmi les chiffres.

#### Ce que j'ai changé, et pourquoi chaque chose

**Trois gestes numérotés** au lieu de huit réglages : ① la photo ② le format
③ fabriquer. Tout le reste se replie — et se replie **sous** le bouton. La
version précédente enterrait l'action principale derrière deux sections
repliées ; on ne cherche pas le bouton « Fabriquer » après « Catalogues de
commande ».

**Des pastilles plutôt que des champs.** Le format se clique (32 / 48 / 64 /
96, avec les centimètres), la couleur du cadre se choisit à l'œil sur des
pastilles de couleur. Une pastille n'est pas un doublon du champ : c'est le
champ qu'elle remplit, et un test vérifie les deux sens — cliquer écrit, taper
une valeur libre n'enfonce aucune pastille. S'ils divergeaient, on fabriquerait
une taille et on en lirait une autre.

**Un bouton qui s'enfonce sur son épaisseur**, comme une brique qu'on presse.
Une ombre portée de 4 px, `translateY(3px)` au clic. C'est du CSS, ça ne coûte
rien, et ça donne à l'objet la matière qu'il décrit.

**Des tenons qui se posent pendant la fabrication.** Indéterminé et assumé : la
chaîne ne rend pas d'avancement, et une barre qui progresserait toute seule
mentirait.

Rien n'est chargé de l'extérieur. La frise de tenons est un
`radial-gradient` répété, pas une image — la page doit rester utilisable hors
ligne, et le test qui l'exige n'a pas bougé.

#### Le comparateur, et le piège qu'il fallait éviter

Le geste le plus satisfaisant pour un outil photo → mosaïque, c'est de tirer
une poignée et de voir l'une devenir l'autre. La tentation était de superposer
la photo d'origine. **Ç'aurait été faux.**

L'œuvre est rognée au rapport de la mosaïque, moyennée par tenon, et entourée
d'un cadre que la photo n'a pas. Superposer la photo brute produit un
glissement — et un glissement fait **mentir** la comparaison : on croirait
juger la quantification alors qu'on regarde un décalage.

D'où `apercu_source.png` : la photo passée par le **même** cadrage, le **même**
rééchantillonnage et le **même** cadre que la grille quantifiée. Elle se
superpose au pixel près. Les tests le vérifient des deux côtés — mêmes
dimensions sur trois épaisseurs de cadre, même couleur au coin du cadre, et
dans le navigateur les deux `naturalWidth` mesurés.

Un effet de bord que je n'avais pas cherché : **elle montre ce que le cadrage a
coupé**, qui n'était visible nulle part jusqu'ici.

Et là où la comparaison n'a pas de sens — la vue des joints, le relief éclairé
— le comparateur disparaît, parce qu'il comparerait deux choses différentes.

#### Deux défauts que seul le thème sombre montrait

J'avais écrit `color: rgba(255,255,255,.7)` pour le sous-titre d'une pastille
enfoncée. En thème clair, le fond enfoncé est sombre : lisible. **En thème
sombre, ce fond devient clair**, et du blanc translucide dessus disparaît. Les
centimètres étaient invisibles pour la moitié des utilisateurs. Une couleur ne
se code pas en dur quand le thème inverse les rôles.

Et `29×29 cm` en 23 px gras débordait sa tuile. `clamp()` plutôt qu'une taille
fixe : le nombre doit tenir, pas le contraire.

Les deux ne se voient qu'en regardant — d'où les captures en clair, en sombre
et en 390 px de large avant de conclure.

---

### 5.60 Passe de contrôle : sept défauts, dont trois que j'avais écrits moi-même

« Vois ce qui peut buguer. » J'ai maltraité la chaîne plutôt que de la relire.

#### Ce qui ne casse pas

Vingt-trois entrées dégénérées — photo de 1 pixel, bande de 3 pixels de large,
mosaïque de 1 tenon, image unie, damier au pixel, palette d'une seule couleur,
cadrage aux deux extrêmes, quatre jeux de tuiles — **aucun plantage**. Refus
propres là où il en faut. Six fabrications simultanées : jetons distincts,
résultats identiques, plafond de cache respecté. Les nombres concordent entre
tous les fichiers livrés (nomenclature = pièces = lignes du `.ldr` = pièces du
`.json`) sur trois configurations. Pointe mémoire sur 12 Mpx : 154 Mo.

#### Quatre entrées qui partaient dans le mur

| Entrée | Avant | Maintenant |
|---|---|---|
| `cadre = 500` | **plus de 2 minutes**, aucune réponse | refus immédiat |
| `studs = 100 000` | erreur de mémoire après une longue attente | refus immédiat |
| `relief = 99` | accepté | refus immédiat |
| titre de 100 000 caractères | accepté, part dans le PDF | refus immédiat |

Le premier est le pire : depuis la page, un `500` tapé à la place de `2`
bloquait le serveur sans rien dire. Les bornes ne sont pas des limites de goût,
et elles se disent comme telles — « un cadre de 500 tenons n'entoure plus
rien », « une œuvre plus grande se fait en plusieurs, côte à côte ».

#### Le défaut qui était dans chaque notice livrée

Je n'ai pas de rasteriseur PDF ici, et le visualiseur de Chromium ne rend rien
en mode headless. J'ai donc vérifié la mise en page **numériquement** : chaque
aplat, chaque image, chaque ligne de texte, contre les bords de la page et les
marges. C'est plus rigoureux que de regarder.

Résultat : sur **sept configurations sur huit**, la page du cadre écrivait une
phrase qui débordait la marge droite de **109 points** — soit 69 points *au-delà
du bord du papier*. La phrase était coupée à l'impression, sur la dernière page
de toute notice avec cadre, c'est-à-dire **par défaut**, depuis que j'ai ajouté
le cadre (§ 5.52).

La cause est instructive : il existait `_couper`, qui découpe une liste de
références sur ses séparateurs « · », et **rien** pour replier une phrase. Sans
outil, j'avais écrit les trois phrases d'un seul tenant. Le manque d'un
replieur de prose *est* le défaut ; `_replier` existe maintenant, et un test
vérifie la propriété — rien ne sort de la page, aucune ligne ne dépasse les
marges, deux images d'une même page ne se recouvrent pas — sur huit fascicules
aux réglages différents.

#### Sept dixièmes du travail d'image étaient une répétition exacte

Une photo de téléphone en 48 tenons prenait **27 secondes**, contre 3,4 s pour
la même mosaïque depuis une petite image. Le profil désignait `resample_box`.

En instrumentant plutôt qu'en supposant : la chaîne réduisait la **même** image
de 9 Mpx **huit fois** — deux pour quantifier, quatre pour mesurer la fidélité,
une pour le débruitage, une pour l'aperçu de la source que je venais d'ajouter.

La tentation était de réduire une fois en deux étapes. **C'eût été faux** : une
moyenne de boîte en deux temps n'égale la moyenne en un temps que si les
découpages tombent juste, et 4000 ne se divise pas en 192 groupes égaux. La
sortie aurait changé, un peu, silencieusement.

Ce qui est exact, c'est de ne pas refaire deux fois le même calcul. Un cache
indexé par l'**identité** de l'image (hacher 36 Mo coûterait ce qu'on
économise) : **27 s → 4,5 s**, et un test compare les empreintes SHA-256 de
tous les fichiers livrés, cache actif contre cache neutralisé, sur quatre
configurations. Une optimisation qui change la sortie n'est pas une
optimisation.

| Photo | Mosaïque | Avant | Après |
|---|---|---|---|
| 12 Mpx | 48 tenons | 27,1 s | **4,5 s** |
| 0,5 Mpx | 48 tenons | 3,8 s | 3,8 s |

La résolution de la photo ne compte presque plus : c'est la taille de la
mosaïque qui décide, ce qui est le bon comportement.

#### Et le défaut de ma propre correction

Mon premier cache gardait une référence **forte** sur l'image d'entrée, pour
que son identifiant ne puisse pas être recyclé. Raisonnement juste, conséquence
mauvaise : jusqu'à cent mégaoctets retenus entre deux fabrications, pour rien.

Une référence **faible** supprime la fuite — et déplace la charge de la preuve.
Un identifiant se recycle dès que l'objet meurt ; une nouvelle image née à
l'adresse d'une ancienne recevrait alors la réduction de l'ancienne, et la
mosaïque sortirait fausse **sans une ligne d'erreur**. La vérification
`garde() is image` n'est donc plus une ceinture de plus : c'est elle qui rend
le procédé correct. Un test crée et détruit quarante images alternées pour
forcer le recyclage.

C'est le troisième défaut de cette passe que j'avais écrit moi-même — après la
phrase qui débordait et le cache qui fuyait. Les quatre autres étaient des
entrées non bornées.

---

### 5.61 Une vraie photo de téléphone, et le défaut qu'elle a trouvé en cinq minutes

Deuxième photo réelle du projet, et la deuxième fois qu'elle trouve mieux que
mes images synthétiques.

#### Ce que le fichier contenait

4,3 Mo, JPEG d'iPhone. **Orientation EXIF = 6** — la photo est stockée
couchée. Segments `APP1 Exif`, `APP2 ICC_PROFILE`, `APP10 AROT`.

**Pas de XMP.** Donc pas de carte de profondeur : ce n'est pas une photo prise
en mode Portrait. Le chemin `embedded_depth` — GDepth, XMP étendu, Dynamic
Depth Container — **reste non testé contre un vrai fichier**. Il faut le dire
plutôt que de laisser croire que cette photo l'a couvert.

Ce qui a été vérifié, et qui l'est pour la première fois sur un fichier réel :
le décodeur JPEG au huitième (3024×4032 → 378×504), l'orientation EXIF
appliquée dans le bon sens, le cadrage 48×64 aux proportions de la photo.
**Aucune violation d'invariant, aucun plantage.**

#### Mon œil s'est trompé avant le code

Le débardeur paraît blanc sur la photo. Il ressort **sombre** dans la mosaïque,
et j'ai d'abord cru à un défaut de quantification. Mesure : le pixel vaut
`#535D72`, **L\* = 39**. La personne est à contre-jour ; le vêtement est dans
son ombre. Notre système visuel corrige l'éclairement, la mosaïque non — et
elle a raison, elle rend ce que la photo contient.

C'est utile à écrire : la fidélité se mesure sur les pixels, pas sur ce qu'on
croit voir.

#### Le vrai défaut : décider sur une grille qu'on modifie ensuite

Le journal annonçait « tramage : appliqué — 710 tuiles isolées », puis
« nettoyage : 673 tuiles isolées effacées ». La chaîne **tramait, puis effaçait
son propre tramage**.

Mesuré sur cette photo :

| | par tuile | tonal 4×4 moyen | tonal 4×4 **pire** | tuiles isolées |
|---|---|---|---|---|
| sans tramage, brut | 9,79 | 7,45 | 14,65 | 58 |
| avec tramage, brut | 10,52 | **3,96** | **9,45** | 710 |
| sans tramage, **livré** | 9,80 | 7,57 | 14,65 | 27 |
| avec tramage, **livré** | 9,99 | 6,70 | **14,65** | 106 |

Le critère « auto » compare le **pire écart tonal** et exige 1 ΔE de gain. Sur
les grilles brutes il voyait **+5,20** — franchement au-dessus du seuil. Sur la
grille réellement livrée, après nettoyage, le gain est **+0,00**.

Le nettoyage efface 604 des 710 tuiles tramées et, avec elles, tout l'avantage
qui justifiait le tramage. On payait **227 pièces** (+16 %) et tout le grain
visible pour un gain nul.

La cause est structurelle et banale : le tramage automatique et le nettoyage
des tuiles isolées ont été ajoutés à des moments différents (§ 5.x et § 5.54),
la décision vit dans `mosaic.quantize` et le nettoyage dans `pipeline.run`.
**Le module qui décide ne savait pas ce que l'appelant ferait ensuite.**

La correction est de juger les candidats **tels qu'ils seront livrés** :
`quantize(..., denoise_tolerance=…)`. Sur cette photo, le tramage est
désormais écarté — 1405 pièces au lieu de 1632, aucune perte sur la grille
livrée. Sur un ciel dégradé, le cas d'école, il reste choisi : le gain y
**survit** au nettoyage (+1,05). Deux tests gardent les deux sens, et le
premier vérifie d'abord que son image pose bien la question — gain franc avant
nettoyage, gain effacé après — sans quoi il ne prouverait rien.

#### Ce qui limite encore le rendu, et que le code ne peut pas corriger

La palette provisoire compte **douze couleurs**, avec un trou de clarté entre
L\* = 46 et L\* = 67 : exactement là où vivent un chemin de sable ensoleillé et
une silhouette à contre-jour. Le ciel part en blanc pur, les mi-tons
s'aplatissent. La chaîne le dit en tête de journal à chaque fabrication —
`LDConfig.ldr` introuvable, la palette officielle divise l'écart par deux — mais
elle livre quand même, et l'utilisateur voit d'abord le résultat.

Ce n'est pas un défaut de code. C'est la limite que l'installation d'une
palette officielle lève, et la seule chose que je puisse faire de plus est de
continuer à le dire clairement.

---

### 5.62 « Ajoute toute la bibliothèque » — et pourquoi je ne la commets toujours pas

En § 5.55 j'avais refusé de commettre `LDConfig.ldr` : le fichier appartient à
LDraw.org et ne porte **aucune mention de licence** — je viens de le revérifier
sur le fichier lui-même, il n'y a ni `!LICENSE`, ni copyright, ni CCAL. Ce
refus tient, et il tient même quand le propriétaire du dépôt demande le
contraire : recopier une donnée dont on n'a pas vérifié la provenance est
exactement ce que ce projet s'interdit partout ailleurs.

Mais « je ne le commets pas » n'est une bonne réponse que si l'utilisateur a un
autre chemin. Il n'en avait pas : `--ldconfig CHEMIN` suppose qu'on a déjà
LDraw installé. **Le manque n'était pas le fichier, c'était l'installation.**

#### Ce que ça change, mesuré

Sur une photo réelle, à 48 tenons :

| | ΔE par tuile | pire écart tonal | trous de palette | pièces |
|---|---|---|---|---|
| 12 couleurs (secours) | 9,2 | 11,6 | 4 | 2 040 |
| **159 couleurs (80 solides)** | **6,8** | **8,2** | 2 | 2 254 |

Ce n'est pas un gain de métrique : c'est la différence entre un visage qui est
une tache rouge et un visage qui se lit.

#### L'installateur, et ce qu'il refuse

`installer_palette()` essaie trois sources dans l'ordre — les deux adresses
officielles de LDraw.org, puis le miroir que LPub3D distribue avec son
installateur — et dit laquelle il tente. Depuis ce conteneur, les deux
premières sont bloquées par le proxy et la troisième répond : **1,2 s**, 159
couleurs. Le mécanisme est donc vérifié de bout en bout sur le réseau réel ; la
joignabilité des deux adresses officielles ne l'est pas, et c'est écrit dans le
code plutôt que sous-entendu.

Ce qui est téléchargé est **vérifié avant d'être écrit** : au moins 100
couleurs dont 40 solides (LDConfig en compte 159 dont 80). Un portail captif
d'entreprise, un 404 renvoyé en HTML, un fichier tronqué : tous produisent
quelque chose qui n'est pas une palette, et **rien ne s'installe**. Une palette
silencieusement fausse ferait sortir toute la mosaïque à côté, sans une ligne
d'erreur — c'est le seul mode de panne qui compte ici. L'écriture passe par un
fichier `.partiel` puis un remplacement atomique : une coupure ne doit pas
laisser un demi-fichier là où on ira le lire.

L'adresse n'est **jamais** fournie par la page. Une URL qui viendrait du réseau
ferait de ce serveur un relais pour aller chercher n'importe quoi à la place de
qui l'héberge ; un test vérifie que `Atelier.installer_palette` ne prend aucun
paramètre.

#### Deux défauts que j'ai écrits en le faisant

**Une collision de noms.** Le lanceur assignait `palette = complete...` plus
bas dans la même fonction ; Python traite alors `palette` comme locale
**partout**, et mon `palette.installer_palette()` levait un `UnboundLocalError`
avant même de partir. Trouvé en lançant la commande, pas en la relisant.

**Une attente muette de trois minutes.** Trois sources à soixante secondes de
délai : sur un réseau qui bloque la première, le programme paraissait mort.
Vingt secondes suffisent à vingt-huit kilo-octets, et le programme dit
maintenant ce qu'il tente.

#### Un test qui testait la machine et non le code

Installer la palette ici a fait tomber un test :
`test_recherche_ne_rend_que_des_fichiers_lisibles` affirmait que
`find_ldconfig` rend `None` — ce qui n'est vrai que sur un poste où LDraw n'est
installé nulle part. Il passait par accident depuis le début.

Il isole désormais les emplacements système et les variables d'environnement,
et vérifie **les deux sens** : un chemin absent est ignoré, un fichier présent
est rendu. Sans le second, il passerait aussi sur une fonction qui rend
toujours `None`.

Le reste de la suite passe à l'identique avec 12 ou avec 80 couleurs — donc
rien n'y dépendait secrètement de la petite palette.

#### Et une validation du correctif de la veille

Le § 5.61 avait appris à la décision de tramage à juger la grille livrée. Avec
12 couleurs elle refusait le tramage sur la photo du vélo (gain livré : 0,00) ;
avec 80, elle l'accepte (**+3,64**). Le même critère, deux réponses opposées
selon ce que la palette permet — c'est exactement ce qu'on lui demande.

---

### 5.63 « Peux-tu être encore plus précis ? » — oui, et la mesure dit exactement où

Question à réponse mesurable. Deux nombres, et le premier réfute la moitié de
la question.

#### Le choix des couleurs est déjà optimal, et c'est démontrable

Le **plancher de la palette** est l'écart qu'on aurait si chaque tenon prenait
la meilleure couleur qui existe. C'est l'erreur incompressible à résolution et
palette données.

Sur une photo réelle, 48 tenons, 80 couleurs solides : plancher **6,68**,
obtenu **6,68**. Marge de progrès : **+0,00**.

Sans tramage, chaque tenon prend le plus proche — donc le résultat *est* le
plancher par construction, et l'égalité vérifie surtout que `nearest` ne se
trompe jamais. Mais la conséquence compte : chercher un meilleur algorithme de
choix de couleur est perdu d'avance. La chaîne le dit maintenant dans son
journal, pour deux centièmes de seconde.

#### L'écart par tuile ne répond pas à la question posée

| tenons | écart par tuile | détail (grille commune) |
|---|---|---|
| 32 | 6,79 | 9,97 |
| 48 | 6,76 | 9,07 |
| 64 | 6,72 | 8,56 |
| 96 | 6,66 | 7,85 |
| 128 | — | 7,50 |

Tripler la résolution gagne **0,13** sur l'écart par tuile. Pourquoi ? Parce
que cette mesure compare chaque tuile à la zone qu'elle remplace, et que la
zone rétrécit avec le nombre de tenons. Elle mesure la **fidélité de couleur**,
bornée par la palette — pas du tout ce qu'on gagne en **détail**.

D'où `detail_gap`, qui compare aux mêmes points physiques quelle que soit la
taille : 10,0 à 32 tenons, 7,5 à 128. Là, le gain est réel.

#### Deux pièges, tombés l'un après l'autre

**Une grille trop grossière.** Ma première mesure employait 120 points de large
pour comparer jusqu'à 128 tenons. Elle ne mesurait plus le détail d'une
mosaïque plus fine qu'elle : elle le ratait. Résultat : 128 tenons ressortaient
**pires** que 96. J'ai failli conclure à un optimum autour de 96 — l'artefact
venait de ma mesure, pas de l'œuvre. Avec une grille trois fois plus fine que
la plus fine des mosaïques, la courbe est monotone.

**Une grille variable.** Ma deuxième version la calculait depuis la taille de
chaque mosaïque. Chaque format était alors mesuré sur sa propre échelle, ce qui
ne compare rien. La grille se calcule une fois, depuis la plus grande des
tailles, et sert à toutes. La fonction l'exige en paramètre et refuse une
grille plus grossière que la mosaïque, plutôt que de la déduire silencieusement.

Deux fois le même défaut, sous deux formes : **l'instrument de mesure faisait
partie de ce qui était mesuré.**

#### Ce que ça donne comme conseil

| format | pièces | détail | gain | pièces par 0,1 de gain |
|---|---|---|---|---|
| 32×48 | 1 060 | 9,89 | | |
| 48×71 | 2 282 | 8,93 | +0,95 | 128 |
| 72×106 | 4 606 | 8,32 | +0,61 | 380 |
| 96×142 | 7 871 | 7,75 | +0,58 | 567 |

Le coût d'un pas de finesse **triple** entre 48 et 96 tenons. C'est
l'arbitrage le plus conséquent de toute la chaîne — on engage des milliers de
pièces — et rien n'aidait à le prendre.

Il ne peut pas être tranché une fois pour toutes : un portrait lisse et une
façade ciselée n'ont pas le même point de rupture. Il se calcule **par photo**,
d'où `--conseil-format`. Dix secondes, et à la demande : c'est une question
qu'on pose une fois avant d'acheter, pas à chaque fabrication.

#### La réponse courte

**En couleur, non** — on est au plancher de ce que 80 couleurs permettent.
**En détail, oui**, et chaque pas coûte trois fois le précédent.

---

### 5.64 Le conseil de format dans la page — et le même défaut, refait un commit plus tard

Avant d'ajouter quoi que ce soit à l'interface, j'ai vérifié ce que je venais
de livrer. Bien m'en a pris.

#### Le conseil ne conseillait pas sur ce qu'il allait fabriquer

`conseil_de_format` quantifiait **de son côté** : sans cadre, sans nettoyage
des tuiles isolées, sans tramage automatique. Il annonçait donc des nombres de
pièces faux :

| format | annoncé | livré | écart |
|---|---|---|---|
| 32 tenons | 1 082 | 1 114 | −32 |
| 48 tenons | 2 282 | 2 254 | +28 |
| 72 tenons | 4 606 | 4 515 | +91 |

Le pire n'est pas l'ampleur, c'est que les erreurs **se compensaient à moitié**
— le cadre ajoute des pièces, le nettoyage en retire — et que les chiffres
*paraissaient* donc plausibles. Un utilisateur les emploie pour décider
d'acheter deux mille pièces.

C'est **exactement** le défaut du § 5.61, refait un commit plus tard : évaluer
une grille qui n'est pas celle qu'on livre. Deux fois la même erreur, c'est que
le problème n'était pas l'inattention mais la **duplication** — deux endroits
construisaient la grille, ils ont divergé.

D'où `grille_livree` et `mosaique_livree` : une seule fonction chacune,
appelée par la chaîne comme par le conseil. Vérifié à zéro pièce d'écart sur
sept configurations qui touchent chacune un maillon différent — sans cadre,
cadre épais, relief, jeu de tuiles large, sans nettoyage, tramage imposé.

#### La vignette que j'avais mise ne montrait rien

Premier jet : une vignette de l'œuvre entière, 56 pixels de large. À cette
taille, une mosaïque de 96 tenons et une de 32 se ressemblent **exactement**.
L'image censée montrer le gain de détail décorait.

Ce qui le montre : le **tiers central** de chaque candidat, affiché à largeur
constante. C'est le même morceau de la scène — la photo est la même —, et la
version fine y met trois fois plus de tuiles. La main et la montre du sujet
apparaissent progressivement de 32 à 96 tenons. Un test vérifie la propriété
qui compte : les largeurs *naturelles* croissent, les largeurs *affichées* sont
identiques.

#### Une troisième duplication, évitée celle-là

Le panneau de conseil devait envoyer les réglages courants. Ils étaient
construits en ligne dans le gestionnaire de soumission. Les recopier aurait
créé la même divergence que ci-dessus, dans le navigateur cette fois : un
conseil calculé avec un autre cadre ou un autre jeu de tuiles ne conseille
rien. `reglagesActuels()` lit le formulaire une seule fois, pour les deux.

Trois duplications rencontrées dans la même heure, dont deux déjà devenues des
bugs. C'est le motif de la journée, et il valait d'être écrit.

---

### 5.65 La notice tenait dans ses marges — mais disait-elle vrai ?

§ 5.60 avait vérifié la **géométrie** des pages : rien ne déborde, rien ne se
recouvre. Une notice peut tenir dans ses marges et raconter n'importe quoi.
Son contenu n'avait jamais été contrôlé.

Quatre propriétés, celles dont dépend la seule promesse qui compte — *si on la
suit, on obtient le modèle* :

| Propriété | Ce qu'un défaut coûterait |
|---|---|
| chaque pièce posée une fois et une seule | une pièce oubliée : le modèle ne tient pas ; en double : on en achète une de trop |
| chaque rangée couverte par une bande, une fois | une bande entière n'est montrée nulle part |
| une lettre par couleur, unique | sans lettre la notice imprime « ? » ; partagée, on pose la mauvaise sans le voir |
| l'encart de chaque bande = son contenu | on sort du sachet ce qu'il ne faut pas |

**Résultat : rien à corriger.** Sur sept configurations — relief, sections,
sans cadre, tuiles larges, tuiles rondes, palette bridée — le plan couvre
exactement les pièces du modèle, les bandes exactement les rangées, chaque
couleur a sa lettre, et la somme de tous les encarts fait toutes les tuiles.

#### Mon instrument était faux, encore une fois

Le premier passage a signalé « bande 0 : encart annonce 77 de trop, 77 de
moins » sur les trois configurations. Égalité parfaite entre le trop et le
moins : c'est la signature d'une erreur de **clé**, pas d'un défaut.

`pieces_of_band` rend `(design, LegoColor, quantité)` — le deuxième élément est
un objet couleur, pas un code. Je comparais des clés de natures différentes.
Aucun défaut du code, un défaut de ma mesure.

C'est la deuxième fois dans ce projet qu'un contrôle hâtif accuse à tort — la
première était le faux rapport sur `nearest` (§ 5.x), où je passais du Lab à
une fonction qui attend du RVB. Le réflexe qui sauve est le même : **une
symétrie trop parfaite dans un écart dénonce l'instrument, pas le sujet.**

Les quatre contrôles sont maintenant des tests permanents. C'était la dernière
surface livrée que rien ne gardait.

---

### 5.66 Deux photos, un défaut réel, et un remède que j'ai refusé de livrer

Deux photographies : deux Cavaliers sur un lit, et un lièvre de bronze dans une
vigne. Ni l'une ni l'autre ne porte de XMP — le chemin de la carte de
profondeur **reste non testé** contre un vrai fichier.

#### Ce qu'elles ont montré

Le lièvre a un **plancher de palette à 9,5 ΔE**, contre 6,7 à 6,9 pour les
autres. Les trous sont le ciel (`#92A0CC`, `#A1AED7` — un bleu-violet pâle) et
les verts d'herbe : **19 % des tuiles** à 10-12 ΔE de la couleur voulue. Le
LEGO ne fabrique pas ces teintes. Ce n'est pas un défaut d'algorithme, et la
chaîne atteint son plancher exactement.

#### Le défaut, trouvé en regardant

Sur la photo du vélo, le critère de tramage annonce **+3,64 ΔE** en faveur du
tramage, et la chaîne l'applique. J'ai rendu les deux versions côte à côte :
la version tramée est un **semis de confettis** blancs et bleus dans le ciel,
franchement moins belle que la nette.

La cause est structurelle : la justesse tonale se mesure sur la **moyenne** de
blocs de 4×4 tuiles, et une moyenne ne voit pas le grain qu'elle moyenne. Deux
damiers de tons opposés ont la même moyenne qu'un aplat. Le critère est
**aveugle au grain** — et `blending_tiles`, vérifié ici, dit qu'à 1 comme à 4 m
l'œil résout chaque tuile : le grain, lui, se voit toujours.

#### Le remède que j'ai construit, puis refusé de livrer

`detail_gap` (§ 5.63) compare aux mêmes points physiques sans moyenner : il
voit le semis. Sur les quatre photos réelles il classe comme mon œil. J'ai donc
ajouté une seconde condition : *le tramage doit gagner en tonalité sans coûter
en grain*.

Elle corrige bien le cas du vélo. **Mais elle refuse aussi le dégradé pur** —
où le tramage ne sème pas : il pose une ceinture d'une tuile le long de chaque
bord de bande, et cela adoucit vraiment la transition. Rendu et regardé : c'est
mieux.

| | perte de détail | verdict de l'œil |
|---|---|---|
| photo (vélo) | −0,13 | tramage **pire** |
| dégradé pur | −0,12 | tramage **meilleur** |

**La même grandeur, un verdict opposé.** Aucun seuil ne les sépare — la photo a
même le plus *gros* gain tonal des deux. La fraction de surface touchée sépare
presque (7,6 % contre 11,6-15,8 %), mais ajuster un seuil sur six points dont
deux jugés à l'œil, c'est inventer une constante et l'habiller en principe.

Un test existait précisément pour ce moment : *« le tramage automatique ne se
déclenche jamais »*. Il est tombé, et il avait raison — ma correction rendait
le mode `auto` muet partout.

**J'ai annulé la correction.** Échanger un défaut vérifié sur une photo contre
un autre vérifié sur un dégradé, en rendant vide un mode qui porte le nom
« auto », sur la foi d'un seul jugement à l'œil : ce n'est pas une amélioration,
c'est un déplacement de mon goût dans le code.

#### Ce que j'ai livré à la place

Le chiffre. La chaîne dit maintenant, quand elle applique le tramage, **ce
qu'il coûte en finesse locale** :

```
  tramage : applique — il gagne de la justesse tonale et laisse 791 tuiles
            isolees de grain.
            ce grain coute +0.40 delta E de finesse locale — le gain tonal se
            mesure sur des moyennes qui ne le voient pas.
            « --tramage aucun » si vous preferez la nettete.
```

Et la contradiction entre les deux mesures est **épinglée par un test** plutôt
qu'affirmée en prose : qui touchera au critère saura exactement ce qu'il
échange.

Mesurer et informer, plutôt que trancher en silence sur des preuves minces.

---

## 6. Où en est-on de la demande produit

> photo → modélisation LEGO Art hyper précise → liste de course → notice de montage

La chaîne **existe et tourne** : `python3 demo_lego_art.py photo.png --studs 48`.

| Étape | État | Ce qui manque |
|---|---:|---|
| Photo → analyse | **~99 %** | JPEG (au huitième — coût mesuré à 0,5 ΔE, § 5.31), PNG, PPM, orientation EXIF, rééchantillonnage en lumière linéaire, recadrage au bon rapport, quantification CIEDE2000 exacte, alerte sous 2 px/tenon, recadrage attentionnel par énergie de gradient. **Interface web** : glisser-déposer, réglages, aperçus, ZIP (§ 5.50). Manque : rien d'identifié. |
| → modélisation LEGO Art | **~95 %** | Solveur + substrat validé H1–H6 et refusé quand il ne tient pas, palette officielle importable, fusion des tuiles, choix de palette au coût mesuré. **La fidélité est à la limite du médium** (§ 6.3). Relief en plateaux, aux seuils d'Otsu, et profondeur **mesurée** quand la photo en porte une (§ 6.10). Découpe en sections bâties séparément (§ 5.51). Manque : rien d'identifié en 2D. |
| → liste de course | **~97 %** | Nomenclature exacte, filtrée aux couleurs commandables, garde-fou anti-omission, export CSV, contrainte d'approvisionnement. export BrickLink prêt à l'envoi. Table de correspondance BrickLink **importée** de l'export officiel via le LEGOID (§ 5.55). Manque : les prix — hors périmètre assumé. |
| → notice de montage | **~92 %** | Plan acyclique, PDF autonome (couverture en couleurs pleines, liste de course avec pastilles et codes, pose du fond, mosaïque bande par bande avec réglettes et légende), ordre vérifié contre le plan, marge d'impression vérifiée. Encart des pieces par etape, bande dessinee avec une lettre par piece, deux a quatre etapes par page, page du cadre (§ 5.52). Manque : les dessins de pieces en perspective des vraies notices. |

**Environ 92 % de la demande.** Le bond depuis les ~15 % initiaux n'est pas un
tour de passe-passe : la demande est du LEGO **Art**, donc un probleme 2D. Le
volume 3D — de loin le plus lourd — n'en fait pas partie.

Ce qui reste est domine par deux choses tres differentes : du **rendu
graphique** pour la notice, et de la **donnee reelle** (palette officielle,
catalogue, prix). Aucune des deux n'est un probleme d'architecture.

### 6.1 Mesures de bout en bout

Paysage → mosaïque 48×48 (format LEGO Art officiel), palette officielle :

| Étape | Résultat |
|---|---|
| Modèle | **1411 pièces** (1283 tuiles + 128 de fond), 4608 liaisons |
| Génération | 0,68 s |
| Validation H1–H6 | 2,59 s, **0 violation** |
| Fidélité | 8,3 ΔE par tuile, 3,7 de justesse tonale |
| Liste de course | 37 lots, 1411 pièces |
| Notice | 369 étapes, PDF de 17 pages, 175 Ko |
| `modele.ldr` | 1412 pièces, 62 Ko |
| `modele.json` | 0,76 Mo |

Pour comparaison, la même photo au début de la passe d'optimisation : **2917
pièces** et **23,9 ΔE** par tuile. Soit −52 % de pièces et un écart divisé par
près de trois, sans qu'aucun tenon ne change de couleur par rapport à ce que la
palette permet.

Le modèle n'est **écrit que s'il passe les six invariants**. Une mosaïque qui ne
tiendrait pas ensemble n'est pas livrée — c'est tout l'intérêt d'avoir bâti le
noyau d'abord. Et depuis § 5.35, `build` refuse en amont les formats dont le
fond ne peut pas tenir, au lieu de laisser les invariants le découvrir.

### 6.2 Ce que la mosaïque a révélé sur la demande elle-même


Une mosaïque naïve — les tuiles posées côte à côte sur le plan, exactement ce
que produit un « pixel art → briques » — passe H2, H4 et H6 sans un seul
défaut, **et n'est pas un objet** : 64 tuiles, 64 composants séparés. Seul H5
le voit. Le solveur impose donc un substrat de deux couches de plates croisées,
et c'est vérifié à chaque génération.

### 6.3 La fidélité est à la limite du médium, et c'est mesurable


Question posée : « peut-on faire plus précis ? ». Réponse mesurée sur un
portrait, palette officielle :

| Côté | ΔE/tuile | Ton moyen | Pièces | Taille |
|---:|---:|---:|---:|---:|
| 32 | 8,02 | 6,45 | 441 | 25,6 cm |
| 48 | 7,89 | 7,01 | 904 | 38,4 cm |
| 64 | 8,57 | 4,41 | 2943 | 51,2 cm |
| 96 | 8,60 | 4,41 | 6639 | 76,8 cm |

**La résolution n'améliore pas la précision de COULEUR.** Elle achète en
revanche du **détail**, et c'est une distinction que la formulation précédente
de ce paragraphe écrasait. Sur une nature morte de fleurs : 6,16 ΔE en 48×48
contre 6,03 en 96×96 — l'écart de couleur ne bouge pas — mais à 48×48 les
fleurs sont des taches, et à 96×96 ce sont des fleurs. Deux questions
distinctes, deux réponses distinctes : *la couleur est-elle juste ?* (palette)
et *la forme est-elle lisible ?* (résolution). Et l'écart de la palette seule,
mesuré indépendamment — moyenne des ΔE entre chaque couleur voulue et la plus
proche couleur LEGO — vaut **7,89 ΔE en 48×48**, soit exactement l'écart
constaté. Autrement dit : la totalité de l'erreur restante vient de ce que LEGO
ne fabrique pas la couleur demandée. Aucun algorithme ne la réduira.

Ajouter des tenons agrandit l'œuvre, ça ne l'affine pas. C'est une propriété du
médium, pas une limite du logiciel — et ça clôt la question « hyper précise » :
on y est.

### 6.4 Une peinture se quantifie mieux qu'une photo

Question posée : une photo rendra-t-elle comme une œuvre peinte en LEGO Art ?
Mesure sur trois sources, même palette officielle, même 48×48 :

| Source | ΔE/tuile | Ton moyen | Couleurs employées |
|---|---:|---:|---:|
| Nature morte peinte | **6,16** | 5,40 | **9** |
| Photo — portrait | 7,89 | 7,01 | 16 |
| Photo — paysage | 8,27 | 3,73 | 15 |

Une peinture arrive **déjà simplifiée** : aplats saturés, contours francs,
palette restreinte par le geste du peintre. C'est exactement ce qu'une mosaïque
sait rendre. Une photo arrive avec des dégradés continus et des zones peu
saturées — le cas difficile.

Le jaune y aide : **22 des 80 couleurs solides** LEGO sont dans la plage
jaune/ocre, et des jaunes de nature morte y tombent à 3–8 ΔE, bien au-dessous
de la moyenne.

**Une idée testée puis rejetée.** Traiter la photo pour lui donner ce caractère
— postériser, saturer — avant de quantifier. Mesuré contre la photo d'origine,
donc sans circularité :

| Traitement | ΔE/tuile | Couleurs | Pièces |
|---|---:|---:|---:|
| Aucun | **7,89** | 16 | **776** |
| Postérisé 6 paliers | 14,79 | 29 | 2006 |
| Postérisé 4 paliers | 17,25 | 29 | 1043 |
| Postérisé 3 paliers | 21,37 | 29 | 775 |

Pire sur les trois axes à la fois : fidélité, nombre de couleurs, nombre de
pièces. Le rendu le confirme sans appel — visage rose et gris, sol violet.
Postériser fabrique des couleurs que LEGO ne produit pas, et la quantification
doit ensuite approcher une couleur **doublement** fausse. Non implémenté.

Ce qui rapproche vraiment du rendu d'une œuvre peinte ne coûte rien : **choisir
une photo aux bonnes propriétés** — sujet graphique, couleurs franches,
silhouette nette, peu de dégradés subtils.

### 6.5 Profil de la chaîne complète


Paysage 48×48, palette officielle, 1411 pièces :

| Étape | Temps |
|---|---:|
| Quantification | 0,42 s |
| Modèle + fusion | 0,33 s |
| Assemblage | 0,12 s |
| **Six invariants** | **2,64 s** |
| Notice PDF | 0,27 s |
| Export JSON | 0,08 s |
| **Total** | **3,87 s** |

Les invariants pèsent 68 % du total. C'est la preuve que le modèle tient : on
ne l'allège pas.

`--couleurs auto` ajoutait 9,0 s parce qu'il **construisait un modèle complet**
— géométries, connecteurs, substrat, vérification de connexité — pour chacune
des quinze palettes candidates, et n'en relisait que deux nombres. Or ces deux
nombres se déduisent de la grille seule : la fusion se fait ligne par ligne et
ne dépend de rien d'autre. `cost_of_grid` les calcule directement, et le
substrat — qui ne dépend pas de la palette — n'est mesuré qu'une fois.
**9,0 s → 5,0 s**, comptes vérifiés identiques au modèle construit.

### 6.6 Les limites honnêtes de ce qui est livré


Toutes mesurées, aucune supposée.

- **La fidélité est plafonnée par la palette, pas par le logiciel.** 7,89 ΔE par
  tuile sur un portrait, et l'écart de la palette seule vaut exactement 7,89 :
  toute l'erreur restante vient de ce que LEGO ne fabrique pas la couleur
  demandée. La résolution n'y change rien (§ 6.3).
- **Palette provisoire de 12 couleurs par défaut.** `load_ldconfig()` importe les
  162 officielles et cherche le fichier dans les emplacements d'installation
  usuels ; sans lui, l'écart double. Le fichier n'est pas livré ici : sa licence
  n'a pas pu être confirmée (§ 6.8).
- **La fusion des tuiles change la surface**, pas les couleurs : appareil à
  joints décalés au lieu de la grille uniforme des sets officiels (§ 5.36).
  `apercu_joints.png` le montre, `--references minimal` rend la grille.
- **Le recadrage automatique mesure du détail, pas un sujet.** Un fond texturé
  derrière un visage lisse l'attire vers le fond (§ 5.41).
- **La commande BrickLink exige une table** de correspondance des couleurs que
  le dépôt ne fournit pas — c'est une donnée, pas du code (§ 5.40).
- **Notice en vue de dessus seulement.** C'est le bon choix pour une mosaïque —
  une perspective n'ajouterait rien à une œuvre plate — mais un assemblage en
  volume demanderait autre chose.
- **Une mosaïque d'un tenon de large ne tient pas** au-delà de quelques tenons.
  `build` le constate et refuse plutôt que de livrer (§ 5.35).

### 6.7 Ce qui reste, et pourquoi


Les trois premiers points de cette liste, dans ses versions précédentes, sont
faits : palette officielle importable, tramage décidé par image, export
BrickLink. Ce qui reste se range en trois catégories très différentes.

**Fait depuis.** L'interface : « mettre une photo dans l'app » était le dernier
point de la demande d'origine qui restait littéralement ouvert. Il ne l'est plus
(§ 5.50).

**Des données, tranchées (§ 5.55).** `LDConfig.ldr` n'est pas redistribué — sa
licence n'a pas pu être confirmée — mais il est désormais cherché via `LDRAWDIR`
et dans quatre emplacements de plus. La table de correspondance BrickLink
n'est plus une donnée manquante : elle **s'importe** d'un export BrickLink, via
le LEGOID que porte LDConfig, et ce qui reste non apparié sort en gabarit à
compléter.

**Une préférence esthétique.** Ce qui reste de la ligne graphique : les vraies
notices dessinent chaque pièce en perspective, avec ses tenons. La nôtre les
nomme et les montre à plat. C'est du dessin, et rien ne le mesure — mais la
structure, elle, est celle d'une notice LEGO depuis le § 5.52.

**Un autre produit.** Volume 3D, connecteurs Technic,
géométrie non-AABB, stabilité mécanique : tout cela est listé en § 3 avec la
décision que chacun réclame, et cible BFK-002. Ce n'est pas du reste, c'est une
suite.

### 6.8 La seule question qui n'est pas technique

`LDConfig.ldr` — les 162 couleurs officielles — n'est pas livré dans ce dépôt,
et c'est la seule zone que je n'ai pas fermée par décision délibérée.

Le fichier de licence joint à la bibliothèque LDraw est **CC BY 2.0**. Mais son
texte définit l'œuvre couverte comme *les pièces portant la ligne*
`0 !LICENSE Redistributable under CCAL version 2.0`. Vérification faite :

| Fichier | Porte le marqueur |
|---|---|
| `3001.dat` et les autres pièces | **oui** — d'où l'export LDraw, § 5.39 |
| `LDConfig.ldr` | **non** |

Redistribuer un fichier dont je ne peux pas confirmer le marqueur de licence est
une action tournée vers l'extérieur, et elle n'est pas la mienne. Le code le
cherche dans les emplacements d'installation usuels de LDraw, LeoCAD et
BrickLink Studio, et `--ldconfig` prend un chemin. La décision de l'intégrer
appartient au propriétaire du dépôt.

Écart mesuré sans lui : la palette provisoire de 12 couleurs laisse **deux fois
plus d'écart** que les 80 officielles.

---

### 6.9 Le volume : ce que la chaîne peut promettre, et ce qu'elle ne peut pas

La demande d'origine ne portait pas sur le relief, mais la question est venue :
un tableau LEGO Art a du volume, en a-t-on ?

**Oui, et il ne coûte aucune précision.** L'écart par tuile est identique à zéro,
un, deux, trois, quatre ou six étages — 10,60 ΔE sur le portrait de test, 6,16
sur les Tournesols, aux réglages par défaut, sans une décimale d'écart. Les
deux axes sont orthogonaux : la couleur se décide dans le plan, la hauteur en z.
Le noyau n'a rien eu à apprendre pour valider du volume, il est 3D depuis le
premier jour (H1–H6 passent sans une violation sur les élévations testées).

Le prix est en pièces, et il est modeste depuis la correction du § 5.46 :
+10 % pour un étage, +17 % pour deux, +33 % pour quatre.

Ce qu'il faut dire honnêtement, en revanche, sur « aussi intéressant que les
LEGO Art officiels » :

**Notre relief est topographique. Le leur est sculpté.** Une carte d'élévations
tirée de la clarté produit des terrasses de niveau — le relief d'une carte d'état
major. Le relief d'un set LEGO Art ou Ideas est dessiné à la main, pièce par
pièce, et il n'emploie pas que de la hauteur : il change aussi de **type** de
pièce selon l'endroit — tuiles rondes, tuiles-fromage, pentes. Rien dans une
photo ne dit qu'un visage est devant un mur ; toute source de hauteur est donc
une **convention**, pas une mesure, et l'automate ne peut pas décider ce que le
sujet *est*.

Ce que la convention donne, et c'est déjà beaucoup : sur les Tournesols, les
fleurs se détachent du fond avec une ombre nette, les cœurs se creusent, la
ligne de table marche. Sur un portrait, à deux étages, on obtient une silhouette
en relief — le sujet devant, le fond derrière — et non un visage modelé.

Trois conventions ont été comparées, à fidélité rigoureusement égale (les
Tournesols, 48×48, deux étages, toutes lues sur la grille non tramée) :

| Convention | Cases isolées | Plateaux | Pièces |
|---|---:|---:|---:|
| clarté (bas-relief) | 0 | 8 | 1126 |
| chroma (saturés en haut) | 0 | 3 | 1080 |
| écart à la couleur de fond | 0 | 3 | 1159 |

Et une correction à ma propre mesure précédente : j'avais noté la chroma comme
« bruitée » (47 cases isolées, 90 plateaux). C'était faux — c'était le tramage
du § 5.46, pas la convention. Une fois le défaut corrigé, les trois sont
également propres et coûtent à peu près la même chose. Elles ne diffèrent plus
que par **ce qu'elles montrent** : la clarté terrasse les pétales et creuse les
cœurs (8 plateaux), les deux autres se contentent de détacher le sujet du fond
(3 plateaux). La clarté est donc retenue par défaut, comme la plus riche et
comme la convention du camée — l'œil lit spontanément le clair comme proche.
`build(heights=…)` accepte n'importe quelle autre carte.

---

### 6.10 La profondeur mesurée : ce qui existe, ce que j'ai retenu, ce que j'ai réfuté

Jusqu'ici tout le relief de ce dépôt était une **convention**. « Une photo ne
contient aucune information de profondeur » — je l'ai écrit plusieurs fois, et
c'est **faux au moins une fois sur deux**.

#### Ce qui existe

| Technique | Fiabilité | Verdict ici |
|---|---|---|
| Réseau monoculaire (MiDaS, Depth Anything, Marigold) | excellente | **importée** — absurde à embarquer, parfaite à lire |
| Carte embarquée par l'appareil (Dynamic Depth, GDepth) | **mesurée** | **lue** — c'est de la mesure, pas une convention |
| Profondeur par le flou (depth from defocus) | physique mais confondante | **réfutée**, mesures ci-dessous |
| Perspective aérienne / dark channel prior | scènes brumeuses seulement | non retenue, domaine trop étroit |
| Shape from shading | mal posée sans direction de lumière | non retenue |
| Stéréo, photométrique, multi-flash | fiables | hors sujet : demandent plusieurs prises |

#### Ce que j'ai retenu

`depth.py` ouvre deux portes, et une seule ligne les sépare de la convention :
la **provenance**, que la commande affiche toujours.

`--carte-profondeur` accepte une carte PNG, PPM ou JPEG. C'est le pont vers
l'état de l'art : on lance Depth Anything ailleurs, on donne le résultat ici.

`embedded_depth` extrait la carte que le téléphone a **déjà écrite** dans le
JPEG. Un mode portrait mesure la profondeur — deux objectifs, un capteur de
temps de vol — et la dépose dans le fichier. Les deux formats de Google se
lisent : GDepth (base64 dans le XMP, réassemblé quand il déborde en segments
étendus) et Dynamic Depth (le XMP est un annuaire, les images sont concaténées
à la suite du fichier).

**Le contrôle qui compte** : la carte doit avoir les proportions de la photo, à
2 % près. Une carte issue d'un autre recadrage produirait un relief
**parfaitement propre et parfaitement faux** — le pire des résultats, parce que
rien ne le signale à l'œil. `DepthMismatch` refuse.

**Et un défaut trouvé en branchant tout ça** : je réduisais la carte de
profondeur à la moyenne, comme une photo. Moyenner deux distances de part et
d'autre d'un bord invente une distance qui n'existe nulle part — le sujet à 1 m,
le mur à 4 m, et un fantôme à 2,5 m sur tout le contour. Sur une carte à **deux**
profondeurs, réduite en 48×48 :

| Réduction | Valeurs distinctes | Plateaux | Cases isolées |
|---|---:|---:|---:|
| moyenne | 21 | 36 | 28 |
| médiane | **2** | **2** | **0** |

C'est la même erreur que moyenner des octets sRGB (§ 5.24) : la bonne moyenne
dépend de la grandeur. `resample_median` réduit ce qu'on n'a pas le droit de
moyenner ; sur un champ lisse les deux coïncident, donc rien n'est perdu.

Le cas qui justifie tout le module, vérifié par test : un sujet **sombre** sur
fond **clair**. La convention l'enfonce en creux — elle a raison d'après ce
qu'elle sait. La carte le remet devant.

#### Ce que j'ai réfuté

**La profondeur par le flou.** L'idée est juste : la profondeur de champ est un
fait optique, présent dans le fichier. Deux mesures la disqualifient.

Elle survit mal à notre décodage. Le décodage JPEG au huitième rend la moyenne
de chaque bloc 8×8 — mesurer une haute fréquence après l'avoir supprimée :

| Rayon du flou | Rapport net/flou en pleine résolution | Au huitième |
|---:|---:|---:|
| 2 px | 118 | 1,9 |
| 6 px | 269 | 8,4 |
| 12 px | 1004 | 19,2 |

Ce n'est pas rédhibitoire au-delà de 6 px. Ce qui l'est, c'est le second point :
**la netteté confond « loin » et « sans texture »**. Trois régions à la **même**
distance, toutes parfaitement nettes :

| Région | Netteté mesurée |
|---|---:|
| texture fine | 16,63 |
| dégradé doux | 1,54 |
| aplat | 1,50 |

Un aplat net mesure exactement comme un fond flou. Un ciel uni partirait au fond,
un mur texturé juste derrière le sujet resterait devant. Le résultat serait un
relief **confiant et faux** — précisément ce que `DepthMismatch` existe pour
empêcher ailleurs. Combler les zones sans texture demande une segmentation,
c'est-à-dire le réseau de neurones qu'on importe déjà.

Retenu comme mesuré et écarté, pour ne pas y revenir.

### 5.67 « As-tu joué avec la profondeur ? » — non, et c'est en vérifiant que j'ai trouvé le défaut

Question posée sur les rendus livrés. Réponse vérifiée avant d'être donnée :
`Reglages.relief` vaut **0** par défaut et aucun `apercu_relief.png` n'existe
dans aucun des quatre dossiers de sortie produits. **Tous les rendus montrés
étaient plats.** La chaîne sait faire du relief depuis longtemps ; je ne l'avais
jamais employé sur une photo réelle.

#### Le défaut, trouvé en relisant le chemin qu'on m'interrogeait sur

`carte_de_relief` a trois sources, de la mesure à la convention : carte fournie,
carte embarquée dans le JPEG, clarté de la photo. Les deux premières reçoivent
`near_is_bright=not reglages.profondeur_inversee`. La troisième :

```python
return mosaic.relief_from_image(
    image, reglages.studs, hauteur, reglages.relief,
    thresholds=reglages.seuils, fit="stretch",
)
```

`invert` n'est **jamais passé**. `relief_from_image` l'accepte, `etage_field`
l'applique, aucun appelant ne le fournit. La convention « clair = haut » était
donc **impossible à renverser** depuis la commande comme depuis la page :
`--profondeur-inversee` ne parle que de l'encodage d'une carte fournie, et le
seul chemin qui fonctionne sans carte — celui que prend toute photo ordinaire —
n'avait aucun interrupteur.

#### Ce que cela donnait, mesuré sur la photo du lièvre

48×64 tenons, trois étages, élévation moyenne du tiers haut et du tiers bas :

| Convention | tiers haut (ciel) | tiers bas (sol) |
|---|---:|---:|
| clair = haut (le seul disponible) | 2,25 | 0,40 |
| sombre = haut | 0,75 | 2,60 |

**Le ciel saillait de 5 mm devant le sol.** Sur un portrait la convention du
camée reste la bonne — un visage est plus clair que son fond — d'où un défaut
inchangé et un interrupteur, plutôt qu'un renversement.

#### Pourquoi rien ne l'avait attrapé

`relief_edge_alignment` est **aveugle à l'inversion** : les marches tombent aux
mêmes endroits dans les deux sens (555 contre 559 tenons de marche sur la photo
des chiens ; 0,61 de rendement dans les deux cas sur le lièvre). Le seul
indicateur du journal ne pouvait pas voir le problème. Le mesurer demandait une
grandeur **orientée**, et il n'y en avait aucune.

#### Livré

`mosaic.relief_tilt(heights)` — élévation moyenne du tiers haut moins celle du
tiers bas — et la ligne de journal correspondante :

```
  relief  : 3 etage(s), 9.6 mm d'epaisseur
            source : CONVENTION du bas-relief, clair = haut
            tiers haut +1.85 etage(s) par rapport au tiers bas — le haut de
            l'image RESSORT ; sur un paysage c'est le ciel devant le sol —
            renversez la convention (sombre = haut)
```

Plus `Reglages.relief_inverse`, `--relief-inverse`, et une case dans la page.

Le seuil de signalement (un demi-étage) est un **repère de lecture**, comme le
1 % de tours isolées voisin, et non une constante mesurée : trois photos ne
suffisent pas à étalonner un critère automatique — c'est la leçon du § 5.66,
appliquée le lendemain. Le journal **signale**, il ne corrige pas.

Vérification de l'instrument sur les deux photos réelles : il alerte sur le
lièvre (+1,85) et se tait sur les chiens (−1,38), où la convention du camée
donne effectivement le meilleur rendu — les chiens se détachent de la couette.
Deux photos ne prouvent rien ; elles ne le contredisent pas.

**Le premier jet du signalement avait lui-même un angle mort.** Il se taisait
dès que `relief_inverse` était mis, au motif que le remède était déjà pris. Un
ciel **sombre** renversé ressort exactement pareil, et le journal serait
redevenu muet sur le seul cas qu'il existe pour attraper. Corrigé :
l'observation est toujours dite, le remède seulement quand il en reste un. Et
sur une carte **mesurée** la même pente accuse l'encodage de la carte
(`--profondeur-inversee`), pas la convention de clarté — ce qui donne au
signalement une seconde utilité qu'il n'avait pas été conçu pour avoir.

#### Le défaut du § 5.61 guettait une troisième fois

`conseil_de_format` recalcule les élévations de son côté pour annoncer un
nombre de pièces. Ajouter l'option sans l'y passer aurait fait mentir le conseil
de 116 pièces sur la photo des chiens. Le cas est entré dans le test
paramétré qui compare le conseil à ce que la chaîne livre — et ce test tombe
bien (465 ≠ 462) si on retire l'option d'un seul des deux côtés. Vérifié en la
retirant.

#### Ce que l'aperçu montre du relief, mesuré aussi

`preview(relief=True)` éclaire les marches, pas les plateaux — physiquement
correct pour une vue de dessus. Mesuré sur le lièvre : **11,4 % de la surface**
est ombrée, de 38,7/255 en moyenne. Le relief se voit donc, mais uniquement aux
ruptures ; deux conventions opposées donnent deux images qui se ressemblent au
premier coup d'œil. C'est une limite de la vue de dessus, pas un défaut à
corriger en inventant un rendu.

#### Ce que la commande a gagné au passage

Les options de `demo_lego_art.py` vivaient dans `main`, hors de portée de tout
test sans lancer une fabrication complète. `construire_analyseur()` les isole.
Un drapeau qui n'arrive pas jusqu'aux `Reglages` n'existe pas pour
l'utilisateur — c'est précisément ce qui venait d'arriver.


### 5.68 La photo suivante ne passait pas du tout — et l'instrument de la veille était déjà aveugle

Une cinquième photo : un homme en combinaison sur une plage, deux chiens, la mer.
La chaîne l'a **refusée** avant toute mosaïque.

```
JPEG progressif ou etendu non supporte : ce decodeur ne lit que le baseline
sequentiel (SOF0/SOF1). Reenregistrer la photo en baseline, ou en PNG.
```

#### Ce que les cinq photos disent ensemble

| photo | taille | encodage | segments |
|---|---:|---|---|
| vélo | 4257 Ko | baseline | Exif + ICC |
| chiens | 2306 Ko | baseline | Exif + ICC |
| lièvre | 2234 Ko | baseline | Exif + ICC |
| **plage** | **103 Ko** | **SOF2 progressif** | JFIF seul |

Les trois arrivées en original sont baseline. Celle passée par une messagerie
est progressive, sans EXIF, à 4 % du poids. Le refus était honnête — il valait
mille fois mieux qu'une image fausse — mais il refusait **le cas le plus
courant** : quelqu'un qui transfère une photo depuis son téléphone. Une demande
en quatre points qui commence par « mettre une photo dans l'app » n'est pas
satisfaite par un message d'erreur exact.

#### Pourquoi c'était bon marché

Un JPEG progressif range ses coefficients en balayages successifs : les DC de
toute l'image d'abord, puis les AC par tranches spectrales, chacune raffinée
bit à bit. **Ce décodeur ne garde que le DC.** Les balayages AC — l'essentiel
du fichier — se sautent donc sans être décodés. La photo de plage compte huit
balayages ; trois portent du DC.

```
(3, Ss=0, Se=0, Ah=0, Al=2)   <- DC initial, entrelacé
(3, Ss=0, Se=0, Ah=2, Al=1)   <- raffinement
(3, Ss=0, Se=0, Ah=1, Al=0)   <- raffinement
(1, Ss=1, Se=63, ...)  x5     <- sautés
```

Le décodeur y a gagné une structure plus juste : il parcourt désormais **tous**
les balayages au lieu de s'arrêter au premier, et la moyenne du bloc se calcule
une fois à la fin, à partir du coefficient DC brut — au fil du décodage, aucun
raffinement n'aurait été possible.

#### Vérifications

- Les trois photos baseline se décodent **au bit près comme avant** (SHA-256
  identiques). Un remaniement du décodeur qui changerait une image existante
  serait une régression silencieuse.
- Un **encodeur progressif** dans le fichier de test, sur le même principe que
  l'encodeur baseline qui existait déjà : blocs unis, domaine où un décodeur DC
  doit être exact au bit près. « Ça a l'air bon sur une photo » ne prouve rien.
- Le cas **4:2:0**, où la grille de blocs de la luminance et celle de la
  chrominance diffèrent : une erreur d'indice y donne une image *plausible*, les
  couleurs glissant d'un bloc. Test non vide, vérifié en intervertissant deux
  indices dans le décodeur — lui seul tombe.
- Le raffinement testé séparément, avec deux bits d'approximation et des
  valeurs impaires : sans lui le DC reste faux d'un bit, et le test précédent
  passerait quand même.

Restent refusés, explicitement : sans perte (SOF3), arithmétique, hiérarchique.
Aucun appareil n'en produit, et un décodeur qui ne lit que le DC n'a rien à
lire dans un JPEG sans perte — il n'y en a pas.

#### Un défaut préexistant, trouvé en jetant des octets au hasard

En vérifiant que le nouveau décodeur ne boucle pas sur un fichier tronqué, une
corruption a fait sortir `_build_huffman` par un **`IndexError` sec** — pas une
erreur explicite, une erreur d'indice à huit appels de profondeur. Vérifié sur
la version d'avant : **identique**, le défaut n'était pas de moi. Une table qui
annonce douze symboles et n'en porte que trois est maintenant refusée en le
disant. Quarante corruptions aléatoires d'un en-tête valide : quarante refus
propres, zéro `IndexError`.

Un fichier progressif tronqué à 30 % rend d'ailleurs l'image **entière** : les
balayages DC sont au début, et ce sont les seuls que nous lisons. Propriété du
format, pas mérite du code — mais elle explique pourquoi la troncature ne
produit rien d'étrange ici.

#### Et la pente du § 5.67 s'est fait prendre le lendemain

La même photo, trois étages, convention par défaut. `relief_tilt` rend **−0,86**
et le journal se tait. Bande par bande :

| bande | élévation moyenne |
|---|---:|
| ciel | 2,00 |
| ciel bas / horizon | 2,37 |
| mer | 1,35 |
| sable moyen | 2,45 |
| sable premier plan | 3,00 |

Le sable du premier plan est à 3,00 : le plus proche est bien le plus haut,
c'est juste. Mais **le ciel est à 2,00 et la mer à 1,35** — le ciel saille de
2 mm devant une mer qui est deux cents mètres plus près. La pente ne le voit
pas : elle compare deux bandes, et un premier plan clair compense un ciel clair.

**Je n'ai pas ajouté de critère.** Un test de monotonie, une troisième bande,
un seuil sur la variance : ce serait une nouvelle règle calibrée sur cinq
photos, exactement ce que le § 5.66 a refusé et ce que le § 5.67 s'interdit
dans sa propre docstring. La limite est écrite ici, avec ses chiffres, et
l'instrument continue de dire ce qu'il mesure — ni plus, ni moins.


### 5.69 Un arbitrage dont on ne publiait qu'un côté

Sixième photographie : un Cavalier en contre-jour, fond flou. Fichier Apple
d'origine — Exif, ICC « appl », APP10 « AROT » — 3024×4032, baseline. Elle a
traversé la chaîne sans incident : 1275 pièces, plancher de palette à 6,7 ΔE.

#### Le mode portrait ne viendra pas

Recherche exhaustive dans le fichier : `xmpmeta` **0 occurrence**, `GDepth` 0,
`Container` 0, `MPF` 0, zéro octet après l'EOI final. L'Exif lui-même est
réduit à l'orientation et aux dimensions — ni marque, ni modèle, ni ouverture.

Bilan sur **six photographies réelles** : aucune ne porte de XMP. `embedded_depth`
ne lit que les deux conteneurs de Google — GDepth et Dynamic Depth, tous deux
portés par du XMP. Le chemin embarqué **n'a jamais eu l'occasion de servir une
seule fois**, et redemander « une photo prise en mode portrait » ne pouvait pas
le faire servir.

Ce n'est pas un défaut du code : il fait ce qu'il annonce, et ses tests le
vérifient contre des conteneurs conformes. C'est un défaut de **portée**, et il
était écrit noir sur blanc dans la docstring : « le fichier que vous avez déjà
sur votre téléphone contient donc, souvent, la carte de profondeur du sujet ».
Corrigé pour dire ce qui est lu, et ce qui a été mesuré.

#### Le vrai défaut, trouvé en regardant le rendu

Le tramage automatique s'est déclenché, et la version nette est visiblement
meilleure : la porte sombre à gauche se crible de damier. Troisième photo réelle
où `auto` déclenche et où l'œil préfère la version nette.

En allant lire pourquoi, un défaut simple est apparu — indépendant de tout seuil.
Le journal disait :

```
  tramage : applique — il gagne de la justesse tonale et laisse 558 tuiles
            isolees de grain.
            ce grain coute +0.39 delta E de finesse locale
```

**Le prix sans le bien.** Le gain était calculé dans `quantize`, servait à
décider, et était jeté. Un arbitrage dont on ne publie qu'un côté n'est pas un
arbitrage — et le § 5.66 avait explicitement choisi *mesurer et informer plutôt
que trancher*. La moitié de la mesure manquait.

Le gain ressort désormais **par le même appel que la décision** (`rapport=`), et
non par un recalcul : recalculer ailleurs, c'est le défaut des § 5.61 et § 5.64,
fait deux fois.

#### Ce que les chiffres montrent, une fois publiés

| photo | gain tonal (pire écart) | coût en grain | verdict de l'œil |
|---|---:|---:|---|
| lièvre | −0,44 | — | écarté, correctement |
| plage | 1,02 | +0,24 | match nul |
| cavalier | 1,17 | +0,39 | **nette meilleure** |
| vélo | 3,64 | +0,40 | **nette meilleure** |

Deux des trois déclenchements sont **marginaux** — 1,02 et 1,17 pour un seuil à
1,00 — ce qui suggérait de relever le seuil. Mais le vélo gagne **3,64** et
reste pire à l'œil : aucun seuil sur cette grandeur ne sauve les trois cas.

Les deux grandeurs ne sont d'ailleurs **pas commensurables** — l'une est le pire
écart tonal sur des moyennes de blocs 4×4, l'autre une perte de finesse locale —
et le journal les nomme séparément plutôt que de les soustraire. Écrire
« coût > gain » aurait été une erreur d'unités déguisée en verdict.

Le critère reste donc inchangé, pour la troisième fois, et pour une raison
mesurée et non par prudence : rien de ce que j'ai essayé ne sépare les cas. Ce
qui change, c'est que le lecteur voit enfin les deux nombres.


### 5.70 Passe méticuleuse : neuf audits verts, et trois bombes dans le décodeur

Demande d'une passe complète « pour ne laisser aucun doute ». Neuf audits écrits
et exécutés en dehors de la suite, sur les six photographies réelles. **Cinq
fois sur neuf, le premier verdict rouge venait de mon instrument, pas du code.**

| audit | ce qui a été vérifié | verdict |
|---|---|---|
| 1 | déterminisme : 3 photos × 9 fichiers, deux fabrications | identique à l'octet |
| 2 | liste de course vs LDraw, **pièce par pièce et couleur par couleur** | exact |
| 3 | export BrickLink : 51 lots, 845 pièces | exact |
| 4 | **le `modele.json` livré, rechargé et repassé aux six invariants** | 0 violation ×4 |
| 5 | notice vs liste, par pièce, sur 5 configurations | exact |
| 6 | ordre de montage : chaque prérequis posé avant d'être invoqué | exact |
| 7 | LDraw : coordonnées entières, rotations droites, aucun doublon | exact |
| 8 | route de fichiers, **vrai serveur HTTP** : 6 traversées | 404, aucune fuite |
| 9 | matrice de 28 combinaisons d'options, chacune vérifiée à fond | 27 bâties, 1 refusée |

Le quatrième est le plus fort de tous : ce n'est pas le modèle en mémoire qui
passe les invariants, c'est **le fichier tel qu'il est écrit sur le disque**,
rechargé, ses liaisons ré-émises par l'oracle. Relief 3, sans cadre, tuiles
minimales : zéro violation.

#### Les instruments faux, listés parce qu'ils instruisent

`design` au lieu de `design_id` ; `dumps_wanted_list(table=…)` qui n'existe pas ;
un `^(\d+)\s*x` qui attrapait le numéro d'étape ; « provisoire » cherché en
minuscules quand le journal crie `PROVISOIRE` ; des noms de modules cités en
prose pris pour des chemins. **Le total concordait à chaque fois** — 845 = 845 —
et seul le groupement divergeait : la signature d'une erreur de mesure, pas de
calcul. C'est la troisième fois dans ce dépôt qu'une symétrie trop propre dans
un écart accuse l'instrument.

#### Trois bombes, au seul endroit qui lit des octets d'un inconnu

Treize octets d'en-tête décident de tout ce qu'un décodeur alloue, et rien
n'oblige ces treize octets à dire la vérité.

| attaque | avant | après |
|---|---|---|
| PNG annonçant 2³¹−1 × 2³¹−1 | `zlib.error` hors contrat, **connexion coupée sans un mot** | 400, message clair |
| PNG, 204 Ko → 200 Mo décompressés | **200 OK**, mosaïque bâtie dessus | 400, refusé à 50 Mo |
| JPEG de **171 octets** annonçant 32000×32000 | **plusieurs minutes** de processeur | refusé en 0,000 s |

La parade existait déjà dans ce dépôt — `pickabrick._lire_borne`, plafond à
128 Mo — et n'avait jamais été appliquée au décodeur d'images, c'est-à-dire au
seul endroit qui lit des octets venus du réseau. Le catalogue d'éléments, qu'on
va chercher soi-même, était protégé ; la photo qu'un inconnu dépose ne l'était
pas.

La borne n'est pas un chiffre de confort. Elle est calée sur ce que le décodeur
alloue **vraiment**, mesuré :

| image | pixels | pic mémoire | octets par pixel |
|---|---:|---:|---:|
| 1000×1000 | 1,0 Mpx | 9,0 Mo | 9,0 |
| 2000×2000 | 4,0 Mpx | 36,0 Mo | 9,0 |
| 3000×4000 | 12,0 Mpx | 108,0 Mo | 9,0 |

Neuf octets par pixel. `PIXELS_MAXIMUM = 80_000_000` plafonne donc l'allocation
vers 720 Mo et reste **au-dessus du plus gros capteur grand public** — 61 Mpx en
plein format, 48 Mpx sur un téléphone. Aucune photographie réelle n'est refusée ;
un en-tête menteur l'est immédiatement. Les cinq photos réelles se décodent au
**bit près** comme avant (SHA-256 identiques).

#### Ce qui reste ouvert

La combinaison `sections=12` **avec** relief est refusée par un message dont le
conseil est faux : « choisissez un côté de section multiple de 4 » — or 12 en
est un. Le vrai obstacle est un joint qui ne se trouve pas enjambé à `y=24`,
ce qui dépend du pavage réel et non d'une divisibilité. `sections=12` seul
passe. Le refus est légitime (il empêche un assemblage non connexe) ; c'est le
conseil qui ment, et il n'est pas corrigé ici faute d'avoir établi la règle
vraie. Noté plutôt que réparé à l'aveugle.


### 5.71 Quatre critères essayés, quatre réfutés — et c'est le défaut qui change

Demande explicite : régler le problème du tramage automatique. Mandat pour
toucher au critère, refusé trois fois jusqu'ici (§ 5.66, § 5.67, § 5.69).

#### Trois hypothèses, trois réfutations par la mesure

**1. « Le tramage pose une bordure cohérente sur un dégradé, un semis isolé sur
une photo. »** Le dépôt mesure déjà les tuiles isolées. Réfuté :

| | tuiles isolées après tramage |
|---|---:|
| dégradé vertical | 17,7 % |
| dégradé doux | **43,8 %** |
| plage | 15,3 % |
| cavalier | 17,6 % |
| lièvre | 30,1 % |

Le dégradé en produit **plus** que les photos. L'hypothèse va à l'envers.

**2. « Le tramage fait déraper des tuiles loin de la couleur voulue. »** Née
d'une observation réelle : dans le ciel de la plage, le tramage sème des points
**magenta** sur du bleu. Mesuré sur la distribution complète des écarts par
tuile — tuiles au-delà de 12 ΔE ajoutées par le tramage :

| dégradé vertical | dégradé doux | vélo | cavalier |
|---:|---:|---:|---:|
| +1,4 % | **+8,8 %** | +0,4 % | +0,1 % |

Encore à l'envers.

**3. « Le tramage corrige des faux contours, et il n'y en a que sur du lisse. »**
Un faux contour : deux tuiles voisines de couleurs différentes là où la photo,
elle, ne change pas — le défaut exact que le tramage existe pour corriger,
mesuré sur la grille **nette**. Réfuté aussi :

| dégradé vertical | dégradé doux | vélo | cavalier |
|---:|---:|---:|---:|
| 3,98 % | 3,98 % | **8,34 %** | **8,16 %** |

Les photos en ont **deux fois plus** que les dégradés, et c'est pourtant là que
le tramage est le plus laid.

#### Ce que quatre réfutations veulent dire

Avec le gain tonal (§ 5.69), quatre grandeurs indépendantes ont été essayées.
Toutes pointent à l'envers de l'œil ou ne séparent pas. La conclusion n'est pas
« il faut chercher mieux » — c'est que **la différence n'est pas dans le
tramage**, elle est dans ce qu'il remplace : une bande franche sur un champ
lisse est un artefact très saillant, une photographie n'en a pas.

Et le seul objet parfaitement lisse de tout le jeu d'essai est un **dégradé
synthétique**. Personne ne photographie un dégradé.

#### Livré : le défaut change, pas le critère

`Reglages.tramage` vaut désormais `"aucun"`, dans les **trois** façades — les
`Reglages`, la ligne de commande et la page l'écrasaient chacune de leur côté,
et un test le vérifie maintenant. `auto` reste disponible et se comporte
exactement comme avant.

Bénéfice mesuré au-delà du rendu : le tramage isole des tuiles, et une tuile
isolée coûte une pièce. Le défaut net économise **116 à 257 pièces** sur les
trois photos concernées.

Le journal chiffre les deux côtés de la décision, y compris quand il ne trame
pas :

```
  tramage : ecarte (defaut) — il gagnerait +2.02 delta E sur le pire ecart
            tonal, +0.35 de finesse locale, 258 tuile(s) isolees de grain.
```

Et pour que ce chiffre ne puisse pas mentir, `arbitrage_du_tramage` est
désormais la **seule** implémentation : la décision de `quantize` et le compte
rendu du journal en sortent tous les deux. Recalculer ailleurs est le défaut des
§ 5.61 et § 5.64, déjà commis deux fois ; ici il aurait été commis une
troisième, puisque le journal doit rendre compte d'un calcul que la chaîne ne
fait plus.

Le fond de l'argument était dans le dépôt depuis le début, et personne ne l'avait
confronté à autre chose qu'un dégradé : `blending_tiles` dit que l'œil résout
chaque tuile de 8 mm **à toute distance de lecture**. Le fondu optique sur lequel
repose le tramage n'a jamais lieu ; le grain, lui, se voit toujours.


### 5.72 « Ajoute plus de pièces » — la demande était fausse, l'intuition juste

Demande : ajouter des pièces à la collection pour réduire l'effet de pixels et
la trame mal faite.

#### La première moitié ne pouvait pas marcher, et ça se mesure

Les quatre jeux de tuiles produisent une grille de couleurs **identique** :

| jeu | tuiles posées | grille identique |
|---|---:|---|
| minimal (1×1) | 3072 | référence |
| standard | 1327 | oui |
| large (jusqu'à 1×8) | 1001 | oui |
| art (rondes) | 3072 | oui |

Les tuiles 1×N sont des **fusions** de cases de même couleur. Elles divisent le
nombre de pièces par trois et ne changent pas un pixel. Le pas de 8 mm est celui
du tenon ; le catalogue LEGO n'a rien de plus petit dans le plan, et la
géométrie de ce dépôt ne modélise que des boîtes alignées sur la grille — une
tuile diagonale demanderait une primitive de collision que le noyau n'a pas.

Le seul levier géométrique est donc la **résolution**, déjà disponible
(`--studs`), et c'est elle qui fait disparaître les pixels : à 96 tenons au lieu
de 48, la grille est quatre fois plus fine.

#### La seconde moitié cachait un vrai gisement, et un vrai défaut

Les couleurs étaient retenues sur leur **finition** : opaques et mates. Prudent,
et faux **dans les deux sens**.

**Trop large.** Une couleur mate obsolète reste retenue alors qu'aucune tuile
n'existe plus dedans. La chaîne construisait donc des mosaïques avec des
couleurs qu'elle ne pouvait pas prouver commandables, et l'utilisateur ne
l'apprenait qu'au rapport des manquants, après coup.

**Trop étroite.** Les nacrées existent bel et bien en tuile 1×1. Mesuré à 48×64 :

| jeu de couleurs | n | vélo | cavalier | lièvre |
|---|---:|---:|---:|---:|
| solides seuls | 82 | 5,03 | 4,78 | 7,07 |
| + nacrées | 93 | **4,33** | **4,21** | 6,85 |
| + nacrées + métallisées | 102 | 4,29 | 4,29 | **6,72** |

Sept dixièmes de ΔE pour zéro pièce de plus — autant que doubler la résolution.

#### Livré : `couleurs_prouvees`

La règle est renversée. Avec un catalogue d'éléments, une couleur est retenue
si le fichier **prouve** que chacune des références demandées existe dedans.
Toutes les références, pas seulement la 1×1 : la fusion est automatique, et une
couleur sans 1×4 rendrait la liste incommandable dès que la fusion s'en sert —
un test le vérifie en fournissant un catalogue qui n'a que la 1×1.

Sur le vélo, avec un catalogue couvrant les couleurs opaques : **7,4 → 5,7 ΔE
par tuile**, pire écart tonal 12,4 → 8,6, +20 couleurs débloquées, −2 écartées.

Le plancher `COULEURS_PROUVEES_MINIMUM = 24` — le nombre de couleurs d'un set
LEGO Art officiel — refuse un catalogue partiel **en le disant**, plutôt que de
livrer une mosaïque en trois couleurs sans que personne comprenne pourquoi.

#### Un défaut dans ce que je venais d'écrire

Vérification systématique des cas dégradés, et le mécanisme s'est fait prendre :
un catalogue de 24 couleurs — juste au-dessus du plancher — était **adopté avec
une simple ligne d'information**, et faisait passer l'écart de **6,7 à 9,2 ΔE**.

Adopter reste juste sur le fond : on ne commande pas des tuiles qui n'existent
pas. Mais un catalogue nettement plus étroit que la règle de finition est
presque toujours un fichier **incomplet**, pas un catalogue LEGO réduit — et
dégrader le rendu sans le dire aurait été le pire des deux comportements.

En dessous de la moitié de la palette, la ligne passe donc en **alerte** et
nomme le remède : vérifier le fichier, ou le retirer pour revenir à la règle de
finition. Trois cas, trois comportements distincts, chacun sous test :

| catalogue prouve | comportement |
|---|---|
| moins de 24 couleurs | **refusé**, palette de finition conservée |
| moins de la moitié | adopté, **en alerte**, avec le remède |
| au-delà | adopté, en information |

#### Ce qui reste une supposition, et il faut le dire

Le gain ci-dessus est mesuré avec un catalogue **de synthèse** qui affirme que
les nacrées existent dans les trois références. Je n'ai aucun moyen de le
vérifier ici, et ce dépôt n'invente pas de données catalogue. Le mécanisme est
livré et testé ; **la vérité vient du fichier de l'utilisateur**. Sans
catalogue, rien ne change — la règle de finition reste, et le journal reste
muet.


### 5.73 H2 coûtait 45 % de la chaîne — trois fois plus qu'il ne devait

La résolution est le seul levier contre l'effet de pixels (§ 5.72), et elle
coûtait cher : 33 s à 96×128 tenons. Le profil désigne un coupable unique —
`check_h2_collision`, **45 % de toute la chaîne**.

#### Trois gaspillages, tous corrigés sans changer un bit du résultat

**1. Neuf découpes sur dix ne touchaient rien.** `solid_overlap` retire les
vides de la zone examinée, un par un, en découpant les morceaux. Mesuré sur une
mosaïque réelle de 1588 pièces : les grandes plates du substrat portent jusqu'à
**226 vides**, et sur les 449 214 découpes examinées, **91,2 % ne touchaient
même pas la zone étudiée**. La boucle les traversait toutes, pour chaque
morceau déjà découpé.

L'élagage est **prouvable**, pas heuristique : `pieces` part de `(base,)` et
`_subtract_box` ne rend que des sous-boîtes de son argument. Par récurrence,
tout morceau est inclus dans `base` ; un vide disjoint de `base` est donc
disjoint de chaque morceau.

**2. Huit coins transformés au lieu de deux.** `Orientation` n'accepte que des
coefficients dans {−1, 0, 1} avec M^T M = I — cela force exactement une valeur
non nulle par ligne et par colonne, soit une **permutation signée des axes**.
Le noyau en accepte donc exactement **24**, vérifié en force brute sur les 3⁹
combinaisons de coefficients. Chaque coordonnée de sortie vaut alors ± une
seule coordonnée d'entrée : ses extrêmes viennent de `min` et `max`. Deux coins
suffisent. Vérifié sur les 24 orientations × 40 boîtes tirées au hasard : zéro
désaccord.

**3. Le même calcul fait deux fois.** `intersection_aabb` appelait
`geometric_relation`, qui calcule les intervalles de recouvrement, puis les
recalculait pour bâtir le résultat — sur 2,7 millions d'appels. Le critère est
désormais écrit sur place, donc il **peut dériver** : c'est le seul risque du
changement, et un test compare les deux sur 40 000 paires tirées au hasard.

#### Le résultat

| | avant | après |
|---|---:|---:|
| contrôle à 48×64 | 3,85 s | **0,72 s** |
| total à 48×64 | ~13 s | **5,4 s** |
| contrôle à 96×128 | 14,77 s | **3,26 s** |
| total à 96×128 | ~33 s | **13,1 s** |
| la suite complète | 4 min 52 | **2 min 23** |

**Identique au bit près.** Six configurations — relief, sections, sans cadre,
tuiles minimales et larges — comparées par 74 empreintes SHA-256 portant sur
tous les fichiers livrés, les mesures et le journal. Seules les durées écoulées
diffèrent, et elles ont été neutralisées pour que la comparaison porte sur le
contenu et non sur le chronomètre.

#### Le risque réel de ce commit, et comment il est tenu

Une optimisation qui rendrait H2 **aveugle** serait le pire défaut possible de
ce dépôt : un invariant vert qui ne veut rien dire. Les tests ne mesurent donc
pas la vitesse, ils construisent des pénétrations réelles et vérifient qu'elles
sont toujours vues — y compris quand le vide qui compte est **noyé parmi 220
inutiles en ordre aléatoire**, et quand un vide tangent de volume nul ne doit
rien retirer.

#### Ce que le profil dit maintenant

H2 est passé de 47,7 à 11,2 s de profil et n'est plus dominant. Les trois coûts
sont désormais du même ordre : H2 (11,2 s), la notice (9,3 s) et le décodage
JPEG (7,6 s).

#### La notice redessinait treize fois la même pièce

`render_piece` est une fonction **pure** de ses quatre arguments — elle ne lit
que le catalogue et des constantes — et la notice la rappelle à chaque étape,
puisque chaque étape rappelle « ce qu'il faut sortir du sachet ». La redondance
**croît avec la résolution**, c'est-à-dire exactement là où le temps compte :

| format | appels | dessins distincts | redondance |
|---|---:|---:|---:|
| 48×64 | 789 | 114 | 6,9× |
| 96×128 | 1693 | 128 | **13,2×** |

Un cache borné à 256 entrées (le double du pire cas observé) suffit. L'échelle
entre dans la clé **sans arrondi** : arrondir rendrait le cache approximatif.
`Image` étant un value object gelé aux données en `bytes`, partager le même
objet entre appelants est sans danger — et un test l'exige plutôt que de le
supposer.

**Une leçon de mesure au passage.** Une première mesure en un seul essai donnait
13,1 → 12,3 s : j'ai failli conclure que le gain ne valait pas la complexité.
Sur trois essais, la médiane dit **13,50 → 10,24 s**, soit −24 %. Le premier
chiffre était du bruit. Un gain de 6 % et un gain de 24 % n'appellent pas la
même décision, et rien ne les distinguait sans répétition.

#### Le compte total

| | début de session | maintenant |
|---|---:|---:|
| 48×64 | ~13 s | **4,79 s** |
| 96×128 | ~33 s | **10,24 s** |

Soit **−63 %** et **−69 %**, à résultat identique au bit près dans les deux cas.


---

## 7. Ce qu'un solveur devra respecter

Pour que la couche 2 se branche sans rouvrir le noyau :

1. Ne jamais construire un `PhysicalBond` — seul `evaluate_connector_pair` en émet, et H3 le vérifie.
2. Appeler `evaluate_placement` avant de poser, `add_part` pour poser : jamais reconstruire un `ConstructionGraph` à la main.
3. Passer une `ConnectorTolerance` explicite à chaque appel — il n'existe aucune valeur par défaut, et c'est voulu.
4. Utiliser `LatticeSearchApproximation` en production, la référence O(n²) en test de conformité — et vérifier P ⊆ C_fast, jamais C_ref ⊆ C_fast.
5. Ne pas sérialiser de liaisons : un document porte des pièces, l'oracle porte le jugement.

---

### 5.74 « Hébergée » n'était pas un réglage — c'était trois hypothèses fausses

La demande : *« j'aimerais qu'on puisse utiliser l'ensemble sur une app
hébergée »*. La tentation était de répondre `--adresse 0.0.0.0` et un
`Dockerfile`. Trois hypothèses tenaient silencieusement dans `webapp.py`, et
aucune ne survit à un deuxième utilisateur.

**Ce qu'il fallait mesurer d'abord.** Le chiffre qui décide de tout est le pire
coût qu'une seule requête peut imposer. Extrapolé linéairement depuis
40 000 tenons, le plafond de la chaîne (250 000) annonçait 250 s et 2,9 Go.
Mesuré : **388,7 s et 3 439 Mo**. Le coût est linéaire *plus quelque chose*, et
ce quelque chose se paie exactement là où il ne reste plus de marge. Un plafond
calculé sur la pente du milieu du tableau aurait autorisé un tiers de tenons de
trop — et un tiers de trop ne donne pas une erreur lisible, il donne un
processus tué en plein calcul.

Cette mesure a tranché seule ce qui aurait pu être un débat d'architecture :
aucune fonction sans serveur ne tient six minutes et demie ni trois giga-octets
et demi. **Conteneur.** Sans mesure, c'était un avis ; avec, c'est une donnée.

**Ce que la parallélisation n'apporte pas.** Deuxième mesure, contre
l'intuition : deux fabrications en parallèle prennent chacune **2,15 fois** plus
longtemps, et le débit total *baisse* (0,120 → 0,112 → 0,107 mosaïque/s à
1, 2 et 4 fils). La chaîne est du Python pur ; le verrou global la sérialise et
les fils n'ajoutent que du changement de contexte. Une deuxième place de
fabrication aurait donc tenu deux pointes de mémoire en même temps pour rendre
les deux réponses deux fois plus tard. **Une seule place** — et le refus
immédiat qui en découle (0,1 s, avec `Retry-After`) vaut mieux qu'une attente
muette d'une minute. Refuser la concurrence rend en prime chaque mosaïque
autorisée plus grande, puisque le budget mémoire n'est plus divisé.

**Le défaut de fond, celui qu'aucun test local ne pouvait montrer.** L'`Atelier`
portait un état d'**installation** : palette, catalogues de commande. C'est
juste tant qu'il n'y a qu'un utilisateur, qui est aussi celui qui répond de la
machine. Hébergé, le catalogue déposé par un visiteur changeait la liste de
course de tous les autres — et un catalogue partiel l'aurait *dégradée* sans
que personne comprenne pourquoi. Un atelier par session le ferme ; mais un
magasin de résultats par session aurait multiplié la borne par le nombre de
visiteurs, c'est-à-dire ne l'aurait plus bornée du tout. D'où la séparation :
**catalogues par visiteur, magasin unique borné en octets** — les jetons étant
imprévisibles, le partager ne partage pas la lecture.

Au passage, `RESULTATS_GARDES = 8` s'est révélé ne rien borner : huit mosaïques
de 24 × 32 pèsent trois mega-octets, huit de 200 × 200 en pèsent cent soixante.
Compter les objets n'est pas une borne quand leur taille varie d'un facteur
cinquante.

**Une constante que je venais d'écrire n'en était pas une.** La machine de
travail a redémarré au milieu de ce chantier, et la suite de tests est passée
de 116 s à 190 s **sans qu'une seule ligne de production n'ait changé** — le
`--durations` ne montrait aucun test neuf en cause. En refaisant deux points du
tableau après ce redémarrage : la colonne **mémoire identique à l'octet près**
(135 Mo, 217 Mo), la colonne **temps multipliée par 1,8**.

*Correction apportée depuis (voir 5.75).* J'ai d'abord écrit « une seconde
machine ». Des mesures répétées ensuite montrent que cette machine-ci varie
seule d'un facteur 1,6 d'un moment à l'autre, tout en restant à 8 % près au
sein d'un même processus. Le fait décisif ne change pas et se renforce même :
la mémoire se reproduit, le temps non — qu'il s'agisse d'une autre machine ou
de la même à une autre heure.

C'est-à-dire que `MEMOIRE_PAR_TENON` est une propriété du logiciel et que
`CPU_PAR_TENON` n'en est pas une. Le plafond de durée que je venais de livrer
aurait été faux de 80 % chez qui héberge, et faux dans le mauvais sens :
autorisant des fabrications que la passerelle de l'hébergeur aurait coupées.

La correction n'est pas de rendre la constante réglable — personne ne saurait
quoi y mettre — mais de **mesurer la machine au démarrage** : une mosaïque de
32 × 32, chronométrée, corrigée par le rapport entre ce régime et celui du
plafond. Ce rapport-là, lui, est bien une propriété du logiciel : c'est la
forme de la courbe, pas sa hauteur. On mesure la hauteur là où le service
tourne, on applique la forme mesurée une fois ici. Coût : 1,9 s au démarrage,
imprimées. Sur cette machine, le plafond est passé de 37 500 à 23 942 tenons —
et c'est le bon chiffre.

Le défaut n'a pas été trouvé par une relecture ni par un test, mais par une
anomalie que j'aurais pu attribuer au bruit : *« la suite est plus lente »*.
Elle l'était pour une raison, et la raison invalidait une constante.

**Quatre défauts trouvés dans mon propre code neuf, avant de le livrer.**

1. La page de refus recopiait l'en-tête `Host` du client dans du HTML. Une
   page qui reflète ce que le client envoie offre au premier venu d'écrire ce
   que lira le visiteur suivant. Le lien, celui qui le détient l'a déjà : rien
   à recopier.
2. Le seau à jetons ne purgeait son dictionnaire qu'au moment d'**accorder**.
   Un client changeant de clé à chaque requête était donc toujours refusé — et
   faisait grossir le dictionnaire sans borne, c'est-à-dire exactement pendant
   une attaque, exactement quand il fallait qu'il tienne. Le limiteur devenait
   l'attaque.
3. Le seau anti-force-brute comptait aussi les **réussites**. Une famille ou un
   bureau — une seule adresse pour tout le monde — se serait retrouvé
   verrouillé dehors dès le sixième visiteur muni du bon lien. C'est un test
   qui l'a montré, en échouant sur une raison que je n'avais pas prévue.
4. La borne de sessions était appliquée *avant* l'insertion : la limite
   annoncée valait toujours `MAXIMUM + 1`.

Aucun de ces quatre n'aurait été trouvé par relecture. Trois l'ont été en
écrivant les tests, un en regardant le code neuf comme s'il venait de
quelqu'un d'autre.

**Ce qui reste ouvert, et qui est dit dans `docs/HEBERGEMENT.md` plutôt que
caché :** une seule instance (les sessions vivent dans le processus ; deux
instances derrière un répartiteur renverraient le visiteur à la page « atelier
privé » au milieu de son travail), une seule clé pour tout le monde, aucun
journal de qui a fabriqué quoi, et des résultats qui ne survivent pas à un
redémarrage. Aller au-delà demanderait un témoin signé et un magasin hors du
processus — deux chantiers, pas un réglage.

**Ce qui n'a pas pu être vérifié ici.** Le `Dockerfile` n'a pas été construit :
il n'y a pas de démon Docker dans cet environnement. Chacune de ses étapes a
été exécutée telle quelle à la main — installation de la palette dans
`/usr/share/ldraw`, `compileall`, import des modules, démarrage du lanceur
depuis une copie ne contenant *que* les fichiers que `COPY` prend, avec un
`HOME` étranger — et le trajet complet a été vérifié en vrai HTTP. Mais la
mécanique de Docker elle-même reste à essayer par qui hébergera.

---

### 5.75 « Que faut-il pour que tout soit optimisé ? » — mesurer d'abord, et se méfier de son propre profileur

La demande invitait à proposer une liste. Une liste d'optimisations non
mesurées n'est pas un plan, c'est une opinion. Voici ce que la mesure a dit —
y compris quand elle a réfuté mes deux premières idées.

**Le profileur ment, et ce dépôt le savait déjà.** `cProfile` place
`intersection_aabb` (3,2 millions d'appels) et `LDUVector.__post_init__`
(2,5 millions) en tête. Or la docstring de `_require_int`, écrite lors d'une
passe précédente, prévient noir sur blanc : *« cProfile facture son propre coût
PAR APPEL : ce sont les fonctions les plus appelées qu'il gonfle le plus »*.
Le profileur désignait donc exactement les fonctions qu'il déforme le plus.
J'ai failli optimiser un artefact de mesure.

**Ce que cette machine vaut comme instrument.** Huit fabrications identiques
dans un même processus : étendue 1,08×. La même mesure d'une heure à l'autre :
1,6×. Conclusion méthodologique, appliquée à tout ce qui suit — **aucun A/B
n'est valable ailleurs que dans un seul processus, entrelacé**. Une
optimisation de 10 % « prouvée » entre deux exécutions séparées ne prouve rien.

**La carte honnête du temps**, par les chronomètres que la chaîne tient
elle-même (deux mesures par exécution, aucun biais par appel) :

| Phase | Part |
|---|---:|
| contrôle (H1 à H6) | 40 % |
| modèle (solveur mosaïque) | 26 % |
| le reste (image, quantification, notice, PDF, exports) | 35 % |

**Hypothèse 1, réfutée par la mesure.** Mémoriser `solid_overlap` sur ses
arguments exacts. Instrumentation : 10 090 appels, **10 090 arguments
distincts, 0 % de répétition**. Un cache n'aurait jamais servi.

**Hypothèse 2, vraie mais décevante.** Les mêmes 10 090 appels ne comptent que
**179 formes relatives** : les coordonnées absolues ne se répètent jamais, la
géométrie relative se répète toujours. `solid_overlap` est équivariant par
translation — intersection et différence commutent avec la translation, donc
translater les cinq entrées translate la sortie, exactement. Prototype :
**+11 %** seulement. Raison : normaliser les deux opérandes **à chaque paire**
coûte presque autant que calculer — jusqu'à 226 vides par pièce, deux fois par
paire.

**Hypothèse 3, la bonne.** Normaliser **une fois par pièce** et non une fois
par paire : chaque géométrie reçoit un *numéro de forme*, et la clé d'une paire
se réduit à cinq entiers — deux numéros et un écart. Sur un carré de 96
tenons : 103 764 paires jugées, **1 046 situations géométriquement distinctes,
13 formes**. Mesuré en A/B entrelacé, livrables identiques : **+19 %** sur la
chaîne entière, et **42 % de moins sur H2**. Le mémo vit dans `collision.py`,
c'est-à-dire dans l'autorité elle-même : il ne court-circuite personne, il rend
un verdict que cette autorité a déjà prononcé sur la même situation.

Un mémo faux à cet endroit ne casserait pas la chaîne — il rendrait **H2 vert**
sur une mosaïque où deux pièces s'interpénètrent, la pire panne que ce dépôt
puisse produire. D'où huit tests qui ne vérifient pas qu'il est rapide mais
qu'il est *incapable* de changer un verdict : invariance par translation,
différentiel sur mille situations tirées au hasard, mémo chaud de mille CLEAR
suivi d'une pénétration réelle, non-réattribution des numéros de forme, oubli
d'une forme qui coûte un calcul et jamais un verdict, et 42 empreintes SHA-256
sur six configurations — dont un refus, qui doit être le même refus.

**Hypothèse 4, mesurée puis abandonnée.** Combien coûte la garantie ℤ³ ? On la
débranche — ce qui est interdit — et on mesure le plafond : **7,9 %**. Tout
« chemin rapide » qui préserverait la garantie n'en récupérerait qu'une
fraction. La garantie d'exactitude du contrat coûte 8 % : c'est bon marché.
Idée close, avec un chiffre plutôt qu'avec un avis.

**Le gain gratuit.** Trois paires de mesures alternées 3.11 / 3.13 pour annuler
la dérive de la machine : **−17 % de calcul et −8 % de mémoire**, sans toucher
une ligne. *(Chiffre refait en 5.76 après la pose des `__slots__` : il tombe à
−15 % et −12 %. Les deux changements mordent en partie sur la même chose.)* Les deux bornes du plafond hébergé en dépendent. L'image Docker est
déjà sur 3.13 ; le lanceur hébergé le dit maintenant quand il tourne sur plus
ancien.

**Fausse alerte, et elle mérite d'être écrite.** En vérifiant que le mémo ne
changeait rien, une configuration a refusé le modèle : `sections=4` sur 64 × 64,
dix violations H4/H5. Première réaction : le mémo. Vérification : le refus est
identique **sans** le mémo. Deuxième réaction : la découpe en sections est
cassée. Vérification : `--sections N` signifie *des sections de N tenons de
côté*, pas *N sections*. Je demandais des sections de quatre tenons — un carré
de quatre tenons ne peut pas être enjambé par une plate de jonction. Avec des
valeurs réelles (16, 32, 48 tenons), tout est livré. **L'instrument était faux,
pas le code** — pour la sixième fois dans ce projet, et c'est toujours la même
signature : une hypothèse sur une interface, jamais vérifiée dans le code.

Reste un point réel et mineur : à 2 et 3 tenons, la chaîne refuse **tout de
suite et en disant pourquoi** ; à 4, elle calcule puis échoue sur une liste
opaque de pièces flottantes. Les invariants font leur travail — rien de faux
n'est livré — mais le message pourrait arriver plus tôt. Ouvert, non corrigé,
et de faible gravité : personne ne demande des sections de quatre tenons.

---

### 5.76 La mémoire : deux hypothèses, une réfutée, et un tiers de `__dict__` vides

Suite directe de 5.75. Le calcul avait baissé de 19 % ; la mémoire, elle,
n'avait jamais été regardée. Elle décide pourtant seule de ce qu'un petit
conteneur peut fabriquer : à 512 Mo, c'est elle qui borne, pas la durée.

**Instrument.** Un fil qui échantillonne le RSS toutes les 20 ms, et des
repères posés autour des phases. Le RSS et non `tracemalloc` : c'est lui que
regarde le tueur de processus, et il compte ce que Python n'a pas rendu au
système. Sur un carré de 128 tenons, pointe à 243 Mo pour 9,4 Mo de livrables :

| Phase | Δ | Cumul |
|---|---:|---:|
| lecture, réduction, quantification | +10 Mo | 28 Mo |
| **modèle** | **+105 Mo** | 134 Mo |
| contrôle (assemble) | +30 Mo | 169 Mo |
| H2 | +51 Mo | 215 Mo |
| aperçus, nomenclature, notice, JSON | +28 Mo | 243 Mo |

**Hypothèse 1, réfutée par une mesure directe.** H2 construit une géométrie
monde par pièce — 16 471 géométries, 146 654 vides — et les tient toutes en
même temps. Le mémo de 5.75 permettrait de ne les matérialiser que sur les 1 %
de paires qui manquent le cache. Sauf que la mesure directe du dictionnaire dit
**15 Mo**, pas 51 : le reste du saut venait d'ailleurs dans la phase. Restructurer
le chemin de H2 — l'invariant où « faux » veut dire « vert alors qu'il fallait
rouge » — pour 6 % de la pointe : non. Idée close avant d'écrire une ligne.

**Hypothèse 2, la bonne, et elle était sous les yeux.** Les classes de base sont
des `@dataclass(frozen=True)`. Chaque instance porte donc un `__dict__` vide de
plus de cent octets — et ces classes se comptent par centaines de milliers : une
seule pièce 2×2 porte une pose, un AABB monde, huit connecteurs et une géométrie
à neuf vides. Pesée sur 200 000 boîtes : **523 octets l'une sans `__slots__`,
351 avec**.

`slots=True` sur `LDUVector`, `AABB`, `Orientation`, `Connector` et
`PlacedPart`. A/B alterné entre deux copies du dépôt, trois paires, empreinte
SHA-256 des livrables identique aux six exécutions :

| | sans slots | avec slots |
|---|---:|---:|
| mémoire (128 × 128) | 223 Mo | **174 Mo** (−22 %) |
| calcul | 10,86 s | **10,18 s** (−6 %) |

La mémoire ne bougeait pas d'un mégaoctet d'une exécution à l'autre — 223 Mo
trois fois de suite — ce qui rend cette mesure-là plus sûre que n'importe
laquelle des mesures de temps de ce registre.

`CollisionGeometry` en est volontairement exclue : elle garde son numéro de
forme sur l'instance (5.75), ce qui demande un dictionnaire ; et elle est cent
fois moins nombreuse que les AABB qu'elle contient, lesquelles ont bien des
slots. Coût de l'exception, mesuré : environ 2 % de la pointe.

**Ce que `sys.getsizeof` aurait fait croire.** Il rend 56 octets pour un
vecteur avec ou sans slots — il ne compte pas le `__dict__` attaché. Mesurer
200 000 objets au RSS donne 523 contre 351. Un troisième instrument de mesure
qui ment dans ce projet, après cProfile et le compteur de sections.

**Effet là où ça compte.** Le plafond hébergé d'un conteneur de 512 Mo passe de
15 915 à **17 825 tenons**, celui d'un giga-octet de 36 512 à **40 894** — 202
tenons de côté, plus de quatre fois le côté d'un set LEGO Art officiel. Un test
adversarial garde les `__slots__` : sans lui, un `slots=True` retiré par
distraction ferait remonter la mémoire d'un quart en silence, et aucun test
fonctionnel ne s'en apercevrait.

**Bilan des deux passes — et une erreur d'arithmétique corrigée ici même.**
J'avais d'abord écrit « −26 % de calcul (388,7 s → 337,5 s au plafond) ». Ces
deux nombres donnent **−13 %**, pas −26. Le 26 ne venait de nulle part : je
l'avais additionné de tête à partir des gains mesurés sur 96 × 96 (−19 %) et
128 × 128 (−6 %), qui ne s'appliquent pas au plafond et ne s'additionnent pas.

Ce qui est réellement établi, et à quel degré :

| Mesure | Gain | Solidité |
|---|---:|---|
| mémo de verdicts, 96 × 96, A/B **entrelacé dans un processus** | −19 % calcul | forte |
| `__slots__`, 128 × 128, A/B **alterné entre deux copies** | −22 % mémoire | très forte (223 Mo trois fois de suite) |
| `__slots__`, même protocole | −6 % calcul | moyenne (bruit du même ordre) |
| plafond 500 × 500, mémoire, avant/après | 3 439 → 2 945 Mo, −14 % | forte (la mémoire ne dérive pas) |
| plafond 500 × 500, calcul, avant/après | 388,7 → 337,5 s, −13 % | **indicative seulement** |

La dernière ligne est indicative et pas mieux : les deux mesures ont été prises
à des heures différentes, sur une machine dont 5.75 a établi qu'elle dérive de
60 %. La mémoire, elle, se reproduit à l'octet près — c'est pourquoi elle est
la seule comparaison avant/après de ce registre à laquelle on peut se fier
entre deux sessions.

S'ajoute **−15 % de calcul et −12 % de mémoire** en passant de Python 3.11 à
3.13 — chiffre refait APRÈS les slots, car celui d'avant (−17 % / −8 %) ne
valait plus.

---

### 5.77 Onze formes, seize mille pièces — et une piste réfutée en chemin

Troisième passe, après le mémo de verdicts (5.75) et les `__slots__` (5.76). Le
modèle restait le plus gros bloc de mémoire : 64 Mo sur 127. Recensement des
objets vivants à la fin d'une fabrication de 128 × 128 :

| Objet | Instances | **Valeurs distinctes** |
|---|---:|---:|
| `LDUVector` | 551 984 | 162 |
| `AABB` | 179 596 | — |
| `Connector` | 88 160 | **132** |
| géométries locales | 16 471 | **11** |
| tuples de connecteurs | 16 471 | **11** |

`PartDefinition.geometry()` et `.connectors()` rebâtissaient tout **à chaque
pose**. Seize mille copies de onze objets — et comme chaque géométrie porte
neuf vides, soit neuf AABB et dix-huit vecteurs, c'est là que naissaient la
plupart des 551 984 `LDUVector`.

Ces objets sont gelés et ne contiennent que des champs gelés : deux pièces du
même dessin peuvent partager le même objet sans qu'aucun code puisse s'en
apercevoir. Un `lru_cache(256)` sur `brick_geometry` et `brick_connectors`,
dont tous les arguments sont des entiers, suffit. A/B alterné entre deux copies
du dépôt, empreinte SHA-256 identique aux six exécutions — **et c'est la même
empreinte qu'avant les slots**, donc les trois passes n'ont pas déplacé un bit :

| | sans partage | avec partage |
|---|---:|---:|
| mémoire (128 × 128) | 177 Mo | **128 Mo** (−28 %) |
| calcul | 10,80 s | **9,48 s** (−12 %) |

**La piste réfutée, et elle valait ses cinq minutes.** Les 1 655 952
coordonnées de ces vecteurs ne comptent que **162 valeurs distinctes** :
interner les entiers semblait évident. Mesure du nombre d'objets entiers
réellement tenus : **89 983**, pas 1,6 million — Python les partage déjà
largement par simple réutilisation de références. Interner n'aurait rendu que
**3 Mo sur 175**, au prix d'un accès à un dictionnaire dans `__post_init__`,
c'est-à-dire sur le chemin le plus chaud de la chaîne. Refusé sur la mesure,
pas sur l'intuition — qui disait le contraire.

**Le rapport haut-sur-étalon monte à chaque passe** : 1,33 au départ, 1,45
après le mémo, 1,63 après le partage. Ce n'est pas une dérive, c'est le signe
que les optimisations portent : chacune retire une part quasi linéaire du coût
et laisse peser davantage ce qui croît plus vite. La constante est arrondie
au-dessus à chaque fois, jamais en dessous.

**Bilan des trois passes**, à livrables identiques au bit près :

| | départ | maintenant | |
|---|---:|---:|---:|
| calcul au plafond (250 000 tenons) | 388,7 s | 278,2 s | **−28 %** |
| mémoire au plafond | 3 439 Mo | 2 315 Mo | **−33 %** |
| plafond hébergé, conteneur 512 Mo | 15 915 tenons | 22 282 | **+40 %** |
| plafond hébergé, conteneur 1 Go | 36 512 tenons | 51 118 | **+40 %** |
| suite de tests | ~116 s | ~75 s | — |

La ligne « calcul au plafond » garde la réserve de 5.76 : les deux mesures sont
séparées dans le temps sur une machine qui dérive. La ligne mémoire, elle, est
solide — c'est la seule grandeur de ce dépôt qui se reproduise à l'octet près.

**Ce qui reste ouvert.** « Le reste » — quantification, aperçus, notice, PDF,
exports — n'a toujours pas été passé au crible qu'ont subi H2 et le modèle. Et
la mémoire résiduelle (2,3 Go au plafond) est maintenant structurelle : elle
tient à ce qu'un `LDUVector` soit un objet Python, ce que le contrat impose.
La réduire davantage demanderait une représentation en colonnes, c'est-à-dire
un autre contrat.

---

### 5.78 Seize pour cent de la chaîne pour une ligne de journal

Quatrième passe. Après les trois précédentes, « le reste » était devenu la
part dominante : **51 %** contre 25 % au modèle et 24 % au contrôle — exactement
ce que 5.77 annonçait comme prochaine mine.

Des chronomètres autour des fonctions de haut niveau, quelques dizaines
d'appels, aucun biais par appel :

| Phase | Part |
|---|---:|
| notice PDF | 17,6 % |
| **couleurs manquantes (`dominant_colors`)** | **16,0 %** |
| H2 collision | 13,8 % |
| modèle | 7,7 % |
| écart de détail | 7,4 % |
| aperçu (rendu) | 7,2 % |
| arbitrage du tramage | 6,7 % |
| assemblage (graphe) | 6,5 % |
| modèle JSON | 4,4 % |

Le deuxième poste est une **ligne de journal**. Pas un livrable : la phrase qui
dit *« 1620 tuiles veulent un bleu pâle autour de #AEC8E8, et votre palette n'a
que du Light Bluish Gray à 22 delta E »*. C'est une des lignes les plus utiles
que la chaîne écrive — elle transforme une plainte en décision — et elle
coûtait un sixième de tout le calcul.

La cause : des k-moyennes en Lab, douze passes sur tous les pixels, douze
centres chacune, avec une boucle intérieure écrite

    plus_proche = min(range(count),
        key=lambda c: sum((lab[t] - centres[c][t]) ** 2 for t in range(3)))

soit **5,3 millions de générateurs et 1,3 million de fermetures** pour un carré
de 96 tenons. Déroulée à la main, elle rend exactement la même chose, et les
trois raisons sont à écrire parce que ce sont les trois façons de se tromper :

1. `sum()` part de zéro et additionne dans l'ordre `t = 0, 1, 2` ; l'écriture
   `d0*d0 + d1*d1 + d2*d2` fait la même chose dans le même ordre, et `0 + d0`
   vaut exactement `d0` en virgule flottante.
2. `x ** 2` et `x * x` sont le même flottant IEEE.
3. `min` garde le **premier** minimum ; la boucle déroulée doit donc comparer
   avec un `<` strict et non un `<=`. C'est là qu'une réécriture dérape, et
   c'est invisible sauf sur des égalités — un test les provoque exprès.

| | avant | après |
|---|---:|---:|
| la phase | 0,74 s (16,0 %) | **0,15 s (3,7 %)** |
| la chaîne, A/B alterné, 128 × 128 | 9,62 s | **7,90 s** (−18 %) |

Empreinte SHA-256 des livrables identique aux six exécutions, et c'est
toujours la même qu'avant les trois passes précédentes.

**Où l'on s'arrête, et pourquoi.** Le profil est maintenant plat : notice 20 %,
H2 16 %, modèle 9,5 %, et six postes entre 3 et 9 %. Aucun poste dominant ne
reste. Les gains suivants demanderaient dix changements pour ce qu'un seul
rapportait ici — c'est le moment d'arrêter, et le dire vaut mieux que continuer
par habitude.

**Bilan des quatre passes**, livrables identiques au bit près :

| | départ | maintenant | |
|---|---:|---:|---:|
| calcul au plafond (250 000 tenons) | 388,7 s | 260,7 s | **−33 %** |
| mémoire au plafond | 3 439 Mo | 2 315 Mo | **−33 %** |
| calcul, 96 × 96 | 7,6 s | 4,2 s | **−45 %** |
| plafond hébergé, 512 Mo | 15 915 tenons | 22 282 | **+40 %** |
| plafond hébergé, 1 Go | 36 512 tenons | 51 118 | **+40 %** |
| plafond hébergé, 2 Go | 37 500 tenons | 57 142 | **+52 %** |
| suite de tests | ~116 s | ~75 s | — |

Les lignes de temps gardent la réserve de 5.76 : mesures séparées dans le temps
sur une machine qui dérive de 60 %. Les A/B entrelacés de chaque passe, eux,
sont solides ; c'est leur composition qui l'est moins que chacun d'eux.

**Le chiffre de Python 3.13, refait une troisième fois.** −17 % / −8 % avant
toute optimisation, −15 % / −12 % après les slots, **−6 % / −15 %** après les
quatre passes. Chaque optimisation mangeait une part de ce que 3.13 apportait :
les deux travaillent sur le coût *par objet*. Le gain de calcul n'est plus
distinguable du bruit et c'est écrit comme tel ; celui de mémoire, lui, se
reproduit à l'identique (85 Mo contre 72). Une mesure prise avant une
optimisation ne vaut plus rien après — trois fois de suite dans ce registre.

Le rapport haut-sur-étalon a monté à chaque passe — 1,33, puis 1,45, 1,63,
1,78. Ce n'est pas une dérive : chaque optimisation retire du coût quasi
linéaire et laisse peser ce qui croît plus vite. Il faudra le refaire monter
encore le jour où quelqu'un s'attaquera à la notice.
