# BFK-001 — BrickForge Kernel v3.3.2

Implémentation Python du contrat **BFK-001 v3.3.2**
(`docs/BFK001_IMPLEMENTATION_BRIEF_v3_3_2.md`).

Principe directeur : **séparation stricte des autorités — géométrie → collision
→ mécanique**. Arithmétique exacte dans ℤ³, immutabilité profonde, `PhysicalBond`
opaque.

État : **428 tests verts** (T1a–T14 + compléments + intégration H1–H6 + accroche
LEGO réelle + couche CAO + conformité par tirage aléatoire + toute la couche
LEGO Art : palette, mosaïque, relief, notice, atelier, commandes).

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
`--ldconfig LDConfig.ldr` — ou rien du tout si `LDRAWDIR` est posée, ou si
LDraw, LeoCAD ou BrickLink Studio est installé : le fichier est alors trouvé
tout seul. Il se trouve aussi dans le paquet PyPI `pyldraw`. Les
couleurs transparentes, chromées, nacrées et caoutchouc en sont écartées
automatiquement : une liste de course doit être commandable.

`--couleurs 24` restreint la mosaïque aux vingt-quatre couleurs qui servent le
mieux *cette* photo — et atteint désormais ce qui en demandait quatre-vingts
(6,89 contre 6,85 ΔE). Une liste de course trois fois plus courte à qualité
égale. Le sélecteur était bridé par un plafond de 24 grappes dans son propre
résumé de l'image ; voir § 5.30 du registre.

Produit `apercu.png`, `apercu_source.png`, `apercu_joints.png`, `liste_de_course.csv`, `notice.txt`, **`notice.pdf`**, **`modele.ldr`** et `modele.json` (plus `commande_bricklink.xml` avec `--bricklink`, `commande_lego.csv` avec `--elements`) —
**mais seulement si le modèle passe les six invariants du noyau**. Une mosaïque
qui ne tiendrait pas ensemble n'est pas livrée.

Sur une photo 256×256 en 48×48 tenons : 2917 pièces, 4608 liaisons, 0 violation,
10 références, 126 étapes de montage, le tout en ~5 s.

Aucune dépendance : PNG, palette, quantification et rendu sont en bibliothèque
standard.

## L'atelier, dans le navigateur

```bash
python3 app_lego_art.py
```

Puis <http://127.0.0.1:8000> : déposez une photo, réglez la taille et le relief,
récupérez le dossier complet en ZIP. Aucune dépendance — `http.server` et
`zipfile` sont dans la bibliothèque standard, et la page est un seul fichier
sans une seule ressource externe.

**Trois gestes, pas huit réglages.** ① la photo ② le format ③ fabriquer. Le
format se choisit sur des pastilles (32 / 48 / 64 / 96 tenons, avec les cm), la
couleur du cadre sur des pastilles de couleur, et tout le reste — tramage,
sections, nettoyage, seuils — se replie sous « Réglages fins », **après** le
bouton : l'action principale ne se cherche pas derrière deux sections repliées.

**Le comparateur.** Sur l'aperçu, une poignée qu'on tire révèle la photo sous
l'œuvre. Ce n'est pas la photo brute : c'est
`apercu_source.png`, la photo **telle que la mosaïque l'a vue** — même rognage,
même moyenne par tenon, même cadre. Elle se superpose au pixel près, sans quoi
on croirait juger la quantification en regardant un décalage. Elle montre au
passage ce que le cadrage a coupé, qui n'était visible nulle part.

Aucun fichier n'est chargé de l'extérieur : la frise de tenons, les boutons qui
s'enfoncent comme une brique et les tenons qui se posent pendant la fabrication
sont du CSS. La page reste utilisable hors ligne.

Il n'y a **pas deux chaînes**. L'interface appelle `bfk001/pipeline.py`,
exactement comme `demo_lego_art.py` : deux façades, un seul calcul, aucune
divergence possible. C'est le refactor qui a révélé que la chaîne n'était pas
déterministe (§ 5.49) — comparer deux implémentations est un détecteur que la
relecture ne remplace pas.

Le serveur écoute sur la boucle locale, et ce n'est pas un réglage timide :
rien n'authentifie qui que ce soit et chaque requête coûte plusieurs secondes de
calcul. Rien n'est servi depuis le disque — tout ce qui sort a été fabriqué en
mémoire pendant la requête, ce qui retire d'un coup toute la famille des
traversées de chemin. Un fichier se télécharge par son **nom**, cherché dans le
dictionnaire du résultat : il ne peut désigner que ce qui vient d'être fabriqué.

La seule chose que l'atelier écrit hors du dossier de sortie, ce sont les
**catalogues de commande** — et seulement si on lui donne un dossier où les
garder. Sans dossier, `Atelier()` ne touche à rien : une bibliothèque n'a pas à
écrire dans le dossier personnel de qui l'importe parce que c'est pratique pour
l'application.

---

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
pytest test_bfk001_atelier.py           # la chaîne partagée, et un vrai aller-retour HTTP
pytest test_bfk001_pickabrick.py        # commande LEGO : ce qu'un catalogue d'elements a le droit de dire
pytest test_bfk001_page.py              # la page dans un vrai navigateur (se saute sans Playwright)
```

Aucune dépendance hors `pytest` (bibliothèque standard uniquement). Un seul
fichier de tests en demande une de plus, `playwright`, et il se saute
proprement sans elle : c'est le seul moyen d'exécuter le JavaScript de la
page, et deux défauts s'y cachaient que vingt tests verts ne voyaient pas
(§ 5.50). Rien de ce qui est **livré** n'en a besoin.

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
| `bfk001/imaging.py` | — | Lecture PNG/PPM, rééchantillonnage par moyenne de bloc en lumière linéaire, et par **médiane** pour ce qu'on n'a pas le droit de moyenner (**hors contrat**) |
| `bfk001/jpeg.py` | — | Décodeur JPEG baseline **au huitième** (DC seul), orientation EXIF (**hors contrat**) |
| `bfk001/palette.py` | — | Palette LEGO, import LDConfig, quantification CIE L\*a\*b\* (**hors contrat**) |
| `bfk001/mosaic.py` | — | Solveur LEGO Art : image → modèle avec substrat (**hors contrat**) |
| `bfk001/instructions.py` | — | Plan de montage acyclique, ordonné par portance (**hors contrat**) |
| `bfk001/booklet.py` | — | Notice imprimable : PDF écrit à la main, mosaïque bande par bande (**hors contrat**) |
| `bfk001/ldraw.py` | — | Export `.ldr` : conventions d'axes et d'origine lues dans une pièce officielle (**hors contrat**) |
| `bfk001/bricklink.py` | — | Liste de souhaits BrickLink ; refuse de deviner une couleur absente de la table (**hors contrat**) |
| `bfk001/pickabrick.py` | — | Commande LEGO Pick a Brick : l'**element id** s'importe d'un catalogue, il ne se calcule pas (**hors contrat**) |
| `bfk001/depth.py` | — | Profondeur **mesurée** : cartes externes, et extraction de la carte embarquée par les appareils en mode portrait (**hors contrat**) |
| `bfk001/pipeline.py` | — | **La chaîne** : photo → fichiers livrables, en mémoire. Une seule, appelée à l'identique par la commande et par l'interface (**hors contrat**) |
| `bfk001/webapp.py` | — | L'atelier dans le navigateur : serveur local, page autonome sans ressource externe, catalogues de commande déposés et retenus (**hors contrat**) |
| `bfk001/panels.py` | — | Découpe en sections bâties séparément, et la couche de plates qui les réunit (**hors contrat**) |

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

## Choisir une couleur et en mesurer une : deux outils

`delta_e` est CIEDE2000, exacte à quatre décimales sur les quinze paires de
contrôle de Sharma. Elle **mesure**.

`delta_e_selection` est CIEDE2000 **sans son terme de rotation**, et c'est elle
qui **choisit**. Ce n'est pas une approximation. Le terme croisé RT·tC·tH
modélise une interaction de la région bleue pour de *petits* écarts — la CIE
borne explicitement la formule aux écarts faibles. Choisir dans une palette de
quatre-vingts teintes, c'est comparer des écarts de 5 à 40, hors de son domaine.

Trouvé sur la première photographie réelle passée dans la chaîne. Pour un gris
sombre neutre, le terme retirait **731 au carré de la distance** et faisait
gagner un violet saturé : des dizaines de tuiles magenta sur une porte noire.
Le pire écart tonal est passé de 18,2 à 10,8 ΔE. Détail en § 5.53 du registre.

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

**Palette officielle.** `LDConfig.ldr` est cherché d'abord via **`LDRAWDIR`** —
la variable d'environnement que la distribution LDraw pose elle-même et que tous
ses outils lisent, c'est-à-dire en demandant à l'installation où elle est plutôt
qu'en le supposant — puis dans seize emplacements où LDraw, LeoCAD et BrickLink
Studio le déposent. Aucun drapeau à fournir si l'un d'eux est installé.

Il n'est **pas** embarqué dans ce dépôt, et c'est une décision, pas un oubli : la
licence CC BY 2.0 livrée avec LDraw définit l'Œuvre comme les pièces portant le
marqueur `0 !LICENSE Redistributable under CCAL version 2.0`. `3001.dat` le
porte — c'est ce qui a permis d'en tirer les conventions d'axes de l'export
LDraw. `LDConfig.ldr` ne le porte pas. On ne redistribue pas un fichier dont la
licence n'a pas pu être confirmée (§ 5.27 et § 5.55).
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

## Les tuiles isolées : moins de grain et moins de pièces

Une tuile dont **aucune voisine ne partage la couleur** vient presque toujours
de la quantification et non de la photo : elle est née du choix de palette. Elle
coûte une pièce à elle seule et brise la suite qui la traverse.

`--debruitage 4` (le défaut) lui donne la couleur dominante de ses voisines, à
deux conditions :

1. **au moins deux voisines** partagent cette couleur — une tuile entourée de
   quatre teintes différentes est dans une zone de détail, pas dans un aplat ;
2. **l'écart à la photo ne s'aggrave pas de plus de 4 ΔE** — c'est ce qui
   protège les vrais détails isolés : un œil sombre au milieu d'une joue dépasse
   largement quatre ΔE et reste.

Palette officielle, 48 tenons, cadre compris :

| Image | Pièces | Lots | Tuiles isolées | ΔE par tuile |
|---|---|---|---|---|
| vélo | 1124 → **1069** | 39 → 38 | 142 → **91** | 7,82 → 7,84 |
| tournesols | 1091 → **1047** | 19 → 19 | 66 → **14** | 6,16 → 6,19 |
| portrait | 1401 → 1395 | 13 → 13 | 31 → **20** | 10,55 → 10,56 |

Le gain va **dans les deux sens** — moins de grain à l'œil, moins de pièces à
poser — et le prix tient dans la deuxième décimale. `--debruitage 0` le désactive.

---

## Le coût : moitié moins de pièces, rendu identique

Fusionner les tuiles voisines de même couleur ne change **aucune couleur** — une
1×4 rouge montre les mêmes quatre tenons rouges que quatre 1×1 — et divise le
nombre de pièces par deux.

Elle change en revanche la **surface**, ce que ce dépôt a d'abord nié. Une 1×4
n'a pas de joint interne là où quatre 1×1 en ont trois : le résultat n'est plus
la grille régulière des sets LEGO Art officiels, c'est un appareil à joints
décalés, comme un mur de briques. Les sets officiels n'emploient que des 1×1,
malgré le coût — ils achètent l'uniformité. `apercu_joints.png` montre la
différence avant de commander, et `--references minimal` rend la grille.

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

## Recadrage

Une photo 4:3 dans une mosaïque carrée doit être rognée. `--cadrage auto`
(défaut) place la fenêtre là où l'**énergie de gradient** est la plus forte —
un centrage aveugle coupe la tête d'un sujet haut dans le cadre : mesuré, y
100…400 au lieu de y 16…316 sur un portrait 300×500.

Le critère ne reconnaît rien : il mesure du détail. Un fond de feuillage
derrière un visage lisse l'attire vers le feuillage — un test le démontre.
`--cadrage 0.3` reprend la main.

---

## La table de couleurs BrickLink s'importe

`LDConfig.ldr` porte le **LEGOID** — l'identifiant de couleur du système LEGO —
en commentaire au-dessus de chaque couleur, pour 131 de ses 162 entrées.
BrickLink publie le même identifiant dans son export de couleurs. La
correspondance se **déduit** donc, elle ne se recopie pas :

```bash
python3 demo_lego_art.py photo.jpg --bricklink couleurs_bricklink.tsv
```

`--bricklink` accepte indifféremment l'export téléchargé depuis BrickLink ou une
table à deux colonnes remplie à la main — le format est reconnu tout seul.
L'appariement se fait d'abord **par LEGOID** (exact), puis **par nom normalisé**
(`Dark_Bluish_Grey` = `Dark Bluish Gray`). Ce qui ne s'apparie ni par l'un ni par
l'autre est **rendu, pas deviné**, et la chaîne écrit `couleurs_a_completer.csv`
avec le nom, la valeur RVB et le LEGOID de chaque couleur manquante. Une ligne
remplie suffit ; une ligne laissée vide est une absence, pas une erreur.

**Aucune correspondance n'est écrite de mémoire dans ce dépôt.** Une liste de
course avec une couleur inventée est pire qu'une liste incomplète : la seconde se
voit, la première se paie à la livraison.

---

## Commander la liste

```bash
python3 demo_lego_art.py photo.jpg --bricklink couleurs.csv
```

Produit `commande_bricklink.xml`, uploadable tel quel comme liste de souhaits.

Les références de **pièces** sont communes à LDraw et BrickLink — rien à
traduire. Les codes **couleur**, non, et la correspondance n'est dérivable ni du
RVB ni du nom. Le dépôt n'en fournit donc aucune : `couleurs.csv` est une table
à deux colonnes (`code LDraw, code BrickLink`) que vous alimentez depuis la
source de votre choix.

**Ce qui n'est pas dans la table n'est pas deviné** : l'export refuse et nomme
les couleurs manquantes. Une liste incomplète se paie en pièces manquantes le
jour du montage ; une liste fausse se paie en pièces inutilisables.

---

## Commander chez LEGO, directement

Oui, mais pas avec le même fichier. Pick a Brick a un bouton **« Upload list »**
qui avale un CSV à deux colonnes, `elementId,quantity`, jusqu'à **400 références
différentes** par envoi. Une chose seulement sépare notre nomenclature de ce
fichier, et elle est de taille.

Pick a Brick ne veut pas le numéro de **moule** (3024, 3020, 2431…) mais
l'**element id** : le numéro qui désigne un moule **dans une couleur**. Et ce
numéro est **attribué, pas calculé**. Il n'existe aucune fonction de (moule,
couleur) vers element ; deux couleurs voisines d'une même pièce ont des numéros
sans aucun rapport. Le déduire est impossible, l'inventer est exclu.

Donc la même règle que pour BrickLink, pour la même raison : **on importe.**

```bash
# catalogue portant lui-même les noms de couleur (export BrickLink, par ex.)
python3 demo_lego_art.py photo.jpg --elements catalogue.csv

# catalogue qui ne désigne ses couleurs que par un numéro (Rebrickable)
python3 demo_lego_art.py photo.jpg \
    --elements elements.csv --elements-couleurs colors.csv
```

Produit **`commande_lego.csv`**, à déposer tel quel sur Pick a Brick — et
`commande_lego_1.csv`, `commande_lego_2.csv`… si la mosaïque dépasse les 400
lots, parce qu'au-delà l'envoi échoue en bloc sans dire que c'est le *nombre de
références* qui gêne.

Trois façons de désigner une couleur sont reconnues, par ordre de confiance :
un **identifiant LEGO** (exact — LDConfig porte le même, c'est le LEGOID), un
**nom** (apparié après normalisation), ou un **identifiant nu**, qui est
**refusé seul**. Le numéro 71 vaut `Light Bluish Gray` chez LDraw et tout autre
chose ailleurs : l'interpréter au hasard ne donnerait pas une liste incomplète
mais une liste **fausse**, des pièces de la mauvaise couleur livrées et payées.
Avec la table de couleurs qui accompagne le catalogue, le même fichier passe.

Une différence assumée avec l'export BrickLink : ici, un lot introuvable
**n'empêche pas** l'écriture du fichier. Le mode de panne n'est pas le même —
chez BrickLink il faudrait *deviner un code* et l'erreur ne se voit qu'à la
livraison ; ici un lot introuvable est un lot **absent**, constaté à l'upload,
et `pieces_sans_element.csv` le nomme avec son LEGOID pour qu'on le cherche à la
main. Perdre les 45 autres lots pour un lot exotique ne protégerait de rien.

**Ce que ce dépôt ne saura jamais** : qu'un element existe au catalogue ne dit
rien de sa **disponibilité**. Pick a Brick a son propre stock, variable selon le
pays et le jour. Aucun prix, aucune disponibilité n'est inventé ici ; c'est
l'envoi lui-même qui dira ce qui est vendable aujourd'hui.

---

## Commander depuis l'atelier

C'est le chemin le plus court, et il ne demande aucune ligne de commande.

**Une fois, pour toute la vie de l'installation.** Ouvrez
« Catalogues de commande » dans la colonne de gauche, déposez-y le catalogue
d'elements ([`elements.csv` chez Rebrickable](https://rebrickable.com/downloads/),
avec `colors.csv`) et l'export de couleurs BrickLink si vous en voulez la liste
de souhaits. Le `.csv.gz` se dépose **tel quel** : c'est reconnu aux octets
d'en-tête, pas à l'extension, et décompressé pour vous.

Ce qui est gardé sur la machine (`~/.brickforge` par défaut, `--memoire CHEMIN`
ailleurs, `--sans-memoire` nulle part) n'est **pas le catalogue d'origine** mais
ce qu'on en a **retenu** : quelques centaines de lignes vérifiées, où les
couleurs sont désignées par leur **nom**. Deux conséquences — le fichier est
minuscule, et `colors.csv` n'est plus nécessaire au redémarrage suivant.

**Ensuite, à chaque œuvre.** La carte **Commander** apparaît sous les chiffres :

| | Ce que fait le bouton | Pourquoi |
|---|---|---|
| **LEGO Pick a Brick** | télécharge `commande_lego.csv` | son formulaire prend un **fichier** |
| **BrickLink** | met le XML dans le **presse-papier** | son formulaire d'import ne prend **pas** de fichier — il faut coller |

Chaque encadré porte le lien vers la page où déposer, ouverte dans un nouvel
onglet. Les lots sans element id sont dits en rouge, avec leur propre fichier.

Sans catalogue, la carte le dit et **ouvre le panneau toute seule** : la réponse
est à trois centimètres de la question.

Tout reste faisable en ligne de commande — les catalogues se donnent aussi au
lanceur, et l'atelier les reprend :

```bash
python3 app_lego_art.py --bricklink couleurs.csv \
    --elements elements.csv.gz --elements-couleurs colors.csv
```

Et `liste_de_course.csv`, la liste **lisible**, gagne une colonne `element_id`
dès qu'un catalogue est chargé. Les deux fichiers sortent de la même fonction —
un test vérifie qu'ils disent la même chose, parce que personne ne compare
jamais un CSV à deux colonnes avec une liste de courses.

---

## Export LDraw

`modele.ldr` s'ouvre dans LeoCAD, BrickLink Studio ou LDView : le modèle en 3D,
pièce par pièce, avec ses vraies couleurs.

Deux données étaient nécessaires, et elles ont été **lues** dans `3001.dat`
officiel, pas devinées : l'origine des pièces (centre de l'empreinte, face
supérieure du corps) et la convention d'axes (`y_ldraw = −z_noyau`). Le module
vérifie à l'import que le changement d'axes a un déterminant de **+1** — un
déterminant −1 serait une réflexion, et une mosaïque exportée en miroir ne se
signalerait par rien.

Le test relit le fichier produit et compare les empreintes reconstruites à
celles du noyau : exact sur les 24 rotations.

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

## Le relief

`--relief N` donne du volume à l'œuvre : chaque tuile est surélevée de 0 à N
plates (3,2 mm chacune), sur des couches de plates fusionnées posées sous la
mosaïque. Le noyau valide ce volume sans rien changer — il est 3D depuis le
premier jour.

**Le relief ne coûte aucune précision.** L'écart par tuile est identique à zéro,
un, deux ou six étages : la couleur se décide dans le plan, la hauteur en z. Il
coûte des pièces, et seulement des pièces : +10 % pour un étage, +17 % pour
deux, +33 % pour quatre.

**Le relief se lit sur une grille non tramée, jamais sur celle qu'on pose.** Le
tramage échange de la justesse tonale contre du bruit spatial, et il est gagnant
parce que l'œil fond ce bruit dans les couleurs. Il ne le fond jamais dans les
hauteurs : une marche de 3,2 mm porte une ombre. Un relief tramé est un lit de
clous — 1473 tours isolées sur 3840 tenons, 22 % du modèle dépensés en grain.
`relief_from_image` quantifie donc une seconde fois **sans tramage**, uniquement
pour lire les hauteurs, puis régularise en plateaux par une médiane 3×3. Les
couleurs posées ne changent pas d'un ΔE.

La commande affiche les deux mesures qui disent si le relief est une sculpture
ou du grain relevé — nombre de plateaux et nombre de cases isolées — et prévient
quand il mouchette :

```
  relief  : 2 etage(s), 6.4 mm d'epaisseur — convention du bas-relief, clair = haut
            3 plateaux (le plus grand : 2503 tenons), 0 case(s) isolee(s)
```

**Ce qu'il faut savoir avant d'en attendre un set officiel.** Une photo ne
contient aucune profondeur : rien dans le fichier ne dit qu'un visage est devant
un mur. Élever selon la clarté est une **convention** — celle du camée — et elle
se trompe exactement là où la photo la contredit : un sujet sombre sur fond clair
sortira en creux. `--relief` accepte `invert` par l'API, et `build(heights=…)`
accepte n'importe quelle autre carte.

Le relief obtenu est **topographique** : des terrasses de niveau. Celui d'un set
LEGO Art est dessiné à la main et change aussi de *type* de pièce selon
l'endroit. Au-delà de deux étages les bandes de niveau deviennent plus fines
qu'un tenon et se fragmentent — la richesse du relief s'achète en **résolution**,
pas en étages : à 96×96, quatre étages donnent 112 plateaux pour 0,7 % de cases
isolées, contre 53 plateaux pour 1,6 % à 48×48.

---

## La profondeur : mesurée plutôt que conventionnelle

Le relief tiré de la clarté est une **convention** — celle du camée. Elle se
trompe exactement là où la photo la contredit : un sujet sombre sur fond clair
sort en creux. Deux chemins donnent une profondeur **mesurée**, et la commande
affiche toujours lequel a servi :

```
  relief  : 2 etage(s), 6.4 mm d'epaisseur
            source : carte de profondeur fournie (240x240) — profondeur MESUREE
```

**`--carte-profondeur fichier.png`** accepte une carte PNG, PPM ou JPEG. C'est
le pont vers l'état de l'art : un estimateur monoculaire (MiDaS, Depth Anything,
Marigold) en produit d'excellentes, hors de ce dépôt, avec un réseau de neurones
qu'il serait absurde d'embarquer ici. Ajoutez `--profondeur-inversee` si la carte
encode une distance (proche = sombre) plutôt qu'une disparité.

**La carte embarquée dans le JPEG** est lue automatiquement, sans rien demander.
Un téléphone en mode portrait *mesure* la profondeur et beaucoup d'appareils
l'écrivent dans le fichier à côté de l'image. Les deux formats de Google se
lisent : GDepth (base64 dans le XMP, réassemblé quand il déborde en segments
étendus) et Dynamic Depth (le XMP est un annuaire, les images sont concaténées à
la suite du fichier). La carte est **redressée** comme la photo : elle est
écrite dans le repère des pixels stockés et ne porte pas d'EXIF à elle, alors
que la photo décodée a déjà subi sa rotation — sans ce redressement, toute photo
de téléphone prise en portrait échouait au contrôle de proportions. Réserve
honnête : les conteneurs de test sont fabriqués à la norme, ils vérifient
l'analyseur contre le **format**, pas contre les particularités d'un appareil
réel.

**Le contrôle qui compte.** La carte doit avoir les proportions de la photo à
2 % près, sinon `DepthMismatch` refuse. Une carte issue d'un autre recadrage
produirait un relief parfaitement propre et parfaitement faux — le pire des
résultats, parce que rien ne le signale à l'œil.

**Une carte de profondeur se réduit à la médiane, jamais à la moyenne.**
Moyenner deux distances de part et d'autre d'un bord invente une distance qui
n'existe nulle part : le sujet à 1 m, le mur à 4 m, un fantôme à 2,5 m sur tout
le contour. Sur une carte à deux profondeurs réduite en 48×48, la moyenne en
fabrique 21 et mouchette le contour (36 plateaux, 28 cases isolées) ; la médiane
en garde 2 (2 plateaux, aucune case isolée). Sur un champ lisse les deux
coïncident, donc rien n'est perdu.

**Ce qui a été mesuré et écarté : la profondeur par le flou.** L'idée est juste
— la profondeur de champ est un fait optique présent dans le fichier — mais la
netteté confond « loin » et « sans texture ». Trois régions à la même distance,
toutes parfaitement nettes, mesurent 16,63 (texture fine), 1,54 (dégradé) et
1,50 (aplat) : un aplat net mesure exactement comme un fond flou. Le détail et
les chiffres sont en § 6.10 du registre.

---

## Où tombent les marches du relief

Un relief ne se voit que par ses marches : une marche porte une ombre, le reste
est plat. `relief_edge_alignment` mesure ce qui compte — la part du contraste de
la photo que les marches exploitent, entre 0 et 1, **normalisée par leur
nombre** :

```
            rendement des marches 0.85 sur 1
```

Le découpage par défaut est celui d'**Otsu** (`--seuils otsu`), qui pose les
seuils dans les creux de l'histogramme, là où l'image se sépare en régions.
`--seuils uniform` tranche la plage de clarté en parts égales : les marches
tombent au milieu des dégradés, et un étage peut ne rien relever du tout tout en
coûtant ses plates. La commande le signale :

```
            ATTENTION : 3 etages demandes mais seules les hauteurs [0, 3] servent.
```

---

## Découper une grande œuvre

Une mosaïque de 96 tenons fait 77 cm de côté et près de neuf mille pièces. D'un
seul tenant, elle ne passe ni sur une table, ni dans un carton, ni entre deux
mains.

`--sections 48` (ou le menu de l'atelier) la découpe. Chaque section est un
**modèle complet** — son propre fond croisé, ses tuiles, sa notice PDF — donc
bâtissable et vérifiable seule ; une couche de plates posée **dessous** les
réunit, à cheval sur les joints.

```
  sections: 2 x 2 de 48 tenons, chacune un modele complet,
            196 plates de jonction par-dessous
```

Deux promesses, vérifiées par le noyau et par les tests :

1. **chaque section passe H1–H6 toute seule** ;
2. **l'assemblage entier, jonction comprise, passe H1–H6 aussi.**

Le surcoût est de quelques pour cent, et il baisse quand l'œuvre grandit —
c'est-à-dire précisément quand on en a besoin :

| Œuvre | Sections | D'un seul tenant | Découpée | Surcoût |
|---|---|---:|---:|---:|
| 32×32 | 2×2 de 16 | 984 | 1081 | +9,9 % |
| 48×48 | 2×2 de 24 | 2185 | 2341 | +7,1 % |
| 64×64 | 2×2 de 32 | 3831 | 4050 | +5,7 % |
| 96×96 | 2×2 de 48 | 8466 | 8843 | **+4,5 %** |

**Ce qui n'est pas promis : la rigidité.** H5 dit « d'un seul tenant », pas « ne
plie pas ». Une jonction par-dessous est une charnière : deux sections liées
ainsi tiennent ensemble et fléchissent. Le noyau ne sait pas mesurer cela — c'est
du ressort de BFK-002 — et je ne vais pas prétendre le contraire. Pour une œuvre
à accrocher, un cadre reste la bonne réponse.

C'est d'ailleurs la différence avec les sets LEGO Art officiels : leurs panneaux
16×16 ne se lient **pas** entre eux, c'est le cadre qui les tient. Le substrat
`panels` de `mosaic.build` reproduit cet arrangement, et le noyau le refuse —
454 violations de H5 sur une œuvre de 32 tenons. Il a raison : sans le cadre,
ça tombe en morceaux.

---

## Le cadre

**Toute œuvre est encadrée par défaut.** `--cadre 0` le retire, `--cadre-couleur`
le change (0 noir, 15 blanc, 70 brun rougeâtre, 71 gris clair, 72 gris foncé).

Le cadre est un mur de briques posé sur le substrat, **autour** de l'image et
jamais dessus : l'emprise grandit de deux tenons de chaque côté, l'image ne perd
rien. Sa hauteur est calculée pour qu'il **dépasse** la surface — une assise sans
relief, deux avec — parce qu'un cadre à fleur n'est pas un cadre, c'est une
bordure peinte. Ce qui fait lire un tableau, c'est l'ombre que son cadre porte
sur lui, et le modèle la porte réellement.

Deux appareils se croisent, et aucun n'est décoratif :

- **en plan**, les bandes horizontales courent sur toute la largeur une assise
  sur deux, les verticales l'autre — sinon les quatre angles seraient quatre
  joints traversants et le cadre s'ouvrirait aux coins ;
- **en élévation**, la découpe de chaque course part décalée d'une assise sur
  l'autre, pour que les joints ne se superposent pas.

Trois conséquences, toutes mesurées :

1. **Il ceinture les sections.** C'était la réserve honnête de la découpe : une
   jonction par-dessous est une charnière. Un cadre fermé sur les quatre côtés
   est une ceinture. Le noyau ne mesure toujours pas la raideur, mais
   l'arrangement est celui des sets officiels, et pour cette raison-là.
2. **Il rend constructibles des formats qui ne l'étaient pas.** Une bande d'un
   tenon de large est impossible sans cadre — son fond se scinde en dix-neuf
   morceaux et `build` refuse — et parfaitement valide avec.
3. Il coûte ses briques : 144 pièces pour une œuvre de 32 tenons, 208 pour une
   de 48. C'est le prix d'un tableau plutôt que d'un carrelage.

---

## La notice, comme une notice LEGO

La notice a longtemps eu une autre forme : une vue de l'œuvre entière, puis la
lecture de chaque ligne en clair — `2x4A^ · 1G^ · 2C^^`. C'était exact, compact,
et illisible. **Une notice LEGO ne demande jamais de décoder.** Elle montre les
pièces à sortir, puis montre où les poser.

Chaque étape porte donc, dans l'ordre du geste :

1. **l'encart** « À sortir pour cette étape » — la petite boîte grise de toute
   notice LEGO, qui dit exactement quoi prendre avant de commencer ;
2. **la bande en grand**, avec les joints réels entre pièces et **une lettre au
   centre de chaque pièce** — jamais de chaque tenon : imprimer quatre fois « A »
   sur une tuile 1×4 ferait compter quatre pièces là où on n'en prend qu'une ;
3. **le repérage** — l'œuvre entière en petit, la bande marquée.

**Deux à quatre étapes par page**, comme dans un fascicule LEGO : une seule
laissait les deux tiers de la feuille blancs. Sur les Tournesols en 32 tenons, la
notice est passée de 15 à 10 pages en devenant plus lisible.

Le fond et le relief ne se nomment plus pareil (« Fond — couche 2 sur 2 » contre
« Relief — étage 1 sur 2 »), et **le cadre a sa page à lui, en dernier** : rien
n'oblige physiquement à le poser après, mais une notice raconte un geste, et on
encadre un tableau une fois peint.

**Les pièces sont dessinées en perspective, avec leurs tenons** — dans l'encart
des étapes comme dans la liste de course, le même dessin pour n'avoir qu'un
langage à apprendre. Une pastille de couleur ne dit ni la forme ni la taille, et
devant un bac de vrac c'est la forme qu'on cherche.

Le dessin est une projection isométrique tracée par `render_piece`, à quatre fois
la taille finale puis réduite par `resample_box` — l'anticrénelage vient du
rééchantillonnage en lumière linéaire déjà écrit pour les photos, sans une ligne
de plus. Tout vient du catalogue : l'emprise, la hauteur du corps, et `has_studs`.
Une tuile n'a pas de tenons parce que le catalogue le dit, pas parce que son nom
commence par « Tile ». Les trois faces visibles reçoivent trois éclairements —
sans cet écart, un cube isométrique se lit comme un hexagone plat.

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
