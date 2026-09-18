import { describe, expect, it } from "vitest";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { crc32, nomSur, zip } from "@/lib/zip";

/**
 * Archive ZIP écrite à la main (brief §8.11). Un test qui se contente de
 * relire sa propre écriture ne prouve rien : ce qui compte est qu'un vrai
 * décompresseur ouvre l'archive et retrouve les octets exacts. On se sert
 * donc de `unzip` quand il est là, et on vérifie la structure sinon.
 */
const texte = (valeur: string): Uint8Array => new TextEncoder().encode(valeur);

const unzipDisponible = (): boolean => {
  try {
    execFileSync("unzip", ["-v"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
};

describe("CRC-32", () => {
  /** Valeurs de référence du standard : si elles bougent, tout est faux. */
  it("donne les valeurs connues du standard", () => {
    expect(crc32(texte(""))).toBe(0);
    expect(crc32(texte("a"))).toBe(0xe8b7be43);
    expect(crc32(texte("123456789"))).toBe(0xcbf43926);
    expect(crc32(texte("The quick brown fox jumps over the lazy dog"))).toBe(0x414fa339);
  });
});

describe("noms de fichiers", () => {
  /**
   * Un `..` dans un nom d'entrée est une vieille attaque toujours efficace :
   * certains décompresseurs écrivent alors hors du dossier choisi.
   */
  it("refuse de sortir du dossier", () => {
    expect(nomSur("../../etc/passwd")).toBe("etc/passwd");
    expect(nomSur("/absolu/photo.jpg")).toBe("absolu/photo.jpg");
    expect(nomSur("./a/./b.jpg")).toBe("a/b.jpg");
    expect(nomSur("..")).toBe("fichier");
  });

  it("remplace les caractères que Windows refuse, sans rendre illisible", () => {
    expect(nomSur("photo:1.jpg")).toBe("photo-1.jpg");
    expect(nomSur('a"b?c*.jpg')).toBe("a-b-c-.jpg");
  });

  it("garde les accents, qui sont parfaitement valables en UTF-8", () => {
    expect(nomSur("Chloé — été.jpg")).toBe("Chloé — été.jpg");
  });
});

describe("archive", () => {
  it("commence par la signature d'un fichier ZIP", () => {
    const archive = zip([{ nom: "a.txt", octets: texte("bonjour") }]);
    expect([...archive.subarray(0, 4)]).toEqual([0x50, 0x4b, 0x03, 0x04]);
  });

  it("se termine par le répertoire central, avec le bon nombre d'entrées", () => {
    const archive = zip([
      { nom: "a.txt", octets: texte("un") },
      { nom: "b.txt", octets: texte("deux") },
    ]);
    const fin = archive.subarray(archive.length - 22);
    expect([...fin.subarray(0, 4)]).toEqual([0x50, 0x4b, 0x05, 0x06]);
    expect(fin[8]! | (fin[9]! << 8)).toBe(2);
  });

  it("rend les noms uniques plutôt que d'écraser en silence", () => {
    const archive = zip([
      { nom: "photo.jpg", octets: texte("un") },
      { nom: "photo.jpg", octets: texte("deux") },
      { nom: "photo.jpg", octets: texte("trois") },
    ]);
    const contenu = Buffer.from(archive).toString("latin1");
    expect(contenu).toContain("photo.jpg");
    expect(contenu).toContain("photo-2.jpg");
    expect(contenu).toContain("photo-3.jpg");
  });

  it("produit une archive vide valable", () => {
    const archive = zip([]);
    expect(archive.length).toBe(22);
    expect([...archive.subarray(0, 4)]).toEqual([0x50, 0x4b, 0x05, 0x06]);
  });
});

/**
 * Le test qui compte : un vrai décompresseur ouvre l'archive et retrouve les
 * octets exacts, y compris pour un fichier binaire et un nom accentué.
 */
describe.skipIf(!unzipDisponible())("relue par un vrai décompresseur", () => {
  it("rend exactement ce qu'on lui a donné", () => {
    const binaire = new Uint8Array(1024);
    for (let index = 0; index < binaire.length; index += 1) binaire[index] = (index * 7) % 256;

    const archive = zip([
      { nom: "souvenirs/Chloé.txt", octets: texte("Un mot avec des accents : été, Noël.") },
      { nom: "souvenirs/binaire.dat", octets: binaire },
      { nom: "vide.txt", octets: new Uint8Array(0) },
    ]);

    const dossier = mkdtempSync(join(tmpdir(), "jl-zip-"));
    try {
      const chemin = join(dossier, "archive.zip");
      writeFileSync(chemin, archive);

      // `unzip -t` vérifie chaque CRC : c'est lui qui juge notre écriture.
      const controle = execFileSync("unzip", ["-t", chemin], { encoding: "utf8" });
      expect(controle).toContain("No errors detected");

      execFileSync("unzip", ["-q", chemin, "-d", join(dossier, "sortie")]);
      const sortie = join(dossier, "sortie");
      expect(readdirSync(sortie).sort()).toEqual(["souvenirs", "vide.txt"]);
      expect(readFileSync(join(sortie, "souvenirs", "Chloé.txt"), "utf8")).toBe(
        "Un mot avec des accents : été, Noël.",
      );
      expect(new Uint8Array(readFileSync(join(sortie, "souvenirs", "binaire.dat")))).toEqual(
        binaire,
      );
      expect(readFileSync(join(sortie, "vide.txt")).length).toBe(0);
    } finally {
      rmSync(dossier, { recursive: true, force: true });
    }
  });
});
