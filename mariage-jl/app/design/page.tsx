import { cookies } from "next/headers";
import { ConfortLecture } from "@/components/ConfortLecture";
import { DemoMouvement } from "@/components/DemoMouvement";
import { Filet } from "@/components/Filet";
import { Monogram } from "@/components/Monogram";
import { PileCouleurs } from "@/components/PileCouleurs";
import { Signature } from "@/components/Signature";
import { COOKIE_LANGUE, LANGUE_DEFAUT, dictionnaire, estLangue } from "@/lib/i18n";
import { MOMENTS, NEUTRES, arrondi2, contraste } from "@/lib/tokens";

export const metadata = { title: "Direction artistique — J & L" };

/** Page de validation interne de la direction artistique (brief §13, V0). */
export default async function PageDesign() {
  const magasin = await cookies();
  const valeur = magasin.get(COOKIE_LANGUE)?.value;
  const langue = estLangue(valeur) ? valeur : LANGUE_DEFAUT;
  const t = dictionnaire(langue);

  const mesures = MOMENTS.map((moment) => ({
    ...moment,
    nom: t.moments[moment.key].nom,
    moment: t.moments[moment.key].moment,
    surNoir: arrondi2(contraste(moment.hex, NEUTRES.noir)),
  }));

  const contrastesNeutres = [
    { libelle: `${NEUTRES.ivoire} / ${NEUTRES.noir}`, valeur: arrondi2(contraste(NEUTRES.ivoire, NEUTRES.noir)) },
    { libelle: `${NEUTRES.papierTexte} / ${NEUTRES.papierFond}`, valeur: arrondi2(contraste(NEUTRES.papierTexte, NEUTRES.papierFond)) },
    { libelle: `${NEUTRES.matiere} / ${NEUTRES.noir}`, valeur: arrondi2(contraste(NEUTRES.matiere, NEUTRES.noir)) },
  ];

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-14 px-6 py-14">
      <header className="flex flex-col gap-5">
        <Signature mention={t.accueil.signature} titreAccessible="Julien & Lauriane" />
        <h1 className="jl-titre text-3xl">{t.design.titre}</h1>
        <p className="jl-doux max-w-prose">{t.design.intro}</p>
        <hr className="jl-filet" />
      </header>

      <ConfortLecture
        langueCourante={langue}
        libelles={{
          titre: t.confort.titre,
          taille: t.confort.taille,
          tailles: {
            normale: t.confort.taille_normale,
            grande: t.confort.taille_grande,
            "tres-grande": t.confort.taille_tres_grande,
          },
          papier: t.confort.papier,
          mouvement: t.confort.mouvement,
          langue: t.confort.langue,
          bascule: t.langue.bascule,
        }}
      />

      <hr className="jl-filet" />

      <section aria-labelledby="couleurs" className="flex flex-col gap-6">
        <h2 id="couleurs" className="jl-etiquette">{t.design.section_couleurs}</h2>
        <ul className="flex flex-col gap-6">
          {mesures.map((moment) => (
            <li key={moment.id} className="flex flex-col gap-3">
              <div className="flex items-baseline gap-4">
                <span
                  aria-hidden="true"
                  style={{ width: 16, height: 16, background: moment.hex, display: "inline-block" }}
                />
                <span className="jl-titre text-xl">
                  {moment.id} · {moment.nom}
                </span>
                <span className="jl-doux">{moment.moment}</span>
              </div>
              <Filet couleur={moment.hex} />
              <p className="jl-doux text-sm">
                {moment.ral} · {moment.hex} · {t.design.contraste_sur_noir} :{" "}
                <span className="tabular-nums">{moment.surNoir.toFixed(2)}</span> ·{" "}
                {moment.surNoir >= 4.5
                  ? t.design.contraste_verdict_texte
                  : t.design.contraste_verdict_fil}{" "}
                — {t.design.role_fil}
              </p>
            </li>
          ))}
        </ul>
        <p className="jl-doux max-w-prose text-sm">{t.design.note_couleurs}</p>
      </section>

      <hr className="jl-filet" />

      <section aria-labelledby="neutres" className="flex flex-col gap-4">
        <h2 id="neutres" className="jl-etiquette">{t.design.section_neutres}</h2>
        <p>
          {t.neutres.fond} · <span className="tabular-nums">{NEUTRES.ivoire}</span>
        </p>
        <p>
          {t.neutres.matiere} · <span className="tabular-nums">{NEUTRES.matiere}</span>
        </p>
        <p>
          {t.neutres.noir} · <span className="tabular-nums">{NEUTRES.noir}</span>
        </p>
        <p>
          {t.neutres.papier} · <span className="tabular-nums">{NEUTRES.papierFond} / {NEUTRES.papierTexte}</span>
        </p>
        <PileCouleurs orientation="horizontale" />
      </section>

      <hr className="jl-filet" />

      <section aria-labelledby="typo" className="flex flex-col gap-6">
        <h2 id="typo" className="jl-etiquette">{t.design.section_typo}</h2>
        <p className="jl-titre text-5xl">03 · 06 · 2028</p>
        <p className="jl-doux text-sm">{t.design.typo_titre}</p>
        <p className="max-w-prose">
          Julien et Lauriane vont se marier. Après tout ce temps. Chacun connaît déjà l’autre par cœur.
        </p>
        <p className="jl-doux text-sm">{t.design.typo_texte}</p>
        <p className="jl-etiquette">{t.design.typo_etiquette}</p>
        <table className="w-full max-w-sm text-left">
          <caption className="jl-doux mb-2 text-left text-sm">
            Chiffres alignés et tabulaires — horaires d’exemple, non contractuels
          </caption>
          <tbody className="tabular-nums">
            <tr><td className="py-1">11 : 00</td><td className="jl-doux">→ 12 : 30</td></tr>
            <tr><td className="py-1">14 : 45</td><td className="jl-doux">→ 16 : 00</td></tr>
            <tr><td className="py-1">19 : 30</td><td className="jl-doux">→ 23 : 00</td></tr>
          </tbody>
        </table>
      </section>

      <hr className="jl-filet" />

      <section aria-labelledby="monogramme" className="flex flex-col gap-8">
        <h2 id="monogramme" className="jl-etiquette">{t.design.section_monogramme}</h2>
        <div className="flex flex-wrap items-end gap-10">
          <div className="flex flex-col items-center gap-3">
            <Monogram hauteur={96} variante="plein" titre="Julien & Lauriane" />
            <span className="jl-doux text-sm">{t.design.monogramme_plein}</span>
          </div>
          <div className="flex flex-col items-center gap-3">
            <Monogram hauteur={96} variante="contour" />
            <span className="jl-doux text-sm">{t.design.monogramme_contour}</span>
          </div>
          <div className="flex flex-col items-center gap-3">
            <Monogram hauteur={40} variante="plein" />
            <span className="jl-doux text-sm">40 px</span>
          </div>
          <div className="flex flex-col items-center gap-3">
            <Monogram hauteur={24} variante="plein" />
            <span className="jl-doux text-sm">24 px</span>
          </div>
        </div>
        <div className="flex flex-col gap-3">
          <p className="jl-doux text-sm">
            Comparaison à valider : tracé vectorisé (wght 400, servi par l’API) contre texte vivant en
            wght 470 demandé par le brief.
          </p>
          <div className="flex flex-wrap items-end gap-10">
            <Monogram hauteur={72} variante="plein" />
            <span
              className="jl-titre"
              style={{ fontSize: 72, lineHeight: 1, fontVariationSettings: '"opsz" 24, "wght" 470' }}
            >
              J<span style={{ fontStyle: "italic", fontSize: "95%" }}>&amp;</span>L
            </span>
          </div>
        </div>
        <Signature mention={t.accueil.signature} hauteurMonogramme={56} />
      </section>

      <hr className="jl-filet" />

      <section aria-labelledby="mouvement" className="flex flex-col gap-6">
        <h2 id="mouvement" className="jl-etiquette">{t.design.section_mouvement}</h2>
        <DemoMouvement libelle={t.design.mouvement_rejouer} note={t.design.mouvement_note} />
      </section>

      <hr className="jl-filet" />

      <section aria-labelledby="contrastes" className="flex flex-col gap-4">
        <h2 id="contrastes" className="jl-etiquette">{t.design.section_contraste}</h2>
        <ul className="flex flex-col gap-2">
          {contrastesNeutres.map((mesure) => (
            <li key={mesure.libelle} className="tabular-nums">
              {mesure.libelle} : {mesure.valeur.toFixed(2)}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
