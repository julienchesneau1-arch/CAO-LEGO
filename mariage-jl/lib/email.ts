import "server-only";
import { requete } from "./db";
import { env } from "./env";

/**
 * Envoi d'e-mails (brief §5 et V2).
 *
 * Le prestataire n'est pas choisi (question V1-03) : les e-mails sont donc
 * **mis en file** en base, et un transport les sort de la file. Deux
 * conséquences volontaires :
 * - rien n'est perdu en attendant la décision ;
 * - le jour où le prestataire est choisi, il n'y a qu'une fonction à écrire
 *   ici — aucun écran, aucune logique métier à retoucher.
 *
 * Le transport « console » écrit les e-mails dans la sortie standard : c'est
 * ce qui permet de relire exactement ce qui serait parti.
 */
export type Courriel = {
  readonly id: string;
  readonly destinataire: string;
  readonly sujet: string;
  readonly corps: string;
  readonly tentatives: number;
};

export type Transport = (courriel: Courriel) => Promise<void>;

export async function mettreEnFile(
  destinataire: string,
  sujet: string,
  corps: string,
): Promise<void> {
  await requete(
    "insert into public.emails (destinataire, sujet, corps) values ($1, $2, $3)",
    [destinataire, sujet, corps],
  );
}

export async function filePendante(limite = 50): Promise<ReadonlyArray<Courriel>> {
  return requete<Courriel>(
    `select id, destinataire, sujet, corps, tentatives
       from public.emails
      where statut = 'en_attente' and tentatives < 5
      order by cree_le
      limit $1`,
    [limite],
  );
}

const transportConsole: Transport = async (courriel) => {
  console.log(
    [
      "───────────────────────────────",
      `À      : ${courriel.destinataire}`,
      `Sujet  : ${courriel.sujet}`,
      "",
      courriel.corps,
      "───────────────────────────────",
    ].join("\n"),
  );
};

/**
 * Transport actif. Tant qu'aucun prestataire n'est choisi, c'est la console :
 * les e-mails restent visibles sans jamais partir vers de vraies adresses.
 */
export function transport(): Transport {
  const choix = env().JL_EMAIL_TRANSPORT ?? "console";
  if (choix === "console") return transportConsole;
  throw new Error(
    `Transport e-mail « ${choix} » inconnu : il reste à écrire dans lib/email.ts (question V1-03).`,
  );
}

export type Bilan = { readonly envoyes: number; readonly echecs: number };

/** Vide la file avec le transport actif. Une erreur ne bloque pas les suivants. */
export async function viderFile(transportChoisi: Transport = transport()): Promise<Bilan> {
  const attente = await filePendante();
  let envoyes = 0;
  let echecs = 0;

  for (const courriel of attente) {
    try {
      await transportChoisi(courriel);
      await requete(
        "update public.emails set statut = 'envoye', envoye_le = now() where id = $1",
        [courriel.id],
      );
      envoyes += 1;
    } catch (erreur) {
      const message = erreur instanceof Error ? erreur.message.slice(0, 400) : "erreur inconnue";
      const definitif = courriel.tentatives + 1 >= 5;
      await requete(
        `update public.emails
            set tentatives = tentatives + 1,
                erreur = $2,
                statut = case when $3 then 'echec' else 'en_attente' end
          where id = $1`,
        [courriel.id, message, definitif],
      );
      echecs += 1;
    }
  }

  return { envoyes, echecs };
}
