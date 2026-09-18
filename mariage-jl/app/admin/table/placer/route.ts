import type { NextRequest } from "next/server";
import { z } from "zod";
import { exigerAdmin } from "@/lib/admin";
import { redirection } from "@/lib/http";
import { affecter } from "@/lib/table";

const Saisie = z.object({
  invite: z.string().uuid(),
  table: z.string().uuid().nullable(),
});

export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const brute = donnees.get("table")?.toString() ?? "";
  const saisie = Saisie.safeParse({
    invite: donnees.get("invite")?.toString(),
    table: brute === "" ? null : brute,
  });
  if (!saisie.success) return redirection("/admin/table?etat=erreur");

  await affecter(saisie.data.invite, saisie.data.table);
  return redirection("/admin/table?etat=enregistre");
}
