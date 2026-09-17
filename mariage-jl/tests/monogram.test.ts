import { describe, expect, it } from "vitest";
import { MONOGRAMME_TRACES, MONOGRAMME_VIEWBOX } from "@/components/monogram.generated";

describe("monogramme vectorisé", () => {
  it("contient les trois tracés J, & et L", () => {
    expect(MONOGRAMME_TRACES.map((t) => t.lettre)).toEqual(["J", "&", "L"]);
  });

  it("expose des tracés réels et non des textes", () => {
    for (const trace of MONOGRAMME_TRACES) {
      expect(trace.d.startsWith("M")).toBe(true);
      expect(trace.d.length).toBeGreaterThan(50);
    }
  });

  it("déclare une zone de dessin exploitable", () => {
    const parts = MONOGRAMME_VIEWBOX.split(" ").map(Number);
    expect(parts).toHaveLength(4);
    expect(parts.every((n) => Number.isFinite(n))).toBe(true);
    expect(parts[2]).toBeGreaterThan(0);
    expect(parts[3]).toBeGreaterThan(0);
  });
});
