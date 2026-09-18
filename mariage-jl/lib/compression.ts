/**
 * Compression des images dans le navigateur (brief §8.7 et §0 bis : « les
 * vidéos sont limitées à 60 secondes, compressées côté navigateur quand
 * c'est possible »).
 *
 * Le ré-encodage par `canvas` a un effet de bord précieux : il **perd toutes
 * les métadonnées**, EXIF et donc GPS compris. C'est une première barrière ;
 * la vraie est côté serveur (lib/metadonnees.ts), parce qu'un ré-encodage
 * peut échouer et que l'envoi part quand même.
 *
 * HEIC : Safari sur iPhone sait le décoder, donc la conversion en JPEG a
 * lieu exactement là où le HEIC est produit. Ailleurs (Chrome, Firefox) le
 * décodage échoue, on garde le fichier d'origine, et le serveur le refuse
 * avec une explication. Aucun décodeur HEIC embarqué : ce serait 400 Ko de
 * WebAssembly pour un cas qui se règle tout seul.
 */
export const COTE_MAX = 2000;
export const QUALITE = 0.82;
export const DUREE_VIDEO_MAX_S = 60;

export type Prepare = {
  readonly blob: Blob;
  readonly nom: string;
  readonly mime: string;
  readonly largeur: number | null;
  readonly hauteur: number | null;
  readonly duree: number | null;
  /** Vrai si le fichier a été ré-encodé, donc débarrassé de ses métadonnées. */
  readonly reencode: boolean;
};

export type RefusLocal = "video_trop_longue" | "type_refuse";

const estImage = (type: string): boolean => type.startsWith("image/");
const estVideo = (type: string): boolean => type.startsWith("video/");

/** Dimensions cibles : on ne grandit jamais une image déjà petite. */
export function dimensions(
  largeur: number,
  hauteur: number,
  coteMax = COTE_MAX,
): { readonly largeur: number; readonly hauteur: number } {
  const plusGrand = Math.max(largeur, hauteur);
  if (plusGrand <= coteMax) return { largeur, hauteur };
  const facteur = coteMax / plusGrand;
  return {
    largeur: Math.max(1, Math.round(largeur * facteur)),
    hauteur: Math.max(1, Math.round(hauteur * facteur)),
  };
}

export async function preparer(fichier: File): Promise<Prepare | { readonly refus: RefusLocal }> {
  if (estVideo(fichier.type)) return preparerVideo(fichier);
  if (!estImage(fichier.type)) return { refus: "type_refuse" };
  return preparerImage(fichier);
}

async function preparerImage(fichier: File): Promise<Prepare> {
  try {
    const image = await createImageBitmap(fichier);
    const cible = dimensions(image.width, image.height);
    const toile = document.createElement("canvas");
    toile.width = cible.largeur;
    toile.height = cible.hauteur;
    const contexte = toile.getContext("2d");
    if (contexte === null) throw new Error("pas de contexte 2d");
    contexte.drawImage(image, 0, 0, cible.largeur, cible.hauteur);
    image.close();

    const blob = await new Promise<Blob | null>((resoudre) =>
      toile.toBlob(resoudre, "image/jpeg", QUALITE),
    );
    if (blob === null) throw new Error("ré-encodage impossible");

    return {
      blob,
      nom: `${fichier.name.replace(/\.[^.]+$/, "")}.jpg`,
      mime: "image/jpeg",
      largeur: cible.largeur,
      hauteur: cible.hauteur,
      duree: null,
      reencode: true,
    };
  } catch {
    // HEIC hors Safari, image abîmée, mémoire insuffisante : on garde le
    // fichier tel quel. Le serveur tranchera, et il le dira.
    return {
      blob: fichier,
      nom: fichier.name,
      mime: fichier.type,
      largeur: null,
      hauteur: null,
      duree: null,
      reencode: false,
    };
  }
}

/**
 * Vidéo : aucune recompression (il faudrait un encodeur), mais la durée est
 * vérifiée ici, avant l'envoi. Refuser 200 Mo après les avoir téléversés
 * serait une insulte à un forfait mobile.
 */
async function preparerVideo(fichier: File): Promise<Prepare | { readonly refus: RefusLocal }> {
  const duree = await dureeVideo(fichier);
  if (duree !== null && duree > DUREE_VIDEO_MAX_S + 0.5) {
    return { refus: "video_trop_longue" };
  }
  return {
    blob: fichier,
    nom: fichier.name,
    mime: fichier.type,
    largeur: null,
    hauteur: null,
    duree,
    reencode: false,
  };
}

function dureeVideo(fichier: File): Promise<number | null> {
  return new Promise((resoudre) => {
    const url = URL.createObjectURL(fichier);
    const lecteur = document.createElement("video");
    const finir = (valeur: number | null): void => {
      URL.revokeObjectURL(url);
      resoudre(valeur);
    };
    lecteur.preload = "metadata";
    lecteur.onloadedmetadata = () =>
      finir(Number.isFinite(lecteur.duration) ? lecteur.duration : null);
    lecteur.onerror = () => finir(null);
    lecteur.src = url;
  });
}
