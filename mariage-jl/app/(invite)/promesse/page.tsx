import { Promesse } from "@/components/Promesse";
import { Signature } from "@/components/Signature";
import { env } from "@/lib/env";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";
export const metadata = { title: "La promesse — J & L" };

/**
 * « La promesse » (brief §8.10) : un vœu scellé jusqu'au 3 juin 2029.
 * Écho direct au texte — « Leur plus belle promesse reste à faire. »
 *
 * Aucun compteur de participation, aucun classement, rien qui compare les
 * invités entre eux (§17).
 */
export default async function PagePromesse() {
  const { t } = await langueEtTextes();
  const cle = env().JL_PROMESSE_CLE_PUBLIQUE ?? null;

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-10 px-6 py-14">
      <Signature mention={t.accueil.signature} hauteurMonogramme={48} />
      <header className="flex flex-col gap-4">
        <h1 className="jl-titre text-3xl">{t.promesse.titre}</h1>
        <p className="jl-titre text-xl">{t.promesse.echo}</p>
        <p className="jl-doux max-w-prose">{t.promesse.intro}</p>
      </header>
      <hr className="jl-filet" />
      <Promesse
        clePublique={cle === "" ? null : cle}
        libelles={{
          champ: t.promesse.champ,
          sceller: t.promesse.sceller,
          scelle: t.promesse.scelle,
          erreur: t.promesse.erreur,
          indisponible: t.promesse.indisponible,
        }}
      />
      <p className="jl-doux text-sm">{t.promesse.garantie}</p>
    </main>
  );
}
