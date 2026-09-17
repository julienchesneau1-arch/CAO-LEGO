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
