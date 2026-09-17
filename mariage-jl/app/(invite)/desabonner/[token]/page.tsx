import { Signature } from "@/components/Signature";
import { langueEtTextes } from "@/lib/page-commune";
import { desinscrireParJeton } from "@/lib/rappels";

export const dynamic = "force-dynamic";
export const metadata = { title: "Désinscription — J & L", robots: { index: false } };

/**
 * Désinscription depuis un e-mail (brief §11). Un tap suffit : pas de
 * connexion, pas de formulaire, pas de « êtes-vous sûr ». Le message est le
 * même que le jeton soit valide ou déjà utilisé — inutile d'apprendre à un
 * curieux si une adresse était inscrite.
 */
export default async function PageDesabonner({
  params,
}: {
  readonly params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const { t } = await langueEtTextes();
  await desinscrireParJeton(token);

  return (
    <main className="mx-auto flex max-w-xl flex-col gap-8 px-6 py-16">
      <Signature mention={t.accueil.signature} />
      <h1 className="jl-titre text-2xl">{t.rappels.desinscrit_titre}</h1>
      <p>{t.rappels.desinscrit_texte}</p>
    </main>
  );
}
