import { listerFoyers } from "@/lib/invites";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";

/** Invités : import, état, révocation, planche à imprimer (brief §14). */
export default async function PageInvitesAdmin() {
  const { t } = await langueEtTextes();
  const foyers = await listerFoyers();
  const bordure = { borderColor: "var(--filet)" };

  const statut = (valeur: string | null): string =>
    valeur === "yes"
      ? t.admin.oui
      : valeur === "no"
        ? t.admin.non
        : valeur === "maybe"
          ? t.admin.peutetre
          : "—";

  return (
    <main className="flex flex-col gap-10">
      <h1 className="jl-titre text-2xl">{t.admin.invites}</h1>

      <section aria-labelledby="import" className="flex flex-col gap-4">
        <h2 id="import" className="jl-etiquette">
          {t.admin.import_titre}
        </h2>
        <p className="jl-doux text-sm">{t.admin.import_format}</p>
        <p className="border p-4 text-sm" style={bordure}>
          {t.admin.import_avertissement}
        </p>
        <form
          method="post"
          action="/admin/invites/importer"
          encType="multipart/form-data"
          className="flex flex-col gap-4"
        >
          <input
            type="file"
            name="fichier"
            accept=".csv,text/csv"
            required
            className="jl-cible border px-4 py-3"
            style={bordure}
          />
          <button type="submit" className="jl-cible self-start border px-5 py-3" style={bordure}>
            {t.admin.import_bouton}
          </button>
        </form>
      </section>

      <section aria-labelledby="liste" className="flex flex-col gap-4">
        <hr className="jl-filet" />
        <h2 id="liste" className="jl-etiquette">
          {t.admin.foyers}
        </h2>
        {foyers.length === 0 ? (
          <p className="jl-doux">{t.admin.aucun_foyer}</p>
        ) : (
          <table className="w-full text-left">
            <thead>
              <tr className="jl-doux text-sm">
                <th scope="col" className="py-2">{t.admin.colonne_foyer}</th>
                <th scope="col" className="py-2">{t.admin.colonne_invites}</th>
                <th scope="col" className="py-2">{t.admin.colonne_statut}</th>
                <th scope="col" className="py-2">{t.admin.colonne_ouvert}</th>
                <th scope="col" className="py-2">{t.admin.colonne_action}</th>
              </tr>
            </thead>
            <tbody>
              {foyers.map((foyer) => (
                <tr key={foyer.id} style={{ borderTop: "1px solid var(--filet)" }}>
                  <td className="py-3">{foyer.label_public}</td>
                  <td className="py-3 tabular-nums">{foyer.invites}</td>
                  <td className="py-3">{statut(foyer.statut)}</td>
                  <td className="py-3">{foyer.first_opened_at === null ? "—" : "✓"}</td>
                  <td className="py-3">
                    {foyer.revoked_at === null ? (
                      <form method="post" action="/admin/invites/revoquer">
                        <input type="hidden" name="foyer" value={foyer.id} />
                        <button type="submit" className="jl-cible underline underline-offset-4">
                          {t.admin.revoquer}
                        </button>
                      </form>
                    ) : (
                      <span className="jl-doux">{t.admin.revoque}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section aria-labelledby="planche" className="flex flex-col gap-4">
        <hr className="jl-filet" />
        <h2 id="planche" className="jl-etiquette">
          {t.admin.planche_titre}
        </h2>
        <p className="border p-4 text-sm" style={bordure}>
          {t.admin.planche_avertissement}
        </p>
        <form method="post" action="/admin/invites/planche">
          <button type="submit" className="jl-cible border px-5 py-3" style={bordure}>
            {t.admin.planche_bouton}
          </button>
        </form>
      </section>
    </main>
  );
}
