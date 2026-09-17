import Link from "next/link";
import { cookies } from "next/headers";
import { CarteAFaire } from "@/components/CarteAFaire";
import { CompteARebours } from "@/components/CompteARebours";
import { FiletsEtapes } from "@/components/FiletsEtapes";
import { Film } from "@/components/Film";
import { PremierLancement } from "@/components/PremierLancement";
import { Signature } from "@/components/Signature";
import { restant } from "@/lib/compte";
import { env } from "@/lib/env";
import { aRepondu, foyerCourant, parametres, periodeCourante } from "@/lib/foyer";
import {
  COOKIE_LANGUE,
  LANGUE_DEFAUT,
  dictionnaire,
  estLangue,
  formater,
  formaterDate,
} from "@/lib/i18n";
import { etapesFranchies } from "@/lib/periode";

export const dynamic = "force-dynamic";

/**
 * Accueil (brief §7 et §8.1). Le contenu suit la période : « Avant » et
 * « Semaine J » montrent le film, le compte à rebours et la carte « À faire ».
 * Les périodes « Jour J » et « Après » arrivent en V3 et V4 : l'écran le dit
 * plutôt que d'afficher une page vide.
 */
export default async function Accueil() {
  const magasin = await cookies();
  const valeurLangue = magasin.get(COOKIE_LANGUE)?.value;
  const langue = estLangue(valeurLangue) ? valeurLangue : LANGUE_DEFAUT;
  const t = dictionnaire(langue);

  const maintenant = new Date();
  const parametresJournee = await parametres();
  const periode = await periodeCourante(maintenant);
  const foyer = await foyerCourant();
  const repondu = foyer === undefined ? false : await aRepondu(foyer.id);

  const etapes = etapesFranchies(maintenant, parametresJournee.date_mariage, repondu).map(
    (etape) => ({
      libelle: t.accueil[`etape_${etape.etape}` as const],
      franchie: etape.franchie,
    }),
  );

  const bienvenue =
    foyer === undefined
      ? t.accueil.bienvenue_generique
      : formater(t.accueil.bienvenue, { foyer: foyer.label_public });

  const limite = parametresJournee.date_limite_reponse;
  const action = repondu
    ? { texte: t.accueil.a_faire_rien }
    : {
        texte:
          limite === null
            ? t.accueil.a_faire_repondre
            : formater(t.accueil.a_faire_repondre_avant, {
                date: formaterDate(limite, langue),
              }),
        lien: "/reponse",
      };

  const { JL_FILM_URL, JL_FILM_POSTER_URL } = env();

  return (
    <>
      <PremierLancement
        langueCourante={langue}
        libelles={{
          passer: t.lancement.passer,
          suivant: t.lancement.suivant,
          ecran1: t.lancement.ecran1,
          ecran3_titre: t.lancement.ecran3_titre,
          ecran3_texte: t.lancement.ecran3_texte,
          bienvenue,
          confort: {
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
          },
        }}
      />

      <main className="mx-auto flex max-w-2xl flex-col gap-12 px-6 py-14">
        <header className="flex flex-col gap-6">
          <Signature mention={t.accueil.signature} titreAccessible="Julien & Lauriane" />
          <p className="jl-titre text-4xl tracking-[0.12em]">{t.accueil.date}</p>
          <p className="jl-doux">{t.accueil.lieu}</p>
          <p>{bienvenue}</p>
        </header>

        <hr className="jl-filet" />

        {periode === "avant" || periode === "semaine" ? (
          <>
            <CompteARebours
              cibleIso={parametresJournee.date_mariage.toISOString()}
              initial={restant(parametresJournee.date_mariage.getTime(), maintenant.getTime())}
              libelles={{
                titre: t.accueil.compte_titre,
                jours: t.accueil.compte_jours,
                heures: t.accueil.compte_heures,
                minutes: t.accueil.compte_minutes,
                secondes: t.accueil.compte_secondes,
              }}
            />
            <FiletsEtapes etapes={etapes} />
            <CarteAFaire
              titre={t.accueil.a_faire}
              action={action.texte}
              {...(action.lien === undefined ? {} : { lien: action.lien })}
            />
            <Film
              {...(JL_FILM_URL === undefined || JL_FILM_URL === "" ? {} : { url: JL_FILM_URL })}
              {...(JL_FILM_POSTER_URL === undefined || JL_FILM_POSTER_URL === ""
                ? {}
                : { poster: JL_FILM_POSTER_URL })}
              libelles={{
                titre: t.accueil.film_titre,
                attente: t.accueil.film_attente,
                lire: t.accueil.film_lire,
              }}
            />
          </>
        ) : (
          <p className="jl-doux">
            {periode === "jour" ? t.accueil.periode_jour : t.accueil.periode_apres}
          </p>
        )}

        <hr className="jl-filet" />

        <Link
          href="/le-texte"
          className="jl-etiquette jl-cible flex items-center underline decoration-1 underline-offset-8"
        >
          {t.texte.lien}
        </Link>

        <Link
          href="/promesse"
          className="jl-etiquette jl-cible flex items-center underline decoration-1 underline-offset-8"
        >
          {t.promesse.lien}
        </Link>

        {foyer === undefined ? null : (
          <Link
            href="/partager"
            className="jl-etiquette jl-cible flex items-center underline decoration-1 underline-offset-8"
          >
            {t.accueil.partager_lien}
          </Link>
        )}
      </main>
    </>
  );
}
