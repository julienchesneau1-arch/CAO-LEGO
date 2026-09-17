import { NextResponse } from "next/server";
import { requete } from "@/lib/db";
import { env } from "@/lib/env";

export const dynamic = "force-dynamic";

/**
 * Sonde de disponibilité (brief §0 bis) : elle vérifie l'application ET la
 * base, puisque c'est la base qui porte toutes les données. La sonde externe
 * interroge cette route, ce qui garde aussi le projet Supabase actif.
 */
export async function GET(): Promise<NextResponse> {
  const debut = Date.now();
  let base: "ok" | "indisponible" = "indisponible";
  let detail: string | undefined;

  try {
    await requete("select 1");
    base = "ok";
  } catch (erreur) {
    detail = erreur instanceof Error ? erreur.message.slice(0, 120) : "erreur inconnue";
  }

  return NextResponse.json(
    {
      etat: base === "ok" ? "ok" : "degrade",
      base,
      ...(detail === undefined ? {} : { detail }),
      version: env().JL_VERSION,
      latence_ms: Date.now() - debut,
      horodatage: new Date().toISOString(),
    },
    { status: base === "ok" ? 200 : 503, headers: { "cache-control": "no-store" } },
  );
}
