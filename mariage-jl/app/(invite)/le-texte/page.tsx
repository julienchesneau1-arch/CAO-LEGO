import { Palindrome } from "@/components/Palindrome";
import { Signature } from "@/components/Signature";
import { langueEtTextes } from "@/lib/page-commune";
import { PIVOT } from "@/lib/palindrome";

export const dynamic = "force-dynamic";
export const metadata = { title: "Le texte — J & L" };

/** « Le texte » (brief §8.8). Rien à expliquer, rien à ajouter. */
export default async function PageLeTexte() {
  const { t } = await langueEtTextes();

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-12 px-6 py-14">
      <Signature mention={t.accueil.signature} hauteurMonogramme={48} />
      <Palindrome
        pivot={PIVOT}
        revoir={t.texte.revoir}
        libelleListe={t.texte.lien}
        sensEndroit={t.texte.sens_endroit}
        sensInverse={t.texte.sens_inverse}
      />
    </main>
  );
}
