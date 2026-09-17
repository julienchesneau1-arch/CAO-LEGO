# Base de données

Les migrations sont numérotées et s'appliquent **dans l'ordre**. Elles ne
contiennent aucune donnée inventée : les horaires, lieux et textes sont `NULL`
et s'éditent depuis l'espace admin.

| Fichier | Contenu |
|---|---|
| `migrations/20260917120000_schema.sql` | 24 tables, contraintes, index, amorçage des 5 moments et de la date du mariage |
| `migrations/20260917120100_rls.sql` | Refus par défaut sur toutes les tables, droits, 31 politiques, gardes de la régie |
| `migrations/20260917120200_retention.sql` | Purges de rétention (allergies, réponses, galerie, vœux, journaux, jetons) |
| `tests/00_compat_local.sql` | **Tests uniquement** : recrée ce que Supabase fournit déjà (rôles `anon`, `authenticated`, `service_role`, schéma `auth`). Jamais appliqué en production. |

## Appliquer sur le projet Supabase (quand il existera — question V0-06)

```bash
supabase link --project-ref <ref>
supabase db push          # applique migrations/ dans l'ordre
```

Puis, une seule fois, dans `Database → Cron` : planifier
`select jl.executer_purges()` chaque nuit. La migration le fait
automatiquement si l'extension `pg_cron` est déjà active.

## Vérifier les politiques en local, sans Docker

```bash
./scripts/pg-local.sh start
pnpm test tests/rls.test.ts
./scripts/pg-local.sh stop
```

Les tests créent une base jetable `jl_rls_test`, appliquent le shim puis les
migrations, et vérifient 26 comportements : refus par défaut, cloisonnement
régie / admin, allergies invisibles de la régie, vœux illisibles même de
l'admin, purges de rétention, aucun jeton stocké en clair.

## Ce que la base ne fait pas

- **Aucun invité ne détient de clé Supabase.** Les lectures des invités passent
  par le serveur Next.js, qui filtre par foyer. `anon` n'a aucun droit de table.
- **La régie ne voit aucune donnée personnelle** : ni foyers, ni invités, ni
  allergies. Deux déclencheurs l'empêchent de modifier autre chose que le
  décalage d'un moment et le statut d'un média.
- **La promesse n'est lisible par personne**, pas même par l'admin : aucune
  politique de lecture n'existe, et le contenu est chiffré par le navigateur.
