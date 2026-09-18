import "server-only";
import { adminCourant, type SessionAdmin } from "./admin";
import { requete } from "./db";

/**
 * Régie du jour J (brief §9). Trois gestes, pas un de plus : publier une
 * annonce, décaler un moment, couper les envois de photos. La régie ne voit
 * ni les allergies ni les données personnelles — c'est la RLS qui le garantit
 * côté base, et ce module qui ne lui offre rien d'autre côté serveur.
 */
export async function exigerRegie(): Promise<SessionAdmin | undefined> {
  const session = await adminCourant();
  if (session === undefined) return undefined;
  return session.role === "admin" || session.role === "regie" ? session : undefined;
}

/**
 * Décale un moment **et tous ceux qui le suivent** (brief §9). Retarder le
 * dîner de vingt minutes retarde la fête d'autant : c'est le comportement
 * attendu d'une journée qui glisse, et l'inverse — décaler un seul moment —
 * produirait des horaires qui se chevauchent.
 */
export async function decalerDepuis(momentId: string, minutes: number): Promise<number> {
  const lignes = await requete<{ id: string }>(
    `update public.moments set shift_minutes = shift_minutes + $2
      where id >= $1 returning id`,
    [momentId, minutes],
  );
  await journaliser("regie.decalage", `${momentId}:${minutes >= 0 ? "+" : ""}${minutes}`);
  return lignes.length;
}

/** Remet tous les horaires à ce qui était prévu. */
export async function annulerDecalages(): Promise<void> {
  await requete("update public.moments set shift_minutes = 0 where shift_minutes <> 0");
  await journaliser("regie.decalage", "remise a zero");
}

export async function couperEnvois(couper: boolean): Promise<void> {
  await requete("update public.parametres set photos_en_pause = $1, maj_le = now() where id = 1", [
    couper,
  ]);
  await journaliser("regie.envois", couper ? "coupes" : "rouverts");
}

/** Réglage de la cérémonie débranchée : décision des mariés, pas de la régie. */
export async function reglerCeremonieDebranchee(active: boolean): Promise<void> {
  await requete(
    "update public.parametres set ceremonie_debranchee = $1, maj_le = now() where id = 1",
    [active],
  );
  await journaliser("ceremonie.debranchee", active ? "active" : "desactivee");
}

async function journaliser(action: string, cible: string): Promise<void> {
  await requete("insert into public.audit_log (role, action, target) values ('regie', $1, $2)", [
    action,
    cible,
  ]);
}
