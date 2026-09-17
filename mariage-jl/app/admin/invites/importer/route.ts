import type { NextRequest } from "next/server";
import { headers } from "next/headers";
import { exigerAdmin } from "@/lib/admin";
import { lireCsvFoyers } from "@/lib/csv";
import { creerFoyers } from "@/lib/invites";
import { redirection } from "@/lib/http";
import { planchePdf } from "@/lib/planche-qr";

/**
 * Import CSV (brief §14). La réponse est **directement le PDF** de la
 * planche : les jetons et codes n'existent en clair qu'à cet instant, ils ne
 * sont jamais écrits en base (brief §11).
 */
export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const fichier = donnees.get("fichier");
  if (!(fichier instanceof File)) return redirection("/admin/invites?etat=fichier");

  const { foyers, erreurs } = lireCsvFoyers(await fichier.text());
  if (foyers.length === 0) {
    return redirection(`/admin/invites?etat=vide&lignes=${erreurs.length}`);
  }

  const impressions = await creerFoyers(foyers);
  const entetes = await headers();
  const domaine = entetes.get("x-forwarded-host") ?? entetes.get("host") ?? "mariage-jl";
  const pdf = await planchePdf(impressions, { domaine });

  return new Response(pdf as BodyInit, {
    headers: {
      "content-type": "application/pdf",
      "content-disposition": 'attachment; filename="planche-qr-mariage-jl.pdf"',
      "cache-control": "no-store",
    },
  });
}
