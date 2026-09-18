import type { NextRequest } from "next/server";
import { z } from "zod";
import { exigerAdmin } from "@/lib/admin";
import { redirection } from "@/lib/http";
import { supprimerTable } from "@/lib/table";

/**
 * Supprimer une table libère les personnes qui y étaient assises : la
 * contrainte `on delete cascade` du schéma s'en charge, et l'écran affiche
 * alors les personnes redevenues sans table.
 */
export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const saisie = z.string().uuid().safeParse(donnees.get("table")?.toString());
  if (!saisie.success) return redirection("/admin/table?etat=erreur");

  await supprimerTable(saisie.data);
  return redirection("/admin/table?etat=supprime");
}
