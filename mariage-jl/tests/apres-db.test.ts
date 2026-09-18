import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Client } from "pg";

/**
 * La période « Après » (brief §8.11) et la fin de vie des données (§11).
 *
 * Ce qui compte ici : les dates annoncées à l'invité sont **celles des
 * purges**, une archive ne contient que ce que l'invité a le droit de voir,
 * et un fichier dont la ligne a disparu quitte réellement le disque.
 */
const RACINE = join(import.meta.dirname, "..");
const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = "jl_apres_test";
const URL_BASE = new URL(`/${BASE}`, URL_ADMIN).href;

let client: Client | undefined;
let indisponible: string | undefined;
let apres: typeof import("@/lib/apres") | undefined;
let medias: typeof import("@/lib/medias") | undefined;
let dossier = "";
let foyerA = "";
let foyerB = "";

function jpeg(): Uint8Array {
  return new Uint8Array([0xff, 0xd8, 0xff, 0xdb, 0x00, 0x05, 0x00, 0x01, 0x02, 0xff, 0xda, 0x00,
    0x04, 0x01, 0x02, 0x03]);
}

const unzipDisponible = (): boolean => {
  try {
    execFileSync("unzip", ["-v"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
};

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

  for (const [nom, jeton] of [
    ["Foyer A", "jeton-apres-a"],
    ["Foyer B", "jeton-apres-b"],
  ] as const) {
    const { rows } = await client.query<{ id: string }>(
      `insert into public.households (label_public, token_sha256, backup_code_sha256)
       values ($1, $2, $3) returning id`,
      [
        nom,
        createHash("sha256").update(jeton).digest(),
        createHash("sha256").update(`${jeton}-code`).digest(),
      ],
    );
    if (nom === "Foyer A") foyerA = rows[0]?.id ?? "";
    else foyerB = rows[0]?.id ?? "";
  }
  await client.query(
    "insert into public.guests (household_id, first_name, sort_order) values ($1, 'Camille', 0)",
    [foyerA],
  );

  dossier = mkdtempSync(join(tmpdir(), "jl-apres-"));
  process.env["JL_DATABASE_URL"] = URL_BASE;
  process.env["JL_MEDIAS_DIR"] = dossier;
  apres = await import("@/lib/apres");
  medias = await import("@/lib/medias");
}, 60_000);

afterAll(async () => {
  await client?.end();
  if (dossier !== "") rmSync(dossier, { recursive: true, force: true });
});

const decrire = () => (indisponible ? describe.skip : describe);

decrire()("échéances annoncées à l'invité", () => {
  /**
   * Le point de principe : les dates viennent de la base, pas d'un calcul
   * recopié dans l'application. Un écran ne peut donc pas annoncer une date
   * que les purges ne tiendront pas.
   */
  it("sont celles des purges, pas un calcul parallèle", async () => {
    const liste = await apres!.echeances();
    const trouve = (quoi: string): string =>
      liste.find((e) => e.quoi === quoi)!.le.toISOString().slice(0, 10);

    // Le mariage est le 3 juin 2028 (amorcé par la migration de schéma).
    expect(trouve("allergies")).toBe("2028-07-03");
    expect(trouve("reponses")).toBe("2028-09-03");
    expect(trouve("acces")).toBe("2028-09-03");
    expect(trouve("medias")).toBe("2029-06-03");
    expect(trouve("voeux")).toBe("2029-06-03");
  });

  it("suivent la date du mariage si elle change", async () => {
    await client!.query("update public.parametres set date_mariage = date '2030-01-01'");
    expect((await apres!.echeance("medias"))?.toISOString().slice(0, 10)).toBe("2031-01-01");
    await client!.query("update public.parametres set date_mariage = date '2028-06-03'");
  });
});

decrire()("ce que nous détenons", () => {
  it("compte sans recopier les données elles-mêmes", async () => {
    const donnees = await apres!.mesDonnees(foyerA);
    expect(donnees.invites).toBe(1);
    expect(donnees.aRepondu).toBe(false);
    expect(donnees.allergies).toBe(0);
    expect(donnees.souvenirs).toBe(0);
    // Aucun champ ne porte de contenu : ce sont des nombres et des booléens.
    for (const valeur of Object.values(donnees)) {
      expect(["number", "boolean"]).toContain(typeof valeur);
    }
  });

  it("ne mélange pas deux foyers", async () => {
    expect((await apres!.mesDonnees(foyerB)).invites).toBe(0);
  });
});

decrire()("livre d'or", () => {
  it("ne montre que les messages que leur auteur a rendus visibles", async () => {
    await client!.query(
      `insert into public.absent_messages (household_id, body, visibility) values
         ($1, 'Nous pensons à vous.', 'guestbook'),
         ($1, 'Un mot privé.', 'private')`,
      [foyerB],
    );
    const liste = await apres!.livreDOr();
    expect(liste.map((m) => m.body)).toEqual(["Nous pensons à vous."]);
    // Et aucun identifiant de foyer n'en sort.
    expect(Object.keys(liste[0] ?? {}).sort()).toEqual(["body", "created_at", "id"]);
  });
});

decrire()("archive ZIP", () => {
  it("contient les souvenirs visibles de l'invité", async () => {
    await medias!.accorderConsentementMedias(foyerA, "invites");
    await medias!.enregistrerMedia({
      foyer: foyerA,
      momentId: "03",
      mime: "image/jpeg",
      octets: jpeg(),
    });
    await medias!.accorderConsentementMedias(foyerB, "invites");
    await medias!.enregistrerMedia({
      foyer: foyerB,
      momentId: "04",
      mime: "image/jpeg",
      octets: jpeg(),
    });

    const toutes = await apres!.archiveDesSouvenirs({
      foyer: foyerA,
      mesSouvenirs: false,
      prefixe: "souvenirs",
    });
    expect(toutes.nombre).toBe(2);

    const miennes = await apres!.archiveDesSouvenirs({
      foyer: foyerA,
      mesSouvenirs: true,
      prefixe: "mes-souvenirs",
    });
    expect(miennes.nombre).toBe(1);
  });

  /**
   * Une archive ne doit pas devenir une porte dérobée : ce qu'un invité ne
   * voit pas dans la galerie ne doit pas se retrouver dans son ZIP.
   */
  it("n'emporte pas un souvenir confié aux seuls mariés", async () => {
    await medias!.accorderConsentementMedias(foyerB, "maries");
    await medias!.enregistrerMedia({
      foyer: foyerB,
      momentId: "05",
      mime: "image/jpeg",
      octets: jpeg(),
    });

    const vueParA = await apres!.archiveDesSouvenirs({
      foyer: foyerA,
      mesSouvenirs: false,
      prefixe: "souvenirs",
    });
    expect(vueParA.nombre).toBe(2); // toujours deux : le confié n'y est pas

    const vueParB = await apres!.archiveDesSouvenirs({
      foyer: foyerB,
      mesSouvenirs: true,
      prefixe: "mes-souvenirs",
    });
    expect(vueParB.nombre).toBe(2); // B revoit le sien, confié compris
  });

  it("n'emporte plus une photo dont le retrait a été demandé", async () => {
    const liste = await medias!.galerie({ foyer: foyerA });
    const cible = liste.find((m) => m.household_id === foyerA);
    await medias!.demanderRetrait(cible!.id, foyerB, null);

    const apresRetrait = await apres!.archiveDesSouvenirs({
      foyer: foyerA,
      mesSouvenirs: false,
      prefixe: "souvenirs",
    });
    expect(apresRetrait.nombre).toBe(1);
    await medias!.masquer(cible!.id, false);
  });

  it.skipIf(!unzipDisponible())("s'ouvre avec un vrai décompresseur", () => {
    return (async () => {
      const archive = await apres!.archiveDesSouvenirs({
        foyer: foyerA,
        mesSouvenirs: false,
        prefixe: "souvenirs-du-mariage",
      });
      const temporaire = mkdtempSync(join(tmpdir(), "jl-zip-apres-"));
      try {
        const chemin = join(temporaire, "a.zip");
        writeFileSync(chemin, archive.octets);
        const controle = execFileSync("unzip", ["-t", chemin], { encoding: "utf8" });
        expect(controle).toContain("No errors detected");
        // Les noms sont rangés sous un dossier, avec la date et le moment.
        expect(execFileSync("unzip", ["-l", chemin], { encoding: "utf8" })).toContain(
          "souvenirs-du-mariage/",
        );
      } finally {
        rmSync(temporaire, { recursive: true, force: true });
      }
    })();
  });
});

decrire()("fichiers orphelins", () => {
  it("quittent le disque quand leur ligne a disparu", async () => {
    const envoi = await medias!.enregistrerMedia({
      foyer: foyerA,
      momentId: "01",
      mime: "image/jpeg",
      octets: jpeg(),
    });
    const id = (envoi as { id: string }).id;
    const { rows } = await client!.query<{ storage_path: string }>(
      "select storage_path from public.media where id = $1",
      [id],
    );
    const chemin = rows[0]!.storage_path;

    // Tant que la ligne existe, le fichier reste — même si on demande la purge.
    expect(await apres!.supprimerFichiersOrphelins([chemin])).toEqual([]);
    expect(() => readFileSync(join(dossier, chemin))).not.toThrow();

    await client!.query("delete from public.media where id = $1", [id]);
    expect(await apres!.supprimerFichiersOrphelins([chemin])).toEqual([chemin]);
    expect(() => readFileSync(join(dossier, chemin))).toThrow();
  });

  /**
   * Le sens inverse. Une vignette cassée dans la galerie est le symptôme
   * visible d'une ligne sans fichier : elle reste à l'écran de tous les
   * invités jusqu'à ce que quelqu'un le remarque.
   */
  it("et les lignes dont le fichier a disparu s'en vont aussi", async () => {
    const envoi = await medias!.enregistrerMedia({
      foyer: foyerA,
      momentId: "02",
      mime: "image/jpeg",
      octets: jpeg(),
    });
    const id = (envoi as { id: string }).id;
    const { rows } = await client!.query<{ storage_path: string }>(
      "select storage_path from public.media where id = $1",
      [id],
    );

    // Tous les fichiers sont là : rien ne doit disparaître.
    const tous = await client!.query<{ storage_path: string }>(
      "select storage_path from public.media",
    );
    const chemins = tous.rows.map((ligne) => ligne.storage_path);
    expect(await apres!.supprimerLignesSansFichier(chemins)).toBe(0);
    expect((await medias!.galerie({ foyer: foyerA })).some((m) => m.id === id)).toBe(true);

    // Un seul fichier disparaît : une seule ligne part, et pas les autres.
    rmSync(join(dossier, rows[0]!.storage_path), { force: true });
    const restants = chemins.filter((chemin) => chemin !== rows[0]!.storage_path);
    expect(await apres!.supprimerLignesSansFichier(restants)).toBe(1);
    expect((await medias!.galerie({ foyer: foyerA })).some((m) => m.id === id)).toBe(false);
    expect((await medias!.galerie({ foyer: foyerA, pourLesMaries: true })).length).toBe(
      restants.length - (await lignesMasquees()),
    );
  });

  it("ne touche pas à un fichier inconnu de la liste qu'on lui donne", async () => {
    const restants = await medias!.galerie({ foyer: foyerA, pourLesMaries: true });
    expect(restants.length).toBeGreaterThan(0);
    // On ne passe aucun chemin : rien ne doit disparaître.
    expect(await apres!.supprimerFichiersOrphelins([])).toEqual([]);
    expect((await medias!.galerie({ foyer: foyerA, pourLesMaries: true })).length).toBe(
      restants.length,
    );
  });
});

/** Les médias masqués ne sortent pas de la galerie : on les compte à part. */
async function lignesMasquees(): Promise<number> {
  const { rows } = await client!.query<{ n: number }>(
    "select count(*)::int as n from public.media where status <> 'published'",
  );
  return Number(rows[0]?.n ?? 0);
}

decrire()("photos du photographe", () => {
  it("ne demandent aucun consentement et vivent dans leur section", async () => {
    const envoi = await medias!.enregistrerMedia({
      foyer: null,
      momentId: null,
      mime: "image/jpeg",
      octets: jpeg(),
      source: "photographe",
    });
    expect("id" in envoi).toBe(true);

    // Absentes de la galerie des invités…
    const galerieInvites = await medias!.galerie({ foyer: foyerA });
    expect(galerieInvites.some((m) => m.source === "photographe")).toBe(false);

    // …et présentes quand on les demande.
    const duPhotographe = await medias!.galerie({ foyer: foyerA, source: "photographe" });
    expect(duPhotographe).toHaveLength(1);
    expect(duPhotographe[0]?.household_id).toBeNull();
  });

  it("un envoi d'invité sans foyer reste refusé", async () => {
    expect(
      await medias!.enregistrerMedia({
        foyer: null,
        momentId: null,
        mime: "image/jpeg",
        octets: jpeg(),
      }),
    ).toEqual({ refus: "sans_consentement" });
  });
});
