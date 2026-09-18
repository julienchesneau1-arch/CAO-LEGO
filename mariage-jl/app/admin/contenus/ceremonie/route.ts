import type { NextRequest } from "next/server";
import { exigerAdmin } from "@/lib/admin";
import { redirection } from "@/lib/http";
import { reglerCeremonieDebranchee } from "@/lib/regie";

/** Réglage de la cérémonie débranchée (brief §8.6) : décision des mariés. */
export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  await reglerCeremonieDebranchee(donnees.get("debranchee") === "1");
  return redirection("/admin/contenus?section=journee&etat=enregistre");
}
