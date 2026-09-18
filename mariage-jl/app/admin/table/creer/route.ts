import type { NextRequest } from "next/server";
import { z } from "zod";
import { exigerAdmin } from "@/lib/admin";
import { redirection } from "@/lib/http";
import { creerTable } from "@/lib/table";

const Saisie = z.object({
  label: z.string().min(1).max(60),
  capacite: z.number().int().min(1).max(99).nullable(),
  ordre: z.number().int().min(0).max(999),
});

export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const capaciteBrute = donnees.get("capacite")?.toString().trim() ?? "";
  const saisie = Saisie.safeParse({
    label: donnees.get("label")?.toString().trim(),
    capacite: capaciteBrute === "" ? null : Number(capaciteBrute),
    ordre: Number(donnees.get("ordre") ?? 0),
  });
  if (!saisie.success) return redirection("/admin/table?etat=erreur");

  await creerTable(saisie.data.label, saisie.data.capacite, saisie.data.ordre);
  return redirection("/admin/table?etat=enregistre");
}
