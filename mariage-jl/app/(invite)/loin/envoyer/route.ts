import type { NextRequest } from "next/server";
import { z } from "zod";
import { requete } from "@/lib/db";
import { foyerCourant, tentativeAutorisee } from "@/lib/foyer";
import { redirection } from "@/lib/http";

/**
 * Message des absents (brief §8.9, simplifié par la section 0 bis : écrit
 * uniquement). L'invité choisit qui peut le lire ; par défaut, les mariés
 * seuls.
 */
const Saisie = z.object({
  message: z.string().min(2).max(2000),
  visibilite: z.enum(["private", "guestbook"]),
});

export async function POST(requeteHttp: NextRequest): Promise<Response> {
  const foyer = await foyerCourant();
  if (!(await tentativeAutorisee("loin", "1 hour", 20))) {
    return redirection("/loin?etat=erreur");
  }

  const donnees = await requeteHttp.formData();
  const saisie = Saisie.safeParse({
    message: donnees.get("message"),
    visibilite: donnees.get("visibilite") ?? "private",
  });
  if (!saisie.success) return redirection("/loin?etat=erreur");

  await requete(
    `insert into public.absent_messages (household_id, body, visibility)
     values ($1, $2, $3)`,
    [foyer?.id ?? null, saisie.data.message, saisie.data.visibilite],
  );
  return redirection("/loin?etat=envoye");
}
