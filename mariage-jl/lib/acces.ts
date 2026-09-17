import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto";

/**
 * Accès des invités (brief §6). Trois règles tenues par ce fichier :
 * 1. un jeton n'est jamais stocké : seule son empreinte SHA-256 va en base ;
 * 2. toute comparaison de secret est à temps constant ;
 * 3. le cookie de foyer est signé, donc infalsifiable sans le secret serveur.
 */

/** 160 bits de hasard, écrits en base32 sans caractère ambigu. */
const ALPHABET_JETON = "abcdefghijkmnopqrstuvwxyz23456789"; // sans l, 0, 1
const ALPHABET_CODE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; // sans I, O, 0, 1

function tirer(alphabet: string, longueur: number): string {
  const octets = randomBytes(longueur * 2);
  let sortie = "";
  for (let i = 0; sortie.length < longueur; i += 1) {
    const octet = octets[i % octets.length] ?? 0;
    // Rejet du reste pour garder une distribution uniforme.
    if (octet < 256 - (256 % alphabet.length)) {
      sortie += alphabet[octet % alphabet.length];
    }
  }
  return sortie;
}

/** Jeton d'invitation : 32 caractères, soit ≈ 160 bits. */
export function genererJeton(): string {
  return tirer(ALPHABET_JETON, 32);
}

/** Code de secours imprimé sous le QR : 6 caractères lisibles à l'œil. */
export function genererCodeSecours(): string {
  return tirer(ALPHABET_CODE, 6);
}

export function empreinte(secret: string): Buffer {
  return createHash("sha256").update(secret.trim().toLowerCase(), "utf8").digest();
}

export function memeSecret(a: Buffer, b: Buffer): boolean {
  return a.length === b.length && timingSafeEqual(a, b);
}

export type SessionFoyer = {
  readonly foyer: string;
  readonly emis: number;
};

const SEPARATEUR = ".";

export function signerSession(session: SessionFoyer, secret: string): string {
  const charge = Buffer.from(JSON.stringify(session), "utf8").toString("base64url");
  const signature = createHmac("sha256", secret).update(charge).digest("base64url");
  return `${charge}${SEPARATEUR}${signature}`;
}

export function lireSession(valeur: string | undefined, secret: string): SessionFoyer | undefined {
  if (valeur === undefined) return undefined;
  const [charge, signature] = valeur.split(SEPARATEUR);
  if (charge === undefined || signature === undefined) return undefined;

  const attendue = createHmac("sha256", secret).update(charge).digest();
  let fournie: Buffer;
  try {
    fournie = Buffer.from(signature, "base64url");
  } catch {
    return undefined;
  }
  if (!memeSecret(attendue, fournie)) return undefined;

  try {
    const brut: unknown = JSON.parse(Buffer.from(charge, "base64url").toString("utf8"));
    if (
      typeof brut === "object" &&
      brut !== null &&
      typeof (brut as SessionFoyer).foyer === "string" &&
      typeof (brut as SessionFoyer).emis === "number"
    ) {
      return brut as SessionFoyer;
    }
  } catch {
    return undefined;
  }
  return undefined;
}

export const COOKIE_FOYER = "jl_foyer";
export const COOKIE_GENERIQUE = "jl_generique";
export const DUREE_COOKIE_S = 60 * 60 * 24 * 550; // ≈ 18 mois

/** Clé de limitation de débit : jamais l'adresse IP en clair (brief §11). */
export function cleDebit(prefixe: string, identifiant: string): string {
  return `${prefixe}:${createHash("sha256").update(identifiant, "utf8").digest("base64url").slice(0, 22)}`;
}
