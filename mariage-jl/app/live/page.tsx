import { MurEnDirect } from "@/components/MurEnDirect";
import { galerie } from "@/lib/medias";
import { headers } from "next/headers";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";
export const metadata = { title: "Le mur — J & L", robots: { index: false } };

/**
 * Mur en direct pour projection (brief §8.7). Aucun accès de foyer n'est
 * demandé : l'écran est projeté dans la salle, il n'y a personne à
 * reconnaître. En revanche il ne montre **que** les souvenirs confiés aux
 * invités — jamais ceux réservés aux mariés.
 */
export default async function PageLive() {
  const { t } = await langueEtTextes();
  // Même règle que la planche QR : le domaine vient de la requête, il n'est
  // pas inventé tant que la question V0-02 est ouverte.
  const entetes = await headers();
  const domaine = entetes.get("x-forwarded-host") ?? entetes.get("host") ?? "";
  // `pourLesMaries` reste faux et aucun foyer n'est passé : seuls les
  // médias de visibilité « invites » remontent.
  const medias = await galerie({ limite: 60 });

  return (
    <MurEnDirect
      identifiants={medias.filter((media) => media.kind === "photo").map((media) => media.id)}
      qr={domaine === "" ? "" : `https://${domaine}/g`}
      libelles={{ titre: t.live.titre, attente: t.live.attente, signature: t.accueil.signature }}
    />
  );
}
