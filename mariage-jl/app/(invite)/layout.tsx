import { Navigation } from "@/components/Navigation";
import { periodeCourante } from "@/lib/foyer";
import { onglets } from "@/lib/navigation";
import { langueEtTextes } from "@/lib/page-commune";
import type { Periode } from "@/lib/periode";

/**
 * Espace des invités : c'est ici que vit la barre de navigation (brief §7).
 * L'espace des mariés et la page de validation de la direction artistique
 * sont en dehors de ce groupe : ils n'affichent pas les onglets des invités.
 */
export default async function LayoutInvite({
  children,
}: {
  readonly children: React.ReactNode;
}) {
  const { t } = await langueEtTextes();

  // Si la base est injoignable, la navigation ne doit pas emporter la page :
  // on retombe sur la période « avant », qui est la plus longue.
  let periode: Periode = "avant";
  try {
    periode = await periodeCourante();
  } catch {
    periode = "avant";
  }

  return (
    <>
      <div className="flex-1">{children}</div>
      <Navigation onglets={onglets(periode)} libelles={t.navigation} />
    </>
  );
}
