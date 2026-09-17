import { headers } from "next/headers";
import { exigerAdmin } from "@/lib/admin";
import { regenererAcces } from "@/lib/invites";
import { redirection } from "@/lib/http";
import { planchePdf } from "@/lib/planche-qr";

/**
 * Réimpression : les accès sont régénérés, donc les planches déjà imprimées
 * cessent de fonctionner. C'est la conséquence de ne jamais conserver un
 * jeton en clair, et l'écran l'annonce avant le clic.
 */
export async function POST(): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const impressions = await regenererAcces();
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
