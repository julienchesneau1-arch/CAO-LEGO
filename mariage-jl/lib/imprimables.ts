import { PDFDocument, StandardFonts, rgb, type PDFFont, type PDFPage } from "pdf-lib";
import QRCode from "qrcode";
import { MONOGRAMME_TRACES, MONOGRAMME_VIEWBOX } from "@/components/monogram.generated";

/**
 * Imprimables du jour J (brief §9 et §10).
 *
 * — **Cartes de table** : le plan B imprimé. Si l'application ou le réseau
 *   tombe, personne n'est perdu : la carte porte le QR générique, les cinq
 *   moments, le Wi-Fi et un numéro à appeler.
 * — **Fiche régie** : horaires, contacts, procédures de panne, sur une page.
 *
 * Les deux sont en mode Papier (ivoire et encre), mesuré à 14,57 de
 * contraste : un QR y est lu sans peine et une carte posée sur une nappe
 * reste lisible à la bougie.
 */
const IVOIRE = rgb(0xe9 / 255, 0xe2 / 255, 0xd8 / 255);
const ENCRE = rgb(0x12 / 255, 0x12 / 255, 0x12 / 255);
const A4 = { largeur: 595.28, hauteur: 841.89 };
/** A5 paysage : une carte se plie en deux et tient debout sur une table. */
const A5 = { largeur: 595.28, hauteur: 420.94 };

const [, , LARGEUR_VB, HAUTEUR_VB] = MONOGRAMME_VIEWBOX.split(" ").map(Number);

export type MomentImprime = {
  readonly id: string;
  readonly nom: string;
  readonly heure: string | null;
  readonly lieu: string | null;
};

export type CarteDeTable = {
  readonly table: string;
  readonly prenoms: ReadonlyArray<string>;
};

export type ContactImprime = { readonly role: string; readonly nom: string; readonly telephone: string };

function monogramme(page: PDFPage, x: number, y: number, hauteur: number): void {
  const echelle = hauteur / (HAUTEUR_VB ?? 1);
  for (const trace of MONOGRAMME_TRACES) {
    page.drawSvgPath(trace.d, { x, y, scale: echelle, color: ENCRE });
  }
}

const largeurMonogramme = (hauteur: number): number =>
  hauteur * ((LARGEUR_VB ?? 1) / (HAUTEUR_VB ?? 1));

/**
 * Découpe un texte pour qu'il tienne dans une largeur donnée. Sans cela une
 * adresse longue sortirait de la page — et on ne s'en apercevrait qu'à
 * l'impression, trop tard.
 */
function lignes(texte: string, police: PDFFont, taille: number, largeur: number): string[] {
  const mots = texte.split(/\s+/).filter((mot) => mot !== "");
  const sortie: string[] = [];
  let courante = "";
  for (const mot of mots) {
    const essai = courante === "" ? mot : `${courante} ${mot}`;
    if (police.widthOfTextAtSize(essai, taille) > largeur && courante !== "") {
      sortie.push(courante);
      courante = mot;
    } else {
      courante = essai;
    }
  }
  if (courante !== "") sortie.push(courante);
  return sortie;
}

/** Une carte par table (brief §10), A5 paysage, une page chacune. */
export async function cartesDeTablePdf(
  cartes: ReadonlyArray<CarteDeTable>,
  options: {
    readonly domaine: string;
    readonly moments: ReadonlyArray<MomentImprime>;
    readonly wifi: string | null;
    readonly contact: ContactImprime | null;
    readonly libelles: Readonly<Record<string, string>>;
  },
): Promise<Uint8Array> {
  const document = await PDFDocument.create();
  document.setTitle("Cartes de table — Mariage J&L");

  const titre = await document.embedFont(StandardFonts.TimesRoman);
  const gras = await document.embedFont(StandardFonts.TimesRomanBold);

  const lien = options.domaine === "" ? "" : `https://${options.domaine}/g`;
  const qr =
    lien === ""
      ? undefined
      : await document.embedPng(
          await QRCode.toBuffer(lien, { margin: 0, width: 240, errorCorrectionLevel: "M" }),
        );

  // Une carte vide serait absurde : s'il n'y a pas de table, on imprime une
  // carte générique, qui sert encore de plan B.
  const aImprimer = cartes.length === 0 ? [{ table: "", prenoms: [] }] : cartes;

  for (const carte of aImprimer) {
    const page = document.addPage([A5.largeur, A5.hauteur]);
    page.drawRectangle({ x: 0, y: 0, width: A5.largeur, height: A5.hauteur, color: IVOIRE });

    const hauteurMono = 22;
    monogramme(page, 36, A5.hauteur - 40, hauteurMono);
    page.drawText(options.libelles["signature"] ?? "", {
      x: 36 + largeurMonogramme(hauteurMono) + 12,
      y: A5.hauteur - 46,
      size: 8,
      font: titre,
      color: ENCRE,
    });

    if (carte.table !== "") {
      page.drawText(carte.table, {
        x: 36,
        y: A5.hauteur - 96,
        size: 34,
        font: gras,
        color: ENCRE,
      });
    }

    // Les prénoms de la table, sur deux colonnes si besoin.
    let y = A5.hauteur - 124;
    for (const ligne of lignes(carte.prenoms.join(" · "), titre, 11, A5.largeur - 220)) {
      page.drawText(ligne, { x: 36, y, size: 11, font: titre, color: ENCRE });
      y -= 15;
    }

    // Le programme : c'est lui qui sauve la soirée si l'application tombe.
    y -= 12;
    page.drawText(options.libelles["programme"] ?? "", {
      x: 36,
      y,
      size: 8,
      font: gras,
      color: ENCRE,
    });
    y -= 18;
    for (const moment of options.moments) {
      page.drawText(`${moment.id}  ${moment.nom}`, {
        x: 36,
        y,
        size: 11,
        font: titre,
        color: ENCRE,
      });
      const droite = `${moment.heure ?? options.libelles["heure_inconnue"] ?? ""}${
        moment.lieu === null ? "" : ` · ${moment.lieu}`
      }`;
      page.drawText(droite, { x: 210, y, size: 10, font: titre, color: ENCRE });
      y -= 16;
    }

    // Wi-Fi et numéro : les deux choses qu'on cherche quand rien ne marche.
    y -= 10;
    const bas: string[] = [];
    if (options.wifi !== null && options.wifi !== "") {
      bas.push(`${options.libelles["wifi"] ?? ""} ${options.wifi}`);
    }
    if (options.contact !== null) {
      bas.push(`${options.contact.nom} · ${options.contact.telephone}`);
    }
    for (const ligne of bas) {
      for (const morceau of lignes(ligne, titre, 10, A5.largeur - 220)) {
        page.drawText(morceau, { x: 36, y, size: 10, font: titre, color: ENCRE });
        y -= 14;
      }
    }

    if (qr !== undefined) {
      const taille = 118;
      page.drawImage(qr, {
        x: A5.largeur - taille - 36,
        y: 40,
        width: taille,
        height: taille,
      });
      page.drawText(options.domaine, {
        x: A5.largeur - 36 - titre.widthOfTextAtSize(options.domaine, 8),
        y: 28,
        size: 8,
        font: titre,
        color: ENCRE,
      });
    }
  }

  return document.save();
}

export type FicheRegie = {
  readonly moments: ReadonlyArray<MomentImprime>;
  readonly contacts: ReadonlyArray<ContactImprime>;
  readonly procedures: ReadonlyArray<{ readonly titre: string; readonly texte: string }>;
  readonly wifi: string | null;
  readonly domaine: string;
};

/**
 * Fiche régie imprimable (brief §9) : horaires, contacts, procédures en cas
 * de panne. Une seule page, à garder dans une poche — elle doit marcher
 * quand plus rien d'autre ne marche.
 */
export async function ficheRegiePdf(
  fiche: FicheRegie,
  libelles: Readonly<Record<string, string>>,
): Promise<Uint8Array> {
  const document = await PDFDocument.create();
  document.setTitle("Fiche régie — Mariage J&L");
  document.setSubject("Document interne : ne pas diffuser.");

  const titre = await document.embedFont(StandardFonts.TimesRoman);
  const gras = await document.embedFont(StandardFonts.TimesRomanBold);
  const page = document.addPage([A4.largeur, A4.hauteur]);
  page.drawRectangle({ x: 0, y: 0, width: A4.largeur, height: A4.hauteur, color: IVOIRE });

  const hauteurMono = 24;
  monogramme(page, 48, A4.hauteur - 48, hauteurMono);
  page.drawText(libelles["titre"] ?? "", {
    x: 48 + largeurMonogramme(hauteurMono) + 14,
    y: A4.hauteur - 56,
    size: 10,
    font: gras,
    color: ENCRE,
  });

  let y = A4.hauteur - 100;
  const section = (nom: string): void => {
    y -= 10;
    page.drawText(nom, {
      x: 48,
      y,
      size: 8,
      font: gras,
      color: ENCRE,
    });
    y -= 6;
    page.drawLine({
      start: { x: 48, y },
      end: { x: A4.largeur - 48, y },
      thickness: 0.5,
      color: ENCRE,
    });
    y -= 18;
  };

  section(libelles["horaires"] ?? "");
  for (const moment of fiche.moments) {
    page.drawText(`${moment.id}  ${moment.nom}`, { x: 48, y, size: 12, font: titre, color: ENCRE });
    page.drawText(moment.heure ?? libelles["heure_inconnue"] ?? "", {
      x: 240,
      y,
      size: 12,
      font: gras,
      color: ENCRE,
    });
    if (moment.lieu !== null) {
      page.drawText(moment.lieu, { x: 320, y, size: 11, font: titre, color: ENCRE });
    }
    y -= 18;
  }

  section(libelles["contacts"] ?? "");
  if (fiche.contacts.length === 0) {
    page.drawText(libelles["sans_contact"] ?? "", { x: 48, y, size: 11, font: titre, color: ENCRE });
    y -= 18;
  }
  for (const contact of fiche.contacts) {
    page.drawText(`${contact.role} · ${contact.nom}`, {
      x: 48,
      y,
      size: 12,
      font: titre,
      color: ENCRE,
    });
    page.drawText(contact.telephone, { x: 320, y, size: 12, font: gras, color: ENCRE });
    y -= 18;
  }

  if (fiche.wifi !== null && fiche.wifi !== "") {
    section(libelles["wifi"] ?? "");
    for (const ligne of lignes(fiche.wifi, titre, 11, A4.largeur - 96)) {
      page.drawText(ligne, { x: 48, y, size: 11, font: titre, color: ENCRE });
      y -= 15;
    }
  }

  section(libelles["procedures"] ?? "");
  for (const procedure of fiche.procedures) {
    page.drawText(procedure.titre, { x: 48, y, size: 12, font: gras, color: ENCRE });
    y -= 16;
    for (const ligne of lignes(procedure.texte, titre, 11, A4.largeur - 96)) {
      page.drawText(ligne, { x: 48, y, size: 11, font: titre, color: ENCRE });
      y -= 14;
    }
    y -= 8;
  }

  if (fiche.domaine !== "") {
    page.drawText(`${fiche.domaine}/g`, {
      x: 48,
      y: 40,
      size: 9,
      font: titre,
      color: ENCRE,
    });
  }

  return document.save();
}
