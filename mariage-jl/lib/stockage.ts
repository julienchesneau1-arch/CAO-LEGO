import "server-only";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { env } from "./env";

/**
 * Stockage des médias (brief §8.7). Même dessin que le transport e-mail :
 * une interface, une mise en œuvre locale, et **une fonction à écrire** le
 * jour où le projet Supabase existe (question V0-06). Rien dans le reste du
 * code ne sait où les fichiers vivent.
 *
 * La mise en œuvre par fichiers convient au VPS de la section 0 bis : les
 * médias sont sur le disque, servis par le serveur Next après vérification
 * du foyer — jamais par une URL publique devinable.
 */
export type Stockage = {
  readonly ecrire: (chemin: string, octets: Uint8Array) => Promise<void>;
  readonly lire: (chemin: string) => Promise<Uint8Array | undefined>;
  readonly supprimer: (chemin: string) => Promise<void>;
};

const racine = (): string => resolve(env().JL_MEDIAS_DIR ?? ".medias");

/**
 * Un chemin de média est **fabriqué** par le serveur à partir d'un
 * identifiant tiré au hasard : il ne vient jamais de l'invité. Cette
 * vérification est la ceinture, au cas où un appelant futur l'oublie.
 */
function chemainSur(chemin: string): string {
  const complet = resolve(join(racine(), chemin));
  if (complet !== racine() && !complet.startsWith(`${racine()}/`)) {
    throw new Error("Chemin de média hors du dossier de stockage.");
  }
  return complet;
}

const fichiers: Stockage = {
  async ecrire(chemin, octets) {
    const complet = chemainSur(chemin);
    await mkdir(dirname(complet), { recursive: true });
    await writeFile(complet, octets);
  },
  async lire(chemin) {
    try {
      return new Uint8Array(await readFile(chemainSur(chemin)));
    } catch {
      return undefined;
    }
  },
  async supprimer(chemin) {
    await rm(chemainSur(chemin), { force: true });
  },
};

export function stockage(): Stockage {
  // Une seule mise en œuvre pour l'instant, et c'est assumé : ajouter
  // Supabase Storage ici sera une trentaine de lignes, le jour où le projet
  // existe. Voir docs/QUESTIONS_BLOQUANTES.md, V0-06.
  return fichiers;
}
