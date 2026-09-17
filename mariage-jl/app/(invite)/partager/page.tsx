import { cookies, headers } from "next/headers";
import { LienCopiable } from "@/components/LienCopiable";
import { foyerCourant } from "@/lib/foyer";
import { COOKIE_LANGUE, LANGUE_DEFAUT, dictionnaire, estLangue, formater } from "@/lib/i18n";
import { JOURS_VALIDITE, OUVERTURES_MAX } from "@/lib/partage";

export const dynamic = "force-dynamic";
export const metadata = { title: "Partager l'accès — J & L" };

/**
 * « Partager l'accès au foyer » (brief §6) — c'est aussi « un proche répond
 * pour moi » : un seul mécanisme, décidé en section 0 bis.
 */
export default async function PagePartager({
  searchParams,
}: {
  readonly searchParams: Promise<{ jeton?: string; etat?: string }>;
}) {
  const magasin = await cookies();
  const valeur = magasin.get(COOKIE_LANGUE)?.value;
  const t = dictionnaire(estLangue(valeur) ? valeur : LANGUE_DEFAUT);
  const { jeton } = await searchParams;
  const foyer = await foyerCourant();

  if (foyer === undefined) {
    return (
      <main className="mx-auto flex max-w-xl flex-col gap-8 px-6 py-14">
        <h1 className="jl-titre text-3xl">{t.partager.titre}</h1>
        <p>{t.partager.non_reconnu}</p>
      </main>
    );
  }

  const entetes = await headers();
  const hote = entetes.get("x-forwarded-host") ?? entetes.get("host") ?? "";
  const protocole = entetes.get("x-forwarded-proto") ?? "https";
  const lien = jeton === undefined ? undefined : `${protocole}://${hote}/p/${jeton}`;

  return (
    <main className="mx-auto flex max-w-xl flex-col gap-8 px-6 py-14">
      <h1 className="jl-titre text-3xl">{t.partager.titre}</h1>
      <p className="jl-doux max-w-prose">{t.partager.intro}</p>

      {lien === undefined ? (
        <form method="post" action="/partager/creer">
          <button
            type="submit"
            className="jl-cible border px-5 py-3"
            style={{ borderColor: "var(--filet)" }}
          >
            {t.partager.creer}
          </button>
        </form>
      ) : (
        <>
          <LienCopiable
            lien={lien}
            libelleCopier={t.partager.copier}
            libelleCopie={t.partager.copie}
          />
          <p className="jl-doux text-sm">
            {formater(t.partager.validite, {
              jours: String(JOURS_VALIDITE),
              ouvertures: String(OUVERTURES_MAX),
            })}
          </p>
        </>
      )}
    </main>
  );
}
