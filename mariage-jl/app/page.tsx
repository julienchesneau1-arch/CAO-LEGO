import Link from "next/link";
import { cookies } from "next/headers";
import { Signature } from "@/components/Signature";
import { COOKIE_LANGUE, LANGUE_DEFAUT, dictionnaire, estLangue } from "@/lib/i18n";

/**
 * V0 : page d'attente. Elle ne contient que des informations connues
 * (brief §2). L'accueil « Avant » est livré en V1.
 */
export default async function Accueil() {
  const magasin = await cookies();
  const valeur = magasin.get(COOKIE_LANGUE)?.value;
  const t = dictionnaire(estLangue(valeur) ? valeur : LANGUE_DEFAUT).accueil;

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-10 px-6 py-16">
      <div className="jl-apparition">
        <Signature mention={t.signature} titreAccessible="Julien & Lauriane" />
      </div>
      <div className="flex flex-col gap-3">
        <p className="jl-titre text-4xl tracking-[0.12em]">{t.date}</p>
        <p className="jl-doux">{t.lieu}</p>
      </div>
      <hr className="jl-filet" />
      <p className="max-w-prose leading-relaxed">{t.attente}</p>
      <Link href="/design" className="jl-etiquette jl-cible flex items-center underline decoration-1 underline-offset-8">
        {t.lien_design}
      </Link>
    </main>
  );
}
