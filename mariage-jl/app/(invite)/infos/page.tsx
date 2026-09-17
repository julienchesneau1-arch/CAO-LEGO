import { contenus, hebergements } from "@/lib/contenus";
import { itineraires } from "@/lib/cartes";
import { formater } from "@/lib/i18n";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";
export const metadata = { title: "Informations pratiques — J & L" };

const SECTIONS = [
  "venir",
  "dormir",
  "tenue",
  "enfants",
  "accessibilite",
  "rentrer",
  "covoiturage",
  "liste_mariage",
] as const;

/**
 * Infos (brief §8.4). Chaque section vient de l'espace admin : tant qu'elle
 * n'est pas écrite, l'écran le dit clairement au lieu d'afficher du vide ou,
 * pire, une information inventée.
 */
export default async function PageInfos() {
  const { langue, t } = await langueEtTextes();
  const [blocs, lits] = await Promise.all([contenus(langue), hebergements()]);
  const destination = t.infos.adresse;

  const aCompleter = (texte: string): boolean =>
    texte.trim() === "" || texte.includes("[À COMPLÉTER]") || texte.includes("[TO BE COMPLETED]");

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-10 px-6 py-12">
      <h1 className="jl-titre text-3xl">{t.infos.titre}</h1>

      <section aria-labelledby="itineraire" className="flex flex-col gap-4">
        <h2 id="itineraire" className="jl-etiquette">
          {t.infos.itineraire}
        </h2>
        <p>{t.infos.adresse}</p>
        <ul className="flex flex-wrap gap-3">
          {itineraires(destination).map((itineraire) => (
            <li key={itineraire.cle}>
              <a
                href={itineraire.url}
                rel="noreferrer"
                target="_blank"
                className="jl-cible flex items-center border px-4 py-3"
                style={{ borderColor: "var(--filet)" }}
              >
                {t.infos[`itineraire_${itineraire.cle}` as "itineraire_apple"]}
              </a>
            </li>
          ))}
        </ul>
      </section>

      {SECTIONS.map((section) => {
        const bloc = blocs[`infos.${section}`];
        const texte = bloc?.texte ?? "";
        const vide = aCompleter(texte);
        return (
          <section key={section} aria-labelledby={`infos-${section}`} className="flex flex-col gap-3">
            <hr className="jl-filet" />
            <h2 id={`infos-${section}`} className="jl-etiquette">
              {t.infos[section]}
            </h2>
            <p className={vide ? "jl-doux" : "whitespace-pre-line"}>
              {vide ? t.infos.attente : texte}
            </p>

            {/* Les hébergements viennent de l'admin : tant que la liste est
                vide, la section dit simplement qu'elle arrive. */}
            {section === "dormir" && lits.length > 0 ? (
              <ul className="flex flex-col gap-6">
                {lits.map((lit) => (
                  <li key={lit.id} className="flex flex-col gap-2 border p-5" style={{ borderColor: "var(--filet)" }}>
                    <p className="jl-titre text-xl">{lit.name}</p>
                    {lit.distance_km === null ? null : (
                      <p className="jl-doux tabular-nums">
                        {formater(t.infos_dormir.distance, { km: String(lit.distance_km) })}
                      </p>
                    )}
                    {lit.price_hint === null ? null : (
                      <p className="jl-doux">
                        {formater(t.infos_dormir.prix, { prix: lit.price_hint })}
                      </p>
                    )}
                    {lit.shuttle === null ? null : (
                      <p className="jl-doux">
                        {lit.shuttle ? t.infos_dormir.navette : t.infos_dormir.sans_navette}
                      </p>
                    )}
                    {lit.phone === null ? null : (
                      <a href={`tel:${lit.phone.replace(/\s/g, "")}`} className="jl-cible flex items-center underline decoration-1 underline-offset-8">
                        {t.infos_dormir.telephone} · {lit.phone}
                      </a>
                    )}
                    {lit.url === null ? null : (
                      <a href={lit.url} rel="noreferrer" target="_blank" className="jl-cible flex items-center underline decoration-1 underline-offset-8">
                        {t.infos_dormir.reserver}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            ) : null}
            {bloc?.lien == null ? null : (
              <a
                href={bloc.lien}
                rel="noreferrer"
                target="_blank"
                className="jl-cible jl-etiquette flex items-center underline decoration-1 underline-offset-8"
              >
                {t.infos.ouvrir_lien}
              </a>
            )}
          </section>
        );
      })}
    </main>
  );
}
