import { cookies } from "next/headers";
import { Signature } from "@/components/Signature";
import { COOKIE_LANGUE, LANGUE_DEFAUT, dictionnaire, estLangue } from "@/lib/i18n";

export const dynamic = "force-dynamic";
export const metadata = { title: "Retrouver mon invitation — J & L" };

/** Chemin de secours si le QR ne fonctionne pas (brief §6). */
export default async function PageRetrouver({
  searchParams,
}: {
  readonly searchParams: Promise<{ etat?: string }>;
}) {
  const magasin = await cookies();
  const valeur = magasin.get(COOKIE_LANGUE)?.value;
  const t = dictionnaire(estLangue(valeur) ? valeur : LANGUE_DEFAUT);
  const { etat } = await searchParams;

  const message =
    etat === "debit"
      ? t.retrouver.trop_essais
      : etat === "expire"
        ? t.erreurs.lien_expire
        : etat === "inconnu"
          ? t.retrouver.echec
          : undefined;

  return (
    <main className="mx-auto flex max-w-xl flex-col gap-10 px-6 py-14">
      <Signature mention={t.accueil.signature} titreAccessible="Julien & Lauriane" />
      <h1 className="jl-titre text-3xl">{t.retrouver.titre}</h1>
      <p className="jl-doux max-w-prose">{t.retrouver.intro}</p>

      {message === undefined ? null : (
        <p role="alert" className="border p-4" style={{ borderColor: "var(--filet)" }}>
          {message}
        </p>
      )}

      <form method="post" action="/retrouver/verifier" className="flex flex-col gap-6">
        <label className="flex flex-col gap-2">
          <span className="jl-etiquette">{t.retrouver.champ_nom}</span>
          <input
            name="nom"
            required
            autoComplete="family-name"
            className="jl-cible border bg-transparent px-4 py-3"
            style={{ borderColor: "var(--filet)", color: "var(--texte)" }}
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className="jl-etiquette">{t.retrouver.champ_code}</span>
          <input
            name="code"
            required
            inputMode="text"
            autoCapitalize="characters"
            autoComplete="off"
            maxLength={8}
            className="jl-cible border bg-transparent px-4 py-3 tracking-[0.3em] uppercase"
            style={{ borderColor: "var(--filet)", color: "var(--texte)" }}
          />
        </label>
        <button
          type="submit"
          className="jl-cible border px-5 py-3 self-start"
          style={{ borderColor: "var(--filet)" }}
        >
          {t.retrouver.envoyer}
        </button>
      </form>

      <p className="jl-doux text-sm">
        {t.retrouver.aide_contact.replace("{contact}", t.commun.a_completer)}
      </p>
    </main>
  );
}
