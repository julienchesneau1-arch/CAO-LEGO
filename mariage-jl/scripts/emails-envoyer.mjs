#!/usr/bin/env node
/**
 * Vide la file des e-mails avec le transport configuré.
 *
 *   JL_DATABASE_URL=... node scripts/emails-envoyer.mjs
 *
 * Tant qu'aucun prestataire n'est choisi (question V1-03), le transport
 * « console » affiche les e-mails sans les envoyer : c'est la façon de relire
 * exactement ce qui partirait.
 *
 * Une fois le prestataire choisi, cette commande devient la tâche planifiée
 * côté Supabase et rien d'autre ne change.
 */
import { viderFile } from "../lib/email.ts";

if (process.env.JL_DATABASE_URL === undefined) {
  console.error("JL_DATABASE_URL est absent : voir .env.example.");
  process.exit(2);
}

const bilan = await viderFile();
console.log(`\n${bilan.envoyes} e-mail(s) traité(s), ${bilan.echecs} en échec.`);
process.exit(bilan.echecs > 0 ? 1 : 0);
