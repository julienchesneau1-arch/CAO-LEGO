#!/usr/bin/env node
/**
 * Paire de clés VAPID pour les notifications (brief §5).
 *
 *   node scripts/push-cles.mjs
 *
 * Aucun prestataire n'est nécessaire : ces clés authentifient notre serveur
 * auprès des services de notification des navigateurs. La clé privée est un
 * secret d'environnement comme un autre — elle ne va pas dans le dépôt.
 */
import webpush from "web-push";

const { publicKey, privateKey } = webpush.generateVAPIDKeys();

console.log(`
À copier dans .env.local :

JL_VAPID_CLE_PUBLIQUE=${publicKey}
JL_VAPID_CLE_PRIVEE=${privateKey}
JL_VAPID_CONTACT=mailto:[ADRESSE À COMPLÉTER]

La clé publique est partagée avec le navigateur de l'invité ; la privée reste
sur le serveur. Les changer invalide tous les abonnements existants.
`);
