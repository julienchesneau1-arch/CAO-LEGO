import { Filet } from "@/components/Filet";
import { FileAttente } from "@/components/FileAttente";
import { foyerCourant } from "@/lib/foyer";
import { formater } from "@/lib/i18n";
import { genreMoment, moments, nomMoment } from "@/lib/moments";
import { langueEtTextes } from "@/lib/page-commune";
import { REGIMES, invitesDuFoyer, reponseDuFoyer, reponseVerrouillee } from "@/lib/rsvp";
import { MOMENTS } from "@/lib/tokens";

export const dynamic = "force-dynamic";
export const metadata = { title: "Votre réponse — J & L" };

const couleur = (id: string): string =>
  MOMENTS.find((moment) => moment.id === id)?.hex ?? "var(--filet)";

/**
 * Réponse (brief §8.2). Deux formulaires HTML, sans JavaScript :
 * un tap enregistre le oui, le non ou le « pas encore sûr » ; le reste est
 * facultatif et déjà prérempli. Le parcours « Non » est bienveillant et ne
 * demande plus rien.
 */
export default async function PageReponse({
  searchParams,
}: {
  readonly searchParams: Promise<{ etat?: string }>;
}) {
  const { langue, t } = await langueEtTextes();
  const { etat } = await searchParams;
  const foyer = await foyerCourant();

  if (foyer === undefined) {
    return (
      <main className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-12">
        <h1 className="jl-titre text-3xl">{t.reponse.titre}</h1>
        <p>{t.reponse.non_reconnu}</p>
      </main>
    );
  }

  const [reponse, invites, liste, verrouillee] = await Promise.all([
    reponseDuFoyer(foyer.id),
    invitesDuFoyer(foyer.id),
    moments(),
    reponseVerrouillee(),
  ]);

  const confirmation =
    reponse === null
      ? undefined
      : reponse.statut === "yes"
        ? t.reponse.enregistre_oui
        : reponse.statut === "maybe"
          ? t.reponse.enregistre_peutetre
          : t.reponse.enregistre_non;

  const bordure = { borderColor: "var(--filet)" };

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-10 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="jl-titre text-3xl">{t.reponse.titre}</h1>
        <FileAttente
          libelles={{
            enAttente: t.horsligne.en_attente,
            enAttentePluriel: t.horsligne.en_attente_pluriel,
            envoye: t.horsligne.envoye,
          }}
        />
        {etat === "erreur" || etat === "debit" ? (
          <p role="alert" className="border p-4" style={bordure}>
            {t.reponse.erreur}
          </p>
        ) : null}
        {verrouillee ? (
          <p role="alert" className="border p-4" style={bordure}>
            {t.reponse.verrouille}
          </p>
        ) : null}
      </header>

      {/* Étape 1 : un seul tap, enregistré tout de suite. */}
      <section aria-labelledby="etape1" className="flex flex-col gap-5">
        <h2 id="etape1" className="jl-titre text-2xl">
          {t.reponse.question}
        </h2>
        {confirmation === undefined ? null : (
          <div className="flex flex-col gap-3">
            <p className="jl-titre text-xl">{confirmation}</p>
            <Filet couleur={couleur(reponse?.statut === "no" ? "04" : "01")} largeur="8rem" anime />
          </div>
        )}
        {verrouillee ? null : (
          <form method="post" action="/reponse/statut" data-file-attente className="flex flex-wrap gap-3">
            {(
              [
                ["yes", t.reponse.oui],
                ["no", t.reponse.non],
                ["maybe", t.reponse.peutetre],
              ] as const
            ).map(([valeur, libelle]) => (
              <button
                key={valeur}
                type="submit"
                name="statut"
                value={valeur}
                aria-pressed={reponse?.statut === valeur}
                className="jl-cible jl-titre border px-6 py-3 text-xl"
                style={{
                  ...bordure,
                  background: reponse?.statut === valeur ? "var(--filet)" : "transparent",
                }}
              >
                {libelle}
              </button>
            ))}
          </form>
        )}
      </section>

      {/* Parcours « Non » : on ne demande plus rien, sauf un mot si l'envie vient. */}
      {reponse?.statut === "no" ? (
        <section aria-labelledby="mot" className="flex flex-col gap-5">
          <hr className="jl-filet" />
          <h2 id="mot" className="jl-etiquette">
            {t.reponse.message}
          </h2>
          <p className="jl-doux">{t.reponse.non_suite}</p>
          <a
            href="/loin"
            className="jl-cible jl-etiquette flex items-center underline decoration-1 underline-offset-8"
          >
            {t.loin.titre}
          </a>
          {verrouillee ? null : (
            <form method="post" action="/reponse/details" data-file-attente className="flex flex-col gap-4">
              <label className="flex flex-col gap-2">
                <span className="sr-only">{t.reponse.message}</span>
                <textarea
                  name="message"
                  rows={4}
                  defaultValue={reponse.message_to_couple ?? ""}
                  className="border bg-transparent px-4 py-3"
                  style={{ ...bordure, color: "var(--texte)" }}
                />
              </label>
              <button type="submit" className="jl-cible self-start border px-5 py-3" style={bordure}>
                {t.reponse.envoyer}
              </button>
            </form>
          )}
        </section>
      ) : null}

      {/* Étapes 2 à 4, seulement si le foyer vient. Tout est prérempli. */}
      {reponse !== null && reponse.statut !== "no" && !verrouillee ? (
        <form method="post" action="/reponse/details" data-file-attente className="flex flex-col gap-10">
          <section aria-labelledby="etape2" className="flex flex-col gap-6">
            <hr className="jl-filet" />
            <h2 id="etape2" className="jl-etiquette">
              {t.reponse.detail_titre}
            </h2>

            {invites.map((invite) => (
              <fieldset key={invite.id} className="flex flex-col gap-4 border p-5" style={bordure}>
                <legend className="jl-titre text-xl">
                  {invite.first_name} {invite.last_name ?? ""}
                </legend>
                <input type="hidden" name="invite" value={invite.id} />

                <p className="jl-doux text-sm">{t.reponse.presence_tous}</p>

                <details>
                  <summary className="jl-cible jl-etiquette flex items-center">
                    {t.reponse.preciser}
                  </summary>
                  <div className="mt-4 flex flex-col gap-3">
                    <input type="hidden" name={`precise-${invite.id}`} value="1" />
                    {liste.map((moment) => (
                      <label key={moment.id} className="jl-cible flex items-center gap-3">
                        <input
                          type="checkbox"
                          name={`presence-${invite.id}`}
                          value={moment.id}
                          defaultChecked={
                            invite.presences.length === 0 || invite.presences.includes(moment.id)
                          }
                        />
                        <span>
                          {moment.id} · {nomMoment(moment, langue)}
                          <span className="jl-doux"> — {genreMoment(moment, langue)}</span>
                        </span>
                      </label>
                    ))}
                  </div>
                </details>

                <div className="flex flex-col gap-3">
                  <span className="jl-etiquette">{t.reponse.menu_titre}</span>
                  <p className="jl-doux text-sm">{t.reponse.menu_attente}</p>
                  <label className="flex flex-col gap-2">
                    <span className="jl-doux text-sm">{t.reponse.menu_libre}</span>
                    <input
                      name={`menu-${invite.id}`}
                      defaultValue={invite.menu_choice ?? ""}
                      className="jl-cible border bg-transparent px-4 py-3"
                      style={{ ...bordure, color: "var(--texte)" }}
                    />
                  </label>
                  <div className="flex flex-wrap gap-4">
                    {REGIMES.map((regime) => (
                      <label key={regime} className="jl-cible flex items-center gap-3">
                        <input
                          type="checkbox"
                          name={`regime-${invite.id}`}
                          value={regime}
                          defaultChecked={invite.diet_flags.includes(regime)}
                        />
                        <span>{t.reponse[`regime_${regime}` as "regime_vegetarien"]}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <label className="flex flex-col gap-2">
                  <span className="jl-etiquette">{t.reponse.allergies_champ}</span>
                  <input
                    name={`allergies-${invite.id}`}
                    defaultValue={invite.allergies ?? ""}
                    className="jl-cible border bg-transparent px-4 py-3"
                    style={{ ...bordure, color: "var(--texte)" }}
                  />
                </label>
              </fieldset>
            ))}

            {/* Donnée de santé : consentement explicite, séparé, versionné. */}
            <div className="flex flex-col gap-3 border p-5" style={bordure}>
              <span className="jl-etiquette">{t.reponse.allergies_titre}</span>
              <p className="jl-doux text-sm">{t.reponse.allergies_explication}</p>
              <label className="jl-cible flex items-start gap-3">
                <input type="checkbox" name="consentement-allergies" value="1" />
                <span>{t.reponse.allergies_consentement}</span>
              </label>
            </div>
          </section>

          <section aria-labelledby="etape4" className="flex flex-col gap-4">
            <hr className="jl-filet" />
            <h2 id="etape4" className="jl-etiquette">
              {t.reponse.facultatif}
            </h2>
            <details>
              <summary className="jl-cible flex items-center underline decoration-1 underline-offset-8">
                {t.reponse.facultatif_ouvrir}
              </summary>
              <div className="mt-4 flex flex-col gap-4">
                {(
                  [
                    ["chanson", t.reponse.chanson, reponse.song_request],
                    ["hebergement", t.reponse.hebergement, reponse.lodging_note],
                    ["transport", t.reponse.transport, reponse.transport_note],
                  ] as const
                ).map(([nom, libelle, valeur]) => (
                  <label key={nom} className="flex flex-col gap-2">
                    <span className="jl-doux">{libelle}</span>
                    <input
                      name={nom}
                      defaultValue={valeur ?? ""}
                      className="jl-cible border bg-transparent px-4 py-3"
                      style={{ ...bordure, color: "var(--texte)" }}
                    />
                  </label>
                ))}
                <label className="flex flex-col gap-2">
                  <span className="jl-doux">{t.reponse.message}</span>
                  <textarea
                    name="message"
                    rows={4}
                    defaultValue={reponse.message_to_couple ?? ""}
                    className="border bg-transparent px-4 py-3"
                    style={{ ...bordure, color: "var(--texte)" }}
                  />
                </label>
              </div>
            </details>
          </section>

          <button type="submit" className="jl-cible self-start border px-6 py-3" style={bordure}>
            {t.reponse.envoyer}
          </button>
        </form>
      ) : null}

      {etat === "enregistre" ? (
        <p aria-live="polite" className="jl-doux">
          {formater(t.reponse.enregistre, {})}
        </p>
      ) : null}
    </main>
  );
}
