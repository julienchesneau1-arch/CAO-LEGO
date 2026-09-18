import type { NextRequest } from "next/server";
import { z } from "zod";
import { exigerAdmin } from "@/lib/admin";
import { redirection } from "@/lib/http";
import { masquer } from "@/lib/medias";

/** Retirer une photo du photographe : elle est masquée, jamais effacée. */
export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const saisie = z.string().uuid().safeParse(donnees.get("media")?.toString());
  if (!saisie.success) return redirection("/admin/photographe");

  await masquer(saisie.data, true);
  return redirection("/admin/photographe");
}
