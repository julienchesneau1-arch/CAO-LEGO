import "server-only";
import { z } from "zod";
import { requete, transaction, une } from "./db";

/** Régimes proposés : exactement ceux nommés par le brief §8.2. */
export const REGIMES = ["vegetarien", "sans_porc", "sans_alcool"] as const;
export type Regime = (typeof REGIMES)[number];

export const STATUTS = ["yes", "no", "maybe"] as const;
export type Statut = (typeof STATUTS)[number];

export type Invite = {
  readonly id: string;
  readonly first_name: string;
  readonly last_name: string | null;
  readonly is_child: boolean;
  readonly age_years: number | null;
  readonly menu_choice: string | null;
  readonly diet_flags: ReadonlyArray<string>;
  readonly allergies: string | null;
  readonly presences: ReadonlyArray<string>;
};

export type Reponse = {
  readonly statut: Statut;
  readonly verrouillee: boolean;
  readonly song_request: string | null;
  readonly message_to_couple: string | null;
  readonly lodging_note: string | null;
  readonly transport_note: string | null;
} | null;

/** Le formulaire se verrouille après la date limite (brief §8.2). */
export async function reponseVerrouillee(): Promise<boolean> {
  const ligne = await une<{ verrouille: boolean }>(
    `select coalesce(date_limite_reponse < current_date, false) as verrouille
       from public.parametres where id = 1`,
  );
  return ligne?.verrouille ?? false;
}

export async function reponseDuFoyer(foyerId: string): Promise<Reponse> {
  const ligne = await une<{
    status: Statut;
    locked_at: Date | null;
    song_request: string | null;
    message_to_couple: string | null;
    lodging_note: string | null;
    transport_note: string | null;
  }>(
    `select status, locked_at, song_request, message_to_couple, lodging_note, transport_note
       from public.rsvp where household_id = $1`,
    [foyerId],
  );
  if (ligne === undefined) return null;
  return {
    statut: ligne.status,
    verrouillee: ligne.locked_at !== null,
    song_request: ligne.song_request,
    message_to_couple: ligne.message_to_couple,
    lodging_note: ligne.lodging_note,
    transport_note: ligne.transport_note,
  };
}

export async function invitesDuFoyer(foyerId: string): Promise<ReadonlyArray<Invite>> {
  return requete<Invite>(
    `select g.id, g.first_name, g.last_name, g.is_child, g.age_years,
            g.menu_choice, g.diet_flags,
            a.content as allergies,
            coalesce(
              (select array_agg(p.moment_id order by p.moment_id)
                 from public.rsvp_attendance p
                where p.guest_id = g.id and p.attending), '{}'
            ) as presences
       from public.guests g
       left join public.health_allergies a on a.guest_id = g.id
      where g.household_id = $1
      order by g.sort_order, g.first_name`,
    [foyerId],
  );
}

/** Étape 1 : la seule réponse qui compte vraiment, enregistrée en un tap. */
export async function enregistrerStatut(foyerId: string, statut: Statut): Promise<void> {
  await requete(
    `insert into public.rsvp (household_id, status)
     values ($1, $2)
     on conflict (household_id) do update
        set status = excluded.status, updated_at = now()
      where public.rsvp.locked_at is null`,
    [foyerId, statut],
  );
}

export const SchemaDetails = z.object({
  presences: z.record(z.string(), z.array(z.string())),
  menus: z.record(z.string(), z.string().max(120)),
  regimes: z.record(z.string(), z.array(z.enum(REGIMES))),
  allergies: z.record(z.string(), z.string().max(500)),
  consentementAllergies: z.boolean(),
  versionConsentement: z.string().min(1),
  chanson: z.string().max(200).optional(),
  message: z.string().max(2000).optional(),
  hebergement: z.string().max(500).optional(),
  transport: z.string().max(500).optional(),
});

export type Details = z.infer<typeof SchemaDetails>;

/**
 * Étape 2 à 4, en une seule transaction (brief §8.2).
 *
 * Les allergies sont une donnée de santé : sans consentement explicite, elles
 * ne sont pas écrites, et une saisie précédente est effacée (brief §11).
 * La date de purge est calculée dès l'écriture : 30 jours après le mariage.
 */
export async function enregistrerDetails(
  foyerId: string,
  details: Details,
  momentsConnus: ReadonlyArray<string>,
): Promise<void> {
  await transaction(async (executer) => {
    const invites = await executer<{ id: string }>(
      "select id from public.guests where household_id = $1",
      [foyerId],
    );
    const autorises = new Set(invites.map((invite) => invite.id));

    for (const inviteId of Object.keys(details.presences)) {
      if (!autorises.has(inviteId)) continue; // jamais l'invité d'un autre foyer

      const presents = new Set(
        (details.presences[inviteId] ?? []).filter((moment) => momentsConnus.includes(moment)),
      );
      for (const moment of momentsConnus) {
        await executer(
          `insert into public.rsvp_attendance (guest_id, moment_id, attending)
           values ($1, $2, $3)
           on conflict (guest_id, moment_id) do update set attending = excluded.attending`,
          [inviteId, moment, presents.has(moment)],
        );
      }

      await executer(
        `update public.guests set menu_choice = $2, diet_flags = $3 where id = $1`,
        [
          inviteId,
          details.menus[inviteId]?.trim() === "" ? null : (details.menus[inviteId] ?? null),
          details.regimes[inviteId] ?? [],
        ],
      );

      const allergie = details.allergies[inviteId]?.trim() ?? "";
      if (details.consentementAllergies && allergie !== "") {
        await executer(
          `insert into public.health_allergies
             (guest_id, content, consent_at, consent_text_version, purge_after)
           values ($1, $2, now(), $3,
                   (select date_mariage + 30 from public.parametres where id = 1))
           on conflict (guest_id) do update
              set content = excluded.content,
                  consent_at = excluded.consent_at,
                  consent_text_version = excluded.consent_text_version,
                  purge_after = excluded.purge_after`,
          [inviteId, allergie, details.versionConsentement],
        );
      } else {
        // Consentement retiré ou champ vidé : la donnée de santé disparaît.
        await executer("delete from public.health_allergies where guest_id = $1", [inviteId]);
      }
    }

    await executer(
      `update public.rsvp
          set song_request = $2, message_to_couple = $3,
              lodging_note = $4, transport_note = $5, updated_at = now()
        where household_id = $1 and locked_at is null`,
      [
        foyerId,
        details.chanson ?? null,
        details.message ?? null,
        details.hebergement ?? null,
        details.transport ?? null,
      ],
    );
  });
}
