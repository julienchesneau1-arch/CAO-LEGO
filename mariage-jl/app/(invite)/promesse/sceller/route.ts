import type { NextRequest } from "next/server";
import { z } from "zod";
import { requete } from "@/lib/db";
import { tentativeAutorisee } from "@/lib/foyer";

/**
 * Dépôt d'un vœu scellé (brief §8.10). Le serveur n'accepte qu'une enveloppe
 * déjà chiffrée : il ne voit jamais le texte, et il n'a aucun moyen de
 * l'ouvrir. Le foyer n'est volontairement **pas** enregistré — un vœu est
 * anonyme, sans quoi les mariés pourraient deviner qui a écrit quoi.
 */
const Enveloppe = z.object({
  v: z.literal(1),
  cle: z.string().min(32).max(1000),
  iv: z.string().min(8).max(64),
  texte: z.string().min(8).max(8000),
});

export async function POST(requeteHttp: NextRequest): Promise<Response> {
  if (!(await tentativeAutorisee("promesse", "1 hour", 10))) {
    return new Response("trop de tentatives", { status: 429 });
  }

  let brut: unknown;
  try {
    brut = await requeteHttp.json();
  } catch {
    return new Response("enveloppe illisible", { status: 400 });
  }

  const enveloppe = Enveloppe.safeParse(brut);
  if (!enveloppe.success) return new Response("enveloppe invalide", { status: 400 });

  await requete("insert into public.promises (ciphertext) values ($1)", [
    JSON.stringify(enveloppe.data),
  ]);
  return new Response(null, { status: 204 });
}
