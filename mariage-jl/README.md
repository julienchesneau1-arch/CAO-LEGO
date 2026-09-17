# L'application du mariage de Julien & Lauriane

3 juin 2028 · Domaine de Roiffé · `03 · 06 · 2028`

Ce dépôt contient l'application que les invités ouvriront depuis le QR code du faire-part, et la page de secours qui la remplace en cas de panne.

**Ce document est écrit pour Julien.** Aucune connaissance de développement n'est nécessaire pour les commandes ci-dessous.

---

## Où en est-on

| Version | Contenu | État |
|---|---|---|
| **V0 — Fondations** | Jetons de la direction artistique, polices, monogramme vectorisé, signature, page `/design`, page de secours statique, squelette de traductions, vérifications automatiques | **Livrée, en attente de ta validation** |
| V1 — Le socle | Accès par QR, réponse, programme, infos, FAQ, admin invités, planche QR | pas commencée |
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
pnpm captures          # captures d'écran mobile dans captures/
pnpm gen:secours      # recompose la page de secours (secours/index.html)
pnpm gen:monogram     # régénère le monogramme vectorisé depuis la police
```

Deux pages existent aujourd'hui :

- `/` — page d'attente, uniquement des informations connues ;
- `/design` — **la page à valider** : les cinq couleurs, les neutres, la typographie, le monogramme, la signature, le mouvement, les contrastes mesurés, et les réglages de confort de lecture (trois tailles de texte, mode Papier, animations réduites, français/anglais).

---

## La page de secours

`secours/index.html` est une page unique, sans script, sans police distante, sans appel réseau : 7 ko. Elle est déployée sur **GitHub Pages**, donc en dehors du VPS — si le serveur tombe, elle reste debout.

À faire une seule fois dans GitHub : `Settings` → `Pages` → `Source : GitHub Actions`. Le dépôt la publiera à chaque modification. Le jour où le domaine est acheté, on décommente la ligne `CNAME` dans `.github/workflows/pages.yml`.

---

## Deux règles que le code applique tout seul

1. **Aucune information inventée.** Tout ce qui n'est pas connu s'affiche `[À COMPLÉTER]` et sera éditable depuis l'espace admin. Horaires, adresses, prix, noms, liens : rien n'est deviné.
2. **Les cinq couleurs ne portent jamais de texte.** Un test échoue si une couleur de moment est utilisée comme couleur de texte quelque part dans le code.

Les vérifications tournent aussi à chaque envoi de code (`.github/workflows/ci.yml`) : traductions complètes en français et en anglais, TypeScript strict, tests, compilation, page de secours à jour.

---

## Versions des outils, relevées le 17 septembre 2026

Next.js 16.3.5 · React 19.3.0 · Tailwind CSS 4.3.3 · TypeScript 5.9.3 · Vitest 5.0.1 · Playwright 1.63.0.

Source : registre npm. `nextjs.org` est inaccessible depuis l'environnement de développement (proxy de sortie) — les versions ont donc été vérifiées sur les métadonnées publiées des paquets, et non sur la documentation en ligne.
