/**
 * Chiffrement de « La promesse » (brief §8.10 et §11).
 *
 * Le brief exige que les vœux soient « invisibles de tous, y compris des
 * mariés » jusqu'au 3 juin 2029. Une politique de base de données n'y suffit
 * pas : qui détient la connexion lit la table. Le vœu est donc chiffré **dans
 * le navigateur** avec une clé publique, et seule la clé privée — imprimée,
 * conservée hors ligne, jamais déposée sur le serveur — permet de l'ouvrir.
 *
 * Schéma hybride, avec WebCrypto seul, sans dépendance :
 * - une clé AES-256-GCM tirée au hasard par vœu chiffre le texte ;
 * - cette clé est elle-même chiffrée en RSA-OAEP-2048 (SHA-256) ;
 * - l'enveloppe stockée ne contient que des éléments chiffrés.
 *
 * RSA seul ne suffirait pas : il ne chiffre que ~190 octets, un mot de vœu en
 * fait davantage.
 */
export type Enveloppe = {
  readonly v: 1;
  readonly cle: string; // clé AES chiffrée (RSA-OAEP), base64
  readonly iv: string; // vecteur d'initialisation AES-GCM, base64
  readonly texte: string; // texte chiffré (AES-GCM), base64
};

const ALGO_RSA = { name: "RSA-OAEP", hash: "SHA-256" } as const;

const enBase64 = (octets: ArrayBuffer): string =>
  btoa(String.fromCharCode(...new Uint8Array(octets)));

function depuisBase64(valeur: string): ArrayBuffer {
  const brut = atob(valeur);
  const tampon = new ArrayBuffer(brut.length);
  const vue = new Uint8Array(tampon);
  for (let i = 0; i < brut.length; i += 1) vue[i] = brut.charCodeAt(i);
  return tampon;
}

export async function importerClePublique(spkiBase64: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "spki",
    depuisBase64(spkiBase64),
    ALGO_RSA,
    false,
    ["encrypt"],
  );
}

export async function importerClePrivee(pkcs8Base64: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "pkcs8",
    depuisBase64(pkcs8Base64),
    ALGO_RSA,
    false,
    ["decrypt"],
  );
}

export async function sceller(texte: string, clePublique: CryptoKey): Promise<Enveloppe> {
  const cleAes = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, [
    "encrypt",
  ]);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ivTampon = new ArrayBuffer(12);
  new Uint8Array(ivTampon).set(iv);
  const chiffre = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    cleAes,
    new TextEncoder().encode(texte),
  );
  const cleBrute = await crypto.subtle.exportKey("raw", cleAes);
  const cleChiffree = await crypto.subtle.encrypt({ name: "RSA-OAEP" }, clePublique, cleBrute);

  return {
    v: 1,
    cle: enBase64(cleChiffree),
    iv: enBase64(ivTampon),
    texte: enBase64(chiffre),
  };
}

export async function desceller(enveloppe: Enveloppe, clePrivee: CryptoKey): Promise<string> {
  if (enveloppe.v !== 1) throw new Error(`Enveloppe de version inconnue : ${String(enveloppe.v)}`);

  const cleBrute = await crypto.subtle.decrypt(
    { name: "RSA-OAEP" },
    clePrivee,
    depuisBase64(enveloppe.cle),
  );
  const cleAes = await crypto.subtle.importKey("raw", cleBrute, { name: "AES-GCM" }, false, [
    "decrypt",
  ]);
  const clair = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: new Uint8Array(depuisBase64(enveloppe.iv)) },
    cleAes,
    depuisBase64(enveloppe.texte),
  );
  return new TextDecoder().decode(clair);
}
