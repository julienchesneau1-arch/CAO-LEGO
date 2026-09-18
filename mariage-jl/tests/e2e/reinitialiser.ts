import { Client } from "pg";
import { URL_E2E } from "./fixtures";

/**
 * Remet le foyer d'essai dans son état de départ. Les deux gabarits de
 * téléphone tournent l'un après l'autre sur la même base : sans cela, la
 * réponse enregistrée par l'iPhone changerait ce que voit l'Android.
 */
export async function reinitialiserFoyer(): Promise<void> {
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  try {
    await client.query("delete from public.health_allergies");
    await client.query("delete from public.rsvp_attendance");
    await client.query("delete from public.rsvp");
    await client.query("delete from public.household_links");
    await client.query("update public.guests set menu_choice = null, diet_flags = '{}'");
    await client.query("delete from public.tentatives");
  } finally {
    await client.end();
  }
}

/**
 * Remet les contenus éditables dans leur état d'amorçage : tout à
 * « [À COMPLÉTER] », aucun horaire, aucun hébergement. Les deux gabarits de
 * téléphone partagent la base : sans cela, le second verrait les textes
 * écrits par le premier.
 */
export async function reinitialiserContenus(): Promise<void> {
  const client = new Client({ connectionString: URL_E2E });
  await client.connect();
  try {
    await client.query(
      `update public.moments set starts_at = null, ends_at = null, place = null,
              ambience_fr = null, ambience_en = null, detail_fr = null, detail_en = null,
              shift_minutes = 0`,
    );
    await client.query(
      `update public.content_blocks
          set value = jsonb_build_object('texte', case locale when 'fr' then '[À COMPLÉTER]'
                                                              else '[TO BE COMPLETED]' end,
                                         'lien', null)`,
    );
    await client.query(
      `update public.faq set answer_fr = '[À COMPLÉTER]', answer_en = '[TO BE COMPLETED]',
              published = true`,
    );
    await client.query("delete from public.accommodations");
    await client.query("update public.parametres set date_limite_reponse = null where id = 1");
    await client.query("delete from public.audit_log");
  } finally {
    await client.end();
  }
}
