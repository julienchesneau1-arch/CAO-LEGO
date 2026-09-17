import { describe, expect, it } from "vitest";
import { construireIcs } from "@/lib/ics";

const MAINTENANT = new Date("2026-09-17T10:00:00Z");
const OPTIONS = { domaine: "exemple.test", maintenant: MAINTENANT };

describe("fichier .ics", () => {
  it("termine chaque ligne par CRLF, comme l'exige la norme", () => {
    const ics = construireIcs(
      [
        {
          uid: "moment-01@exemple.test",
          titre: "L'Éclat",
          debut: new Date("2028-06-03T09:00:00Z"),
          fin: new Date("2028-06-03T10:30:00Z"),
        },
      ],
      OPTIONS,
    );
    expect(ics.startsWith("BEGIN:VCALENDAR\r\n")).toBe(true);
    expect(ics.endsWith("END:VCALENDAR\r\n")).toBe(true);
    expect(ics.split("\r\n").length).toBeGreaterThan(8);
    expect(ics).not.toMatch(/[^\r]\n/);
  });

  it("échappe les virgules, points-virgules et retours à la ligne", () => {
    const ics = construireIcs(
      [
        {
          uid: "u@exemple.test",
          titre: "Dîner, puis fête ; à confirmer",
          debut: new Date("2028-06-03T19:30:00Z"),
          fin: null,
          description: "Deux lignes\nici",
        },
      ],
      OPTIONS,
    );
    expect(ics).toContain("SUMMARY:Dîner\\, puis fête \; à confirmer");
    expect(ics).toContain("DESCRIPTION:Deux lignes\\nici");
  });

  it("plie les lignes trop longues sans couper un caractère accentué", () => {
    const ics = construireIcs(
      [
        {
          uid: "u@exemple.test",
          titre: "é".repeat(80),
          debut: new Date("2028-06-03T19:30:00Z"),
          fin: null,
        },
      ],
      OPTIONS,
    );
    for (const ligne of ics.split("\r\n")) {
      expect(Buffer.from(ligne, "utf8").length).toBeLessThanOrEqual(75);
    }
    // Le texte reste intact une fois déplié.
    const deplie = ics.replace(/\r\n /g, "");
    expect(deplie).toContain(`SUMMARY:${"é".repeat(80)}`);
  });

  it("garde des identifiants stables : un second téléchargement met à jour", () => {
    const premier = construireIcs(
      [{ uid: "moment-03@exemple.test", titre: "La Rencontre", debut: MAINTENANT, fin: null }],
      OPTIONS,
    );
    const second = construireIcs(
      [{ uid: "moment-03@exemple.test", titre: "La Rencontre", debut: MAINTENANT, fin: null }],
      OPTIONS,
    );
    expect(premier).toEqual(second);
    expect(premier).toContain("UID:moment-03@exemple.test");
  });

  it("écrit une journée entière quand l'heure n'est pas connue", () => {
    const ics = construireIcs(
      [
        {
          uid: "mariage@exemple.test",
          titre: "Mariage de Julien & Lauriane",
          debut: new Date("2028-06-03T00:00:00+02:00"),
          fin: null,
          journeeEntiere: true,
        },
      ],
      OPTIONS,
    );
    expect(ics).toContain("DTSTART;VALUE=DATE:20280603");
    expect(ics).toContain("DTEND;VALUE=DATE:20280604");
    expect(ics).not.toContain("DTSTART:2028");
  });

  it("ne produit aucun événement pour une liste vide, mais reste un calendrier valide", () => {
    const ics = construireIcs([], OPTIONS);
    expect(ics).toContain("BEGIN:VCALENDAR");
    expect(ics).not.toContain("BEGIN:VEVENT");
  });
});
