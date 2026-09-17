import type { Metadata, Viewport } from "next";
import { Bodoni_Moda, Cormorant_Garamond } from "next/font/google";
import { cookies } from "next/headers";
import { COOKIE_LANGUE, LANGUE_DEFAUT, estLangue } from "@/lib/i18n";
import "./globals.css";

/** Polices auto-hébergées par next/font : aucune requête vers Google à l'exécution. */
const bodoni = Bodoni_Moda({
  subsets: ["latin"],
  axes: ["opsz"],
  style: ["normal", "italic"],
  display: "swap",
  variable: "--police-titre",
});

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500"],
  style: ["normal", "italic"],
  display: "swap",
  variable: "--police-texte",
});

export const metadata: Metadata = {
  title: "J & L — 03 · 06 · 2028",
  description: "Julien & Lauriane — 3 juin 2028, Domaine de Roiffé.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#080808",
  width: "device-width",
  initialScale: 1,
};

/**
 * Applique les préférences de confort avant le premier rendu, pour éviter
 * qu'un invité voie l'écran changer sous ses yeux.
 */
const SCRIPT_CONFORT = `try{var p=JSON.parse(localStorage.getItem("jl_confort")||"{}");var r=document.documentElement;
if(p.taille)r.dataset.taille=p.taille;if(p.papier)r.dataset.papier=p.papier;if(p.mouvement)r.dataset.mouvement=p.mouvement;}catch(e){}`;

export default async function RacineLayout({
  children,
}: {
  readonly children: React.ReactNode;
}) {
  const magasin = await cookies();
  const valeur = magasin.get(COOKIE_LANGUE)?.value;
  const langue = estLangue(valeur) ? valeur : LANGUE_DEFAUT;

  return (
    <html lang={langue} data-taille="normale" data-papier="non" data-mouvement="normal">
      <head>
        <script dangerouslySetInnerHTML={{ __html: SCRIPT_CONFORT }} />
      </head>
      <body className={`${bodoni.variable} ${cormorant.variable}`} data-vignette="oui">
        {children}
      </body>
    </html>
  );
}
