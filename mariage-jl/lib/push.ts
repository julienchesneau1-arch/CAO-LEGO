import "server-only";
import webpush from "web-push";
import { requete } from "./db";
import { env } from "./env";

/**
 * Notifications Web Push (brief §5 et §7).
 *
 * Aucun prestataire n'est nécessaire : le serveur parle directement au
 * service de notification du navigateur, authentifié par une paire de clés
 * VAPID que l'on génère soi-même (`pnpm push:cles`).
 *
 * Deux règles du brief tenues ici :
 * - l'autorisation n'est **jamais** demandée au premier chargement (§17) :
 *   elle l'est au clic de l'invité, et nulle part ailleurs ;
 * - un abonnement périmé est supprimé plutôt que réessayé indéfiniment.
 */
export type Abonnement = {
  readonly endpoint: string;
  readonly keys: { readonly p256dh: string; readonly auth: string };
};

export function pushConfigure(): boolean {
  const { JL_VAPID_CLE_PUBLIQUE, JL_VAPID_CLE_PRIVEE, JL_VAPID_CONTACT } = env();
  return (
    JL_VAPID_CLE_PUBLIQUE !== undefined &&
    JL_VAPID_CLE_PUBLIQUE !== "" &&
    JL_VAPID_CLE_PRIVEE !== undefined &&
    JL_VAPID_CLE_PRIVEE !== "" &&
    JL_VAPID_CONTACT !== undefined &&
    JL_VAPID_CONTACT !== ""
  );
}

export function clePubliquePush(): string | null {
  const cle = env().JL_VAPID_CLE_PUBLIQUE;
  return cle === undefined || cle === "" ? null : cle;
}

function configurer(): void {
  const { JL_VAPID_CLE_PUBLIQUE, JL_VAPID_CLE_PRIVEE, JL_VAPID_CONTACT } = env();
  if (!pushConfigure()) throw new Error("Les clés VAPID sont absentes : voir pnpm push:cles.");
  webpush.setVapidDetails(
    JL_VAPID_CONTACT as string,
    JL_VAPID_CLE_PUBLIQUE as string,
    JL_VAPID_CLE_PRIVEE as string,
  );
}

export async function enregistrerAbonnement(
  foyerId: string,
  abonnement: Abonnement,
): Promise<void> {
  await requete(
    `insert into public.push_subscription (household_id, endpoint, p256dh, auth)
     values ($1, $2, $3, $4)
     on conflict (endpoint) do nothing`,
    [foyerId, abonnement.endpoint, abonnement.keys.p256dh, abonnement.keys.auth],
  );
}

export type Envoi = { readonly envoyes: number; readonly perimes: number };

/**
 * Envoie une notification à tous les abonnés. Les abonnements que le service
 * de notification déclare périmés (404, 410) sont supprimés : sans cela, la
 * liste ne ferait que grossir et chaque envoi ralentirait.
 */
export async function notifier(titre: string, corps: string, chemin = "/"): Promise<Envoi> {
  configurer();
  const abonnes = await requete<{ endpoint: string; p256dh: string; auth: string }>(
    "select endpoint, p256dh, auth from public.push_subscription",
  );

  const charge = JSON.stringify({ titre, corps, chemin });
  let envoyes = 0;
  const perimes: string[] = [];

  for (const abonne of abonnes) {
    try {
      await webpush.sendNotification(
        { endpoint: abonne.endpoint, keys: { p256dh: abonne.p256dh, auth: abonne.auth } },
        charge,
        { TTL: 60 * 60 * 12 },
      );
      envoyes += 1;
    } catch (erreur) {
      const statut = (erreur as { statusCode?: number }).statusCode;
      if (statut === 404 || statut === 410) perimes.push(abonne.endpoint);
    }
  }

  if (perimes.length > 0) {
    await requete("delete from public.push_subscription where endpoint = any($1)", [perimes]);
  }
  return { envoyes, perimes: perimes.length };
}
