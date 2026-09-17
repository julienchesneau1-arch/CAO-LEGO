"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Onglet } from "@/lib/navigation";

/**
 * Barre de navigation unique (brief §7). Fixée en bas, atteignable au pouce,
 * cibles de 48 px, onglet courant annoncé aux lecteurs d'écran.
 */
export function Navigation({
  onglets,
  libelles,
}: {
  readonly onglets: ReadonlyArray<Onglet>;
  readonly libelles: Readonly<Record<string, string>>;
}) {
  const chemin = usePathname();
  if (onglets.length === 0) return null;

  return (
    <nav
      aria-label={libelles["navigation"] ?? "Navigation"}
      className="sticky bottom-0 z-40 border-t"
      style={{ borderColor: "var(--filet)", background: "var(--fond)" }}
    >
      <ul className="mx-auto flex max-w-2xl overflow-hidden">
        {onglets.map((onglet) => {
          const actif =
            onglet.chemin === "/" ? chemin === "/" : chemin.startsWith(onglet.chemin);
          return (
            <li key={onglet.cle} className="min-w-0 flex-1">
              <Link
                href={onglet.chemin}
                aria-current={actif ? "page" : undefined}
                className="jl-cible flex flex-col items-center justify-center gap-2 px-1 py-3 text-center"
              >
                <span
                  aria-hidden="true"
                  style={{
                    display: "block",
                    width: "1.5rem",
                    height: "2px",
                    background: actif ? "var(--texte)" : "transparent",
                  }}
                />
                <span className="jl-onglet" style={{ opacity: actif ? 1 : 0.6 }}>
                  {libelles[onglet.cle] ?? onglet.cle}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
