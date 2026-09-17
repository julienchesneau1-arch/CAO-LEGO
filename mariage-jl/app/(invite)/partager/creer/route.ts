import { empreinte, genererJeton } from "@/lib/acces";
import { une } from "@/lib/db";
import { foyerCourant, tentativeAutorisee } from "@/lib/foyer";
import { redirection } from "@/lib/http";
import { JOURS_VALIDITE, OUVERTURES_MAX } from "@/lib/partage";

/**
 * Crée un lien de partage du foyer (brief §6). Le jeton n'est stocké que
 * haché : il n'est affiché qu'une fois, à celui qui vient de le créer.
 */
export async function POST(): Promise<Response> {
  const foyer = await foyerCourant();
  if (foyer === undefined) {
    return redirection("/retrouver?etat=inconnu");
  }
  if (!(await tentativeAutorisee("partage-creation", "1 hour", 10))) {
    return redirection("/partager?etat=debit");
  }

  const jeton = genererJeton();
  await une(
    `insert into public.household_links
       (household_id, token_sha256, max_opens, expires_at)
     values ($1, $2, $3, now() + ($4 || ' days')::interval)`,
    [foyer.id, empreinte(jeton), OUVERTURES_MAX, String(JOURS_VALIDITE)],
  );

  return redirection(`/partager?jeton=${jeton}`);
}
