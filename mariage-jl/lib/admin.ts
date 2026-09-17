import "server-only";
import { cookies } from "next/headers";
import { createHmac, timingSafeEqual } from "node:crypto";
import { empreinte, genererJeton } from "./acces";
import { requete, une } from "./db";
import { secretCookie } from "./env";

export const COOKIE_ADMIN = "jl_admin";
export const DUREE_SESSION_S = 60 * 60 * 8; // une soirée de travail
export const DUREE_LIEN_MIN = 30;

export type RoleAdmin = "admin" | "regie" | "tech";
export type SessionAdmin = { readonly email: string; readonly role: RoleAdmin; readonly exp: number };

/**
 * Accès administrateur (brief §6). Le lien magique est un jeton à usage
 * unique, vérifié en base ; la session est un cookie signé, limité dans le
 * temps. Tant que le prestataire e-mail n'est pas choisi (question V1-03),
 * le lien est remis de la main à la main par Julien.
 */
export async function creerLienMagique(email: string): Promise<string | undefined> {
  const connu = await une<{ email: string }>(
    "select email from public.admin_users where email = $1 and revoked_at is null",
    [email.trim().toLowerCase()],
  );
  if (connu === undefined) return undefined;

  const jeton = genererJeton();
  await requete(
    `insert into public.admin_magic_links (email, token_sha256, expires_at)
     values ($1, $2, now() + ($3 || ' minutes')::interval)`,
    [connu.email, empreinte(jeton), String(DUREE_LIEN_MIN)],
  );
  return jeton;
}

export async function consommerLienMagique(jeton: string): Promise<SessionAdmin | undefined> {
  const ligne = await une<{ email: string; role: RoleAdmin }>(
    "select email, role from jl.consommer_lien_admin($1)",
    [empreinte(jeton)],
  );
  if (ligne === undefined) return undefined;
  return {
    email: ligne.email,
    role: ligne.role,
    exp: Math.floor(Date.now() / 1000) + DUREE_SESSION_S,
  };
}

export function signerSessionAdmin(session: SessionAdmin): string {
  const charge = Buffer.from(JSON.stringify(session), "utf8").toString("base64url");
  return `${charge}.${createHmac("sha256", secretCookie()).update(charge).digest("base64url")}`;
}

function lireSessionAdmin(valeur: string | undefined): SessionAdmin | undefined {
  if (valeur === undefined) return undefined;
  const [charge, signature] = valeur.split(".");
  if (charge === undefined || signature === undefined) return undefined;

  const attendue = createHmac("sha256", secretCookie()).update(charge).digest();
  let fournie: Buffer;
  try {
    fournie = Buffer.from(signature, "base64url");
  } catch {
    return undefined;
  }
  if (attendue.length !== fournie.length || !timingSafeEqual(attendue, fournie)) return undefined;

  try {
    const brut: unknown = JSON.parse(Buffer.from(charge, "base64url").toString("utf8"));
    const session = brut as SessionAdmin;
    if (typeof session.email !== "string" || typeof session.exp !== "number") return undefined;
    if (session.exp * 1000 < Date.now()) return undefined;
    if (session.role !== "admin" && session.role !== "regie" && session.role !== "tech") {
      return undefined;
    }
    return session;
  } catch {
    return undefined;
  }
}

/**
 * Session administrateur de la requête. Le rôle est **revérifié en base** à
 * chaque appel : révoquer un accès dans l'admin le coupe immédiatement, sans
 * attendre l'expiration du cookie.
 */
export async function adminCourant(): Promise<SessionAdmin | undefined> {
  const session = lireSessionAdmin((await cookies()).get(COOKIE_ADMIN)?.value);
  if (session === undefined) return undefined;
  try {
    const ligne = await une<{ role: RoleAdmin }>(
      "select role from public.admin_users where email = $1 and revoked_at is null",
      [session.email],
    );
    if (ligne === undefined) return undefined;
    return { ...session, role: ligne.role };
  } catch {
    return undefined;
  }
}

export async function exigerAdmin(): Promise<SessionAdmin | undefined> {
  const session = await adminCourant();
  return session?.role === "admin" ? session : undefined;
}
