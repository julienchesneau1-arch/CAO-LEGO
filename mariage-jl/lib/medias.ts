import "server-only";
import { randomUUID } from "node:crypto";
import { requete, une } from "./db";
import { env } from "./env";
import { nettoyer } from "./metadonnees";
import { stockage } from "./stockage";

/**
 * Photos et vidéos des invités (brief §8.7). Trois règles tiennent tout :
 *
 * 1. **Rien n'est stocké sans avoir été nettoyé.** Un format que le serveur
 *    ne sait pas nettoyer est refusé : mieux vaut un envoi qui échoue avec
 *    une explication qu'une photo géolocalisée sur nos disques (§11).
 * 2. **Aucune URL publique.** Le fichier est servi par une route qui vérifie
 *    le foyer : un lien deviné ne donne rien.
 * 3. **Aucun compteur affiché** (§17). Le « j'aime » existe pour trier, il
 *    ne s'affiche jamais en nombre.
 */
export const MIMES_PHOTO = ["image/jpeg", "image/png"] as const;
export const MIMES_VIDEO = ["video/mp4", "video/quicktime"] as const;

export type RefusEnvoi =
  | "trop_gros"
  | "type_refuse"
  | "metadonnees"
  | "envois_suspendus"
  | "sans_consentement"
  | "sans_foyer";

/**
 * Version du texte de consentement au partage (brief §8.7). Comme pour les
 * allergies, elle est enregistrée avec le consentement : si le texte change,
 * on sait ce que le foyer a réellement accepté.
 */
export const VERSION_CONSENTEMENT_MEDIAS = "medias-2026-09-18";

export type Visibilite = "invites" | "maries";

export type ConsentementMedias = {
  readonly visibilite: Visibilite;
  readonly consent_at: Date;
};

export async function consentementMedias(
  foyer: string,
): Promise<ConsentementMedias | undefined> {
  return une<ConsentementMedias>(
    `select visibilite, consent_at from public.media_consent
      where household_id = $1 and revoked_at is null`,
    [foyer],
  );
}

/**
 * Consentement au premier envoi. La visibilité « maries » est là pour la
 * prudence que le brief demande sur les photos d'enfants : le foyer partage,
 * mais seulement avec Julien et Lauriane.
 */
export async function accorderConsentementMedias(
  foyer: string,
  visibilite: Visibilite,
): Promise<void> {
  await requete(
    `insert into public.media_consent (household_id, consent_text_version, visibilite)
     values ($1, $2, $3)
     on conflict (household_id) do update
        set consent_at = now(), consent_text_version = excluded.consent_text_version,
            visibilite = excluded.visibilite, revoked_at = null`,
    [foyer, VERSION_CONSENTEMENT_MEDIAS, visibilite],
  );
}

/**
 * Retirer son consentement arrête les **envois suivants**. Il ne réécrit pas
 * le passé : pour retirer une photo déjà envoyée, c'est « Demander le
 * retrait », qui la masque immédiatement.
 */
export async function retirerConsentementMedias(foyer: string): Promise<void> {
  await requete(
    "update public.media_consent set revoked_at = now() where household_id = $1",
    [foyer],
  );
}

export type Media = {
  readonly id: string;
  readonly moment_id: string | null;
  readonly kind: "photo" | "video";
  readonly mime: string;
  readonly status: "pending" | "published" | "hidden";
  readonly created_at: Date;
  readonly household_id: string | null;
  readonly visibilite: Visibilite;
  /** `photographe` pour la section distincte du brief §8.11. */
  readonly source: "invite" | "photographe";
};

export const octetsMax = (): number => env().JL_MEDIA_MAX_MO * 1024 * 1024;

/**
 * Enregistre un média. Renvoie son identifiant, ou la raison du refus — une
 * chaîne que l'écran traduit, jamais un message technique jeté à l'invité.
 */
export async function enregistrerMedia(entree: {
  /** Nul pour les photos du photographe : elles n'appartiennent à personne. */
  readonly foyer: string | null;
  readonly momentId: string | null;
  readonly mime: string;
  readonly octets: Uint8Array;
  readonly largeur?: number | undefined;
  readonly hauteur?: number | undefined;
  readonly dureeS?: number | undefined;
  /**
   * `photographe` court-circuite le consentement : ce sont les mariés qui
   * déposent les photos de leur photographe, pas un invité qui partage les
   * siennes. Tout le reste — nettoyage des métadonnées, refus des formats
   * inconnus, modération, purge — reste identique.
   */
  readonly source?: "invite" | "photographe" | undefined;
}): Promise<{ readonly id: string } | { readonly refus: RefusEnvoi }> {
  if (entree.octets.byteLength > octetsMax()) return { refus: "trop_gros" };

  const estPhoto = (MIMES_PHOTO as readonly string[]).includes(entree.mime);
  const estVideo = (MIMES_VIDEO as readonly string[]).includes(entree.mime);
  if (!estPhoto && !estVideo) return { refus: "type_refuse" };

  const duPhotographe = entree.source === "photographe";

  // Rien ne part sans consentement : c'est la condition du brief §8.7, et
  // c'est elle qui fixe aussi la visibilité du média.
  const consentement = duPhotographe
    ? ({ visibilite: "invites", consent_at: new Date() } as const)
    : entree.foyer === null
      ? undefined
      : await consentementMedias(entree.foyer);
  if (consentement === undefined) return { refus: "sans_consentement" };

  const propre = nettoyer(entree.octets);
  if (!propre.nettoye) return { refus: "metadonnees" };

  const id = randomUUID();
  // Le chemin est fabriqué ici, jamais fourni : deux niveaux de dossiers
  // pour qu'un dossier ne finisse pas avec dix mille fichiers.
  const chemin = `${id.slice(0, 2)}/${id}`;
  await stockage().ecrire(chemin, propre.octets);

  await requete(
    `insert into public.media
       (id, storage_path, household_id, moment_id, kind, mime, bytes,
        width, height, duration_s, status, gps_stripped, visibilite, source)
     values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'published', true, $11, $12)`,
    [
      id,
      chemin,
      entree.foyer,
      entree.momentId,
      estVideo ? "video" : "photo",
      entree.mime,
      propre.octets.byteLength,
      entree.largeur ?? null,
      entree.hauteur ?? null,
      entree.dureeS ?? null,
      consentement.visibilite,
      duPhotographe ? "photographe" : "invite",
    ],
  );
  return { id };
}

/**
 * Galerie (brief §8.7). Les filtres sont ceux du brief : par moment, « mes
 * photos », les plus récentes. Les médias masqués n'apparaissent pour
 * personne, pas même pour le foyer qui les a envoyés — sinon la modération
 * ne voudrait rien dire.
 */
export async function galerie(options: {
  readonly momentId?: string | undefined;
  readonly foyer?: string | undefined;
  readonly mesMedias?: boolean | undefined;
  readonly limite?: number | undefined;
  /** Vrai seulement pour l'écran des mariés. */
  readonly pourLesMaries?: boolean | undefined;
  /** Par défaut, seules les photos des invités. */
  readonly source?: "invite" | "photographe" | "toutes" | undefined;
}): Promise<ReadonlyArray<Media>> {
  const conditions = ["status = 'published'"];
  const valeurs: unknown[] = [];

  /*
    Les photos du photographe vivent dans une section à part (brief §8.11) :
    elles ne remontent pas dans la galerie des invités, ni sur le mur, à
    moins qu'on les demande explicitement.
  */
  if (options.source !== "toutes") {
    valeurs.push(options.source ?? "invite");
    conditions.push(`source = $${valeurs.length}`);
  }

  // Un média confié « aux mariés seulement » n'apparaît pas dans la galerie
  // des invités — sauf pour le foyer qui l'a envoyé, qui doit pouvoir le
  // relire et demander son retrait.
  if (options.pourLesMaries !== true) {
    valeurs.push(options.foyer ?? null);
    conditions.push(`(visibilite = 'invites' or household_id = $${valeurs.length})`);
  }

  if (options.momentId !== undefined) {
    valeurs.push(options.momentId);
    conditions.push(`moment_id = $${valeurs.length}`);
  }
  if (options.mesMedias === true) {
    // Sans foyer reconnu, « mes photos » ne peut rien renvoyer : on ne
    // devine pas, on ne montre rien.
    valeurs.push(options.foyer ?? null);
    conditions.push(`household_id = $${valeurs.length}`);
  }
  valeurs.push(options.limite ?? 120);

  return requete<Media>(
    `select id, moment_id, kind, mime, status, created_at, household_id, visibilite, source
       from public.media
      where ${conditions.join(" and ")}
      order by created_at desc
      limit $${valeurs.length}`,
    valeurs,
  );
}

export async function media(id: string): Promise<(Media & { storage_path: string }) | undefined> {
  return une<Media & { storage_path: string }>(
    `select id, storage_path, moment_id, kind, mime, status, created_at, household_id,
            visibilite, source
       from public.media where id = $1`,
    [id],
  );
}

/**
 * Octets d'un média, pour la route qui le sert. Elle refuse un média masqué,
 * et un média confié aux seuls mariés si l'appelant n'est ni les mariés ni le
 * foyer qui l'a envoyé.
 */
export async function octetsDuMedia(
  id: string,
  appelant: { readonly foyer?: string | undefined; readonly maries?: boolean | undefined },
): Promise<{ readonly octets: Uint8Array; readonly mime: string } | undefined> {
  const ligne = await media(id);
  if (ligne === undefined || ligne.status !== "published") return undefined;
  if (
    ligne.visibilite === "maries" &&
    appelant.maries !== true &&
    ligne.household_id !== appelant.foyer
  ) {
    return undefined;
  }
  const octets = await stockage().lire(ligne.storage_path);
  return octets === undefined ? undefined : { octets, mime: ligne.mime };
}

/** Nombre de médias par moment : sert à l'écran des mariés, pas aux invités. */
export async function comptesParMoment(): Promise<ReadonlyArray<{ moment_id: string | null; n: number }>> {
  return requete<{ moment_id: string | null; n: number }>(
    `select moment_id, count(*)::int as n from public.media
      where status = 'published' group by moment_id order by moment_id`,
  );
}

// ------------------------------------------------------------- Modération

/**
 * Masquer une photo (brief §9, un tap). Le fichier reste sur le disque : une
 * décision prise dans l'urgence d'une soirée doit pouvoir se défaire. La
 * suppression définitive relève de la rétention (V4).
 */
export async function masquer(id: string, masque: boolean): Promise<void> {
  await requete("update public.media set status = $2 where id = $1", [
    id,
    masque ? "hidden" : "published",
  ]);
  await journaliser(masque ? "media.masque" : "media.rendu", id);
}

export async function signalements(): Promise<
  ReadonlyArray<{
    readonly id: string;
    readonly media_id: string;
    readonly reason: string | null;
    readonly created_at: Date;
    readonly resolved_at: Date | null;
    readonly status: string;
  }>
> {
  return requete(
    `select t.id, t.media_id, t.reason, t.created_at, t.resolved_at, m.status
       from public.media_takedown t
       join public.media m on m.id = t.media_id
      order by t.resolved_at is not null, t.created_at desc
      limit 100`,
  );
}

/**
 * Demande de retrait (brief §8.7 : « en un tap »). Elle **masque tout de
 * suite** : faire attendre quelqu'un qui demande le retrait d'une photo où
 * il apparaît serait le contraire de ce que le brief promet. La régie peut
 * la rendre visible ensuite si c'était une erreur.
 */
export async function demanderRetrait(
  mediaId: string,
  foyer: string | undefined,
  raison: string | null,
): Promise<boolean> {
  const existe = await media(mediaId);
  if (existe === undefined) return false;

  await requete(
    `insert into public.media_takedown (media_id, requester_household_id, reason)
     values ($1, $2, $3)`,
    [mediaId, foyer ?? null, raison],
  );
  await masquer(mediaId, true);
  return true;
}

export async function resoudreSignalement(id: string): Promise<void> {
  await requete("update public.media_takedown set resolved_at = now() where id = $1", [id]);
}

// --------------------------------------------------------------- J'aime

/**
 * « J'aime » privé : il sert **uniquement** au tri (brief §8.7) et n'est
 * jamais affiché en nombre (§17). Un seul par foyer et par média.
 */
export async function basculerSignal(mediaId: string, foyer: string): Promise<boolean> {
  const lignes = await requete<{ media_id: string }>(
    "delete from public.media_signal where media_id = $1 and household_id = $2 returning media_id",
    [mediaId, foyer],
  );
  if (lignes.length > 0) return false;
  await requete(
    "insert into public.media_signal (media_id, household_id) values ($1, $2) on conflict do nothing",
    [mediaId, foyer],
  );
  return true;
}

export async function signauxDuFoyer(foyer: string): Promise<ReadonlySet<string>> {
  const lignes = await requete<{ media_id: string }>(
    "select media_id from public.media_signal where household_id = $1",
    [foyer],
  );
  return new Set(lignes.map((ligne) => ligne.media_id));
}

async function journaliser(action: string, cible: string): Promise<void> {
  await requete("insert into public.audit_log (role, action, target) values ('regie', $1, $2)", [
    action,
    cible,
  ]);
}
