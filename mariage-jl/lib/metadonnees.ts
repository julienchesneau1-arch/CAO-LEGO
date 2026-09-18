/**
 * Retrait des métadonnées des médias envoyés par les invités (brief §8.7 et
 * §11 : « suppression GPS »).
 *
 * Pourquoi côté serveur alors que le navigateur ré-encode déjà les images :
 * parce qu'un ré-encodage peut échouer (HEIC hors Safari, fichier trop grand,
 * onglet en arrière-plan) et que l'envoi part quand même. Le serveur est donc
 * la barrière qui compte — celle qu'aucun navigateur ne peut contourner.
 *
 * Aucune dépendance : ces formats se lisent avec des octets et un compteur,
 * et une bibliothèque de plus serait une surface d'attaque de plus.
 */

const lireU32 = (octets: Uint8Array, index: number): number =>
  ((octets[index] ?? 0) << 24) |
  ((octets[index + 1] ?? 0) << 16) |
  ((octets[index + 2] ?? 0) << 8) |
  (octets[index + 3] ?? 0);

const marque = (octets: Uint8Array, index: number, texte: string): boolean => {
  for (let i = 0; i < texte.length; i += 1) {
    if (octets[index + i] !== texte.charCodeAt(i)) return false;
  }
  return true;
};

export type Format = "jpeg" | "png" | "mp4" | "inconnu";

export function format(octets: Uint8Array): Format {
  if (octets[0] === 0xff && octets[1] === 0xd8) return "jpeg";
  if (
    octets[0] === 0x89 &&
    octets[1] === 0x50 &&
    octets[2] === 0x4e &&
    octets[3] === 0x47
  ) {
    return "png";
  }
  // Un fichier ISO-BMFF commence par la taille de son premier atome, suivie
  // de « ftyp ». C'est vrai du MP4 comme du MOV des iPhone.
  if (octets.length > 12 && marque(octets, 4, "ftyp")) return "mp4";
  return "inconnu";
}

/**
 * JPEG : on garde les segments d'image et on jette tous les APPn. EXIF
 * (APP1), XMP (APP1 encore), IPTC et le profil couleur (APP2) disparaissent
 * ensemble — donc la position GPS aussi, qui vit dans EXIF.
 *
 * Le profil couleur est une perte assumée : une photo de mariage vue sur un
 * téléphone ne souffre pas de repasser en sRGB, et garder APP2 obligerait à
 * distinguer les APP1 « EXIF » des APP1 « XMP », donc à faire confiance à
 * une étiquette écrite par l'appareil.
 */
export function nettoyerJpeg(octets: Uint8Array): Uint8Array {
  const morceaux: Uint8Array[] = [octets.subarray(0, 2)]; // SOI
  let index = 2;

  while (index + 3 < octets.length) {
    if (octets[index] !== 0xff) break; // flux abîmé : on s'arrête là
    const type = octets[index + 1] ?? 0;

    // Début des données compressées : tout le reste est l'image.
    if (type === 0xda) {
      morceaux.push(octets.subarray(index));
      index = octets.length;
      break;
    }
    const taille = ((octets[index + 2] ?? 0) << 8) | (octets[index + 3] ?? 0);
    if (taille < 2) break;
    const fin = index + 2 + taille;
    const estApp = type >= 0xe0 && type <= 0xef;
    const estCommentaire = type === 0xfe;
    if (!estApp && !estCommentaire) morceaux.push(octets.subarray(index, fin));
    index = fin;
  }

  return concatener(morceaux);
}

/**
 * PNG : on jette les blocs de métadonnées et on garde les blocs d'image. La
 * liste est explicite — un bloc inconnu est **gardé**, parce qu'un PNG dont
 * on retire un bloc critique ne s'affiche plus.
 */
const BLOCS_PNG_A_JETER = new Set(["eXIf", "tEXt", "iTXt", "zTXt", "tIME", "dSIG"]);

export function nettoyerPng(octets: Uint8Array): Uint8Array {
  const morceaux: Uint8Array[] = [octets.subarray(0, 8)]; // signature
  let index = 8;

  while (index + 8 <= octets.length) {
    const taille = lireU32(octets, index);
    const nom = String.fromCharCode(
      octets[index + 4] ?? 0,
      octets[index + 5] ?? 0,
      octets[index + 6] ?? 0,
      octets[index + 7] ?? 0,
    );
    const fin = index + 12 + taille; // taille + nom + données + CRC
    if (fin > octets.length) break;
    if (!BLOCS_PNG_A_JETER.has(nom)) morceaux.push(octets.subarray(index, fin));
    index = fin;
    if (nom === "IEND") break;
  }

  return concatener(morceaux);
}

/**
 * MP4 / MOV : la position GPS des iPhone et des Android vit dans
 * `moov/udta` (atome `©xyz`) et dans `moov/meta`. On réécrit le fichier en
 * retirant ces deux atomes partout où ils apparaissent.
 *
 * On ne touche à rien d'autre : ni `mdat` (les images), ni `stbl` (les
 * tables d'échantillons, qui portent des décalages absolus). Retirer `udta`
 * ne décale rien de ce que `stbl` indexe, parce que `udta` est à l'intérieur
 * de `moov` et que `moov` n'est pas indexé par des décalages — contrairement
 * à `mdat`, auquel on ne touche pas.
 */
const ATOMES_A_JETER = new Set(["udta", "meta"]);
const ATOMES_CONTENEURS = new Set(["moov", "trak", "mdia", "minf", "edts"]);

export function nettoyerMp4(octets: Uint8Array): Uint8Array {
  return nettoyerAtomes(octets, 0, octets.length);
}

function nettoyerAtomes(octets: Uint8Array, debut: number, fin: number): Uint8Array {
  const morceaux: Uint8Array[] = [];
  let index = debut;

  while (index + 8 <= fin) {
    let taille = lireU32(octets, index);
    let entete = 8;
    if (taille === 1) {
      // Taille 64 bits : on ne la réécrit pas, on la recopie telle quelle.
      entete = 16;
      const haut = lireU32(octets, index + 8);
      const bas = lireU32(octets, index + 12);
      taille = haut * 2 ** 32 + bas;
    } else if (taille === 0) {
      taille = fin - index; // dernier atome, jusqu'au bout
    }
    if (taille < entete || index + taille > fin) {
      // Atome incohérent : on recopie le reste sans prétendre le comprendre.
      morceaux.push(octets.subarray(index, fin));
      break;
    }

    const nom = String.fromCharCode(
      octets[index + 4] ?? 0,
      octets[index + 5] ?? 0,
      octets[index + 6] ?? 0,
      octets[index + 7] ?? 0,
    );

    if (ATOMES_A_JETER.has(nom)) {
      // Rien à recopier : l'atome disparaît entièrement.
    } else if (ATOMES_CONTENEURS.has(nom) && entete === 8) {
      const interieur = nettoyerAtomes(octets, index + entete, index + taille);
      const enTete = new Uint8Array(8);
      const nouvelle = 8 + interieur.length;
      enTete[0] = (nouvelle >>> 24) & 0xff;
      enTete[1] = (nouvelle >>> 16) & 0xff;
      enTete[2] = (nouvelle >>> 8) & 0xff;
      enTete[3] = nouvelle & 0xff;
      enTete.set(octets.subarray(index + 4, index + 8), 4);
      morceaux.push(enTete, interieur);
    } else {
      morceaux.push(octets.subarray(index, index + taille));
    }
    index += taille;
  }

  return concatener(morceaux);
}

function concatener(morceaux: ReadonlyArray<Uint8Array>): Uint8Array {
  const total = morceaux.reduce((somme, morceau) => somme + morceau.length, 0);
  const sortie = new Uint8Array(total);
  let position = 0;
  for (const morceau of morceaux) {
    sortie.set(morceau, position);
    position += morceau.length;
  }
  return sortie;
}

export type Nettoyage = {
  readonly octets: Uint8Array;
  readonly format: Format;
  /** Vrai seulement si le format a été reconnu **et** nettoyé. */
  readonly nettoye: boolean;
};

/**
 * Point d'entrée unique. Un format inconnu ressort **inchangé et marqué non
 * nettoyé** : c'est à l'appelant de refuser, pas à cette fonction de mentir
 * sur ce qu'elle a fait.
 */
export function nettoyer(octets: Uint8Array): Nettoyage {
  const type = format(octets);
  switch (type) {
    case "jpeg":
      return { octets: nettoyerJpeg(octets), format: type, nettoye: true };
    case "png":
      return { octets: nettoyerPng(octets), format: type, nettoye: true };
    case "mp4":
      return { octets: nettoyerMp4(octets), format: type, nettoye: true };
    default:
      return { octets, format: type, nettoye: false };
  }
}
