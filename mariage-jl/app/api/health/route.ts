import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Sonde de disponibilité (brief §0 bis). En V0 elle ne vérifie que
 * l'application : le contrôle de Supabase sera ajouté avec la base, en V1.
 */
export function GET() {
  return NextResponse.json(
    {
      etat: "ok",
      version: process.env["JL_VERSION"] ?? "v0-dev",
      supabase: "non branché en V0",
      horodatage: new Date().toISOString(),
    },
    { headers: { "cache-control": "no-store" } },
  );
}
