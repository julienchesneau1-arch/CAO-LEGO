import { openDB, type IDBPDatabase } from "idb";

/**
 * File d'attente persistante (brief §5 et §12 : « réponses et médias en file
 * d'attente », « Tout ce que vous faites sera envoyé dès son retour »).
 *
 * Elle vit dans IndexedDB, donc elle survit à la fermeture de l'application
 * et au redémarrage du téléphone. Les médias la rejoindront en V3.
 *
 * Limite honnête, déjà signalée dans docs/PLAN.md : sur iPhone, rien ne peut
 * repartir tant que l'application est fermée (Safari n'implémente pas la
 * synchronisation en arrière-plan). La reprise a donc lieu à la réouverture,
 * et l'interface le dit au lieu de promettre le contraire.
 */
const BASE = "jl-file";
const MAGASIN = "envois";
const VERSION = 1;

export type EnvoiEnAttente = {
  readonly id?: number;
  readonly action: string;
  readonly champs: ReadonlyArray<readonly [string, string]>;
  readonly cree: number;
};

async function base(): Promise<IDBPDatabase> {
  return openDB(BASE, VERSION, {
    upgrade(instance) {
      if (!instance.objectStoreNames.contains(MAGASIN)) {
        instance.createObjectStore(MAGASIN, { keyPath: "id", autoIncrement: true });
      }
    },
  });
}

export async function mettreEnAttente(envoi: Omit<EnvoiEnAttente, "id">): Promise<void> {
  const instance = await base();
  await instance.add(MAGASIN, envoi);
  instance.close();
}

export async function enAttente(): Promise<ReadonlyArray<EnvoiEnAttente>> {
  const instance = await base();
  const tout = (await instance.getAll(MAGASIN)) as EnvoiEnAttente[];
  instance.close();
  return tout;
}

/**
 * Tente d'envoyer la file, du plus ancien au plus récent, et ne retire une
 * entrée que si le serveur l'a acceptée. Renvoie le nombre d'envois partis.
 */
export async function vider(): Promise<number> {
  const instance = await base();
  const attente = (await instance.getAll(MAGASIN)) as EnvoiEnAttente[];
  let partis = 0;

  for (const envoi of attente) {
    const corps = new FormData();
    for (const [cle, valeur] of envoi.champs) corps.append(cle, valeur);
    try {
      const reponse = await fetch(envoi.action, {
        method: "POST",
        body: corps,
        redirect: "follow",
      });
      if (!reponse.ok) break; // le réseau est là mais le serveur refuse : on garde
      if (envoi.id !== undefined) await instance.delete(MAGASIN, envoi.id);
      partis += 1;
    } catch {
      break; // toujours hors ligne : on réessaiera
    }
  }

  instance.close();
  return partis;
}
