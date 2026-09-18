import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Client } from "pg";

/**
 * Photos et vidéos contre un vrai PostgreSQL et un vrai disque. Ce qui est
 * vérifié ici est ce que le brief promet aux invités : rien n'est stocké
 * sans consentement, rien n'est stocké géolocalisé, une demande de retrait
 * masque immédiatement, et un média confié aux mariés ne fuit pas.
 */
const RACINE = join(import.meta.dirname, "..");
const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = "jl_medias_test";
const URL_BASE = new URL(`/${BASE}`, URL_ADMIN).href;

let client: Client | undefined;
let indisponible: string | undefined;
let medias: typeof import("@/lib/medias") | undefined;
let dossier = "";
let foyerA = "";
let foyerB = "";

/** JPEG minimal mais structurellement vrai, avec un APP1 « Exif » géolocalisé. */
function jpegAvecGps(): Uint8Array {
  const exif = "Exif\0\0GPSLatitude47.1234GPSLongitude0.4321";
  const octets: number[] = [0xff, 0xd8];
  octets.push(0xff, 0xe1, ((exif.length + 2) >> 8) & 0xff, (exif.length + 2) & 0xff);
  for (const caractere of exif) octets.push(caractere.charCodeAt(0));
  octets.push(0xff, 0xdb, 0x00, 0x05, 0x00, 0x01, 0x02);
  octets.push(0xff, 0xda, 0x00, 0x04, 0x01, 0x02, 0x03, 0x04, 0x05);
  return new Uint8Array(octets);
}

const HEIC = new Uint8Array([...Buffer.from("ftypheic-non-nettoyable", "latin1")]);

beforeAll(async () => {
  const gestion = new Client({ connectionString: URL_ADMIN });
  try {
    await gestion.connect();
  } catch (erreur) {
    indisponible = `PostgreSQL injoignable : ${(erreur as Error).message}`;
    if (process.env["JL_REQUIRE_DB"] === "1") throw new Error(indisponible);
    return;
  }
  await gestion.query(`drop database if exists ${BASE}`);
  await gestion.query(`create database ${BASE}`);
  await gestion.end();

  client = new Client({ connectionString: URL_BASE });
  await client.connect();
  for (const fichier of [
    join(RACINE, "supabase", "tests", "00_compat_local.sql"),
    ...readdirSync(join(RACINE, "supabase", "migrations"))
      .filter((f) => f.endsWith(".sql"))
      .sort()
      .map((f) => join(RACINE, "supabase", "migrations", f)),
  ]) {
    await client.query(readFileSync(fichier, "utf8"));
  }

  const empreinte = (secret: string): Buffer =>
    createHash("sha256").update(secret).digest();
  for (const [nom, jeton] of [
    ["Foyer A", "jeton-a"],
    ["Foyer B", "jeton-b"],
  ] as const) {
    const { rows } = await client.query<{ id: string }>(
      `insert into public.households (label_public, token_sha256, backup_code_sha256)
       values ($1, $2, $3) returning id`,
      [nom, empreinte(jeton), empreinte(`${jeton}-code`)],
    );
    if (nom === "Foyer A") foyerA = rows[0]?.id ?? "";
    else foyerB = rows[0]?.id ?? "";
  }

  dossier = mkdtempSync(join(tmpdir(), "jl-medias-"));
  process.env["JL_DATABASE_URL"] = URL_BASE;
  process.env["JL_MEDIAS_DIR"] = dossier;
  medias = await import("@/lib/medias");
}, 60_000);

afterAll(async () => {
  await client?.end();
  if (dossier !== "") rmSync(dossier, { recursive: true, force: true });
});

const decrire = () => (indisponible ? describe.skip : describe);

decrire()("consentement au premier envoi", () => {
  it("refuse un envoi tant que le foyer n'a pas donné son accord", async () => {
    const resultat = await medias!.enregistrerMedia({
      foyer: foyerA,
      momentId: "03",
      mime: "image/jpeg",
      octets: jpegAvecGps(),
    });
    expect(resultat).toEqual({ refus: "sans_consentement" });
    const { rows } = await client!.query<{ n: number }>("select count(*)::int as n from public.media");
    expect(Number(rows[0]?.n)).toBe(0);
  });

  it("enregistre la version du texte accepté", async () => {
    await medias!.accorderConsentementMedias(foyerA, "invites");
    const { rows } = await client!.query<{ consent_text_version: string }>(
      "select consent_text_version from public.media_consent where household_id = $1",
      [foyerA],
    );
    expect(rows[0]?.consent_text_version).toBe(medias!.VERSION_CONSENTEMENT_MEDIAS);
  });

  it("retirer l'accord arrête les envois suivants sans effacer le passé", async () => {
    const premier = await medias!.enregistrerMedia({
      foyer: foyerA,
      momentId: "03",
      mime: "image/jpeg",
      octets: jpegAvecGps(),
    });
    expect("id" in premier).toBe(true);

    await medias!.retirerConsentementMedias(foyerA);
    const apres = await medias!.enregistrerMedia({
      foyer: foyerA,
      momentId: "03",
      mime: "image/jpeg",
      octets: jpegAvecGps(),
    });
    expect(apres).toEqual({ refus: "sans_consentement" });

    // Le premier envoi est toujours là : retirer son accord ne réécrit pas
    // le passé, il empêche la suite.
    expect((await medias!.galerie({ foyer: foyerA })).length).toBe(1);
    await medias!.accorderConsentementMedias(foyerA, "invites");
  });
});

decrire()("ce qui est réellement écrit sur le disque", () => {
  it("ne garde aucune position GPS", async () => {
    const resultat = await medias!.enregistrerMedia({
      foyer: foyerA,
      momentId: "04",
      mime: "image/jpeg",
      octets: jpegAvecGps(),
    });
    expect("id" in resultat).toBe(true);
    const id = (resultat as { id: string }).id;

    const { rows } = await client!.query<{ storage_path: string; gps_stripped: boolean }>(
      "select storage_path, gps_stripped from public.media where id = $1",
      [id],
    );
    const chemin = join(dossier, rows[0]?.storage_path ?? "");
    const surDisque = readFileSync(chemin);
    expect(surDisque.includes(Buffer.from("GPSLatitude"))).toBe(false);
    expect(surDisque.includes(Buffer.from("Exif"))).toBe(false);
    // Et l'image reste une image.
    expect(surDisque[0]).toBe(0xff);
    expect(surDisque[1]).toBe(0xd8);
    expect(rows[0]?.gps_stripped).toBe(true);
  });

  /**
   * Le point de principe : un format que le serveur ne sait pas nettoyer est
   * **refusé**, pas stocké en espérant que personne ne regarde.
   */
  it("refuse un fichier dont il ne sait pas retirer les métadonnées", async () => {
    const resultat = await medias!.enregistrerMedia({
      foyer: foyerA,
      momentId: "04",
      mime: "image/jpeg",
      octets: HEIC,
    });
    expect(resultat).toEqual({ refus: "metadonnees" });
  });

  it("refuse un type qui n'est pas une photo ni une vidéo", async () => {
    expect(
      await medias!.enregistrerMedia({
        foyer: foyerA,
        momentId: null,
        mime: "application/pdf",
        octets: jpegAvecGps(),
      }),
    ).toEqual({ refus: "type_refuse" });
  });

  it("refuse un fichier plus lourd que la limite", async () => {
    const enorme = new Uint8Array(medias!.octetsMax() + 1);
    enorme[0] = 0xff;
    enorme[1] = 0xd8;
    expect(
      await medias!.enregistrerMedia({
        foyer: foyerA,
        momentId: null,
        mime: "image/jpeg",
        octets: enorme,
      }),
    ).toEqual({ refus: "trop_gros" });
  });
});

decrire()("galerie et filtres", () => {
  it("filtre par moment", async () => {
    const parMoment = await medias!.galerie({ momentId: "04", foyer: foyerA });
    expect(parMoment.length).toBeGreaterThan(0);
    expect(parMoment.every((media) => media.moment_id === "04")).toBe(true);
  });

  it("« mes souvenirs » ne montre que ceux du foyer", async () => {
    await medias!.accorderConsentementMedias(foyerB, "invites");
    await medias!.enregistrerMedia({
      foyer: foyerB,
      momentId: "04",
      mime: "image/jpeg",
      octets: jpegAvecGps(),
    });

    const aVu = await medias!.galerie({ foyer: foyerA, mesMedias: true });
    expect(aVu.every((media) => media.household_id === foyerA)).toBe(true);
    const bVu = await medias!.galerie({ foyer: foyerB, mesMedias: true });
    expect(bVu.every((media) => media.household_id === foyerB)).toBe(true);
    expect(aVu.length).toBeGreaterThan(0);
    expect(bVu.length).toBe(1);
  });

  it("sans foyer reconnu, « mes souvenirs » ne montre rien", async () => {
    expect(await medias!.galerie({ mesMedias: true })).toEqual([]);
  });
});

decrire()("visibilité « aux mariés seulement »", () => {
  let confie = "";

  it("n'apparaît pas dans la galerie des autres foyers", async () => {
    await medias!.accorderConsentementMedias(foyerB, "maries");
    const resultat = await medias!.enregistrerMedia({
      foyer: foyerB,
      momentId: "05",
      mime: "image/jpeg",
      octets: jpegAvecGps(),
    });
    confie = (resultat as { id: string }).id;

    const vuParA = await medias!.galerie({ foyer: foyerA });
    expect(vuParA.some((media) => media.id === confie)).toBe(false);
    // Mais le foyer qui l'a envoyé le revoit, pour pouvoir le retirer.
    const vuParB = await medias!.galerie({ foyer: foyerB });
    expect(vuParB.some((media) => media.id === confie)).toBe(true);
  });

  it("ne se télécharge pas avec un simple identifiant", async () => {
    expect(await medias!.octetsDuMedia(confie, { foyer: foyerA })).toBeUndefined();
    expect(await medias!.octetsDuMedia(confie, {})).toBeUndefined();
    // Les mariés et le foyer d'origine, oui.
    expect(await medias!.octetsDuMedia(confie, { maries: true })).toBeDefined();
    expect(await medias!.octetsDuMedia(confie, { foyer: foyerB })).toBeDefined();
  });

  it("apparaît dans la galerie des mariés", async () => {
    const vuParLesMaries = await medias!.galerie({ pourLesMaries: true });
    expect(vuParLesMaries.some((media) => media.id === confie)).toBe(true);
  });
});

decrire()("demande de retrait", () => {
  it("masque immédiatement, avant toute relecture", async () => {
    const envoi = await medias!.enregistrerMedia({
      foyer: foyerA,
      momentId: "03",
      mime: "image/jpeg",
      octets: jpegAvecGps(),
    });
    const id = (envoi as { id: string }).id;

    expect(await medias!.demanderRetrait(id, foyerB, "J’apparais dessus.")).toBe(true);

    // Masquée pour tout le monde, y compris pour le foyer qui l'a envoyée.
    expect((await medias!.galerie({ foyer: foyerA })).some((m) => m.id === id)).toBe(false);
    expect(await medias!.octetsDuMedia(id, { maries: true })).toBeUndefined();

    const signales = await medias!.signalements();
    expect(signales.some((signalement) => signalement.media_id === id)).toBe(true);
  });

  it("ne signale rien pour un identifiant inconnu", async () => {
    expect(
      await medias!.demanderRetrait("00000000-0000-0000-0000-000000000000", foyerA, null),
    ).toBe(false);
  });

  /**
   * Une décision prise dans l'urgence d'une soirée doit pouvoir se défaire :
   * le fichier n'est pas supprimé, seulement masqué.
   */
  it("se défait : la régie peut rendre la photo visible", async () => {
    const signale = (await medias!.signalements())[0];
    expect(signale).toBeDefined();
    await medias!.masquer(signale!.media_id, false);
    expect(await medias!.octetsDuMedia(signale!.media_id, { maries: true })).toBeDefined();
    await medias!.masquer(signale!.media_id, true);
  });

  it("classe un signalement sans le rouvrir", async () => {
    const signale = (await medias!.signalements())[0];
    await medias!.resoudreSignalement(signale!.id);
    const apres = (await medias!.signalements()).find((s) => s.id === signale!.id);
    expect(apres?.resolved_at).not.toBeNull();
  });
});

decrire()("« j'aime » privé", () => {
  it("se pose, se retire, et n'est jamais compté à l'écran", async () => {
    const visible = (await medias!.galerie({ foyer: foyerA }))[0];
    expect(visible).toBeDefined();

    expect(await medias!.basculerSignal(visible!.id, foyerA)).toBe(true);
    expect((await medias!.signauxDuFoyer(foyerA)).has(visible!.id)).toBe(true);
    expect(await medias!.basculerSignal(visible!.id, foyerA)).toBe(false);
    expect((await medias!.signauxDuFoyer(foyerA)).has(visible!.id)).toBe(false);
  });

  it("n'est jamais exposé par la galerie : aucun champ de comptage", async () => {
    const liste = await medias!.galerie({ foyer: foyerA });
    for (const media of liste) {
      expect(Object.keys(media)).not.toContain("aimes");
      expect(Object.keys(media)).not.toContain("count");
    }
  });
});
