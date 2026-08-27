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

## 6. Où en est-on de la demande produit

> photo → modélisation LEGO Art hyper précise → liste de course → notice de montage

La chaîne **existe et tourne** : `python3 demo_lego_art.py photo.png --studs 48`.

| Étape | État | Ce qui manque |
|---|---:|---|
| Photo → analyse | **~99 %** | JPEG (au huitième — coût mesuré à 0,5 ΔE, § 5.31), PNG, PPM, orientation EXIF, rééchantillonnage en lumière linéaire, recadrage au bon rapport, quantification CIEDE2000 exacte, alerte sous 2 px/tenon, recadrage attentionnel par énergie de gradient. **Interface web** : glisser-déposer, réglages, aperçus, ZIP (§ 5.50). Manque : rien d'identifié. |
| → modélisation LEGO Art | **~95 %** | Solveur + substrat validé H1–H6 et refusé quand il ne tient pas, palette officielle importable, fusion des tuiles, choix de palette au coût mesuré. **La fidélité est à la limite du médium** (§ 6.3). Relief en plateaux, aux seuils d'Otsu, et profondeur **mesurée** quand la photo en porte une (§ 6.10). Découpe en sections bâties séparément (§ 5.51). Manque : rien d'identifié en 2D. |
| → liste de course | **~90 %** | Nomenclature exacte, filtrée aux couleurs commandables, garde-fou anti-omission, export CSV, contrainte d'approvisionnement. export BrickLink prêt à l'envoi. Manque : la **table** de correspondance des couleurs, qui est une donnée et non du code, et les prix — hors périmètre assumé. |
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

**Des données, pas du code.** La table de correspondance des couleurs BrickLink
et le fichier `LDConfig.ldr`. Le code qui s'en sert existe et est testé ; ni
l'une ni l'autre n'a pu être vérifiée ici. Ce sont des décisions
d'approvisionnement, pas d'ingénierie.

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

---

## 7. Ce qu'un solveur devra respecter

Pour que la couche 2 se branche sans rouvrir le noyau :

1. Ne jamais construire un `PhysicalBond` — seul `evaluate_connector_pair` en émet, et H3 le vérifie.
2. Appeler `evaluate_placement` avant de poser, `add_part` pour poser : jamais reconstruire un `ConstructionGraph` à la main.
3. Passer une `ConnectorTolerance` explicite à chaque appel — il n'existe aucune valeur par défaut, et c'est voulu.
4. Utiliser `LatticeSearchApproximation` en production, la référence O(n²) en test de conformité — et vérifier P ⊆ C_fast, jamais C_ref ⊆ C_fast.
5. Ne pas sérialiser de liaisons : un document porte des pièces, l'oracle porte le jugement.
