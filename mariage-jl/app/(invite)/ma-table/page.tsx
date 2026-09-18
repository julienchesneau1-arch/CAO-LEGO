import { Filet } from "@/components/Filet";
import { foyerCourant } from "@/lib/foyer";
import { formater } from "@/lib/i18n";
import { langueEtTextes } from "@/lib/page-commune";
import { chercherUnePlace, placesDuFoyer, prenomsDeLaTable, tables } from "@/lib/table";

export const dynamic = "force-dynamic";
export const metadata = { title: "Ma table — J & L", robots: { index: false } };

/**
 * Plan de table (brief §0 bis : « recherche de son nom, table »).
 *
 * La recherche est un formulaire GET, pas un champ qui filtre une liste
 * chargée d'avance : la liste des invités n'est jamais envoyée en entier au
 * téléphone. Chercher « Marie » renvoie un prénom et une table, rien d'autre
 * — ni son foyer, ni sa réponse, ni son régime (§11).
 *
 * La présentation des voisins de table est **coupée** par la section 0 bis :
 * on donne les prénoms de la table, pas qui est qui.
 */
export default async function PageMaTable({
  searchParams,
}: {
  readonly searchParams: Promise<{ q?: string }>;
}) {
  const { t } = await langueEtTextes();
  const { q } = await searchParams;
  const terme = (q ?? "").trim();
  const foyer = await foyerCourant();

  const [liste, places, resultats] = await Promise.all([
    tables(),
    foyer === undefined ? Promise.resolve([]) : placesDuFoyer(foyer.id),
    terme.length >= 2 ? chercherUnePlace(terme) : Promise.resolve([]),
  ]);

  const maTable = places.find((place) => place.table_id !== null);
  const voisins =
    maTable?.table_id === undefined || maTable.table_id === null
      ? []
      : await prenomsDeLaTable(maTable.table_id);
  const bordure = { borderColor: "var(--filet)" };

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-10 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="jl-titre text-3xl">{t.table.titre}</h1>
        <p className="jl-doux">{t.table.intro}</p>
      </header>

      {liste.length === 0 ? (
        <p className="jl-doux">{t.table.sans_plan}</p>
      ) : (
        <>
          <section aria-labelledby="ma-place" className="flex flex-col gap-4">
            <h2 id="ma-place" className="jl-etiquette">
              {t.table.titre}
            </h2>
            {foyer === undefined ? (
              <p className="jl-doux">{t.table.sans_foyer}</p>
            ) : maTable?.table_label == null ? (
              <p className="jl-doux">{t.table.sans_place}</p>
            ) : (
              <>
                <Filet />
                <p className="jl-titre text-4xl">
                  {formater(t.table.votre_table, { table: maTable.table_label })}
                </p>
                <p className="jl-etiquette">{t.table.avec}</p>
                <ul className="flex flex-wrap gap-x-4 gap-y-1">
                  {voisins.map((prenom) => (
                    <li key={prenom}>{prenom}</li>
                  ))}
                </ul>
              </>
            )}
          </section>

          <section
            aria-labelledby="chercher"
            role="region"
            className="flex flex-col gap-4"
          >
            <hr className="jl-filet" />
            <h2 id="chercher" className="jl-etiquette">
              {t.table.chercher}
            </h2>
            <form method="get" action="/ma-table" className="flex flex-col gap-3">
              <label className="flex flex-col gap-2">
                <span className="jl-doux text-sm">{t.table.chercher_aide}</span>
                <input
                  type="search"
                  name="q"
                  defaultValue={terme}
                  minLength={2}
                  maxLength={60}
                  className="jl-cible border bg-transparent px-4 py-3"
                  style={{ ...bordure, color: "var(--texte)" }}
                />
              </label>
              <button type="submit" className="jl-cible self-start border px-5 py-3" style={bordure}>
                {t.table.chercher}
              </button>
            </form>

            {terme.length < 2 ? null : resultats.length === 0 ? (
              <p role="status" className="jl-doux">
                {t.table.aucun_resultat}
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {resultats.map((resultat) => (
                  <li
                    key={`${resultat.prenom}-${resultat.table ?? ""}`}
                    className="flex items-baseline justify-between gap-4"
                  >
                    <span>{resultat.prenom}</span>
                    <span className="jl-doux">
                      {resultat.table === null
                        ? t.table.resultat_sans_table
                        : formater(t.table.votre_table, { table: resultat.table })}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <p className="jl-doux text-sm">{t.table.papier}</p>
        </>
      )}
    </main>
  );
}
