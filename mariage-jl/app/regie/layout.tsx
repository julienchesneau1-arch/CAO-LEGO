import { Signature } from "@/components/Signature";
import { langueEtTextes } from "@/lib/page-commune";
import { exigerRegie } from "@/lib/regie";

export const dynamic = "force-dynamic";
export const metadata = { title: "Régie — J & L", robots: { index: false } };

/**
 * Écran régie (brief §9). Même garde que l'admin, rôle vérifié en base à
 * chaque requête. Aucune redirection : un visiteur sans accès n'apprend pas
 * qu'il existe une page de connexion ailleurs.
 */
export default async function RegieLayout({
  children,
}: {
  readonly children: React.ReactNode;
}) {
  const { t } = await langueEtTextes();
  const session = await exigerRegie();

  if (session === undefined) {
    return (
      <main className="mx-auto flex max-w-xl flex-col gap-6 px-6 py-16">
        <Signature mention={t.accueil.signature} />
        <h1 className="jl-titre text-2xl">{t.regie.refus}</h1>
        <p className="jl-doux">{t.admin.refus_detail}</p>
      </main>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-4">
        <Signature mention={t.accueil.signature} hauteurMonogramme={44} />
        <h1 className="jl-titre text-2xl">{t.regie.titre}</h1>
        <p className="jl-doux text-sm">{session.email}</p>
        <hr className="jl-filet" />
      </header>
      {children}
    </div>
  );
}
