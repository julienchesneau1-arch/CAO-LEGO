import { describe, expect, it } from "vitest";
import {
  cleDebit,
  empreinte,
  genererCodeSecours,
  genererJeton,
  lireSession,
  memeSecret,
  signerSession,
} from "@/lib/acces";

const SECRET = "secret-de-test-suffisamment-long-0123456789";

describe("jetons d'invitation", () => {
  it("fait 32 caractères, sans caractère ambigu", () => {
    const jeton = genererJeton();
    expect(jeton).toHaveLength(32);
    expect(jeton).not.toMatch(/[l01]/);
    expect(jeton).toMatch(/^[a-z2-9]+$/);
  });

  it("ne se répète pas", () => {
    const tirages = new Set(Array.from({ length: 200 }, () => genererJeton()));
    expect(tirages.size).toBe(200);
  });

  it("donne un code de secours de 6 caractères lisibles", () => {
    const code = genererCodeSecours();
    expect(code).toHaveLength(6);
    expect(code).not.toMatch(/[IO01]/);
  });
});

describe("empreintes", () => {
  it("ne conserve jamais le secret en clair", () => {
    const jeton = genererJeton();
    const hache = empreinte(jeton);
    expect(hache).toHaveLength(32);
    expect(hache.toString("hex")).not.toContain(jeton);
  });

  it("ignore la casse et les espaces du code saisi à la main", () => {
    expect(empreinte("abc123").equals(empreinte(" ABC123 "))).toBe(true);
  });

  it("compare à temps constant et refuse les longueurs différentes", () => {
    expect(memeSecret(empreinte("a"), empreinte("a"))).toBe(true);
    expect(memeSecret(empreinte("a"), empreinte("b"))).toBe(false);
    expect(memeSecret(Buffer.from("court"), empreinte("a"))).toBe(false);
  });
});

describe("cookie de foyer signé", () => {
  const session = { foyer: "11111111-1111-1111-1111-111111111111", emis: 1_758_000_000 };

  it("se relit tel quel", () => {
    expect(lireSession(signerSession(session, SECRET), SECRET)).toEqual(session);
  });

  it("refuse une charge modifiée", () => {
    const signe = signerSession(session, SECRET);
    const [charge, signature] = signe.split(".");
    const autre = Buffer.from(
      JSON.stringify({ foyer: "22222222-2222-2222-2222-222222222222", emis: session.emis }),
      "utf8",
    ).toString("base64url");
    expect(charge).not.toBe(autre);
    expect(lireSession(`${autre}.${signature}`, SECRET)).toBeUndefined();
  });

  it("refuse une signature d'un autre secret", () => {
    expect(lireSession(signerSession(session, "un-autre-secret-de-test-0123456789"), SECRET)).toBeUndefined();
  });

  it("refuse une valeur absente ou malformée", () => {
    expect(lireSession(undefined, SECRET)).toBeUndefined();
    expect(lireSession("nimportequoi", SECRET)).toBeUndefined();
    expect(lireSession("a.b", SECRET)).toBeUndefined();
  });
});

describe("limitation de débit", () => {
  it("ne laisse fuir aucune adresse en clair dans la clé", () => {
    const cle = cleDebit("retrouver", "203.0.113.42");
    expect(cle.startsWith("retrouver:")).toBe(true);
    expect(cle).not.toContain("203.0.113");
    expect(cle.length).toBeLessThanOrEqual(34);
  });
});
