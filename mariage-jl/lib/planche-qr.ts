import { PDFDocument, StandardFonts, rgb } from "pdf-lib";
import QRCode from "qrcode";
import { MONOGRAMME_TRACES, MONOGRAMME_VIEWBOX } from "@/components/monogram.generated";

export type FoyerAImprimer = {
  readonly label: string;
  readonly jeton: string;
  readonly code: string;
};

/** Mode Papier : le contraste mesuré est de 14,57 — un QR y est lu sans peine. */
const IVOIRE = rgb(0xe9 / 255, 0xe2 / 255, 0xd8 / 255);
const ENCRE = rgb(0x12 / 255, 0x12 / 255, 0x12 / 255);
const A4 = { largeur: 595.28, hauteur: 841.89 };
const COLONNES = 2;
const RANGEES = 4;

/**
 * Planche de QR par foyer (brief §14, imprimable V1).
 *
 * Le jeton n'existe en clair qu'ici, au moment d'imprimer : la base n'en
 * garde que l'empreinte. C'est pourquoi la planche est produite au moment de
 * la création ou de la régénération des accès, et jamais reconstituée.
 *
 * La typographie est celle des polices standard du PDF : Bodoni Moda sera
 * embarquée avec les fichiers de l'imprimeur, en V3, pour les imprimables
 * destinés aux invités (cartes de table, panneaux).
 */
export async function planchePdf(
  foyers: ReadonlyArray<FoyerAImprimer>,
  options: { readonly domaine: string },
): Promise<Uint8Array> {
  const document = await PDFDocument.create();
  document.setTitle("Planche QR — Mariage J&L");
  document.setSubject("Document interne : ne pas diffuser.");

  const titre = await document.embedFont(StandardFonts.TimesRoman);
  const gras = await document.embedFont(StandardFonts.TimesRomanBold);
  const mono = await document.embedFont(StandardFonts.Courier);

  const [, , largeurVb, hauteurVb] = MONOGRAMME_VIEWBOX.split(" ").map(Number);
  const parPage = COLONNES * RANGEES;
  const pages = Math.max(1, Math.ceil(foyers.length / parPage));

  for (let numeroPage = 0; numeroPage < pages; numeroPage += 1) {
    const page = document.addPage([A4.largeur, A4.hauteur]);
    page.drawRectangle({ x: 0, y: 0, width: A4.largeur, height: A4.hauteur, color: IVOIRE });

    // Monogramme vectoriel en tête de planche.
    const hauteurMono = 26;
    const echelle = hauteurMono / (hauteurVb ?? 1);
    for (const trace of MONOGRAMME_TRACES) {
      page.drawSvgPath(trace.d, {
        x: 40,
        y: A4.hauteur - 40,
        scale: echelle,
        color: ENCRE,
      });
    }
    page.drawText("PLANCHE QR — DOCUMENT INTERNE", {
      x: 40 + (largeurVb ?? 0) * echelle + 16,
      y: A4.hauteur - 54,
      size: 9,
      font: gras,
      color: ENCRE,
      opacity: 0.7,
    });
    page.drawText(`${numeroPage + 1} / ${pages}`, {
      x: A4.largeur - 60,
      y: A4.hauteur - 54,
      size: 9,
      font: titre,
      color: ENCRE,
      opacity: 0.7,
    });

    const lot = foyers.slice(numeroPage * parPage, (numeroPage + 1) * parPage);
    const largeurCase = (A4.largeur - 80) / COLONNES;
    const hauteurCase = (A4.hauteur - 140) / RANGEES;

    for (const [index, foyer] of lot.entries()) {
      const colonne = index % COLONNES;
      const rangee = Math.floor(index / COLONNES);
      const x = 40 + colonne * largeurCase;
      const y = A4.hauteur - 100 - (rangee + 1) * hauteurCase;

      page.drawRectangle({
        x,
        y,
        width: largeurCase - 12,
        height: hauteurCase - 12,
        borderColor: ENCRE,
        borderOpacity: 0.2,
        borderWidth: 0.5,
      });

      const lien = `https://${options.domaine}/i/${foyer.jeton}`;
      const png = await QRCode.toBuffer(lien, {
        type: "png",
        margin: 1,
        scale: 8,
        errorCorrectionLevel: "M",
        color: { dark: "#121212ff", light: "#e9e2d8ff" },
      });
      const image = await document.embedPng(png);
      const cote = Math.min(largeurCase - 60, hauteurCase - 90);

      page.drawImage(image, {
        x: x + (largeurCase - 12 - cote) / 2,
        y: y + hauteurCase - 24 - cote,
        width: cote,
        height: cote,
      });

      page.drawText(foyer.label.slice(0, 40), {
        x: x + 14,
        y: y + 46,
        size: 11,
        font: gras,
        color: ENCRE,
      });
      page.drawText("Code de secours", {
        x: x + 14,
        y: y + 30,
        size: 7,
        font: titre,
        color: ENCRE,
        opacity: 0.6,
      });
      page.drawText(foyer.code, {
        x: x + 14,
        y: y + 16,
        size: 13,
        font: mono,
        color: ENCRE,
      });
      page.drawText(options.domaine, {
        x: x + largeurCase - 12 - 14 - titre.widthOfTextAtSize(options.domaine, 7),
        y: y + 16,
        size: 7,
        font: titre,
        color: ENCRE,
        opacity: 0.6,
      });
    }
  }

  return document.save();
}
