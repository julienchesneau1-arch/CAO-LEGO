import { describe, expect, it } from "vitest";
import { format, nettoyer, nettoyerJpeg, nettoyerMp4, nettoyerPng } from "@/lib/metadonnees";

/**
 * Retrait des métadonnées (brief §8.7, §11). Ces tests construisent des
 * fichiers minimaux mais **structurellement vrais** : l'enjeu n'est pas
 * qu'une fonction renvoie quelque chose, c'est que la position GPS ne soit
 * plus dans les octets et que l'image reste lisible.
 */
const octets = (...valeurs: ReadonlyArray<number | string>): Uint8Array => {
  const liste: number[] = [];
  for (const valeur of valeurs) {
    if (typeof valeur === "number") liste.push(valeur);
    else for (const caractere of valeur) liste.push(caractere.charCodeAt(0));
  }
  return new Uint8Array(liste);
};

const contient = (donnees: Uint8Array, texte: string): boolean =>
  Buffer.from(donnees).includes(Buffer.from(texte, "latin1"));

const u32 = (valeur: number): ReadonlyArray<number> => [
  (valeur >>> 24) & 0xff,
  (valeur >>> 16) & 0xff,
  (valeur >>> 8) & 0xff,
  valeur & 0xff,
];

describe("reconnaissance des formats", () => {
  it("distingue JPEG, PNG, MP4 et le reste", () => {
    expect(format(octets(0xff, 0xd8, 0xff, 0xe0))).toBe("jpeg");
    expect(format(octets(0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a))).toBe("png");
    expect(format(octets(...u32(20), "ftypisom", 0, 0, 0, 0))).toBe("mp4");
    expect(format(octets("HEICmaybe"))).toBe("inconnu");
    expect(format(octets())).toBe("inconnu");
  });
});

describe("JPEG", () => {
  /** APP1 « Exif » contenant une position, puis l'image. */
  const avecGps = (): Uint8Array => {
    const exif = "Exif\0\0GPSLatitude47.1234GPSLongitude0.4321";
    return octets(
      0xff, 0xd8, // SOI
      0xff, 0xe1, ((exif.length + 2) >> 8) & 0xff, (exif.length + 2) & 0xff, exif, // APP1
      0xff, 0xe2, 0x00, 0x09, "ICCprof", // APP2 : 2 octets de taille + 7 de charge
      0xff, 0xfe, 0x00, 0x09, "comment", // COM
      0xff, 0xdb, 0x00, 0x05, 0x00, 0x01, 0x02, // DQT, à garder
      0xff, 0xda, 0x00, 0x04, 0x01, 0x02, 0x03, 0x04, 0x05, // SOS + données
    );
  };

  it("retire la position GPS", () => {
    const source = avecGps();
    expect(contient(source, "GPSLatitude")).toBe(true);
    const propre = nettoyerJpeg(source);
    expect(contient(propre, "GPSLatitude")).toBe(false);
    expect(contient(propre, "GPSLongitude")).toBe(false);
    expect(contient(propre, "Exif")).toBe(false);
  });

  it("retire aussi les commentaires et le profil couleur", () => {
    const propre = nettoyerJpeg(avecGps());
    expect(contient(propre, "comment")).toBe(false);
    expect(contient(propre, "ICCprof")).toBe(false);
  });

  /**
   * Le point qui compte autant que le retrait : le fichier doit rester une
   * image. On vérifie la signature, la table de quantification et le début
   * des données compressées.
   */
  it("garde une image lisible", () => {
    const propre = nettoyerJpeg(avecGps());
    expect(propre[0]).toBe(0xff);
    expect(propre[1]).toBe(0xd8);
    expect(contient(propre, "\xff\xdb")).toBe(true);
    expect(contient(propre, "\xff\xda")).toBe(true);
    // Les données après SOS sont intactes.
    expect(propre.subarray(propre.length - 5)).toEqual(
      new Uint8Array([0x01, 0x02, 0x03, 0x04, 0x05]),
    );
  });

  it("ne casse pas un fichier tronqué", () => {
    const tronque = octets(0xff, 0xd8, 0xff, 0xe1, 0x00);
    expect(() => nettoyerJpeg(tronque)).not.toThrow();
    expect(nettoyerJpeg(tronque).subarray(0, 2)).toEqual(new Uint8Array([0xff, 0xd8]));
  });
});

describe("PNG", () => {
  const bloc = (nom: string, donnees: string): ReadonlyArray<number | string> => [
    ...u32(donnees.length),
    nom,
    donnees,
    ...u32(0), // CRC : jamais relu ici
  ];

  const avecGps = (): Uint8Array =>
    octets(
      0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
      ...bloc("IHDR", "wwwwhhhh_____"),
      ...bloc("eXIf", "GPSLatitude47"),
      ...bloc("tEXt", "Comment\0pris a Roiffe"),
      ...bloc("IDAT", "pixels"),
      ...bloc("IEND", ""),
    );

  it("retire les blocs de métadonnées et garde les blocs d'image", () => {
    const propre = nettoyerPng(avecGps());
    expect(contient(propre, "GPSLatitude")).toBe(false);
    expect(contient(propre, "pris a Roiffe")).toBe(false);
    expect(contient(propre, "IHDR")).toBe(true);
    expect(contient(propre, "IDAT")).toBe(true);
    expect(contient(propre, "IEND")).toBe(true);
  });

  it("garde un bloc inconnu plutôt que de casser l'image", () => {
    const avecInconnu = octets(
      0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
      ...bloc("IHDR", "wwwwhhhh_____"),
      ...bloc("pHYs", "resolution"),
      ...bloc("IDAT", "pixels"),
      ...bloc("IEND", ""),
    );
    expect(contient(nettoyerPng(avecInconnu), "pHYs")).toBe(true);
  });
});

describe("MP4 et MOV", () => {
  const atome = (nom: string, contenu: ReadonlyArray<number | string>): ReadonlyArray<number | string> => {
    const taille =
      8 +
      contenu.reduce<number>(
        (somme, valeur) => somme + (typeof valeur === "number" ? 1 : valeur.length),
        0,
      );
    return [...u32(taille), nom, ...contenu];
  };

  const avecGps = (): Uint8Array =>
    octets(
      ...atome("ftyp", ["isomiso2"]),
      ...atome("moov", [
        ...atome("mvhd", ["entetefilm"]),
        ...atome("udta", [...atome("©xyz", ["+47.1234+000.4321/"])]),
        ...atome("trak", [...atome("tkhd", ["pisteee_"]), ...atome("udta", ["encoredugps"])]),
      ]),
      ...atome("mdat", ["images_de_la_video"]),
    );

  it("retire la position des iPhone, partout où elle se cache", () => {
    const source = avecGps();
    expect(contient(source, "+47.1234+000.4321/")).toBe(true);
    const propre = nettoyerMp4(source);
    expect(contient(propre, "+47.1234+000.4321/")).toBe(false);
    expect(contient(propre, "encoredugps")).toBe(false);
    expect(contient(propre, "udta")).toBe(false);
  });

  it("garde les images et l'en-tête du film", () => {
    const propre = nettoyerMp4(avecGps());
    expect(contient(propre, "images_de_la_video")).toBe(true);
    expect(contient(propre, "entetefilm")).toBe(true);
    expect(contient(propre, "pisteee_")).toBe(true);
    expect(contient(propre, "ftyp")).toBe(true);
  });

  /**
   * La taille de `moov` doit être **réécrite** après retrait : un lecteur qui
   * fait confiance à l'ancienne taille lirait dans le vide.
   */
  it("réécrit la taille des conteneurs qu'il a réduits", () => {
    const propre = nettoyerMp4(avecGps());
    let index = 0;
    while (index + 8 <= propre.length) {
      const taille =
        ((propre[index] ?? 0) << 24) |
        ((propre[index + 1] ?? 0) << 16) |
        ((propre[index + 2] ?? 0) << 8) |
        (propre[index + 3] ?? 0);
      const nom = String.fromCharCode(
        propre[index + 4] ?? 0,
        propre[index + 5] ?? 0,
        propre[index + 6] ?? 0,
        propre[index + 7] ?? 0,
      );
      if (nom === "moov") {
        // Somme des atomes internes restants, plus l'en-tête.
        let interne = index + 8;
        let cumul = 8;
        while (interne < index + taille) {
          const t =
            ((propre[interne] ?? 0) << 24) |
            ((propre[interne + 1] ?? 0) << 16) |
            ((propre[interne + 2] ?? 0) << 8) |
            (propre[interne + 3] ?? 0);
          expect(t).toBeGreaterThan(0);
          cumul += t;
          interne += t;
        }
        expect(cumul).toBe(taille);
      }
      if (taille <= 0) break;
      index += taille;
    }
    // Et la somme des atomes de premier niveau couvre exactement le fichier.
    expect(index).toBe(propre.length);
  });

  it("recopie sans broncher un fichier incohérent", () => {
    const casse = octets(...u32(9999), "moov", 0x01, 0x02);
    expect(() => nettoyerMp4(casse)).not.toThrow();
    expect(nettoyerMp4(casse).length).toBe(casse.length);
  });
});

describe("point d'entrée", () => {
  it("dit clairement qu'il n'a pas nettoyé un format inconnu", () => {
    const heic = octets("ftypheic-mais-pas-au-bon-endroit");
    const resultat = nettoyer(heic);
    expect(resultat.nettoye).toBe(false);
    expect(resultat.format).toBe("inconnu");
    expect(resultat.octets).toEqual(heic);
  });

  it("marque nettoyé ce qu'il a réellement traité", () => {
    expect(nettoyer(octets(0xff, 0xd8, 0xff, 0xda, 0x00, 0x02)).nettoye).toBe(true);
  });
});
