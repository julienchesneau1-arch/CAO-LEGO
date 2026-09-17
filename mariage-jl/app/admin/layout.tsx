import { Signature } from "@/components/Signature";
import { exigerAdmin } from "@/lib/admin";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";
export const metadata = { title: "Espace des mariés — J & L", robots: { index: false } };

/**
 * Tout l'espace admin passe par ce garde (brief §11 : rôle vérifié côté
 * serveur). Aucune redirection : un visiteur sans lien valide ne doit même
 * pas apprendre qu'il existe une page de connexion ailleurs.
 */
export default async function AdminLayout({
  children,
}: {
  readonly children: React.ReactNode;
}) {
  const { t } = await langueEtTextes();
  const session = await exigerAdmin();

  if (session === undefined) {
    return (
      <main className="mx-auto flex max-w-xl flex-col gap-6 px-6 py-16">
        <Signature mention={t.accueil.signature} />
        <h1 className="jl-titre text-2xl">{t.admin.refus}</h1>
        <p className="jl-doux">{t.admin.refus_detail}</p>
      </main>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-4">
        <Signature mention={t.accueil.signature} hauteurMonogramme={44} />
        <nav aria-label={t.admin.titre} className="flex gap-6">
          <a href="/admin" className="jl-cible jl-etiquette flex items-center">
            {t.admin.tableau}
          </a>
          <a href="/admin/invites" className="jl-cible jl-etiquette flex items-center">
            {t.admin.invites}
          </a>
        </nav>
        <p className="jl-doux text-sm">{session.email}</p>
        <hr className="jl-filet" />
      </header>
      {children}
    </div>
  );
}
