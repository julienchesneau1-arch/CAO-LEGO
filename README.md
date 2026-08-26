# BFK-001 — BrickForge Kernel v3.3.2

Implémentation Python du contrat **BFK-001 v3.3.2**
(`docs/BFK001_IMPLEMENTATION_BRIEF_v3_3_2.md`).

Principe directeur : **séparation stricte des autorités — géométrie → collision
→ mécanique**. Arithmétique exacte dans ℤ³, immutabilité profonde, `PhysicalBond`
opaque.

État : **87 tests verts** (T1a–T14 + compléments + intégration H1–H6 + accroche
LEGO réelle + couche CAO + conformité par tirage aléatoire).

Toutes les zones d'ombre — fermées comme ouvertes — sont recensées dans
[`docs/ZONES_DOMBRE.md`](docs/ZONES_DOMBRE.md) : chacune est soit fermée avec sa
preuve, soit nommée avec la décision qui lui manque.

---

## La chaîne complète, en une commande

```bash
python3 demo_lego_art.py photo.jpg --studs 48 --hauteur 64 --sortie resultat/
```

JPEG, PNG ou PPM. L'orientation EXIF est appliquée, et la palette est
diagnostiquée **avant** de construire : si elle ne peut pas rendre la photo, la
commande le dit et nomme les couleurs qui manquent.

**Palette officielle.** Les 12 couleurs intégrées ne suffisent à aucune photo
(17,8 ΔE sur un paysage, contre 9,7 avec la palette officielle). Fournir
`--ldconfig LDConfig.ldr` — le fichier est livré avec LDraw, LeoCAD et
BrickLink Studio, et se trouve aussi dans le paquet PyPI `pyldraw`. Les
couleurs transparentes, chromées, nacrées et caoutchouc en sont écartées
automatiquement : une liste de course doit être commandable.

`--couleurs 24` restreint la mosaïque aux vingt-quatre couleurs qui servent le
mieux *cette* photo — et atteint désormais ce qui en demandait quatre-vingts
(6,89 contre 6,85 ΔE). Une liste de course trois fois plus courte à qualité
égale. Le sélecteur était bridé par un plafond de 24 grappes dans son propre
résumé de l'image ; voir § 5.30 du registre.

Produit `apercu.png`, `liste_de_course.csv`, `notice.txt`, **`notice.pdf`** et `modele.json` —
**mais seulement si le modèle passe les six invariants du noyau**. Une mosaïque
qui ne tiendrait pas ensemble n'est pas livrée.

Sur une photo 256×256 en 48×48 tenons : 2917 pièces, 4608 liaisons, 0 violation,
10 références, 126 étapes de montage, le tout en ~5 s.

Aucune dépendance : PNG, palette, quantification et rendu sont en bibliothèque
standard.

## Exécution

```bash
pytest                                  # toute la suite
pytest test_bfk001_adversarial.py       # T1a–T14 (Section M)
pytest test_bfk001_integration.py       # Phase 7, invariants H1–H6
pytest test_bfk001_cad.py               # couche CAO (hors contrat)
pytest test_bfk001_conformance.py       # propriétés, sur tirages aléatoires
pytest test_bfk001_lego_art.py          # mosaïque : ce que le noyau accepte et refuse
pytest test_bfk001_pipeline.py          # photo → modèle → liste de course → notice
pytest test_bfk001_booklet.py           # structure du PDF, rendu des pages, ordre vérifié
pytest test_bfk001_substrat.py          # emprise exacte du fond et connexité, 1521 formats
pytest test_bfk001_couleur.py           # lumière linéaire, CIEDE2000, palette officielle
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
| `bfk001/lego.py` | — | Métrologie du système LEGO en LDU, `LEGO_TOLERANCE`, briques et plates de référence (**hors contrat**) |
| `bfk001/rotations.py` | — | Les 24 rotations discrètes, énumérées et nommées (**hors contrat**) |
| `bfk001/fast_search.py` | H.4 | `LatticeSearchApproximation` : recherche O(n) avec preuve de complétude (**hors contrat**) |
| `bfk001/catalog.py` | — | Références LEGO, couleurs, nomenclature (**hors contrat**) |
| `bfk001/serialization.py` | — | Persistance JSON sans aucune liaison (**hors contrat**) |
| `bfk001/imaging.py` | — | Lecture PNG/PPM, rééchantillonnage par moyenne de bloc (**hors contrat**) |
| `bfk001/jpeg.py` | — | Décodeur JPEG baseline **au huitième** (DC seul), orientation EXIF (**hors contrat**) |
| `bfk001/palette.py` | — | Palette LEGO, import LDConfig, quantification CIE L\*a\*b\* (**hors contrat**) |
| `bfk001/mosaic.py` | — | Solveur LEGO Art : image → modèle avec substrat (**hors contrat**) |
| `bfk001/instructions.py` | — | Plan de montage acyclique, ordonné par portance (**hors contrat**) |
| `bfk001/booklet.py` | — | Notice imprimable : PDF écrit à la main, mosaïque bande par bande (**hors contrat**) |

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

## Couche CAO

Le noyau seul ne suffit pas à écrire un logiciel de conception. Cinq briques
manquantes ont été ajoutées **hors contrat**, chacune déléguant aux autorités :

| Besoin | Réponse | Garantie |
|---|---|---|
| « Puis-je poser cette pièce ici ? » | `evaluate_placement` | Verdict pur, sans état produit ; n'invente aucune règle — H2 (aucune pénétration), H6 (pas sous le plan), H4 (fondée ou reliée) |
| Poser / retirer sans tout recalculer | `add_part`, `remove_part` | Les liaisons existantes sont conservées **par identité** : la trace d'audit ne défile pas à chaque pose |
| Tourner une pièce | `all_rotations`, `rotation_x/y/z`, `Orientation.inverse`, `transform_world_to_local` | Groupe des 24, fermé et inversible, exact dans ℤ³ |
| Passer à l'échelle | `LatticeSearchApproximation` (O(n) prouvé), `GridSpatialIndex` (requête exhaustive) | H1 démontré, pas espéré ; l'élagage de H2 est sans perte car DISJOINT ⇒ CLEAR |
| Sauvegarder, acheter | `dumps_model` / `loads_model`, `bill_of_materials` | Un document ne porte **jamais** de liaison : l'oracle les ré-émet au chargement, sinon H3 tomberait |

---

## Métrologie LEGO

**1 LDU = 0,4 mm** (standard LDraw). Ce n'est pas une unité arbitraire : c'est le
plus grand diviseur commun des cotes du système, ce qui rend toutes les
dimensions exactement entières — et c'est précisément ce qui rend la décision
A.1 (arithmétique exacte dans ℤ³) applicable au LEGO sans approximation.

| Grandeur | LDU | mm |
|---|---:|---:|
| Pas de tenon | 20 | 8,0 |
| Demi-tenon (jumper) | 10 | 4,0 |
| Hauteur de brique | 24 | 9,6 |
| Hauteur de plate | 8 | 3,2 |
| Diamètre de tenon | 12 | 4,8 |
| Hauteur de tenon | 4 | 1,6 |
| Épaisseur de paroi | 4 | 1,6 |

3 plates = 1 brique : 3 × 8 = 24 LDU, exactement. Testé.

### Valeur de `ConnectorTolerance` : 0,5 LDU = 0,2 mm

`LEGO_TOLERANCE = ConnectorTolerance(max_position_error_ldu=0.5, max_angular_error_deg=0.0)`

Trois bornes justifient ce choix :

- **Borne haute — strictement < 1 LDU.** Dans ℤ³, deux sites de connexion
  distincts sont distants d'au moins 1 LDU ; l'écart réellement utile est même
  d'au moins 8 LDU (hauteur de plate) en vertical et 10 LDU (demi-tenon) dans le
  plan. Une tolérance sous 1 LDU est donc **exactement équivalente à exiger la
  coïncidence** : aucun bond fantôme n'est structurellement possible.
  `test_tolerance_is_lattice_safe` le vérifie sur les 26 voisins unitaires plus
  les décalages du système — ce n'est pas une supposition.
- **Borne basse — strictement > 0.** Le jeu d'accroche réel d'une pièce est de
  l'ordre du centième de millimètre (≈ 0,025 LDU). Une tolérance nulle serait
  juste pour un réseau parfait mais fausse dès que BFK-002 introduira de la
  géométrie mesurée ou non alignée sur le réseau. 0,5 LDU laisse un facteur 20
  au-dessus du jeu physique.
- **Choix — la moitié du quantum du modèle.** Rayon d'accrochage naturel : toute
  position est à moins d'un demi-LDU d'au plus un site du réseau.

`max_angular_error_deg = 0.0` dit la vérité du modèle : BFK-001 statue sur
l'égalité exacte des normales opposées et ne lit jamais ce champ.

Ce n'est **pas** une valeur par défaut — A.2 l'interdit. C'est une constante
nommée que l'appelant passe explicitement ; `ConnectorTolerance()` lève toujours
`TypeError`.

### L'accroche réelle, modélisée

La brique de référence inclut ses tenons dans l'`exterior`. Deux briques
empilées ont donc des extérieurs qui **se recouvrent** (`OVERLAPPING`), et seule
la soustraction exacte des voids évite le faux positif : les tenons de la brique
basse sont intégralement absorbés par la cavité de la brique haute →
`CONTACT`. Un décalage d'un demi-tenon, ou un enfoncement de 4 LDU →
`PENETRATION`. C'est le cas canonique du système, et il tombe pile sur ce que
`solid_overlap` sait faire.

Deux approximations assumées, **toutes deux du côté sûr** :

1. Un tenon cylindrique est modélisé par son AABB, donc un prisme carré de
   12 × 12 LDU. Le modèle est plus **gros** que la pièce réelle : il peut refuser
   un assemblage légal en diagonale, jamais accepter une pénétration réelle.
2. Le tube d'accroche interne n'est **pas** modélisé. L'accroche LEGO est un
   ajustement serré : tenon et tube s'interpénètrent physiquement, et c'est cette
   interférence qui tient la construction. Une autorité géométrique exacte
   classerait cela `PENETRATION`. L'élasticité est hors scope BFK-001 (cf.
   P0_E) : la cavité est donc un vide franc, et l'accroche est portée par
   l'oracle mécanique, pas par la géométrie.

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
`bfk001/validation.py` (H1–H6), `bfk001/orchestration.py` et `bfk001/lego.py`.
Aucun n'émet de jugement mécanique ou géométrique : ils appellent les autorités.
`lego.py` est la seule couche qui connaisse le système LEGO — le noyau, lui,
reste agnostique et ne manipule que des entiers.

### 8. Validations défensives à la construction

`Orientation` vérifie {−1,0,1}, MᵀM = I et det = +1 ; `AABB` vérifie
min ≤ max ; `Connector` vérifie que la normale est l'une des 6 directions
axiales unitaires ; `ConstructionState` refuse un `spatial_snapshot` exposant
`insert`/`remove`. Ces contrôles dérivent du contrat mais n'y sont pas écrits
comme obligations d'implémentation.

### 9. `collide()` transforme les vides à la demande

L'algorithme F.5 les transforme dès l'étape 1 ; ils ne servent qu'à l'étape 5.
Les transformer seulement en cas d'`OVERLAPPING` ne change aucun résultat — et
rend H2 **17× plus rapide** sur un modèle réel (2,48 s → 0,14 s sur 400 pièces),
parce qu'une pièce courante porte plus de vingt vides et que l'immense majorité
des paires ne se recouvrent pas.

### 10. T14 — assertion affinée

`solid_overlap()` réutilise légitimement `intersection_aabb()` en interne. T14
vérifie donc l'**ordre de première entrée** dans chaque autorité de la chaîne,
et qu'aucune n'est franchie deux fois (`geometric_relation`, `solid_overlap`,
`collision_status` : exactement un appel chacune).

---

## Colorimétrie : deux erreurs systématiques corrigées

**Le rééchantillonnage moyennait des octets sRGB.** sRGB est un encodage en
puissance ≈ 2,2 ; en moyenner les octets revient à moyenner des logarithmes. Un
damier noir/blanc renvoie exactement 50 % de la lumière — soit sRGB **188** — et
le code en donnait **127** (21 % de luminance). 23 ΔE d'erreur, systématiquement
dans le sens sombre, sur toutes les zones texturées d'une photo. On linéarise
maintenant, on moyenne, on réencode.

Le centroïde dans L\*a\*b\* minimise pourtant l'écart *par tuile* — c'est
démontrable. Il a été écarté : il répond à la mauvaise question. Une grande zone
de texture noire et blanche renvoie 50 % de la lumière, et une tuile à L\*=50 n'en
renvoie que 19 %. L'œil intègre les grandes surfaces.

**`nearest` choisissait un violet pour un bleu.** La distance euclidienne dans
L\*a\*b\* préférait Violet `#4354A3` à Blue `#0055BF` pour la cible `#005AB4` —
quasiment la même couleur — de 0,68 ΔE. C'est la distorsion connue de la région
bleue. `Palette.nearest` emploie désormais **CIEDE2000**, dont le terme de
rotation est centré sur H = 275°, c'est-à-dire sur les bleus. Coût : nul —
0,71 s contre 0,76 s, la conversion de la cible sortie de la boucle payait plus
cher que la formule.

Bout en bout, en CIEDE2000, palette officielle, 48×48 :

| | écart/tuile | tonale moyenne | tonale au pire |
|---|---:|---:|---:|
| avant | 17,00 | 11,19 | 24,35 |
| **après** | 17,80 | **6,02** | **9,12** |

**Palette officielle.** `LDConfig.ldr` est cherché aux emplacements où LDraw,
LeoCAD et BrickLink Studio le déposent — aucun drapeau à fournir si l'un d'eux
est installé. Il n'est pas embarqué dans ce dépôt : voir § 5.27 du registre.
Sur la même photo, 14,2 → **7,7 ΔE** par tuile.

### Le cadrage : la chaîne écrasait toute photo non carrée

Question simple, réponse accablante : **que devient un cercle ?** Un cercle
parfait dans une photo 400×300, quantifié en 48×48, sortait à **24 × 32
tenons** — un rapport de 0,750, écrasé d'un quart. `resample_box` applique le
rectangle source au rectangle cible : il étire. Or presque toute photo est en
4:3 et presque toute mosaïque LEGO Art est carrée. Sur un portrait, c'est fatal,
et aucun ΔE ne le voit puisque les couleurs restent justes.

Sans `--hauteur`, le CLI suit désormais les proportions de la photo : `--studs
48` sur du 4:3 donne 48 × 36 tenons, rien n'est rogné ni étiré. Demander un
carré, c'est demander un recadrage — annoncé, et déplaçable par `--cadrage 0..1`.

### Le tramage, rejeté puis adopté

Le tramage avait été rejeté sur un argument de physique : un tenon fait 8 mm,
deux tuiles ne fusionnent qu'à 55 m, donc l'œil voit le damier. L'argument est
juste — **Floyd-Steinberg complet transforme un ciel en neige**, l'essai visuel
est sans appel — mais il comparait au mauvais témoin. L'alternative n'est pas
« rien », c'est une **bande à bord franc**, et l'œil est plus sensible à un bord
qu'à du grain.

Le défaut est donc `"adaptive"` : on ne trame que là où la palette ne sait pas
produire la couleur voulue. Erreur tonale au pire **12,4 → 7,8 ΔE** pour deux
références de plus ; Floyd complet en aurait coûté dix-sept. La diffusion se
fait en **serpentin**, un rang sur deux à l'envers, ce qui casse les vermicules
diagonaux de Floyd-Steinberg — trois lignes, et trois références de moins.

La force de diffusion est **plafonnée à 0,5**, et ce plafond est le genou
mesuré de la courbe : à 0,5 le pire écart tonal a déjà rejoint celui du tramage
plein (8,54 ΔE), au-delà on n'achète plus que du **grain inventé** — la
variation d'une tuile à sa voisine que la photo ne contient pas. C'est la mesure
qui manquait à toutes les décisions précédentes sur le tramage : celle du coût.

`--tramage aucun|adaptatif|complet` pour trancher soi-même.

---

## Le coût : moitié moins de pièces, rendu identique

Une tuile 1×4 rouge montre exactement les mêmes quatre tenons rouges que quatre
tuiles 1×1. Fusionner les tuiles voisines de même couleur ne coûte donc **aucune
fidélité** — un test compare les aperçus octet par octet — et divise le nombre de
pièces par deux.

```bash
python3 demo_lego_art.py photo.jpg --references standard --couleurs auto
```

| Références | Pièces | Lots | Gain |
|---|---:|---:|---:|
| 1×1 seule | 2304 | 15 | — |
| 1×1, 1×2 | 1571 | 23 | −32 % |
| **1×1, 1×2, 1×4** (défaut) | **1283** | **30** | **−44 %** |
| + 1×6, 1×8 | 1105 | 50 | −52 % |

Le défaut s'arrête à trois références : au-delà, chaque point gagné coûte
plusieurs lots de plus à trouver, et les tuiles longues sont rares dans beaucoup
de couleurs. Le découpage d'une ligne est **optimal** (programmation dynamique,
pas glouton : avec des tuiles de 1, 3 et 4, un run de 6 fait 3+3 et non 4+1+1).

**Le programme ne connaît ni les prix ni les stocks.** Il minimise le nombre de
pièces et de lots, pas des euros — aucune donnée de prix n'est inventée. Si vous
savez ce que votre fournisseur a réellement en tuile, `--codes-couleur
0,1,4,14,15,71,72` impose la contrainte et toute l'optimisation se fait à
l'intérieur.

`--couleurs auto` cherche la plus petite palette qui reste dans la tolérance sur
**deux** critères — écart par tuile *et* justesse tonale. Le second est
indispensable : l'écart par tuile plafonne à huit couleurs alors que la justesse
tonale continue de s'améliorer jusqu'à quatre-vingts. Sur un paysage, 13 couleurs
au lieu de 80 coûtent 0,09 ΔE de justesse tonale — imperceptible — et
économisent 111 pièces et 5 lots. La commande annonce ce qu'elle abandonne.

---

## Le tramage se décide par image

Il n'a pas de bon réglage universel. Sur un paysage, le tramage adaptatif
améliore le pire écart tonal (12,4 → 7,5) ; sur un portrait aux grands aplats
de peau, il l'**aggrave** (10,2 → 11,5) et crible le visage de damier. Un défaut
fixe se trompe forcément sur l'une des deux.

`--tramage auto` (défaut) mesure les deux et tranche : **tramer si et seulement
si le pire écart tonal s'améliore d'au moins 1 ΔE**, le seuil de perception. Le
pire et non le moyen — le travail du tramage est de supprimer les faux contours,
pas de grappiller une moyenne.

Effet secondaire : ne pas tramer allonge les suites de même couleur, donc la
fusion des tuiles rend davantage. Sur le portrait, 776 tuiles au lieu de 1567.

---

## Le fond de la mosaïque

Deux couches de plates croisées, **rognées à l'emprise exacte de l'œuvre**, puis
**fusionnées en grandes plates** — 128 pièces au lieu de 657 sur une 48×48, pour
un fond que personne ne verra.

La fusion est sûre par construction, pas par balayage : contracter deux sommets
d'un graphe connexe laisse un graphe connexe, et fusionner des plates déjà
posées **est** une contraction. Repaver de zéro, en revanche, scinde le fond —
non pas à cause du réseau, qui tient toujours, mais parce que les cellules
rognées du bord doivent être découpées en pièces réelles, et cette découpe
réaligne les joints sur ceux de la couche du dessous (294 formats sur 441).
Sans rognage, la couche décalée dépasse d'un tenon en x et de deux en y sur
chaque bord : l'œuvre finie porte un liséré de plate grise nue.

Le rognage n'est pas gratuit. Au bord, une cellule se réduit parfois à un tenon
de large, et une plate 1×2 n'enjambe un joint de la couche du dessous — aux
multiples de 4 tenons — que si elle commence sur un tenon **impair**. Les
cellules de la couche décalée commencent à 4k+2, donc toujours sur un tenon
pair : leurs plates s'arrêtent pile sur les joints au lieu de les enjamber, et
le fond se scinde en bandes indépendantes. Une plate 1×1 en tête re-phase la
colonne.

Ce n'est pas une preuve, c'est une vérification : `test_bfk001_substrat.py`
balaie les 1521 formats de 2×2 à 40×40 et vérifie que le fond couvre exactement
l'emprise et reste d'un seul tenant. Le détail des deux variantes qui ont échoué
est en § 5.22 du registre.

---

## La notice PDF

`booklet.py` écrit le PDF à la main — objets numérotés, table de renvois,
images compressées par `zlib`, polices de base. Rien à embarquer, aucune
dépendance. Un test relit le fichier octet par octet : chaque décalage de la
table doit tomber pile sur l'en-tête de son objet, chaque flux doit se
décompresser, aucun objet ne doit être orphelin. Un lecteur PDF répare
silencieusement une table cassée ; « ça s'ouvre » ne prouve donc rien.

Le fascicule ne suit **pas** une page par étape du plan. `plan_build` regroupe
par couleur : sur une mosaïque 48×48 il produit 733 étapes du type « poser 4
tuiles rouges », dispersées dans 2304 cases. La notice procède comme les
notices LEGO Art officielles — **ligne par ligne**, avec le comptage des suites
(« 5 gris foncé · 9 vert · 4 gris foncé ») — et tient en **16 pages**.

Le plan reste l'autorité sur ce qui *peut* être posé quand ; le fascicule
choisit seulement l'*ordre*, et `_verifier_ordre` refuse d'écrire le PDF si
l'ordre choisi violait une dépendance du plan.

Trois règles de rendu, chacune née d'un défaut vu à l'image (§ 5.20 du
registre) :

- toute réglure tracée **dans** la mosaïque **assombrit** au lieu de peindre —
  un trait opaque mentirait sur la teinte de la tuile qu'il recouvre ;
- ce qui reste à poser est **damié**, motif qui n'est la couleur d'aucune tuile
  et ne peut donc pas être lu comme une consigne ;
- les joints de la couche de fond précédente sont retracés par-dessus la
  suivante, sans quoi la page ne montrerait plus le **décalage** qui fait tenir
  le fond.

Les chiffres des réglettes sont du **texte PDF**, pas des pixels : nets à
l'impression, et rien à embarquer comme fonte matricielle.

La lecture emploie des **codes courts avec légende** — « 3A · 5B · 12C » — et
non les noms LDraw complets : « Light Bluish Gray » et « Dark Bluish Gray » ne
diffèrent que par leur premier mot et se confondent à la lecture. Le nom complet
reste dans la légende, sur chaque page, et dans la liste de course.

Tout le contenu est vérifié à l'intérieur d'une **marge sûre de 10 mm**, celle
qu'une imprimante de bureau ne rend pas — vérifier « dans la page » ne veut rien
dire pour un document destiné au papier.

---

## Points restés ouverts (Sections N et Q)

| Point | État |
|---|---|
| Valeur numérique de `ConnectorTolerance` | **Fixée pour BFK-001 :** `LEGO_TOLERANCE` = 0,5 LDU (0,2 mm), justifiée ci-dessus et vérifiée par `test_tolerance_is_lattice_safe`. Reste à réexaminer en BFK-002, quand de la géométrie non alignée sur le réseau apparaîtra. Aucune valeur par défaut n'existe dans le code. |
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
| `ConnectorTolerance` sans défaut ; angle non utilisé | ✅ `ConnectorTolerance()` lève `TypeError` |
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
