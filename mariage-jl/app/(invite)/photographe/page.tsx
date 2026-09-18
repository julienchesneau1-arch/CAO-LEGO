import Link from "next/link";
import { foyerCourant } from "@/lib/foyer";
import { galerie } from "@/lib/medias";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";
export const metadata = { title: "Le regard du photographe — J & L", robots: { index: false } };

/**
 * « Le regard du photographe » (brief §8.11, section distincte, accès
 * protégé). Ici, « protégé » veut dire : **depuis une invitation
 * reconnue seulement**. Le QR générique ouvre le programme et les infos ; il
 * n'ouvre pas les photos du photographe.
 *
 * C'est une interprétation, et elle est consignée comme telle dans
 * docs/QUESTIONS_BLOQUANTES.md (V4-02) : plutôt que d'inventer un code que
 * les mariés devraient transmettre, on s'appuie sur la barrière qui existe
 * déjà et que tout le monde franchit avec son faire-part.
 */
export default async function PagePhotographe() {
  const { t } = await langueEtTextes();
  const foyer = await foyerCourant();

  if (foyer === undefined) {
    return (
      <main className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-12">
        <h1 className="jl-titre text-3xl">{t.photographe.titre}</h1>
        <p className="jl-doux">{t.photographe.reserve}</p>
        <Link
          href="/retrouver"
          className="jl-cible jl-etiquette flex items-center underline decoration-1 underline-offset-8"
        >
          {t.retrouver.titre}
        </Link>
      </main>
    );
  }

  const medias = await galerie({ foyer: foyer.id, limite: 400, source: "photographe" });

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="jl-titre text-3xl">{t.photographe.titre}</h1>
        <p className="jl-doux">{t.photographe.intro}</p>
      </header>

      {medias.length === 0 ? (
        <p className="jl-doux">{t.photographe.attente}</p>
      ) : (
        <ul className="grid grid-cols-3 gap-2">
          {medias.map((media) => (
            <li key={media.id}>
              <Link
                href={`/photos/${media.id}?retour=${encodeURIComponent("/photographe")}`}
                aria-label={t.photos.ouvrir}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`/m/${media.id}`}
                  alt=""
                  loading="lazy"
                  className="aspect-square w-full object-cover"
                />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
