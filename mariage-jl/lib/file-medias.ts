import { openDB, type IDBPDatabase } from "idb";

/**
 * File d'envoi des souvenirs (brief §8.7 : « file d'envoi persistante,
 * reprend après coupure, fermeture de l'app ou redémarrage »).
 *
 * Elle vit dans IndexedDB et garde les **octets** du fichier, pas une
 * référence : un `File` choisi dans le sélecteur ne survit pas à la
 * fermeture de l'onglet, un `Blob` stocké, oui.
 *
 * Limite honnête, déjà consignée dans docs/PLAN.md : sur iPhone, rien ne
 * repart tant que l'application est fermée (Safari n'a pas la
 * synchronisation en arrière-plan). La reprise a lieu à la réouverture, et
 * l'écran le dit au lieu de promettre le contraire.
 */
const BASE = "jl-medias";
const MAGASIN = "souvenirs";
const VERSION = 1;

export type SouvenirEnAttente = {
  readonly id?: number;
  readonly blob: Blob;
  readonly nom: string;
  readonly mime: string;
  readonly moment: string | null;
  readonly defi?: string | null;
  readonly largeur: number | null;
  readonly hauteur: number | null;
  readonly duree: number | null;
  readonly wifiSeulement: boolean;
  readonly cree: number;
  /** Nombre de refus définitifs : sert à ne pas boucler pour rien. */
  readonly refus?: number;
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

export async function mettreEnAttente(souvenir: Omit<SouvenirEnAttente, "id">): Promise<void> {
  const instance = await base();
  await instance.add(MAGASIN, souvenir);
  instance.close();
}

export async function enAttente(): Promise<ReadonlyArray<SouvenirEnAttente>> {
  const instance = await base();
  const tout = (await instance.getAll(MAGASIN)) as SouvenirEnAttente[];
  instance.close();
  return tout;
}

export async function oublier(id: number): Promise<void> {
  const instance = await base();
  await instance.delete(MAGASIN, id);
  instance.close();
}

export type Reseau = "wifi" | "mobile" | "inconnu";

/**
 * Type de réseau, **sans rien deviner**. Chrome sur Android le dit ;
 * Safari ne l'expose pas. Dans ce cas on répond « inconnu », et l'appelant
 * choisit d'attendre un geste plutôt que d'envoyer par erreur sur un forfait
 * mobile.
 */
export function reseau(): Reseau {
  const connexion = (
    navigator as Navigator & { connection?: { type?: string; effectiveType?: string } }
  ).connection;
  if (connexion?.type === "wifi" || connexion?.type === "ethernet") return "wifi";
  if (connexion?.type === "cellular") return "mobile";
  return "inconnu";
}

export type Resultat = { readonly partis: number; readonly retenus: number; readonly refuses: number };

/**
 * Tente d'envoyer la file, du plus ancien au plus récent.
 *
 * — Un envoi accepté est oublié.
 * — Un envoi refusé **définitivement** (415, 413, 403) est oublié aussi : le
 *   garder reviendrait à réessayer à l'infini un fichier que le serveur ne
 *   prendra jamais.
 * — Tout le reste (réseau absent, 409 « envois suspendus », 500) est gardé.
 *
 * `forcer` ignore l'option « seulement en Wi-Fi » : c'est le bouton
 * « Envoyer maintenant ».
 */
export async function vider(forcer = false): Promise<Resultat> {
  const instance = await base();
  const attente = (await instance.getAll(MAGASIN)) as SouvenirEnAttente[];
  let partis = 0;
  let retenus = 0;
  let refuses = 0;

  for (const souvenir of attente) {
    if (!forcer && souvenir.wifiSeulement && reseau() !== "wifi") {
      retenus += 1;
      continue;
    }

    const corps = new FormData();
    corps.append("fichier", souvenir.blob, souvenir.nom);
    if (souvenir.moment !== null) corps.append("moment", souvenir.moment);
    if (souvenir.defi != null) corps.append("defi", souvenir.defi);
    if (souvenir.largeur !== null) corps.append("largeur", String(souvenir.largeur));
    if (souvenir.hauteur !== null) corps.append("hauteur", String(souvenir.hauteur));
    if (souvenir.duree !== null) corps.append("duree", String(souvenir.duree));

    try {
      const reponse = await fetch("/photos/televerser", { method: "POST", body: corps });
      if (reponse.ok) {
        if (souvenir.id !== undefined) await instance.delete(MAGASIN, souvenir.id);
        partis += 1;
        continue;
      }
      if ([403, 413, 415, 400].includes(reponse.status)) {
        if (souvenir.id !== undefined) await instance.delete(MAGASIN, souvenir.id);
        refuses += 1;
        continue;
      }
      retenus += 1;
    } catch {
      // Toujours hors ligne : on garde, et on réessaiera.
      retenus += 1;
    }
  }

  instance.close();
  return { partis, retenus, refuses };
}
