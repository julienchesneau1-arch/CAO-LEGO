import { formater } from "@/lib/i18n";
import { galerie } from "@/lib/medias";
import { langueEtTextes } from "@/lib/page-commune";

export const dynamic = "force-dynamic";

const BORDURE = { borderColor: "var(--filet)" };

/**
 * Dépôt des photos du photographe (brief §8.11). Le formulaire est un envoi
 * de fichiers classique, sans file d'attente : les mariés le font depuis un
 * ordinateur, au calme, pas depuis un téléphone au milieu d'une fête.
 */
export default async function PageAdminPhotographe({
  searchParams,
}: {
  readonly searchParams: Promise<{ ajoutees?: string; refusees?: string }>;
}) {
  const { t } = await langueEtTextes();
  const { ajoutees, refusees } = await searchParams;
  const medias = await galerie({ limite: 200, source: "photographe", pourLesMaries: true });

  return (
    <main className="flex flex-col gap-8">
      <h1 className="jl-titre text-2xl">{t.admin_photographe.titre}</h1>
      <p className="jl-doux">{t.admin_photographe.intro}</p>

      {ajoutees === undefined ? null : (
        <p aria-live="polite" className="jl-doux">
          {formater(t.admin_photographe.envoyees, { nombre: ajoutees })}
          {refusees === undefined || refusees === "0"
            ? ""
            : ` ${formater(t.admin_photographe.refusees, { nombre: refusees })}`}
        </p>
      )}

      <form
        method="post"
        action="/admin/photographe/televerser"
        encType="multipart/form-data"
        className="flex flex-col gap-4"
      >
        <label className="flex flex-col gap-2">
          <span className="jl-etiquette">{t.admin_photographe.choisir}</span>
          <input
            type="file"
            name="fichiers"
            accept="image/jpeg,image/png"
            multiple
            required
            className="jl-cible border bg-transparent px-4 py-3"
            style={{ ...BORDURE, color: "var(--texte)" }}
          />
        </label>
        <button type="submit" className="jl-cible self-start border px-5 py-3" style={BORDURE}>
          {t.admin_contenus.enregistrer}
        </button>
      </form>

      <hr className="jl-filet" />

      {medias.length === 0 ? (
        <p className="jl-doux">{t.admin_photographe.aucune}</p>
      ) : (
        <ul className="grid grid-cols-3 gap-3">
          {medias.map((media) => (
            <li key={media.id} className="flex flex-col gap-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`/m/${media.id}`}
                alt=""
                loading="lazy"
                className="aspect-square w-full object-cover"
              />
              <form method="post" action="/admin/photographe/retirer">
                <input type="hidden" name="media" value={media.id} />
                <button
                  type="submit"
                  className="jl-cible jl-etiquette w-full border px-2 py-2"
                  style={BORDURE}
                >
                  {t.admin_photographe.retirer}
                </button>
              </form>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
