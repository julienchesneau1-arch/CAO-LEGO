import Link from "next/link";
import { EnvoyerSouvenir } from "@/components/EnvoyerSouvenir";
import { foyerCourant } from "@/lib/foyer";
import { etatJournee } from "@/lib/journee";
import { consentementMedias } from "@/lib/medias";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";
export const metadata = { title: "Partager un souvenir — J & L", robots: { index: false } };

/**
 * « Partager un souvenir » (brief §8.7). Le consentement est demandé **une
 * fois**, avant le premier envoi, et il porte la visibilité : aux invités,
 * ou aux mariés seulement — c'est la prudence que le brief demande pour les
 * photos d'enfants.
 */
export default async function PageEnvoyer({
  searchParams,
}: {
  readonly searchParams: Promise<{ etat?: string }>;
}) {
  const { t } = await langueEtTextes();
  const { etat } = await searchParams;
  const foyer = await foyerCourant();
  const [journee, accord] = await Promise.all([
    etatJournee(),
    foyer === undefined ? Promise.resolve(undefined) : consentementMedias(foyer.id),
  ]);
  const bordure = { borderColor: "var(--filet)" };

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="jl-titre text-3xl">{t.envoi.titre}</h1>
        <Link
          href="/photos"
          className="jl-cible jl-etiquette flex items-center underline decoration-1 underline-offset-8"
        >
          {t.photos.retour}
        </Link>
      </header>

      {etat === "consenti" ? (
        <p aria-live="polite" className="jl-doux">
          {t.envoi.consenti}
        </p>
      ) : null}
      {etat === "retire" ? (
        <p aria-live="polite" className="jl-doux">
          {t.envoi.retire}
        </p>
      ) : null}
      {etat === "erreur" ? (
        <p role="alert" className="border p-4" style={bordure}>
          {t.photos.erreur}
        </p>
      ) : null}

      {foyer === undefined ? (
        <p role="alert" className="border p-4" style={bordure}>
          {t.photos.sans_foyer}
        </p>
      ) : accord === undefined ? (
        <section aria-labelledby="consentement" className="flex flex-col gap-5">
          <h2 id="consentement" className="jl-etiquette">
            {t.envoi.consentement_titre}
          </h2>
          <p>{t.envoi.consentement_texte}</p>
          <p className="jl-doux">{t.envoi.consentement_enfants}</p>
          <form method="post" action="/photos/consentement" className="flex flex-col gap-4">
            <fieldset className="flex flex-col gap-3">
              <legend className="jl-etiquette">{t.envoi.consentement_accepter}</legend>
              <label className="jl-cible flex items-center gap-3">
                <input type="radio" name="visibilite" value="invites" defaultChecked />
                <span>{t.envoi.consentement_invites}</span>
              </label>
              <label className="jl-cible flex items-center gap-3">
                <input type="radio" name="visibilite" value="maries" />
                <span>{t.envoi.consentement_maries}</span>
              </label>
            </fieldset>
            <button type="submit" className="jl-cible self-start border px-5 py-3" style={bordure}>
              {t.envoi.consentement_accepter}
            </button>
          </form>
        </section>
      ) : (
        <>
          <p className="jl-doux">
            {accord.visibilite === "maries" ? t.envoi.accord_actuel_maries : t.envoi.accord_actuel}
          </p>
          <EnvoyerSouvenir
            momentCourant={journee.courant?.id ?? null}
            suspendu={journee.envoisEnPause}
            libelles={{
              titre: t.envoi.titre,
              choisir: t.envoi.choisir,
              wifi: t.envoi.wifi,
              rien: t.envoi.rien,
              en_attente: t.envoi.en_attente,
              partis: t.envoi.partis,
              refuses: t.envoi.refuses,
              travail: t.envoi.travail,
              suspendu: t.envoi.suspendu,
              envoyer_maintenant: t.envoi.envoyer_maintenant,
              iphone: t.envoi.iphone,
              video_trop_longue: t.envoi.video_trop_longue,
              type_refuse: t.envoi.type_refuse,
            }}
          />
          <form method="post" action="/photos/consentement">
            <input type="hidden" name="retirer" value="1" />
            <button type="submit" className="jl-cible jl-doux border px-5 py-3" style={bordure}>
              {t.envoi.retirer}
            </button>
          </form>
        </>
      )}
    </main>
  );
}
