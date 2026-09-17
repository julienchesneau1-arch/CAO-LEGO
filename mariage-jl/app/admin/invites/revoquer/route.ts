import type { NextRequest } from "next/server";
import { z } from "zod";
import { exigerAdmin } from "@/lib/admin";
import { revoquerFoyer } from "@/lib/invites";
import { redirection } from "@/lib/http";

const Saisie = z.object({ foyer: z.string().uuid() });

/** Révocation d'un accès : le QR imprimé cesse d'ouvrir l'invitation. */
export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const saisie = Saisie.safeParse({ foyer: donnees.get("foyer") });
  if (!saisie.success) return redirection("/admin/invites?etat=erreur");

  await revoquerFoyer(saisie.data.foyer);
  return redirection("/admin/invites");
}
