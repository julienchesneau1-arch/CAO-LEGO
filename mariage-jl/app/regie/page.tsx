import { etatJournee } from "@/lib/journee";
import { galerie, signalements } from "@/lib/medias";
import { formater } from "@/lib/i18n";
import { heure, nomMoment } from "@/lib/moments";
import { moments } from "@/lib/moments";
import { langueEtTextes } from "@/lib/page-commune";
import { MOMENTS } from "@/lib/tokens";

export const dynamic = "force-dynamic";

const BORDURE = { borderColor: "var(--filet)" };
const BOUTON = "jl-cible border px-5 py-3";
/**
 * Trois pas suffisent : la journée glisse par quarts d'heure, pas par
 * minutes. Le pas est **partagé** par tous les moments : six boutons par
 * moment faisaient trente boutons à l'écran, ce qui n'est pas « utilisable
 * d'une main » (brief §9).
 */
const PAS = [5, 15, 30] as const;
const PAS_DEFAUT = 15;

const couleur = (id: string): string =>
  MOMENTS.find((moment) => moment.id === id)?.hex ?? "var(--filet)";

/**
 * Régie du jour J (brief §9), utilisable d'une main : publier une annonce
 * depuis un modèle, décaler un moment et ceux qui le suivent, suspendre les
 * envois de souvenirs. Rien d'autre — et surtout aucune donnée personnelle.
 */
export default async function PageRegie({
  searchParams,
}: {
  readonly searchParams: Promise<{ etat?: string; pas?: string }>;
}) {
  const { langue, t } = await langueEtTextes();
  const { etat, pas: pasBrut } = await searchParams;
  const pas = PAS.find((candidat) => String(candidat) === pasBrut) ?? PAS_DEFAUT;
  const [journee, liste, signales, derniers] = await Promise.all([
    etatJournee(),
    moments(),
    signalements(),
    galerie({ limite: 12, pourLesMaries: true }),
  ]);

  const messages: Readonly<Record<string, string>> = {
    publiee: t.regie.publiee,
    decale: t.regie.decale,
    remis: t.regie.remis,
    coupes: t.regie.coupes,
    rouverts: t.regie.rouverts,
    modere: t.regie_medias.titre,
  };
  // Les modèles sont désignés par leur clé, pas par leur texte : la route
  // retrouve alors les deux langues dans les dictionnaires, et un invité
  // anglophone reçoit une vraie traduction, pas du français recopié.
  const modeles = [
    { cle: "ceremonie", texte: t.regie.modele_ceremonie },
    { cle: "cocktail", texte: t.regie.modele_cocktail },
    { cle: "diner", texte: t.regie.modele_diner },
    { cle: "navette", texte: t.regie.modele_navette },
  ] as const;

  return (
    <main className="flex flex-col gap-10">
      {etat !== undefined && messages[etat] !== undefined ? (
        <p aria-live="polite" className="jl-doux">
          {messages[etat]}
        </p>
      ) : null}
      {etat === "erreur" ? (
        <p role="alert" className="border p-4" style={BORDURE}>
          {t.regie.erreur}
        </p>
      ) : null}

      {/* ------------------------------------------------------- Annonce */}
      <section aria-labelledby="annonce" className="flex flex-col gap-5">
        <h2 id="annonce" className="jl-titre text-xl">
          {t.regie.annonce}
        </h2>
        <p className="jl-etiquette">{t.regie.modeles}</p>
        <ul className="flex flex-col gap-3">
          {modeles.map((modele) => (
            <li key={modele.cle}>
              <form method="post" action="/regie/publier">
                <input type="hidden" name="modele" value={modele.cle} />
                <button type="submit" className={`${BOUTON} w-full text-left`} style={BORDURE}>
                  {modele.texte}
                </button>
              </form>
            </li>
          ))}
        </ul>
        <form method="post" action="/regie/publier" className="flex flex-col gap-4">
          <label className="flex flex-col gap-2">
            <span className="jl-etiquette">{t.admin_annonces.champ_fr}</span>
            <textarea
              name="texte"
              rows={3}
              required
              maxLength={500}
              className="jl-cible border bg-transparent px-4 py-3"
              style={{ ...BORDURE, color: "var(--texte)" }}
            />
          </label>
          <p className="jl-doux text-sm">{t.regie.libre_note}</p>
          <button type="submit" className={`${BOUTON} self-start`} style={BORDURE}>
            {t.regie.publier}
          </button>
        </form>
      </section>

      {/* ------------------------------------------------------ Horaires */}
      <section aria-labelledby="horaires" className="flex flex-col gap-5">
        <hr className="jl-filet" />
        <h2 id="horaires" className="jl-titre text-xl">
          {t.regie.horaires}
        </h2>
        {/* Le pas, choisi une fois, s'applique à tous les moments. */}
        <div className="flex flex-col gap-2">
          <p className="jl-etiquette" id="pas">
            {t.regie.pas}
          </p>
          <ul aria-labelledby="pas" className="flex flex-wrap gap-3">
            {PAS.map((candidat) => (
              <li key={candidat}>
                <a
                  href={`/regie?pas=${candidat}`}
                  aria-current={candidat === pas ? "true" : undefined}
                  className={`${BOUTON} flex items-center tabular-nums`}
                  style={
                    candidat === pas
                      ? { borderColor: "var(--texte)" }
                      : { ...BORDURE, color: "var(--doux)" }
                  }
                >
                  {formater(t.regie.pas_minutes, { minutes: String(candidat) })}
                </a>
              </li>
            ))}
          </ul>
        </div>

        <ul className="flex flex-col gap-6">
          {liste.map((moment) => (
            <li key={moment.id} className="flex flex-col gap-3">
              <div
                className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-l-2 pl-4"
                style={{ borderColor: couleur(moment.id) }}
              >
                <span className="jl-numero">{moment.id}</span>
                <span>{nomMoment(moment, langue)}</span>
                <span className="jl-doux tabular-nums">
                  {heure(moment.starts_at, langue) ?? t.programme.horaire_inconnu}
                </span>
                {moment.shift_minutes === 0 ? null : (
                  <span className="jl-doux tabular-nums">
                    ·{" "}
                    {formater(t.regie.decalage_actuel, {
                      minutes: `${moment.shift_minutes > 0 ? "+" : ""}${moment.shift_minutes}`,
                    })}
                  </span>
                )}
                {journee.courant?.id === moment.id ? (
                  <span className="jl-etiquette">{t.maintenant.en_cours}</span>
                ) : null}
              </div>
              <form method="post" action="/regie/decaler" className="flex flex-wrap gap-3">
                <input type="hidden" name="moment" value={moment.id} />
                <button
                  type="submit"
                  name="minutes"
                  value={String(pas)}
                  className={BOUTON}
                  style={BORDURE}
                >
                  {formater(t.regie.decaler_plus, { minutes: String(pas) })}
                </button>
                <button
                  type="submit"
                  name="minutes"
                  value={String(-pas)}
                  className={BOUTON}
                  style={BORDURE}
                >
                  {formater(t.regie.decaler_moins, { minutes: String(pas) })}
                </button>
              </form>
            </li>
          ))}
        </ul>
        <p className="jl-doux text-sm">{t.regie.decaler}</p>
        {liste.every((moment) => moment.shift_minutes === 0) ? null : (
          <form method="post" action="/regie/decaler">
            <input type="hidden" name="remise" value="1" />
            <button type="submit" className={`${BOUTON} self-start`} style={BORDURE}>
              {t.regie.remise}
            </button>
          </form>
        )}
      </section>

      {/* ----------------------------------------------------- Souvenirs */}
      <section aria-labelledby="souvenirs" className="flex flex-col gap-5" id="souvenirs">
        <hr className="jl-filet" />
        <h2 id="souvenirs" className="jl-titre text-xl">
          {t.regie_medias.titre}
        </h2>
        {signales.length === 0 ? (
          <p className="jl-doux">{t.regie_medias.aucun}</p>
        ) : (
          <ul className="flex flex-col gap-6">
            {signales.map((signalement) => (
              <li key={signalement.id} className="flex flex-col gap-3">
                <div className="flex items-start gap-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`/m/${signalement.media_id}`}
                    alt=""
                    className="h-20 w-20 shrink-0 object-cover"
                    style={{ borderTop: "2px solid var(--filet)" }}
                  />
                  <div className="flex min-w-0 flex-col gap-1">
                    <p className="jl-etiquette">
                      {signalement.status === "hidden"
                        ? t.regie_medias.masque
                        : t.regie_medias.visible}
                    </p>
                    <p className="jl-doux text-sm">
                      {signalement.reason ?? t.regie_medias.sans_raison}
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-3">
                  <form method="post" action="/regie/medias">
                    <input type="hidden" name="media" value={signalement.media_id} />
                    <input
                      type="hidden"
                      name="masquer"
                      value={signalement.status === "hidden" ? "0" : "1"}
                    />
                    <button type="submit" className={BOUTON} style={BORDURE}>
                      {signalement.status === "hidden"
                        ? t.regie_medias.rendre
                        : t.regie_medias.masquer}
                    </button>
                  </form>
                  {signalement.resolved_at === null ? (
                    <form method="post" action="/regie/medias">
                      <input type="hidden" name="signalement" value={signalement.id} />
                      <button type="submit" className={`${BOUTON} jl-doux`} style={BORDURE}>
                        {t.regie_medias.resoudre}
                      </button>
                    </form>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}

        {derniers.length === 0 ? null : (
          <>
            <h3 className="jl-etiquette">{t.regie_medias.derniers}</h3>
            {/*
              Une image seule ne dit pas ce qu'un appui va faire. Le bouton
              porte donc son libellé sous la vignette : masquer une photo par
              inadvertance, un soir de fête, serait facile et désagréable.
            */}
            <ul className="grid grid-cols-3 gap-3">
              {derniers.map((media) => (
                <li key={media.id} className="flex flex-col gap-2">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`/m/${media.id}`}
                    alt=""
                    className="aspect-square w-full object-cover"
                    style={{ borderTop: "2px solid var(--filet)" }}
                  />
                  <form method="post" action="/regie/medias">
                    <input type="hidden" name="media" value={media.id} />
                    <input type="hidden" name="masquer" value="1" />
                    <button
                      type="submit"
                      className="jl-cible jl-etiquette w-full border px-2 py-2"
                      style={BORDURE}
                    >
                      {t.regie_medias.masquer}
                    </button>
                  </form>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      {/* -------------------------------------------------------- Envois */}
      <section aria-labelledby="envois" className="flex flex-col gap-4">
        <hr className="jl-filet" />
        <h2 id="envois" className="jl-titre text-xl">
          {t.regie.envois}
        </h2>
        <p className="jl-doux">
          {journee.pendantCeremonie
            ? t.regie.etat_ceremonie
            : journee.envoisEnPause
              ? t.regie.etat_coupe
              : t.regie.etat_ouvert}
        </p>
        <form method="post" action="/regie/envois">
          <input type="hidden" name="couper" value={journee.pauseManuelle ? "0" : "1"} />
          <button type="submit" className={`${BOUTON} self-start`} style={BORDURE}>
            {journee.pauseManuelle ? t.regie.rouvrir : t.regie.couper}
          </button>
        </form>
      </section>
    </main>
  );
}
