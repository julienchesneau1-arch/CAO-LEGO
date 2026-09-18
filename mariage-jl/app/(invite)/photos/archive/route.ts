import type { NextRequest } from "next/server";
import { archiveDesSouvenirs } from "@/lib/apres";
import { foyerCourant } from "@/lib/foyer";
import { redirection } from "@/lib/http";

/**
 * Archive ZIP personnelle (brief §8.11). Elle se fabrique à la demande et
 * n'est jamais mise en cache : une photo retirée entre-temps n'y est donc
 * plus, ce qui est le seul comportement acceptable après une demande de
 * retrait.
 */
export async function GET(requete: NextRequest): Promise<Response> {
  const foyer = await foyerCourant();
  if (foyer === undefined) return redirection("/photos?etat=sans_foyer");

  const mesSouvenirs = requete.nextUrl.searchParams.get("mes") === "1";
  const { octets } = await archiveDesSouvenirs({
    foyer: foyer.id,
    mesSouvenirs,
    prefixe: mesSouvenirs ? "mes-souvenirs" : "souvenirs-du-mariage",
  });

  return new Response(new Uint8Array(octets), {
    headers: {
      "content-type": "application/zip",
      "content-disposition": `attachment; filename="${
        mesSouvenirs ? "mes-photos-jl.zip" : "photos-du-mariage-jl.zip"
      }"`,
      // Privé et jamais conservé : l'archive reflète l'instant où elle est
      // demandée, pas un état plus ancien.
      "cache-control": "no-store, private",
    },
  });
}
