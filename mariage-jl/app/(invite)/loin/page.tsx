import { FileAttente } from "@/components/FileAttente";
import { Signature } from "@/components/Signature";
import { contenus } from "@/lib/contenus";
import { foyerCourant } from "@/lib/foyer";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";
export const metadata = { title: "Ceux qui sont loin — J & L" };

/**
 * « Ceux qui sont loin » (brief §8.9, tel que tranché en section 0 bis) :
 * un message écrit, et plus tard un lien de diffusion privé — jamais un
 * lecteur intégré, jamais une infrastructure sur mesure.
 */
export default async function PageLoin({
  searchParams,
}: {
  readonly searchParams: Promise<{ etat?: string }>;
}) {
  const { langue, t } = await langueEtTextes();
  const { etat } = await searchParams;
  const foyer = await foyerCourant();
  const blocs = await contenus(langue);
  const diffusion = blocs["loin.diffusion"];
  const bordure = { borderColor: "var(--filet)" };

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-10 px-6 py-14">
      <Signature mention={t.accueil.signature} hauteurMonogramme={48} />
      <h1 className="jl-titre text-3xl">{t.loin.titre}</h1>

      <FileAttente
        libelles={{
          enAttente: t.horsligne.en_attente,
          enAttentePluriel: t.horsligne.en_attente_pluriel,
          envoye: t.horsligne.envoye,
        }}
      />

      {etat === "envoye" ? (
        <p aria-live="polite" className="jl-titre text-xl">
          {t.loin.envoye}
        </p>
      ) : null}
      {etat === "erreur" ? (
        <p role="alert" className="border p-4" style={bordure}>
          {t.loin.erreur}
        </p>
      ) : null}

      <p className="jl-doux max-w-prose">{t.loin.intro}</p>

      <form method="post" action="/loin/envoyer" data-file-attente className="flex flex-col gap-5">
        <label className="flex flex-col gap-2">
          <span className="jl-etiquette">{t.loin.champ}</span>
          <textarea
            name="message"
            rows={6}
            required
            minLength={2}
            maxLength={2000}
            className="border bg-transparent px-4 py-3"
            style={{ ...bordure, color: "var(--texte)" }}
          />
        </label>

        <fieldset className="flex flex-col gap-3">
          <legend className="jl-etiquette mb-2">{t.loin.visibilite}</legend>
          {(
            [
              ["private", t.loin.visibilite_prive],
              ["guestbook", t.loin.visibilite_livre],
            ] as const
          ).map(([valeur, libelle], index) => (
            <label key={valeur} className="jl-cible flex items-center gap-3">
              <input type="radio" name="visibilite" value={valeur} defaultChecked={index === 0} />
              <span>{libelle}</span>
            </label>
          ))}
        </fieldset>

        <button type="submit" className="jl-cible self-start border px-6 py-3" style={bordure}>
          {t.loin.envoyer}
        </button>
      </form>

      <hr className="jl-filet" />

      <section aria-labelledby="diffusion" className="flex flex-col gap-3">
        <h2 id="diffusion" className="jl-etiquette">
          {t.loin.diffusion_titre}
        </h2>
        {/* Le lien n'apparaît qu'aux foyers reconnus (brief §8.9 et §11). */}
        {foyer !== undefined && diffusion?.lien != null ? (
          <a
            href={diffusion.lien}
            rel="noreferrer"
            target="_blank"
            className="jl-cible flex items-center underline decoration-1 underline-offset-8"
          >
            {diffusion.texte === "" ? t.loin.diffusion_titre : diffusion.texte}
          </a>
        ) : (
          <p className="jl-doux">{t.loin.diffusion_attente}</p>
        )}
      </section>
    </main>
  );
}
