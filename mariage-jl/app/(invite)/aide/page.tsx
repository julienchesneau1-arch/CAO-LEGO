import { itineraires } from "@/lib/cartes";
import { contacts, contenus } from "@/lib/contenus";
import { numeroComposable } from "@/lib/contenus-admin";
import { formater } from "@/lib/i18n";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";
export const metadata = { title: "Aide — J & L", robots: { index: false } };

/**
 * Aide (brief §8.6 et §0 bis). Deux boutons d'appel, l'itinéraire, le Wi-Fi.
 * « Je suis en retard » et « J'ai perdu un objet » sont **coupés** par la
 * section 0 bis : la régie s'appelle, elle ne se notifie pas.
 *
 * Un contact sans numéro n'affiche **pas** de bouton d'appel : un bouton qui
 * ne compose rien serait pire que pas de bouton du tout.
 */
export default async function PageAide() {
  const { langue, t } = await langueEtTextes();
  const [liste, blocs] = await Promise.all([contacts(langue), contenus(langue)]);
  const wifi = blocs["jour.wifi"];
  const bordure = { borderColor: "var(--filet)" };

  const nomCourt = (cle: string): string =>
    cle === "aide.regie" ? t.aide.regie : t.aide.temoin;

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-10 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="jl-titre text-3xl">{t.aide.titre}</h1>
        <p className="jl-doux">{t.aide.intro}</p>
      </header>

      <section aria-labelledby="appeler" className="flex flex-col gap-4">
        <h2 id="appeler" className="jl-etiquette">
          {t.aide.titre}
        </h2>
        <ul className="flex flex-col gap-4">
          {liste.map((contact) => (
            <li key={contact.cle} className="flex flex-col gap-2">
              <p className="jl-etiquette">{nomCourt(contact.cle)}</p>
              {contact.telephone === null ? (
                <p className="jl-doux text-sm">{t.aide.sans_numero}</p>
              ) : (
                <a
                  href={`tel:${numeroComposable(contact.telephone)}`}
                  className="jl-cible flex items-center border px-5 py-3"
                  style={bordure}
                >
                  {formater(t.aide.appeler, { nom: contact.nom })}
                </a>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="perdu" className="flex flex-col gap-4">
        <hr className="jl-filet" />
        <h2 id="perdu" className="jl-etiquette">
          {t.aide.perdu_titre}
        </h2>
        <p className="jl-doux">{t.aide.perdu_texte}</p>
        <p>{t.infos.adresse}</p>
        <ul className="flex flex-wrap gap-3">
          {itineraires(t.infos.adresse).map((itineraire) => (
            <li key={itineraire.cle}>
              <a
                href={itineraire.url}
                rel="noreferrer"
                target="_blank"
                className="jl-cible flex items-center border px-4 py-3"
                style={bordure}
              >
                {t.infos[`itineraire_${itineraire.cle}` as "itineraire_apple"]}
              </a>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="wifi" className="flex flex-col gap-3">
        <hr className="jl-filet" />
        <h2 id="wifi" className="jl-etiquette">
          {t.aide.wifi_titre}
        </h2>
        <p className={wifi === undefined ? "jl-doux" : ""}>
          {wifi === undefined || wifi.texte.trim() === "" ? t.infos.attente : wifi.texte}
        </p>
      </section>
    </main>
  );
}
