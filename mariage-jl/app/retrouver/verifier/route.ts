import { type NextRequest } from "next/server";
import { z } from "zod";
import { COOKIE_FOYER, DUREE_COOKIE_S, signerSession } from "@/lib/acces";
import { requete } from "@/lib/db";
import { enProduction, secretCookie } from "@/lib/env";
import { redirection } from "@/lib/http";
import { foyerParCodeSecours, marquerOuverture, tentativeAutorisee } from "@/lib/foyer";
import { contientNom } from "@/lib/texte";

/**
 * « Retrouver mon invitation » (brief §6) : nom + code à six caractères.
 * Formulaire HTML classique, sans JavaScript : c'est le chemin de secours,
 * il doit marcher sur le téléphone le plus ancien et le réseau le plus faible.
 */
const Saisie = z.object({
  nom: z.string().min(2).max(120),
  code: z.string().min(6).max(8),
});

export async function POST(requeteHttp: NextRequest): Promise<Response> {
  const donnees = await requeteHttp.formData();
  const saisie = Saisie.safeParse({
    nom: donnees.get("nom"),
    code: donnees.get("code"),
  });

  const echec = (etat: string): Response => redirection(`/retrouver?etat=${etat}`);

  if (!saisie.success) return echec("inconnu");

  // Cinq essais par heure : un code de six caractères ne se devine pas ainsi.
  if (!(await tentativeAutorisee("retrouver", "1 hour", 5))) return echec("debit");

  const foyer = await foyerParCodeSecours(saisie.data.code);
  if (foyer === undefined) return echec("inconnu");

  // Le code est le secret ; le nom confirme, sans jamais dire lequel a échoué.
  const noms = await requete<{ nom: string }>(
    `select label_public as nom from public.households where id = $1
     union all
     select trim(coalesce(first_name,'') || ' ' || coalesce(last_name,'')) as nom
       from public.guests where household_id = $1`,
    [foyer.id],
  );
  if (!contientNom(noms.map((l) => l.nom), saisie.data.nom)) return echec("inconnu");

  await marquerOuverture(foyer.id);

  const reponse = redirection("/");
  reponse.cookies.set({
    name: COOKIE_FOYER,
    value: signerSession({ foyer: foyer.id, emis: Math.floor(Date.now() / 1000) }, secretCookie()),
    httpOnly: true,
    sameSite: "lax",
    secure: enProduction(),
    path: "/",
    maxAge: DUREE_COOKIE_S,
  });
  return reponse;
}
