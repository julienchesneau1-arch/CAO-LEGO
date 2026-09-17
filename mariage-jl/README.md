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
| V2 → V4 | voir `docs/PLAN.md` | pas commencées |

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
