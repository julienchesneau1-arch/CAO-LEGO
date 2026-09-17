import { annonces } from "@/lib/annonces";
import { formater } from "@/lib/i18n";
import { langueEtTextes } from "@/lib/page-commune";
import { pushConfigure } from "@/lib/push";

export const dynamic = "force-dynamic";

/** Publication des annonces par les mariés (brief §14). */
export default async function PageAdminAnnonces({
  searchParams,
}: {
  readonly searchParams: Promise<{ etat?: string; envoyees?: string }>;
}) {
  const { langue, t } = await langueEtTextes();
  const { etat, envoyees } = await searchParams;
  const liste = await annonces(langue);
  const bordure = { borderColor: "var(--filet)" };

  return (
    <main className="flex flex-col gap-8">
      <h1 className="jl-titre text-2xl">{t.admin_annonces.titre}</h1>

      {etat === "publiee" ? (
        <p aria-live="polite" className="jl-doux">
          {t.admin_annonces.publiee}
          {envoyees === undefined
            ? ""
            : ` ${formater(t.admin_annonces.envoyees, { nombre: envoyees })}`}
        </p>
      ) : null}
      {etat === "erreur" ? (
        <p role="alert" className="border p-4" style={bordure}>
          {t.admin_annonces.erreur}
        </p>
      ) : null}

      <form method="post" action="/admin/annonces/publier" className="flex flex-col gap-5">
        <label className="flex flex-col gap-2">
          <span className="jl-etiquette">{t.admin_annonces.champ_fr}</span>
          <textarea
            name="texte_fr"
            rows={3}
            required
            maxLength={500}
            className="border bg-transparent px-4 py-3"
            style={{ ...bordure, color: "var(--texte)" }}
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className="jl-etiquette">{t.admin_annonces.champ_en}</span>
          <textarea
            name="texte_en"
            rows={3}
            required
            maxLength={500}
            className="border bg-transparent px-4 py-3"
            style={{ ...bordure, color: "var(--texte)" }}
          />
        </label>

        {pushConfigure() ? (
          <label className="jl-cible flex items-center gap-3">
            <input type="checkbox" name="notifier" value="1" />
            <span>{t.admin_annonces.notifier}</span>
          </label>
        ) : (
          <p className="jl-doux text-sm">{t.admin_annonces.push_absent}</p>
        )}

        <button type="submit" className="jl-cible self-start border px-5 py-3" style={bordure}>
          {t.admin_annonces.publier}
        </button>
      </form>

      {liste.length === 0 ? null : (
        <section aria-labelledby="historique" className="flex flex-col gap-4">
          <hr className="jl-filet" />
          <h2 id="historique" className="jl-etiquette">
            {t.admin_annonces.historique}
          </h2>
          <ul className="flex flex-col gap-4">
            {liste.map((annonce) => (
              <li key={annonce.id} className="flex flex-col gap-1">
                <p>{annonce.texte}</p>
                <p className="jl-doux text-sm tabular-nums">
                  {annonce.published_at.toISOString().slice(0, 16).replace("T", " ")}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
