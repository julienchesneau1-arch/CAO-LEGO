import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { Client } from "pg";

/**
 * Édition des contenus depuis l'espace des mariés, contre un vrai PostgreSQL.
 * Ce qui est vérifié ici est ce dont dépend l'invité : un horaire saisi à
 * 15:30 s'affiche à 15:30 au domaine, un champ vidé redevient une attente
 * explicite, et un contenu dépublié disparaît de la FAQ.
 */
const RACINE = join(import.meta.dirname, "..");
const URL_ADMIN =
  process.env["JL_TEST_DATABASE_URL"] ?? "postgres://postgres@127.0.0.1:55432/postgres";
const BASE = "jl_contenus_test";
const URL_BASE = new URL(`/${BASE}`, URL_ADMIN).href;

let client: Client | undefined;
let indisponible: string | undefined;
let admin: typeof import("@/lib/contenus-admin") | undefined;
let lecture: typeof import("@/lib/contenus") | undefined;
let momentsLus: typeof import("@/lib/moments") | undefined;

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

  process.env["JL_DATABASE_URL"] = URL_BASE;
  admin = await import("@/lib/contenus-admin");
  lecture = await import("@/lib/contenus");
  momentsLus = await import("@/lib/moments");
}, 60_000);

afterAll(async () => {
  await client?.end();
});

const decrire = () => (indisponible ? describe.skip : describe);

const VIDE = {
  place: null,
  ambience_fr: null,
  ambience_en: null,
  detail_fr: null,
  detail_en: null,
} as const;

decrire()("horaires des moments", () => {
  it("relit exactement l'heure saisie, au fuseau du domaine", async () => {
    await admin!.enregistrerMoment("02", {
      ...VIDE,
      debut: "15:30",
      fin: "16:15",
      place: "La chapelle",
      ambience_fr: "Solennel",
      ambience_en: "Solemn",
    });
    const apres = (await admin!.momentsAdmin("fr")).find((m) => m.id === "02");
    expect(apres?.debut).toBe("15:30");
    expect(apres?.fin).toBe("16:15");
    expect(apres?.place).toBe("La chapelle");
    expect(apres?.ambience_en).toBe("Solemn");
  });

  it("affiche l'heure du domaine à l'invité, quel que soit le fuseau du serveur", async () => {
    const moment = (await momentsLus!.moments()).find((m) => m.id === "02");
    expect(momentsLus!.heure(moment?.starts_at ?? null, "fr")).toBe("15:30");
  });

  /**
   * « La Nuit » finit après minuit. Sans ce calcul, la fin tomberait la
   * veille du mariage et l'agenda exporté serait absurde.
   */
  it("place au lendemain une fin d'après minuit", async () => {
    await admin!.enregistrerMoment("05", { ...VIDE, debut: "22:00", fin: "03:00" });
    const { rows } = await client!.query<{ duree: string }>(
      `select (ends_at - starts_at)::text as duree from public.moments where id = '05'`,
    );
    expect(rows[0]?.duree).toBe("05:00:00");
  });

  it("garde le décalage de la régie par-dessus l'horaire saisi", async () => {
    await client!.query("update public.moments set shift_minutes = 20 where id = '02'");
    const moment = (await momentsLus!.moments()).find((m) => m.id === "02");
    expect(momentsLus!.heure(moment?.starts_at ?? null, "fr")).toBe("15:50");
    // L'écran de saisie montre toujours l'heure de référence, pas la décalée.
    expect((await admin!.momentsAdmin("fr")).find((m) => m.id === "02")?.debut).toBe("15:30");
    await client!.query("update public.moments set shift_minutes = 0 where id = '02'");
  });

  it("revient à l'attente explicite quand les champs sont vidés", async () => {
    await admin!.enregistrerMoment("02", { ...VIDE, debut: null, fin: null });
    const apres = (await admin!.momentsAdmin("fr")).find((m) => m.id === "02");
    expect(apres?.debut).toBeNull();
    expect(apres?.place).toBeNull();
    await admin!.enregistrerMoment("02", { ...VIDE, debut: "15:30", fin: "16:15" });
  });
});

decrire()("blocs de texte", () => {
  it("écrit les deux langues d'un seul geste", async () => {
    await admin!.enregistrerBloc(
      "infos.tenue",
      { texte_fr: "Tenue de ville.", texte_en: "Smart casual.", lien: null },
      "maries@exemple.test",
    );
    expect((await lecture!.contenus("fr"))["infos.tenue"]?.texte).toBe("Tenue de ville.");
    expect((await lecture!.contenus("en"))["infos.tenue"]?.texte).toBe("Smart casual.");
  });

  it("ne garde un lien que sur les blocs qui en affichent un", async () => {
    await admin!.enregistrerBloc(
      "infos.liste_mariage",
      { texte_fr: "Chez notre caviste.", texte_en: "At our wine merchant.", lien: "https://exemple.test/liste" },
      "maries@exemple.test",
    );
    await admin!.enregistrerBloc(
      "infos.tenue",
      { texte_fr: "Tenue de ville.", texte_en: "Smart casual.", lien: "https://exemple.test/ignore" },
      "maries@exemple.test",
    );
    const fr = await lecture!.contenus("fr");
    expect(fr["infos.liste_mariage"]?.lien).toBe("https://exemple.test/liste");
    expect(fr["infos.tenue"]?.lien).toBeNull();
  });

  it("note qui a écrit, pour que la relecture sache à qui parler", async () => {
    const { rows } = await client!.query<{ updated_by: string }>(
      `select updated_by from public.content_blocks where key = 'infos.tenue' and locale = 'en'`,
    );
    expect(rows[0]?.updated_by).toBe("maries@exemple.test");
  });
});

decrire()("FAQ", () => {
  it("enregistre une réponse et la sert à l'invité", async () => {
    const question = (await admin!.faqAdmin())[0]!;
    await admin!.enregistrerFaq(question.id, {
      question_fr: question.question_fr,
      question_en: question.question_en,
      answer_fr: "Dès 14 h, jusqu’au bout de la nuit.",
      answer_en: "From 2 pm until the end of the night.",
      published: true,
      sort_order: question.sort_order,
    });
    const servie = (await lecture!.faq("fr")).find((q) => q.id === question.id);
    expect(servie?.reponse).toBe("Dès 14 h, jusqu’au bout de la nuit.");
  });

  it("retire de la FAQ une question dépubliée", async () => {
    const question = (await admin!.faqAdmin())[0]!;
    await admin!.enregistrerFaq(question.id, { ...question, published: false });
    expect((await lecture!.faq("fr")).some((q) => q.id === question.id)).toBe(false);
    await admin!.enregistrerFaq(question.id, { ...question, published: true });
  });

  it("ajoute puis supprime une question", async () => {
    const avant = (await admin!.faqAdmin()).length;
    const id = await admin!.ajouterFaq({
      question_fr: "Peut-on venir la veille ?",
      question_en: "May we arrive the day before?",
      answer_fr: "Oui.",
      answer_en: "Yes.",
      published: true,
      sort_order: 99,
    });
    expect(id).toBeTypeOf("string");
    expect((await admin!.faqAdmin()).length).toBe(avant + 1);
    await admin!.supprimerFaq(id as string);
    expect((await admin!.faqAdmin()).length).toBe(avant);
  });
});

decrire()("hébergements", () => {
  it("ajoute, relit et supprime, avec une distance décimale", async () => {
    const id = await admin!.ajouterHebergement({
      name: "Le Relais",
      distance_km: "3.5",
      price_hint: "90 € la nuit",
      url: "https://exemple.test/relais",
      phone: "+33 5 49 00 00 00",
      shuttle: true,
      sort_order: 1,
    });
    const lits = await lecture!.hebergements();
    const ajoute = lits.find((l) => l.id === id);
    expect(ajoute?.name).toBe("Le Relais");
    expect(ajoute?.distance_km).toBe("3.5");
    expect(ajoute?.shuttle).toBe(true);

    await admin!.enregistrerHebergement(id as string, {
      name: "Le Relais du Domaine",
      distance_km: null,
      price_hint: null,
      url: null,
      phone: null,
      shuttle: false,
      sort_order: 2,
    });
    const modifie = (await lecture!.hebergements()).find((l) => l.id === id);
    expect(modifie?.name).toBe("Le Relais du Domaine");
    expect(modifie?.distance_km).toBeNull();
    expect(modifie?.shuttle).toBe(false);

    await admin!.supprimerHebergement(id as string);
    expect((await lecture!.hebergements()).some((l) => l.id === id)).toBe(false);
  });
});

decrire()("date limite de réponse", () => {
  it("s'enregistre et se relit depuis les paramètres de la journée", async () => {
    const foyer = await import("@/lib/foyer");
    await admin!.enregistrerDateLimite("2028-04-15");
    const apres = await foyer.parametres();
    expect(apres.date_limite_reponse?.toISOString().slice(0, 10)).toBe("2028-04-15");
  });

  it("accepte de redevenir vide tant que rien n'est décidé", async () => {
    const foyer = await import("@/lib/foyer");
    await admin!.enregistrerDateLimite(null);
    expect((await foyer.parametres()).date_limite_reponse).toBeNull();
  });
});

decrire()("reste à compléter", () => {
  it("diminue à mesure que les contenus sont écrits", async () => {
    const avant = await admin!.resteACompleter();
    await admin!.enregistrerBloc(
      "infos.venir",
      { texte_fr: "Par la D147.", texte_en: "Via the D147.", lien: null },
      "maries@exemple.test",
    );
    expect(await admin!.resteACompleter()).toBe(avant - 1);
  });

  it("tombe à zéro quand tout est rempli", async () => {
    await client!.query(
      `update public.content_blocks set value = jsonb_set(value, '{texte}', '"écrit"')`,
    );
    // Les contacts de l'écran Aide comptent aussi : un contact sans numéro
    // est un bouton d'appel qui n'existe pas (brief §0 bis).
    await client!.query(
      `update public.content_blocks set value = jsonb_set(value, '{telephone}', '"+33612345678"')
        where key like 'aide.%'`,
    );
    await client!.query(`update public.faq set answer_fr = 'écrit', answer_en = 'written'`);
    await client!.query(`update public.moments
        set starts_at = (select date_mariage from public.parametres where id = 1) + time '12:00'`);
    await admin!.enregistrerDateLimite("2028-04-15");
    expect(await admin!.resteACompleter()).toBe(0);
  });
});

decrire()("journal d'audit", () => {
  it("garde la trace des modifications sans y écrire d'adresse", async () => {
    const { rows } = await client!.query<{ action: string; target: string; role: string }>(
      "select action, target, role from public.audit_log order by id",
    );
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.map((r) => r.action)).toContain("moment.maj");
    expect(rows.map((r) => r.action)).toContain("bloc.maj");
    for (const ligne of rows) {
      expect(ligne.role).toBe("admin");
      expect(ligne.target).not.toContain("@");
    }
  });
});
