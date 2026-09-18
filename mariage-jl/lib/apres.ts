import "server-only";
import { requete } from "./db";
import { galerie, media } from "./medias";
import { stockage } from "./stockage";
import { zip, type EntreeZip } from "./zip";

/**
 * La période « Après » (brief §8.11) et la fin de vie des données (§11).
 *
 * Deux principes :
 * — les échéances ne sont **jamais recalculées ici**. Elles viennent de
 *   `jl.echeances()`, c'est-à-dire des mêmes expressions que les purges. Un
 *   écran ne peut donc pas annoncer une date que la base ne tiendra pas.
 * — une archive se fabrique à la demande, jamais à l'avance : un ZIP stocké
 *   serait une deuxième copie des photos à protéger et à purger.
 */
export type Echeance = { readonly quoi: string; readonly le: Date };

export async function echeances(): Promise<ReadonlyArray<Echeance>> {
  return requete<Echeance>("select quoi, le from jl.echeances()");
}

export async function echeance(quoi: string): Promise<Date | undefined> {
  return (await echeances()).find((ligne) => ligne.quoi === quoi)?.le;
}

/**
 * Archive ZIP des souvenirs (brief §8.11). `mesSouvenirs` restreint au
 * foyer ; sinon ce sont tous les souvenirs visibles des invités, plus ceux
 * que ce foyer a confiés aux mariés — exactement ce que la galerie lui
 * montre, ni plus ni moins.
 *
 * Aucune archive n'est mise en cache : elle se refabrique à chaque demande.
 * Une photo retirée entre-temps n'y est donc plus, ce qui est le seul
 * comportement acceptable après une demande de retrait.
 */
export async function archiveDesSouvenirs(options: {
  readonly foyer: string | undefined;
  readonly mesSouvenirs: boolean;
  readonly pourLesMaries?: boolean | undefined;
  readonly prefixe: string;
}): Promise<{ readonly octets: Uint8Array; readonly nombre: number }> {
  const liste = await galerie({
    ...(options.foyer === undefined ? {} : { foyer: options.foyer }),
    ...(options.mesSouvenirs ? { mesMedias: true } : {}),
    ...(options.pourLesMaries === true ? { pourLesMaries: true } : {}),
    limite: 2000,
  });

  const entrees: EntreeZip[] = [];
  for (const ligne of liste) {
    const complet = await media(ligne.id);
    if (complet === undefined) continue;
    const octets = await stockage().lire(complet.storage_path);
    if (octets === undefined) continue;

    // Le nom porte la date et le moment : une archive de deux cents photos
    // doit rester rangeable une fois décompressée.
    const extension = extensionDe(ligne.mime);
    const jour = ligne.created_at.toISOString().slice(0, 10);
    const moment = ligne.moment_id ?? "00";
    entrees.push({
      nom: `${options.prefixe}/${jour}-${moment}-${ligne.id.slice(0, 8)}.${extension}`,
      octets,
      date: ligne.created_at,
    });
  }

  return { octets: zip(entrees), nombre: entrees.length };
}

const EXTENSIONS: Readonly<Record<string, string>> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "video/mp4": "mp4",
  "video/quicktime": "mov",
};

export const extensionDe = (mime: string): string => EXTENSIONS[mime] ?? "bin";

/**
 * Supprime du disque les fichiers dont la ligne a disparu de la base — ce
 * que la purge SQL ne peut pas faire (brief §11 : « les objets du Storage
 * sont supprimés par l'application, qui lit cette même règle »).
 *
 * L'ordre compte : on liste d'abord les chemins encore référencés, puis on
 * parcourt le disque. Un fichier écrit entre les deux est conservé, jamais
 * l'inverse — perdre une photo vaut bien plus cher que garder un orphelin
 * une nuit de plus.
 */
export async function supprimerFichiersOrphelins(
  fichiersSurDisque: ReadonlyArray<string>,
): Promise<ReadonlyArray<string>> {
  const lignes = await requete<{ storage_path: string }>(
    "select storage_path from public.media",
  );
  const connus = new Set(lignes.map((ligne) => ligne.storage_path));
  const orphelins = fichiersSurDisque.filter((chemin) => !connus.has(chemin));
  for (const chemin of orphelins) await stockage().supprimer(chemin);
  return orphelins;
}

/**
 * Le pendant : supprime les **lignes** dont le fichier a disparu du disque.
 *
 * Cela n'arrive pas en fonctionnement normal — c'est justement pourquoi il
 * faut s'en occuper. Une restauration partielle, un volume remonté de
 * travers, un nettoyage manuel : la ligne survit, et la galerie affiche une
 * vignette cassée à tous les invités jusqu'à ce que quelqu'un s'en aperçoive.
 *
 * On ne supprime que ce qui est explicitement absent de la liste fournie,
 * jamais sur la foi d'une lecture qui aurait pu échouer.
 */
export async function supprimerLignesSansFichier(
  fichiersSurDisque: ReadonlyArray<string>,
): Promise<number> {
  const presents = new Set(fichiersSurDisque);
  const lignes = await requete<{ id: string; storage_path: string }>(
    "select id, storage_path from public.media",
  );
  const perdues = lignes.filter((ligne) => !presents.has(ligne.storage_path));
  if (perdues.length === 0) return 0;

  await requete("delete from public.media where id = any($1::uuid[])", [
    perdues.map((ligne) => ligne.id),
  ]);
  return perdues.length;
}

/**
 * Ce que nous détenons sur un foyer, pour l'écran « Mes données » (§11).
 * On compte, on ne recopie pas : l'écran doit dire ce qui existe, pas
 * réafficher les allergies de chacun.
 */
export type MesDonnees = {
  readonly invites: number;
  readonly aRepondu: boolean;
  readonly allergies: number;
  readonly souvenirs: number;
  readonly messages: number;
  readonly rappels: boolean;
  readonly notifications: number;
};

export async function mesDonnees(foyer: string): Promise<MesDonnees> {
  const [invites, reponse, allergies, souvenirs, messages, rappels, notifications] =
    await Promise.all([
      compter("select count(*)::int as n from public.guests where household_id = $1", foyer),
      compter("select count(*)::int as n from public.rsvp where household_id = $1", foyer),
      compter(
        `select count(*)::int as n from public.health_allergies a
           join public.guests g on g.id = a.guest_id
          where g.household_id = $1`,
        foyer,
      ),
      compter("select count(*)::int as n from public.media where household_id = $1", foyer),
      compter(
        "select count(*)::int as n from public.absent_messages where household_id = $1",
        foyer,
      ),
      compter(
        `select count(*)::int as n from public.reminder_optin
          where household_id = $1 and revoked_at is null`,
        foyer,
      ),
      compter(
        "select count(*)::int as n from public.push_subscription where household_id = $1",
        foyer,
      ),
    ]);

  return {
    invites,
    aRepondu: reponse > 0,
    allergies,
    souvenirs,
    messages,
    rappels: rappels > 0,
    notifications,
  };
}

async function compter(sql: string, foyer: string): Promise<number> {
  const lignes = await requete<{ n: number }>(sql, [foyer]);
  return Number(lignes[0]?.n ?? 0);
}

/**
 * Le livre d'or : les messages que leurs auteurs ont choisi de rendre
 * visibles (brief §8.9). Les messages privés n'en sortent jamais, et aucun
 * message ne porte le nom de son foyer à l'écran.
 */
export async function livreDOr(): Promise<
  ReadonlyArray<{ readonly id: string; readonly body: string; readonly created_at: Date }>
> {
  return requete(
    `select id, body, created_at from public.absent_messages
      where visibility = 'guestbook'
      order by created_at desc limit 200`,
  );
}
