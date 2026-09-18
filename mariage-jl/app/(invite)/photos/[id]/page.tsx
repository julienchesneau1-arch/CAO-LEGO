import Link from "next/link";
import { notFound } from "next/navigation";
import { Filet } from "@/components/Filet";
import { foyerCourant } from "@/lib/foyer";
import { media } from "@/lib/medias";
import { moments, nomMoment } from "@/lib/moments";
import { langueEtTextes } from "@/lib/page-commune";
import { MOMENTS } from "@/lib/tokens";

export const dynamic = "force-dynamic";
export const metadata = { title: "Un souvenir — J & L", robots: { index: false } };

const couleur = (id: string | null): string =>
  MOMENTS.find((moment) => moment.id === id)?.hex ?? "var(--filet)";

/**
 * Un souvenir en grand, avec les deux seules actions que le brief prévoit :
 * « j'aime » (privé, pour le tri) et « demander le retrait » (en un tap, et
 * la photo est masquée avant même que nous la regardions).
 */
export default async function PageUnSouvenir({
  params,
  searchParams,
}: {
  readonly params: Promise<{ id: string }>;
  readonly searchParams: Promise<{ retour?: string }>;
}) {
  const { langue, t } = await langueEtTextes();
  const { id } = await params;
  const { retour } = await searchParams;
  const foyer = await foyerCourant();

  const ligne = await media(id);
  if (ligne === undefined || ligne.status !== "published") notFound();
  if (
    ligne.visibilite === "maries" &&
    (foyer === undefined || ligne.household_id !== foyer.id)
  ) {
    notFound();
  }

  const liste = await moments();
  const moment = liste.find((candidat) => candidat.id === ligne.moment_id);
  const propre = retour !== undefined && retour.startsWith("/photos") ? retour : "/photos";
  const bordure = { borderColor: "var(--filet)" };

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-10">
      <Link
        href={propre}
        className="jl-cible jl-etiquette flex items-center underline decoration-1 underline-offset-8"
      >
        {t.photos.retour}
      </Link>

      <Filet couleur={couleur(ligne.moment_id)} />
      {moment === undefined ? null : (
        <p className="jl-etiquette">{nomMoment(moment, langue)}</p>
      )}

      {ligne.kind === "video" ? (
        // eslint-disable-next-line jsx-a11y/media-has-caption
        <video src={`/m/${ligne.id}`} controls playsInline className="w-full" />
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={`/m/${ligne.id}`} alt="" className="w-full" />
      )}

      {ligne.visibilite === "maries" ? (
        <p className="jl-doux text-sm">{t.photos.maries_seulement}</p>
      ) : null}

      {foyer === undefined ? null : (
        <form method="post" action="/photos/aimer">
          <input type="hidden" name="media" value={ligne.id} />
          <input type="hidden" name="retour" value={`/photos/${ligne.id}`} />
          <button type="submit" className="jl-cible border px-5 py-3" style={bordure}>
            {t.photos.aimer}
          </button>
        </form>
      )}

      <section aria-labelledby="retrait" className="flex flex-col gap-4">
        <hr className="jl-filet" />
        <h2 id="retrait" className="jl-etiquette">
          {t.photos.retrait_titre}
        </h2>
        <p className="jl-doux">{t.photos.retrait_texte}</p>
        <form method="post" action="/photos/retrait" className="flex flex-col gap-4">
          <input type="hidden" name="media" value={ligne.id} />
          <label className="flex flex-col gap-2">
            <span className="jl-etiquette">{t.photos.retrait_raison}</span>
            <textarea
              name="raison"
              rows={2}
              maxLength={500}
              className="jl-cible border bg-transparent px-4 py-3"
              style={{ ...bordure, color: "var(--texte)" }}
            />
          </label>
          <button type="submit" className="jl-cible self-start border px-5 py-3" style={bordure}>
            {t.photos.retrait_envoyer}
          </button>
        </form>
      </section>
    </main>
  );
}
