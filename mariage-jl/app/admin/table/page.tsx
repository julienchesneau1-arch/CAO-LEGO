import { formater } from "@/lib/i18n";
import { langueEtTextes } from "@/lib/page-commune";
import { tables, toutesLesPlaces } from "@/lib/table";

export const dynamic = "force-dynamic";

const BORDURE = { borderColor: "var(--filet)" };
const CHAMP = "jl-cible border bg-transparent px-4 py-3";
const STYLE_CHAMP = { ...BORDURE, color: "var(--texte)" };
const BOUTON = "jl-cible border px-5 py-3";

/**
 * Plan de table côté mariés (brief §0 bis). Une table se crée, une personne
 * se pose. Le choix se fait avec un `select` qui s'enregistre au changement
 * — pas de glisser-déposer : cet écran doit marcher au téléphone, dans un
 * train, avec un pouce.
 */
export default async function PageAdminTable({
  searchParams,
}: {
  readonly searchParams: Promise<{ etat?: string }>;
}) {
  const { t } = await langueEtTextes();
  const { etat } = await searchParams;
  const [liste, places] = await Promise.all([tables(), toutesLesPlaces()]);
  const sansTable = places.filter((place) => place.table_id === null).length;

  return (
    <main className="flex flex-col gap-10">
      <h1 className="jl-titre text-2xl">{t.admin_table.titre}</h1>
      <p className="jl-doux">{t.admin_table.intro}</p>
      <p aria-live="polite">
        {sansTable === 0
          ? t.admin_table.complet
          : formater(t.admin_table.reste, { nombre: String(sansTable) })}
      </p>

      {etat === "enregistre" || etat === "supprime" ? (
        <p aria-live="polite" className="jl-doux">
          {etat === "supprime" ? t.admin_table.supprime : t.admin_table.enregistre}
        </p>
      ) : null}
      {etat === "erreur" ? (
        <p role="alert" className="border p-4" style={BORDURE}>
          {t.admin_table.erreur}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-4">
        <a href="/admin/table/cartes" className={`${BOUTON} flex items-center`} style={BORDURE}>
          {t.admin_table.cartes}
        </a>
        <a href="/admin/table/fiche" className={`${BOUTON} flex items-center`} style={BORDURE}>
          {t.admin_table.fiche}
        </a>
      </div>

      <section aria-labelledby="tables" className="flex flex-col gap-5">
        <hr className="jl-filet" />
        <h2 id="tables" className="jl-etiquette">
          {t.admin_table.tables}
        </h2>
        {liste.length === 0 ? <p className="jl-doux">{t.admin_table.aucune}</p> : null}
        <ul className="flex flex-col">
          {liste.map((table) => (
            <li key={table.id} className="flex flex-col">
              <div className="flex items-center justify-between gap-4 py-3">
                <span>
                  {table.label}
                  {table.capacity === null ? "" : ` · ${table.capacity}`}
                </span>
                <form method="post" action="/admin/table/supprimer">
                  <input type="hidden" name="table" value={table.id} />
                  <button type="submit" className="jl-cible jl-doux jl-etiquette px-2 py-2">
                    {t.admin_table.supprimer}
                  </button>
                </form>
              </div>
              <hr className="jl-filet" />
            </li>
          ))}
        </ul>

        <form method="post" action="/admin/table/creer" className="flex flex-col gap-4">
          <h3 className="jl-etiquette">{t.admin_table.nouvelle}</h3>
          <label className="flex flex-col gap-2">
            <span className="jl-etiquette">{t.admin_table.label}</span>
            <input type="text" name="label" required maxLength={60} className={CHAMP} style={STYLE_CHAMP} />
          </label>
          <div className="flex flex-wrap gap-5">
            <label className="flex flex-col gap-2">
              <span className="jl-etiquette">{t.admin_table.capacite}</span>
              <input
                type="number"
                name="capacite"
                min={1}
                max={99}
                className={`${CHAMP} w-24 tabular-nums`}
                style={STYLE_CHAMP}
              />
            </label>
            <label className="flex flex-col gap-2">
              <span className="jl-etiquette">{t.admin_table.ordre}</span>
              <input
                type="number"
                name="ordre"
                min={0}
                max={999}
                defaultValue={liste.length + 1}
                className={`${CHAMP} w-24 tabular-nums`}
                style={STYLE_CHAMP}
              />
            </label>
          </div>
          <button type="submit" className={`${BOUTON} self-start`} style={BORDURE}>
            {t.admin_table.creer}
          </button>
        </form>
      </section>

      {liste.length === 0 ? null : (
        <section aria-labelledby="personnes" className="flex flex-col gap-4">
          <hr className="jl-filet" />
          <h2 id="personnes" className="jl-etiquette">
            {t.admin_table.personnes}
          </h2>
          <ul className="flex flex-col gap-4">
            {places.map((place) => (
              <li key={place.guest_id} className="flex flex-col gap-2">
                <p>
                  {place.prenom}
                  <span className="jl-doux"> · {place.foyer}</span>
                </p>
                <form
                  method="post"
                  action="/admin/table/placer"
                  className="flex flex-wrap items-end gap-3"
                >
                  <input type="hidden" name="invite" value={place.guest_id} />
                  <label className="flex flex-col gap-2">
                    <span className="jl-etiquette">{t.admin_table.placer}</span>
                    <select
                      name="table"
                      defaultValue={place.table_id ?? ""}
                      className={CHAMP}
                      style={STYLE_CHAMP}
                    >
                      <option value="">{t.admin_table.sans_table}</option>
                      {liste.map((table) => (
                        <option key={table.id} value={table.id}>
                          {table.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button type="submit" className={BOUTON} style={BORDURE}>
                    {t.admin_contenus.enregistrer}
                  </button>
                </form>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
