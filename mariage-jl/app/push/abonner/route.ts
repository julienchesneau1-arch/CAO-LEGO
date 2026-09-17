import type { NextRequest } from "next/server";
import { z } from "zod";
import { foyerCourant, tentativeAutorisee } from "@/lib/foyer";
import { enregistrerAbonnement, pushConfigure } from "@/lib/push";

/**
 * Abonnement aux notifications (brief §5). Réservé aux foyers reconnus : une
 * notification n'a de sens que pour un invité, et cela évite qu'un passant
 * remplisse la table.
 */
const Abonnement = z.object({
  endpoint: z.string().url().max(600),
  keys: z.object({ p256dh: z.string().min(16).max(200), auth: z.string().min(8).max(100) }),
});

export async function POST(requete: NextRequest): Promise<Response> {
  if (!pushConfigure()) return new Response("notifications non configurées", { status: 503 });

  const foyer = await foyerCourant();
  if (foyer === undefined) return new Response("foyer inconnu", { status: 403 });
  if (!(await tentativeAutorisee("push", "1 hour", 20))) {
    return new Response("trop de tentatives", { status: 429 });
  }

  let brut: unknown;
  try {
    brut = await requete.json();
  } catch {
    return new Response("abonnement illisible", { status: 400 });
  }

  const abonnement = Abonnement.safeParse(brut);
  if (!abonnement.success) return new Response("abonnement invalide", { status: 400 });

  await enregistrerAbonnement(foyer.id, abonnement.data);
  return new Response(null, { status: 204 });
}
