import Link from "next/link";
import { Signature } from "@/components/Signature";
import { dictionnaire } from "@/lib/i18n";

export const metadata = { title: "Hors ligne — J & L" };

/**
 * Écran servi quand une page non mise en cache est demandée sans réseau
 * (brief §3 : « Pas de réseau pour l'instant. Tout ce que vous faites sera
 * envoyé dès son retour. »).
 *
 * Volontairement **statique et bilingue** : il est précaché à l'installation,
 * donc il ne peut pas dépendre du cookie de langue de l'invité — et il ne
 * contient aucune donnée personnelle, ce qui est la condition pour qu'il ait
 * le droit de vivre dans le cache.
 */
export default function PageHorsLigne() {
  const fr = dictionnaire("fr");
  const en = dictionnaire("en");

  return (
    <main className="mx-auto flex max-w-xl flex-col gap-8 px-6 py-16">
      <Signature mention={fr.accueil.signature} />
      <h1 className="jl-titre text-2xl">{fr.horsligne.titre}</h1>
      <p>{fr.horsligne.texte}</p>
      <p className="jl-doux">{en.horsligne.texte}</p>
      <hr className="jl-filet" />
      <p className="jl-doux">{fr.horsligne.disponible}</p>
      <ul className="flex flex-col gap-3">
        {(
          [
            ["/programme", fr.navigation.programme],
            ["/infos", fr.navigation.infos],
            ["/faq", fr.navigation.faq],
          ] as const
        ).map(([chemin, libelle]) => (
          <li key={chemin}>
            <Link
              href={chemin}
              className="jl-cible flex items-center underline decoration-1 underline-offset-8"
            >
              {libelle}
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
