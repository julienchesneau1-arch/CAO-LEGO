import Link from "next/link";
import { Filet } from "@/components/Filet";
import { foyerCourant } from "@/lib/foyer";
import { galerie, signauxDuFoyer } from "@/lib/medias";
import { moments, nomMoment } from "@/lib/moments";
import { langueEtTextes } from "@/lib/page-commune";
import { MOMENTS } from "@/lib/tokens";

export const dynamic = "force-dynamic";
export const metadata = { title: "Les souvenirs — J & L", robots: { index: false } };

const couleur = (id: string | null): string =>
  MOMENTS.find((moment) => moment.id === id)?.hex ?? "var(--filet)";

/**
 * Galerie partagée (brief §8.7) : grille sobre de trois colonnes, filtres
 * par moment et « Mes souvenirs ». Aucun compteur n'est affiché (§17) : le
 * « j'aime » existe pour trier, pas pour classer les invités entre eux.
 *
 * « Photos où je suis » est **coupé** par la section 0 bis, remplacé par
 * « Mes souvenirs » et « Demander le retrait ».
 */
export default async function PagePhotos({
  searchParams,
}: {
  readonly searchParams: Promise<{ moment?: string; mes?: string; etat?: string }>;
}) {
  const { langue, t } = await langueEtTextes();
  const { moment: momentBrut, mes, etat } = await searchParams;
  const foyer = await foyerCourant();

  const liste = await moments();
  const momentId = liste.some((candidat) => candidat.id === momentBrut) ? momentBrut : undefined;
  const mesMedias = mes === "1";

  const [medias, aimes] = await Promise.all([
    galerie({
      ...(momentId === undefined ? {} : { momentId }),
      ...(foyer === undefined ? {} : { foyer: foyer.id }),
      ...(mesMedias ? { mesMedias: true } : {}),
    }),
    foyer === undefined ? new Set<string>() : signauxDuFoyer(foyer.id),
  ]);

  const lien = (parametres: Readonly<Record<string, string>>): string => {
    const url = new URLSearchParams(parametres);
    const chaine = url.toString();
    return chaine === "" ? "/photos" : `/photos?${chaine}`;
  };
  const nomDuMoment = (id: string | null): string => {
    const trouve = liste.find((candidat) => candidat.id === id);
    return trouve === undefined ? "" : nomMoment(trouve, langue);
  };

  const ici = lien({
    ...(momentId === undefined ? {} : { moment: momentId }),
    ...(mesMedias ? { mes: "1" } : {}),
  });

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="jl-titre text-3xl">{t.photos.titre}</h1>
        <p className="jl-doux">{t.photos.intro}</p>
      </header>

      {etat === "retire" ? (
        <p aria-live="polite" className="jl-doux">
          {t.photos.retire}
        </p>
      ) : null}
      {etat === "erreur" ? (
        <p role="alert" className="border p-4" style={{ borderColor: "var(--filet)" }}>
          {t.photos.erreur}
        </p>
      ) : null}
      {etat === "sans_foyer" ? (
        <p role="alert" className="border p-4" style={{ borderColor: "var(--filet)" }}>
          {t.photos.sans_foyer}
        </p>
      ) : null}

      <Link
        href="/photos/envoyer"
        className="jl-cible self-start border px-5 py-3"
        style={{ borderColor: "var(--filet)" }}
      >
        {t.photos.envoyer}
      </Link>

      <nav aria-label={t.photos.filtre_moment} className="flex flex-col gap-3">
        <ul className="flex flex-wrap gap-x-4 gap-y-2">
          <li>
            <a
              href="/photos"
              aria-current={momentId === undefined && !mesMedias ? "page" : undefined}
              className="jl-cible jl-etiquette flex items-center"
              style={{
                color: momentId === undefined && !mesMedias ? "var(--texte)" : "var(--doux)",
              }}
            >
              {t.photos.filtre_tous}
            </a>
          </li>
          {foyer === undefined ? null : (
            <li>
              <a
                href={lien({ mes: "1" })}
                aria-current={mesMedias ? "page" : undefined}
                className="jl-cible jl-etiquette flex items-center"
                style={{ color: mesMedias ? "var(--texte)" : "var(--doux)" }}
              >
                {t.photos.filtre_mes}
              </a>
            </li>
          )}
        </ul>
        <ul className="flex flex-wrap gap-x-4 gap-y-2">
          {liste.map((moment) => (
            <li key={moment.id}>
              <a
                href={lien({
                  moment: moment.id,
                  ...(mesMedias ? { mes: "1" } : {}),
                })}
                aria-current={momentId === moment.id ? "page" : undefined}
                className="jl-cible flex items-center gap-2"
                style={{ color: momentId === moment.id ? "var(--texte)" : "var(--doux)" }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    display: "block",
                    width: "0.75rem",
                    height: "2px",
                    background: couleur(moment.id),
                  }}
                />
                <span className="jl-etiquette">{nomMoment(moment, langue)}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>

      <Filet couleur={couleur(momentId ?? null)} />

      {medias.length === 0 ? (
        <p className="jl-doux">{t.photos.aucune}</p>
      ) : (
        <ul className="grid grid-cols-3 gap-2">
          {medias.map((media) => (
            <li key={media.id} className="relative">
              {/*
                Une vignette n'a pas de texte : sans nom accessible, le lien
                serait annoncé « lien » et rien d'autre. Le moment donne le
                seul repère honnête — décrire la photo demanderait de la
                regarder, ce que personne ne fait ici.
              */}
              <Link
                href={`/photos/${media.id}?retour=${encodeURIComponent(ici)}`}
                aria-label={`${t.photos.ouvrir}${
                  media.moment_id === null ? "" : ` — ${nomDuMoment(media.moment_id)}`
                }`}
              >
                {media.kind === "video" ? (
                  <span
                    className="jl-cible flex aspect-square items-center justify-center border"
                    style={{ borderColor: couleur(media.moment_id) }}
                  >
                    <span className="jl-etiquette">{t.photos.video}</span>
                  </span>
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={`/m/${media.id}`}
                    alt=""
                    loading="lazy"
                    className="aspect-square w-full object-cover"
                    style={{ borderTop: `2px solid ${couleur(media.moment_id)}` }}
                  />
                )}
              </Link>
              {aimes.has(media.id) ? (
                <span
                  aria-hidden="true"
                  className="absolute right-1 top-1 block h-2 w-2"
                  style={{ background: "var(--texte)" }}
                />
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
