# L'application du mariage de Julien & Lauriane

3 juin 2028 · Domaine de Roiffé · `03 · 06 · 2028`

Ce dépôt contient l'application que les invités ouvriront depuis le QR code du faire-part, et la page de secours qui la remplace en cas de panne.

**Ce document est écrit pour Julien.** Aucune connaissance de développement n'est nécessaire pour les commandes ci-dessous.

---

## Où en est-on

| Version | Contenu | État |
|---|---|---|
| **V0 — Fondations** | Jetons de la direction artistique, polices, monogramme vectorisé, signature, page `/design`, page de secours statique, squelette de traductions, **schéma de base + politiques RLS testées**, vérifications automatiques | **Livrée, validée le 17/09/2026** |
| **V1 — Le socle** | Accès par QR, code de secours, QR générique, partage de l'accès, premier lancement, accueil « Avant », navigation, Programme + `.ics`, Infos, FAQ, réponse complète, espace des mariés, planche QR PDF | **complet, en attente des contenus et des relectures** |
| **V2 — La préparation** | « Le texte », « La promesse », messages des absents, hébergements, fil d'annonces, Web Push, rappels e-mail en opt-in avec file d'envoi | **complète côté code** — reste le contenu des rappels et le choix du prestataire |
| **Contenus éditables** | `/admin/contenus` : horaires des moments, blocs d'Infos, réponses de la FAQ, hébergements, date limite — tout se remplit depuis le téléphone | **livré** — c'est ici que se remplissent les « [À COMPLÉTER] » |
| **V3 — Le jour J** | « Maintenant », cérémonie débranchée, checklist et météo de la semaine J, Aide avec boutons d'appel, régie (annonces, décalage, suspension, modération), photos et vidéos avec file d'envoi persistante, mur `/live`, plan de table, cartes de table et fiche régie PDF | **complète côté code** — reste les défis photo (bonus) |
| **V4 — Après** | « Merci », le regard du photographe, le livre d'or, le film, archives ZIP, « Mes données » avec les dates de suppression | **livrée** |

Ce qui n'est **pas** fait en V0, volontairement : aucun achat de domaine, aucune action sur le VPS, aucun projet Supabase. Ces trois points attendent tes réponses (`docs/QUESTIONS_BLOQUANTES.md`, section V0).

---

## À lire dans cet ordre

1. `docs/PLAN.md` — architecture, modèle de données, écrans, versions, risques, anomalies relevées.
2. `docs/QUESTIONS_BLOQUANTES.md` — ce que j'attends de toi, classé par version.
3. `docs/PROPOSITIONS.md` — trois micro-interactions et trois idées de confort, à accepter ou refuser.
4. `docs/INFRA.md` — squelette de l'audit du VPS, vide jusqu'à ce que j'aie les accès.
5. `docs/BRIEF_v6.md` — le brief d'origine, conservé comme source de vérité.

---

## Commandes

Prérequis : Node.js 22 et pnpm (`corepack enable` suffit).

```bash
pnpm install          # installe les dépendances
pnpm dev              # démarre l'app en local sur http://localhost:3000
pnpm verify           # traductions + TypeScript + tests + compilation
pnpm test:e2e         # parcours Playwright (iPhone et Android simulés)
pnpm captures          # captures d'écran mobile dans captures/
pnpm gen:secours      # recompose la page de secours (secours/index.html)
pnpm gen:monogram     # régénère le monogramme vectorisé depuis la police
pnpm db:local         # démarre un PostgreSQL jetable pour les tests de sécurité
pnpm db:seed          # base de développement + trois foyers d'essai (jetons affichés)
pnpm db:stop          # arrête PostgreSQL
```

`pnpm verify` exécute 50 tests. Les 26 tests de sécurité de la base ont besoin
d'un PostgreSQL : sans lui, ils sont ignorés en local (et refusés en
intégration continue, où une base est fournie). Voir `supabase/README.md`.

Les écrans existants :

- `/i/<jeton>` — ouverture d'une invitation depuis le QR du faire-part. L'appareil est reconnu ensuite, sans compte ni installation.
- `/` — accueil. Compte à rebours, fil des cinq étapes, une seule action à la fois, emplacement du film.
- `/retrouver` — « Retrouver mon invitation » avec le nom et le code à six caractères. Formulaire HTML simple, fonctionne sans JavaScript.
- `/partager` — partager l'accès au foyer : c'est aussi « un proche répond pour moi ».
- `/p/<jeton>` — le lien de partage, tel que le reçoit le proche.
- `/g` — QR générique des cartes de table : aucune donnée nominative.
- `/design` — **la page de validation de la direction artistique** : couleurs, neutres, typographie, monogramme, signature, mouvement, contrastes mesurés, réglages de confort de lecture.

- `/programme` et `/programme/<moment>` — les cinq moments, le déroulé, « Ajouter à mon agenda ».
- `/infos` — venir, dormir, tenue, enfants, accessibilité, rentrer en sécurité, covoiturage, liste de mariage.
- `/faq` — les dix-huit questions, avec recherche qui marche sans réseau.
- `/reponse` — un tap pour répondre, le reste facultatif et prérempli.
- `/admin` — ton espace : tableau de bord, invités, import CSV, planche QR.

Pour essayer en local : `pnpm db:local && pnpm db:seed` affiche trois liens d'ouverture et leurs codes de secours.

## Entrer dans ton espace

Le brief prévoit un lien magique par e-mail ; le prestataire n'est pas encore
choisi (question V1-03). Le mécanisme est déjà là, seule la livraison change :

```bash
pnpm admin:lien julien@exemple.fr --inviter        # première fois
pnpm admin:lien julien@exemple.fr                  # ensuite
```

La commande affiche un lien **valable 30 minutes et à usage unique**. Le jour
où le prestataire e-mail est choisi, c'est ce même lien qui partira par
courriel, sans rien changer d'autre.

## Imprimer la planche QR

1. Prépare un fichier CSV : `foyer;invites;langue`, les prénoms d'un même foyer
   séparés par une barre verticale (`Prénom A|Prénom B`).
2. Dans `/admin/invites`, importe-le : le PDF de la planche se télécharge
   immédiatement.
3. **Garde ce PDF.** Les QR codes et les codes de secours ne sont pas conservés
   en clair dans la base — c'est ce qui protège les invitations en cas de fuite.
   Une réimpression régénère les accès et invalide les planches déjà sorties.

---

## La page de secours

`secours/index.html` est une page unique, sans script, sans police distante, sans appel réseau : 7 ko. Elle est déployée sur **GitHub Pages**, donc en dehors du VPS — si le serveur tombe, elle reste debout.

À faire une seule fois dans GitHub : `Settings` → `Pages` → `Source : GitHub Actions`. Le dépôt la publiera à chaque modification. Le jour où le domaine est acheté, on décommente la ligne `CNAME` dans `.github/workflows/pages.yml`.

---

## La promesse — à faire une seule fois

```bash
pnpm promesse:cles
```

La commande affiche deux clés. La **publique** va dans `.env.local`
(`JL_PROMESSE_CLE_PUBLIQUE`) : elle ne sert qu'à sceller, elle n'a rien de
secret. La **privée** est à imprimer en deux exemplaires, confiés à deux
personnes différentes, puis à effacer de l'écran. Elle n'existe nulle part
ailleurs : c'est ce qui garantit que personne — vous compris — ne peut lire un
vœu avant le 3 juin 2029.

Ce jour-là : `pnpm promesse:ouvrir cle-privee.txt` écrit tous les vœux dans un
fichier. Avant cette date, la commande refuse.

**Perdre la clé privée rend les vœux définitivement illisibles.** C'est le prix
de la promesse.

## Écrire les contenus

Tout ce que l'application affiche « [À COMPLÉTER] » se remplit depuis
**`/admin/contenus`**, au téléphone, sans commande et sans SQL. Cinq familles :

| Onglet | Ce qui s'y écrit |
|---|---|
| La journée | la date limite de réponse |
| Les moments | horaires, lieu, ambiance et déroulé des cinq moments |
| Les infos | les neuf blocs de la page Infos, en français et en anglais |
| La FAQ | les réponses aux dix-huit questions, l'ordre, et ce qui est visible |
| Les hébergements | nom, distance, prix indicatif, navette, téléphone, lien |

Le compteur en haut de l'écran dit combien d'éléments restent à écrire, et
chaque liste indique l'état de ses éléments. Tu choisis d'abord dans la liste,
tu écris ensuite : un formulaire n'enregistre qu'un élément, donc une saisie
dans le train ne peut pas écraser ce que tu venais d'écrire ailleurs.

Trois choses que l'écran fait pour toi, et qu'il vaut mieux connaître :

- **Un champ vidé redevient une attente**, pas un blanc : l'invité lit
  « Horaire à confirmer » au lieu de voir un trou.
- **Une fin avant le début compte pour le lendemain** : La Nuit de 22:00 à
  03:00 est bien une nuit, pas une erreur.
- **Un lien doit commencer par `https://`.** Tout le reste est refusé, y
  compris si le navigateur l'avait laissé passer.

Les noms et les genres des cinq moments ne sont pas modifiables : ils viennent
de la direction artistique, pas d'un formulaire.

## Le jour J

Trois choses à savoir, et rien à faire :

- **L'application bascule toute seule.** À J-7 elle montre la checklist et la météo ; le 3 juin, l'accueil devient « Maintenant » : le moment en cours en grand, le suivant en dessous. Les horaires viennent de `/admin/contenus` — rien n'est codé en dur.
- **La cérémonie débranchée est active par défaut.** Pendant L'Horizon, l'écran invite à ranger son téléphone et suspend l'envoi de souvenirs ; la coupure se lève seule à la fin. Tu peux la désactiver dans `/admin/contenus`, onglet « La journée ».
- **La régie a son propre écran, `/regie`.** Donne le rôle `regie` à une ou deux personnes de confiance : elles pourront publier une annonce, décaler un moment (et tous les suivants), suspendre les envois — et rien d'autre. Elles ne voient ni les allergies ni les données des foyers.

Pour ouvrir un accès régie :

```bash
pnpm admin:lien              # affiche le lien à usage unique
```

Les numéros de l'écran Aide s'écrivent dans `/admin/contenus`, onglet « Les contacts ». Tant qu'un numéro est vide, aucun bouton d'appel n'apparaît.

## Les souvenirs des invités

Un invité donne son accord une fois, choisit ses photos, et c'est tout. Ce que
tu dois savoir :

- **Rien n'est stocké avec sa position.** Le téléphone ré-encode les images,
  et le serveur retire de nouveau toutes les métadonnées — EXIF des JPEG,
  blocs des PNG, atomes de position des vidéos d'iPhone. Un fichier que le
  serveur ne sait pas nettoyer est **refusé**, avec une explication à
  l'invité.
- **Aucune adresse publique.** Une photo passe par une route qui vérifie
  l'invitation. Un lien deviné ne donne rien.
- **Un invité peut confier ses photos aux mariés seulement** (utile pour les
  photos d'enfants). Elles n'apparaissent alors ni dans la galerie des
  autres, ni sur le mur projeté.
- **N'importe qui peut demander le retrait d'une photo où il apparaît, en un
  tap.** Elle est masquée tout de suite, avant même que vous la regardiez.
  Le fichier n'est pas supprimé : tu peux la rendre visible depuis `/regie`.
- **Rien n'est perdu sans réseau.** Les envois attendent dans le téléphone et
  repartent d'eux-mêmes. Sur iPhone, ils repartent à la réouverture de
  l'application — Safari ne permet pas mieux, et l'écran le dit.

Où vivent les fichiers : dans le dossier `JL_MEDIAS_DIR` (à sauvegarder). Le
jour où le projet Supabase existe, il y a **une trentaine de lignes** à écrire
dans `lib/stockage.ts`, et rien d'autre à toucher.

Le mur à projeter est à l'adresse **`/live`** : diaporama plein écran, aucun
nom, aucun compteur.

## Le plan de table

Dans `/admin/table` : tu crées les tables, puis tu poses chaque personne avec
un menu déroulant. L'invité voit sa table dans `/ma-table` et peut chercher
quelqu'un — « chloe » trouve « Chloé ». La recherche ne dit que le prénom et
la table.

Deux boutons sur le même écran produisent les imprimables du brief :

- **Les cartes de table** (une page A5 par table) : QR générique, les cinq
  moments, le Wi-Fi, un numéro. C'est le plan B si l'application ou le réseau
  tombe.
- **La fiche régie** (une page A4) : horaires, contacts, et ce qu'il faut
  faire si quelque chose casse.

Ce qui n'est pas encore écrit dans `/admin/contenus` n'est **pas imprimé** :
mieux vaut un blanc qu'un « [À COMPLÉTER] » sur une nappe.

## Après le mariage

L'application bascule une dernière fois toute seule. L'accueil devient
« Merci » : ton mot (à écrire dans `/admin/contenus`, onglet « Les infos »),
quelques photos, et les liens vers ce qui reste à voir.

- **Le regard du photographe** : dépose les photos dans
  `/admin/photographe`. Elles apparaissent dans `/photographe`, une section à
  part, visible seulement depuis une invitation — le QR générique ne l'ouvre
  pas. Elles ne se mélangent jamais aux photos des invités.
- **Le livre d'or** `/messages` : uniquement les mots dont l'auteur a choisi
  qu'ils soient visibles. Les messages privés restent privés.
- **Les archives** : chaque invité peut emporter « toutes les photos » ou
  « mes photos » en un fichier ZIP. L'archive est fabriquée à la demande :
  une photo retirée n'y est plus.
- **`/mes-donnees`** : ce que nous détenons pour ce foyer, et les dates de
  suppression automatique. Ces dates viennent des purges elles-mêmes — elles
  ne peuvent pas être fausses.

Les suppressions automatiques tournent chaque nuit sur Supabase. En attendant,
et pour nettoyer les fichiers du disque :

```bash
pnpm purger        # purge les lignes échues, puis les fichiers orphelins
```

## Annonces et notifications

Depuis `/admin/annonces`, tu publies une annonce en français et en anglais.
Elle apparaît aussitôt dans `/annonces` et sur l'accueil des invités. Une case
permet, si tu le veux, d'envoyer en plus une notification aux invités qui l'ont
demandée — ce n'est jamais automatique.

Pour activer les notifications, une seule fois :

```bash
pnpm push:cles        # affiche les trois lignes à coller dans .env.local
```

Aucun prestataire, aucun compte : ces clés authentifient notre serveur auprès
des navigateurs. Les changer déconnecte tous les abonnés.

## Rappels par e-mail

L'invité donne son adresse dans sa réponse, et peut s'arrêter en un tap.
Tant que le prestataire n'est pas choisi (question V1-03), les e-mails
s'accumulent dans une file sans partir :

```bash
pnpm emails:envoyer   # affiche ce qui partirait, sans rien envoyer
```

Quand tu auras choisi le prestataire, il y aura **une fonction à écrire** dans
`lib/email.ts`. Les écrans, l'opt-in et la désinscription ne changeront pas.

## Sans réseau

Le programme, les infos et la FAQ restent consultables une fois ouverts, la
recherche comprise. Une réponse donnée sans réseau est gardée dans le
téléphone et repart d'elle-même au retour du réseau.

Ce qui n'est **jamais** mis en cache : l'accueil, la réponse, le partage et ton
espace — ils portent le nom du foyer ou des données personnelles. Un téléphone
prêté ou perdu ne les révèle pas.

## Deux règles que le code applique tout seul

1. **Aucune information inventée.** Tout ce qui n'est pas connu s'affiche `[À COMPLÉTER]` et sera éditable depuis l'espace admin. Horaires, adresses, prix, noms, liens : rien n'est deviné.
2. **Les cinq couleurs ne portent jamais de texte.** Un test échoue si une couleur de moment est utilisée comme couleur de texte quelque part dans le code.
3. **La base refuse tout par défaut.** Un invité n'a aucune clé d'accès à la base ; la régie ne voit ni foyers, ni invités, ni allergies ; les vœux de « La promesse » ne sont lisibles par personne, pas même par vous. Vingt-six tests le vérifient à chaque envoi de code.

Les vérifications tournent aussi à chaque envoi de code (`.github/workflows/ci.yml`) : traductions complètes en français et en anglais, TypeScript strict, tests, compilation, page de secours à jour.

---

## Versions des outils, relevées le 17 septembre 2026

Next.js 16.3.5 · React 19.3.0 · Tailwind CSS 4.3.3 · TypeScript 5.9.3 · Vitest 5.0.1 · Playwright 1.63.0.

Source : registre npm. `nextjs.org` est inaccessible depuis l'environnement de développement (proxy de sortie) — les versions ont donc été vérifiées sur les métadonnées publiées des paquets, et non sur la documentation en ligne.
