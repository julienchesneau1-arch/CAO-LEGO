import { defisAdmin } from "@/lib/defis";
import { nomMoment, moments } from "@/lib/moments";
import { langueEtTextes } from "@/lib/page-commune";
import { MOMENTS } from "@/lib/tokens";

export const dynamic = "force-dynamic";

const BORDURE = { borderColor: "var(--filet)" };
const CHAMP = "jl-cible border bg-transparent px-4 py-3";
const STYLE_CHAMP = { ...BORDURE, color: "var(--texte)" };

const couleur = (id: string): string =>
  MOMENTS.find((moment) => moment.id === id)?.hex ?? "var(--filet)";

/**
 * Défis photo (brief §8.7, bonus). Un par moment, dans sa couleur. Les
 * intitulés ne sont pas fournis par le brief : ils restent vides, et un défi
 * sans intitulé n'apparaît nulle part, même publié.
 */
export default async function PageAdminDefis({
  searchParams,
}: {
  readonly searchParams: Promise<{ etat?: string }>;
}) {
  const { langue, t } = await langueEtTextes();
  const { etat } = await searchParams;
  const [defis, liste] = await Promise.all([defisAdmin(), moments()]);

  return (
    <main className="flex flex-col gap-8">
      <h1 className="jl-titre text-2xl">{t.admin_defis.titre}</h1>
      <p className="jl-doux">{t.admin_defis.intro}</p>
      <p className="jl-doux text-sm">{t.admin_defis.aucun_classement}</p>

      {etat === "enregistre" ? (
        <p aria-live="polite" className="jl-doux">
          {t.admin_contenus.enregistre}
        </p>
      ) : null}
      {etat === "erreur" ? (
        <p role="alert" className="border p-4" style={BORDURE}>
          {t.admin_contenus.erreur}
        </p>
      ) : null}

      <ul className="flex flex-col gap-10">
        {defis.map((defi) => {
          const moment = liste.find((candidat) => candidat.id === defi.moment_id);
          return (
            <li key={defi.id} className="flex flex-col gap-4">
              <div
                className="flex flex-wrap items-baseline gap-x-3 border-l-2 pl-4"
                style={{ borderColor: couleur(defi.moment_id) }}
              >
                <span className="jl-numero">{defi.moment_id}</span>
                <span className="jl-titre text-xl">
                  {moment === undefined ? "" : nomMoment(moment, langue)}
                </span>
              </div>
              <form
                method="post"
                action="/admin/defis/enregistrer"
                className="flex flex-col gap-4"
              >
                <input type="hidden" name="defi" value={defi.id} />
                <label className="flex flex-col gap-2">
                  <span className="jl-etiquette">{t.admin_defis.titre_fr}</span>
                  <input
                    type="text"
                    name="title_fr"
                    required
                    maxLength={120}
                    defaultValue={defi.title_fr}
                    className={CHAMP}
                    style={STYLE_CHAMP}
                  />
                </label>
                <label className="flex flex-col gap-2">
                  <span className="jl-etiquette">{t.admin_defis.titre_en}</span>
                  <input
                    type="text"
                    name="title_en"
                    required
                    maxLength={120}
                    defaultValue={defi.title_en}
                    className={CHAMP}
                    style={STYLE_CHAMP}
                  />
                </label>
                <label className="jl-cible flex items-center gap-3">
                  <input
                    type="checkbox"
                    name="published"
                    value="1"
                    defaultChecked={defi.published}
                  />
                  <span>{t.admin_defis.publie}</span>
                </label>
                <button
                  type="submit"
                  className="jl-cible self-start border px-5 py-3"
                  style={BORDURE}
                >
                  {t.admin_contenus.enregistrer}
                </button>
              </form>
            </li>
          );
        })}
      </ul>
    </main>
  );
}
