import type { NextRequest } from "next/server";
import { adminCourant } from "@/lib/admin";
import { foyerCourant } from "@/lib/foyer";
import { octetsDuMedia } from "@/lib/medias";

/**
 * Sert un média (brief §8.7 et §11). Aucune URL publique : le fichier passe
 * par ici, et l'appelant doit être un foyer reconnu ou les mariés. Un lien
 * deviné ne donne rien, et un média masqué disparaît pour tout le monde.
 */
export async function GET(
  _requete: NextRequest,
  contexte: { readonly params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await contexte.params;
  const [foyer, admin] = await Promise.all([foyerCourant(), adminCourant()]);
  if (foyer === undefined && admin === undefined) {
    return new Response(null, { status: 404 });
  }

  const fichier = await octetsDuMedia(id, {
    foyer: foyer?.id,
    maries: admin?.role === "admin",
  });
  if (fichier === undefined) return new Response(null, { status: 404 });

  return new Response(new Uint8Array(fichier.octets), {
    headers: {
      "content-type": fichier.mime,
      // Privé et court : le média ne doit pas rester dans un cache partagé,
      // et un média masqué doit disparaître vite des téléphones.
      "cache-control": "private, max-age=300",
      "content-disposition": "inline",
      "x-content-type-options": "nosniff",
    },
  });
}
