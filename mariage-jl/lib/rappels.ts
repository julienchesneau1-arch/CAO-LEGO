import "server-only";
import { empreinte, genererJeton } from "./acces";
import { requete, une } from "./db";
import { mettreEnFile } from "./email";

/**
 * Rappels par e-mail (brief V2). L'opt-in est **explicite** : rien n'est
 * envoyé sans que l'invité l'ait demandé, et chaque e-mail portera un lien de
 * désinscription qui fonctionne en un tap, sans rien demander d'autre.
 */
export type Optin = { readonly email: string; readonly consent_at: Date };

export async function optinDuFoyer(foyerId: string): Promise<Optin | undefined> {
  return une<Optin>(
    `select email, consent_at from public.reminder_optin
      where household_id = $1 and revoked_at is null`,
    [foyerId],
  );
}

/**
 * Enregistre le consentement et renvoie le lien de désinscription à mettre
 * dans les e-mails. Le jeton n'est stocké que haché : un accès à la base ne
 * permet pas de désinscrire quelqu'un à sa place.
 */
export async function activerRappels(
  foyerId: string,
  email: string,
): Promise<{ readonly jetonDesinscription: string }> {
  const jeton = genererJeton();
  await requete(
    `insert into public.reminder_optin
       (household_id, email, consent_at, unsubscribe_token_sha256)
     values ($1, $2, now(), $3)
     on conflict (household_id) do update
        set email = excluded.email,
            consent_at = now(),
            unsubscribe_token_sha256 = excluded.unsubscribe_token_sha256,
            revoked_at = null`,
    [foyerId, email.trim().toLowerCase(), empreinte(jeton)],
  );
  return { jetonDesinscription: jeton };
}

export async function desactiverRappels(foyerId: string): Promise<void> {
  await requete(
    "update public.reminder_optin set revoked_at = now() where household_id = $1",
    [foyerId],
  );
}

/** Désinscription par le lien d'un e-mail, sans connexion ni question. */
export async function desinscrireParJeton(jeton: string): Promise<boolean> {
  const ligne = await une<{ household_id: string }>(
    `update public.reminder_optin set revoked_at = now()
      where unsubscribe_token_sha256 = $1 and revoked_at is null
      returning household_id`,
    [empreinte(jeton)],
  );
  return ligne !== undefined;
}

/**
 * Confirmation d'inscription. Le contenu des rappels eux-mêmes reste à écrire
 * (question V2-01) : on ne promet donc ni nombre, ni calendrier.
 */
export async function envoyerConfirmation(
  email: string,
  lienDesinscription: string,
): Promise<void> {
  await mettreEnFile(
    email,
    "Julien & Lauriane — vos rappels sont activés",
    [
      "Vous recevrez nos rappels à cette adresse.",
      "",
      "Nous n'enverrons que l'essentiel, et rien d'autre.",
      "",
      `Pour ne plus rien recevoir, un seul lien : ${lienDesinscription}`,
      "",
      "Julien & Lauriane",
    ].join("\n"),
  );
}
