import { echeances, mesDonnees } from "@/lib/apres";
import { foyerCourant } from "@/lib/foyer";
import { formaterDate } from "@/lib/i18n";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";
export const metadata = { title: "Mes données — J & L", robots: { index: false } };

/**
 * « Mes données » (brief §11). L'écran **compte** ce que nous détenons, il ne
 * le recopie pas : redire les allergies de chacun à l'écran serait exposer
 * une donnée de santé pour rien.
 *
 * Les dates viennent de `jl.echeances()`, c'est-à-dire des mêmes expressions
 * que les purges : l'écran ne peut pas annoncer une date que la base ne
 * tiendra pas.
 */
export default async function PageMesDonnees() {
  const { langue, t } = await langueEtTextes();
  const foyer = await foyerCourant();

  if (foyer === undefined) {
    return (
      <main className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-12">
        <h1 className="jl-titre text-3xl">{t.donnees.titre}</h1>
        <p className="jl-doux">{t.donnees.sans_foyer}</p>
      </main>
    );
  }

  const [donnees, liste] = await Promise.all([mesDonnees(foyer.id), echeances()]);

  const lignes: ReadonlyArray<{ readonly libelle: string; readonly valeur: string }> = [
    { libelle: t.donnees.invites, valeur: String(donnees.invites) },
    {
      libelle: t.donnees.reponse,
      valeur: donnees.aRepondu ? t.donnees.reponse_oui : t.donnees.reponse_non,
    },
    { libelle: t.donnees.allergies, valeur: String(donnees.allergies) },
    { libelle: t.donnees.souvenirs, valeur: String(donnees.souvenirs) },
    { libelle: t.donnees.messages, valeur: String(donnees.messages) },
    {
      libelle: t.donnees.rappels,
      valeur: donnees.rappels ? t.donnees.rappels_oui : t.donnees.rappels_non,
    },
    { libelle: t.donnees.notifications, valeur: String(donnees.notifications) },
  ];

  const nomEcheance: Readonly<Record<string, string>> = {
    allergies: t.donnees.allergies,
    reponses: t.donnees.reponse,
    acces: t.retrouver.titre,
    medias: t.donnees.souvenirs,
    journaux: t.admin.tableau,
    voeux: t.promesse.lien,
  };

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-10 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="jl-titre text-3xl">{t.donnees.titre}</h1>
        <p className="jl-doux">{t.donnees.intro}</p>
      </header>

      {/*
        Une liste de définitions n'accepte que `dt`, `dd` et un `div` qui les
        enveloppe directement. Le filet est donc une bordure, pas un `<hr>` :
        axe-core signalait sinon chaque ligne comme mal formée.
      */}
      <dl className="flex flex-col">
        {lignes.map((ligne) => (
          <div
            key={ligne.libelle}
            className="flex items-baseline justify-between gap-4 border-b py-3"
            style={{ borderColor: "var(--filet)" }}
          >
            <dt>{ligne.libelle}</dt>
            <dd className="tabular-nums">{ligne.valeur}</dd>
          </div>
        ))}
      </dl>

      <section aria-labelledby="echeances" role="region" className="flex flex-col gap-3">
        <h2 id="echeances" className="jl-etiquette">
          {t.donnees.echeances}
        </h2>
        <ul className="flex flex-col gap-2">
          {liste.map((echeance) => (
            <li key={echeance.quoi} className="flex items-baseline justify-between gap-4">
              <span>{nomEcheance[echeance.quoi] ?? echeance.quoi}</span>
              <span className="jl-doux tabular-nums">{formaterDate(echeance.le, langue)}</span>
            </li>
          ))}
        </ul>
      </section>

      <p className="jl-doux">{t.donnees.demander}</p>
    </main>
  );
}
