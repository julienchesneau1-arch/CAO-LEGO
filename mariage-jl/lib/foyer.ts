import "server-only";
import { cookies, headers } from "next/headers";
import { COOKIE_FOYER, cleDebit, empreinte, lireSession } from "./acces";
import { une, requete } from "./db";
import { secretCookie } from "./env";
import { estPeriode, periodeEffective, type Periode } from "./periode";

export type Foyer = {
  readonly id: string;
  readonly label_public: string;
  readonly lang_default: string;
};

export type Parametres = {
  readonly date_mariage: Date;
  readonly date_limite_reponse: Date | null;
  readonly periode_forcee: Periode | null;
  readonly periode_forcee_jusqu_a: Date | null;
  /** Réglage des mariés : la cérémonie coupe-t-elle les envois ? (§8.6) */
  readonly ceremonie_debranchee: boolean;
};

/** Paramètres de la journée. La date du mariage est la seule valeur certaine. */
export async function parametres(): Promise<Parametres> {
  const ligne = await une<{
    date_mariage: Date;
    date_limite_reponse: Date | null;
    periode_forcee: string | null;
    periode_forcee_jusqu_a: Date | null;
    ceremonie_debranchee: boolean;
  }>(
    `select date_mariage, date_limite_reponse, periode_forcee, periode_forcee_jusqu_a,
            ceremonie_debranchee
       from public.parametres where id = 1`,
  );
  if (ligne === undefined) throw new Error("La table parametres est vide.");
  const forcee = ligne.periode_forcee ?? undefined;
  return {
    date_mariage: ligne.date_mariage,
    date_limite_reponse: ligne.date_limite_reponse,
    periode_forcee: estPeriode(forcee) ? forcee : null,
    periode_forcee_jusqu_a: ligne.periode_forcee_jusqu_a,
    ceremonie_debranchee: ligne.ceremonie_debranchee,
  };
}

export async function periodeCourante(maintenant = new Date()): Promise<Periode> {
  const p = await parametres();
  return periodeEffective(maintenant, p.date_mariage, {
    periode: p.periode_forcee,
    jusqua: p.periode_forcee_jusqu_a,
  });
}

/** Recherche par empreinte : le jeton en clair ne touche jamais la base. */
export async function foyerParJeton(jeton: string): Promise<Foyer | undefined> {
  return une<Foyer>(
    `select id, label_public, lang_default from public.households
      where token_sha256 = $1 and revoked_at is null`,
    [empreinte(jeton)],
  );
}

export async function foyerParCodeSecours(code: string): Promise<Foyer | undefined> {
  return une<Foyer>(
    `select id, label_public, lang_default from public.households
      where backup_code_sha256 = $1 and revoked_at is null`,
    [empreinte(code)],
  );
}

/**
 * Lien de partage du foyer (brief §6). Sert aussi de « un proche répond pour
 * moi » : un seul mécanisme, conformément aux arbitrages de la section 0 bis.
 * L'ouverture est comptée dans la même requête que la vérification.
 */
export async function foyerParLienPartage(jeton: string): Promise<Foyer | undefined> {
  return une<Foyer>(
    `with lien as (
       update public.household_links
          set opens = opens + 1
        where token_sha256 = $1
          and revoked_at is null
          and expires_at > now()
          and opens < max_opens
        returning household_id
     )
     select h.id, h.label_public, h.lang_default
       from public.households h join lien on lien.household_id = h.id
      where h.revoked_at is null`,
    [empreinte(jeton)],
  );
}

export async function marquerOuverture(foyerId: string): Promise<void> {
  await requete("select jl.marquer_ouverture($1)", [foyerId]);
}

export async function aRepondu(foyerId: string): Promise<boolean> {
  const ligne = await une<{ existe: boolean }>(
    "select true as existe from public.rsvp where household_id = $1",
    [foyerId],
  );
  return ligne !== undefined;
}

/** Foyer reconnu par le cookie signé, ou rien. Ne lève jamais. */
export async function foyerCourant(): Promise<Foyer | undefined> {
  const session = lireSession((await cookies()).get(COOKIE_FOYER)?.value, secretCookie());
  if (session === undefined) return undefined;
  try {
    return await une<Foyer>(
      `select id, label_public, lang_default from public.households
        where id = $1 and revoked_at is null`,
      [session.foyer],
    );
  } catch {
    return undefined;
  }
}

/**
 * Limitation de débit (brief §11). L'identifiant d'appelant est haché avant
 * d'atteindre la base : aucune adresse IP n'est conservée en clair.
 */
export async function tentativeAutorisee(
  prefixe: string,
  fenetre: string,
  maximum: number,
): Promise<boolean> {
  const entetes = await headers();
  const appelant =
    entetes.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    entetes.get("x-real-ip") ??
    "inconnu";
  const ligne = await une<{ autorise: boolean }>(
    "select jl.tentative_autorisee($1, $2::interval, $3) as autorise",
    [cleDebit(prefixe, appelant), fenetre, maximum],
  );
  return ligne?.autorise ?? false;
}
