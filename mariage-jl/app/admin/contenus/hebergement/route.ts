import type { NextRequest } from "next/server";
import { z } from "zod";
import { exigerAdmin } from "@/lib/admin";
import {
  ajouterHebergement,
  enregistrerHebergement,
  lienAcceptable,
  supprimerHebergement,
  texteOuNull,
} from "@/lib/contenus-admin";
import { redirection } from "@/lib/http";

const RETOUR = "/admin/contenus?section=hebergements";

const Saisie = z.object({
  name: z.string().min(1).max(200),
  distance_km: z
    .string()
    .regex(/^\d{1,3}([.,]\d)?$/)
    .nullable(),
  price_hint: z.string().max(100).nullable(),
  url: z.string().max(500).nullable(),
  phone: z.string().max(40).nullable(),
  shuttle: z.boolean().nullable(),
  sort_order: z.number().int().min(0).max(999),
});

export async function POST(requete: NextRequest): Promise<Response> {
  if ((await exigerAdmin()) === undefined) return redirection("/admin");

  const donnees = await requete.formData();
  const id = donnees.get("id")?.toString() ?? "";

  if (donnees.get("supprimer") === "1") {
    if (id === "") return redirection(`${RETOUR}&etat=erreur`);
    await supprimerHebergement(id);
    return redirection(`${RETOUR}&etat=supprime`);
  }

  const champ = (nom: string): string | null => texteOuNull(donnees.get(nom)?.toString());
  const distance = champ("distance_km");
  const saisie = Saisie.safeParse({
    name: donnees.get("name"),
    // Une distance se saisit avec une virgule en français : on la normalise.
    distance_km: distance === null ? null : distance.replace(",", "."),
    price_hint: champ("price_hint"),
    url: champ("url"),
    phone: champ("phone"),
    shuttle: donnees.get("shuttle") === "1",
    sort_order: Number(donnees.get("sort_order") ?? 0),
  });
  if (!saisie.success) return redirection(`${RETOUR}&etat=erreur`);

  if (saisie.data.url !== null && !lienAcceptable(saisie.data.url)) {
    return redirection(`${RETOUR}&etat=lien`);
  }

  if (donnees.get("action") === "ajout") await ajouterHebergement(saisie.data);
  else if (id !== "") await enregistrerHebergement(id, saisie.data);
  else return redirection(`${RETOUR}&etat=erreur`);

  return redirection(`${RETOUR}&etat=enregistre`);
}
