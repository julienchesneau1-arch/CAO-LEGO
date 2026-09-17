import { Notifications } from "@/components/Notifications";
import { annonces } from "@/lib/annonces";
import { langueEtTextes } from "@/lib/page-commune";
import { clePubliquePush } from "@/lib/push";

export const dynamic = "force-dynamic";
export const metadata = { title: "Les annonces — J & L" };

/**
 * Fil d'annonces (brief V2 et §8.6). Aucune donnée personnelle : il est donc
 * lisible aussi depuis le QR générique, et il peut vivre dans le cache.
 */
export default async function PageAnnonces() {
  const { langue, t } = await langueEtTextes();
  const liste = await annonces(langue);
  const cle = clePubliquePush();

  const dateLisible = (date: Date): string =>
    new Intl.DateTimeFormat(langue === "fr" ? "fr-FR" : "en-GB", {
      timeZone: "Europe/Paris",
      day: "numeric",
      month: "long",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-10 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="jl-titre text-3xl">{t.annonces.titre}</h1>
        <p className="jl-doux">{t.annonces.intro}</p>
      </header>

      {liste.length === 0 ? (
        <p className="jl-doux">{t.annonces.aucune}</p>
      ) : (
        <ol className="flex flex-col gap-8">
          {liste.map((annonce) => (
            <li key={annonce.id} className="flex flex-col gap-2">
              <hr className="jl-filet" />
              <p className="jl-etiquette">{dateLisible(annonce.published_at)}</p>
              <p className="jl-titre text-xl">{annonce.texte}</p>
              <p className="jl-doux text-sm">
                {annonce.author_role === "regie" ? t.annonces.par_regie : t.annonces.par_admin}
              </p>
            </li>
          ))}
        </ol>
      )}

      <hr className="jl-filet" />

      {cle === null ? null : (
        <Notifications
          clePublique={cle}
          libelles={{
            titre: t.notifications.titre,
            explication: t.notifications.explication,
            activer: t.notifications.activer,
            active: t.notifications.active,
            refuse: t.notifications.refuse,
            impossible: t.notifications.impossible,
          }}
        />
      )}
    </main>
  );
}
