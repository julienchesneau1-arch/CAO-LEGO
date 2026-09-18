import { galerie } from "@/lib/medias";

/**
 * Liste des souvenirs du mur. Renvoie **seulement des identifiants** : le
 * mur n'a besoin de rien d'autre, et surtout pas de savoir quel foyer a
 * envoyé quoi. Les médias confiés aux seuls mariés n'y sont pas.
 */
export async function GET(): Promise<Response> {
  const medias = await galerie({ limite: 60 });
  return Response.json(
    { identifiants: medias.filter((media) => media.kind === "photo").map((media) => media.id) },
    { headers: { "cache-control": "no-store" } },
  );
}
