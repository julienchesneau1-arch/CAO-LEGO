import { Film } from "@/components/Film";
import { contenus } from "@/lib/contenus";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";
export const metadata = { title: "Le film de la journée — J & L", robots: { index: false } };

/**
 * Le film de la journée (brief §8.11, « si fourni »). Son adresse s'écrit
 * depuis l'admin comme le reste : tant qu'elle n'est pas écrite, l'écran dit
 * qu'il n'y a rien, au lieu de montrer un lecteur vide.
 */
export default async function PageFilm() {
  const { langue, t } = await langueEtTextes();
  const blocs = await contenus(langue);
  const bloc = blocs["apres.film"];
  const lien = bloc?.lien ?? null;

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-8 px-6 py-12">
      <h1 className="jl-titre text-3xl">{t.film.titre}</h1>
      {bloc === undefined ||
      bloc.texte.trim() === "" ||
      bloc.texte.includes("[À COMPLÉTER]") ||
      bloc.texte.includes("[TO BE COMPLETED]") ? null : (
        <p>{bloc.texte}</p>
      )}
      <Film
        {...(lien === null ? {} : { url: lien })}
        libelles={{ titre: t.film.titre, attente: t.film.attente, lire: t.film.lire }}
      />
    </main>
  );
}
