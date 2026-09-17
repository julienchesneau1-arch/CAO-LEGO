#!/usr/bin/env node
/**
 * Paire de clés de « La promesse » (brief §8.10).
 *
 *   node scripts/promesse-cles.mjs
 *
 * Affiche :
 * - la **clé publique**, à mettre dans JL_PROMESSE_CLE_PUBLIQUE. Elle n'a
 *   rien de secret : elle ne sert qu'à sceller.
 * - la **clé privée**, à imprimer en deux exemplaires et à confier à deux
 *   personnes différentes. Elle ne doit jamais être enregistrée sur le
 *   serveur, ni dans le dépôt, ni dans une messagerie : c'est la seule chose
 *   qui rend vraie la phrase « personne ne les lira, pas même eux ».
 *
 * Perdre la clé privée rend les vœux définitivement illisibles. C'est le prix
 * de la promesse, et c'est assumé (question V2-05).
 */
const paire = await crypto.subtle.generateKey(
  {
    name: "RSA-OAEP",
    modulusLength: 2048,
    publicExponent: new Uint8Array([1, 0, 1]),
    hash: "SHA-256",
  },
  true,
  ["encrypt", "decrypt"],
);

const base64 = (octets) => Buffer.from(octets).toString("base64");
const publique = base64(await crypto.subtle.exportKey("spki", paire.publicKey));
const privee = base64(await crypto.subtle.exportKey("pkcs8", paire.privateKey));

const enLignes = (valeur) => (valeur.match(/.{1,64}/g) ?? []).join("\n");

console.log(`
=== CLÉ PUBLIQUE — à copier dans .env.local (JL_PROMESSE_CLE_PUBLIQUE) ===

${publique}

=== CLÉ PRIVÉE — à imprimer, en deux exemplaires, puis à effacer d'ici ===

${enLignes(privee)}

Rappels :
  1. la clé privée ne va ni dans le dépôt, ni dans .env, ni dans un message ;
  2. deux exemplaires papier, deux personnes différentes ;
  3. sans elle, les vœux du 3 juin 2029 resteront fermés pour toujours ;
  4. pour les ouvrir le jour venu : pnpm promesse:ouvrir cle-privee.txt
`);
