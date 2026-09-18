import Link from "next/link";
import { livreDOr } from "@/lib/apres";
import { formaterDate } from "@/lib/i18n";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";
export const metadata = { title: "Le livre d’or — J & L", robots: { index: false } };

/**
 * Le livre d'or (brief §8.9). Seuls les messages dont l'auteur a choisi la
 * visibilité « livre d'or » y figurent ; les messages privés n'en sortent
 * jamais, et aucun nom de foyer n'est affiché.
 */
export default async function PageMessages() {
  const { langue, t } = await langueEtTextes();
  const messages = await livreDOr();

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="jl-titre text-3xl">{t.messages.titre}</h1>
        <p className="jl-doux">{t.messages.intro}</p>
      </header>

      {messages.length === 0 ? (
        <p className="jl-doux">{t.messages.aucun}</p>
      ) : (
        <ul className="flex flex-col gap-8">
          {messages.map((message) => (
            <li key={message.id} className="flex flex-col gap-2">
              <hr className="jl-filet" />
              <p className="jl-titre text-xl">{message.body}</p>
              <p className="jl-doux text-sm">{formaterDate(message.created_at, langue)}</p>
            </li>
          ))}
        </ul>
      )}

      <Link
        href="/loin"
        className="jl-cible jl-etiquette flex items-center underline decoration-1 underline-offset-8"
      >
        {t.messages.ecrire}
      </Link>
    </main>
  );
}
