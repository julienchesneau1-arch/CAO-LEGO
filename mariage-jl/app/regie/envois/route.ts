import type { NextRequest } from "next/server";
import { redirection } from "@/lib/http";
import { couperEnvois, exigerRegie } from "@/lib/regie";

/** Suspendre ou rouvrir l'envoi de souvenirs (brief §9), en un tap. */
export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerRegie()) === undefined) return redirection("/regie");

  const donnees = await requete.formData();
  const couper = donnees.get("couper") === "1";
  await couperEnvois(couper);
  return redirection(`/regie?etat=${couper ? "coupes" : "rouverts"}`);
}
