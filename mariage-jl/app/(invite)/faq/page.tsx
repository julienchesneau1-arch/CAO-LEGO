import { RechercheFaq } from "@/components/RechercheFaq";
import { faq } from "@/lib/contenus";
import { formater } from "@/lib/i18n";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";
export const metadata = { title: "Questions fréquentes — J & L" };

export default async function PageFaq() {
  const { langue, t } = await langueEtTextes();
  const questions = await faq(langue);

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-8 px-6 py-12">
      <header className="flex flex-col gap-3">
        <h1 className="jl-titre text-3xl">{t.faq.titre}</h1>
        <p className="jl-doux">{formater(t.faq.compte, { nombre: String(questions.length) })}</p>
      </header>
      <RechercheFaq
        questions={questions}
        libelles={{
          recherche: t.faq.recherche,
          aucun: t.faq.aucun_resultat,
          reponseAttendue: t.faq.reponse_attendue,
        }}
      />
    </main>
  );
}
